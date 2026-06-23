"""
测试配置和公共 fixtures
"""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# 设置测试环境变量
os.environ["API_KEY"] = "test-api-key"
os.environ["API_BASE_URL"] = "https://test-api.example.com/v1/chat/completions"
os.environ["DEFAULT_MODEL"] = "test-model"
os.environ["MEMORY_ENABLED"] = "false"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test_db"


@pytest.fixture
def mock_httpx_client():
    """Mock httpx.AsyncClient"""
    client = AsyncMock()
    client.post = AsyncMock()
    client.aclose = AsyncMock()
    return client


@pytest.fixture
def mock_db_pool():
    """Mock asyncpg connection pool"""
    pool = AsyncMock()
    pool.acquire = AsyncMock()
    pool.release = AsyncMock()
    pool.close = AsyncMock()
    return pool


@pytest.fixture
def mock_db_connection():
    """Mock asyncpg connection"""
    conn = AsyncMock()
    conn.fetch = AsyncMock()
    conn.fetchrow = AsyncMock()
    conn.execute = AsyncMock()
    conn.fetchval = AsyncMock()
    return conn


@pytest.fixture
def sample_messages():
    """示例消息列表"""
    return [
        {"role": "user", "content": "你好，我想了解一下Python"},
        {"role": "assistant", "content": "Python是一种流行的编程语言..."},
        {"role": "user", "content": "能详细说说吗？"},
    ]


@pytest.fixture
def sample_memory():
    """示例记忆数据"""
    return {
        "id": 1,
        "content": "用户对Python感兴趣",
        "importance": 0.8,
        "created_at": "2026-06-23T10:00:00+08:00",
        "is_active": True,
        "layer": 1,
    }


@pytest.fixture
def sample_memories(sample_memory):
    """示例记忆列表"""
    return [
        sample_memory,
        {
            "id": 2,
            "content": "用户喜欢技术讨论",
            "importance": 0.6,
            "created_at": "2026-06-22T10:00:00+08:00",
            "is_active": True,
            "layer": 1,
        },
        {
            "id": 3,
            "content": "用户是一名开发者",
            "importance": 0.9,
            "created_at": "2026-06-21T10:00:00+08:00",
            "is_active": True,
            "layer": 3,
        },
    ]
