"""
对话路由

/v1/chat/completions 路由保留在 main.py 中，因为包含复杂的分区缓存和记忆注入逻辑。
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Request, Depends
from fastapi.responses import StreamingResponse, JSONResponse

router = APIRouter()

# /v1/chat/completions 路由保留在 main.py 中


@router.get("/v1/models")
async def list_models():
    """列出可用模型"""
    return {
        "data": [
            {"id": "anthropic/claude-sonnet-4", "object": "model"},
            {"id": "anthropic/claude-haiku-4", "object": "model"},
            {"id": "openai/gpt-4o", "object": "model"},
        ]
    }
