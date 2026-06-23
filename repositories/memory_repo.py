"""
PostgreSQL 记忆存储实现

实现 MemoryRepository 接口，使用 PostgreSQL 存储记忆数据。
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

import asyncpg

from .base import MemoryRepository


class PostgresMemoryRepository(MemoryRepository):
    """PostgreSQL 记忆存储实现"""

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def save(
        self, content: str, importance: int = 5, source_session: str = ""
    ) -> int:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO memories (content, importance, source_session) VALUES ($1, $2, $3) RETURNING id",
                content,
                importance,
                source_session,
            )
            return row["id"]

    async def get_by_id(self, memory_id: int) -> Optional[Dict[str, Any]]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM memories WHERE id = $1", memory_id
            )
            return dict(row) if row else None

    async def update(
        self,
        memory_id: int,
        content: Optional[str] = None,
        importance: Optional[int] = None,
    ) -> bool:
        async with self.pool.acquire() as conn:
            if content is not None:
                await conn.execute(
                    "UPDATE memories SET content = $1 WHERE id = $2",
                    content,
                    memory_id,
                )
            if importance is not None:
                await conn.execute(
                    "UPDATE memories SET importance = $1 WHERE id = $2",
                    importance,
                    memory_id,
                )
            return True

    async def delete(self, memory_id: int) -> bool:
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM memories WHERE id = $1", memory_id
            )
            return result.endswith("1")

    async def batch_delete(self, memory_ids: List[int]) -> int:
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM memories WHERE id = ANY($1)", memory_ids
            )
            # 提取删除数量
            return int(result.split()[-1]) if result else 0

    async def list_all(
        self,
        limit: Optional[int] = None,
        layer: Optional[int] = None,
        active_only: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        async with self.pool.acquire() as conn:
            conditions = []
            params = []
            idx = 1

            if layer is not None:
                conditions.append(f"layer = ${idx}")
                params.append(layer)
                idx += 1

            if active_only:
                conditions.append("is_active = TRUE")

            where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            limit_clause = f"LIMIT ${idx}" if limit else ""

            if limit:
                params.append(limit)

            sql = f"SELECT * FROM memories {where} ORDER BY id {limit_clause}"
            rows = await conn.fetch(sql, *params)
            return [dict(r) for r in rows]

    async def count(self) -> int:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT COUNT(*) as cnt FROM memories")
            return row["cnt"]

    async def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """关键词搜索（简化版，完整实现在 MemoryService 中）"""
        from ..utils.text import extract_search_keywords

        keywords = extract_search_keywords(query)
        if not keywords:
            return []

        async with self.pool.acquire() as conn:
            case_parts = []
            params = []
            for i, kw in enumerate(keywords):
                case_parts.append(
                    f"CASE WHEN content ILIKE '%' || ${i + 1} || '%' THEN 1 ELSE 0 END"
                )
                params.append(kw)

            hit_count_expr = " + ".join(case_parts)
            max_hits = len(keywords)
            where_parts = [
                f"content ILIKE '%' || ${i + 1} || '%'" for i in range(len(keywords))
            ]
            where_clause = f"is_active = TRUE AND ({' OR '.join(where_parts)})"

            limit_idx = len(keywords) + 1
            params.append(limit * 3)

            sql = f"""
                SELECT id, content, importance, created_at, last_accessed, is_active, layer, title,
                       ({hit_count_expr}) AS hit_count,
                       ({hit_count_expr})::float / {max_hits}.0 AS kw_score
                FROM memories
                WHERE {where_clause}
                ORDER BY kw_score DESC
                LIMIT ${limit_idx}
            """
            rows = await conn.fetch(sql, *params)
            return [dict(r) for r in rows]

    async def get_recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM memories ORDER BY created_at DESC LIMIT $1",
                limit,
            )
            return [dict(r) for r in rows]

    async def get_layer_statistics(self) -> Dict[str, int]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT layer, COUNT(*) as cnt FROM memories WHERE is_active = TRUE GROUP BY layer"
            )
            stats = {"layer1": 0, "layer2": 0, "layer3": 0}
            for row in rows:
                layer = row["layer"]
                if layer == 1:
                    stats["layer1"] = row["cnt"]
                elif layer == 2:
                    stats["layer2"] = row["cnt"]
                elif layer == 3:
                    stats["layer3"] = row["cnt"]
            return stats

    async def promote_to_core(self, memory_id: int, title: str = None) -> bool:
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE memories SET layer = 3, title = $1 WHERE id = $2",
                title,
                memory_id,
            )
            return True

    async def deactivate(self, memory_ids: List[int]) -> bool:
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE memories SET is_active = FALSE WHERE id = ANY($1)",
                memory_ids,
            )
            return True

    async def merge(
        self,
        source_ids: List[int],
        content: str,
        importance: int = 5,
        title: str = None,
    ) -> Optional[int]:
        async with self.pool.acquire() as conn:
            # 创建新记忆
            row = await conn.fetchrow(
                "INSERT INTO memories (content, importance, layer, title, merged_from) VALUES ($1, $2, 2, $3, $4) RETURNING id",
                content,
                importance,
                title,
                source_ids,
            )
            new_id = row["id"]

            # 停用源记忆
            await conn.execute(
                "UPDATE memories SET is_active = FALSE WHERE id = ANY($1)",
                source_ids,
            )

            return new_id

    async def check_duplicate(
        self, content: str, threshold: float = 0.7
    ) -> Dict[str, Any]:
        async with self.pool.acquire() as conn:
            # 简单的关键词匹配检查
            rows = await conn.fetch(
                "SELECT id, content, importance FROM memories WHERE is_active = TRUE AND content ILIKE '%' || $1 || '%' LIMIT 5",
                content[:50],
            )
            return {
                "is_duplicate": len(rows) > 0,
                "similar_memories": [dict(r) for r in rows],
            }
