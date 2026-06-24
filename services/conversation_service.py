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

    async def update_message_content(self, message_id: int, new_content: str) -> int:
        """更新单条消息内容"""
        return await self.repo.update_message_content(message_id, new_content)

    async def save_message(
        self, session_id: str, role: str, content: str, model: str = "", metadata: str = None
    ) -> int:
        """保存消息"""
        return await self.repo.save_message(session_id, role, content, model, metadata)

    async def get_last_user_content(self, session_id: str) -> str:
        """获取最后一条用户消息"""
        return await self.repo.get_last_user_content(session_id)

    async def update_last_assistant_message(self, session_id: str, content: str) -> bool:
        """更新最后一条助手消息"""
        return await self.repo.update_last_assistant_message(session_id, content)

    @staticmethod
    def db_row_to_message(row: dict) -> dict:
        """把DB记录还原成API消息格式"""
        import json as _json

        msg = {"role": row["role"], "content": row.get("content") or ""}

        meta_str = row.get("metadata")
        if meta_str:
            try:
                meta = _json.loads(meta_str)
                if "tool_calls" in meta:
                    msg["tool_calls"] = meta["tool_calls"]
                    if not row.get("content"):
                        msg["content"] = None
                if "reasoning_content" in meta:
                    msg["reasoning_content"] = meta["reasoning_content"]
                if "tool_call_id" in meta:
                    msg["tool_call_id"] = meta["tool_call_id"]
                if "name" in meta:
                    msg["name"] = meta["name"]
            except Exception:
                pass

        return msg
