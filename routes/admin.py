"""
管理路由

处理 /api/admin/* 端点。
"""

from typing import Dict, Any
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/api/models")
async def list_models():
    """列出模型"""
    return {
        "data": [
            {"id": "anthropic/claude-sonnet-4", "object": "model"},
            {"id": "anthropic/claude-haiku-4", "object": "model"},
            {"id": "openai/gpt-4o", "object": "model"},
        ]
    }
