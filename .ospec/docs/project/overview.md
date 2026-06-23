---
name: project-overview
title: "memory-gateway 项目概览"
tags: ["project", "overview", "architecture"]
---

# 项目概览

## 项目简介

**memory-gateway** 是一个轻量级 LLM 转发网关，为 AI 对话系统添加长期记忆层。

核心能力：
- 接收 OpenAI 兼容客户端的消息
- 自动搜索相关记忆，注入 system prompt
- 转发给 LLM API（OpenRouter、OpenAI、Ollama 等）
- 后台自动提取并存储新记忆

## 当前状态

- **代码规模**：5,500+ 行（main.py 3026、database.py 2176、memory_extractor.py 295）
- **测试覆盖**：41 个单元测试（pytest 框架已就绪）
- **核心功能**：三层记忆架构、分区缓存、四维混合搜索

## 技术债务

- `main.py` 3000+ 行，路由/业务/流式处理混杂
- `database.py` 2000+ 行，52 个函数无分层
- 依赖 pgvector 扩展，部署复杂
- 无 CI/CD、无类型检查

## 战略方向

**先拆架构，后迁 zvec**

```
Phase 1: 架构重构（Week 1-2）
    ↓  结构清晰、职责分离、测试覆盖
Phase 2: zvec 迁移（Week 3）
    ↓  替换向量存储、简化部署
Phase 3: 网关优化（Week 4+）
    ↓  uvloop、日志、OAuth、监控
```

## 核心特性

| 特性 | 状态 | 说明 |
|------|------|------|
| 三层记忆 | ✅ | 碎片→事件→核心 |
| 分区缓存 | ✅ | A/B 轮转 + 摘要压缩 |
| 混合搜索 | ✅ | 关键词 + 语义 + 重要性 + 时间 |
| 向量搜索 | ⚠️ | 依赖 pgvector，后续迁移 zvec |
| 测试覆盖 | ⚠️ | 框架就绪，覆盖待提升 |
| 架构分层 | ❌ | 待重构 |

## 目标架构

```
客户端 → FastAPI → Routes → Services → Repositories → PostgreSQL/zvec
                           ↓
                    Memory Extraction (LLM)
```
