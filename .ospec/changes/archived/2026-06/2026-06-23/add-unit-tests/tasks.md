---
feature: add-unit-tests
created: 2026-06-23
optional_steps: []
---

## 上下文引用

**项目文档：**
- 项目概览: [.ospec/docs/project/overview.md](../../../../../docs/project/overview.md)
- 技术栈: [.ospec/docs/project/tech-stack.md](../../../../../docs/project/tech-stack.md)
- 架构说明: [.ospec/docs/project/architecture.md](../../../../../docs/project/architecture.md)
- 模块地图: [.ospec/docs/project/module-map.md](../../../../../docs/project/module-map.md)
- API 总览: [.ospec/docs/project/api-overview.md](../../../../../docs/project/api-overview.md)

**模块技能：**
- memory_extractor.py - 记忆提取模块
- database.py - 数据库操作模块
- main.py - 网关主程序

## 任务清单

- [x] 添加 pytest 依赖到 pyproject.toml
- [x] 创建 pytest 配置文件和 conftest.py
- [x] 创建 tests/ 目录结构
- [x] 编写 test_memory_extractor.py 单元测试
- [x] 编写 test_database.py 单元测试（使用 mock）
- [x] 编写 test_main.py 路由测试
- [x] 运行测试确保全部通过
- [x] 更新相关文档
