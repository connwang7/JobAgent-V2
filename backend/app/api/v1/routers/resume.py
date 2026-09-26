from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_session
from app.models.user import User
from app.repositories.resume import ResumeRepository
from app.schemas.common import ok
from app.schemas.resume import ResumeEventOut, ResumeOut
from app.services import resume as resume_service

router = APIRouter(prefix="/resumes", tags=["resume"])


@router.post("", status_code=201)
async def upload_resume(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """multipart 上传：PDF magic 校验 + 10MB 上限；解析走 Celery 异步。"""
    data = await file.read()
    resume = await resume_service.upload(
        ResumeRepository(db), user, file.filename or "resume.pdf", data
    )
    await db.commit()
    return ok(ResumeOut.model_validate(resume).model_dump())


@router.get("")
async def list_resumes(user: User = Depends(get_current_user),
                       db: AsyncSession = Depends(get_session)):
    rows = await ResumeRepository(db).list_by_user(user.id)
    return ok([ResumeOut.model_validate(r).model_dump() for r in rows])


@router.delete("")
async def clear_resumes(user: User = Depends(get_current_user),
                        db: AsyncSession = Depends(get_session)):
    """一键清空：删除当前用户的全部简历版本（含对象存储与操作时间线）。

    不可恢复，前端需二次确认。会话/求职信上的 resume_id 会置空而不是被删。
    """
    return ok(await resume_service.clear_resumes(ResumeRepository(db), user))


@router.post("/{resume_id}/reparse")
async def reparse_resume(resume_id: int,
                         user: User = Depends(get_current_user),
                         db: AsyncSession = Depends(get_session)):
    """重新触发解析。

    典型场景：首次上传时还没配大模型 API Key（状态会是 failed 并带原因），
    配好后不用重传文件，点这里即可。
    """
    resume = await resume_service.reparse(ResumeRepository(db), user, resume_id)
    return ok(ResumeOut.model_validate(resume).model_dump())


@router.delete("/{resume_id}")
async def delete_resume(resume_id: int,
                        user: User = Depends(get_current_user),
                        db: AsyncSession = Depends(get_session)):
    """删除单个版本（对象存储 + 时间线 + 主记录）。"""
    return ok(await resume_service.delete_resume(ResumeRepository(db), user, resume_id))


@router.get("/{resume_id}/events")
async def list_resume_events(resume_id: int,
                             user: User = Depends(get_current_user),
                             db: AsyncSession = Depends(get_session)):
    """版本操作时间线：上传 → 重新解析 → 解析开始 → 成功/失败（含耗时与失败原因）。"""
    repo = ResumeRepository(db)
    resume = await resume_service.get_profile(repo, user, resume_id)  # 顺便做归属校验
    rows = await repo.list_events(resume.id)
    return ok({
        "resume_id": resume.id,
        "version": resume.version,
        "status": resume.status,
        "events": [ResumeEventOut.model_validate(e).model_dump() for e in rows],
    })


@router.get("/{resume_id}/profile")
async def get_profile(resume_id: int, user: User = Depends(get_current_user),
                      db: AsyncSession = Depends(get_session)):
    resume = await resume_service.get_profile(ResumeRepository(db), user, resume_id)
    return ok({
        "resume_id": resume.id,
        "status": resume.status,
        "profile": resume.profile,
        "raw_analysis": (resume.profile or {}).get("raw_analysis", ""),
    })
