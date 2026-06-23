"""
PostgreSQL 对话存储实现

实现 ConversationRepository 接口，使用 PostgreSQL 存储对话数据。
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

import asyncpg

from .base import ConversationRepository


class PostgresConversationRepository(ConversationRepository):
    """PostgreSQL 对话存储实现"""

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        model: str = "",
        metadata: str = None,
    ) -> int:
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO conversations (session_id, role, content, model, metadata) VALUES ($1, $2, $3, $4, $5)",
                session_id,
                role,
                content,
                model,
                metadata,
            )
            return 0  # 不返回 ID，保持向后兼容

    async def get_messages(
        self, session_id: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM conversations WHERE session_id = $1 ORDER BY created_at DESC LIMIT $2",
                session_id,
                limit,
            )
            return [dict(r) for r in reversed(rows)]

    async def get_last_user_content(self, session_id: str) -> str:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT content FROM conversations
                WHERE session_id = $1 AND role = 'user'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                session_id,
            )
            return row["content"] if row else ""

    async def update_last_assistant_message(
        self, session_id: str, content: str
    ) -> bool:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE conversations SET content = $1
                WHERE id = (
                    SELECT id FROM conversations
                    WHERE session_id = $2 AND role = 'assistant'
                    ORDER BY created_at DESC
                    LIMIT 1
                )
                """,
                content,
                session_id,
            )
            return True

    async def list_sessions(
        self, page: int = 1, per_page: int = 20
    ) -> Dict[str, Any]:
        async with self.pool.acquire() as conn:
            offset = (page - 1) * per_page

            # 获取总数
            count_row = await conn.fetchrow(
                "SELECT COUNT(DISTINCT session_id) as cnt FROM conversations"
            )
            total = count_row["cnt"]

            # 获取会话列表
            rows = await conn.fetch(
                """
                SELECT session_id, MAX(created_at) as last_active,
                       COUNT(*) as message_count
                FROM conversations
                GROUP BY session_id
                ORDER BY last_active DESC
                LIMIT $1 OFFSET $2
                """,
                per_page,
                offset,
            )

            return {
                "conversations": [dict(r) for r in rows],
                "total": total,
                "page": page,
                "per_page": per_page,
            }

    async def delete_session(self, session_id: str) -> bool:
        async with self.pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM conversations WHERE session_id = $1", session_id
            )
            return True

    async def batch_delete_sessions(self, session_ids: List[str]) -> int:
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM conversations WHERE session_id = ANY($1)", session_ids
            )
            return int(result.split()[-1]) if result else 0

    async def merge_sessions(
        self, source_ids: List[str], target_id: str
    ) -> Dict[str, Any]:
        async with self.pool.acquire() as conn:
            # 将源会话的消息移动到目标会话
            await conn.execute(
                "UPDATE conversations SET session_id = $1 WHERE session_id = ANY($2)",
                target_id,
                source_ids,
            )
            return {"merged": len(source_ids), "target": target_id}

    async def search(
        self, query: str, limit: int = 20, offset: int = 0
    ) -> List[Dict[str, Any]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT DISTINCT session_id, MAX(created_at) as last_active
                FROM conversations
                WHERE content ILIKE '%' || $1 || '%'
                GROUP BY session_id
                ORDER BY last_active DESC
                LIMIT $2 OFFSET $3
                """,
                query,
                limit,
                offset,
            )
            return [dict(r) for r in rows]

    async def rename_session(self, old_id: str, new_id: str) -> bool:
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE conversations SET session_id = $1 WHERE session_id = $2",
                new_id,
                old_id,
            )
            return True

    async def export_all(self) -> List[Dict[str, Any]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM conversations ORDER BY session_id, created_at"
            )
            return [dict(r) for r in rows]

    async def import_records(self, records: List[Dict[str, Any]]) -> int:
        async with self.pool.acquire() as conn:
            count = 0
            for record in records:
                try:
                    await conn.execute(
                        "INSERT INTO conversations (session_id, role, content, model, metadata) VALUES ($1, $2, $3, $4, $5)",
                        record["session_id"],
                        record["role"],
                        record.get("content"),
                        record.get("model", ""),
                        record.get("metadata"),
                    )
                    count += 1
                except Exception:
                    continue
            return count
