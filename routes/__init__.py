"""路由层 - HTTP 请求处理"""

from .chat import router as chat_router
from .memories import router as memories_router
from .conversations import router as conversations_router
from .settings import router as settings_router
from .partition import router as partition_router
from .admin import router as admin_router

__all__ = [
    "chat_router",
    "memories_router",
    "conversations_router",
    "settings_router",
    "partition_router",
    "admin_router",
]
