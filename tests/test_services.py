"""
Service 层单元测试（使用 mock repository）
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.memory_service import MemoryService
from services.cache_service import CacheService
from services.extraction_service import ExtractionService


# ============================================================
# MemoryService
# ============================================================

class TestMemoryService:
    """测试 MemoryService"""

    @pytest.fixture
    def mock_repo(self):
        repo = AsyncMock()
        repo.save = AsyncMock(return_value=1)
        repo.get_by_id = AsyncMock(return_value={"id": 1, "content": "记忆"})
        repo.update = AsyncMock(return_value=True)
        repo.delete = AsyncMock(return_value=True)
        repo.batch_delete = AsyncMock(return_value=3)
        repo.list_all = AsyncMock(return_value=[{"id": 1, "content": "a"}])
        repo.count = AsyncMock(return_value=10)
        repo.search = AsyncMock(return_value=[{"id": 1, "content": "匹配"}])
        repo.get_recent = AsyncMock(return_value=[{"id": 2, "content": "新"}])
        repo.get_layer_statistics = AsyncMock(return_value={"layer1": 5, "layer2": 3, "layer3": 2})
        repo.promote_to_core = AsyncMock(return_value=True)
        repo.deactivate = AsyncMock(return_value=True)
        repo.merge = AsyncMock(return_value=99)
        repo.check_duplicate = AsyncMock(return_value={"is_duplicate": False, "similar_memories": []})
        return repo

    @pytest.mark.asyncio
    async def test_save_memory(self, mock_repo):
        svc = MemoryService(mock_repo)
        result = await svc.save_memory("内容", importance=7, source_session="s1")
        assert result == 1
        mock_repo.save.assert_called_once_with("内容", 7, "s1")

    @pytest.mark.asyncio
    async def test_get_memory(self, mock_repo):
        svc = MemoryService(mock_repo)
        result = await svc.get_memory(1)
        assert result["content"] == "记忆"

    @pytest.mark.asyncio
    async def test_update_memory(self, mock_repo):
        svc = MemoryService(mock_repo)
        result = await svc.update_memory(1, content="新")
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_memory(self, mock_repo):
        svc = MemoryService(mock_repo)
        result = await svc.delete_memory(1)
        assert result is True

    @pytest.mark.asyncio
    async def test_batch_delete(self, mock_repo):
        svc = MemoryService(mock_repo)
        result = await svc.batch_delete_memories([1, 2, 3])
        assert result == 3

    @pytest.mark.asyncio
    async def test_list_memories(self, mock_repo):
        svc = MemoryService(mock_repo)
        result = await svc.list_memories(limit=10, layer=1, active_only=True)
        assert len(result) == 1
        mock_repo.list_all.assert_called_once_with(10, 1, True)

    @pytest.mark.asyncio
    async def test_count_memories(self, mock_repo):
        svc = MemoryService(mock_repo)
        result = await svc.count_memories()
        assert result == 10

    @pytest.mark.asyncio
    async def test_search_memories_keyword_only(self, mock_repo):
        svc = MemoryService(mock_repo)
        result = await svc.search_memories("查询", limit=5, use_vector=False)
        assert len(result) == 1
        mock_repo.search.assert_called_once_with("查询", 15)

    @pytest.mark.asyncio
    async def test_get_recent_memories(self, mock_repo):
        svc = MemoryService(mock_repo)
        result = await svc.get_recent_memories(limit=5)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_layer_statistics(self, mock_repo):
        svc = MemoryService(mock_repo)
        result = await svc.get_layer_statistics()
        assert result["layer1"] == 5

    @pytest.mark.asyncio
    async def test_promote_to_core(self, mock_repo):
        svc = MemoryService(mock_repo)
        result = await svc.promote_to_core(1, title="核心")
        assert result is True

    @pytest.mark.asyncio
    async def test_deactivate_memories(self, mock_repo):
        svc = MemoryService(mock_repo)
        result = await svc.deactivate_memories([1, 2])
        assert result is True

    @pytest.mark.asyncio
    async def test_merge_memories(self, mock_repo):
        svc = MemoryService(mock_repo)
        result = await svc.merge_memories([1, 2], content="合并", importance=8)
        assert result == 99

    @pytest.mark.asyncio
    async def test_check_duplicate(self, mock_repo):
        svc = MemoryService(mock_repo)
        result = await svc.check_duplicate("内容")
        assert result["is_duplicate"] is False


# ============================================================
# CacheService
# ============================================================

class TestCacheService:
    """测试 CacheService"""

    @pytest.fixture
    def mock_cache_repo(self):
        repo = AsyncMock()
        repo.get_state = AsyncMock(return_value={"summary": "摘要", "a_start_round": 0})
        repo.save_state = AsyncMock()
        repo.delete_state = AsyncMock(return_value=True)
        repo.list_all = AsyncMock(return_value=[{"session_id": "s1"}])
        return repo

    @pytest.mark.asyncio
    async def test_get_state_disabled(self, mock_cache_repo):
        svc = CacheService.__new__(CacheService)
        svc.cache_repo = mock_cache_repo
        svc.enabled = False
        svc.partition_x = 15
        result = await svc.get_state("s1")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_state_enabled(self, mock_cache_repo):
        svc = CacheService.__new__(CacheService)
        svc.cache_repo = mock_cache_repo
        svc.enabled = True
        svc.partition_x = 15
        result = await svc.get_state("s1")
        assert result == {"summary": "摘要", "a_start_round": 0}

    @pytest.mark.asyncio
    async def test_save_state_disabled(self, mock_cache_repo):
        svc = CacheService.__new__(CacheService)
        svc.cache_repo = mock_cache_repo
        svc.enabled = False
        svc.partition_x = 15
        await svc.save_state("s1", summary="test")
        mock_cache_repo.save_state.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_state(self, mock_cache_repo):
        svc = CacheService.__new__(CacheService)
        svc.cache_repo = mock_cache_repo
        svc.enabled = True
        result = await svc.delete_state("s1")
        assert result is True

    @pytest.mark.asyncio
    async def test_should_rotate_false(self, mock_cache_repo):
        svc = CacheService.__new__(CacheService)
        svc.cache_repo = mock_cache_repo
        svc.enabled = True
        svc.partition_x = 15
        result = await svc.should_rotate("s1", current_round=5)
        assert result is False

    @pytest.mark.asyncio
    async def test_should_rotate_true(self, mock_cache_repo):
        svc = CacheService.__new__(CacheService)
        svc.cache_repo = mock_cache_repo
        svc.enabled = True
        svc.partition_x = 15
        result = await svc.should_rotate("s1", current_round=20)
        assert result is True

    @pytest.mark.asyncio
    async def test_get_summary(self, mock_cache_repo):
        svc = CacheService.__new__(CacheService)
        svc.cache_repo = mock_cache_repo
        svc.enabled = True
        result = await svc.get_summary("s1")
        assert result == "摘要"

    @pytest.mark.asyncio
    async def test_get_summary_empty(self, mock_cache_repo):
        mock_cache_repo.get_state = AsyncMock(return_value=None)
        svc = CacheService.__new__(CacheService)
        svc.cache_repo = mock_cache_repo
        svc.enabled = True
        result = await svc.get_summary("nonexistent")
        assert result == ""


# ============================================================
# ExtractionService
# ============================================================

class TestExtractionServiceParseMemories:
    """测试 ExtractionService._parse_memories"""

    def test_parse_valid_json(self):
        svc = ExtractionService.__new__(ExtractionService)
        result = svc._parse_memories('[{"content": "记忆", "importance": 7}]')
        assert len(result) == 1
        assert result[0]["content"] == "记忆"

    def test_parse_markdown_json(self):
        svc = ExtractionService.__new__(ExtractionService)
        result = svc._parse_memories('```json\n[{"content": "记忆", "importance": 5}]\n```')
        assert len(result) == 1

    def test_parse_empty_array(self):
        svc = ExtractionService.__new__(ExtractionService)
        result = svc._parse_memories("[]")
        assert result == []

    def test_parse_invalid_json(self):
        svc = ExtractionService.__new__(ExtractionService)
        result = svc._parse_memories("这不是JSON")
        assert result == []

    def test_parse_embedded_json(self):
        svc = ExtractionService.__new__(ExtractionService)
        result = svc._parse_memories('结果：[{"content": "提取", "importance": 4}] 以上')
        assert len(result) == 1
        assert result[0]["content"] == "提取"

    def test_parse_filters_invalid(self):
        svc = ExtractionService.__new__(ExtractionService)
        result = svc._parse_memories('[{"content": "有效", "importance": 5}, {"invalid": "无效"}, "字符串"]')
        assert len(result) == 1
        assert result[0]["content"] == "有效"


class TestExtractionServiceExtractMemories:
    """测试 ExtractionService.extract_memories"""

    @pytest.mark.asyncio
    async def test_no_api_key(self):
        svc = ExtractionService.__new__(ExtractionService)
        svc.api_key = ""
        result = await svc.extract_memories([{"role": "user", "content": "test"}])
        assert result == []

    @pytest.mark.asyncio
    async def test_empty_messages(self):
        svc = ExtractionService.__new__(ExtractionService)
        svc.api_key = "test-key"
        result = await svc.extract_memories([])
        assert result == []


class TestExtractionServiceScoreMemories:
    """测试 ExtractionService.score_memories"""

    @pytest.mark.asyncio
    async def test_empty_texts(self):
        svc = ExtractionService.__new__(ExtractionService)
        result = await svc.score_memories([])
        assert result == []

    @pytest.mark.asyncio
    async def test_score_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '[{"content": "记忆", "importance": 8}]'}}]
        }

        svc = ExtractionService.__new__(ExtractionService)
        svc.api_key = "test-key"
        svc.api_base_url = "https://test.api/v1"
        svc.memory_model = "test-model"

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_cls.return_value = mock_client

            result = await svc.score_memories(["记忆"])
            assert len(result) == 1
            assert result[0]["importance"] == 8

    @pytest.mark.asyncio
    async def test_score_api_error(self):
        mock_response = MagicMock()
        mock_response.status_code = 500

        svc = ExtractionService.__new__(ExtractionService)
        svc.api_key = "test-key"
        svc.api_base_url = "https://test.api/v1"
        svc.memory_model = "test-model"

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_cls.return_value = mock_client

            result = await svc.score_memories(["记忆"])
            assert result[0]["importance"] == 5
