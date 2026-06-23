"""
Embedding 计算工具函数

从 database.py 提取的 embedding 计算逻辑。
"""

import os
from typing import List

import httpx

# Embedding 配置
EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY", "")
EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL", "https://api.openai.com/v1")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "256"))


async def compute_embedding(text: str) -> List[float]:
    """
    调用 OpenAI 兼容的 Embedding API 计算文本向量

    参数：
        text: 要计算 embedding 的文本

    返回：
        向量列表，失败返回空列表
    """
    if not EMBEDDING_API_KEY:
        return []

    try:
        if len(text) > 4000:
            text = text[:4000]

        body = {
            "model": EMBEDDING_MODEL,
            "input": text,
        }
        if EMBEDDING_DIM > 0:
            body["dimensions"] = EMBEDDING_DIM

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{EMBEDDING_BASE_URL}/embeddings",
                headers={
                    "Authorization": f"Bearer {EMBEDDING_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["data"][0]["embedding"]
    except Exception as e:
        print(f"⚠️ Embedding计算失败: {e}")
        return []


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """
    计算两个向量的余弦相似度

    参数：
        a: 向量 a
        b: 向量 b

    返回：
        余弦相似度（0-1）
    """
    import math

    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0
    return dot / (norm_a * norm_b)
