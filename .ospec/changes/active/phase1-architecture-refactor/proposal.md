---
name: phase1-architecture-refactor
status: active
created: 2026-06-23
affects: [main.py, database.py]
flags: []
---

## 背景

当前项目存在严重的代码组织问题：
- `main.py` 3000+ 行，路由、业务逻辑、流式处理混杂
- `database.py` 2000+ 行，52 个函数无分层
- 修改一处影响全局，测试困难
- 为后续 zvec 迁移打基础，需要先建立清晰的架构

## 项目上下文

**项目文档：**
- 项目概览: [.ospec/docs/project/overview.md](../../../docs/project/overview.md)
- 技术栈: [.ospec/docs/project/tech-stack.md](../../../docs/project/tech-stack.md)
- 架构说明: [.ospec/docs/project/architecture.md](../../../docs/project/architecture.md)
- 模块地图: [.ospec/docs/project/module-map.md](../../../docs/project/module-map.md)
- API 总览: [.ospec/docs/project/api-overview.md](../../../docs/project/api-overview.md)

**关联模块：**
- main.py - 网关主程序（待拆分）
- database.py - 数据库操作（待拆分）

## 目标

- 拆分 main.py 为 routes/services/middleware/utils
- 拆分 database.py 为 Repository 模式
- 建立清晰的分层架构
- 保持所有现有功能正常
- 测试覆盖率 80%+

## 范围

**涉及：**
- 目录结构重组
- Repository 接口抽象
- Service 层提取
- Route 层提取
- 测试补充

**不涉及：**
- 存储层替换（zvec 迁移在 Phase 2）
- 新功能开发
- 性能优化

## 验收标准

- [x] main.py 精简到 200 行以内
- [x] database.py 拆分为多个 Repository
- [x] 每个文件职责单一
- [x] 所有 API 端点正常工作
- [x] 测试全部通过
- [x] 测试覆盖率 >= 80%
