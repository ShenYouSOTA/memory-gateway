"""
记忆整理辅助函数

从 main.py 迁移出来的记忆整理相关函数。
"""

import os
import json
import re
import asyncio
import httpx
from typing import Dict, Any
from datetime import datetime, date


CONSOLIDATION_PROMPT = """
你是记忆整理助手。请将以下对话碎片整理成完整的事件记录。

要求：
1. 按主题/事件分组，相关的碎片合并到一起
2. 每个事件一条记录，不要太细碎也不要太笼统
3. 每条记录包含：标题（10字内）+ 完整描述
4. 合并重复内容，保留重要细节
5. 保留原文中的主观感受、情绪表达和个人化用语，不要改写为客观陈述或第三方总结
6. content字段中不要使用双引号，用单引号或书名号代替

碎片记忆：
{fragments}

请用 JSON 格式输出：
[
  {{
    "title": "事件标题（10字内）",
    "content": "完整的事件描述",
    "importance": 5,
    "merged_ids": [1, 2, 3]
  }}
]

只输出 JSON，不要其他内容。确保 JSON 语法正确。
"""


async def consolidate_memories_for_date_range(
    start_date: date,
    end_date: date,
    api_key: str = "",
    api_base_url: str = "",
) -> Dict[str, Any]:
    """整理指定时间段的碎片记忆"""
    from database import (
        get_fragments_by_date_range,
        create_event_memory,
        deactivate_memories,
    )
    
    # 获取该时间段的碎片
    fragments = await get_fragments_by_date_range(start_date, end_date)
    
    if not fragments:
        return {
            "status": "no_fragments",
            "start_date": str(start_date),
            "end_date": str(end_date),
        }
    
    # 构建碎片文本
    fragments_text = "\n".join(
        [
            f"[ID={f['id']}] ({f['created_at'].strftime('%m-%d') if hasattr(f['created_at'], 'strftime') else str(f['created_at'])[:10]}) {f['content']}"
            for f in fragments
        ]
    )
    
    # 调用 AI 进行整理
    prompt = CONSOLIDATION_PROMPT.format(fragments=fragments_text)
    
    # 使用环境变量配置的模型，默认 haiku 节省成本
    consolidation_model = os.getenv("MEMORY_MODEL", "") or os.getenv(
        "DEFAULT_MODEL", "anthropic/claude-haiku-4.5"
    )
    
    if not api_key:
        api_key = os.getenv("API_KEY", "")
    if not api_base_url:
        api_base_url = os.getenv("API_BASE_URL", "https://openrouter.ai/api/v1/chat/completions")
    
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            # 最多重试2次（应对429限流）
            last_error = None
            for attempt in range(3):
                response = await client.post(
                    api_base_url,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": consolidation_model,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 2000,
                    },
                )
                
                if response.status_code == 429:
                    wait_time = (attempt + 1) * 10
                    print(f"⚠️ 整理API 429限流，{wait_time}秒后重试（第{attempt + 1}次）")
                    last_error = f"429 Too Many Requests (重试{attempt + 1}次)"
                    await asyncio.sleep(wait_time)
                    continue
                
                if response.status_code != 200:
                    last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                    print(f"⚠️ 整理API返回 {response.status_code}: {response.text[:200]}")
                    break
                
                last_error = None
                break
            
            if last_error:
                return {"status": "error", "error": f"API调用失败: {last_error}"}
            
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            # 解析 JSON（三层容错）
            json_match = re.search(r"\[[\s\S]*\]", content)
            if json_match:
                json_str = json_match.group()
                try:
                    events = json.loads(json_str)
                except json.JSONDecodeError:
                    # 方案1：用 strict=False
                    try:
                        events = json.loads(json_str, strict=False)
                    except json.JSONDecodeError:
                        # 方案2：去掉控制字符后重试
                        cleaned = re.sub(r"[\x00-\x1f\x7f]", " ", json_str)
                        try:
                            events = json.loads(cleaned)
                        except json.JSONDecodeError as e:
                            # 方案3：让 AI 重新格式化
                            print(f"⚠️ JSON解析失败，尝试让AI修复: {e}")
                            fix_resp = await client.post(
                                api_base_url,
                                headers={
                                    "Authorization": f"Bearer {api_key}",
                                    "Content-Type": "application/json",
                                },
                                json={
                                    "model": consolidation_model,
                                    "messages": [
                                        {
                                            "role": "user",
                                            "content": f"请修复以下JSON的语法错误，只输出修复后的JSON数组，不要其他内容：\n{json_str[:2000]}",
                                        }
                                    ],
                                    "max_tokens": 2000,
                                },
                            )
                            if fix_resp.status_code == 200:
                                fix_content = (
                                    fix_resp.json()
                                    .get("choices", [{}])[0]
                                    .get("message", {})
                                    .get("content", "")
                                )
                                fix_match = re.search(r"\[[\s\S]*\]", fix_content)
                                if fix_match:
                                    try:
                                        events = json.loads(fix_match.group())
                                        print(f"✅ AI修复JSON成功")
                                    except json.JSONDecodeError:
                                        return {
                                            "status": "error",
                                            "error": "JSON解析失败（AI修复也失败）",
                                            "raw": content[:500],
                                        }
                                else:
                                    return {
                                        "status": "error",
                                        "error": "AI修复未返回有效JSON",
                                        "raw": content[:500],
                                    }
                            else:
                                return {
                                    "status": "error",
                                    "error": f"JSON解析失败，AI修复请求失败: HTTP {fix_resp.status_code}",
                                    "raw": content[:500],
                                }
            else:
                return {
                    "status": "error",
                    "error": "无法解析 AI 返回的 JSON",
                    "raw": content,
                }
            
            # 创建事件记忆并停用碎片
            created_count = 0
            for event in events:
                merged_ids = event.get("merged_ids", [])
                if merged_ids:
                    await create_event_memory(
                        title=event.get("title", ""),
                        content=event.get("content", ""),
                        importance=event.get("importance", 5),
                        event_date=start_date,
                        merged_from=merged_ids,
                    )
                    created_count += 1
            
            # 停用所有已处理的碎片
            all_fragment_ids = [f["id"] for f in fragments]
            await deactivate_memories(all_fragment_ids)
            
            return {
                "status": "ok",
                "start_date": str(start_date),
                "end_date": str(end_date),
                "fragments_processed": len(fragments),
                "events_created": created_count,
            }
    
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def consolidate_memories_for_date(event_date: date, **kwargs) -> Dict[str, Any]:
    """整理指定日期的碎片记忆"""
    return await consolidate_memories_for_date_range(event_date, event_date, **kwargs)
