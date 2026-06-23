"""
记忆路由

处理 /api/memories/* 端点。
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/api/memories")
async def get_memories(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    layer: Optional[int] = Query(None, ge=1, le=3),
):
    """获取记忆列表"""
    memory_service = request.app.state.memory_service
    
    memories = await memory_service.list_memories(
        limit=per_page,
        layer=layer,
        active_only=True,
    )
    total = await memory_service.count_memories()

    return {
        "memories": memories,
        "total": total,
        "page": page,
        "per_page": per_page,
    }


@router.get("/api/memories/search")
async def search_memories(
    request: Request,
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=100),
):
    """搜索记忆"""
    memory_service = request.app.state.memory_service
    
    memories = await memory_service.search_memories(q, limit=limit)
    return {"memories": memories}


@router.put("/api/memories/{memory_id}")
async def update_memory(
    request: Request,
    memory_id: int,
):
    """更新记忆"""
    body = await request.json()
    memory_service = request.app.state.memory_service
    
    success = await memory_service.update_memory(
        memory_id,
        content=body.get("content"),
        importance=body.get("importance"),
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="Memory not found")
    
    return {"success": True}


@router.delete("/api/memories/{memory_id}")
async def delete_memory(
    request: Request,
    memory_id: int,
):
    """删除记忆"""
    memory_service = request.app.state.memory_service
    
    success = await memory_service.delete_memory(memory_id)
    if not success:
        raise HTTPException(status_code=404, detail="Memory not found")
    
    return {"success": True}


@router.post("/api/memories/batch-update")
async def batch_update_memories(
    request: Request,
):
    """批量更新记忆"""
    body = await request.json()
    memory_service = request.app.state.memory_service
    
    memory_ids = body.get("memory_ids", [])
    importance = body.get("importance")
    
    success_count = 0
    for mid in memory_ids:
        success = await memory_service.update_memory(mid, importance=importance)
        if success:
            success_count += 1
    
    return {"success": True, "updated": success_count}


@router.post("/api/memories/batch-delete")
async def batch_delete_memories(
    request: Request,
):
    """批量删除记忆"""
    body = await request.json()
    memory_service = request.app.state.memory_service
    
    memory_ids = body.get("memory_ids", [])
    deleted = await memory_service.batch_delete_memories(memory_ids)
    
    return {"success": True, "deleted": deleted}


@router.get("/api/memories/layer-stats")
async def get_layer_stats(request: Request):
    """获取分层统计"""
    memory_service = request.app.state.memory_service
    
    stats = await memory_service.get_layer_statistics()
    return stats


@router.post("/api/memories/{memory_id}/promote")
async def promote_memory(
    request: Request,
    memory_id: int,
):
    """提升为核心记忆"""
    body = await request.json()
    memory_service = request.app.state.memory_service
    
    title = body.get("title")
    success = await memory_service.promote_to_core(memory_id, title)
    
    if not success:
        raise HTTPException(status_code=404, detail="Memory not found")
    
    return {"success": True}


@router.post("/api/memories/merge")
async def merge_memories(
    request: Request,
):
    """合并记忆"""
    body = await request.json()
    memory_service = request.app.state.memory_service
    
    source_ids = body.get("source_ids", [])
    content = body.get("content", "")
    importance = body.get("importance", 5)
    title = body.get("title")
    
    new_id = await memory_service.merge_memories(
        source_ids, content, importance, title
    )
    
    return {"success": True, "new_id": new_id}


@router.post("/api/memories/check-duplicate")
async def check_duplicate(
    request: Request,
):
    """检查重复记忆"""
    body = await request.json()
    memory_service = request.app.state.memory_service
    
    content = body.get("content", "")
    result = await memory_service.check_duplicate(content)
    
    return result
