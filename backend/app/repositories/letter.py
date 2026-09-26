from sqlalchemy import select

from app.models.letter import CoverLetter, UserMemory
from app.repositories.base import BaseRepository


class LetterRepository(BaseRepository[CoverLetter]):
    model = CoverLetter

    async def list_by_user(self, user_id: int) -> list[CoverLetter]:
        result = await self.session.execute(
            select(CoverLetter)
            .where(CoverLetter.user_id == user_id)
            .order_by(CoverLetter.created_at.desc())
        )
        return list(result.scalars().all())


class MemoryRepository(BaseRepository[UserMemory]):
    model = UserMemory

    async def list_by_user(self, user_id: int, memory_type: str | None = None) -> list[UserMemory]:
        stmt = select(UserMemory).where(UserMemory.user_id == user_id)
        if memory_type:
            stmt = stmt.where(UserMemory.memory_type == memory_type)
        result = await self.session.execute(stmt.order_by(UserMemory.id.desc()))
        return list(result.scalars().all())
