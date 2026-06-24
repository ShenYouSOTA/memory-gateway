"""
AI Memory Gateway — 带记忆系统的 LLM 转发网关
=============================================
让你的 AI 拥有长期记忆。

工作原理：
1. 接收客户端（Kelivo / ChatBox / 任何 OpenAI 兼容客户端）的消息
2. 自动搜索数据库中的相关记忆，注入 system prompt
3. 转发给 LLM API（支持 OpenRouter / OpenAI / 任何兼容接口）
4. 后台自动存储对话 + 用 AI 提取新记忆

环境变量 MEMORY_ENABLED=false 时退化为纯转发网关（第一阶段）。
"""

import os
import json
import uuid
import asyncio
import httpx
from datetime import datetime, timedelta, timezone
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from database import (
    init_tables,
    close_pool,
    save_message,
    search_memories,
    save_memory,
    get_all_memories_count,
    get_recent_memories,
    get_all_memories,
    get_pool,
    get_all_memories_detail,
    update_memory,
    delete_memory,
    delete_memories_batch,
    get_gateway_config,
    set_gateway_config,
    get_all_gateway_config,
    get_conversation_messages,
    get_session_cache_state,
    save_session_cache_state,
    delete_session_cache_state,
    save_token_usage,
    ensure_token_usage_table,
    ensure_conversation_titles_table,
    get_conversations_paginated,
    delete_conversation,
    batch_delete_conversations,
    merge_sessions_to_target,
    list_all_session_cache_states,
    export_all_conversations,
    import_conversations,
    get_last_user_content,
    update_last_assistant_message,
    db_row_to_message,
    backfill_memory_embeddings,
    get_pending_memory_embedding_count,
    search_conversations,
    update_message_content,
    rename_session_id,
    get_fragments_by_date,
    get_fragments_by_date_range,
    create_event_memory,
    deactivate_memories,
    promote_to_core,
    merge_memories,
    check_duplicate_memory,
    update_memory_with_layer,
    get_layer_statistics,
    cleanup_old_fragments,
    revert_merge,
)
import database as _db_module  # 用于 /api/settings 热更新 database.py 全局变量
from memory_extractor import extract_memories, score_memories
from repositories.memory_repo import PostgresMemoryRepository
from repositories.conversation_repo import PostgresConversationRepository
from repositories.config_repo import PostgresConfigRepository
from repositories.vector_repo import ZvecVectorRepository, ZVEC_ENABLED
from services.memory_service import MemoryService
from services.chat_service import ChatService
from services.conversation_service import ConversationService
from services.config_service import ConfigService
from services.extraction_service import ExtractionService
from services.cache_service import CacheService

# ============================================================
# 配置项 —— 全部从环境变量读取，部署时在云平台面板里设置
# ============================================================

# 你的 API Key（OpenRouter / OpenAI / 其他兼容服务）
API_KEY = os.getenv("API_KEY", "")

# API 地址（改这个就能切换不同的 LLM 服务商）
# OpenRouter: https://openrouter.ai/api/v1/chat/completions
# OpenAI:     https://api.openai.com/v1/chat/completions
# 本地 Ollama: http://localhost:11434/v1/chat/completions
API_BASE_URL = os.getenv(
    "API_BASE_URL", "https://openrouter.ai/api/v1/chat/completions"
)

# 默认模型（如果客户端没指定就用这个）
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "anthropic/claude-sonnet-4")

# 网关端口
PORT = int(os.getenv("PORT", "8080"))

# 记忆系统开关（数据库出问题时可以临时关掉）
MEMORY_ENABLED = os.getenv("MEMORY_ENABLED", "false").lower() == "true"

# 每次注入的最大记忆条数
MAX_MEMORIES_INJECT = int(os.getenv("MAX_MEMORIES_INJECT", "15"))

# 记忆提取间隔（0 = 禁用自动提取，1 = 每轮提取，N = 每 N 轮提取一次）
MEMORY_EXTRACT_INTERVAL = int(os.getenv("MEMORY_EXTRACT_INTERVAL", "1"))

# 记忆提取+注入总开关（false时数据库仍连接、消息仍存储，但不提取也不注入记忆）
MEMORY_EXTRACT_ENABLED = os.getenv("MEMORY_EXTRACT_ENABLED", "true").lower() == "true"

# 分区缓存
CACHE_PARTITION_ENABLED = (
    os.getenv("CACHE_PARTITION_ENABLED", "false").lower() == "true"
)
CACHE_PARTITION_X = int(os.getenv("CACHE_PARTITION_X", "15"))
CACHE_SUMMARY_MODEL = os.getenv("CACHE_SUMMARY_MODEL", "anthropic/claude-haiku-4.5")
CACHE_PARTITION_TRIGGER = os.getenv(
    "CACHE_PARTITION_TRIGGER", "rounds"
)  # rounds=按轮次 | time=按时间窗口
CACHE_PARTITION_WINDOW = int(
    os.getenv("CACHE_PARTITION_WINDOW", "30")
)  # 时间窗口（分钟），仅 trigger=time 时生效
PARTITION_SESSION_ID = os.getenv("PARTITION_SESSION_ID", "")


def get_active_session_id() -> str:
    return PARTITION_SESSION_ID


# 时区偏移（小时），用于记忆注入时的日期显示，默认 UTC+8
TIMEZONE_HOURS = int(os.getenv("TIMEZONE_HOURS", "8"))

# 轮次计数器
_round_counter = 0

# 强制流式传输（部分客户端不发stream=true导致thinking数据丢失，开启后强制所有请求走流式）
FORCE_STREAM = os.getenv("FORCE_STREAM", "false").lower() == "true"

# 推理/思维链参数（部分客户端走网关时不会自动添加reasoning参数，导致上游不返回thinking数据）
# 设为 low/medium/high 会在转发请求时注入 reasoning_effort 参数
REASONING_EFFORT = os.getenv("REASONING_EFFORT", "")

# 额外的请求头（有些 API 需要，比如 OpenRouter 需要 Referer）
EXTRA_REFERER = os.getenv("EXTRA_REFERER", "https://ai-memory-gateway.local")
EXTRA_TITLE = os.getenv("EXTRA_TITLE", "AI Memory Gateway")


# ============================================================
# 人设加载
# ============================================================


def load_system_prompt():
    """从 system_prompt.txt 文件读取人设内容"""
    prompt_path = os.path.join(os.path.dirname(__file__), "system_prompt.txt")
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if content:
                return content
    except FileNotFoundError:
        pass
    print("ℹ️  未找到 system_prompt.txt 或文件为空，将不注入 system prompt")
    return ""


SYSTEM_PROMPT = load_system_prompt()
_DEFAULT_SYSTEM_PROMPT = SYSTEM_PROMPT  # 保留文件原始版本
if SYSTEM_PROMPT:
    print(f"✅ 人设已加载，长度：{len(SYSTEM_PROMPT)} 字符")
else:
    print("ℹ️  无人设，纯转发模式")

# System Prompt 缓存（支持设置面板热更新）
_cached_system_prompt = None
_cached_system_prompt_loaded = False


async def get_system_prompt() -> str:
    """获取 system prompt（数据库优先，fallback 到文件）"""
    global _cached_system_prompt, _cached_system_prompt_loaded
    if _cached_system_prompt_loaded:
        return _cached_system_prompt or ""
    try:
        db_prompt = await get_gateway_config("systemPrompt", "")
        if db_prompt:
            _cached_system_prompt = db_prompt
        else:
            _cached_system_prompt = _DEFAULT_SYSTEM_PROMPT
            if _DEFAULT_SYSTEM_PROMPT:
                await set_gateway_config("systemPrompt", _DEFAULT_SYSTEM_PROMPT)
        _cached_system_prompt_loaded = True
        return _cached_system_prompt or ""
    except Exception:
        _cached_system_prompt = _DEFAULT_SYSTEM_PROMPT
        _cached_system_prompt_loaded = True
        return _cached_system_prompt or ""


def invalidate_system_prompt_cache():
    """清除 system prompt 缓存（设置面板更新后调用）"""
    global _cached_system_prompt, _cached_system_prompt_loaded
    _cached_system_prompt = None
    _cached_system_prompt_loaded = False


# ============================================================
# 应用生命周期管理
# ============================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动时初始化数据库，关闭时断开连接"""
    global PARTITION_SESSION_ID
    if MEMORY_ENABLED:
        try:
            await init_tables()
            await ensure_token_usage_table()
            await ensure_conversation_titles_table()
            count = await get_all_memories_count()
            print(f"✅ 记忆系统已启动，当前记忆数量：{count}")

            # 创建 Repository 和 Service 实例，注入到 app.state
            pool = await get_pool()
            memory_repo = PostgresMemoryRepository(pool)
            conversation_repo = PostgresConversationRepository(pool)
            config_repo = PostgresConfigRepository(pool)

            # 初始化 zvec 向量存储（如果启用）
            vector_repo = None
            if ZVEC_ENABLED:
                try:
                    vector_repo = ZvecVectorRepository()
                    await vector_repo.init()
                    print("✅ zvec 向量存储已初始化")
                except Exception as e:
                    print(f"⚠️ zvec 初始化失败，回退到 pgvector: {e}")
                    vector_repo = None

            app.state.memory_repo = memory_repo
            app.state.conversation_repo = conversation_repo
            app.state.config_repo = config_repo
            app.state.vector_repo = vector_repo
            app.state.memory_service = MemoryService(memory_repo, vector_repo)
            app.state.chat_service = ChatService(conversation_repo, memory_repo)
            app.state.conversation_service = ConversationService(conversation_repo)
            app.state.config_service = ConfigService(config_repo)
            app.state.extraction_service = ExtractionService(memory_repo)
            app.state.cache_service = CacheService(conversation_repo)
            print("✅ Service 层依赖注入完成")

            # 从数据库恢复面板配置（重启后保持Dashboard修改过的值）
            try:
                db_cfg = await get_all_gateway_config()
                if db_cfg:
                    _RESTORE_MAIN = {
                        "API_BASE_URL": str,
                        "API_KEY": str,
                        "DEFAULT_MODEL": str,
                        "MEMORY_ENABLED": lambda v: _parse_bool(v),
                        "MAX_MEMORIES_INJECT": int,
                        "MEMORY_EXTRACT_INTERVAL": int,
                        "CACHE_PARTITION_ENABLED": lambda v: _parse_bool(v),
                        "CACHE_PARTITION_X": int,
                        "CACHE_PARTITION_TRIGGER": str,
                        "CACHE_PARTITION_WINDOW": int,
                        "CACHE_SUMMARY_MODEL": str,
                        "FORCE_STREAM": lambda v: _parse_bool(v),
                        "REASONING_EFFORT": str,
                    }
                    _RESTORE_DB = {
                        "EMBEDDING_API_KEY": str,
                        "EMBEDDING_BASE_URL": str,
                        "EMBEDDING_MODEL": str,
                        "EMBEDDING_DIM": int,
                        "MIN_SCORE_THRESHOLD": float,
                        "MEMORY_VECTOR_ENABLED": lambda v: _parse_bool(v),
                        "MEMORY_HW_KEYWORD": float,
                        "MEMORY_HW_SEMANTIC": float,
                        "MEMORY_HW_IMPORTANCE": float,
                        "MEMORY_HW_RECENCY": float,
                        "MEMORY_SEMANTIC_THRESHOLD": float,
                    }
                    restored = []
                    for key, val in db_cfg.items():
                        if not val:
                            continue
                        if key in _RESTORE_MAIN:
                            globals()[key] = _RESTORE_MAIN[key](val)
                            restored.append(key)
                        elif key in _RESTORE_DB:
                            setattr(_db_module, key, _RESTORE_DB[key](val))
                            restored.append(key)
                        elif key == "MEMORY_MODEL":
                            os.environ["MEMORY_MODEL"] = str(val)
                            restored.append(key)
                    if restored:
                        print(
                            f"🔄 从数据库恢复 {len(restored)} 项面板配置: {', '.join(restored)}"
                        )
            except Exception as e:
                print(f"[warning] 恢复面板配置失败: {e}")

            if not MEMORY_EXTRACT_ENABLED:
                print("ℹ️  记忆提取+注入已关闭（MEMORY_EXTRACT_ENABLED=false）")

            # 分区缓存：从DB读取活跃对话线ID
            if CACHE_PARTITION_ENABLED:
                db_sid = await get_gateway_config("partition_session_id", "")
                if db_sid:
                    PARTITION_SESSION_ID = db_sid
                    print(f"🔗 活跃对话线(DB): {PARTITION_SESSION_ID}")
                elif PARTITION_SESSION_ID:
                    await set_gateway_config(
                        "partition_session_id", PARTITION_SESSION_ID
                    )
                    print(f"🔗 活跃对话线(ENV→DB): {PARTITION_SESSION_ID}")
                print(
                    f"🔒 分区缓存已启用: X={CACHE_PARTITION_X}, 摘要模型={CACHE_SUMMARY_MODEL}"
                )
        except Exception as e:
            print(f"⚠️  数据库初始化失败: {e}")
            print("⚠️  记忆系统将不可用，但网关仍可正常转发")
    else:
        print("ℹ️  记忆系统已关闭（设置 MEMORY_ENABLED=true 开启）")

    yield

    if MEMORY_ENABLED:
        await close_pool()


app = FastAPI(title="AI Memory Gateway", version="2.0.0", lifespan=lifespan)

# 静态文件和模板配置
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 挂载路由模块
from routes import (
    chat_router,
    memories_router,
    conversations_router,
    settings_router,
    partition_router,
    admin_router,
)

app.include_router(chat_router)
app.include_router(memories_router)
app.include_router(conversations_router)
app.include_router(settings_router)
app.include_router(partition_router)
app.include_router(admin_router)


# ============================================================
# 记忆注入
# ============================================================

from utils.memory_helpers import build_system_prompt_with_memories as _build_system_prompt_with_memories


# ============================================================
# 分区缓存（Partition Cache）
# ============================================================

from utils.partition_cache import (
    group_by_rounds as _group_by_rounds,
    should_rotate as _should_rotate,
    build_time_injection as _build_time_injection,
    generate_summary as _generate_summary,
    build_basic_cached as _build_basic_cached,
    build_partitioned_messages as _build_partitioned_messages,
    is_anthropic_model as _is_anthropic_model,
    strip_cache_control as _strip_cache_control,
)


# ============================================================
# 后台记忆处理
# ============================================================

from utils.memory_helpers import process_memories_background as _process_memories_background
from utils.stream_helpers import stream_and_capture as _stream_and_capture


# ============================================================
# API 接口
# ============================================================


@app.get("/")
async def health_check():
    """健康检查"""
    memory_count = 0
    if MEMORY_ENABLED:
        try:
            memory_count = await get_all_memories_count()
        except:
            pass

    return {
        "status": "running",
        "gateway": "AI Memory Gateway v2.0",
        "system_prompt_loaded": len(SYSTEM_PROMPT) > 0,
        "system_prompt_length": len(SYSTEM_PROMPT),
        "memory_enabled": MEMORY_ENABLED,
        "memory_count": memory_count,
        "memory_extract_interval": MEMORY_EXTRACT_INTERVAL,
    }


# /v1/models 路由已迁移到 routes/chat.py


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """核心转发接口"""
    if not API_KEY:
        return JSONResponse(
            status_code=500,
            content={"error": "API_KEY 未设置，请在环境变量中配置"},
        )

    body = await request.json()
    messages = body.get("messages", [])

    # ---------- 检测是否应跳过对话存储 ----------
    # 方式1: 客户端通过header显式声明
    skip_conversation_log = (
        request.headers.get("X-Skip-Conversation-Log", "").lower() == "true"
    )

    # 方式2: 自动检测标题生成等辅助请求
    if not skip_conversation_log:
        for msg in messages:
            c = msg.get("content", "")
            if isinstance(c, str):
                cl = c.lower()
                if ("title" in cl and "summarize" in cl) or (
                    "标题" in cl and ("总结" in cl or "概括" in cl)
                ):
                    skip_conversation_log = True
                    print("⏭️  检测到标题生成请求，跳过对话存储")
                    break

    body = await request.json()
    messages = body.get("messages", [])

    # ---------- 提取用户最新消息 ----------
    user_message = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str):
                user_message = content
            elif isinstance(content, list):
                user_message = " ".join(
                    item.get("text", "")
                    for item in content
                    if isinstance(item, dict) and item.get("type") == "text"
                )
            break

    # ---------- 构建 system prompt ----------
    # 先保存原始对话消息（不含 system prompt），用于记忆提取
    original_messages = [msg for msg in messages if msg.get("role") != "system"]

    # ---------- 检测工具调用消息 ----------
    tool_messages = [m for m in messages if m.get("role") == "tool"]
    if tool_messages:
        print(f"🔧 检测到 {len(tool_messages)} 条工具结果消息")

    # ---------- 生成 session ID ----------
    session_id = str(uuid.uuid4())[:8]

    # ---------- 分区缓存模式 ----------
    if CACHE_PARTITION_ENABLED:
        active_sid = get_active_session_id()
        if active_sid:
            session_id = active_sid

        # 从DB读取历史
        try:
            db_history = await get_conversation_messages(session_id, limit=10000)
            db_msgs = []
            for m in db_history or []:
                msg = db_row_to_message(m)
                msg["created_at"] = m.get("created_at")  # 保留时间戳供分区时间窗口判断
                db_msgs.append(msg)
        except Exception as e:
            print(f"[warning] 分区模式读取历史失败: {e}")
            db_msgs = []

        # 提取客户端新消息（非system），可能是user、tool、或带tool_calls的assistant
        client_new_msgs = [m for m in messages if m.get("role") != "system"]
        # 分区模式下，assistant消息来自上一轮response（DB里已存），过滤掉避免重复
        client_new_msgs = [m for m in client_new_msgs if m.get("role") != "assistant"]
        # 工具结果轮次处理：基于DB状态 + 当前轮次tool_call_id精确判断
        client_tools = [m for m in client_new_msgs if m.get("role") == "tool"]
        if client_tools:
            # 判断DB是否处于"等待tool结果"状态（最后一条是assistant(tool_calls)）
            db_last = db_msgs[-1] if db_msgs else None
            db_expecting_tool = (
                db_last
                and db_last.get("role") == "assistant"
                and db_last.get("tool_calls")
            )

            if not db_expecting_tool:
                # DB不在等待tool结果 → 客户端的所有tool都是历史残留（含手动删除后的幽灵）
                stale_ids = [m.get("tool_call_id", "?") for m in client_tools]
                print(
                    f"🔧 去重: DB未在等待tool结果，丢弃{len(client_tools)}条客户端tool (ids: {stale_ids})"
                )
                client_new_msgs = [
                    m for m in client_new_msgs if m.get("role") != "tool"
                ]
            else:
                # DB在等待tool → 只保留匹配当前轮次assistant(tool_calls)的tool
                expected_tool_ids = {
                    tc.get("id") for tc in db_last.get("tool_calls", []) if tc.get("id")
                }
                new_tools = [
                    m
                    for m in client_tools
                    if m.get("tool_call_id") in expected_tool_ids
                ]
                stale_tools = [
                    m
                    for m in client_tools
                    if m.get("tool_call_id") not in expected_tool_ids
                ]

                if stale_tools:
                    print(
                        f"🔧 去重: 丢弃{len(stale_tools)}条非当前轮次tool (ids: {[m.get('tool_call_id', '?') for m in stale_tools]})"
                    )
                if new_tools:
                    print(
                        f"🔧 保留{len(new_tools)}条当前轮次tool (ids: {[m.get('tool_call_id', '?') for m in new_tools]})"
                    )

                # 重建 client_new_msgs
                last_msg = client_new_msgs[-1] if client_new_msgs else None
                client_new_msgs = new_tools[:]
                if last_msg and last_msg.get("role") == "user":
                    client_new_msgs.append(last_msg)

                if new_tools:
                    # Race condition 防护：DB的assistant(tool_calls)已确认存在（db_expecting_tool=True），
                    # 但仍需检查是否被其他并发请求意外清除
                    new_tool_ids = {
                        m.get("tool_call_id")
                        for m in new_tools
                        if m.get("tool_call_id")
                    }
                    db_has_matching_ast = False
                    for m in db_msgs:
                        if m.get("role") == "assistant" and m.get("tool_calls"):
                            ast_tc_ids = {
                                tc.get("id") for tc in m["tool_calls"] if tc.get("id")
                            }
                            if new_tool_ids & ast_tc_ids:
                                db_has_matching_ast = True
                                break
                    if not db_has_matching_ast and new_tool_ids:
                        for m in messages:
                            if m.get("role") == "assistant" and m.get("tool_calls"):
                                ast_tc_ids = {
                                    tc.get("id")
                                    for tc in m["tool_calls"]
                                    if tc.get("id")
                                }
                                if new_tool_ids & ast_tc_ids:
                                    client_new_msgs.insert(0, m)
                                    print(
                                        f"⚠️ Race防护: 从客户端补充assistant(tool_calls)"
                                    )
                                    break
        all_msgs = db_msgs + client_new_msgs

        # 同步更新tool_messages，避免process_memories_background存重复的旧tool
        tool_messages = [m for m in client_new_msgs if m.get("role") == "tool"]

        print(
            f"📦 分区模式: DB历史{len(db_msgs)}条 + 客户端消息{len(client_new_msgs)}条"
        )

        messages = await build_partitioned_messages(
            session_id, all_msgs, SYSTEM_PROMPT, user_message
        )
        body["messages"] = messages

    else:
        # ---------- 原有逻辑：system prompt + 记忆注入 ----------
        if SYSTEM_PROMPT or (
            MEMORY_ENABLED and MEMORY_EXTRACT_ENABLED and user_message
        ):
            if MEMORY_ENABLED and MEMORY_EXTRACT_ENABLED and user_message:
                enhanced_prompt = await build_system_prompt_with_memories(user_message)
            else:
                enhanced_prompt = SYSTEM_PROMPT

            if enhanced_prompt:
                has_system = any(msg.get("role") == "system" for msg in messages)
                if has_system:
                    for i, msg in enumerate(messages):
                        if msg.get("role") == "system":
                            messages[i]["content"] = (
                                enhanced_prompt + "\n\n" + msg["content"]
                            )
                            break
                else:
                    messages.insert(0, {"role": "system", "content": enhanced_prompt})

        body["messages"] = messages

    # ---------- 模型处理 ----------
    model = body.get("model", DEFAULT_MODEL)
    if not model:
        model = DEFAULT_MODEL
    body["model"] = model

    # ---------- cache_control 兼容性处理 ----------
    if CACHE_PARTITION_ENABLED and not _is_anthropic_model(model):
        _strip_cache_control(body.get("messages", []))

    # ---------- 转发请求 ----------
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    # OpenRouter 需要的额外头
    if "openrouter" in API_BASE_URL:
        headers["HTTP-Referer"] = EXTRA_REFERER
        headers["X-Title"] = EXTRA_TITLE

    is_stream = body.get("stream", False)

    # 强制流式传输（解决部分客户端不发stream=true的问题）
    if FORCE_STREAM and not is_stream:
        is_stream = True
        body["stream"] = True
        print(f"⚡ 强制开启流式传输（FORCE_STREAM=true）")

    # 注入推理参数（解决客户端走网关时不带reasoning参数的问题）
    if REASONING_EFFORT:
        # 统一用 reasoning_effort（Claude/OpenAI/Google Gemini OpenAI兼容端点都支持）
        # 先删除客户端可能已带的值，确保用我们配置的
        body.pop("reasoning_effort", None)
        body.pop("google", None)
        body["reasoning_effort"] = REASONING_EFFORT
        print(f"🧠 注入推理参数: reasoning_effort={REASONING_EFFORT}")

    print(
        f"📡 请求: model={model}, stream={is_stream}, memory={'on' if MEMORY_ENABLED else 'off'}",
        flush=True,
    )

    # 调试：打印请求体中的推理相关字段
    debug_keys = {
        k: v
        for k, v in body.items()
        if k in ("reasoning_effort", "google", "reasoning")
    }
    if debug_keys:
        print(f"📡 推理字段: {debug_keys}", flush=True)

    if is_stream:
        return StreamingResponse(
            stream_and_capture(
                headers,
                body,
                session_id,
                user_message,
                model,
                original_messages,
                skip_conversation_log,
                tool_messages,
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )
    else:
        async with httpx.AsyncClient(timeout=300) as client:
            response = await client.post(API_BASE_URL, headers=headers, json=body)

            if response.status_code == 200:
                resp_data = response.json()
                assistant_msg = ""
                assistant_tool_calls = None
                assistant_reasoning = None
                try:
                    msg_obj = resp_data["choices"][0]["message"]
                    assistant_msg = msg_obj.get("content") or ""
                    if msg_obj.get("tool_calls"):
                        assistant_tool_calls = msg_obj["tool_calls"]
                        print(
                            f"🔧 Response 包含 {len(assistant_tool_calls)} 个工具调用"
                        )
                    if msg_obj.get("reasoning_content"):
                        assistant_reasoning = msg_obj["reasoning_content"]
                        print(
                            f"🧠 Response 包含 reasoning_content ({len(assistant_reasoning)}字符)"
                        )
                except (KeyError, IndexError):
                    pass

                if MEMORY_ENABLED and (user_message or tool_messages):
                    asyncio.create_task(
                        process_memories_background(
                            session_id,
                            user_message,
                            assistant_msg,
                            model,
                            context_messages=original_messages,
                            skip_conversation_log=skip_conversation_log,
                            tool_messages=tool_messages,
                            assistant_tool_calls=assistant_tool_calls,
                            assistant_reasoning=assistant_reasoning,
                        )
                    )

                return JSONResponse(status_code=200, content=resp_data)
            else:
                return JSONResponse(
                    status_code=response.status_code, content=response.json()
                )



# ============================================================
# 记忆管理接口
# ============================================================


@app.get("/import/seed-memories")
async def import_seed_memories():
    """一次性导入预置记忆（从 seed_memories.py）"""
    try:
        from seed_memories import run_seed_import

        result = await run_seed_import()
        return result
    except ImportError:
        return {
            "error": "未找到 seed_memories.py，请参考 seed_memories_example.py 创建"
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/export/memories")
async def export_memories():
    """
    导出所有记忆为 JSON（用于备份或迁移）
    浏览器访问这个地址就会返回所有记忆数据
    """
    if not MEMORY_ENABLED:
        return {"error": "记忆系统未启用（设置 MEMORY_ENABLED=true 开启）"}

    try:
        memories = await get_all_memories()
        # 把 datetime 转成字符串
        for mem in memories:
            if mem.get("created_at"):
                mem["created_at"] = str(mem["created_at"])

        return {
            "total": len(memories),
            "exported_at": str(__import__("datetime").datetime.now()),
            "memories": memories,
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """Dashboard - 整合的记忆管理界面"""
    if not MEMORY_ENABLED:
        return HTMLResponse("<h3>记忆系统未启用（设置 MEMORY_ENABLED=true 开启）</h3>")

    return templates.TemplateResponse("dashboard.html", {"request": request})


# ============================================================
# 管理 API - 已迁移到 routes/memories.py
# ============================================================


# /api/memories/* 路由已迁移到 routes/memories.py


@app.post("/import/text")
async def import_text_memories(request: Request):
    """从纯文本导入记忆（每行一条），可选自动评分"""
    if not MEMORY_ENABLED:
        return {"error": "记忆系统未启用（设置 MEMORY_ENABLED=true 开启）"}

    try:
        data = await request.json()
        lines = data.get("lines", [])
        skip_scoring = data.get("skip_scoring", False)

        if not lines:
            return {"error": "没有找到记忆条目"}

        if skip_scoring:
            scored = [{"content": t, "importance": 5} for t in lines]
        else:
            scored = await score_memories(lines)

        imported = 0
        skipped = 0

        for mem in scored:
            content = mem.get("content", "")
            if not content:
                continue

            pool = await get_pool()
            async with pool.acquire() as conn:
                existing = await conn.fetchval(
                    "SELECT COUNT(*) FROM memories WHERE content = $1", content
                )

            if existing > 0:
                skipped += 1
                continue

            await save_memory(
                content=content,
                importance=mem.get("importance", 5),
                source_session="text-import",
            )
            imported += 1

        total = await get_all_memories_count()
        return {
            "status": "done",
            "imported": imported,
            "skipped": skipped,
            "total": total,
        }
    except Exception as e:
        return {"error": str(e)}


@app.post("/import/memories")
async def import_memories(request: Request):
    """从 JSON 导入记忆（用于迁移或恢复备份）"""
    if not MEMORY_ENABLED:
        return {"error": "记忆系统未启用（设置 MEMORY_ENABLED=true 开启）"}

    try:
        data = await request.json()
        memories = data.get("memories", [])

        if not memories:
            return {"error": "没有找到记忆数据，请确认 JSON 格式正确"}

        imported = 0
        skipped = 0

        for mem in memories:
            content = mem.get("content", "")
            if not content:
                continue

            pool = await get_pool()
            async with pool.acquire() as conn:
                existing = await conn.fetchval(
                    "SELECT COUNT(*) FROM memories WHERE content = $1", content
                )

            if existing > 0:
                skipped += 1
                continue

            await save_memory(
                content=content,
                importance=mem.get("importance", 5),
                source_session=mem.get("source_session", "json-import"),
            )
            imported += 1

        total = await get_all_memories_count()
        return {
            "status": "done",
            "imported": imported,
            "skipped": skipped,
            "total": total,
        }
    except Exception as e:
        return {"error": str(e)}


# ============================================================
# 对话记录管理 API - 已迁移到 routes/conversations.py
# ============================================================


# /api/conversations/* 路由已迁移到 routes/conversations.py
# /api/chat/* 路由已迁移到 routes/conversations.py
# /api/admin/merge-sessions 路由已迁移到 routes/admin.py


# ============================================================
# 对话线管理 API（分区缓存）- 已迁移到 routes/partition.py
# ============================================================


# /api/partition/* 路由已迁移到 routes/partition.py


# ============================================================
# 记忆向量补算（带进度追踪）- 已迁移到 routes/admin.py
# ============================================================


# /api/admin/backfill-memory-embeddings/* 路由已迁移到 routes/admin.py


# ============================================================
# 模型列表 API（/api/models）- 已迁移到 routes/admin.py
# ============================================================


# /api/models 路由已迁移到 routes/admin.py


# ============================================================
# 高级设置面板 API（/api/settings）
# Dashboard 前端设置面板用，管理所有运行时可调配置
# ============================================================


def _mask_key(key_value: str) -> str:
    """API Key 打码：只露前5位和后4位"""
    if not key_value:
        return ""
    if len(key_value) < 10:
        return "****"
    return key_value[:5] + "****" + key_value[-4:]


def _is_masked(value: str) -> bool:
    """判断值是否是打码值（用户没改过）"""
    return "****" in str(value)


def _parse_bool(val, fallback=False) -> bool:
    """解析布尔值（兼容字符串/布尔/None）"""
    if val is None:
        return fallback
    if isinstance(val, bool):
        return val
    return str(val).lower() in ("true", "1", "yes")


@app.get("/api/settings")
async def get_settings():
    """获取高级设置（数据库优先，fallback 到环境变量/运行时默认值）"""
    try:
        db = await get_all_gateway_config()

        # --- 基础连接 ---
        api_key_raw = db.get("API_KEY") or API_KEY
        embedding_key_raw = db.get("EMBEDDING_API_KEY") or _db_module.EMBEDDING_API_KEY

        settings = {
            # 基础连接
            "API_BASE_URL": db.get("API_BASE_URL") or str(API_BASE_URL),
            "API_KEY": _mask_key(api_key_raw),
            "DEFAULT_MODEL": db.get("DEFAULT_MODEL") or str(DEFAULT_MODEL),
            # 记忆系统
            "MEMORY_ENABLED": _parse_bool(db.get("MEMORY_ENABLED"), MEMORY_ENABLED),
            "MEMORY_MODEL": db.get("MEMORY_MODEL")
            or os.environ.get("MEMORY_MODEL", ""),
            "MAX_MEMORIES_INJECT": int(
                db.get("MAX_MEMORIES_INJECT") or MAX_MEMORIES_INJECT
            ),
            "MIN_SCORE_THRESHOLD": float(
                db.get("MIN_SCORE_THRESHOLD") or _db_module.MIN_SCORE_THRESHOLD
            ),
            "MEMORY_EXTRACT_INTERVAL": int(
                db.get("MEMORY_EXTRACT_INTERVAL") or MEMORY_EXTRACT_INTERVAL
            ),
            # 缓存分区
            "CACHE_PARTITION_ENABLED": _parse_bool(
                db.get("CACHE_PARTITION_ENABLED"), CACHE_PARTITION_ENABLED
            ),
            "CACHE_PARTITION_X": int(db.get("CACHE_PARTITION_X") or CACHE_PARTITION_X),
            "CACHE_PARTITION_TRIGGER": db.get("CACHE_PARTITION_TRIGGER")
            or CACHE_PARTITION_TRIGGER,
            "CACHE_PARTITION_WINDOW": int(
                db.get("CACHE_PARTITION_WINDOW") or CACHE_PARTITION_WINDOW
            ),
            "CACHE_SUMMARY_MODEL": db.get("CACHE_SUMMARY_MODEL")
            or str(CACHE_SUMMARY_MODEL),
            # 向量搜索（开源版用 EMBEDDING_API_KEY + EMBEDDING_BASE_URL）
            "MEMORY_VECTOR_ENABLED": _parse_bool(
                db.get("MEMORY_VECTOR_ENABLED"), _db_module.MEMORY_VECTOR_ENABLED
            ),
            "EMBEDDING_API_KEY": _mask_key(embedding_key_raw),
            "EMBEDDING_BASE_URL": db.get("EMBEDDING_BASE_URL")
            or str(_db_module.EMBEDDING_BASE_URL),
            "EMBEDDING_MODEL": db.get("EMBEDDING_MODEL")
            or str(_db_module.EMBEDDING_MODEL),
            "EMBEDDING_DIM": int(db.get("EMBEDDING_DIM") or _db_module.EMBEDDING_DIM),
            # 搜索权重
            "MEMORY_HW_KEYWORD": float(
                db.get("MEMORY_HW_KEYWORD") or _db_module.MEMORY_HW_KEYWORD
            ),
            "MEMORY_HW_SEMANTIC": float(
                db.get("MEMORY_HW_SEMANTIC") or _db_module.MEMORY_HW_SEMANTIC
            ),
            "MEMORY_HW_IMPORTANCE": float(
                db.get("MEMORY_HW_IMPORTANCE") or _db_module.MEMORY_HW_IMPORTANCE
            ),
            "MEMORY_HW_RECENCY": float(
                db.get("MEMORY_HW_RECENCY") or _db_module.MEMORY_HW_RECENCY
            ),
            "MEMORY_SEMANTIC_THRESHOLD": float(
                db.get("MEMORY_SEMANTIC_THRESHOLD")
                or _db_module.MEMORY_SEMANTIC_THRESHOLD
            ),
            # 其他
            "FORCE_STREAM": _parse_bool(db.get("FORCE_STREAM"), FORCE_STREAM),
            "REASONING_EFFORT": db.get("REASONING_EFFORT") or str(REASONING_EFFORT),
            # System Prompt
            "systemPrompt": db.get("systemPrompt") or _DEFAULT_SYSTEM_PROMPT or "",
        }

        return {"status": "ok", "settings": settings}
    except Exception as e:
        print(f"[get_settings] 错误: {e}")
        return {"error": str(e)}


@app.put("/api/settings")
async def save_settings(request: Request):
    """保存高级设置（写入数据库 + 热更新运行时变量，立即生效无需重启）"""
    try:
        data = await request.json()
        updated = []
        skipped = []

        # main.py 全局变量映射（key → 类型转换函数）
        _MAIN_VARS = {
            "API_BASE_URL": str,
            "API_KEY": str,
            "DEFAULT_MODEL": str,
            "MEMORY_ENABLED": lambda v: _parse_bool(v),
            "MAX_MEMORIES_INJECT": int,
            "MEMORY_EXTRACT_INTERVAL": int,
            "CACHE_PARTITION_ENABLED": lambda v: _parse_bool(v),
            "CACHE_PARTITION_X": int,
            "CACHE_PARTITION_TRIGGER": str,
            "CACHE_PARTITION_WINDOW": int,
            "CACHE_SUMMARY_MODEL": str,
            "FORCE_STREAM": lambda v: _parse_bool(v),
            "REASONING_EFFORT": str,
        }

        # database.py 全局变量映射（开源版用 EMBEDDING_API_KEY + EMBEDDING_BASE_URL）
        _DB_VARS = {
            "EMBEDDING_API_KEY": str,
            "EMBEDDING_BASE_URL": str,
            "EMBEDDING_MODEL": str,
            "EMBEDDING_DIM": int,
            "MIN_SCORE_THRESHOLD": float,
            "MEMORY_VECTOR_ENABLED": lambda v: _parse_bool(v),
            "MEMORY_HW_KEYWORD": float,
            "MEMORY_HW_SEMANTIC": float,
            "MEMORY_HW_IMPORTANCE": float,
            "MEMORY_HW_RECENCY": float,
            "MEMORY_SEMANTIC_THRESHOLD": float,
        }

        # 只存 os.environ 的变量
        _ENV_ONLY = {"MEMORY_MODEL": str}

        # 打码字段
        _MASKED_KEYS = {"API_KEY", "EMBEDDING_API_KEY"}

        for key, value in data.items():
            # --- 打码字段特殊处理 ---
            if key in _MASKED_KEYS:
                str_val = str(value).strip()
                if _is_masked(str_val):
                    skipped.append(key)
                    continue
                if not str_val:
                    await set_gateway_config(key, "")
                    if key in _MAIN_VARS:
                        globals()[key] = ""
                    elif key in _DB_VARS:
                        setattr(_db_module, key, "")
                    os.environ[key] = ""
                    updated.append(key)
                    continue

            # --- systemPrompt 特殊处理 ---
            if key == "systemPrompt":
                await set_gateway_config("systemPrompt", str(value))
                invalidate_system_prompt_cache()
                updated.append("systemPrompt")
                print(f"[settings] systemPrompt 已更新（{len(str(value))} 字）")
                continue

            # --- 常规字段 ---
            await set_gateway_config(key, str(value))

            if key in _MAIN_VARS:
                typed_value = _MAIN_VARS[key](value)
                globals()[key] = typed_value
                os.environ[key] = str(value)
                updated.append(key)
                print(f"[settings] {key} = {typed_value}")

            elif key in _DB_VARS:
                typed_value = _DB_VARS[key](value)
                setattr(_db_module, key, typed_value)
                os.environ[key] = str(value)
                updated.append(key)
                print(f"[settings] {key} = {typed_value} (database)")

            elif key in _ENV_ONLY:
                typed_value = _ENV_ONLY[key](value)
                os.environ[key] = str(typed_value)
                updated.append(key)
                print(f"[settings] {key} = {typed_value} (env)")

            else:
                skipped.append(key)

        return {
            "status": "ok",
            "updated": updated,
            "skipped": skipped,
            "message": f"已更新 {len(updated)} 项配置，立即生效",
        }
    except Exception as e:
        print(f"[save_settings] 错误: {e}")
        return {"error": str(e)}


# ============================================================

if __name__ == "__main__":
    import uvicorn

    print(f"🚀 AI Memory Gateway 启动中... 端口 {PORT}")
    print(f"📝 人设长度：{len(SYSTEM_PROMPT)} 字符")
    print(f"🤖 默认模型：{DEFAULT_MODEL}")
    print(f"🔗 API 地址：{API_BASE_URL}")
    print(f"🧠 记忆系统：{'开启' if MEMORY_ENABLED else '关闭'}")
    if MEMORY_ENABLED:
        print(f"📝 记忆提取+注入：{'开启' if MEMORY_EXTRACT_ENABLED else '关闭'}")
    print(
        f"🔄 记忆提取间隔：{'禁用' if MEMORY_EXTRACT_INTERVAL == 0 else '每轮提取' if MEMORY_EXTRACT_INTERVAL == 1 else f'每 {MEMORY_EXTRACT_INTERVAL} 轮提取一次'}"
    )
    if CACHE_PARTITION_ENABLED:
        print(
            f"🔒 分区缓存：开启 (X={CACHE_PARTITION_X}, session={PARTITION_SESSION_ID or '未设置'})"
        )
    if FORCE_STREAM:
        print(f"⚡ 强制流式传输：开启")
    if REASONING_EFFORT:
        print(f"🧠 推理参数注入：{REASONING_EFFORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
