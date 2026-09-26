"""generate_letter_doc：求职信确认后 docx 渲染 + 上传对象存储。"""
from app.core.logging import logger
from app.workers.celery_app import celery_app


@celery_app.task(name="generate_letter_doc", bind=True, max_retries=3)
def generate_letter_doc_task(self, letter_id: str) -> dict:
    import asyncio
    return asyncio.run(run_render_letter(letter_id))


async def run_render_letter(letter_id: str) -> dict:
    """实现与 Celery 解耦，便于无 Redis 时进程内降级调用。"""
    from app.agents.tools.render_docx import render_docx
    from app.core.db import AsyncSessionLocal
    from app.models.letter import CoverLetter
    from app.repositories.letter import LetterRepository

    async with AsyncSessionLocal() as db:
        repo = LetterRepository(db)
        letter: CoverLetter | None = await repo.get(letter_id)
        if not letter:
            return {"ok": False, "error": "letter not found"}
        if letter.status != "confirmed":
            return {"ok": False, "error": f"status={letter.status}，仅确认后渲染"}

        result = await render_docx.arun({
            "content": letter.content, "user_id": letter.user_id, "letter_id": letter.id,
        })
        if not result.ok:
            raise RuntimeError(result.error)

        letter.file_key = result.data["file_key"]
        await db.commit()
        logger.info("letter_doc_generated", letter_id=letter.id)
        return {"ok": True, "file_key": letter.file_key}
