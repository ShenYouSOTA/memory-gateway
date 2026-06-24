"""
管理路由

处理 /api/admin/* 端点。
"""

import asyncio
from datetime import datetime, timezone
from typing import Dict, Any
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()

# 补算状态
_backfill_mem_status = {
    "running": False,
    "total": 0,
    "done": 0,
    "error": None,
    "finished_at": None,
}


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


@router.post("/api/admin/merge-sessions")
async def merge_sessions(request: Request):
    """合并对话会话"""
    conversation_service = request.app.state.conversation_service

    body = await request.json()
    source_ids = [s for s in body.get("source_ids", []) if s != body.get("target_id", "")]
    target_id = body.get("target_id", "")

    if not source_ids or not target_id:
        return {"error": "source_ids 和 target_id 不能为空"}

    try:
        result = await conversation_service.merge_sessions(source_ids, target_id)
        return {"status": "ok", **result}
    except Exception as e:
        return {"error": str(e)}


@router.post("/api/admin/backfill-memory-embeddings")
async def backfill_memory_embeddings():
    """给已有记忆补算embedding"""
    from database import backfill_memory_embeddings, get_pending_memory_embedding_count

    if _backfill_mem_status["running"]:
        return {"error": "补算任务正在运行中，请等待完成"}

    try:
        total = await get_pending_memory_embedding_count()
    except Exception as e:
        return {"error": f"查询待处理数量失败: {e}"}

    if total == 0:
        return {
            "status": "done",
            "message": "所有记忆已有embedding，无需补算",
            "total": 0,
            "done": 0,
        }

    _backfill_mem_status["running"] = True
    _backfill_mem_status["total"] = total
    _backfill_mem_status["done"] = 0
    _backfill_mem_status["error"] = None
    _backfill_mem_status["finished_at"] = None

    async def run_backfill():
        try:
            while _backfill_mem_status["running"]:
                updated = await backfill_memory_embeddings(batch_size=20)
                _backfill_mem_status["done"] += updated

                if updated == 0:
                    break

                await asyncio.sleep(1)

            _backfill_mem_status["finished_at"] = datetime.now(timezone.utc).isoformat()
        except Exception as e:
            _backfill_mem_status["error"] = str(e)
        finally:
            _backfill_mem_status["running"] = False

    asyncio.create_task(run_backfill())
    return {"status": "started", "total": total}


@router.get("/api/admin/backfill-memory-embeddings/status")
async def get_backfill_status():
    """查询记忆embedding补算进度"""
    return _backfill_mem_status
