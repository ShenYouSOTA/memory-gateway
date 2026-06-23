---
name: add-unit-tests
status: archived
created: 2026-06-23T00:00:00.000Z
affects: []
flags: []
---

## 背景

当前项目没有任何测试代码，这是一个重大技术债务。项目包含核心业务逻辑（记忆提取、搜索、分区缓存等）需要测试覆盖，以确保代码质量和后续重构的安全性。

## 项目上下文

**项目文档：**
- 项目概览: [.ospec/docs/project/overview.md](../../../../../docs/project/overview.md)
- 技术栈: [.ospec/docs/project/tech-stack.md](../../../../../docs/project/tech-stack.md)
- 架构说明: [.ospec/docs/project/architecture.md](../../../../../docs/project/architecture.md)
- 模块地图: [.ospec/docs/project/module-map.md](../../../../../docs/project/module-map.md)
- API 总览: [.ospec/docs/project/api-overview.md](../../../../../docs/project/api-overview.md)

**关联模块技能：**
- memory_extractor.py - 记忆提取模块
- database.py - 数据库操作模块
- main.py - 网关主程序

**关联 API 文档：**
- FastAPI 路由定义
- asyncpg 数据库操作

**关联设计 / 计划文档：**
- docs/todo.md - 技术债务中明确列出"单元测试覆盖（当前无测试）"

## 目标

- 建立 pytest 测试框架和配置
- 为核心模块创建单元测试
- 为关键业务逻辑提供测试覆盖
- 支持后续 CI/CD 集成

## 范围

**涉及：**
- pytest 配置和依赖
- memory_extractor.py 单元测试
- database.py 核心函数单元测试（mock 数据库连接）
- main.py 关键路由测试
- 测试 fixtures 和工具函数

**不涉及：**
- 端到端集成测试（需要真实数据库）
- 性能测试
- UI 测试

## 验收标准

- [ ] pytest 配置完成，可运行 `pytest` 命令
- [ ] memory_extractor.py 核心函数有测试覆盖
- [ ] database.py 核心函数有测试覆盖（使用 mock）
- [ ] main.py 关键路由有测试覆盖
- [ ] 测试通过率 100%
