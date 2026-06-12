# AI Memory Gateway

轻量级 LLM 转发网关，自动提取和注入记忆。支持任何 OpenAI 兼容客户端（Kelivo、ChatBox 等）和 LLM 服务商（OpenRouter、OpenAI、Ollama 等）。

---

## ✨ 功能

- **长期记忆** — 自动从对话提取关键信息，下次聊天自动回忆
- **三层记忆架构** — 碎片（自动提取）→ 事件（AI 整理）→ 核心（手动标记）
- **分区缓存** — A/B 区轮转 + 摘要压缩，利用 prompt caching 节省 token
- **自定义人设** — `system_prompt.txt` 每次对话自动注入
- **对话管理** — 历史浏览、搜索、批量删除、session 合并
- **Token 统计** — 自动记录每次对话的 token 消耗
- **全端点鉴权** — `GATEWAY_SECRET` 环境变量保护所有 API
- **设置面板** — Dashboard 热更新配置，无需重启
- **向量搜索（可选）** — 关键词 + 语义四维混合搜索

---

## 🚀 快速开始

### 1. 纯转发网关（无需数据库）

```bash
# 本地运行
API_KEY=sk-xxx API_BASE_URL=https://openrouter.ai/api/v1/chat/completions python main.py
```

**部署到 Render：**
1. Fork 代码到 GitHub
2. 创建 Web Service，连接仓库
3. 设置环境变量：

| 变量 | 说明 | 示例 |
|------|------|------|
| `API_KEY` | LLM API Key | `sk-or-v1-xxxx` |
| `API_BASE_URL` | API 地址 | `https://openrouter.ai/api/v1/chat/completions` |
| `DEFAULT_MODEL` | 默认模型 | `anthropic/claude-sonnet-4` |
| `PORT` | 端口 | `8000` |

4. 部署后访问 `https://你的网关地址/` 看到 `{"status":"running"}` 即成功

**连接客户端（Kelivo）：**
- API 地址：`https://你的网关地址.onrender.com/v1`
- API Key：随便填（网关用自己的 key）

### 2. 加上记忆系统

创建 PostgreSQL 数据库（Render/Neon/Supabase 均可），添加环境变量：

| 变量 | 说明 | 默认 |
|------|------|------|
| `DATABASE_URL` | PostgreSQL 连接字符串 | - |
| `MEMORY_ENABLED` | 开启记忆 | `false` |
| `MEMORY_MODEL` | 提取模型（推荐便宜小模型） | `anthropic/claude-haiku-4` |
| `MAX_MEMORIES_INJECT` | 每次注入最大记忆条数 | `15` |
| `MIN_SCORE_THRESHOLD` | 最低分数阈值 | `0.15` |
| `MEMORY_EXTRACT_INTERVAL` | 提取间隔（0=禁用/1=每轮/N=每N轮） | `1` |

部署后访问 `https://你的网关地址/dashboard` 管理记忆。

### 3. 分区缓存（省 token）

| 变量 | 说明 | 默认 |
|------|------|------|
| `CACHE_PARTITION_ENABLED` | 分区缓存开关 | `false` |
| `CACHE_PARTITION_X` | 轮转周期（轮数） | `15` |
| `CACHE_SUMMARY_MODEL` | 摘要模型 | `anthropic/claude-haiku-4` |

> 💡 不需要记忆也能用分区缓存：`MEMORY_ENABLED=true` + `MEMORY_EXTRACT_ENABLED=false` + `CACHE_PARTITION_ENABLED=true`

---

## 📁 文件结构

```
├── main.py                    # 网关主程序
├── database.py                # 数据库操作（PostgreSQL）
├── memory_extractor.py        # AI 记忆提取
├── system_prompt.txt          # AI 人设
├── seed_memories_example.py   # 预置记忆示例
├── pyproject.toml             # 项目配置
├── Dockerfile                 # 容器配置
├── templates/dashboard.html   # Dashboard 界面
└── static/                    # CSS/JS
```

---

## 🛠️ 本地开发

```bash
# 安装依赖（推荐 uv）
uv sync

# 纯转发模式
API_KEY=sk-xxx python main.py

# 带记忆功能
DATABASE_URL=postgresql://... MEMORY_ENABLED=true API_KEY=sk-xxx python main.py
```

---

## 🔧 API 接口

| 路径 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 健康检查 |
| `/v1/chat/completions` | POST | 核心转发接口 |
| `/dashboard` | GET | 管理控制台 |
| `/api/memories` | GET | 获取记忆列表 |
| `/api/settings` | GET/PUT | 运行时配置 |
| `/api/partition/status` | GET | 分区缓存状态 |

---

## 🌐 支持的 LLM 服务

| 服务商 | API_BASE_URL |
|--------|-------------|
| OpenRouter | `https://openrouter.ai/api/v1/chat/completions` |
| OpenAI | `https://api.openai.com/v1/chat/completions` |
| Ollama | `http://localhost:11434/v1/chat/completions` |

---

## ❓ 常见问题

**Q: 部署后 502？**
A: 检查 `PORT` 环境变量，Render 需设为 `8000`。

**Q: 数据库连接失败？**
A: 外部数据库连接字符串末尾加 `?sslmode=require`。

**Q: 记忆太多影响性能？**
A: 每次最多注入 15 条（可调），通过 `MEMORY_EXTRACT_INTERVAL` 控制提取频率。

**Q: 能用免费额度吗？**
A: Render 免费层支持 Web Service + PostgreSQL，LLM API 费用另算。

---

## 📄 许可证

[MIT License](LICENSE)


