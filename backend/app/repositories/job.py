from sqlalchemy import func, or_, select

from app.models.job import JobPosting, MatchResult
from app.repositories.base import BaseRepository


class JobRepository(BaseRepository[JobPosting]):
    model = JobPosting

    async def get_by_url(self, url: str) -> JobPosting | None:
        result = await self.session.execute(select(JobPosting).where(JobPosting.url == url))
        return result.scalar_one_or_none()

    async def search(
        self, keyword: str = "", company: str = "", location: str = "",
        limit: int = 20, offset: int = 0,
    ) -> list[JobPosting]:
        stmt = select(JobPosting)
        if keyword:
            like = f"%{keyword}%"
            stmt = stmt.where(
                or_(JobPosting.title.like(like), JobPosting.description.like(like))
            )
        if company:
            stmt = stmt.where(JobPosting.company.like(f"%{company}%"))
        if location:
            stmt = stmt.where(JobPosting.location.like(f"%{location}%"))
        stmt = stmt.order_by(JobPosting.fetched_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def recent(self, limit: int = 50) -> list[JobPosting]:
        result = await self.session.execute(
            select(JobPosting).order_by(JobPosting.fetched_at.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def count_since(self, fetched_at) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(JobPosting).where(JobPosting.fetched_at >= fetched_at)
        )
        return result.scalar_one()


class MatchRepository(BaseRepository[MatchResult]):
    model = MatchResult

    async def get_cached(self, resume_id: int, job_posting_id: int) -> MatchResult | None:
        result = await self.session.execute(
            select(MatchResult).where(
                MatchResult.resume_id == resume_id,
                MatchResult.job_posting_id == job_posting_id,
            )
        )
        return result.scalar_one_or_none()

    async def top_by_resume(self, resume_id: int, limit: int = 20) -> list[MatchResult]:
        """匹配榜（方案 5.3 关键索引）。"""
        result = await self.session.execute(
            select(MatchResult)
            .where(MatchResult.resume_id == resume_id)
            .order_by(MatchResult.overall_score.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def invalidate_by_resume(self, resume_id: int) -> None:
        result = await self.session.execute(
            select(MatchResult).where(MatchResult.resume_id == resume_id)
        )
        for mr in result.scalars().all():
            await self.session.delete(mr)
