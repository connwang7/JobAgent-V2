"""简历服务：上传校验（PDF magic number / 10MB 上限）、对象存储、解析任务分发、删除。"""
import asyncio

import pymupdf

from app.core.errors import NotFoundError, ValidationError
from app.core.logging import logger
from app.core.storage import get_storage, new_object_key
from app.models.resume import Resume
from app.models.user import User
from app.repositories.job import MatchRepository
from app.repositories.resume import ResumeRepository

MAX_SIZE = 10 * 1024 * 1024
PDF_MAGIC = b"%PDF-"


def human_size(size: int) -> str:
    """给时间线看的人类可读体积，避免前端再写一遍格式化。"""
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.0f} KB"
    return f"{size / 1024 / 1024:.1f} MB"


async def upload(repo: ResumeRepository, user: User, filename: str,
                 data: bytes) -> Resume:
    # 上传校验（方案 4.3）：magic number + 大小上限；文件名不落盘，用对象存储 key
    if not data.startswith(PDF_MAGIC):
        raise ValidationError("仅支持 PDF 格式文件", code="RES-001")
    if len(data) > MAX_SIZE:
        raise ValidationError("文件超过 10MB 上限", code="RES-002")

    file_key = new_object_key(f"resumes/{user.id}", "pdf")
    get_storage().put(file_key, data, content_type="application/pdf")

    # 版本化：每用户保留多版本
    existing = await repo.list_by_user(user.id)
    version = (existing[0].version + 1) if existing else 1

    resume = await repo.add(Resume(
        user_id=user.id,
        file_key=file_key,
        filename=filename[-255:],  # 原文件名仅作展示
        file_size=len(data),
        version=version,
        status="pending",
    ))
    await repo.add_event(
        resume.id, user.id, "uploaded",
        f"v{version} · {resume.filename} · {human_size(len(data))}",
    )
    # 必须先提交再派发：解析任务另开 session 读这一行，而 inline 降级是
    # `loop.create_task` —— 它和请求结束时的 commit 是竞态的，跑前面就会读到
    # "这行还不存在" → 直接 return，状态永远停在 pending、时间线里也没有解析事件。
    # （expire_on_commit=False，提交后 resume 的属性仍可直接读取，响应组装不受影响。）
    await repo.session.commit()

    # 简历解析：优先 Celery，Redis/worker 不可用时进程内后台任务降级（不阻塞上传请求）
    from app.workers.dispatch import dispatch_or_inline
    from app.workers.tasks.parse_resume import parse_resume_task, run_parse_resume
    mode = await dispatch_or_inline(
        parse_resume_task, run_parse_resume, resume.id, parse_mode="inline"
    )
    logger.info("resume_uploaded", resume_id=resume.id, version=version, parse_mode=mode)
    return resume


async def reparse(repo: ResumeRepository, user: User, resume_id: int) -> Resume:
    """重新触发解析（上传时大模型未配置 / 任务被中断后的补救入口）。"""
    resume = await get_profile(repo, user, resume_id)
    resume.status = "pending"
    resume.error = ""
    await repo.add_event(resume.id, user.id, "reparse_requested", f"v{resume.version}")
    await repo.session.commit()

    from app.workers.dispatch import dispatch_or_inline
    from app.workers.tasks.parse_resume import parse_resume_task, run_parse_resume
    mode = await dispatch_or_inline(
        parse_resume_task, run_parse_resume, resume.id, parse_mode="inline"
    )
    logger.info("resume_reparse_dispatched", resume_id=resume.id, parse_mode=mode)
    return resume


async def delete_resume(repo: ResumeRepository, user: User, resume_id: int) -> dict:
    """删除单个版本：对象存储 → 事件 → 主记录。

    顺序是刻意的：先删存储再删库。若存储删除失败，记录照样删掉 ——
    否则用户会陷入"删不掉"的死角（对象已损坏/权限异常时永远删不干净），
    而残留的孤儿对象不影响任何功能，只是占一点空间。
    """
    resume = await get_profile(repo, user, resume_id)
    version, file_key = resume.version, resume.file_key

    object_deleted = False
    if file_key:
        # LocalStorage.delete 是同步文件 IO，放线程里，别卡事件循环
        object_deleted = await asyncio.to_thread(get_storage().delete, file_key)

    await repo.delete_events(resume.id)
    await repo.delete(resume)
    await repo.session.commit()
    logger.info("resume_deleted", resume_id=resume_id, version=version,
                object_deleted=object_deleted)
    return {"id": resume_id, "version": version, "object_deleted": object_deleted}


async def clear_resumes(repo: ResumeRepository, user: User) -> dict:
    """一键清空当前用户的全部简历版本（含对象存储与时间线）。"""
    rows = await repo.list_by_user(user.id)
    if not rows:
        return {"deleted": 0, "objects_deleted": 0}

    objects = 0
    for r in rows:
        if r.file_key:
            if await asyncio.to_thread(get_storage().delete, r.file_key):
                objects += 1

    deleted = await repo.delete_all_by_user(user.id)
    await repo.session.commit()
    logger.info("resumes_cleared", user_id=user.id, deleted=deleted, objects_deleted=objects)
    return {"deleted": deleted, "objects_deleted": objects}


async def get_profile(repo: ResumeRepository, user: User, resume_id: int) -> Resume:
    resume = await repo.get(resume_id)
    if not resume or resume.user_id != user.id:
        raise NotFoundError("简历不存在", code="RES-404")
    return resume


async def invalidate_matches(session, resume_id: int) -> None:
    """简历换版本 → 匹配缓存失效（方案 7.3）。"""
    repo = MatchRepository(session)
    await repo.invalidate_by_resume(resume_id)


def extract_pdf_text(data: bytes) -> str:
    with pymupdf.open(stream=data, filetype="pdf") as pdf:
        return "\n".join(page.get_text() for page in pdf).strip()
