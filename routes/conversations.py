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
    from database import get_conversations_paginated
    
    result = await get_conversations_paginated(page, per_page)
    return result


@router.get("/api/conversations/{session_id}/messages")
async def get_conversation_messages(
    request: Request,
    session_id: str,
    limit: int = Query(100, ge=1, le=1000),
):
    """获取对话消息"""
    from database import get_conversation_messages, db_row_to_message
    
    rows = await get_conversation_messages(session_id, limit)
    messages = [db_row_to_message(r) for r in rows] if rows else []
    return {"messages": messages}


@router.delete("/api/conversations/{session_id}")
async def delete_conversation(
    request: Request,
    session_id: str,
):
    """删除对话"""
    from database import delete_conversation
    
    await delete_conversation(session_id)
    return {"success": True}


@router.post("/api/conversations/batch-delete")
async def batch_delete_conversations(
    request: Request,
):
    """批量删除对话"""
    from database import batch_delete_conversations
    
    body = await request.json()
    session_ids = body.get("session_ids", [])
    deleted = await batch_delete_conversations(session_ids)
    return {"success": True, "deleted": deleted}


@router.get("/api/chat/search")
async def search_conversations(
    request: Request,
    q: str = Query("", min_length=0),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """搜索对话"""
    from database import search_conversations
    
    if not q.strip():
        return {"error": "搜索关键词不能为空", "results": [], "total": 0}
    try:
        results, total = await search_conversations(q.strip(), limit, offset)
        return {"results": results, "total": total}
    except Exception as e:
        return {"error": str(e), "results": [], "total": 0}


@router.get("/api/conversations/export")
async def export_conversations(request: Request):
    """导出对话"""
    from database import export_all_conversations
    
    data = await export_all_conversations()
    return JSONResponse(content=data)


@router.post("/api/conversations/import")
async def import_conversations(
    request: Request,
):
    """导入对话"""
    from database import import_conversations
    
    records = await request.json()
    if not isinstance(records, list):
        return {"error": "格式错误：需要 JSON 数组"}
    imported, skipped = await import_conversations(records)
    return {
        "status": "ok",
        "imported": imported,
        "skipped": skipped,
        "total": imported + skipped,
    }


@router.patch("/api/chat/messages/{message_id}")
async def update_message(message_id: int, request: Request):
    """编辑单条消息内容"""
    from database import update_message_content
    
    body = await request.json()
    content = body.get("content", "").strip()
    if not content:
        return {"error": "内容不能为空"}
    updated = await update_message_content(message_id, content)
    if updated == 0:
        return {"error": "消息不存在"}
    return {"status": "ok"}
