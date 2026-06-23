---
name: tech-stack
title: "memory-gateway 技术栈"
tags: ["project", "tech-stack", "dependencies"]
---

# 技术栈

## 核心框架

| 技术 | 版本 | 用途 |
|------|------|------|
| Python | 3.12+ | 运行时 |
| FastAPI | 0.115+ | Web 框架 |
| uvicorn | 0.30+ | ASGI 服务器 |
| httpx | 0.27+ | HTTP 客户端（LLM API 调用） |

## 数据存储

| 技术 | 版本 | 用途 | 状态 |
|------|------|------|------|
| PostgreSQL | 14+ | 主数据库（记忆、对话、配置） | 生产使用 |
| asyncpg | 0.30+ | PostgreSQL 异步驱动 | 生产使用 |
| pgvector | 0.7+ | 向量搜索扩展 | 可选，后续移除 |
| zvec | 0.5+ | 嵌入式向量数据库 | 待集成 |

## 文本处理

| 技术 | 版本 | 用途 |
|------|------|------|
| jieba | 0.42+ | 中文分词 |
| Jinja2 | 3.1+ | 模板引擎（Dashboard） |

## 开发工具

| 技术 | 版本 | 用途 |
|------|------|------|
| pytest | 8.0+ | 测试框架 |
| pytest-asyncio | 0.23+ | 异步测试支持 |
| uv | - | 依赖管理 |

## 部署

| 技术 | 用途 |
|------|------|
| Docker | 容器化部署 |
| Render | 推荐部署平台 |

## 计划引入

| 技术 | 用途 | 阶段 |
|------|------|------|
| zvec | 向量存储替代 pgvector | Phase 2 |
| uvloop | 事件循环优化 | Phase 3 |
| structlog | 结构化日志 | Phase 3 |
| prometheus-client | 指标采集 | Phase 3 |

## 依赖配置

```toml
# pyproject.toml
[project]
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn>=0.30.0",
    "httpx>=0.27.0",
    "asyncpg>=0.30.0",
    "jieba>=0.42.1",
    "jinja2>=3.1.4",
]

[dependency-groups]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "httpx>=0.27.0",
]
```
