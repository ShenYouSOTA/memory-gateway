# AI Memory Gateway 实施计划

> **战略方向**：先拆架构（结构清晰），后迁 zvec（存储升级）

---

## 总体规划

```
Phase 1: 架构重构（Week 1-2）
    ↓  结构清晰、职责分离、测试覆盖
Phase 2: zvec 迁移（Week 3）
    ↓  替换向量存储、简化部署
Phase 3: 网关优化（Week 4+）
    ↓  uvloop、日志、OAuth、监控
```

---

## Phase 1: 架构重构

### 目标
- 拆分 `main.py`（3000+ 行）为清晰的模块结构
- 拆分 `database.py`（2000+ 行）为职责单一的 Repository
- 建立测试保护网，确保重构安全

### Step 1.1: 目录结构重组

**前置条件**：测试框架已就绪（已完成）

**操作内容**：
```
memory-gateway/
├── main.py                    # 精简为 app 初始化 + lifespan
├── routes/                    # 路由层
│   ├── __init__.py
│   ├── chat.py               # /v1/chat/completions
│   ├── memories.py           # /api/memories/*
│   ├── conversations.py      # /api/conversations/*
│   ├── settings.py           # /api/settings
│   ├── partition.py          # /api/partition/*
│   └── admin.py              # /api/admin/*
├── services/                  # 业务逻辑层
│   ├── __init__.py
│   ├── memory_service.py     # 记忆 CRUD + 搜索
│   ├── chat_service.py       # 对话转发 + 流式处理
│   ├── extraction_service.py # 记忆提取（调用 LLM）
│   └── cache_service.py      # 分区缓存逻辑
├── repositories/              # 数据访问层
│   ├── __init__.py
│   ├── base.py               # Repository 基类
│   ├── memory_repo.py        # 记忆存储
│   ├── conversation_repo.py  # 对话存储
│   ├── config_repo.py        # 配置存储
│   └── vector_repo.py        # 向量存储（后续替换为 zvec）
├── middleware/                # 中间件
│   ├── __init__.py
│   └── auth.py               # 鉴权逻辑
└── utils/                     # 工具函数
    ├── __init__.py
    ├── text.py               # 文本处理（分词等）
    └── embedding.py          # Embedding 计算
```

**验证标准**：
- 所有现有 API 端点正常工作
- 测试全部通过
- 无循环导入

**回滚方案**：git revert

---

### Step 1.2: Repository 层抽象

**前置条件**：Step 1.1 完成

**操作内容**：

1. 定义 Repository 接口：
```python
# repositories/base.py
from abc import ABC, abstractmethod
from typing import List, Optional, Dict

class MemoryRepository(ABC):
    @abstractmethod
    async def save(self, content: str, importance: int, source_session: str) -> int: ...
    
    @abstractmethod
    async def search(self, query: str, limit: int = 10) -> List[Dict]: ...
    
    @abstractmethod
    async def get_by_id(self, memory_id: int) -> Optional[Dict]: ...
    
    @abstractmethod
    async def update(self, memory_id: int, **kwargs) -> bool: ...
    
    @abstractmethod
    async def delete(self, memory_id: int) -> bool: ...
    
    @abstractmethod
    async def list_all(self, **filters) -> List[Dict]: ...

class VectorRepository(ABC):
    @abstractmethod
    async def insert(self, id: str, vector: List[float], metadata: Dict): ...
    
    @abstractmethod
    async def search(self, vector: List[float], topk: int = 10) -> List[Dict]: ...
    
    @abstractmethod
    async def delete(self, id: str): ...
```

2. 实现 PostgreSQL 版本（从 database.py 提取）

**验证标准**：
- Repository 接口定义清晰
- PostgreSQL 实现通过所有测试
- 业务层只依赖接口，不依赖实现

---

### Step 1.3: Service 层提取

**前置条件**：Step 1.2 完成

**操作内容**：

1. 从 main.py 提取业务逻辑到 services/：
```python
# services/memory_service.py
class MemoryService:
    def __init__(self, repo: MemoryRepository, vector_repo: VectorRepository):
        self.repo = repo
        self.vector_repo = vector_repo
    
    async def search_memories(self, query: str, limit: int = 10) -> List[Dict]:
        """四维混合搜索"""
        # 从 main.py 搬过来的逻辑
        ...
    
    async def extract_and_save(self, messages: List[Dict], session_id: str):
        """提取并保存记忆"""
        # 从 main.py 搬过来的逻辑
        ...
```

2. 从 main.py 提取路由到 routes/：
```python
# routes/memories.py
from fastapi import APIRouter, Depends

router = APIRouter()

@router.get("/api/memories")
async def get_memories(memory_service: MemoryService = Depends(get_memory_service)):
    return await memory_service.list_all()
```

**验证标准**：
- main.py 精简到 200 行以内
- 每个文件职责单一
- 测试覆盖 Service 层

---

### Step 1.4: 测试补充

**前置条件**：Step 1.3 完成

**操作内容**：

1. 为每个 Repository 编写单元测试
2. 为每个 Service 编写单元测试（mock Repository）
3. 为每个 Route 编写集成测试
4. 测试覆盖率目标：80%+

**验证标准**：
- `pytest --cov` 覆盖率 >= 80%
- 所有测试通过

---

## Phase 2: zvec 迁移

### 目标
- 替换 pgvector 为 zvec
- 简化部署（去除 PostgreSQL 向量扩展依赖）
- 提升向量搜索性能

### Step 2.1: zvec 集成

**前置条件**：Phase 1 完成

**操作内容**：

1. 添加依赖：
```toml
# pyproject.toml
dependencies = [
    "zvec>=0.5.0",
    # ... 其他依赖
]
```

2. 实现 ZvecRepository：
```python
# repositories/zvec_repo.py
import zvec

class ZvecVectorRepository(VectorRepository):
    def __init__(self, path: str, dim: int = 256):
        self.path = path
        self.dim = dim
        self.collection = None
    
    async def init(self):
        schema = zvec.CollectionSchema(
            name="memories",
            vectors=zvec.VectorSchema("embedding", zvec.DataType.VECTOR_FP32, self.dim),
        )
        self.collection = zvec.create_and_open(path=self.path, schema=schema)
    
    async def insert(self, id: str, vector: List[float], metadata: Dict):
        self.collection.insert([
            zvec.Doc(id=id, vectors={"embedding": vector}, metadata=metadata)
        ])
    
    async def search(self, vector: List[float], topk: int = 10) -> List[Dict]:
        results = self.collection.query(
            zvec.VectorQuery("embedding", vector=vector),
            topk=topk
        )
        return results
```

3. 环境变量控制切换：
```python
ZVEC_ENABLED = os.getenv("ZVEC_ENABLED", "false").lower() == "true"
ZVEC_PATH = os.getenv("ZVEC_PATH", "./zvec_data")
```

**验证标准**：
- zvec 读写正常
- 搜索结果与 pgvector 一致
- 性能测试通过

---

### Step 2.2: 数据迁移脚本

**前置条件**：Step 2.1 完成

**操作内容**：

1. 编写迁移脚本：
```python
# scripts/migrate_to_zvec.py
async def migrate():
    # 1. 从 PostgreSQL 读取所有记忆
    memories = await memory_repo.list_all()
    
    # 2. 计算 embedding（如果没有）
    for mem in memories:
        if not mem.get('embedding'):
            mem['embedding'] = await compute_embedding(mem['content'])
    
    # 3. 写入 zvec
    for mem in memories:
        await zvec_repo.insert(
            id=str(mem['id']),
            vector=mem['embedding'],
            metadata={'content': mem['content'], 'importance': mem['importance']}
        )
```

2. 双写模式（过渡期）：
```python
# 新记忆同时写入 PostgreSQL 和 zvec
async def save_memory(content, importance, session_id):
    pg_id = await pg_repo.save(content, importance, session_id)
    embedding = await compute_embedding(content)
    await zvec_repo.insert(str(pg_id), embedding, {...})
    return pg_id
```

**验证标准**：
- 迁移脚本执行成功
- 数据一致性检查通过
- 可回滚到纯 PostgreSQL 模式

---

### Step 2.3: 完全切换

**前置条件**：Step 2.2 稳定运行 1 周

**操作内容**：

1. 向量搜索完全切换到 zvec
2. PostgreSQL 降级为元数据存储（不含向量列）
3. 移除 pgvector 依赖

**验证标准**：
- 所有功能正常
- 部署文档更新
- 性能指标达标

---

## Phase 3: 网关优化

> 以下步骤从原 PLAN.md 保留，优先级降低

### Step 3.1: uvloop 事件循环替换
- 添加 `uvloop>=0.19.0`
- 异步性能提升 30-50%

### Step 3.2: 结构化日志
- 引入 `structlog`
- 替换所有 `print()` 为结构化日志

### Step 3.3: 连接池调优
- min_size=2, max_size=20
- command_timeout=30

### Step 3.4: MCP OAuth 2.1 鉴权
- 支持标准 OAuth 流程
- 向后兼容 X-Gateway-Key

### Step 3.5: OpenAI API 参数透传
- temperature, top_p, max_tokens 等
- tools, tool_choice

### Step 3.6: Input Guardrail
- 消息数/长度限制
- 敏感词过滤

### Step 3.7: Model Registry
- 模型元信息管理
- 别名解析

### Step 3.8: 成本路由
- 根据任务类型选择最优模型
- 记忆提取用便宜模型

### Step 3.9: Prometheus Metrics
- /metrics 端点
- 请求计数、延迟、token 统计

### Step 3.10: OpenTelemetry Tracing
- 分布式链路追踪
- 可选启用

---

## 依赖关系图

```
Phase 1 (架构重构)
├── Step 1.1 (目录重组) ─────────┐
├── Step 1.2 (Repository 抽象) ←─┤
├── Step 1.3 (Service 提取) ←────┤
└── Step 1.4 (测试补充) ←────────┘

Phase 2 (zvec 迁移)
├── Step 2.1 (zvec 集成) ← Phase 1 完成
├── Step 2.2 (数据迁移) ← Step 2.1
└── Step 2.3 (完全切换) ← Step 2.2 稳定

Phase 3 (网关优化) ← 可与 Phase 2 并行
├── Step 3.1-3.3 (基础优化)
├── Step 3.4-3.6 (安全与参数)
├── Step 3.7-3.8 (智能路由)
└── Step 3.9-3.10 (可观测性)
```

---

## 风险评估

| 阶段 | 风险 | 缓解措施 |
|------|------|----------|
| Phase 1 | 重构引入 bug | 测试保护、小步提交 |
| Phase 2 | zvec 不稳定 | 双写过渡、可回滚 |
| Phase 3 | 优化效果不明显 | 渐进实施、性能监控 |

---

## 时间估算

| 阶段 | 时间 | 产出 |
|------|------|------|
| Phase 1 | 1-2 周 | 清晰架构、测试覆盖 |
| Phase 2 | 1 周 | zvec 集成、性能提升 |
| Phase 3 | 2-3 周 | 生产级网关 |
| **总计** | 4-6 周 | 企业级 Memory Gateway |
