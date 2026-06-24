"""
记忆服务层

封装记忆相关的业务逻辑。
"""

import os
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from repositories.base import MemoryRepository, VectorRepository
from utils.embedding import compute_embedding, cosine_similarity

# 混合搜索权重
MEMORY_HW_KEYWORD = float(os.getenv("MEMORY_HW_KEYWORD", "0.35"))
MEMORY_HW_SEMANTIC = float(os.getenv("MEMORY_HW_SEMANTIC", "0.35"))
MEMORY_HW_IMPORTANCE = float(os.getenv("MEMORY_HW_IMPORTANCE", "0.15"))
MEMORY_HW_RECENCY = float(os.getenv("MEMORY_HW_RECENCY", "0.15"))
MEMORY_SEMANTIC_THRESHOLD = float(os.getenv("MEMORY_SEMANTIC_THRESHOLD", "0.5"))
MIN_SCORE_THRESHOLD = float(os.getenv("MIN_SCORE_THRESHOLD", "0.15"))


class MemoryService:
    """记忆服务"""

    def __init__(self, repo: MemoryRepository, vector_repo: VectorRepository = None):
        self.repo = repo
        self.vector_repo = vector_repo

    async def save_memory(
        self,
        content: str,
        importance: int = 5,
        source_session: str = "",
    ) -> int:
        """保存记忆（双写 PG + zvec）"""
        memory_id = await self.repo.save(content, importance, source_session)

        # zvec 双写
        if self.vector_repo and memory_id:
            try:
                embedding = await compute_embedding(content)
                if embedding:
                    await self.vector_repo.insert(
                        id=str(memory_id),
                        vector=embedding,
                        metadata={
                            "content": content,
                            "importance": importance,
                        },
                    )
            except Exception as e:
                print(f"⚠️ zvec 双写失败（PG 已保存）: {e}")

        return memory_id

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

        # 如果没有向量存储或未启用向量搜索，返回关键词结果
        if not use_vector or not self.vector_repo:
            return keyword_results[:limit]

        # 混合搜索：关键词 + 向量
        try:
            query_embedding = await compute_embedding(query)
            if not query_embedding:
                return keyword_results[:limit]

            # 向量搜索
            vector_results = await self.vector_repo.search(
                query_embedding, topk=limit * 3
            )

            # 合并结果
            return await self._merge_search_results(
                keyword_results, vector_results, limit
            )

        except Exception as e:
            print(f"⚠️ 向量搜索失败，回退到关键词搜索: {e}")
            return keyword_results[:limit]

    async def _merge_search_results(
        self,
        keyword_results: List[Dict[str, Any]],
        vector_results: List[Dict[str, Any]],
        limit: int,
    ) -> List[Dict[str, Any]]:
        """合并关键词和向量搜索结果"""
        now = datetime.now(timezone.utc)

        # 构建候选集
        candidates = {}

        # 关键词结果
        for r in keyword_results:
            mid = r.get("id")
            if mid:
                candidates[mid] = {
                    "content": r.get("content", ""),
                    "importance": r.get("importance", 5),
                    "created_at": r.get("created_at"),
                    "kw_score": r.get("score", 0.0),
                    "similarity": 0.0,
                }

        # 向量结果
        for r in vector_results:
            mid = r.get("id")
            if mid:
                sim = r.get("score", 0.0)
                if sim < MEMORY_SEMANTIC_THRESHOLD:
                    continue
                if mid in candidates:
                    candidates[mid]["similarity"] = sim
                else:
                    candidates[mid] = {
                        "content": r.get("content", ""),
                        "importance": r.get("importance", 5),
                        "created_at": r.get("created_at"),
                        "kw_score": 0.0,
                        "similarity": sim,
                    }

        if not candidates:
            return []

        # 归一化
        kw_scores = {mid: v["kw_score"] for mid, v in candidates.items()}
        sem_scores = {mid: v["similarity"] for mid, v in candidates.items()}
        kw_norm = self._min_max_normalize(kw_scores)
        sem_norm = self._min_max_normalize(sem_scores)

        # 计算最终分数
        final = []
        for mid, info in candidates.items():
            kw = kw_norm.get(mid, 0.0)
            sem = sem_norm.get(mid, 0.0)
            imp = info["importance"] / 10.0

            # 时间衰减
            if info["created_at"]:
                days = (now - info["created_at"]).total_seconds() / 86400.0
                rec = 1.0 / (1.0 + days)
            else:
                rec = 0.0

            score = (
                MEMORY_HW_KEYWORD * kw
                + MEMORY_HW_SEMANTIC * sem
                + MEMORY_HW_IMPORTANCE * imp
                + MEMORY_HW_RECENCY * rec
            )

            final.append(
                {
                    "id": mid,
                    "content": info["content"],
                    "importance": info["importance"],
                    "created_at": info["created_at"],
                    "score": score,
                }
            )

        # 排序和过滤
        final.sort(key=lambda x: (-x["score"], -x["importance"]))

        if MIN_SCORE_THRESHOLD > 0:
            final = [r for r in final if r["score"] >= MIN_SCORE_THRESHOLD]

        return final[:limit]

    def _min_max_normalize(self, scores: Dict[int, float]) -> Dict[int, float]:
        """Min-Max 归一化"""
        if not scores:
            return {}

        values = list(scores.values())
        min_val = min(values)
        max_val = max(values)

        if max_val == min_val:
            return {k: 1.0 for k in scores}

        return {k: (v - min_val) / (max_val - min_val) for k, v in scores.items()}

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

    async def update_full(
        self,
        memory_id: int,
        content: Optional[str] = None,
        importance: Optional[int] = None,
        title: Optional[str] = None,
        layer: Optional[int] = None,
        is_active: Optional[bool] = None,
    ) -> None:
        """更新记忆（支持三层架构全部字段）"""
        await self.repo.update_full(memory_id, content, importance, title, layer, is_active)

    async def cleanup_fragments(self, days: int = 30) -> int:
        """清理指定天数前的归档碎片"""
        return await self.repo.cleanup_fragments(days)

    async def revert_merge(self, memory_id: int) -> Dict[str, Any]:
        """撤回合并操作"""
        return await self.repo.revert_merge(memory_id)
