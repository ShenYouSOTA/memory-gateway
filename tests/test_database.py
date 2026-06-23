"""
database.py 单元测试（使用 mock）
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone
from contextlib import asynccontextmanager


class MockAcquireContext:
    """模拟 asyncpg 的 acquire 上下文管理器"""

    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


def create_mock_pool(conn):
    """创建模拟的连接池"""
    mock_pool = AsyncMock()
    mock_pool.acquire = MagicMock(return_value=MockAcquireContext(conn))
    return mock_pool


class TestGetPool:
    """测试 get_pool 函数"""

    @pytest.mark.asyncio
    async def test_get_pool_no_database_url(self):
        """无 DATABASE_URL 时抛出异常"""
        with patch("database._pool", None):
            with patch("database.DATABASE_URL", ""):
                from database import get_pool
                with pytest.raises(RuntimeError, match="DATABASE_URL 未设置"):
                    await get_pool()


class TestSaveMemory:
    """测试 save_memory 函数"""

    @pytest.mark.asyncio
    async def test_save_memory_success(self):
        """成功保存记忆"""
        mock_conn = AsyncMock()
        mock_row = MagicMock()
        mock_row.__getitem__ = MagicMock(return_value=1)
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)
        mock_pool = create_mock_pool(mock_conn)

        with patch("database.get_pool", return_value=mock_pool):
            with patch("database.MEMORY_VECTOR_ENABLED", False):
                from database import save_memory
                await save_memory("测试记忆", importance=7, source_session="test-session")

                mock_conn.fetchrow.assert_called_once()


class TestSearchMemories:
    """测试 search_memories 函数"""

    @pytest.mark.asyncio
    async def test_search_memories_empty_query(self):
        """空查询返回空列表"""
        with patch("database.get_pool"):
            from database import search_memories
            result = await search_memories("")
            assert result == []


class TestGetAllMemoriesCount:
    """测试 get_all_memories_count 函数"""

    @pytest.mark.asyncio
    async def test_returns_count(self):
        """返回记忆总数"""
        mock_conn = AsyncMock()
        mock_row = MagicMock()
        mock_row.__getitem__ = MagicMock(return_value=5)
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)
        mock_pool = create_mock_pool(mock_conn)

        with patch("database.get_pool", return_value=mock_pool):
            from database import get_all_memories_count
            result = await get_all_memories_count()

            assert result == 5


class TestGetRecentMemories:
    """测试 get_recent_memories 函数"""

    @pytest.mark.asyncio
    async def test_returns_recent_memories(self):
        """返回最近的记忆"""
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(
            return_value=[
                MagicMock(
                    id=1,
                    content="记忆1",
                    importance=5,
                    created_at=datetime.now(timezone.utc),
                ),
                MagicMock(
                    id=2,
                    content="记忆2",
                    importance=6,
                    created_at=datetime.now(timezone.utc),
                ),
            ]
        )
        mock_pool = create_mock_pool(mock_conn)

        with patch("database.get_pool", return_value=mock_pool):
            from database import get_recent_memories
            result = await get_recent_memories(limit=2)

            assert isinstance(result, list)
            assert len(result) == 2


class TestGetGatewayConfig:
    """测试 get_gateway_config 函数"""

    @pytest.mark.asyncio
    async def test_get_existing_config(self):
        """获取存在的配置"""
        mock_conn = AsyncMock()
        mock_row = MagicMock()
        mock_row.__getitem__ = MagicMock(return_value="test_value")
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)
        mock_pool = create_mock_pool(mock_conn)

        with patch("database.get_pool", return_value=mock_pool):
            from database import get_gateway_config
            result = await get_gateway_config("test_key", "default")

            assert result == "test_value"

    @pytest.mark.asyncio
    async def test_get_missing_config_returns_default(self):
        """获取不存在的配置返回默认值"""
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_pool = create_mock_pool(mock_conn)

        with patch("database.get_pool", return_value=mock_pool):
            from database import get_gateway_config
            result = await get_gateway_config("missing_key", "default")

            assert result == "default"


class TestSetGatewayConfig:
    """测试 set_gateway_config 函数"""

    @pytest.mark.asyncio
    async def test_set_config(self):
        """设置配置"""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_pool = create_mock_pool(mock_conn)

        with patch("database.get_pool", return_value=mock_pool):
            from database import set_gateway_config
            await set_gateway_config("test_key", "test_value")

            mock_conn.execute.assert_called_once()


class TestDeleteMemory:
    """测试 delete_memory 函数"""

    @pytest.mark.asyncio
    async def test_delete_memory(self):
        """删除记忆"""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="DELETE 1")
        mock_pool = create_mock_pool(mock_conn)

        with patch("database.get_pool", return_value=mock_pool):
            from database import delete_memory
            await delete_memory(1)

            mock_conn.execute.assert_called_once()


class TestUpdateMemory:
    """测试 update_memory 函数"""

    @pytest.mark.asyncio
    async def test_update_memory_content(self):
        """更新记忆内容"""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="UPDATE 1")
        mock_pool = create_mock_pool(mock_conn)

        with patch("database.get_pool", return_value=mock_pool):
            from database import update_memory
            await update_memory(1, content="新内容")

            mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_memory_importance(self):
        """更新记忆重要性"""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="UPDATE 1")
        mock_pool = create_mock_pool(mock_conn)

        with patch("database.get_pool", return_value=mock_pool):
            from database import update_memory
            await update_memory(1, importance=9)

            mock_conn.execute.assert_called_once()


class TestSaveMessage:
    """测试 save_message 函数"""

    @pytest.mark.asyncio
    async def test_save_message(self):
        """保存消息"""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_pool = create_mock_pool(mock_conn)

        with patch("database.get_pool", return_value=mock_pool):
            from database import save_message
            await save_message(
                session_id="test-session",
                role="user",
                content="测试消息",
                model="test-model",
            )

            mock_conn.execute.assert_called_once()


class TestDeleteMemoriesBatch:
    """测试 delete_memories_batch 函数"""

    @pytest.mark.asyncio
    async def test_batch_delete(self):
        """批量删除记忆"""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="DELETE 3")
        mock_pool = create_mock_pool(mock_conn)

        with patch("database.get_pool", return_value=mock_pool):
            from database import delete_memories_batch
            await delete_memories_batch([1, 2, 3])

            mock_conn.execute.assert_called_once()


class TestGetConversationMessages:
    """测试 get_conversation_messages 函数"""

    @pytest.mark.asyncio
    async def test_get_messages(self):
        """获取对话消息"""
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(
            return_value=[
                MagicMock(
                    id=1,
                    session_id="test-session",
                    role="user",
                    content="测试消息",
                    model="test-model",
                    created_at=datetime.now(timezone.utc),
                )
            ]
        )
        mock_pool = create_mock_pool(mock_conn)

        with patch("database.get_pool", return_value=mock_pool):
            from database import get_conversation_messages
            result = await get_conversation_messages("test-session", limit=10)

            assert isinstance(result, list)
            assert len(result) == 1
