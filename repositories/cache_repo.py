"""
PostgreSQL 缓存状态存储实现

实现 CacheStateRepository 接口，使用 PostgreSQL 存储分区缓存状态。
"""

import json
from typing import Dict, Any, List, Optional

import asyncpg

from .base import CacheStateRepository


class PostgresCacheStateRepository(CacheStateRepository):
    """PostgreSQL 缓存状态存储实现"""

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def get_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT summary, a_start_round, updated_at FROM session_cache_state WHERE session_id = $1",
                session_id,
            )
            if row:
                raw_summary = row["summary"] or ""
                summary_parts = []
                if raw_summary:
                    try:
                        parsed = json.loads(raw_summary)
                        if isinstance(parsed, list):
                            summary_parts = parsed
                        else:
                            summary_parts = [raw_summary]
                    except (json.JSONDecodeError, ValueError):
                        summary_parts = [raw_summary]
                return {
                    "summary_parts": summary_parts,
                    "a_start_round": row["a_start_round"] or 0,
                    "updated_at": row["updated_at"],
                }
            return {"summary_parts": [], "a_start_round": 0, "updated_at": None}

    async def save_state(
        self,
        session_id: str,
        summary: str = "",
        a_start_round: int = 0,
    ) -> None:
        # summary 可能是纯文本或 JSON 字符串，统一存储为 JSON 数组
        if summary:
            try:
                parsed = json.loads(summary)
                if isinstance(parsed, list):
                    summary_json = json.dumps(parsed, ensure_ascii=False)
                else:
                    summary_json = json.dumps([summary], ensure_ascii=False)
            except (json.JSONDecodeError, ValueError):
                summary_json = json.dumps([summary], ensure_ascii=False)
        else:
            summary_json = "[]"

        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO session_cache_state (session_id, summary, a_start_round, updated_at)
                VALUES ($1, $2, $3, NOW())
                ON CONFLICT (session_id)
                DO UPDATE SET summary = $2, a_start_round = $3, updated_at = NOW()
                """,
                session_id,
                summary_json,
                a_start_round,
            )

    async def delete_state(self, session_id: str) -> bool:
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM session_cache_state WHERE session_id = $1", session_id
            )
            return result.endswith("1")

    async def list_all(self) -> List[Dict[str, Any]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT scs.session_id, scs.summary, scs.a_start_round, scs.updated_at,
                       COALESCE(c.message_count, 0) as message_count,
                       COALESCE(tu.chat_tokens, 0) as chat_tokens
                FROM session_cache_state scs
                LEFT JOIN (SELECT session_id, COUNT(*) as message_count FROM conversations GROUP BY session_id) c ON scs.session_id = c.session_id
                LEFT JOIN (SELECT session_id, SUM(total_tokens) as chat_tokens FROM token_usage WHERE usage_type = 'chat' GROUP BY session_id) tu ON scs.session_id = tu.session_id
                ORDER BY scs.updated_at DESC
            """)
            results = []
            for r in rows:
                raw_summary = r["summary"] or ""
                try:
                    parsed = json.loads(raw_summary)
                    if isinstance(parsed, list):
                        summary_parts = parsed
                    else:
                        summary_parts = [raw_summary] if raw_summary else []
                except (json.JSONDecodeError, ValueError):
                    summary_parts = [raw_summary] if raw_summary else []
                results.append(
                    {
                        "session_id": r["session_id"],
                        "summary": "\n\n".join(summary_parts),
                        "summary_length": sum(len(p) for p in summary_parts),
                        "summary_count": len(summary_parts),
                        "a_start_round": r["a_start_round"],
                        "updated_at": r["updated_at"].isoformat()
                        if r["updated_at"]
                        else None,
                        "message_count": r["message_count"],
                        "chat_tokens": r["chat_tokens"],
                    }
                )
            return results
