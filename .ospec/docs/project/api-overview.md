---
name: api-overview
title: "memory-gateway API 总览"
tags: ["project", "api", "overview"]
---

# API 总览

## 基础信息

- **协议**：HTTP/HTTPS
- **格式**：JSON
- **鉴权**：`X-Gateway-Key` header 或 OAuth Bearer token（可选）

## API 端点

### 核心端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 健康检查 |
| POST | `/v1/chat/completions` | LLM 转发（OpenAI 兼容） |
| GET | `/v1/models` | 模型列表 |

### 记忆管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/memories` | 获取记忆列表 |
| GET | `/api/memories/search?q=` | 搜索记忆 |
| PUT | `/api/memories/{id}` | 更新记忆 |
| DELETE | `/api/memories/{id}` | 删除记忆 |
| POST | `/api/memories/batch-update` | 批量更新 |
| POST | `/api/memories/batch-delete` | 批量删除 |

### 三层记忆

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/memories/layer-stats` | 分层统计 |
| POST | `/api/memories/{id}/promote` | 提升为核心 |
| POST | `/api/memories/merge` | 合并记忆 |
| POST | `/api/memories/check-duplicate` | 检查重复 |

### 对话管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/conversations` | 对话列表 |
| GET | `/api/conversations/{session}/messages` | 对话消息 |
| DELETE | `/api/conversations/{session}` | 删除对话 |
| POST | `/api/conversations/batch-delete` | 批量删除 |
| GET | `/api/conversations/export` | 导出对话 |
| POST | `/api/conversations/import` | 导入对话 |

### 分区缓存

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/partition/status` | 缓存状态 |
| GET | `/api/partition/threads` | 线程列表 |
| PUT | `/api/partition/summary` | 更新摘要 |
| DELETE | `/api/partition/summary` | 删除摘要 |

### 系统配置

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/settings` | 获取配置 |
| PUT | `/api/settings` | 更新配置 |
| GET | `/dashboard` | Dashboard 界面 |

### 导入导出

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/export/memories` | 导出记忆 |
| POST | `/import/text` | 导入文本 |
| POST | `/import/memories` | 导入记忆 |

## 请求/响应示例

### 记忆搜索

```bash
GET /api/memories/search?q=Python HTTP/1.1

# 响应
{
  "memories": [
    {
      "id": 1,
      "content": "用户对Python感兴趣",
      "importance": 7,
      "score": 0.85
    }
  ]
}
```

### 对话转发

```bash
POST /v1/chat/completions HTTP/1.1
Content-Type: application/json

{
  "model": "anthropic/claude-sonnet-4",
  "messages": [
    {"role": "user", "content": "你好"}
  ],
  "stream": true
}

# 响应（SSE 流）
data: {"choices":[{"delta":{"content":"你"}}]}
data: {"choices":[{"delta":{"content":"好"}}]}
data: [DONE]
```
