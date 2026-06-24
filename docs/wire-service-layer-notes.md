# wire-service-layer 迁移记录

> 2026-06-24 | ospec change: wire-service-layer

## 做了什么

审计发现 routes/ 层 ~53 处 `from database import` 直调，完全绕过 service/repo 层。本次变更将 routes 全面接入 service 层，消除 `import main`，合并重复代码。

## 关键决策

### 1. CacheStateRepository 补齐

之前 `CacheService` 依赖 `CacheStateRepository` ABC，但没有任何实现。`partition.py` 直调 `database.get_session_cache_state`。

**做法**：新建 `repositories/cache_repo.py`，121 行，完整实现 JSON 序列化/反序列化、JOIN 查询。

**教训**：ABC 定义了就要有实现，否则是摆设。审计时第一时间发现这个问题。

### 2. partition_cache.py vs partition_helpers.py 合并

两个文件有 4 个重复函数，其中 `build_time_injection` 输出格式不同（潜伏 bug）。

**做法**：把 `partition_helpers.py` 独有的 `is_anthropic_model`、`strip_cache_control` 合并到 `partition_cache.py`，删除 `partition_helpers.py`。

**教训**：从 main.py 拆分代码时，不同时间点拆出的文件容易产生重复。审计时用 grep 找重复函数名是高效手段。

### 3. routes 从 database 直调改为 service 调用

**核心模式**：
```python
# 旧：inline import + database 直调
from database import get_all_memories_detail
result = await get_all_memories_detail(...)

# 新：从 app.state 获取 service
memory_service = request.app.state.memory_service
result = await memory_service.list_memories(...)
```

**难点**：
- `update_memory_with_layer` 等 database 函数在 repo 中没有等价方法 → 需要新增 `update_full`
- `get_layer_statistics` 返回格式 repo 和 database 不一致 → 统一格式
- `merge_sessions` repo 版本比 database 版本少处理 token_usage/title → 补齐逻辑

**教训**：repo 层的方法签名要和 database 函数对齐，否则迁移时会踩坑。

### 4. settings 端点留在 main.py

`save_settings` 需要 `globals()` 修改 main.py 模块变量 + `setattr(_db_module, ...)` 修改 database.py 模块变量。这是热更新机制的核心，强行迁移到 routes 会引入更复杂的耦合。

**教训**：不是所有代码都该迁移。与模块生命周期绑定的逻辑（热更新、lifespan）留在 main.py 是合理的。

### 5. backfill 端点保留 database 直调

`backfill_memory_embeddings` 和 `get_pending_memory_embedding_count` 是复杂的 embedding 批处理操作，没有 service 等价物。强行封装到 service 只会增加薄层包装。

**教训**：特殊操作（批处理、迁移脚本）可以保留 database 直调，不必为了"零直调"而过度抽象。

## 测试策略

测试 fixture 从 mock `database.*` 改为 mock `app.state.*_service`：

```python
# 旧
with patch("database.get_all_memories_detail", new_callable=AsyncMock) as mock:
    mock.return_value = {...}
    response = await client.get("/api/memories")

# 新（fixture 层面设置 mock service）
app.state.memory_service = mock_memory_service
# 测试代码直接调用，无需 patch
response = await client.get("/api/memories")
```

好处：测试更稳定，不依赖 database 模块的 import 顺序。

## 数据

- 净减 539 行（+836 / -1375）
- 删除 1 个文件（partition_helpers.py）
- 新增 1 个文件（cache_repo.py）
- 修改 19 个文件
- 测试 105 passed，0 failed

## 待后续处理

| 问题 | 优先级 | 说明 |
|------|--------|------|
| utils/ 4 处 database 直调 | P2 | memory_helpers、consolidation_helpers 被 main.py 的 background task 调用，需要传入 service 实例 |
| Service env var 冻结 | P2 | 构造时读 env，Dashboard 热更新无效 |
| ChatService 搜索路径 | P2 | `_inject_memories` 绕过 MemoryService 直调 repo.search |
| middleware GATEWAY_SECRET | P3 | import 时读取，热更新无效 |
