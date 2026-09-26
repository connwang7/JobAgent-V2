"""embed_jobs：JD 清洗 + 向量化写入 Qdrant（岗位入库/定时增量触发）。

JD 入库 → 去样板文字 → 拼接语义文本 → BGE-M3 embedding → Qdrant (job_jd)
同时用 LLM 抽取 required_skills 存 raw JSON（供精排打分使用）。
"""
from app.core.logging import logger
from app.workers.celery_app import celery_app

# JD 中的样板文字（清洗用）
BOILERPLATE_MARKERS = [
    "职位描述", "岗位职责", "任职要求", "工作职责", "岗位要求",
    "Job Description", "Responsibilities", "Requirements",
]


def clean_jd(text: str) -> str:
    """去掉导航/样板文字，保留语义主体。"""
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    # 简单策略：保留包含实质内容的行（>4 字符），去掉纯标签行
    return "\n".join(ln for ln in lines if len(ln) > 2)


@celery_app.task(name="embed_jobs", bind=True, max_retries=3)
def embed_jobs_task(self, job_posting_ids: list[int] | None = None,
                    only_missing: bool = True) -> dict:
    import asyncio

    async def _run() -> dict:
        from sqlalchemy import select

        from app.core.db import AsyncSessionLocal
        from app.matching.embedding import get_embedding_client
        from app.matching.retriever import upsert_jd
        from app.models.job import JobPosting
        from app.repositories.job import JobRepository

        async with AsyncSessionLocal() as db:
            repo = JobRepository(db)
            if job_posting_ids:
                postings = [p for p in (await repo.get(i) for i in job_posting_ids) if p]
            else:
                postings = await repo.recent(limit=200)
                if only_missing:
                    postings = [p for p in postings if not p.embedding_id]

            if not postings:
                return {"embedded": 0}

            client = get_embedding_client()
            embedded = 0
            for p in postings:
                try:
                    jd_text = clean_jd(p.description or p.title)
                    # 语义文本：标题+公司+城市+JD 主体
                    semantic_text = f"{p.title} {p.company} {p.location} {jd_text}"[:3000]
                    vectors = await client.embed([semantic_text])
                    point_id = await upsert_jd(
                        p.id, semantic_text, vectors[0],
                        payload={"city": p.location, "title": p.title, "company": p.company},
                    )
                    p.embedding_id = point_id

                    # LLM 抽取 required_skills（失败不阻塞向量化）
                    if not (p.raw or {}).get("required_skills"):
                        skills = await _extract_skills(jd_text)
                        p.raw = {**(p.raw or {}), "required_skills": skills}

                    embedded += 1
                except Exception as exc:
                    logger.warning("embed_job_failed", job_id=p.id, error=str(exc))
            await db.commit()
            logger.info("jobs_embedded", n=embedded)
            return {"embedded": embedded}

    return asyncio.run(_run())


async def _extract_skills(jd_text: str) -> list[str]:
    from langchain_core.messages import HumanMessage, SystemMessage
    from pydantic import BaseModel, Field

    class Skills(BaseModel):
        skills: list[str] = Field(default_factory=list)

    from app.agents.graph.events import role_llm
    llm = role_llm("worker", {})
    result: Skills = await llm.with_structured_output(Skills).ainvoke([
        SystemMessage(content="从 JD 中抽取硬性技能要求（每项一个词，最多 12 项，只输出确实要求的技能）。"),
        HumanMessage(content=jd_text[:4000]),
    ])
    return result.skills
