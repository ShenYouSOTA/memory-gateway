"""
记忆提取服务层

封装 LLM 记忆提取的业务逻辑。
"""

import os
import json
import httpx
from typing import List, Dict, Any

from repositories.base import MemoryRepository


class ExtractionService:
    """记忆提取服务"""

    def __init__(self, memory_repo: MemoryRepository):
        self.memory_repo = memory_repo

        # 配置
        self.api_key = os.getenv("API_KEY", "")
        self.api_base_url = os.getenv(
            "API_BASE_URL", "https://openrouter.ai/api/v1/chat/completions"
        )
        self.memory_model = os.getenv("MEMORY_MODEL", "anthropic/claude-haiku-4")

    async def extract_memories(
        self,
        messages: List[Dict[str, str]],
        existing_memories: List[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        从对话中提取记忆

        参数：
            messages: 对话消息列表
            existing_memories: 已有记忆内容列表

        返回：
            记忆列表 [{"content": "...", "importance": N}, ...]
        """
        if not self.api_key:
            return []

        if not messages:
            return []

        # 格式化对话文本
        conversation_text = ""
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if role == "user":
                conversation_text += f"用户: {content}\n"
            elif role == "assistant":
                conversation_text += f"AI: {content}\n"

        if not conversation_text.strip():
            return []

        # 格式化已有记忆
        if existing_memories:
            memories_text = "\n".join(f"- {m}" for m in existing_memories)
        else:
            memories_text = "（暂无已知信息）"

        # 构建提示
        prompt = self._build_extraction_prompt(memories_text)

        # 调用 LLM
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    self.api_base_url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.memory_model,
                        "max_tokens": 1000,
                        "messages": [
                            {"role": "system", "content": prompt},
                            {
                                "role": "user",
                                "content": f"请从以下对话中提取新的记忆：\n\n{conversation_text}",
                            },
                        ],
                    },
                )

                if response.status_code != 200:
                    return []

                data = response.json()
                text = (
                    data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                )

                # 解析结果
                return self._parse_memories(text)

        except Exception as e:
            print(f"⚠️ 记忆提取出错: {e}")
            return []

    def _build_extraction_prompt(self, existing_memories: str) -> str:
        """构建提取提示"""
        return f"""你是信息提取专家，负责从对话中识别并提取值得长期记住的关键信息。

# 提取重点
- 关键信息：提取用户的重要信息和值得回忆的生活细节
- 重要事件：记忆深刻的互动，需包含人物、时间、地点（如有）

# 提取范围
- 个人：年龄、生日、职业、学历、居住地
- 偏好：明确表达的喜好或厌恶
- 健康：身体状况、过敏史、饮食禁忌
- 事件：与AI的重要互动、约定、里程碑
- 关系：家人、朋友、重要同事
- 价值观：表达的信念或长期目标
- 情感：重要的情感时刻或关系里程碑
- 生活：用户当天的活动、饮食、出行、日常经历等生活细节

# 不要提取
- 日常寒暄（"你好""在吗"）
- AI助手自己的回复内容
- 关于记忆系统本身的讨论
- 技术调试、bug修复的过程性讨论
- AI的思考过程、思维链内容

# 已知信息处理【最重要】
<已知信息>
{existing_memories}
</已知信息>

- 新信息必须与已知信息逐条比对
- 相同、相似或语义重复的信息必须忽略
- 已知信息的补充或更新可以提取
- 仅提取完全新增且不与已知信息重复的内容

# 输出格式
请用以下 JSON 格式返回（不要包含其他内容）：
[
  {{"content": "记忆内容", "importance": 分数}},
  {{"content": "记忆内容", "importance": 分数}}
]

importance 分数 1-10，10 最重要。
如果没有值得记住的新信息，返回空数组：[]"""

    def _parse_memories(self, text: str) -> List[Dict[str, Any]]:
        """解析 LLM 返回的记忆"""
        text = text.strip()

        # 清理 markdown 格式
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        # 尝试解析 JSON
        try:
            memories = json.loads(text)
        except json.JSONDecodeError:
            # 正则兜底
            import re

            match = re.search(r"\[.*\]", text, re.DOTALL)
            if match:
                try:
                    memories = json.loads(match.group())
                except json.JSONDecodeError:
                    return []
            else:
                return []

        if not isinstance(memories, list):
            return []

        # 验证格式
        valid_memories = []
        for mem in memories:
            if isinstance(mem, dict) and "content" in mem:
                valid_memories.append(
                    {
                        "content": str(mem["content"]),
                        "importance": int(mem.get("importance", 5)),
                    }
                )

        return valid_memories

    async def score_memories(self, texts: List[str]) -> List[Dict[str, Any]]:
        """对记忆进行评分"""
        if not texts:
            return []

        memories_text = "\n".join(f"- {t}" for t in texts)
        prompt = f"""你是记忆重要性评分专家。请对以下记忆条目逐条评分。

# 评分规则（1-10）
- 9-10：核心身份信息（名字、生日、职业、重要关系）
- 7-8：重要偏好、重大事件、深层情感
- 5-6：日常习惯、一般偏好
- 3-4：临时状态、偶然提及
- 1-2：琐碎信息

# 输入记忆
{memories_text}

# 输出格式
返回 JSON 数组，每条包含原文和评分：
[{{"content": "原文", "importance": 评分数字}}]

只返回 JSON，不要其他文字。"""

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    self.api_base_url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.memory_model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0,
                        "max_tokens": 4000,
                    },
                )

                if response.status_code != 200:
                    return [{"content": t, "importance": 5} for t in texts]

                data = response.json()
                text = (
                    data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                )

                memories = self._parse_memories(text)
                if memories:
                    return memories

                return [{"content": t, "importance": 5} for t in texts]

        except Exception as e:
            print(f"⚠️ 记忆评分出错: {e}")
            return [{"content": t, "importance": 5} for t in texts]
