from sqlalchemy import func, select

from app.models.chat import AgentEvent, AgentRun, Message, Session
from app.repositories.base import BaseRepository


class SessionRepository(BaseRepository[Session]):
    model = Session

    async def list_by_user(self, user_id: int) -> list[Session]:
        result = await self.session.execute(
            select(Session)
            .where(Session.user_id == user_id)
            .order_by(Session.updated_at.desc())
        )
        return list(result.scalars().all())


class MessageRepository(BaseRepository[Message]):
    model = Message

    async def list_by_session(self, session_id: str) -> list[Message]:
        result = await self.session.execute(
            select(Message).where(Message.session_id == session_id).order_by(Message.id)
        )
        return list(result.scalars().all())


class RunRepository(BaseRepository[AgentRun]):
    model = AgentRun

    async def get_by_thread(self, thread_id: str) -> AgentRun | None:
        result = await self.session.execute(
            select(AgentRun)
            .where(AgentRun.thread_id == thread_id)
            .order_by(AgentRun.started_at.desc())
        )
        return result.scalars().first()


class EventRepository(BaseRepository[AgentEvent]):
    model = AgentEvent

    async def list_by_run(self, run_id: str) -> list[AgentEvent]:
        result = await self.session.execute(
            select(AgentEvent).where(AgentEvent.run_id == run_id).order_by(AgentEvent.seq)
        )
        return list(result.scalars().all())

    async def next_seq(self, run_id: str) -> int:
        result = await self.session.execute(
            select(func.max(AgentEvent.seq)).where(AgentEvent.run_id == run_id)
        )
        max_seq = result.scalar_one()
        return (max_seq or 0) + 1
