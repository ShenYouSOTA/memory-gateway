---
name: memory-gateway
title: memory-gateway
tags: ["ospec", "project", "full"]
---

# memory-gateway

> 层级：第 1 层（项目根文档）

## 项目概述

- **项目名称**：memory-gateway
- **模式**：full
- **状态**：已完成 OSpec 初始化
- **简介**：轻量级 LLM 转发网关，自动提取和注入记忆。支持任何 OpenAI 兼容客户端（Kelivo、ChatBox 等）和 LLM 服务商（OpenRouter、OpenAI、Ollama 等）。

## 技术栈

- Python
- Docker

## 项目架构

分层架构：Routes → Services → Repositories → PostgreSQL/zvec。

- `routes/` — HTTP 路由（memories/conversations/partition/admin/chat/settings）
- `services/` — 业务逻辑（MemoryService/ChatService/ExtractionService/CacheService/ConfigService/ConversationService）
- `repositories/` — 数据访问（MemoryRepo/ConversationRepo/ConfigRepo/VectorRepo）
- `utils/` — 工具函数（stream_helpers/partition_cache/memory_helpers/consolidation_helpers）
- `middleware/` — 鉴权（auth.py）
- `main.py` — app 初始化、lifespan、核心转发路由（/v1/chat/completions）
- `database.py` — 连接池、DDL、legacy 直查函数

**当前状态**：routes 层仍直调 database.py，service/repo 层未被充分利用。待修复依赖关系。

## 目录导航

- 文档中心：[docs/SKILL.md](docs/SKILL.md)
- AI 指南：[for-ai/ai-guide.md](for-ai/ai-guide.md)
- 可选知识地图：`knowledge/src/SKILL.md`、`knowledge/tests/SKILL.md`

## 插件阻断

- 开始推进 active change 前先读取 `.skillrc`。
- 如果项目启用了 Stitch，且当前 change 激活了 `stitch_design_review`，先检查 `changes/active/<change>/artifacts/stitch/approval.json`。
- 当 Stitch 审批缺失或状态不是 `approved` 时，视为 change 仍被阻断，先完成设计审核再继续。
