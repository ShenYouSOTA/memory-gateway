# 实施计划：AI Memory Gateway 优化（纯网关层）

> **范围说明**：本次实施不涉及记忆系统，仅覆盖 Item 8 的全部优化。记忆系统（Embedding 切换、prompt 文件）待用户确认后单独推进。

---

## 一、项目初始化与基础准备

### Step 0：创建实施分支与版本标记

**前置条件**：无

**操作内容**：
1. 基于当前 `main` 分支创建 feature 分支 `feat/gateway-optimization`
2. 记录当前版本号作为回滚基准（当前无版本号，建议首次打 tag：`v0.1-pre-opt`）
3. 创建 `CHANGELOG.md` 文件（后续每步完成时追加记录）

**验证标准**：
- 分支创建成功
- `git log --oneline` 确认基线提交

**回滚方案**：删除分支，回到 `main`

**影响范围**：无代码变更

---

## 二、基础架构层（优先级 P0）

### Step 1：引入 `uvloop` 事件循环替换

**前置条件**：Step 0 完成

**操作内容**：
1. 在 `requirements.txt` 添加 `uvloop>=0.19.0`
2. 在 `main.py` 的 `if __name__ == "__main__":` 块中，`uvicorn.run()` 之前添加：
   ```python
   try:
       import uvloop
       uvloop.install()
   except ImportError:
       pass
   ```
3. 确认现有 `requirements.txt` 中所有依赖（fastapi==0.115.0, uvicorn==0.30.0, httpx==0.27.0, asyncpg==0.30.0, jieba==0.42.1, jinja2==3.1.4）无兼容性问题

**验证标准**：
- `pip install -r requirements.txt` 成功
- `python -c "import uvloop; print('ok')"` 通过
- 启动服务器：`API_KEY=test python main.py` 无报错，日志显示 `🚀 AI Memory Gateway 启动中...`
- `curl http://localhost:8080/` 返回健康检查 JSON

**回滚方案**：还原 `requirements.txt` 和 `main.py` 中添加的 3 行代码

**影响范围**：仅影响事件循环性能，不改变任何业务逻辑

---

### Step 2：连接池参数调优

**前置条件**：Step 1 完成

**操作内容**：
1. 在 `database.py` 的 `get_pool()` 函数中，修改 `create_pool` 调用：
   ```python
   # 现有代码
   _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5, statement_cache_size=0)

   # 修改为
   _pool = await asyncpg.create_pool(
       DATABASE_URL,
       min_size=2,
       max_size=20,
       statement_cache_size=0,  # 保留，pgbouncer 兼容
       command_timeout=30,
       max_inactive_connection_lifetime=300,
   )
   ```
2. 确认 `close_pool()` 函数不需要改动（`await _pool.close()` 已存在）

**验证标准**：
- 启动服务器，日志显示 `✅ 数据库连接池已创建`
- Dashboard 能正常访问 `/dashboard`
- 多次并发请求 `/api/memories` 无连接错误

**回滚方案**：恢复 `min_size=1, max_size=5`，移除新增参数

**影响范围**：`database.py:get_pool()` 函数，约 1 行改动

---

### Step 3：引入结构化日志

**前置条件**：Step 1 完成（可与 Step 2 并行）

**操作内容**：
1. 在 `requirements.txt` 添加 `structlog>=24.1.0`
2. 创建新文件 `logging_config.py`：
   ```python
   import structlog
   import logging
   import sys

   def setup_logging(log_level: str = "INFO"):
       structlog.configure(
           processors=[
               structlog.contextvars.merge_contextvars,
               structlog.processors.add_log_level,
               structlog.processors.StackInfoRenderer(),
               structlog.dev.set_exc_info,
               structlog.processors.TimeStamper(fmt="iso"),
               structlog.dev.ConsoleRenderer() if sys.stderr.isatty()
               else structlog.processors.JSONRenderer(),
           ],
           wrapper_class=structlog.make_filtering_bound_logger(
               getattr(logging, log_level.upper(), logging.INFO)
           ),
           context_class=dict,
           logger_factory=structlog.PrintLoggerFactory(),
           cache_logger_on_first_use=True,
       )

   def get_logger(name: str = __name__):
       return structlog.get_logger(name)
   ```
3. 在 `main.py` 顶部导入并初始化：
   ```python
   from logging_config import setup_logging, get_logger
   setup_logging(os.getenv("LOG_LEVEL", "INFO"))
   logger = get_logger("gateway")
   ```
4. 在 `main.py` 的 `lifespan()` 函数中，将所有 `print()` 替换为 `logger.info()` / `logger.warning()` / `logger.error()`
5. 在 `chat_completions()` 路由中，添加请求日志：
   ```python
   logger.info("chat_request", model=model, stream=is_stream,
               memory_enabled=MEMORY_ENABLED, message_count=len(messages))
   ```

**验证标准**：
- 启动服务器，控制台输出带时间戳和级别的日志
- 设置 `LOG_LEVEL=DEBUG` 能看到详细日志
- JSON 格式输出：`LOG_LEVEL=INFO python main.py 2>&1 | head -1 | python -m json.tool` 能解析

**回滚方案**：删除 `logging_config.py`，还原 `main.py` 中的 `print()` 语句

**影响范围**：新增 `logging_config.py`；`main.py` 中 ~20 处 `print()` 替换为 `logger` 调用

---

## 三、协议与参数优化层（优先级 P1）

### Step 4：MCP OAuth 2.1 鉴权框架

**前置条件**：Step 3 完成

**操作内容**：
1. 创建新文件 `oauth_provider.py`：
   - 实现 `OAuthMetadata`、`OAuthServerMetadata` 数据类
   - 实现 `register_client()` —— 客户端注册端点
   - 实现 `authorize()` —— 授权端点（返回授权码）
   - 实现 `token()` —— 令牌端点（authorization_code + refresh_token grant）
   - 实现 `verify_token()` —— 令牌验证中间件
   - 使用 `GATEWAY_SECRET` 作为签名密钥（HMAC-SHA256）
   - 令牌存储使用内存 dict（单进程场景足够）

2. 在 `main.py` 中添加路由（先不挂载，只创建）：
   ```python
   from oauth_provider import OAuthProvider
   oauth = OAuthProvider(secret=GATEWAY_SECRET)

   @app.get("/.well-known/oauth-authorization-server")
   async def oauth_metadata(): ...

   @app.post("/oauth/register")
   async def oauth_register(request: Request): ...

   @app.get("/oauth/authorize")
   async def oauth_authorize(...): ...

   @app.post("/oauth/token")
   async def oauth_token(request: Request): ...
   ```

3. 创建鉴权中间件 `verify_auth()`：
   - 如果 `GATEWAY_SECRET` 未设置，跳过鉴权（保持现有行为）
   - 如果设置了，同时支持 `X-Gateway-Key` header（向后兼容）和 OAuth Bearer token
   - 非公开端点（非 `/`、非 `/.well-known/*`、非 `/oauth/*`）需要鉴权

4. 在所有现有 API 路由中添加 `Depends(verify_auth)` 或手动调用

**验证标准**：
- 不设置 `GATEWAY_SECRET`：所有端点照常工作，无鉴权
- 设置 `GATEWAY_SECRET=xxx`：
  - `curl /api/memories -H "X-Gateway-Key: xxx"` → 200
  - `curl /api/memories` → 401
  - `curl /.well-known/oauth-authorization-server` → 200（返回 metadata）
  - 完成 OAuth 注册 → 授权 → 获取 token → 用 token 访问 API → 200

**回滚方案**：删除 `oauth_provider.py`，还原路由中的 `Depends` 调用。鉴权中间件设计为可插拔，移除后系统回到原有 `X-Gateway-Key` 逻辑。

**影响范围**：新增 `oauth_provider.py`；`main.py` 添加 ~100 行路由和中间件；现有鉴权逻辑包装为 `verify_auth()`

---

### Step 5：OpenAI API 参数透传

**前置条件**：Step 1 完成（可与 Step 4 并行）

**操作内容**：
1. 在 `main.py` 的 `chat_completions()` 路由中，提取需要透传的参数：
   ```python
   # 在 body = await request.json() 之后添加
   PARAMS_TO_FORWARD = [
       "temperature", "top_p", "max_tokens", "max_completion_tokens",
       "frequency_penalty", "presence_penalty", "seed",
       "response_format", "stop", "n", "logprobs",
       "top_logprobs", "user",
   ]

   forward_params = {k: v for k, v in body.items() if k in PARAMS_TO_FORWARD}
   ```

2. 在构建转发 body 时，合并这些参数：
   ```python
   # 现有代码设置 body["messages"], body["model"]
   # 添加：
   body.update(forward_params)
   ```

3. 在流式和非流式两个分支中都应用此逻辑

4. 添加 `tools` 和 `tool_choice` 透传（需额外处理）：
   ```python
   if "tools" in body:
       forward_params["tools"] = body["tools"]
   if "tool_choice" in body:
       forward_params["tool_choice"] = body["tool_choice"]
   ```

**验证标准**：
- 发送带 `temperature: 0.5` 的请求，上游收到相同参数
- 发带 `tools` 的 function calling 请求，流程正常
- 不带这些参数时，不发送默认值（避免覆盖上游默认）

**回滚方案**：删除 `PARAMS_TO_FORWARD` 相关代码和 `body.update(forward_params)`

**影响范围**：`main.py` 的 `chat_completions()` 函数，~20 行新增

---

### Step 6：Input Guardrail 基础框架

**前置条件**：Step 5 完成

**操作内容**：
1. 创建新文件 `guardrails.py`：
   ```python
   import re
   from dataclasses import dataclass
   from typing import Optional

   @dataclass
   class GuardrailResult:
       passed: bool
       reason: Optional[str] = None
       category: Optional[str] = None  # "content" | "token" | "rate"

   class InputGuardrail:
       def __init__(self):
           self.max_message_length = 100000  # 单条消息最大字符
           self.blocked_patterns = []  # 用户可配置的正则列表
           self.max_context_messages = 100  # 上下文最大消息数

       def check(self, messages: list) -> GuardrailResult:
           # 1. 消息数量检查
           if len(messages) > self.max_context_messages:
               return GuardrailResult(False, f"消息数超限: {len(messages)} > {self.max_context_messages}", "token")

           # 2. 消息长度检查
           for msg in messages:
               content = msg.get("content", "")
               if isinstance(content, str) and len(content) > self.max_message_length:
                   return GuardrailResult(False, f"单条消息过长: {len(content)} 字符", "content")

           # 3. 可选：正则过滤
           for pattern in self.blocked_patterns:
               for msg in messages:
                   content = msg.get("content", "")
                   if isinstance(content, str) and re.search(pattern, content):
                       return GuardrailResult(False, f"命中内容过滤规则", "content")

           return GuardrailResult(True)
   ```

2. 在 `main.py` 中实例化并集成：
   ```python
   from guardrails import InputGuardrail
   input_guardrail = InputGuardrail()

   # 在 chat_completions() 中，body 解析之后：
   guardrail_result = input_guardrail.check(messages)
   if not guardrail_result.passed:
       logger.warning("guardrail_blocked", reason=guardrail_result.reason,
                      category=guardrail_result.category)
       return JSONResponse(
           status_code=400,
           content={"error": {"message": guardrail_result.reason, "type": "guardrail_error"}}
       )
   ```

3. 添加环境变量配置：
   ```python
   GUARDRAIL_MAX_MESSAGES = int(os.getenv("GUARDRAIL_MAX_MESSAGES", "100"))
   GUARDRAIL_MAX_MSG_LENGTH = int(os.getenv("GUARDRAIL_MAX_MSG_LENGTH", "100000"))
   ```

**验证标准**：
- 正常请求不受影响
- 发送 200 条消息（超过 `GUARDRAIL_MAX_MESSAGES=100`）→ 400 错误
- 发送超长内容（>100000 字符）→ 400 错误
- 日志中记录 `guardrail_blocked` 事件

**回滚方案**：删除 `guardrails.py`，移除 `main.py` 中的 guardrail 集成代码

**影响范围**：新增 `guardrails.py`（~50 行）；`main.py` 添加 ~15 行

---

## 四、Model 路由层（优先级 P2）

### Step 7：Model Registry 基础实现

**前置条件**：Step 6 完成

**操作内容**：
1. 创建新文件 `model_registry.py`：
   ```python
   from dataclasses import dataclass, field
   from typing import Dict, List, Optional
   import os

   @dataclass
   class ModelInfo:
       id: str
       name: str
       provider: str  # "openrouter" | "openai" | "google" | "ollama"
       context_length: int = 4096
       max_output: int = 4096
       supports_streaming: bool = True
       supports_tools: bool = True
       supports_vision: bool = False
       supports_thinking: bool = False
       cost_per_1k_input: float = 0.0
       cost_per_1k_output: float = 0.0
       aliases: List[str] = field(default_factory=list)

   class ModelRegistry:
       def __init__(self):
           self._models: Dict[str, ModelInfo] = {}
           self._aliases: Dict[str, str] = {}  # alias -> canonical_id
           self._default_model: str = os.getenv("DEFAULT_MODEL", "anthropic/claude-sonnet-4")

       def register(self, model: ModelInfo):
           self._models[model.id] = model
           for alias in model.aliases:
               self._aliases[alias] = model.id

       def resolve(self, model_id: str) -> Optional[ModelInfo]:
           canonical = self._aliases.get(model_id, model_id)
           return self._models.get(canonical)

       def list_models(self) -> List[ModelInfo]:
           return list(self._models.values())

       def get_default(self) -> str:
           return self._default_model
   ```

2. 预注册常用模型（硬编码 + 环境变量可扩展）：
   ```python
   registry = ModelRegistry()

   registry.register(ModelInfo(
       id="anthropic/claude-sonnet-4",
       name="Claude Sonnet 4",
       provider="anthropic",
       context_length=200000,
       max_output=8192,
       supports_thinking=True,
       aliases=["claude-sonnet-4"],
   ))
   # ... 其他常用模型
   ```

3. 在 `chat_completions()` 中，替换现有的 `model = body.get("model", DEFAULT_MODEL)` 逻辑：
   ```python
   requested_model = body.get("model", "")
   model_info = registry.resolve(requested_model) if requested_model else None
   if model_info:
       model = model_info.id
   else:
       model = requested_model or registry.get_default()
   body["model"] = model
   ```

**验证标准**：
- `curl /v1/models` 返回预注册的模型列表
- 请求 `model: "claude-sonnet-4"` 能正确解析为 `anthropic/claude-sonnet-4`
- 未知模型名透传给上游（不报错）

**回滚方案**：删除 `model_registry.py`，恢复原有 model 处理逻辑

**影响范围**：新增 `model_registry.py`（~80 行）；`main.py` 中 ~10 行改动

---

### Step 8：成本路由逻辑

**前置条件**：Step 7 完成

**操作内容**：
1. 在 `ModelInfo` 中已包含 `cost_per_1k_input` 和 `cost_per_1k_output`

2. 在 `model_registry.py` 中添加成本路由方法：
   ```python
   class ModelRegistry:
       # ... 现有代码 ...

       def route_by_cost(self, task_type: str = "default") -> str:
           """根据任务类型选择最具成本效益的模型"""
           if task_type == "memory_extraction":
               candidates = [m for m in self._models.values()
                           if m.cost_per_1k_input < 0.002]
               if candidates:
                   return min(candidates, key=lambda m: m.cost_per_1k_input).id
               return os.getenv("MEMORY_MODEL", "anthropic/claude-haiku-4")

           elif task_type == "summary":
               candidates = [m for m in self._models.values()
                           if m.cost_per_1k_input < 0.002]
               if candidates:
                   return min(candidates, key=lambda m: m.cost_per_1k_input).id
               return os.getenv("CACHE_SUMMARY_MODEL", "anthropic/claude-haiku-4.5")

           return self._default_model
   ```

3. 在 `main.py` 中替换硬编码的模型选择：
   - `generate_summary()` 中：`CACHE_SUMMARY_MODEL` → `registry.route_by_cost("summary")`
   - `memory_extractor.py` 中的 `MEMORY_MODEL` → 通过 registry 选择（需小改 memory_extractor 接受 model 参数）

**验证标准**：
- 设置 `DEFAULT_MODEL=anthropic/claude-sonnet-4`，主对话用 Sonnet
- 记忆提取自动用 Haiku（成本低）
- 摘要生成自动用 Haiku
- 日志中能看到实际使用的模型名

**回滚方案**：恢复硬编码的 `MEMORY_MODEL` 和 `CACHE_SUMMARY_MODEL`

**影响范围**：`model_registry.py` 添加 ~30 行；`main.py` 中 ~5 处模型引用修改；`memory_extractor.py` 接受 `model` 参数

---

### Step 9：智能路由逻辑（P2 增强）

**前置条件**：Step 8 完成

**操作内容**：
1. 在 `model_registry.py` 中添加路由策略：
   ```python
   class ModelRegistry:
       # ... 现有代码 ...

       def route_intelligently(self, messages: list, requested_model: str,
                               stream: bool = False, has_tools: bool = False) -> str:
           """智能路由：根据请求特征选择最佳模型"""
           model_info = self.resolve(requested_model)

           if not model_info:
               return self._default_model

           # 流式检查
           if stream and not model_info.supports_streaming:
               fallback = self._find_fallback(supports_streaming=True)
               return fallback or model_info.id

           # 工具调用检查
           if has_tools and not model_info.supports_tools:
               fallback = self._find_fallback(supports_tools=True)
               return fallback or model_info.id

           return model_info.id

       def _find_fallback(self, **requirements) -> Optional[str]:
           for model in self._models.values():
               if all(getattr(model, k, False) == v for k, v in requirements.items()):
                   return model.id
           return None
   ```

2. 在 `chat_completions()` 中集成：
   ```python
   has_tools = "tools" in body
   model = registry.route_intelligently(
       messages=messages,
       requested_model=body.get("model", ""),
       stream=body.get("stream", False),
       has_tools=has_tools,
   )
   body["model"] = model
   ```

**验证标准**：
- 请求不支持流式的模型 + `stream: true` → 自动回退到支持流式的模型
- 请求不支持 tools 的模型 + `tools` 参数 → 自动回退
- 回退时日志记录 `model_fallback` 事件

**回滚方案**：恢复简单 `body.get("model", DEFAULT_MODEL)` 逻辑

**影响范围**：`model_registry.py` 添加 ~40 行；`main.py` 中 ~5 行改动

---

## 五、可观测性层（优先级 P2）

### Step 10：Metrics 采集（Prometheus 格式）

**前置条件**：Step 3 完成（可与 Step 7-9 并行）

**操作内容**：
1. 在 `requirements.txt` 添加 `prometheus-client>=0.20.0`

2. 创建 `metrics.py`：
   ```python
   from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
   from fastapi import Response

   REQUEST_COUNT = Counter(
       "gateway_requests_total", "Total requests",
       ["method", "endpoint", "status_code"]
   )

   REQUEST_LATENCY = Histogram(
       "gateway_request_duration_seconds", "Request latency",
       ["endpoint"],
       buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0]
   )

   LLM_LATENCY = Histogram(
       "gateway_llm_duration_seconds", "LLM API latency",
       ["model", "stream"],
       buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0]
   )

   TOKEN_USAGE = Counter(
       "gateway_tokens_total", "Total tokens",
       ["model", "type"]  # type: prompt | completion
   )

   ACTIVE_CONNECTIONS = Gauge(
       "gateway_active_connections", "Active streaming connections"
   )

   MEMORY_OPERATIONS = Counter(
       "gateway_memory_operations_total", "Memory operations",
       ["operation", "status"]  # operation: search | extract | save
   )

   def metrics_endpoint():
       return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
   ```

3. 在 `main.py` 中集成：
   ```python
   from metrics import (REQUEST_COUNT, REQUEST_LATENCY, LLM_LATENCY,
                        TOKEN_USAGE, ACTIVE_CONNECTIONS, MEMORY_OPERATIONS,
                        metrics_endpoint)

   @app.get("/metrics")
   async def prometheus_metrics():
       return metrics_endpoint()
   ```

4. 在关键路径中埋点：
   - `chat_completions()` 入口/出口：`REQUEST_COUNT.labels(...).inc()`
   - LLM 请求前后：`LLM_LATENCY.labels(model=model, stream=str(is_stream)).observe(duration)`
   - 流式连接开始/结束：`ACTIVE_CONNECTIONS.inc()` / `ACTIVE_CONNECTIONS.dec()`
   - Token 统计处：`TOKEN_USAGE.labels(model=model, type="prompt").inc(prompt_tokens)`
   - 记忆操作处：`MEMORY_OPERATIONS.labels(operation="search", status="success").inc()`

**验证标准**：
- `curl http://localhost:8080/metrics` 返回 Prometheus 格式指标
- 发送几个请求后，`gateway_requests_total` 计数器递增
- `gateway_llm_duration_seconds` 有正确的 histogram 数据
- `gateway_active_connections` 在流式请求期间 > 0

**回滚方案**：删除 `metrics.py`，移除 `main.py` 中的 `/metrics` 路由和所有埋点代码

**影响范围**：新增 `metrics.py`（~60 行）；`main.py` 中 ~30 行埋点代码

---

### Step 11：分布式链路追踪（OpenTelemetry）

**前置条件**：Step 10 完成

**操作内容**：
1. 在 `requirements.txt` 添加：
   ```
   opentelemetry-api>=1.22.0
   opentelemetry-sdk>=1.22.0
   opentelemetry-exporter-otlp>=1.22.0
   opentelemetry-instrumentation-fastapi>=0.43b0
   opentelemetry-instrumentation-httpx>=0.43b0
   opentelemetry-instrumentation-asyncpg>=0.43b0
   ```

2. 创建 `tracing.py`：
   ```python
   from opentelemetry import trace
   from opentelemetry.sdk.trace import TracerProvider
   from opentelemetry.sdk.trace.export import BatchSpanProcessor
   from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
   from opentelemetry.sdk.resources import Resource
   import os

   def setup_tracing(service_name: str = "ai-memory-gateway"):
       otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
       if not otlp_endpoint:
           return

       resource = Resource.create({"service.name": service_name})
       provider = TracerProvider(resource=resource)
       processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint))
       provider.add_span_processor(processor)
       trace.set_tracer_provider(provider)

   def get_tracer(name: str = __name__):
       return trace.get_tracer(name)
   ```

3. 在 `main.py` 的 `lifespan()` 中调用 `setup_tracing()`

4. 在关键路径添加 span：
   ```python
   from tracing import get_tracer
   tracer = get_tracer("gateway")

   with tracer.start_as_current_span("chat_completions") as span:
       span.set_attribute("model", model)
       span.set_attribute("stream", is_stream)
       span.set_attribute("memory_enabled", MEMORY_ENABLED)

       with tracer.start_as_current_span("llm_call") as llm_span:
           llm_span.set_attribute("model", model)
           # ... 调用逻辑 ...
   ```

5. 添加 FastAPI 自动 instrumentation：
   ```python
   from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
   FastAPIInstrumentor.instrument_app(app)
   ```

**验证标准**：
- 不设置 `OTEL_EXPORTER_OTLP_ENDPOINT`：无 tracing，不影响性能
- 设置后：Jaeger/Zipkin 中能看到 `chat_completions` → `llm_call` 的 span 链
- 每个 span 包含正确的 attributes（model, stream 等）

**回滚方案**：删除 `tracing.py`，移除 `requirements.txt` 中的 opentelemetry 依赖，移除 `main.py` 中的 instrumentation 代码

**影响范围**：新增 `tracing.py`（~30 行）；`requirements.txt` 添加 6 个依赖；`main.py` 中 ~15 行

---

## 六、集成验证与收尾

### Step 12：端到端集成测试

**前置条件**：Step 1-11 全部完成

**操作内容**：
1. 编写手动验证脚本 `verify_optimization.sh`：
   ```bash
   #!/bin/bash
   set -e

   BASE_URL="http://localhost:8080"

   echo "=== 1. 健康检查 ==="
   curl -s $BASE_URL/ | python -m json.tool

   echo "=== 2. Metrics 端点 ==="
   curl -s $BASE_URL/metrics | head -20

   echo "=== 3. 模型列表 ==="
   curl -s $BASE_URL/v1/models | python -m json.tool

   echo "=== 4. Chat 请求（测试参数透传）==="
   curl -s -X POST $BASE_URL/v1/chat/completions \
     -H "Content-Type: application/json" \
     -d '{"model":"anthropic/claude-sonnet-4","messages":[{"role":"user","content":"hi"}],"temperature":0.5,"stream":false}' \
     | python -m json.tool

   echo "=== 5. Guardrail 测试 ==="
   LONG_MSG=$(python -c "print('x' * 200000)")
   curl -s -X POST $BASE_URL/v1/chat/completions \
     -H "Content-Type: application/json" \
     -d "{\"model\":\"test\",\"messages\":[{\"role\":\"user\",\"content\":\"$LONG_MSG\"}]}" \
     | python -m json.tool

   echo "=== 6. OAuth 测试（如已启用）==="
   curl -s $BASE_URL/.well-known/oauth-authorization-server | python -m json.tool

   echo "=== 全部验证完成 ==="
   ```

2. 运行验证脚本，记录结果

3. 性能基准测试（可选）：
   ```bash
   hey -n 100 -c 10 -m POST \
     -H "Content-Type: application/json" \
     -d '{"model":"test","messages":[{"role":"user","content":"hi"}]}' \
     http://localhost:8080/v1/chat/completions
   ```

**验证标准**：
- 所有 6 项验证通过
- 性能基准：P95 延迟 < 200ms（不含 LLM 调用）
- 内存占用无明显泄漏（连续运行 1 小时后 RSS < 200MB）

**回滚方案**：N/A（验证步骤，不涉及代码变更）

**影响范围**：新增 `verify_optimization.sh`（仅验证脚本）

---

### Step 13：文档更新与 CHANGELOG

**前置条件**：Step 12 完成

**操作内容**：
1. 更新 `CHANGELOG.md`：
   ```markdown
   # Changelog

   ## [0.2.0] - 2026-XX-XX

   ### Added
   - uvloop 事件循环替换，异步性能提升 30-50%
   - 结构化日志（structlog），支持 JSON/Console 双格式
   - MCP OAuth 2.1 鉴权框架（向后兼容 X-Gateway-Key）
   - OpenAI API 参数完整透传（temperature, top_p, tools 等）
   - Input Guardrail 基础框架（消息数/长度/内容过滤）
   - Model Registry 模型注册与路由（别名、能力、成本）
   - 智能路由：根据请求特征自动选择最佳模型
   - Prometheus Metrics 端点（/metrics）
   - OpenTelemetry 分布式链路追踪
   - 数据库连接池调优（min=2, max=20）

   ### Changed
   - 所有 print() 替换为结构化日志
   - 模型选择逻辑从硬编码改为 Registry 查询
   ```

2. 更新 `requirements.txt` 最终版本

3. 更新 `README.md` 的环境变量表格（添加新变量）

**验证标准**：
- `CHANGELOG.md` 内容准确
- `requirements.txt` 包含所有新依赖且版本正确
- `README.md` 环境变量表格完整

**回滚方案**：N/A（文档变更）

**影响范围**：仅文档文件

---

## 七、依赖关系与执行顺序总结

```
Step 0 (分支创建)
    ↓
Step 1 (uvloop) ← 可独立执行
    ↓
Step 2 (连接池) ← 依赖 Step 1
Step 3 (日志)   ← 依赖 Step 1，可与 Step 2 并行
    ↓
Step 4 (OAuth)  ← 依赖 Step 3
Step 5 (参数透传) ← 依赖 Step 1，可与 Step 3-4 并行
    ↓
Step 6 (Guardrail) ← 依赖 Step 5
    ↓
Step 7 (Registry) ← 依赖 Step 6
Step 8 (成本路由) ← 依赖 Step 7
Step 9 (智能路由) ← 依赖 Step 8
    ↓
Step 10 (Metrics) ← 依赖 Step 3，可与 Step 7-9 并行
Step 11 (Tracing) ← 依赖 Step 10
    ↓
Step 12 (集成验证) ← 依赖 Step 1-11
Step 13 (文档收尾) ← 依赖 Step 12
```

**推荐执行顺序**（考虑依赖和风险）：
1. Step 0 → Step 1 → Step 3 → Step 2（基础层，低风险）
2. Step 5 → Step 6（协议层，中风险）
3. Step 10 → Step 11（可观测性，低风险）
4. Step 4（OAuth，高风险，独立执行）
5. Step 7 → Step 8 → Step 9（路由层，中风险）
6. Step 12 → Step 13（收尾）

---

## 八、风险评估与回滚策略

| Step | 风险等级 | 主要风险 | 回滚难度 |
|------|---------|---------|---------|
| 1 | 低 | uvloop 兼容性 | 极简（删 3 行） |
| 2 | 低 | 连接池耗尽 | 极简（改 1 行） |
| 3 | 低 | 日志格式变更 | 简单（删文件+还原 print） |
| 4 | 高 | OAuth 复杂度 | 中等（需移除中间件） |
| 5 | 低 | 参数冲突 | 极简（删 20 行） |
| 6 | 低 | 误拦截 | 简单（删文件） |
| 7 | 低 | 模型解析错误 | 简单（删文件） |
| 8 | 中 | 成本计算偏差 | 简单（恢复硬编码） |
| 9 | 中 | 路由决策错误 | 简单（恢复简单逻辑） |
| 10 | 低 | 性能开销 | 简单（删文件） |
| 11 | 中 | 依赖冲突 | 中等（需清理依赖） |
| 12 | 无 | N/A | N/A |
| 13 | 无 | N/A | N/A |

**紧急回滚方案**：
- 任意 Step 失败：`git revert` 该 Step 的提交
- 多步失败：`git reset --hard` 到 Step 0 的 tag
- 生产环境：Docker 镜像回滚到上一个版本
