"""
Repository 接口定义

定义数据访问层的抽象接口，业务层只依赖这些接口，不关心具体实现。
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime


class MemoryRepository(ABC):
    """记忆存储接口"""

    @abstractmethod
    async def save(
        self, content: str, importance: int = 5, source_session: str = ""
    ) -> int:
        """保存记忆，返回 ID"""
        ...

    @abstractmethod
    async def get_by_id(self, memory_id: int) -> Optional[Dict[str, Any]]:
        """获取单条记忆"""
        ...

    @abstractmethod
    async def update(
        self,
        memory_id: int,
        content: Optional[str] = None,
        importance: Optional[int] = None,
    ) -> bool:
        """更新记忆"""
        ...

    @abstractmethod
    async def delete(self, memory_id: int) -> bool:
        """删除单条记忆"""
        ...

    @abstractmethod
    async def batch_delete(self, memory_ids: List[int]) -> int:
        """批量删除记忆，返回删除数量"""
        ...

    @abstractmethod
    async def list_all(
        self,
        limit: Optional[int] = None,
        layer: Optional[int] = None,
        active_only: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """列出所有记忆"""
        ...

    @abstractmethod
    async def count(self) -> int:
        """获取记忆总数"""
        ...

    @abstractmethod
    async def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """搜索记忆（关键词 + 向量混合搜索）"""
        ...

    @abstractmethod
    async def get_recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取最近的记忆"""
        ...

    @abstractmethod
    async def get_layer_statistics(self) -> Dict[str, int]:
        """获取分层统计"""
        ...

    @abstractmethod
    async def promote_to_core(self, memory_id: int, title: str = None) -> bool:
        """提升为核心记忆"""
        ...

    @abstractmethod
    async def deactivate(self, memory_ids: List[int]) -> bool:
        """停用记忆（软删除）"""
        ...

    @abstractmethod
    async def merge(
        self,
        source_ids: List[int],
        content: str,
        importance: int = 5,
        title: str = None,
    ) -> Optional[int]:
        """合并多条记忆，返回新记忆 ID"""
        ...

    @abstractmethod
    async def check_duplicate(
        self, content: str, threshold: float = 0.7
    ) -> Dict[str, Any]:
        """检查重复记忆"""
        ...

    @abstractmethod
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
        ...

    @abstractmethod
    async def cleanup_fragments(self, days: int = 30) -> int:
        """清理指定天数前的归档碎片，返回删除数量"""
        ...

    @abstractmethod
    async def revert_merge(self, memory_id: int) -> Dict[str, Any]:
        """撤回合并操作，恢复原始碎片"""
        ...


class ConversationRepository(ABC):
    """对话存储接口"""

    @abstractmethod
    async def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        model: str = "",
        metadata: str = None,
    ) -> int:
        """保存消息，返回 ID"""
        ...

    @abstractmethod
    async def get_messages(
        self, session_id: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """获取对话消息"""
        ...

    @abstractmethod
    async def get_last_user_content(self, session_id: str) -> str:
        """获取最后一条用户消息"""
        ...

    @abstractmethod
    async def update_last_assistant_message(
        self, session_id: str, content: str
    ) -> bool:
        """更新最后一条助手消息"""
        ...

    @abstractmethod
    async def list_sessions(
        self, page: int = 1, per_page: int = 20
    ) -> Dict[str, Any]:
        """列出对话会话（分页）"""
        ...

    @abstractmethod
    async def delete_session(self, session_id: str) -> bool:
        """删除对话会话"""
        ...

    @abstractmethod
    async def batch_delete_sessions(self, session_ids: List[str]) -> int:
        """批量删除会话，返回删除数量"""
        ...

    @abstractmethod
    async def merge_sessions(
        self, source_ids: List[str], target_id: str
    ) -> Dict[str, Any]:
        """合并会话"""
        ...

    @abstractmethod
    async def search(self, query: str, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        """搜索对话"""
        ...

    @abstractmethod
    async def rename_session(self, old_id: str, new_id: str) -> bool:
        """重命名会话"""
        ...

    @abstractmethod
    async def export_all(self) -> List[Dict[str, Any]]:
        """导出所有对话"""
        ...

    @abstractmethod
    async def import_records(self, records: List[Dict[str, Any]]) -> int:
        """导入对话记录，返回导入数量"""
        ...

    @abstractmethod
    async def update_message_content(self, message_id: int, new_content: str) -> int:
        """更新单条消息内容，返回影响行数"""
        ...


class ConfigRepository(ABC):
    """配置存储接口"""

    @abstractmethod
    async def get(self, key: str, default: str = "") -> str:
        """获取配置值"""
        ...

    @abstractmethod
    async def set(self, key: str, value: str) -> None:
        """设置配置值"""
        ...

    @abstractmethod
    async def get_all(self) -> Dict[str, str]:
        """获取所有配置"""
        ...


class VectorRepository(ABC):
    """向量存储接口"""

    @abstractmethod
    async def init(self) -> None:
        """初始化向量存储"""
        ...

    @abstractmethod
    async def insert(self, id: str, vector: List[float], metadata: Dict[str, Any]) -> bool:
        """插入向量"""
        ...

    @abstractmethod
    async def search(self, vector: List[float], topk: int = 10) -> List[Dict[str, Any]]:
        """向量相似度搜索"""
        ...

    @abstractmethod
    async def delete(self, id: str) -> bool:
        """删除向量"""
        ...

    @abstractmethod
    async def batch_insert(self, items: List[Dict[str, Any]]) -> int:
        """批量插入，返回成功数量"""
        ...


class CacheStateRepository(ABC):
    """缓存状态存储接口"""

    @abstractmethod
    async def get_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取缓存状态"""
        ...

    @abstractmethod
    async def save_state(
        self,
        session_id: str,
        summary: str = "",
        a_start_round: int = 0,
    ) -> None:
        """保存缓存状态"""
        ...

    @abstractmethod
    async def delete_state(self, session_id: str) -> bool:
        """删除缓存状态"""
        ...

    @abstractmethod
    async def list_all(self) -> List[Dict[str, Any]]:
        """列出所有缓存状态"""
        ...
