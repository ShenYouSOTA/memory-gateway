# AI Memory Gateway - Todo & Roadmap

## 📋 待办事项

### 高优先级 (P0)

- [ ] 引入 `uvloop` 事件循环替换，提升并发性能
- [ ] 连接池参数调优（min_size=2, max_size=20, command_timeout=30）
- [ ] 引入结构化日志（structlog），替代 print() 输出
- [ ] MCP OAuth 2.1 鉴权框架，支持标准 OAuth 流程

### 中优先级 (P1)

- [ ] OpenAI API 参数透传（temperature, top_p, max_tokens 等）
- [ ] Input Guardrail 基础框架（敏感词过滤、输入验证）
- [ ] Model Registry 基础实现（模型元信息管理）
- [ ] 成本路由逻辑（根据模型价格自动选择最优模型）

### 低优先级 (P2)

- [ ] 智能路由逻辑（根据任务类型、语言、长度自动选模型）
- [ ] Metrics 采集（Prometheus 格式）
- [ ] 分布式链路追踪（OpenTelemetry）
- [ ] 端到端集成测试
- [ ] 文档更新与 CHANGELOG

---

## 🗺️ Roadmap

### v4.0 - 性能优化与安全加固

**目标：** 提升并发性能，增强安全性

- [x] uv 依赖管理（已完成）
- [ ] uvloop 事件循环
- [ ] 连接池调优
- [ ] 结构化日志
- [ ] MCP OAuth 2.1 鉴权

### v4.1 - 智能路由与参数优化

**目标：** 支持更灵活的模型选择和参数配置

- [ ] OpenAI API 参数透传
- [ ] Model Registry（模型元信息管理）
- [ ] 成本路由（按价格自动选模型）
- [ ] Input Guardrail（敏感词过滤）

### v4.2 - 可观测性与监控

**目标：** 完善监控和调试能力

- [ ] Prometheus Metrics 指标采集
- [ ] OpenTelemetry 分布式链路追踪
- [ ] 请求日志增强（request_id、耗时统计）

### v5.0 - 企业级特性

**目标：** 支持多租户、高可用部署

- [ ] 多租户支持（用户隔离、配额管理）
- [ ] 高可用部署方案（Redis 会话共享）
- [ ] 完整的集成测试套件
- [ ] API 文档自动生成（OpenAPI/Swagger）

---

## 🔧 技术债务

- [ ] `main.py` 拆分（3000+ 行，建议拆分为 routes/services/utils）
- [ ] 添加类型注解（Type Hints）
- [ ] 单元测试覆盖（当前无测试）
- [ ] CI/CD 流水线（GitHub Actions）
- [ ] 代码质量检查（ruff、mypy）

---

## 💡 功能想法（待讨论）

- [ ] 记忆可视化（知识图谱展示）
- [ ] 多语言支持（i18n）
- [ ] 插件系统（自定义记忆提取器）
- [ ] Webhook 通知（记忆提取完成、异常告警）
- [ ] 记忆导出格式扩展（Markdown、CSV）

---

*最后更新：2026-06-12*
