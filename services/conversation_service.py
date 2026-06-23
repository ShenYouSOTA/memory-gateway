"""
对话管理服务层

封装对话管理的业务逻辑。
"""

from typing import List, Dict, Any, Optional

from repositories.base import ConversationRepository


class ConversationService:
    """对话管理服务"""

    def __init__(self, repo: ConversationRepository):
        self.repo = repo

    async def list_sessions(
        self, page: int = 1, per_page: int = 20
    ) -> Dict[str, Any]:
        """列出对话会话"""
        return await self.repo.list_sessions(page, per_page)

    async def get_messages(
        self, session_id: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """获取对话消息"""
        return await self.repo.get_messages(session_id, limit)

    async def delete_session(self, session_id: str) -> bool:
        """删除对话会话"""
        return await self.repo.delete_session(session_id)

    async def batch_delete_sessions(self, session_ids: List[str]) -> int:
        """批量删除会话"""
        return await self.repo.batch_delete_sessions(session_ids)

    async def search(
        self, query: str, limit: int = 20, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """搜索对话"""
        return await self.repo.search(query, limit, offset)

    async def export_all(self) -> List[Dict[str, Any]]:
        """导出所有对话"""
        return await self.repo.export_all()

    async def import_records(self, records: List[Dict[str, Any]]) -> int:
        """导入对话记录"""
        return await self.repo.import_records(records)

    async def merge_sessions(
        self, source_ids: List[str], target_id: str
    ) -> Dict[str, Any]:
        """合并会话"""
        return await self.repo.merge_sessions(source_ids, target_id)

    async def rename_session(self, old_id: str, new_id: str) -> bool:
        """重命名会话"""
        return await self.repo.rename_session(old_id, new_id)
