"""
记忆处理辅助函数

从 main.py 迁移出来的记忆处理相关函数。
"""

import os
import json
import asyncio
import httpx
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone


async def build_system_prompt_with_memories(
    user_message: str,
    system_prompt: str,
    memory_enabled: bool = False,
    memory_extract_enabled: bool = False,
    max_memories_inject: int = 15,
    api_key: str = "",
    api_base_url: str = "",
    timezone_hours: int = 8,
) -> str:
    """构建带记忆的 system prompt"""
    from database import search_memories
    
    if not memory_enabled or not memory_extract_enabled:
        return system_prompt
    
    if max_memories_inject <= 0:
        return system_prompt
    
    try:
        memories = await search_memories(user_message, limit=max_memories_inject)
        
        if not memories:
            return system_prompt
        
        # 格式化记忆文本（带日期，帮助模型判断新旧）
        memory_lines = []
        for mem in memories:
            date_str = ""
            if mem.get("created_at"):
                try:
                    utc_str = str(mem["created_at"])[:19]
                    utc_dt = datetime.strptime(utc_str, "%Y-%m-%d %H:%M:%S").replace(
                        tzinfo=timezone.utc
                    )
                    local_dt = utc_dt + timedelta(hours=timezone_hours)
                    date_str = f"[{local_dt.strftime('%Y-%m-%d')}] "
                except:
                    date_str = f"[{str(mem['created_at'])[:10]}] "
            memory_lines.append(f"- {date_str}{mem['content']}")
        memory_text = "\n".join(memory_lines)
        
        enhanced_prompt = f"""{system_prompt}

【从过往对话中检索到的相关记忆】
{memory_text}

# 记忆应用
- 像朋友般自然运用这些记忆，不刻意展示
- 仅在相关话题出现时引用，避免主动提及
- 对重要信息（如健康、日期、约定）保持一致性
- 新信息与记忆冲突时，以新信息为准
- 模糊记忆可表达不确定性："记得你似乎说过..."
"""
        return enhanced_prompt
    except Exception as e:
        print(f"[build_system_prompt_with_memories] 错误: {e}")
        return system_prompt


# 记忆过滤黑名单
META_BLACKLIST = [
    "记忆库", "记忆系统", "检索", "没有被记录", "没有被提取",
    "记忆遗漏", "尚未被记录", "写入不完整", "检索功能", "系统没有返回",
    "关键词匹配", "语义匹配", "语义检索", "阈值", "数据库",
    "seed", "导入", "部署", "bug", "debug", "端口", "网关",
]


async def process_memories_background(
    session_id: str,
    user_msg: str,
    assistant_msg: str,
    model: str,
    context_messages: list = None,
    skip_conversation_log: bool = False,
    tool_messages: list = None,
    assistant_tool_calls: list = None,
    assistant_reasoning: str = None,
    # 配置参数
    memory_extract_enabled: bool = True,
    memory_extract_interval: int = 1,
    round_counter: int = 0,
):
    """
    后台异步：存储对话 + 提取记忆（不阻塞主流程）
    
    返回：
        new_round_counter: 更新后的轮次计数器
    """
    from database import (
        save_message, save_memory, get_last_user_content,
        update_last_assistant_message, get_recent_memories,
        get_all_memories_count,
    )
    from memory_extractor import extract_memories
    
    try:
        # 1. 存储对话记录（除非明确跳过）
        if skip_conversation_log:
            print(f"⏭️  跳过对话存储（辅助请求）")
        elif tool_messages:
            # 工具结果轮次
            for tm in tool_messages:
                meta_dict = {}
                if tm.get("tool_call_id"):
                    meta_dict["tool_call_id"] = tm["tool_call_id"]
                if tm.get("name"):
                    meta_dict["name"] = tm["name"]
                meta = json.dumps(meta_dict) if meta_dict else None
                await save_message(session_id, "tool", tm.get("content", ""), model, metadata=meta)
            
            if assistant_msg or assistant_tool_calls:
                ast_meta_dict = {}
                if assistant_tool_calls:
                    ast_meta_dict["tool_calls"] = assistant_tool_calls
                if assistant_reasoning:
                    ast_meta_dict["reasoning_content"] = assistant_reasoning
                ast_meta = json.dumps(ast_meta_dict) if ast_meta_dict else None
                await save_message(session_id, "assistant", assistant_msg or "", model, metadata=ast_meta)
        else:
            # 普通对话或首次工具调用
            ast_meta_dict = {}
            if assistant_tool_calls:
                ast_meta_dict["tool_calls"] = assistant_tool_calls
            if assistant_reasoning:
                ast_meta_dict["reasoning_content"] = assistant_reasoning
            assistant_meta = json.dumps(ast_meta_dict) if ast_meta_dict else None
            
            if assistant_tool_calls:
                await save_message(session_id, "user", user_msg, model)
                await save_message(session_id, "assistant", assistant_msg or "", model, metadata=assistant_meta)
            else:
                # 纯文字对话：re-roll检测
                last_user = await get_last_user_content(session_id)
                if last_user and last_user.strip() == user_msg.strip():
                    updated = await update_last_assistant_message(session_id, assistant_msg, model)
                    if not updated:
                        await save_message(session_id, "user", user_msg, model)
                        await save_message(session_id, "assistant", assistant_msg, model, metadata=assistant_meta)
                else:
                    await save_message(session_id, "user", user_msg, model)
                    await save_message(session_id, "assistant", assistant_msg, model, metadata=assistant_meta)
        
        # 2. 检查是否需要提取记忆
        if not memory_extract_enabled:
            return round_counter
        
        if memory_extract_interval == 0:
            return round_counter
        
        round_counter += 1
        
        if memory_extract_interval > 1 and (round_counter % memory_extract_interval != 0):
            return round_counter
        
        # 3. 获取已有记忆
        existing = await get_recent_memories(limit=80)
        existing_contents = [r["content"] for r in existing]
        
        # 4. 构建用于提取的消息列表
        if context_messages:
            tail_count = memory_extract_interval * 2
            recent_msgs = list(context_messages)[-tail_count:] if len(context_messages) > tail_count else list(context_messages)
            messages_for_extraction = recent_msgs + [{"role": "assistant", "content": assistant_msg}]
        else:
            messages_for_extraction = [
                {"role": "user", "content": user_msg},
                {"role": "assistant", "content": assistant_msg},
            ]
        
        new_memories = await extract_memories(messages_for_extraction, existing_memories=existing_contents)
        
        # 5. 过滤垃圾记忆
        filtered_memories = []
        for mem in new_memories:
            content = mem["content"]
            if any(kw in content for kw in META_BLACKLIST):
                continue
            filtered_memories.append(mem)
        
        for mem in filtered_memories:
            await save_memory(content=mem["content"], importance=mem["importance"], source_session=session_id)
        
        if filtered_memories:
            total = await get_all_memories_count()
            print(f"💾 已保存 {len(filtered_memories)} 条新记忆，总计 {total} 条")
        
        return round_counter
    
    except Exception as e:
        print(f"⚠️  后台记忆处理失败: {e}")
        return round_counter


async def build_memory_text(
    user_message: str,
    memory_enabled: bool = False,
    memory_extract_enabled: bool = False,
    max_memories_inject: int = 15,
    timezone_hours: int = 8,
) -> str:
    """构建记忆文本（用于注入）"""
    from database import search_memories
    
    if not memory_enabled or not memory_extract_enabled:
        return ""
    
    if max_memories_inject <= 0:
        return ""
    
    try:
        memories = await search_memories(user_message, limit=max_memories_inject)
        
        if not memories:
            return ""
        
        # 格式化记忆文本
        memory_lines = []
        for mem in memories:
            date_str = ""
            if mem.get("created_at"):
                try:
                    utc_str = str(mem["created_at"])[:19]
                    utc_dt = datetime.strptime(utc_str, "%Y-%m-%d %H:%M:%S").replace(
                        tzinfo=timezone.utc
                    )
                    local_dt = utc_dt + timedelta(hours=timezone_hours)
                    date_str = f"[{local_dt.strftime('%Y-%m-%d')}] "
                except:
                    date_str = f"[{str(mem['created_at'])[:10]}] "
            memory_lines.append(f"- {date_str}{mem['content']}")
        
        return "\n".join(memory_lines)
    except Exception as e:
        print(f"[build_memory_text] 错误: {e}")
        return ""
