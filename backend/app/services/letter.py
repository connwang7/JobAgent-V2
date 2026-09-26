"""求职信服务：状态机 draft → awaiting_confirm → confirmed / archived。

HITL 确认后才触发 docx 渲染（Celery generate_letter_doc）。
"""
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationError
from app.core.logging import logger
from app.core.storage import get_storage
from app.models.letter import CoverLetter
from app.repositories.letter import LetterRepository
from app.repositories.resume import ResumeRepository


async def create_from_run(session: AsyncSession, user_id: int, resume_id: int | None,
                          job_posting_id: int | None, session_id: str | None,
                          content: str, critic: dict | None) -> CoverLetter:
    """interrupt 事件发生时，由 orchestrator 调用创建待确认草稿。"""
    repo = LetterRepository(session)
    letter = await repo.add(CoverLetter(
        user_id=user_id,
        resume_id=resume_id,
        job_posting_id=job_posting_id,
        session_id=session_id,
        content=content,
        status="awaiting_confirm",
        critic_score=critic,
    ))
    await session.commit()
    logger.info("letter_created", letter_id=letter.id, status=letter.status)
    return letter


async def confirm(session: AsyncSession, repo: LetterRepository,
                  letter: CoverLetter, approved: bool) -> CoverLetter:
    if letter.status != "awaiting_confirm":
        raise ValidationError(
            f"当前状态 {letter.status} 不可确认（需为 awaiting_confirm）", code="LTR-001"
        )

    if approved:
        letter.status = "confirmed"
        # docx 渲染：优先 Celery，无 Redis 时进程内后台任务降级（不阻塞确认请求）
        from app.workers.dispatch import dispatch_or_inline
        from app.workers.tasks.render_letter import generate_letter_doc_task, run_render_letter
        await dispatch_or_inline(generate_letter_doc_task, run_render_letter, letter.id)
    else:
        letter.status = "archived"

    await session.commit()
    logger.info("letter_confirmed", letter_id=letter.id, approved=approved)
    return letter


async def get_owned(repo: LetterRepository, user_id: int, letter_id: str) -> CoverLetter:
    letter = await repo.get(letter_id)
    if not letter or letter.user_id != user_id:
        raise NotFoundError("求职信不存在", code="LTR-404")
    return letter


async def download_url(letter: CoverLetter) -> str:
    if not letter.file_key:
        raise ValidationError("求职信尚未生成文档（需先确认）", code="LTR-002")
    return get_storage().presigned_url(letter.file_key, expires=timedelta(hours=2))


async def list_by_user(repo: LetterRepository, user_id: int) -> list[CoverLetter]:
    return await repo.list_by_user(user_id)
