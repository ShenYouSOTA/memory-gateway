"""
memory_extractor.py 单元测试
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from memory_extractor import extract_memories, score_memories


class TestExtractMemories:
    """测试 extract_memories 函数"""

    @pytest.mark.asyncio
    async def test_no_api_key(self):
        """无 API_KEY 时返回空列表"""
        with patch("memory_extractor.API_KEY", ""):
            result = await extract_memories([{"role": "user", "content": "test"}])
            assert result == []

    @pytest.mark.asyncio
    async def test_empty_messages(self):
        """空消息列表返回空列表"""
        with patch("memory_extractor.API_KEY", "test-key"):
            result = await extract_memories([])
            assert result == []

    @pytest.mark.asyncio
    async def test_extract_success(self, sample_messages):
        """成功提取记忆"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": '[{"content": "用户对Python感兴趣", "importance": 7}]'
                    }
                }
            ]
        }

        with patch("memory_extractor.API_KEY", "test-key"):
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.post = AsyncMock(return_value=mock_response)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock()
                mock_client_cls.return_value = mock_client

                result = await extract_memories(sample_messages)

                assert len(result) == 1
                assert result[0]["content"] == "用户对Python感兴趣"
                assert result[0]["importance"] == 7

    @pytest.mark.asyncio
    async def test_extract_with_markdown_json(self, sample_messages):
        """处理 markdown 格式的 JSON 响应"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": '```json\n[{"content": "测试记忆", "importance": 5}]\n```'
                    }
                }
            ]
        }

        with patch("memory_extractor.API_KEY", "test-key"):
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.post = AsyncMock(return_value=mock_response)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock()
                mock_client_cls.return_value = mock_client

                result = await extract_memories(sample_messages)

                assert len(result) == 1
                assert result[0]["content"] == "测试记忆"

    @pytest.mark.asyncio
    async def test_extract_empty_array(self, sample_messages):
        """对话中无新信息时返回空数组"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "[]"}}]
        }

        with patch("memory_extractor.API_KEY", "test-key"):
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.post = AsyncMock(return_value=mock_response)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock()
                mock_client_cls.return_value = mock_client

                result = await extract_memories(sample_messages)

                assert result == []

    @pytest.mark.asyncio
    async def test_extract_api_error(self, sample_messages):
        """API 请求失败时返回空列表"""
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("memory_extractor.API_KEY", "test-key"):
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.post = AsyncMock(return_value=mock_response)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock()
                mock_client_cls.return_value = mock_client

                result = await extract_memories(sample_messages)

                assert result == []

    @pytest.mark.asyncio
    async def test_extract_with_existing_memories(self, sample_messages):
        """已有记忆参与去重对比"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": '[{"content": "新记忆", "importance": 6}]'
                    }
                }
            ]
        }

        existing = ["用户对Python感兴趣", "用户是开发者"]

        with patch("memory_extractor.API_KEY", "test-key"):
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.post = AsyncMock(return_value=mock_response)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock()
                mock_client_cls.return_value = mock_client

                result = await extract_memories(sample_messages, existing_memories=existing)

                assert len(result) == 1
                assert result[0]["content"] == "新记忆"

    @pytest.mark.asyncio
    async def test_extract_invalid_json_fallback(self, sample_messages):
        """JSON 解析失败时尝试正则提取"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": '这是提取结果：[{"content": "正则提取", "importance": 4}] 以上'
                    }
                }
            ]
        }

        with patch("memory_extractor.API_KEY", "test-key"):
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.post = AsyncMock(return_value=mock_response)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock()
                mock_client_cls.return_value = mock_client

                result = await extract_memories(sample_messages)

                assert len(result) == 1
                assert result[0]["content"] == "正则提取"

    @pytest.mark.asyncio
    async def test_extract_invalid_format(self, sample_messages):
        """无效格式的记忆被过滤"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": '[{"content": "有效记忆", "importance": 5}, {"invalid": "无效"}, "字符串"]'
                    }
                }
            ]
        }

        with patch("memory_extractor.API_KEY", "test-key"):
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.post = AsyncMock(return_value=mock_response)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock()
                mock_client_cls.return_value = mock_client

                result = await extract_memories(sample_messages)

                assert len(result) == 1
                assert result[0]["content"] == "有效记忆"


class TestScoreMemories:
    """测试 score_memories 函数"""

    @pytest.mark.asyncio
    async def test_empty_texts(self):
        """空列表返回空列表"""
        result = await score_memories([])
        assert result == []

    @pytest.mark.asyncio
    async def test_score_success(self):
        """成功评分"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": '[{"content": "用户是开发者", "importance": 8}]'
                    }
                }
            ]
        }

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_cls.return_value = mock_client

            result = await score_memories(["用户是开发者"])

            assert len(result) == 1
            assert result[0]["importance"] == 8

    @pytest.mark.asyncio
    async def test_score_api_error(self):
        """API 失败时返回默认分数"""
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_cls.return_value = mock_client

            result = await score_memories(["测试记忆"])

            assert len(result) == 1
            assert result[0]["importance"] == 5
