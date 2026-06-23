"""
记忆服务层

封装记忆相关的业务逻辑。
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from repositories.base import MemoryRepository
from utils.embedding import compute_embedding, cosine_similarity


class MemoryService:
    """记忆服务"""

    def __init__(self, repo: MemoryRepository):
        self.repo = repo

    async def save_memory(
        self,
        content: str,
        importance: int = 5,
        source_session: str = "",
    ) -> int:
        """保存记忆"""
        return await self.repo.save(content, importance, source_session)

    async def get_memory(self, memory_id: int) -> Optional[Dict[str, Any]]:
        """获取单条记忆"""
        return await self.repo.get_by_id(memory_id)

    async def update_memory(
        self,
        memory_id: int,
        content: Optional[str] = None,
        importance: Optional[int] = None,
    ) -> bool:
        """更新记忆"""
        return await self.repo.update(memory_id, content, importance)

    async def delete_memory(self, memory_id: int) -> bool:
        """删除记忆"""
        return await self.repo.delete(memory_id)

    async def batch_delete_memories(self, memory_ids: List[int]) -> int:
        """批量删除记忆"""
        return await self.repo.batch_delete(memory_ids)

    async def list_memories(
        self,
        limit: Optional[int] = None,
        layer: Optional[int] = None,
        active_only: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """列出记忆"""
        return await self.repo.list_all(limit, layer, active_only)

    async def count_memories(self) -> int:
        """获取记忆总数"""
        return await self.repo.count()

    async def search_memories(
        self,
        query: str,
        limit: int = 10,
        use_vector: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        搜索记忆（混合搜索）

        参数：
            query: 搜索查询
            limit: 返回数量
            use_vector: 是否使用向量搜索

        返回：
            记忆列表，按相关性排序
        """
        # 关键词搜索
        keyword_results = await self.repo.search(query, limit * 3)

        if not use_vector:
            return keyword_results[:limit]

        # 向量搜索（如果启用）
        # TODO: 在 Phase 2 中集成 zvec 向量搜索
        return keyword_results[:limit]

    async def get_recent_memories(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取最近的记忆"""
        return await self.repo.get_recent(limit)

    async def get_layer_statistics(self) -> Dict[str, int]:
        """获取分层统计"""
        return await self.repo.get_layer_statistics()

    async def promote_to_core(self, memory_id: int, title: str = None) -> bool:
        """提升为核心记忆"""
        return await self.repo.promote_to_core(memory_id, title)

    async def deactivate_memories(self, memory_ids: List[int]) -> bool:
        """停用记忆"""
        return await self.repo.deactivate(memory_ids)

    async def merge_memories(
        self,
        source_ids: List[int],
        content: str,
        importance: int = 5,
        title: str = None,
    ) -> Optional[int]:
        """合并记忆"""
        return await self.repo.merge(source_ids, content, importance, title)

    async def check_duplicate(
        self, content: str, threshold: float = 0.7
    ) -> Dict[str, Any]:
        """检查重复记忆"""
        return await self.repo.check_duplicate(content, threshold)
