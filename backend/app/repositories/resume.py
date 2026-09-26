from sqlalchemy import delete as sa_delete, select

from app.models.resume import Resume, ResumeEvent
from app.repositories.base import BaseRepository


class ResumeRepository(BaseRepository[Resume]):
    model = Resume

    async def list_by_user(self, user_id: int) -> list[Resume]:
        result = await self.session.execute(
            select(Resume)
            .where(Resume.user_id == user_id)
            .order_by(Resume.version.desc(), Resume.id.desc())
        )
        return list(result.scalars().all())

    async def latest_by_user(self, user_id: int) -> Resume | None:
        resumes = await self.list_by_user(user_id)
        return resumes[0] if resumes else None

    async def list_events(self, resume_id: int) -> list[ResumeEvent]:
        result = await self.session.execute(
            select(ResumeEvent)
            .where(ResumeEvent.resume_id == resume_id)
            .order_by(ResumeEvent.id.asc())
        )
        return list(result.scalars().all())

    async def add_event(self, resume_id: int, user_id: int, event: str,
                        detail: str = "") -> ResumeEvent:
        ev = ResumeEvent(resume_id=resume_id, user_id=user_id, event=event, detail=detail)
        self.session.add(ev)
        await self.session.flush()
        return ev

    async def delete_events(self, resume_id: int) -> None:
        await self.session.execute(
            sa_delete(ResumeEvent).where(ResumeEvent.resume_id == resume_id)
        )

    async def delete_all_by_user(self, user_id: int) -> int:
        """按用户清空简历。时间线一并显式删除；`match_results` 靠 DB 级
        `ON DELETE CASCADE` 级联，`sessions.resume_id` / `cover_letters.resume_id`
        是 `SET NULL`（保留会话与求职信，只断开引用）。"""
        await self.session.execute(
            sa_delete(ResumeEvent).where(ResumeEvent.user_id == user_id)
        )
        result = await self.session.execute(
            sa_delete(Resume).where(Resume.user_id == user_id)
        )
        return result.rowcount or 0
