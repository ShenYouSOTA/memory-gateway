"""
分区缓存路由

处理 /api/partition/* 端点。
"""

from typing import Dict, Any
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()


def _get_cache_service(request: Request):
    return request.app.state.cache_service


def _get_config_service(request: Request):
    return request.app.state.config_service


async def _get_active_session_id(request: Request) -> str:
    """获取活跃对话线 ID"""
    config_service = _get_config_service(request)
    return await config_service.get("partition_session_id", "")


@router.get("/api/partition/status")
async def get_partition_status(request: Request):
    """获取分区状态"""
    cache_service = _get_cache_service(request)
    config_service = _get_config_service(request)

    active_sid = await _get_active_session_id(request)
    state = await cache_service.get_state(active_sid) if active_sid else {}
    state = state or {}

    enabled = (await config_service.get("CACHE_PARTITION_ENABLED", "false")).lower() == "true"
    partition_x = int(await config_service.get("CACHE_PARTITION_X", "15") or "15")
    summary_model = await config_service.get("CACHE_SUMMARY_MODEL", "anthropic/claude-haiku-4.5")

    summary_parts = state.get("summary_parts", [])
    return {
        "enabled": enabled,
        "active_session_id": active_sid,
        "partition_x": partition_x,
        "summary_model": summary_model,
        "summary": "\n\n".join(summary_parts),
        "summary_parts": summary_parts,
        "summary_count": len(summary_parts),
        "summary_length": sum(len(p) for p in summary_parts),
        "a_start_round": state.get("a_start_round", 0),
        "updated_at": state.get("updated_at").isoformat() if state.get("updated_at") else None,
    }


@router.get("/api/partition/threads")
async def get_partition_threads(request: Request):
    """获取分区线程"""
    cache_service = _get_cache_service(request)

    threads = await cache_service.list_all_states()
    active_sid = await _get_active_session_id(request)
    for t in threads:
        t["is_active"] = t["session_id"] == active_sid
    if active_sid and not any(t["session_id"] == active_sid for t in threads):
        threads.insert(0, {
            "session_id": active_sid,
            "summary": "",
            "summary_length": 0,
            "summary_count": 0,
            "a_start_round": 0,
            "updated_at": None,
            "message_count": 0,
            "chat_tokens": 0,
            "is_active": True,
        })
    return {"threads": threads, "active_session_id": active_sid}


@router.put("/api/partition/summary")
async def update_summary(request: Request):
    """更新摘要"""
    cache_service = _get_cache_service(request)

    try:
        body = await request.json()
        sid = body.get("session_id", "")
        summary = body.get("summary", "")
        if not sid:
            return {"error": "session_id 不能为空"}

        state = await cache_service.get_state(sid) or {}
        summary_parts = (
            [summary] if isinstance(summary, str) and summary
            else summary if isinstance(summary, list)
            else []
        )
        a_start = state.get("a_start_round", 0) if summary_parts else 0
        await cache_service.save_state(sid, summary, a_start)
        total_len = sum(len(p) for p in summary_parts)
        return {"status": "ok", "summary_parts": len(summary_parts), "summary_length": total_len}
    except Exception as e:
        return {"error": str(e)}


@router.delete("/api/partition/summary")
async def clear_summary(request: Request):
    """清空摘要"""
    cache_service = _get_cache_service(request)

    try:
        body = await request.json()
        sid = body.get("session_id", "")
        if not sid:
            return {"error": "session_id 不能为空"}
        await cache_service.save_state(sid, "", 0)
        return {"status": "ok"}
    except Exception as e:
        return {"error": str(e)}


@router.post("/api/partition/thread")
async def create_thread(request: Request):
    """创建对话线"""
    cache_service = _get_cache_service(request)

    try:
        body = await request.json()
        new_id = body.get("session_id", "").strip()
        copy_from = body.get("copy_summary_from", "")
        if not new_id:
            return {"error": "session_id 不能为空"}
        existing = await cache_service.get_state(new_id) or {}
        if existing.get("updated_at"):
            return {"error": f"对话线 '{new_id}' 已存在"}
        summary_text = ""
        if copy_from:
            source = await cache_service.get_state(copy_from) or {}
            parts = source.get("summary_parts", [])
            summary_text = "\n\n".join(parts) if parts else ""
        await cache_service.save_state(new_id, summary_text, 0)
        return {"status": "ok", "session_id": new_id, "summary_length": len(summary_text)}
    except Exception as e:
        return {"error": str(e)}


@router.post("/api/partition/switch")
async def switch_thread(request: Request):
    """切换对话线"""
    config_service = _get_config_service(request)

    try:
        body = await request.json()
        new_id = body.get("session_id", "").strip()
        if not new_id:
            return {"error": "session_id 不能为空"}
        old_id = await _get_active_session_id(request)
        await config_service.set("partition_session_id", new_id)
        return {"status": "ok", "old_session_id": old_id, "new_session_id": new_id}
    except Exception as e:
        return {"error": str(e)}


@router.put("/api/partition/thread/rename")
async def rename_thread(request: Request):
    """重命名对话线"""
    conversation_service = request.app.state.conversation_service
    config_service = _get_config_service(request)

    try:
        body = await request.json()
        old_id = body.get("old_id", "").strip()
        new_id = body.get("new_id", "").strip()
        if not old_id or not new_id:
            return {"error": "old_id 和 new_id 不能为空"}
        if old_id == new_id:
            return {"error": "新旧ID相同"}
        success = await conversation_service.rename_session(old_id, new_id)
        if not success:
            return {"error": f"对话线 '{new_id}' 已存在"}
        current_sid = await _get_active_session_id(request)
        if current_sid == old_id:
            await config_service.set("partition_session_id", new_id)
        return {"status": "ok", "old_id": old_id, "new_id": new_id}
    except Exception as e:
        return {"error": str(e)}
