"""parse_resume：PDF 解析 + LLM 结构化画像抽取（简历上传触发）。"""
import time

from app.core.logging import logger
from app.workers.celery_app import celery_app


@celery_app.task(name="parse_resume", bind=True, max_retries=2)
def parse_resume_task(self, resume_id: int) -> dict:
    import asyncio
    return asyncio.run(run_parse_resume(resume_id))


async def run_parse_resume(resume_id: int, parse_mode: str = "celery") -> dict:
    """实现与 Celery 解耦，便于无 Redis 时进程内降级调用。

    `parse_mode` 只是给操作时间线看的一行说明（celery=worker 消费 / inline=进程内降级）。
    Celery 走 `.delay(resume_id)` 传不进 kwargs，所以默认值就写 "celery"；
    降级路径由 `dispatch_or_inline` 显式传 `parse_mode="inline"`。
    """
    from app.agents.graph.state import ResumeProfile
    from app.core.db import AsyncSessionLocal
    from app.core.storage import get_storage
    from app.models.resume import Resume
    from app.repositories.job import MatchRepository
    from app.repositories.resume import ResumeRepository

    started = time.monotonic()

    async with AsyncSessionLocal() as db:
        repo = ResumeRepository(db)
        resume: Resume | None = await repo.get(resume_id)
        if not resume:
            return {"ok": False, "error": "resume not found"}
        resume.status = "parsing"
        await repo.add_event(resume.id, resume.user_id, "parse_started",
                             f"解析模式 {parse_mode}")
        await db.commit()

        try:
            # 1) PDF 文本抽取（对象存储读取）
            data = get_storage().get(resume.file_key)
            from app.services.resume import extract_pdf_text
            resume.parsed_text = extract_pdf_text(data)

            # 2) LLM 结构化画像
            from app.agents.graph.events import role_llm
            from langchain_core.messages import HumanMessage, SystemMessage
            from app.agents.prompts.resume_analyzer import RESUME_ANALYZER_SYSTEM
            from app.models.user import User
            from app.repositories.user import UserRepository

            user = await UserRepository(db).get(resume.user_id)
            context = {
                "llm_pref": (user.llm_model_pref if user else None) or {},
                "llm_api_key_enc": (user.llm_api_key_enc if user else "") or "",
                "llm_base_url": (user.llm_base_url if user else "") or "",
            }
            llm = role_llm("worker", context)
            profile: ResumeProfile = await llm.with_structured_output(ResumeProfile).ainvoke([
                SystemMessage(content=RESUME_ANALYZER_SYSTEM),
                HumanMessage(content=f"简历全文：\n{resume.parsed_text[:12000]}"),
            ])
            resume.profile = profile.model_dump()
            resume.status = "ready"
            resume.error = ""

            # 3) 简历换版本 → 匹配缓存失效
            await MatchRepository(db).invalidate_by_resume(resume.id)

            elapsed = time.monotonic() - started
            await repo.add_event(
                resume.id, resume.user_id, "parse_succeeded",
                f"技能 {len(profile.skills)} 项 · 经历 {profile.experience_years:g} 年"
                f" · 耗时 {elapsed:.1f} 秒",
            )
            await db.commit()
            logger.info("resume_parsed", resume_id=resume.id,
                        skills=len(profile.skills), elapsed=round(elapsed, 2))
            return {"ok": True}
        except Exception as exc:
            elapsed = time.monotonic() - started
            # rollback 会把这一轮解析的全部改动丢掉（含可能已写入的 parsed_text），
            # 所以之后要重新取一行再落 failed，避免在已过期对象上写属性。
            await db.rollback()
            fresh = await repo.get(resume_id)
            if fresh is not None:
                fresh.status = "failed"
                fresh.error = str(exc)[:500]
                await repo.add_event(
                    fresh.id, fresh.user_id, "parse_failed",
                    f"{type(exc).__name__}: {str(exc)[:300]}（耗时 {elapsed:.1f} 秒）",
                )
                await db.commit()
            logger.error("resume_parse_failed", resume_id=resume_id,
                         mode=parse_mode, error=str(exc)[:300])
            raise
