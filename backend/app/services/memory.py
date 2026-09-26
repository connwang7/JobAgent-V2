"""长期记忆：user_memories 表 + Qdrant 向量召回（方案 6.9 节语义记忆层）。"""
import uuid
from datetime import datetime

from pydantic import BaseModel

from app.core.logging import logger
from app.core.db import AsyncSessionLocal
from app.matching.embedding import get_embedding_client
from app.models.letter import UserMemory
from app.repositories.letter import MemoryRepository

MEMORY_COLLECTION = "user_memories"
TOP_K = 5


class MemoryHit(BaseModel):
    content: str
    memory_type: str
    score: float


async def remember(user_id: int, content: str, memory_type: str = "preference",
                   importance: float = 0.5, valid_until: datetime | None = None) -> UserMemory:
    """写入记忆条目并向量化。触发时机：用户显式"记住…"、偏好变更、Critic 修订被采纳。"""
    from app.matching.retriever import get_qdrant
    from qdrant_client import models

    embedding = await get_embedding_client().embed([content])
    point_id = uuid.uuid4().hex

    client = get_qdrant()
    try:
        if not await client.collection_exists(MEMORY_COLLECTION):
            await client.create_collection(
                collection_name=MEMORY_COLLECTION,
                vectors_config=models.VectorParams(size=len(embedding[0]), distance=models.Distance.COSINE),
            )
        await client.upsert(
            collection_name=MEMORY_COLLECTION,
            points=[models.PointStruct(
                id=point_id, vector=embedding[0],
                payload={"user_id": user_id, "memory_type": memory_type, "content": content},
            )],
        )
    finally:
        await client.close()

    async with AsyncSessionLocal() as db:
        repo = MemoryRepository(db)
        mem = await repo.add(UserMemory(
            user_id=user_id, memory_type=memory_type, content=content,
            importance=importance, embedding_id=point_id, valid_until=valid_until,
        ))
        await db.commit()
        return mem


async def recall(user_id: int, query: str, top_k: int = TOP_K) -> list[MemoryHit]:
    """向量召回 top-K 记忆（注入 Planner 与 ChatBot 的 prompt 组装阶段）。"""
    from qdrant_client import models
    from app.matching.retriever import get_qdrant

    try:
        vector = await get_embedding_client().embed_query(query)
        client = get_qdrant()
        try:
            # 注意：query_points 是协程，必须 await 之后再取 .points
            # （写成 await client.query_points(...).points 会得到
            #  "'coroutine' object has no attribute 'points'"，召回永远失败）
            resp = await client.query_points(
                collection_name=MEMORY_COLLECTION,
                query=vector,
                limit=top_k,
                query_filter=models.Filter(must=[models.FieldCondition(
                    key="user_id", match=models.MatchValue(value=user_id),
                )]),
                with_payload=True,
            )
            hits = resp.points
        finally:
            await client.close()
        now = datetime.utcnow()
        results = []
        for h in hits:
            # 效期过滤（如"正在找北京的工作"半年后失效）
            valid_until = h.payload.get("valid_until")
            if valid_until and str(valid_until) < now.isoformat():
                continue
            results.append(MemoryHit(
                content=h.payload.get("content", ""),
                memory_type=h.payload.get("memory_type", "fact"),
                score=h.score,
            ))
        return results
    except Exception as exc:
        logger.warning("memory_recall_failed", error=str(exc))
        return []


async def inject_memories(user_id: int, query: str) -> list[str]:
    """返回可直接拼入 prompt 的记忆文本列表。"""
    return [hit.content for hit in await recall(user_id, query)]
