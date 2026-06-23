---
feature: phase1-architecture-refactor
created: 2026-06-23
optional_steps: []
---

## 上下文引用

**项目文档：**
- 项目概览: [.ospec/docs/project/overview.md](../../../docs/project/overview.md)
- 技术栈: [.ospec/docs/project/tech-stack.md](../../../docs/project/tech-stack.md)
- 架构说明: [.ospec/docs/project/architecture.md](../../../docs/project/architecture.md)
- 模块地图: [.ospec/docs/project/module-map.md](../../../docs/project/module-map.md)
- API 总览: [.ospec/docs/project/api-overview.md](../../../docs/project/api-overview.md)

**关联模块：**
- main.py - 网关主程序
- database.py - 数据库操作

## 任务清单

### Step 1.1: 目录结构重组

- [x] 创建 routes/ 目录和模块
- [x] 创建 services/ 目录和模块
- [x] 创建 repositories/ 目录和模块
- [x] 创建 middleware/ 目录和模块
- [x] 创建 utils/ 目录和模块

### Step 1.2: Repository 层抽象

- [x] 定义 Repository 接口（base.py）
- [x] 实现 MemoryRepository（PostgreSQL）
- [x] 实现 ConversationRepository（PostgreSQL）
- [x] 实现 ConfigRepository（PostgreSQL）

### Step 1.3: Service 层提取

- [x] 提取 MemoryService
- [x] 提取 ChatService
- [x] 提取 ExtractionService
- [x] 提取 CacheService

### Step 1.4: Route 层提取

- [x] 提取 chat 路由
- [x] 提取 memories 路由
- [x] 提取 conversations 路由
- [x] 提取 settings 路由
- [x] 提取 partition 路由
- [x] 提取 admin 路由

### Step 1.5: 测试补充

- [ ] Repository 单元测试
- [ ] Service 单元测试
- [ ] Route 集成测试
- [ ] 测试覆盖率 >= 80%

### 收尾

- [ ] 更新相关文档
- [ ] 重新生成 SKILL.index.json
- [ ] 执行验证并更新 verification.md
