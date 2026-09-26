from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_session
from app.core.errors import AuthError
from app.core.logging import logger
from app.core.security import hash_password, verify_password
from app.models.chat import Session as ChatSession
from app.models.letter import CoverLetter, UserMemory
from app.models.resume import Resume
from app.models.user import User, UserPreference
from app.repositories.user import PreferenceRepository
from app.schemas.common import ok
from app.schemas.preference import PreferenceOut, PreferenceUpdate
from app.schemas.profile import PasswordChange, ProfileOut, ProfileStats, ProfileUpdate
from app.services.memory import remember

router = APIRouter(prefix="/me", tags=["me"])


async def _count(db: AsyncSession, stmt) -> int:
    result = await db.execute(stmt)
    return int(result.scalar() or 0)


@router.get("/profile")
async def get_profile(user: User = Depends(get_current_user),
                      db: AsyncSession = Depends(get_session)):
    """账号信息 + 概览计数（设置页用）。"""
    stats = ProfileStats(
        sessions=await _count(db, select(func.count()).select_from(ChatSession)
                              .where(ChatSession.user_id == user.id)),
        resumes=await _count(db, select(func.count()).select_from(Resume)
                             .where(Resume.user_id == user.id)),
        letters=await _count(db, select(func.count()).select_from(CoverLetter)
                             .where(CoverLetter.user_id == user.id)),
        memories=await _count(db, select(func.count()).select_from(UserMemory)
                              .where(UserMemory.user_id == user.id)),
    )
    return ok(ProfileOut(
        id=user.id,
        email=user.email,
        nickname=user.nickname or "",
        is_active=bool(user.is_active),
        # 注意：库里是 naive UTC，前端统一按 UTC 解析（见 frontend/lib/format.ts）
        created_at=user.created_at.isoformat() if user.created_at else "",
        stats=stats,
    ).model_dump())


@router.put("/profile")
async def update_profile(req: ProfileUpdate,
                         user: User = Depends(get_current_user),
                         db: AsyncSession = Depends(get_session)):
    user.nickname = (req.nickname or "").strip()[:64]
    await db.commit()
    return ok({"nickname": user.nickname})


@router.post("/password")
async def change_password(req: PasswordChange,
                          user: User = Depends(get_current_user),
                          db: AsyncSession = Depends(get_session)):
    """改密码：校验旧密码；新密码强度由 schema 限制（≥8 位）。"""
    if not verify_password(req.old_password, user.password_hash):
        raise AuthError("原密码不正确", code="AUTH-010")
    if req.old_password == req.new_password:
        raise AuthError("新密码不能与原密码相同", code="AUTH-011")

    user.password_hash = hash_password(req.new_password)
    await db.commit()
    logger.info("password_changed", user_id=user.id)
    return ok()


@router.get("/preferences")
async def get_preferences(user: User = Depends(get_current_user),
                          db: AsyncSession = Depends(get_session)):
    prefs = await PreferenceRepository(db).get_by_user(user.id)
    return ok(PreferenceOut(
        city=prefs.city if prefs else "", industry=prefs.industry if prefs else "",
        salary_range=prefs.salary_range if prefs else "", work_type=prefs.work_type if prefs else "",
        raw=prefs.raw if prefs else None,
    ).model_dump())


@router.put("/preferences")
async def update_preferences(req: PreferenceUpdate,
                             user: User = Depends(get_current_user),
                             db: AsyncSession = Depends(get_session)):
    """偏好变更沉淀为长期记忆（方案 6.9 写入时机）。"""
    repo = PreferenceRepository(db)
    prefs = await repo.get_by_user(user.id)
    if prefs is None:
        prefs = await repo.add(UserPreference(user_id=user.id))
    prefs.city = req.city
    prefs.industry = req.industry
    prefs.salary_range = req.salary_range
    prefs.work_type = req.work_type
    prefs.raw = req.raw
    await db.commit()

    # 偏好变更沉淀为长期记忆（方案 6.9）：
    # 记忆向量化依赖 embedding 服务，失败不影响偏好本身落库
    if any([req.city, req.industry, req.salary_range, req.work_type]):
        try:
            await remember(
                user.id,
                content=f"求职偏好：城市={req.city}；行业={req.industry}；薪资={req.salary_range}；工作方式={req.work_type}",
                memory_type="preference",
            )
        except Exception as exc:
            logger.warning("preference_memory_skipped", user_id=user.id, error=str(exc))
    return ok()
