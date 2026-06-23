"""
分区缓存路由

处理 /api/partition/* 端点。
"""

from typing import Dict, Any
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/api/partition/status")
async def get_partition_status(request: Request):
    """获取分区状态"""
    cache_service = request.app.state.cache_service
    
    states = await cache_service.list_all_states()
    return {"states": states}


@router.get("/api/partition/threads")
async def get_partition_threads(request: Request):
    """获取分区线程"""
    cache_service = request.app.state.cache_service
    
    states = await cache_service.list_all_states()
    threads = [
        {
            "session_id": s["session_id"],
            "summary": s.get("summary", ""),
            "a_start_round": s.get("a_start_round", 0),
        }
        for s in states
    ]
    return {"threads": threads}
