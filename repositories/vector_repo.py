"""
向量存储实现

使用 zvec 作为向量数据库，替代 pgvector。
"""

import os
from typing import List, Dict, Any

from .base import VectorRepository

# zvec 配置
ZVEC_ENABLED = os.getenv("ZVEC_ENABLED", "false").lower() == "true"
ZVEC_PATH = os.getenv("ZVEC_PATH", "./zvec_data")
ZVEC_DIM = int(os.getenv("EMBEDDING_DIM", "256"))


class ZvecVectorRepository(VectorRepository):
    """zvec 向量存储实现"""

    def __init__(self, path: str = None, dim: int = None):
        self.path = path or ZVEC_PATH
        self.dim = dim or ZVEC_DIM
        self.collection = None

    async def init(self) -> None:
        """初始化 zvec 集合"""
        try:
            import zvec

            schema = zvec.CollectionSchema(
                name="memories",
                vectors=[
                    zvec.VectorSchema(
                        "embedding",
                        zvec.DataType.VECTOR_FP32,
                        self.dim,
                    )
                ],
            )

            self.collection = zvec.create_and_open(
                path=self.path,
                schema=schema,
            )
            print(f"✅ zvec 向量存储已初始化: {self.path}")

        except ImportError:
            print("⚠️ zvec 未安装，向量搜索将使用 pgvector 或 Python 端计算")
            raise
        except Exception as e:
            print(f"⚠️ zvec 初始化失败: {e}")
            raise

    async def insert(
        self, id: str, vector: List[float], metadata: Dict[str, Any]
    ) -> bool:
        """插入单条向量"""
        if not self.collection:
            return False

        try:
            import zvec

            doc = zvec.Doc(
                id=id,
                vectors={"embedding": vector},
                fields=metadata,
            )
            result = self.collection.insert(doc)
            return result.get("code", -1) == 0
        except Exception as e:
            print(f"⚠️ zvec 插入失败: {e}")
            return False

    async def search(
        self, vector: List[float], topk: int = 10
    ) -> List[Dict[str, Any]]:
        """向量相似度搜索"""
        if not self.collection:
            return []

        try:
            import zvec

            result = self.collection.query(
                vectors=zvec.VectorQuery(
                    field_name="embedding",
                    vector=vector,
                ),
                topk=topk,
            )

            # 转换结果格式
            results = []
            for item in result:
                results.append(
                    {
                        "id": item.get("id"),
                        "score": item.get("score", 0.0),
                        **item.get("fields", {}),
                    }
                )
            return results

        except Exception as e:
            print(f"⚠️ zvec 搜索失败: {e}")
            return []

    async def delete(self, id: str) -> bool:
        """删除向量"""
        if not self.collection:
            return False

        try:
            self.collection.delete(ids=[id])
            return True
        except Exception as e:
            print(f"⚠️ zvec 删除失败: {e}")
            return False

    async def batch_insert(self, items: List[Dict[str, Any]]) -> int:
        """批量插入向量"""
        if not self.collection:
            return 0

        try:
            import zvec

            docs = []
            for item in items:
                doc = zvec.Doc(
                    id=item["id"],
                    vectors={"embedding": item["vector"]},
                    fields=item.get("metadata", {}),
                )
                docs.append(doc)

            self.collection.insert(docs)
            return len(docs)

        except Exception as e:
            print(f"⚠️ zvec 批量插入失败: {e}")
            return 0



