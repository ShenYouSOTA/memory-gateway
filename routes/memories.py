"""
记忆路由

处理 /api/memories/* 端点。
"""

import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import JSONResponse

router = APIRouter()

# 整理状态（异步执行，防重入）
_consolidate_status = {
    "running": False,
    "started_at": None,
    "result": None,
    "error": None,
}


def _get_memory_service(request: Request):
    return request.app.state.memory_service


def _get_config_service(request: Request):
    return request.app.state.config_service


async def _get_timezone_hours(request: Request) -> int:
    """获取时区偏移（从 config_service 或默认值）"""
    try:
        val = await _get_config_service(request).get("TIMEZONE_HOURS", "8")
        return int(val)
    except Exception:
        return 8


def _format_datetime(dt, tz_offset):
    """格式化 datetime 为时区感知字符串"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(tz_offset).strftime("%Y-%m-%d %H:%M:%S")


@router.get("/api/memories")
async def get_memories(
    request: Request,
    layer: int = Query(None),
    active_only: bool = Query(None),
):
    """获取所有记忆（管理页面用）"""
    memory_service = _get_memory_service(request)
    memories = await memory_service.list_memories(layer=layer, active_only=active_only)

    tz_hours = await _get_timezone_hours(request)
    tz_offset = timezone(timedelta(hours=tz_hours))
    for m in memories:
        if isinstance(m, dict) and m.get("created_at"):
            m["created_at"] = _format_datetime(m["created_at"], tz_offset)

    try:
        layer_stats = await memory_service.get_layer_statistics()
    except Exception:
        layer_stats = None

    resp = {"memories": memories}
    if layer_stats:
        resp["layer_stats"] = layer_stats
    return resp


@router.get("/api/memories/search")
async def search_memories(
    request: Request,
    q: str = Query("", min_length=0),
    limit: int = Query(20, ge=1, le=100),
):
    """语义搜索记忆"""
    memory_service = _get_memory_service(request)

    if not q.strip():
        return {"error": "搜索关键词不能为空", "results": []}

    try:
        results = await memory_service.search_memories(q.strip(), limit)
        tz_hours = await _get_timezone_hours(request)
        tz_offset = timezone(timedelta(hours=tz_hours))
        out = []
        for r in results:
            item = dict(r)
            if item.get("created_at"):
                item["created_at"] = _format_datetime(item["created_at"], tz_offset)
            out.append(item)
        return {"results": out, "total": len(out)}
    except Exception as e:
        return {"error": str(e), "results": []}


@router.put("/api/memories/{memory_id}")
async def update_memory(
    request: Request,
    memory_id: int,
):
    """更新记忆"""
    memory_service = _get_memory_service(request)
    data = await request.json()

    if "layer" in data or "title" in data or "is_active" in data:
        await memory_service.update_full(
            memory_id,
            content=data.get("content"),
            importance=data.get("importance"),
            title=data.get("title"),
            layer=data.get("layer"),
            is_active=data.get("is_active"),
        )
    else:
        await memory_service.update_memory(
            memory_id,
            content=data.get("content"),
            importance=data.get("importance"),
        )
    return {"status": "ok", "id": memory_id}


@router.delete("/api/memories/{memory_id}")
async def delete_memory(
    request: Request,
    memory_id: int,
    soft: bool = Query(False),
):
    """删除记忆"""
    memory_service = _get_memory_service(request)

    if soft:
        await memory_service.update_full(memory_id, is_active=False)
    else:
        await memory_service.delete_memory(memory_id)
    return {"status": "ok", "id": memory_id}


@router.post("/api/memories/batch-update")
async def batch_update_memories(
    request: Request,
):
    """批量更新记忆"""
    memory_service = _get_memory_service(request)

    data = await request.json()
    updates = data.get("updates", [])
    if not updates:
        return {"error": "没有要更新的记忆"}
    for item in updates:
        await memory_service.update_full(
            item["id"],
            content=item.get("content"),
            importance=item.get("importance"),
            title=item.get("title"),
            layer=item.get("layer"),
        )
    return {"status": "ok", "updated": len(updates)}


@router.post("/api/memories/batch-delete")
async def batch_delete_memories(
    request: Request,
):
    """批量删除记忆"""
    memory_service = _get_memory_service(request)

    data = await request.json()
    ids = data.get("ids", [])
    if not ids:
        return {"error": "未选择记忆"}
    await memory_service.batch_delete_memories(ids)
    return {"status": "ok", "deleted": len(ids)}


@router.get("/api/memories/layer-stats")
async def get_layer_stats(request: Request):
    """获取分层统计"""
    memory_service = _get_memory_service(request)
    return await memory_service.get_layer_statistics()


@router.post("/api/memories/{memory_id}/promote")
async def promote_memory(
    request: Request,
    memory_id: int,
):
    """提升为核心记忆"""
    memory_service = _get_memory_service(request)

    data = await request.json()
    title = data.get("title")
    await memory_service.promote_to_core(memory_id, title=title)
    return {"status": "ok", "memory_id": memory_id, "layer": 3}


@router.post("/api/memories/merge")
async def merge_memories(
    request: Request,
):
    """合并记忆"""
    memory_service = _get_memory_service(request)

    data = await request.json()
    memory_ids = data.get("ids", [])
    new_title = data.get("title", "")
    new_content = data.get("content", "")
    importance = data.get("importance", 5)
    layer = data.get("layer", 2)

    if not memory_ids or not new_content:
        return {"error": "请提供记忆ID列表和合并后内容"}

    new_id = await memory_service.merge_memories(
        memory_ids, new_content, importance, new_title
    )
    return {"status": "ok", "new_id": new_id, "merged": len(memory_ids)}


@router.post("/api/memories/check-duplicate")
async def check_duplicate(
    request: Request,
):
    """检查重复记忆"""
    memory_service = _get_memory_service(request)

    data = await request.json()
    content = data.get("content", "")
    threshold = data.get("threshold", 0.7)

    if not content:
        return {"error": "请提供记忆内容"}

    return await memory_service.check_duplicate(content, threshold)


@router.post("/api/memories/consolidate")
async def consolidate_memories(request: Request):
    """手动触发整理（异步，立即返回）"""
    from utils.consolidation_helpers import consolidate_memories_for_date_range

    body = await request.json()

    if _consolidate_status.get("running"):
        return {
            "status": "already_running",
            "started_at": _consolidate_status.get("started_at"),
        }

    # 解析日期参数
    if "date" in body and "start_date" not in body:
        start_date = datetime.strptime(body["date"], "%Y-%m-%d").date()
        end_date = start_date
    else:
        start_date_str = body.get("start_date")
        end_date_str = body.get("end_date")

        if not start_date_str or not end_date_str:
            return {"error": "请提供开始和结束日期"}

        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()

        if start_date > end_date:
            return {"error": "开始日期不能晚于结束日期"}

    async def _run():
        _consolidate_status.update({
            "running": True,
            "started_at": f"{start_date}~{end_date}",
            "result": None,
            "error": None,
        })
        try:
            result = await consolidate_memories_for_date_range(start_date, end_date)
            _consolidate_status["result"] = result
        except Exception as e:
            _consolidate_status["error"] = str(e)
        finally:
            _consolidate_status["running"] = False

    asyncio.create_task(_run())
    return {
        "status": "started",
        "start_date": str(start_date),
        "end_date": str(end_date),
    }


@router.get("/api/memories/consolidate/status")
async def get_consolidate_status():
    """查询整理任务状态"""
    return _consolidate_status


@router.post("/api/memories/cleanup-fragments")
async def cleanup_fragments(request: Request):
    """清理指定天数前的归档碎片"""
    memory_service = _get_memory_service(request)

    body = await request.json()
    days = body.get("days", 30)

    try:
        deleted = await memory_service.cleanup_fragments(days)
        return {"status": "ok", "deleted": deleted, "days": days}
    except Exception as e:
        return {"error": str(e)}


@router.post("/api/memories/{memory_id}/revert-merge")
async def revert_merge(memory_id: int, request: Request):
    """撤回合并操作：恢复原始碎片，删除合并后的事件记忆"""
    memory_service = _get_memory_service(request)

    try:
        return await memory_service.revert_merge(memory_id)
    except Exception as e:
        return {"error": str(e)}


@router.post("/api/memories/{memory_id}/restore")
async def restore_memory(memory_id: int, request: Request):
    """恢复已归档的记忆"""
    memory_service = _get_memory_service(request)

    try:
        await memory_service.update_full(memory_id, is_active=True)
        return {"status": "ok", "memory_id": memory_id}
    except Exception as e:
        return {"error": str(e)}
