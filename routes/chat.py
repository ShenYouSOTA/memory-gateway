"""
对话路由

处理 /v1/chat/completions 端点。
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Request, Depends
from fastapi.responses import StreamingResponse, JSONResponse

from ..services.chat_service import ChatService

router = APIRouter()


@router.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """处理对话请求"""
    body = await request.json()

    messages = body.get("messages", [])
    model = body.get("model", "")
    stream = body.get("stream", False)

    # 获取服务实例（从 app.state 注入）
    chat_service: ChatService = request.app.state.chat_service

    # 保存对话（异步，不阻塞）
    session_id = body.get("session_id", "")

    # 处理请求
    if stream:
        async def generate():
            async for chunk in await chat_service.chat_completion(
                messages=messages,
                model=model,
                stream=True,
                session_id=session_id,
            ):
                yield chunk

        return StreamingResponse(generate(), media_type="text/event-stream")
    else:
        result = await chat_service.chat_completion(
            messages=messages,
            model=model,
            stream=False,
            session_id=session_id,
        )
        return JSONResponse(content=result)


@router.get("/v1/models")
async def list_models():
    """列出可用模型"""
    return {
        "data": [
            {"id": "anthropic/claude-sonnet-4", "object": "model"},
            {"id": "anthropic/claude-haiku-4", "object": "model"},
            {"id": "openai/gpt-4o", "object": "model"},
        ]
    }
