"""简历表（版本化，profile 为结构化画像 JSON）。"""
from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, JsonType, LongText, TimestampMixin


class Resume(Base, TimestampMixin):
    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    file_key: Mapped[str] = mapped_column(String(512), default="")  # S3/MinIO 对象 key
    filename: Mapped[str] = mapped_column(String(255), default="")
    file_size: Mapped[int] = mapped_column(BigInteger, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)
    parsed_text: Mapped[str | None] = mapped_column(LongText, nullable=True)
    # 结构化画像 {basic, education[], experience[], skills[], highlights[]}
    profile: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    # pending / parsing / ready / failed
    status: Mapped[str] = mapped_column(String(32), default="pending")
    error: Mapped[str] = mapped_column(Text, default="")


class ResumeEvent(Base, TimestampMixin):
    """简历版本的操作时间线。

    为什么单独一张表而不是在 resumes 上加 started_at / finished_at：
    一次简历可以「重新解析」多次，字段只能记最后一次，无法回放历史；
    而且事件是纯追加的，前端展开即读，改动面最小。

    event 取值：
      uploaded          上传成功（附带文件名 / 版本 / 大小）
      reparse_requested 用户点了「重新解析」
      parse_started     解析任务开始（附解析模式 celery / inline）
      parse_succeeded   解析成功（附带技能数 / 经历年数 / 耗时）
      parse_failed      解析失败（附带错误原文）
    """
    __tablename__ = "resume_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    resume_id: Mapped[int] = mapped_column(
        ForeignKey("resumes.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    event: Mapped[str] = mapped_column(String(32))
    detail: Mapped[str] = mapped_column(Text, default="")
