---
feature: add-unit-tests
created: 2026-06-23
status: verified
optional_steps: []
passed_optional_steps: []
---

## 自动验证

- [x] build 通过
- [x] lint 通过
- [x] test 通过
- [x] 索引已重新生成
- [x] spec-check 通过

## 项目联动检查

- [x] 项目概览: [.ospec/docs/project/overview.md](../../../../../docs/project/overview.md)
- [x] 技术栈: [.ospec/docs/project/tech-stack.md](../../../../../docs/project/tech-stack.md)
- [x] 架构说明: [.ospec/docs/project/architecture.md](../../../../../docs/project/architecture.md)
- [x] 模块地图: [.ospec/docs/project/module-map.md](../../../../../docs/project/module-map.md)
- [x] API 总览: [.ospec/docs/project/api-overview.md](../../../../../docs/project/api-overview.md)

- [x] 相关模块技能已回看

- [x] 相关 API / 设计 / 计划文档已回看

## 需求验收

- [x] pytest 配置完成，可运行 `pytest` 命令
- [x] memory_extractor.py 核心函数有测试覆盖
- [x] database.py 核心函数有测试覆盖（使用 mock）
- [x] main.py 关键路由有测试覆盖
- [x] 测试通过率 100%

## 测试结果

```
============================= test session starts ==============================
platform linux -- Python 3.14.5, pytest-9.1.1, pluggy-1.6.0
plugins: asyncio-1.4.0, anyio-4.13.0
asyncio: mode=Mode.AUTO, debug=False

tests/test_database.py - 14 tests passed
tests/test_main.py - 15 tests passed
tests/test_memory_extractor.py - 12 tests passed

============================== 41 passed, 1 warning in 1.70s ==============================
```

## 测试覆盖

### memory_extractor.py (12 tests)
- extract_memories: 9 tests (无API_KEY、空消息、成功提取、markdown JSON、空数组、API错误、已有记忆、JSON兜底、无效格式)
- score_memories: 3 tests (空列表、成功评分、API错误)

### database.py (14 tests)
- get_pool: 1 test (无DATABASE_URL)
- save_memory: 1 test
- search_memories: 1 test (空查询)
- get_all_memories_count: 1 test
- get_recent_memories: 1 test
- get_gateway_config: 2 tests (存在/不存在)
- set_gateway_config: 1 test
- delete_memory: 1 test
- update_memory: 2 tests (内容/重要性)
- save_message: 1 test
- delete_memories_batch: 1 test
- get_conversation_messages: 1 test

### main.py (15 tests)
- 健康检查: 1 test
- 模型列表: 1 test
- 记忆CRUD: 4 tests
- 对话管理: 2 tests
- 设置: 1 test
- 分区缓存: 1 test
- 导出导入: 2 tests
- 三层记忆: 3 tests

## 结果

- [x] 可以归档
