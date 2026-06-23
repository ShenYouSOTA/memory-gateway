"""
设置路由

处理 /api/settings 端点。
"""

from typing import Dict, Any
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/api/settings")
async def get_settings(request: Request):
    """获取设置"""
    config_service = request.app.state.config_service
    
    settings = await config_service.get_all()
    
    # 添加默认设置
    defaults = {
        "MEMORY_ENABLED": "false",
        "MEMORY_MODEL": "anthropic/claude-haiku-4",
        "MEMORY_EXTRACT_INTERVAL": "1",
        "MAX_MEMORIES_INJECT": "15",
        "MIN_SCORE_THRESHOLD": "0.15",
        "CACHE_PARTITION_ENABLED": "false",
        "CACHE_PARTITION_X": "15",
        "DEFAULT_MODEL": "anthropic/claude-sonnet-4",
    }
    
    result = {**defaults, **settings}
    return result


@router.put("/api/settings")
async def update_settings(request: Request):
    """更新设置"""
    body = await request.json()
    config_service = request.app.state.config_service
    
    for key, value in body.items():
        await config_service.set(key, str(value))
    
    return {"success": True}
