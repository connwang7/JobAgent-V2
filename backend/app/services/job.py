"""岗位与匹配服务。"""
from app.agents.graph.state import ResumeProfile
from app.core.errors import DependencyUnavailableError, NotFoundError
from app.core.logging import logger
from app.matching.embedding import get_embedding_client
from app.matching.retriever import search_similar
from app.matching.scorer import score_match
from app.models.job import JobPosting, MatchResult
from app.models.resume import Resume
from app.repositories.job import JobRepository, MatchRepository
from app.schemas.job import MatchOut
from sqlalchemy.ext.asyncio import AsyncSession


async def search_jobs(repo: JobRepository, keyword: str, company: str,
                      location: str, limit: int, offset: int) -> list[JobPosting]:
    return await repo.search(keyword, company, location, limit, offset)


async def get_matches(session: AsyncSession, match_repo: MatchRepository,
                      job_repo: JobRepository, resume: Resume,
                      top_k: int = 20, force: bool = False) -> list[MatchOut]:
    """RAG 人岗匹配（方案 7.1 数据流）。

    简历画像 → 同一 embedding 空间查询向量 → 向量 top-K 召回
    → 结构化评分（精排） → match_results 落库缓存（同简历同岗位不重算）。
    """
    if not resume.profile:
        raise NotFoundError("简历尚未完成解析，请稍后再试或重新上传", code="RES-403")

    profile = ResumeProfile(**resume.profile)

    # 已有缓存直接返回（除非强制刷新）
    if not force:
        cached = await match_repo.top_by_resume(resume.id, limit=top_k)
        if cached:
            out: list[MatchOut] = []
            for mr in cached:
                posting = await job_repo.get(mr.job_posting_id)
                if posting:
                    out.append(_to_match_out(posting, mr))
            if out:
                return out

    # 查询向量：画像核心信息拼接
    query_text = " ".join(profile.skills) + " " + " ".join(profile.highlights[:5])
    try:
        vector = await get_embedding_client().embed_query(query_text[:2000])
        hits = await search_similar(vector, top_k=top_k)
    except Exception as exc:
        # 向量 / Embedding 不可用属可降级故障：给明确指引，别让整页 500
        logger.warning("match_vector_unavailable", error=str(exc))
        raise DependencyUnavailableError(
            "向量检索暂不可用（Embedding 或 Qdrant 未就绪），暂时算不了人岗匹配；"
            "可先用「岗位搜索」按关键词检索。"
        ) from exc
    results: list[MatchOut] = []
    for hit in hits:
        posting: JobPosting | None = await job_repo.get(hit["job_posting_id"])
        if not posting:
            continue
        required = ((posting.raw or {}).get("required_skills")) or []
        jd_text = posting.description or posting.title
        ms = score_match(profile, required, jd_text, hit["score"])

        # 缓存写入（同简历同岗位不重算）
        mr = await match_repo.get_cached(resume.id, posting.id)
        if mr is None:
            mr = await match_repo.add(MatchResult(
                resume_id=resume.id,
                job_posting_id=posting.id,
                overall_score=ms.overall,
                skill_match=ms.skill_match.model_dump(),
                skill_gaps={"missing": ms.skill_match.missing},
                experience_match=ms.experience_match.model_dump(),
            ))
        results.append(_to_match_out(posting, mr))

    results.sort(key=lambda m: m.overall_score, reverse=True)
    logger.info("matches_computed", resume_id=resume.id, n=len(results))
    return results


def _to_match_out(posting: JobPosting, mr: MatchResult) -> MatchOut:
    return MatchOut(
        job=posting,
        overall_score=mr.overall_score,
        skill_match=mr.skill_match,
        skill_gaps=mr.skill_gaps,
        experience_match=mr.experience_match,
    )
