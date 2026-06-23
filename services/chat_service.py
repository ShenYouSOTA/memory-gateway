"""
对话服务层

封装对话转发和流式处理的业务逻辑。
"""

import os
import json
import asyncio
import httpx
from typing import List, Optional, Dict, Any, AsyncGenerator

from ..repositories.base import ConversationRepository, MemoryRepository


class ChatService:
    """对话服务"""

    def __init__(
        self,
        conversation_repo: ConversationRepository,
        memory_repo: MemoryRepository,
    ):
        self.conversation_repo = conversation_repo
        self.memory_repo = memory_repo

        # 配置
        self.api_key = os.getenv("API_KEY", "")
        self.api_base_url = os.getenv(
            "API_BASE_URL", "https://openrouter.ai/api/v1/chat/completions"
        )
        self.default_model = os.getenv("DEFAULT_MODEL", "anthropic/claude-sonnet-4")
        self.memory_enabled = os.getenv("MEMORY_ENABLED", "false").lower() == "true"

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "",
        stream: bool = False,
        session_id: str = "",
        **kwargs,
    ) -> Dict[str, Any] | AsyncGenerator:
        """
        处理对话请求

        参数：
            messages: 消息列表
            model: 模型名称
            stream: 是否流式
            session_id: 会话 ID
            **kwargs: 其他参数

        返回：
            响应数据或流式生成器
        """
        if not model:
            model = self.default_model

        # 记忆注入（如果启用）
        if self.memory_enabled and session_id:
            messages = await self._inject_memories(messages, session_id)

        # 构建请求体
        body = {
            "model": model,
            "messages": messages,
            "stream": stream,
            **kwargs,
        }

        # 转发请求
        if stream:
            return self._stream_completion(body, session_id)
        else:
            return await self._normal_completion(body, session_id)

    async def _inject_memories(
        self,
        messages: List[Dict[str, str]],
        session_id: str,
    ) -> List[Dict[str, str]]:
        """注入相关记忆到消息中"""
        # 获取最后一条用户消息
        last_user_content = await self.conversation_repo.get_last_user_content(
            session_id
        )
        if not last_user_content:
            return messages

        # 搜索相关记忆
        memories = await self.memory_repo.search(last_user_content, limit=5)
        if not memories:
            return messages

        # 构建记忆提示
        memory_text = "\n".join([f"- {m['content']}" for m in memories])
        memory_prompt = f"\n\n<已知信息>\n{memory_text}\n</已知信息>"

        # 注入到系统消息
        result = []
        system_injected = False
        for msg in messages:
            if msg["role"] == "system" and not system_injected:
                result.append({
                    "role": "system",
                    "content": msg["content"] + memory_prompt,
                })
                system_injected = True
            else:
                result.append(msg)

        if not system_injected:
            result.insert(0, {"role": "system", "content": memory_prompt})

        return result

    async def _normal_completion(
        self,
        body: Dict[str, Any],
        session_id: str,
    ) -> Dict[str, Any]:
        """普通（非流式）请求"""
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                self.api_base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            response.raise_for_status()
            return response.json()

    async def _stream_completion(
        self,
        body: Dict[str, Any],
        session_id: str,
    ) -> AsyncGenerator[bytes, None]:
        """流式请求"""
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                self.api_base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
            ) as response:
                async for chunk in response.aiter_bytes():
                    yield chunk

    async def save_conversation(
        self,
        session_id: str,
        messages: List[Dict[str, str]],
        model: str = "",
    ) -> None:
        """保存对话记录"""
        for msg in messages:
            await self.conversation_repo.save_message(
                session_id=session_id,
                role=msg["role"],
                content=msg.get("content", ""),
                model=model,
            )

    async def get_conversation_history(
        self,
        session_id: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """获取对话历史"""
        return await self.conversation_repo.get_messages(session_id, limit)
