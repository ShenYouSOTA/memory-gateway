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
    from database import get_session_cache_state
    import main
    
    active_sid = main.get_active_session_id()
    state = await get_session_cache_state(active_sid) if active_sid else {}
    return {
        "enabled": main.CACHE_PARTITION_ENABLED,
        "active_session_id": active_sid,
        "partition_x": main.CACHE_PARTITION_X,
        "summary_model": main.CACHE_SUMMARY_MODEL,
        "summary": "\n\n".join(state.get("summary_parts", [])),
        "summary_parts": state.get("summary_parts", []),
        "summary_count": len(state.get("summary_parts", [])),
        "summary_length": sum(len(p) for p in state.get("summary_parts", [])),
        "a_start_round": state.get("a_start_round", 0),
        "updated_at": state.get("updated_at").isoformat() if state.get("updated_at") else None,
    }


@router.get("/api/partition/threads")
async def get_partition_threads(request: Request):
    """获取分区线程"""
    from database import list_all_session_cache_states
    import main
    
    threads = await list_all_session_cache_states()
    active_sid = main.get_active_session_id()
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
    from database import get_session_cache_state, save_session_cache_state
    
    try:
        body = await request.json()
        sid = body.get("session_id", "")
        summary = body.get("summary", "")
        if not sid:
            return {"error": "session_id 不能为空"}
        state = await get_session_cache_state(sid)
        summary_parts = (
            [summary] if isinstance(summary, str) and summary
            else summary if isinstance(summary, list)
            else []
        )
        a_start = state.get("a_start_round", 0) if summary_parts else 0
        await save_session_cache_state(sid, summary_parts, a_start)
        total_len = sum(len(p) for p in summary_parts)
        return {"status": "ok", "summary_parts": len(summary_parts), "summary_length": total_len}
    except Exception as e:
        return {"error": str(e)}


@router.delete("/api/partition/summary")
async def clear_summary(request: Request):
    """清空摘要"""
    from database import save_session_cache_state
    
    try:
        body = await request.json()
        sid = body.get("session_id", "")
        if not sid:
            return {"error": "session_id 不能为空"}
        await save_session_cache_state(sid, [], 0)
        return {"status": "ok"}
    except Exception as e:
        return {"error": str(e)}


@router.post("/api/partition/thread")
async def create_thread(request: Request):
    """创建对话线"""
    from database import get_session_cache_state, save_session_cache_state
    
    try:
        body = await request.json()
        new_id = body.get("session_id", "").strip()
        copy_from = body.get("copy_summary_from", "")
        if not new_id:
            return {"error": "session_id 不能为空"}
        existing = await get_session_cache_state(new_id)
        if existing.get("updated_at"):
            return {"error": f"对话线 '{new_id}' 已存在"}
        summary_parts = []
        if copy_from:
            source = await get_session_cache_state(copy_from)
            summary_parts = source.get("summary_parts", [])
        await save_session_cache_state(new_id, summary_parts, 0)
        total_len = sum(len(p) for p in summary_parts)
        return {"status": "ok", "session_id": new_id, "summary_length": total_len}
    except Exception as e:
        return {"error": str(e)}


@router.post("/api/partition/switch")
async def switch_thread(request: Request):
    """切换对话线"""
    from database import set_gateway_config
    import main
    
    try:
        body = await request.json()
        new_id = body.get("session_id", "").strip()
        if not new_id:
            return {"error": "session_id 不能为空"}
        old_id = main.PARTITION_SESSION_ID
        main.PARTITION_SESSION_ID = new_id
        await set_gateway_config("partition_session_id", new_id)
        return {"status": "ok", "old_session_id": old_id, "new_session_id": new_id}
    except Exception as e:
        return {"error": str(e)}


@router.put("/api/partition/thread/rename")
async def rename_thread(request: Request):
    """重命名对话线"""
    from database import rename_session_id, set_gateway_config
    import main
    
    try:
        body = await request.json()
        old_id = body.get("old_id", "").strip()
        new_id = body.get("new_id", "").strip()
        if not old_id or not new_id:
            return {"error": "old_id 和 new_id 不能为空"}
        if old_id == new_id:
            return {"error": "新旧ID相同"}
        success = await rename_session_id(old_id, new_id)
        if not success:
            return {"error": f"对话线 '{new_id}' 已存在"}
        if main.PARTITION_SESSION_ID == old_id:
            main.PARTITION_SESSION_ID = new_id
            await set_gateway_config("partition_session_id", new_id)
        return {"status": "ok", "old_id": old_id, "new_id": new_id}
    except Exception as e:
        return {"error": str(e)}
