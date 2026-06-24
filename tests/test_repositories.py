"""
Repository 层单元测试（使用 mock）
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone


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
    mock_pool = MagicMock()
    mock_pool.acquire = MagicMock(return_value=MockAcquireContext(conn))
    return mock_pool


# ============================================================
# PostgresMemoryRepository
# ============================================================

class TestPostgresMemoryRepositorySave:
    """测试 PostgresMemoryRepository.save"""

    @pytest.mark.asyncio
    async def test_save_returns_id(self):
        mock_conn = AsyncMock()
        mock_row = MagicMock()
        mock_row.__getitem__ = MagicMock(return_value=42)
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)
        pool = create_mock_pool(mock_conn)

        from repositories.memory_repo import PostgresMemoryRepository
        repo = PostgresMemoryRepository(pool)
        result = await repo.save("测试内容", importance=7, source_session="s1")

        assert result == 42
        mock_conn.fetchrow.assert_called_once()


class TestPostgresMemoryRepositoryGetById:
    """测试 PostgresMemoryRepository.get_by_id"""

    @pytest.mark.asyncio
    async def test_returns_dict_when_found(self):
        mock_conn = AsyncMock()
        mock_row = {"id": 1, "content": "记忆", "importance": 5}
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)
        pool = create_mock_pool(mock_conn)

        from repositories.memory_repo import PostgresMemoryRepository
        repo = PostgresMemoryRepository(pool)
        result = await repo.get_by_id(1)

        assert result == {"id": 1, "content": "记忆", "importance": 5}

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        pool = create_mock_pool(mock_conn)

        from repositories.memory_repo import PostgresMemoryRepository
        repo = PostgresMemoryRepository(pool)
        result = await repo.get_by_id(999)

        assert result is None


class TestPostgresMemoryRepositoryUpdate:
    """测试 PostgresMemoryRepository.update"""

    @pytest.mark.asyncio
    async def test_update_content(self):
        mock_conn = AsyncMock()
        pool = create_mock_pool(mock_conn)

        from repositories.memory_repo import PostgresMemoryRepository
        repo = PostgresMemoryRepository(pool)
        result = await repo.update(1, content="新内容")

        assert result is True
        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_importance(self):
        mock_conn = AsyncMock()
        pool = create_mock_pool(mock_conn)

        from repositories.memory_repo import PostgresMemoryRepository
        repo = PostgresMemoryRepository(pool)
        result = await repo.update(1, importance=9)

        assert result is True
        mock_conn.execute.assert_called_once()


class TestPostgresMemoryRepositoryDelete:
    """测试 PostgresMemoryRepository.delete"""

    @pytest.mark.asyncio
    async def test_delete_returns_true(self):
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="DELETE 1")
        pool = create_mock_pool(mock_conn)

        from repositories.memory_repo import PostgresMemoryRepository
        repo = PostgresMemoryRepository(pool)
        result = await repo.delete(1)

        assert result is True

    @pytest.mark.asyncio
    async def test_delete_returns_false_when_no_row(self):
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="DELETE 0")
        pool = create_mock_pool(mock_conn)

        from repositories.memory_repo import PostgresMemoryRepository
        repo = PostgresMemoryRepository(pool)
        result = await repo.delete(999)

        assert result is False


class TestPostgresMemoryRepositoryBatchDelete:
    """测试 PostgresMemoryRepository.batch_delete"""

    @pytest.mark.asyncio
    async def test_batch_delete_returns_count(self):
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="DELETE 3")
        pool = create_mock_pool(mock_conn)

        from repositories.memory_repo import PostgresMemoryRepository
        repo = PostgresMemoryRepository(pool)
        result = await repo.batch_delete([1, 2, 3])

        assert result == 3


class TestPostgresMemoryRepositoryListAll:
    """测试 PostgresMemoryRepository.list_all"""

    @pytest.mark.asyncio
    async def test_list_all_returns_rows(self):
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(
            return_value=[
                {"id": 1, "content": "a"},
                {"id": 2, "content": "b"},
            ]
        )
        pool = create_mock_pool(mock_conn)

        from repositories.memory_repo import PostgresMemoryRepository
        repo = PostgresMemoryRepository(pool)
        result = await repo.list_all()

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_all_with_limit(self):
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[{"id": 1, "content": "a"}])
        pool = create_mock_pool(mock_conn)

        from repositories.memory_repo import PostgresMemoryRepository
        repo = PostgresMemoryRepository(pool)
        result = await repo.list_all(limit=1)

        assert len(result) == 1


class TestPostgresMemoryRepositoryCount:
    """测试 PostgresMemoryRepository.count"""

    @pytest.mark.asyncio
    async def test_returns_count(self):
        mock_conn = AsyncMock()
        mock_row = MagicMock()
        mock_row.__getitem__ = MagicMock(return_value=10)
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)
        pool = create_mock_pool(mock_conn)

        from repositories.memory_repo import PostgresMemoryRepository
        repo = PostgresMemoryRepository(pool)
        result = await repo.count()

        assert result == 10


class TestPostgresMemoryRepositoryGetRecent:
    """测试 PostgresMemoryRepository.get_recent"""

    @pytest.mark.asyncio
    async def test_returns_recent(self):
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(
            return_value=[{"id": 2, "content": "新"}, {"id": 1, "content": "旧"}]
        )
        pool = create_mock_pool(mock_conn)

        from repositories.memory_repo import PostgresMemoryRepository
        repo = PostgresMemoryRepository(pool)
        result = await repo.get_recent(limit=2)

        assert len(result) == 2


class TestPostgresMemoryRepositoryLayerStats:
    """测试 PostgresMemoryRepository.get_layer_statistics"""

    @pytest.mark.asyncio
    async def test_returns_stats(self):
        mock_conn = AsyncMock()

        def make_row(layer, count, active_count):
            row = MagicMock()
            row.__getitem__ = MagicMock(
                side_effect=lambda k: layer if k == "layer" else (count if k == "count" else active_count)
            )
            return row

        mock_conn.fetch = AsyncMock(
            return_value=[
                make_row(1, 5, 5),
                make_row(2, 3, 3),
                make_row(3, 2, 2),
            ]
        )
        pool = create_mock_pool(mock_conn)

        from repositories.memory_repo import PostgresMemoryRepository
        repo = PostgresMemoryRepository(pool)
        result = await repo.get_layer_statistics()

        assert result == {
            "layer_1": {"total": 5, "active": 5},
            "layer_2": {"total": 3, "active": 3},
            "layer_3": {"total": 2, "active": 2},
        }


class TestPostgresMemoryRepositoryPromoteToCore:
    """测试 PostgresMemoryRepository.promote_to_core"""

    @pytest.mark.asyncio
    async def test_promote(self):
        mock_conn = AsyncMock()
        pool = create_mock_pool(mock_conn)

        from repositories.memory_repo import PostgresMemoryRepository
        repo = PostgresMemoryRepository(pool)
        result = await repo.promote_to_core(1, title="核心")

        assert result is True


class TestPostgresMemoryRepositoryDeactivate:
    """测试 PostgresMemoryRepository.deactivate"""

    @pytest.mark.asyncio
    async def test_deactivate(self):
        mock_conn = AsyncMock()
        pool = create_mock_pool(mock_conn)

        from repositories.memory_repo import PostgresMemoryRepository
        repo = PostgresMemoryRepository(pool)
        result = await repo.deactivate([1, 2])

        assert result is True


class TestPostgresMemoryRepositoryMerge:
    """测试 PostgresMemoryRepository.merge"""

    @pytest.mark.asyncio
    async def test_merge_returns_new_id(self):
        mock_conn = AsyncMock()
        mock_row = MagicMock()
        mock_row.__getitem__ = MagicMock(return_value=99)
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)
        pool = create_mock_pool(mock_conn)

        from repositories.memory_repo import PostgresMemoryRepository
        repo = PostgresMemoryRepository(pool)
        result = await repo.merge([1, 2], content="合并", importance=8)

        assert result == 99


class TestPostgresMemoryRepositoryCheckDuplicate:
    """测试 PostgresMemoryRepository.check_duplicate"""

    @pytest.mark.asyncio
    async def test_duplicate_found(self):
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(
            return_value=[{"id": 1, "content": "重复内容", "importance": 5}]
        )
        pool = create_mock_pool(mock_conn)

        from repositories.memory_repo import PostgresMemoryRepository
        repo = PostgresMemoryRepository(pool)
        result = await repo.check_duplicate("重复")

        assert result["is_duplicate"] is True
        assert len(result["similar_memories"]) == 1

    @pytest.mark.asyncio
    async def test_no_duplicate(self):
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        pool = create_mock_pool(mock_conn)

        from repositories.memory_repo import PostgresMemoryRepository
        repo = PostgresMemoryRepository(pool)
        result = await repo.check_duplicate("全新的内容")

        assert result["is_duplicate"] is False


# ============================================================
# PostgresConversationRepository
# ============================================================

class TestPostgresConversationRepositorySaveMessage:
    """测试 PostgresConversationRepository.save_message"""

    @pytest.mark.asyncio
    async def test_save_message(self):
        mock_conn = AsyncMock()
        pool = create_mock_pool(mock_conn)

        from repositories.conversation_repo import PostgresConversationRepository
        repo = PostgresConversationRepository(pool)
        await repo.save_message("s1", "user", "你好")

        mock_conn.execute.assert_called_once()


class TestPostgresConversationRepositoryGetMessages:
    """测试 PostgresConversationRepository.get_messages"""

    @pytest.mark.asyncio
    async def test_returns_messages(self):
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(
            return_value=[
                {"id": 1, "role": "user", "content": "你好"},
                {"id": 2, "role": "assistant", "content": "你好！"},
            ]
        )
        pool = create_mock_pool(mock_conn)

        from repositories.conversation_repo import PostgresConversationRepository
        repo = PostgresConversationRepository(pool)
        result = await repo.get_messages("s1", limit=10)

        assert isinstance(result, list)


class TestPostgresConversationRepositoryGetLastUserContent:
    """测试 PostgresConversationRepository.get_last_user_content"""

    @pytest.mark.asyncio
    async def test_returns_content(self):
        mock_conn = AsyncMock()
        mock_row = MagicMock()
        mock_row.__getitem__ = MagicMock(return_value="最新用户消息")
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)
        pool = create_mock_pool(mock_conn)

        from repositories.conversation_repo import PostgresConversationRepository
        repo = PostgresConversationRepository(pool)
        result = await repo.get_last_user_content("s1")

        assert result == "最新用户消息"

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_messages(self):
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        pool = create_mock_pool(mock_conn)

        from repositories.conversation_repo import PostgresConversationRepository
        repo = PostgresConversationRepository(pool)
        result = await repo.get_last_user_content("empty")

        assert result == ""


class TestPostgresConversationRepositoryListSessions:
    """测试 PostgresConversationRepository.list_sessions"""

    @pytest.mark.asyncio
    async def test_returns_paginated(self):
        mock_conn = AsyncMock()
        count_row = MagicMock()
        count_row.__getitem__ = MagicMock(return_value=5)
        mock_conn.fetchrow = AsyncMock(return_value=count_row)
        mock_conn.fetch = AsyncMock(
            return_value=[
                {"session_id": "s1", "last_active": datetime.now(timezone.utc), "message_count": 3},
            ]
        )
        pool = create_mock_pool(mock_conn)

        from repositories.conversation_repo import PostgresConversationRepository
        repo = PostgresConversationRepository(pool)
        result = await repo.list_sessions(page=1, per_page=10)

        assert result["total"] == 5
        assert result["page"] == 1
        assert len(result["conversations"]) == 1


class TestPostgresConversationRepositoryDeleteSession:
    """测试 PostgresConversationRepository.delete_session"""

    @pytest.mark.asyncio
    async def test_delete(self):
        mock_conn = AsyncMock()
        pool = create_mock_pool(mock_conn)

        from repositories.conversation_repo import PostgresConversationRepository
        repo = PostgresConversationRepository(pool)
        result = await repo.delete_session("s1")

        assert result is True


class TestPostgresConversationRepositorySearch:
    """测试 PostgresConversationRepository.search"""

    @pytest.mark.asyncio
    async def test_search(self):
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(
            return_value=[{"session_id": "s1", "last_active": datetime.now(timezone.utc)}]
        )
        pool = create_mock_pool(mock_conn)

        from repositories.conversation_repo import PostgresConversationRepository
        repo = PostgresConversationRepository(pool)
        result = await repo.search("关键词")

        assert len(result) == 1


class TestPostgresConversationRepositoryExportAll:
    """测试 PostgresConversationRepository.export_all"""

    @pytest.mark.asyncio
    async def test_export(self):
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(
            return_value=[
                {"session_id": "s1", "role": "user", "content": "hi"},
            ]
        )
        pool = create_mock_pool(mock_conn)

        from repositories.conversation_repo import PostgresConversationRepository
        repo = PostgresConversationRepository(pool)
        result = await repo.export_all()

        assert len(result) == 1


class TestPostgresConversationRepositoryImportRecords:
    """测试 PostgresConversationRepository.import_records"""

    @pytest.mark.asyncio
    async def test_import(self):
        mock_conn = AsyncMock()
        pool = create_mock_pool(mock_conn)

        from repositories.conversation_repo import PostgresConversationRepository
        repo = PostgresConversationRepository(pool)
        records = [
            {"session_id": "s1", "role": "user", "content": "hi"},
            {"session_id": "s1", "role": "assistant", "content": "hello"},
        ]
        result = await repo.import_records(records)

        assert result == 2


# ============================================================
# PostgresConfigRepository
# ============================================================

class TestPostgresConfigRepositoryGet:
    """测试 PostgresConfigRepository.get"""

    @pytest.mark.asyncio
    async def test_get_existing(self):
        mock_conn = AsyncMock()
        mock_row = MagicMock()
        mock_row.__getitem__ = MagicMock(return_value="value1")
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)
        pool = create_mock_pool(mock_conn)

        from repositories.config_repo import PostgresConfigRepository
        repo = PostgresConfigRepository(pool)
        result = await repo.get("key1")

        assert result == "value1"

    @pytest.mark.asyncio
    async def test_get_default(self):
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        pool = create_mock_pool(mock_conn)

        from repositories.config_repo import PostgresConfigRepository
        repo = PostgresConfigRepository(pool)
        result = await repo.get("missing", default="fallback")

        assert result == "fallback"


class TestPostgresConfigRepositorySet:
    """测试 PostgresConfigRepository.set"""

    @pytest.mark.asyncio
    async def test_set(self):
        mock_conn = AsyncMock()
        pool = create_mock_pool(mock_conn)

        from repositories.config_repo import PostgresConfigRepository
        repo = PostgresConfigRepository(pool)
        await repo.set("key1", "value1")

        mock_conn.execute.assert_called_once()


class TestPostgresConfigRepositoryGetAll:
    """测试 PostgresConfigRepository.get_all"""

    @pytest.mark.asyncio
    async def test_get_all(self):
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(
            return_value=[
                {"key": "k1", "value": "v1"},
                {"key": "k2", "value": "v2"},
            ]
        )
        pool = create_mock_pool(mock_conn)

        from repositories.config_repo import PostgresConfigRepository
        repo = PostgresConfigRepository(pool)
        result = await repo.get_all()

        assert result == {"k1": "v1", "k2": "v2"}
