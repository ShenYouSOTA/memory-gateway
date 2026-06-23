---
name: module-map
title: "memory-gateway 模块地图"
tags: ["project", "modules", "map"]
---

# 模块地图

## 当前模块（待重构）

```
memory-gateway/
├── main.py                    # 🔴 主程序（3000+ 行，待拆分）
├── database.py                # 🔴 数据库操作（2000+ 行，待拆分）
├── memory_extractor.py        # ✅ 记忆提取（LLM 调用）
├── templates/
│   └── dashboard.html         # ✅ Dashboard 界面
├── static/                    # ✅ CSS/JS
├── system_prompt.txt          # ✅ AI 人设
└── seed_memories_example.py   # ✅ 预置记忆示例
```

## 目标模块（Phase 1 重构后）

```
memory-gateway/
├── main.py                    # ✅ App 初始化（~200 行）
├── routes/                    # ✅ 路由层
│   ├── __init__.py
│   ├── chat.py               # /v1/chat/completions
│   ├── memories.py           # /api/memories/*
│   ├── conversations.py      # /api/conversations/*
│   ├── settings.py           # /api/settings
│   ├── partition.py          # /api/partition/*
│   └── admin.py              # /api/admin/*
├── services/                  # ✅ 业务逻辑层
│   ├── __init__.py
│   ├── memory_service.py     # 记忆 CRUD + 搜索
│   ├── chat_service.py       # 对话转发 + 流式处理
│   ├── extraction_service.py # 记忆提取
│   └── cache_service.py      # 分区缓存
├── repositories/              # ✅ 数据访问层
│   ├── __init__.py
│   ├── base.py               # 接口定义
│   ├── memory_repo.py        # 记忆存储
│   ├── conversation_repo.py  # 对话存储
│   ├── config_repo.py        # 配置存储
│   └── vector_repo.py        # 向量存储（zvec）
├── middleware/                # ✅ 中间件
│   ├── __init__.py
│   └── auth.py               # 鉴权
├── utils/                     # ✅ 工具函数
│   ├── __init__.py
│   ├── text.py               # 文本处理
│   └── embedding.py          # Embedding 计算
├── memory_extractor.py        # ✅ 记忆提取（保持）
├── templates/                 # ✅ Dashboard
├── static/                    # ✅ 静态资源
└── tests/                     # ✅ 测试（41 个）
    ├── conftest.py
    ├── test_memory_extractor.py
    ├── test_database.py
    └── test_main.py
```

## 模块职责

| 模块 | 职责 | 依赖 |
|------|------|------|
| main.py | App 初始化、lifespan | routes, middleware |
| routes/ | HTTP 请求处理 | services |
| services/ | 业务逻辑 | repositories |
| repositories/ | 数据访问 | PostgreSQL, zvec |
| middleware/ | 鉴权、日志 | - |
| utils/ | 工具函数 | - |
