"""会话、消息与执行轨迹表。"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, JsonType, LongText, TimestampMixin, _utcnow


def _uuid() -> str:
    return uuid.uuid4().hex


class Session(Base, TimestampMixin):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255), default="新会话")
    resume_id: Mapped[int | None] = mapped_column(
        ForeignKey("resumes.id", ondelete="SET NULL"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    # user / assistant / tool
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    agent_name: Mapped[str] = mapped_column(String(64), default="")
    content: Mapped[str] = mapped_column(LongText, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    # 生成物引用：岗位 id 列表、求职信 id 等
    refs: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    thread_id: Mapped[str] = mapped_column(String(64), index=True)  # LangGraph thread
    plan: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    # running / awaiting_human / done / error / archived
    status: Mapped[str] = mapped_column(String(32), default="running", index=True)
    error: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AgentEvent(Base):
    __tablename__ = "agent_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True
    )
    seq: Mapped[int] = mapped_column(Integer, default=0)  # run 内单调递增
    node_name: Mapped[str] = mapped_column(String(64), default="")
    # plan/agent_start/tool_call/tool_result/critic/interrupt/token/final
    event_type: Mapped[str] = mapped_column(String(32), index=True)
    payload: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
