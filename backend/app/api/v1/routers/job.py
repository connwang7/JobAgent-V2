from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_session
from app.core.errors import NotFoundError
from app.models.user import User
from app.repositories.job import JobRepository, MatchRepository
from app.repositories.resume import ResumeRepository
from app.schemas.common import ok
from app.schemas.job import JobOut
from app.services import job as job_service

router = APIRouter(prefix="/jobs", tags=["job"])


@router.get("/search")
async def search_jobs(keyword: str = "", company: str = "", location: str = "",
                      limit: int = Query(20, le=100), offset: int = 0,
                      user: User = Depends(get_current_user),
                      db: AsyncSession = Depends(get_session)):
    rows = await job_service.search_jobs(
        JobRepository(db), keyword, company, location, limit, offset
    )
    return ok([JobOut.model_validate(r).model_dump() for r in rows])


@router.get("/matches")
async def job_matches(resume_id: int | None = None, top_k: int = Query(20, le=50),
                      force: bool = False,
                      user: User = Depends(get_current_user),
                      db: AsyncSession = Depends(get_session)):
    """RAG 匹配结果（可解释：技能覆盖/差距/经验匹配）。"""
    resume_repo = ResumeRepository(db)
    resume = (
        await resume_repo.get(resume_id) if resume_id
        else await resume_repo.latest_by_user(user.id)
    )
    if not resume or resume.user_id != user.id:
        raise NotFoundError("简历不存在", code="RES-404")

    matches = await job_service.get_matches(
        db, MatchRepository(db), JobRepository(db), resume, top_k=top_k, force=force
    )
    return ok([m.model_dump() for m in matches])
