"""
main.py 路由测试
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport


@pytest.fixture
def app():
    """创建 FastAPI 应用实例"""
    with patch("database.init_tables", new_callable=AsyncMock):
        with patch("database.get_pool") as mock_pool:
            mock_pool.return_value = AsyncMock()
            from main import app
            yield app


@pytest.fixture
def client(app):
    """创建测试客户端"""
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


class TestHealthCheck:
    """测试健康检查路由"""

    @pytest.mark.asyncio
    async def test_root_returns_status(self, client):
        """根路径返回状态信息"""
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "running"


class TestModelsEndpoint:
    """测试模型列表路由"""

    @pytest.mark.asyncio
    async def test_list_models(self, client):
        """获取模型列表"""
        response = await client.get("/v1/models")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert isinstance(data["data"], list)


class TestMemoryEndpoints:
    """测试记忆相关路由"""

    @pytest.mark.asyncio
    async def test_get_memories(self, client):
        """获取记忆列表"""
        with patch("database.get_all_memories_detail", new_callable=AsyncMock) as mock:
            mock.return_value = {
                "memories": [],
                "total": 0,
                "page": 1,
                "per_page": 20,
            }
            response = await client.get("/api/memories")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_search_memories(self, client):
        """搜索记忆"""
        with patch("database.search_memories", new_callable=AsyncMock) as mock:
            mock.return_value = []
            response = await client.get("/api/memories/search", params={"q": "test"})
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_delete_memory(self, client):
        """删除记忆"""
        with patch("database.delete_memory", new_callable=AsyncMock):
            response = await client.delete("/api/memories/1")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_update_memory(self, client):
        """更新记忆"""
        with patch("database.update_memory", new_callable=AsyncMock):
            response = await client.put(
                "/api/memories/1",
                json={"content": "新内容", "importance": 8},
            )
            assert response.status_code == 200


class TestConversationEndpoints:
    """测试对话相关路由"""

    @pytest.mark.asyncio
    async def test_get_conversations(self, client):
        """获取对话列表"""
        with patch("database.get_conversations_paginated", new_callable=AsyncMock) as mock:
            mock.return_value = {
                "conversations": [],
                "total": 0,
                "page": 1,
                "per_page": 20,
            }
            response = await client.get("/api/conversations")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_delete_conversation(self, client):
        """删除对话"""
        with patch("database.delete_conversation", new_callable=AsyncMock):
            response = await client.delete("/api/conversations/test-session")
            assert response.status_code == 200


class TestSettingsEndpoints:
    """测试设置相关路由"""

    @pytest.mark.asyncio
    async def test_get_settings(self, client):
        """获取设置"""
        with patch("database.get_all_gateway_config", new_callable=AsyncMock) as mock:
            mock.return_value = {}
            response = await client.get("/api/settings")
            assert response.status_code == 200


class TestPartitionEndpoints:
    """测试分区缓存路由"""

    @pytest.mark.asyncio
    async def test_get_partition_status(self, client):
        """获取分区状态"""
        with patch("database.list_all_session_cache_states", new_callable=AsyncMock) as mock:
            mock.return_value = []
            response = await client.get("/api/partition/status")
            assert response.status_code == 200


class TestExportImport:
    """测试导出导入路由"""

    @pytest.mark.asyncio
    async def test_export_memories(self, client):
        """导出记忆"""
        with patch("database.get_all_memories", new_callable=AsyncMock) as mock:
            mock.return_value = []
            response = await client.get("/export/memories")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_export_conversations(self, client):
        """导出对话"""
        with patch("database.export_all_conversations", new_callable=AsyncMock) as mock:
            mock.return_value = []
            response = await client.get("/api/conversations/export")
            assert response.status_code == 200


class TestLayerEndpoints:
    """测试三层记忆架构路由"""

    @pytest.mark.asyncio
    async def test_get_layer_stats(self, client):
        """获取分层统计"""
        with patch("database.get_layer_statistics", new_callable=AsyncMock) as mock:
            mock.return_value = {"layer1": 0, "layer2": 0, "layer3": 0}
            response = await client.get("/api/memories/layer-stats")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_promote_to_core(self, client):
        """提升为核心记忆"""
        with patch("database.promote_to_core", new_callable=AsyncMock):
            response = await client.post(
                "/api/memories/1/promote",
                json={"title": "核心记忆"},
            )
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_check_duplicate(self, client):
        """检查重复记忆"""
        with patch("database.check_duplicate_memory", new_callable=AsyncMock) as mock:
            mock.return_value = {"is_duplicate": False, "similar_memories": []}
            response = await client.post(
                "/api/memories/check-duplicate",
                json={"content": "测试内容"},
            )
            assert response.status_code == 200
