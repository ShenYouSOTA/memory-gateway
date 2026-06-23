"""
PostgreSQL 配置存储实现

实现 ConfigRepository 接口，使用 PostgreSQL 存储配置数据。
"""

from typing import Dict

import asyncpg

from .base import ConfigRepository


class PostgresConfigRepository(ConfigRepository):
    """PostgreSQL 配置存储实现"""

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def get(self, key: str, default: str = "") -> str:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT value FROM gateway_config WHERE key = $1", key
            )
            return row["value"] if row else default

    async def set(self, key: str, value: str) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO gateway_config (key, value) VALUES ($1, $2)
                ON CONFLICT (key) DO UPDATE SET value = $2
                """,
                key,
                value,
            )

    async def get_all(self) -> Dict[str, str]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT key, value FROM gateway_config")
            return {row["key"]: row["value"] for row in rows}
