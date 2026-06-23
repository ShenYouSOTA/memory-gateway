"""
对话管理路由

处理 /api/conversations/* 端点。
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/api/conversations")
async def get_conversations(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    """获取对话列表"""
    conversation_service = request.app.state.conversation_service
    
    result = await conversation_service.list_sessions(page, per_page)
    return result


@router.get("/api/conversations/{session_id}/messages")
async def get_conversation_messages(
    request: Request,
    session_id: str,
    limit: int = Query(100, ge=1, le=1000),
):
    """获取对话消息"""
    conversation_service = request.app.state.conversation_service
    
    messages = await conversation_service.get_messages(session_id, limit)
    return {"messages": messages}


@router.delete("/api/conversations/{session_id}")
async def delete_conversation(
    request: Request,
    session_id: str,
):
    """删除对话"""
    conversation_service = request.app.state.conversation_service
    
    await conversation_service.delete_session(session_id)
    return {"success": True}


@router.post("/api/conversations/batch-delete")
async def batch_delete_conversations(
    request: Request,
):
    """批量删除对话"""
    body = await request.json()
    conversation_service = request.app.state.conversation_service
    
    session_ids = body.get("session_ids", [])
    deleted = await conversation_service.batch_delete_sessions(session_ids)
    
    return {"success": True, "deleted": deleted}


@router.get("/api/chat/search")
async def search_conversations(
    request: Request,
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """搜索对话"""
    conversation_service = request.app.state.conversation_service
    
    results = await conversation_service.search(q, limit, offset)
    return {"conversations": results}


@router.get("/api/conversations/export")
async def export_conversations(request: Request):
    """导出对话"""
    conversation_service = request.app.state.conversation_service
    
    records = await conversation_service.export_all()
    return {"records": records}


@router.post("/api/conversations/import")
async def import_conversations(
    request: Request,
):
    """导入对话"""
    body = await request.json()
    conversation_service = request.app.state.conversation_service
    
    records = body.get("records", [])
    imported = await conversation_service.import_records(records)
    
    return {"success": True, "imported": imported}
