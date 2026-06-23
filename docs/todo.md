# AI Memory Gateway - Todo & Roadmap

> **战略方向**：先拆架构，后迁 zvec

---

## 📋 待办事项

### Phase 1: 架构重构（Week 1-2）🔴 最高优先级

- [ ] 目录结构重组（routes/services/repositories/utils）
- [ ] Repository 接口抽象（MemoryRepo、VectorRepo）
- [ ] PostgreSQL Repository 实现
- [ ] Service 层提取（MemoryService、ChatService）
- [ ] Route 层提取（memories、conversations、settings）
- [ ] 测试补充（覆盖率 80%+）

### Phase 2: zvec 迁移（Week 3）🟠 高优先级

- [ ] zvec 集成（ZvecVectorRepository）
- [ ] 数据迁移脚本
- [ ] 双写模式（过渡期）
- [ ] 完全切换到 zvec
- [ ] 移除 pgvector 依赖

### Phase 3: 网关优化（Week 4+）🟡 中优先级

- [ ] uvloop 事件循环替换
- [ ] 结构化日志（structlog）
- [ ] 连接池参数调优
- [ ] MCP OAuth 2.1 鉴权
- [ ] OpenAI API 参数透传
- [ ] Input Guardrail 基础框架
- [ ] Model Registry 模型注册
- [ ] 成本路由逻辑

### Phase 4: 可观测性（可选）🟢 低优先级

- [ ] Prometheus Metrics
- [ ] OpenTelemetry Tracing
- [ ] 请求日志增强

---

## 🗺️ Roadmap

### v0.2 - 架构重构

**目标：** 清晰分层，职责分离

- [x] pytest 测试框架（已完成，41 个测试）
- [ ] main.py 拆分（routes/services/repositories）
- [ ] database.py 拆分（Repository 模式）
- [ ] 测试覆盖率 80%+

### v0.3 - zvec 迁移

**目标：** 替换 pgvector，简化部署

- [ ] zvec 集成
- [ ] 数据迁移工具
- [ ] 部署文档更新

### v0.4 - 网关增强

**目标：** 生产级网关能力

- [ ] uvloop 性能优化
- [ ] OAuth 鉴权
- [ ] 智能路由
- [ ] 监控指标

### v1.0 - 企业级

**目标：** 多租户、高可用

- [ ] 多租户支持
- [ ] 高可用方案
- [ ] API 文档自动生成

---

## 🔧 技术债务

| 债务 | 状态 | 计划 |
|------|------|------|
| main.py 拆分（3000+ 行） | 🔴 待处理 | Phase 1 |
| database.py 拆分（2000+ 行） | 🔴 待处理 | Phase 1 |
| pgvector 依赖 | 🟡 待替换 | Phase 2 |
| 无类型注解 | 🟡 待处理 | Phase 3 |
| 无 CI/CD | 🟢 待处理 | Phase 4 |
| 无代码检查 | 🟢 待处理 | Phase 4 |

---

## 💡 功能想法（待讨论）

- [ ] 记忆可视化（知识图谱展示）
- [ ] 多语言支持（i8n）
- [ ] 插件系统（自定义记忆提取器）
- [ ] Webhook 通知（记忆提取完成、异常告警）
- [ ] 记忆导出格式扩展（Markdown、CSV）

---

## 📊 进度追踪

| 阶段 | 状态 | 开始 | 完成 |
|------|------|------|------|
| Phase 1: 架构重构 | 🟡 进行中 | 2026-06-23 | - |
| Phase 2: zvec 迁移 | ⚪ 未开始 | - | - |
| Phase 3: 网关优化 | ⚪ 未开始 | - | - |
| Phase 4: 可观测性 | ⚪ 未开始 | - | - |

---

*最后更新：2026-06-23*
