"""
缓存服务层

封装分区缓存的业务逻辑。
"""

import os
from typing import Optional, Dict, Any, List

from repositories.base import CacheStateRepository


class CacheService:
    """缓存服务"""

    def __init__(self, cache_repo: CacheStateRepository):
        self.cache_repo = cache_repo

        # 配置
        self.enabled = os.getenv("CACHE_PARTITION_ENABLED", "false").lower() == "true"
        self.partition_x = int(os.getenv("CACHE_PARTITION_X", "15"))

    async def get_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取缓存状态"""
        if not self.enabled:
            return None
        return await self.cache_repo.get_state(session_id)

    async def save_state(
        self,
        session_id: str,
        summary: str = "",
        a_start_round: int = 0,
    ) -> None:
        """保存缓存状态"""
        if not self.enabled:
            return
        await self.cache_repo.save_state(session_id, summary, a_start_round)

    async def delete_state(self, session_id: str) -> bool:
        """删除缓存状态"""
        return await self.cache_repo.delete_state(session_id)

    async def list_all_states(self) -> List[Dict[str, Any]]:
        """列出所有缓存状态"""
        return await self.cache_repo.list_all()

    async def should_rotate(self, session_id: str, current_round: int) -> bool:
        """判断是否需要轮转"""
        if not self.enabled:
            return False

        state = await self.cache_repo.get_state(session_id)
        if not state:
            return False

        # 每 partition_x 轮轮转一次
        return (current_round - state.get("a_start_round", 0)) >= self.partition_x

    async def get_summary(self, session_id: str) -> str:
        """获取摘要"""
        state = await self.cache_repo.get_state(session_id)
        return state.get("summary", "") if state else ""

    async def update_summary(self, session_id: str, summary: str) -> None:
        """更新摘要"""
        state = await self.cache_repo.get_state(session_id) or {}
        await self.cache_repo.save_state(
            session_id,
            summary=summary,
            a_start_round=state.get("a_start_round", 0),
        )
