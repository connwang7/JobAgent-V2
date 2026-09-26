"""向量检索：Qdrant（JD collection），payload 过滤（城市/雇佣类型）。"""
import uuid

from qdrant_client import AsyncQdrantClient, models

from app.core.config import settings
from app.core.logging import logger
from app.core.net import is_local_endpoint

VECTOR_SIZE = 1024


def get_qdrant() -> AsyncQdrantClient:
    # check_compatibility=False：服务未启动时避免客户端噪音告警
    # trust_env：Qdrant 是本机/内网服务，不能走系统代理（否则 502 upstream connect failed）
    return AsyncQdrantClient(url=settings.qdrant_url, check_compatibility=False,
                             timeout=3.0,
                             trust_env=not is_local_endpoint(settings.qdrant_url))


async def ensure_collection() -> None:
    client = get_qdrant()
    try:
        if not await client.collection_exists(settings.qdrant_collection):
            await client.create_collection(
                collection_name=settings.qdrant_collection,
                vectors_config=models.VectorParams(size=VECTOR_SIZE, distance=models.Distance.COSINE),
            )
            logger.info("qdrant_collection_created", collection=settings.qdrant_collection)
    finally:
        await client.close()


async def upsert_jd(job_posting_id: int, text: str, vector: list[float],
                    payload: dict | None = None) -> str:
    """JD 向量入库。point id 用确定性 uuid5（同岗位重写不产生冗余点）。"""
    client = get_qdrant()
    point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"job:{job_posting_id}"))
    try:
        await client.upsert(
            collection_name=settings.qdrant_collection,
            points=[models.PointStruct(
                id=point_id, vector=vector,
                payload={"job_posting_id": job_posting_id, **(payload or {})},
            )],
        )
    finally:
        await client.close()
    return point_id


async def search_similar(vector: list[float], top_k: int = 20,
                         city: str | None = None) -> list[dict]:
    """向量召回 + payload 过滤。返回 [{job_posting_id, score, payload}]。"""
    client = get_qdrant()
    flt = None
    if city:
        flt = models.Filter(must=[models.FieldCondition(
            key="city", match=models.MatchText(text=city),
        )])
    try:
        # 注意：query_points 是协程，必须 await 之后再取 .points（否则抛
        # "'coroutine' object has no attribute 'points'"，向量召回静默失败）
        resp = await client.query_points(
            collection_name=settings.qdrant_collection,
            query=vector,
            limit=top_k,
            query_filter=flt,
            with_payload=True,
        )
        hits = resp.points
        return [
            {
                "job_posting_id": h.payload.get("job_posting_id"),
                "score": h.score,
                "payload": h.payload,
            }
            for h in hits
        ]
    finally:
        await client.close()
