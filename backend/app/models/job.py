"""岗位与匹配结果表。"""
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, JsonType, LongText, TimestampMixin


class JobPosting(Base, TimestampMixin):
    __tablename__ = "job_postings"
    __table_args__ = (
        UniqueConstraint("url", name="uq_job_postings_url"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # serper / manual / api
    source: Mapped[str] = mapped_column(String(32), default="serper")
    external_id: Mapped[str] = mapped_column(String(128), default="")
    title: Mapped[str] = mapped_column(String(255), default="", index=True)
    company: Mapped[str] = mapped_column(String(255), default="", index=True)
    location: Mapped[str] = mapped_column(String(128), default="")
    employment_type: Mapped[str] = mapped_column(String(32), default="")
    salary_text: Mapped[str] = mapped_column(String(128), default="")
    description: Mapped[str | None] = mapped_column(LongText, nullable=True)
    url: Mapped[str] = mapped_column(String(768), index=True, nullable=False)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    raw: Mapped[dict | None] = mapped_column(JsonType, nullable=True)  # 含 LLM 抽取的 required_skills
    embedding_id: Mapped[str] = mapped_column(String(128), default="")  # Qdrant point id
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=True
    )


class MatchResult(Base, TimestampMixin):
    __tablename__ = "match_results"
    __table_args__ = (
        UniqueConstraint("resume_id", "job_posting_id", name="uq_match_resume_job"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id", ondelete="CASCADE"), index=True)
    job_posting_id: Mapped[int] = mapped_column(
        ForeignKey("job_postings.id", ondelete="CASCADE")
    )
    overall_score: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    # {covered: [...], missing: [...], score: 0-1}
    skill_match: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    skill_gaps: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    experience_match: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
