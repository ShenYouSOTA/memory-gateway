"""
分区缓存核心逻辑

从 main.py 迁移出来的分区缓存相关函数。
"""

import os
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone


def is_anthropic_model(model: str) -> bool:
    """判断是否为 Anthropic Claude 系列模型（只有 Claude 支持 cache_control）"""
    model_lower = model.lower()
    return "claude" in model_lower or "anthropic" in model_lower


def strip_cache_control(messages: list):
    """
    剥掉消息中的 cache_control 字段，非 Claude 模型用不了。
    如果 content 数组只剩纯文本 block，降级回字符串格式。
    """
    stripped = 0
    for msg in messages:
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict) and "cache_control" in block:
                del block["cache_control"]
                stripped += 1
        if (
            len(content) == 1
            and isinstance(content[0], dict)
            and content[0].get("type") == "text"
        ):
            msg["content"] = content[0]["text"]
    if stripped > 0:
        print(
            f"🔧 兼容性处理: 剥离了 {stripped} 个 cache_control 字段（非 Claude 模型）"
        )


def group_by_rounds(history: list) -> list:
    """将历史消息按轮次分组"""
    rounds = []
    current_round = []
    
    for msg in history:
        role = msg.get("role", "")
        if role == "user" and current_round:
            rounds.append(current_round)
            current_round = []
        current_round.append(msg)
    
    if current_round:
        rounds.append(current_round)
    
    return rounds


def should_rotate(b_rounds_count: int, x: int, a_msgs: list) -> bool:
    """判断是否需要轮转"""
    return b_rounds_count >= x and len(a_msgs) > 0


def build_time_injection(timezone_hours: int = 8) -> str:
    """构建时间注入文本"""
    now = datetime.now(timezone(timedelta(hours=timezone_hours)))
    weekday_names = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    weekday = weekday_names[now.weekday()]
    time_str = now.strftime("%Y年%m月%d日 %H:%M")
    return f"【当前时间】{time_str} {weekday}"


async def generate_summary(
    messages: list,
    session_id: str = "",
    api_key: str = "",
    api_base_url: str = "",
    model: str = "anthropic/claude-haiku-4.5",
    extra_headers: dict = None,
) -> str:
    """调用轻量模型压缩A区消息为摘要"""
    import httpx
    
    if not messages:
        return ""
    
    conversation_text = ""
    for msg in messages:
        role_label = "用户" if msg["role"] == "user" else "AI"
        content = msg["content"] if isinstance(msg["content"], str) else str(msg["content"])
        conversation_text += f"{role_label}: {content}\n\n"
    
    prompt = f"""请将以下对话压缩成简洁摘要。保留关键信息（事件、决定、情感、约定），去掉日常寒暄和重复内容。用第三人称叙述，控制在300字以内。

---
{conversation_text}
---

摘要："""
    
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        if extra_headers:
            headers.update(extra_headers)
        
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                api_base_url,
                headers=headers,
                json={
                    "model": model,
                    "max_tokens": 500,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            if response.status_code == 200:
                data = response.json()
                if "choices" in data:
                    summary = data["choices"][0]["message"]["content"].strip()
                    print(f"📝 生成摘要: {len(summary)}字")
                    return summary
    except Exception as e:
        print(f"[generate_summary] 错误: {e}")
    
    return ""


async def build_basic_cached(
    history: list,
    base_prompt: str,
    user_message: str,
    current_user_msg: dict,
    timezone_hours: int = 8,
    memory_text: str = "",
) -> list:
    """基础版prompt caching（历史不够分区时的降级模式）"""
    result = []
    if base_prompt:
        result.append({
            "role": "system",
            "content": [
                {
                    "type": "text",
                    "text": base_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
        })
    
    for msg in history:
        m = {k: v for k, v in msg.items() if k not in ("created_at",)}
        result.append(m)
    
    if current_user_msg:
        parts = [build_time_injection(timezone_hours)]
        if memory_text:
            parts.append(memory_text)
        parts.append(current_user_msg["content"])
        result.append({"role": "user", "content": "\n\n".join(parts)})
    
    return result


async def build_partitioned_messages(
    session_id: str,
    all_messages: list,
    base_prompt: str,
    user_message: str,
    # 配置参数
    partition_x: int = 15,
    partition_trigger: str = "rounds",
    partition_window: int = 30,
    max_rotations: int = 2,
    timezone_hours: int = 8,
    # 依赖函数
    get_cache_state=None,
    save_cache_state=None,
    generate_summary_func=None,
    memory_text: str = "",
) -> list:
    """
    分区缓存模式：构建带breakpoint的messages数组。
    """
    non_system = [m for m in all_messages if m.get("role") != "system"]
    
    current_user_msg = None
    history = non_system[:]
    if history and history[-1].get("role") == "user":
        current_user_msg = history.pop()
    
    # 清洗孤立的tool消息
    cleaned = []
    orphan_count = 0
    for msg in history:
        if msg.get("role") == "tool":
            prev = cleaned[-1] if cleaned else None
            if prev and (
                prev.get("role") == "tool"
                or (prev.get("role") == "assistant" and prev.get("tool_calls"))
            ):
                cleaned.append(msg)
            else:
                orphan_count += 1
        else:
            cleaned.append(msg)
    if orphan_count > 0:
        print(f"⚠️ 清理了 {orphan_count} 条孤立tool消息")
    history = cleaned
    
    # 按逻辑轮分组
    rounds = group_by_rounds(history)
    total_rounds = len(rounds)
    
    state = await get_cache_state(session_id) if get_cache_state else {}
    summary_parts = state.get("summary_parts", [])
    a_start_round = state.get("a_start_round", 0)
    
    if total_rounds < partition_x:
        return await build_basic_cached(
            history, base_prompt, user_message, current_user_msg,
            timezone_hours, memory_text
        )
    
    # 计算A/B区
    a_end_round = a_start_round + partition_x
    a_round_groups = rounds[a_start_round:a_end_round]
    b_round_groups = rounds[a_end_round:]
    a_msgs = [msg for rnd in a_round_groups for msg in rnd]
    b_msgs = [msg for rnd in b_round_groups for msg in rnd]
    b_rounds_count = len(b_round_groups)
    
    rotation_count = 0
    max_rot = max_rotations if partition_trigger == "time" else 999
    while should_rotate(b_rounds_count, partition_x, a_msgs) and rotation_count < max_rot:
        rotation_count += 1
        trigger_info = (
            f"B区{b_rounds_count}轮 >= X={partition_x}"
            if partition_trigger != "time"
            else f"A区首条消息超出{partition_window}分钟窗口"
        )
        print(f"🔄 轮转#{rotation_count}: session={session_id}, {trigger_info}")
        
        if generate_summary_func:
            new_summary = await generate_summary_func(a_msgs, session_id)
            if new_summary:
                summary_parts.append(new_summary)
        
        a_start_round += partition_x
        a_end_round = a_start_round + partition_x
        a_round_groups = rounds[a_start_round:a_end_round]
        b_round_groups = rounds[a_end_round:]
        a_msgs = [msg for rnd in a_round_groups for msg in rnd]
        b_msgs = [msg for rnd in b_round_groups for msg in rnd]
        b_rounds_count = len(b_round_groups)
    
    if rotation_count > 0 and save_cache_state:
        await save_cache_state(session_id, summary_parts, a_start_round)
        summary_total = sum(len(p) for p in summary_parts)
        print(f"🔄 轮转完成(共{rotation_count}次): 摘要{len(summary_parts)}段/{summary_total}字")
    
    # 拼装messages
    result = []
    if base_prompt:
        result.append({
            "role": "system",
            "content": [
                {
                    "type": "text",
                    "text": base_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
        })
    
    # 摘要区
    if summary_parts:
        blocks = [{"type": "text", "text": "[以下是之前对话的摘要，帮助你回忆上下文]"}]
        for i, part in enumerate(summary_parts):
            item = {"type": "text", "text": part}
            if i == len(summary_parts) - 1:
                item["cache_control"] = {"type": "ephemeral"}
            blocks.append(item)
        result.append({"role": "user", "content": blocks})
        result.append({"role": "assistant", "content": "好的，我已了解之前的对话内容。"})
    
    for i, msg in enumerate(a_msgs):
        m = {k: v for k, v in msg.items() if k not in ("created_at",)}
        if i == len(a_msgs) - 1 and msg.get("role") != "tool":
            text = m.get("content") or ""
            if isinstance(text, str) and text:
                m["content"] = [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]
        result.append(m)
    
    for i, msg in enumerate(b_msgs):
        m = {k: v for k, v in msg.items() if k not in ("created_at",)}
        if i == len(b_msgs) - 1 and len(b_msgs) > 0 and msg.get("role") != "tool":
            text = m.get("content") or ""
            if isinstance(text, str) and text:
                m["content"] = [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]
        result.append(m)
    
    if current_user_msg:
        parts = [build_time_injection(timezone_hours)]
        if memory_text:
            parts.append(memory_text)
        
        current_text = current_user_msg["content"]
        if isinstance(current_text, list):
            current_text = " ".join(
                item.get("text", "")
                for item in current_text
                if isinstance(item, dict) and item.get("type") == "text"
            )
        parts.append(current_text)
        result.append({"role": "user", "content": "\n\n".join(parts)})
    
    bp_count = 1 + (1 if summary_parts else 0) + (1 if a_msgs else 0) + (1 if b_msgs else 0)
    summary_total = sum(len(p) for p in summary_parts)
    print(f"🔒 分区缓存: BP×{bp_count} | 摘要{'有' if summary_parts else '无'}({len(summary_parts)}段/{summary_total}字) | A区{len(a_msgs)}条 | B区{len(b_msgs)}条 | 总{len(result)}条messages")
    return result
