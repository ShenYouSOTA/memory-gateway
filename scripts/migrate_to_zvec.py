#!/usr/bin/env python3
"""
zvec 数据迁移脚本

将 PostgreSQL 中的记忆数据迁移到 zvec 向量数据库。

使用方法：
    python scripts/migrate_to_zvec.py

环境变量：
    DATABASE_URL: PostgreSQL 连接字符串
    ZVEC_ENABLED: 是否启用 zvec
    ZVEC_PATH: zvec 数据存储路径
    EMBEDDING_API_KEY: Embedding API Key
    EMBEDDING_BASE_URL: Embedding API 地址
    EMBEDDING_MODEL: Embedding 模型
    EMBEDDING_DIM: 向量维度
"""

import asyncio
import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import get_pool, init_tables, get_all_memories_detail
from utils.embedding import compute_embedding
from repositories.vector_repo import ZvecVectorRepository


async def migrate():
    """执行迁移"""
    print("🚀 开始 zvec 数据迁移...")

    # 初始化数据库
    await init_tables()

    # 获取所有记忆
    memories = await get_all_memories_detail()
    print(f"📊 共有 {len(memories)} 条记忆")

    if not memories:
        print("✅ 没有需要迁移的记忆")
        return

    # 初始化 zvec
    dim = int(os.getenv("EMBEDDING_DIM", "256"))
    zvec_repo = ZvecVectorRepository(dim=dim)
    await zvec_repo.init()

    # 逐条迁移
    success_count = 0
    skip_count = 0
    error_count = 0

    for i, mem in enumerate(memories, 1):
        mem_id = str(mem["id"])
        content = mem.get("content", "")

        if not content:
            skip_count += 1
            continue

        try:
            # 计算 embedding
            embedding = await compute_embedding(content)
            if not embedding:
                print(f"⚠️ 记忆 {mem_id} embedding 计算失败，跳过")
                skip_count += 1
                continue

            # 构建元数据
            metadata = {
                "content": content,
                "importance": mem.get("importance", 5),
                "layer": mem.get("layer", 1),
                "is_active": mem.get("is_active", True),
            }

            # 插入 zvec
            success = await zvec_repo.insert(mem_id, embedding, metadata)
            if success:
                success_count += 1
            else:
                error_count += 1

            # 进度显示
            if i % 100 == 0 or i == len(memories):
                print(f"⏳ 进度: {i}/{len(memories)} (成功: {success_count}, 跳过: {skip_count}, 失败: {error_count})")

        except Exception as e:
            print(f"❌ 记忆 {mem_id} 迁移失败: {e}")
            error_count += 1

    print(f"\n✅ 迁移完成:")
    print(f"   - 成功: {success_count}")
    print(f"   - 跳过: {skip_count}")
    print(f"   - 失败: {error_count}")


async def verify():
    """验证迁移结果"""
    print("\n🔍 验证迁移结果...")

    dim = int(os.getenv("EMBEDDING_DIM", "256"))
    zvec_repo = ZvecVectorRepository(dim=dim)
    await zvec_repo.init()

    # 测试搜索
    test_query = "用户喜欢什么"
    embedding = await compute_embedding(test_query)
    if embedding:
        results = await zvec_repo.search(embedding, topk=5)
        print(f"📝 测试查询: '{test_query}'")
        print(f"   返回 {len(results)} 条结果")
        for r in results[:3]:
            print(f"   - [score={r.get('score', 0):.3f}] {r.get('content', '')[:60]}...")
    else:
        print("⚠️ 测试查询 embedding 计算失败")


def main():
    """主函数"""
    # 检查环境变量
    if not os.getenv("DATABASE_URL"):
        print("❌ 错误: DATABASE_URL 环境变量未设置")
        sys.exit(1)

    if not os.getenv("EMBEDDING_API_KEY"):
        print("❌ 错误: EMBEDDING_API_KEY 环境变量未设置")
        sys.exit(1)

    # 执行迁移
    asyncio.run(migrate())

    # 验证结果
    asyncio.run(verify())


if __name__ == "__main__":
    main()
