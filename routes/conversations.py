"""
对话管理路由

处理 /api/conversations/* 端点。
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import JSONResponse

router = APIRouter()


def _get_conversation_service(request: Request):
    return request.app.state.conversation_service


@router.get("/api/conversations")
async def get_conversations(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    """获取对话列表"""
    conversation_service = _get_conversation_service(request)
    return await conversation_service.list_sessions(page, per_page)


@router.get("/api/conversations/{session_id}/messages")
async def get_conversation_messages(
    request: Request,
    session_id: str,
    limit: int = Query(100, ge=1, le=1000),
):
    """获取对话消息"""
    conversation_service = _get_conversation_service(request)
    rows = await conversation_service.get_messages(session_id, limit)
    messages = [conversation_service.db_row_to_message(r) for r in rows] if rows else []
    return {"messages": messages}


@router.delete("/api/conversations/{session_id}")
async def delete_conversation(
    request: Request,
    session_id: str,
):
    """删除对话"""
    conversation_service = _get_conversation_service(request)
    await conversation_service.delete_session(session_id)
    return {"success": True}


@router.post("/api/conversations/batch-delete")
async def batch_delete_conversations(
    request: Request,
):
    """批量删除对话"""
    conversation_service = _get_conversation_service(request)
    body = await request.json()
    session_ids = body.get("session_ids", [])
    deleted = await conversation_service.batch_delete_sessions(session_ids)
    return {"success": True, "deleted": deleted}


@router.get("/api/chat/search")
async def search_conversations(
    request: Request,
    q: str = Query("", min_length=0),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """搜索对话"""
    conversation_service = _get_conversation_service(request)

    if not q.strip():
        return {"error": "搜索关键词不能为空", "results": [], "total": 0}
    try:
        results = await conversation_service.search(q.strip(), limit, offset)
        return {"results": results, "total": len(results)}
    except Exception as e:
        return {"error": str(e), "results": [], "total": 0}


@router.get("/api/conversations/export")
async def export_conversations(request: Request):
    """导出对话"""
    conversation_service = _get_conversation_service(request)
    data = await conversation_service.export_all()
    return JSONResponse(content=data)


@router.post("/api/conversations/import")
async def import_conversations(
    request: Request,
):
    """导入对话"""
    conversation_service = _get_conversation_service(request)

    records = await request.json()
    if not isinstance(records, list):
        return {"error": "格式错误：需要 JSON 数组"}
    imported = await conversation_service.import_records(records)
    return {
        "status": "ok",
        "imported": imported,
        "skipped": 0,
        "total": imported,
    }


@router.patch("/api/chat/messages/{message_id}")
async def update_message(message_id: int, request: Request):
    """编辑单条消息内容"""
    conversation_service = _get_conversation_service(request)

    body = await request.json()
    content = body.get("content", "").strip()
    if not content:
        return {"error": "内容不能为空"}
    updated = await conversation_service.update_message_content(message_id, content)
    if updated == 0:
        return {"error": "消息不存在"}
    return {"status": "ok"}
