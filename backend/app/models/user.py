"""用户与偏好表。"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, JsonType, TimestampMixin, _utcnow


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    nickname: Mapped[str] = mapped_column(String(64), default="")
    # 用户级 LLM 配置：AES-GCM 加密存储，解密只在调用 LLM 的内存中发生
    llm_api_key_enc: Mapped[str] = mapped_column(Text, default="")
    llm_base_url: Mapped[str] = mapped_column(String(512), default="")
    # 角色→模型 覆盖映射，如 {"planner": "qwen-plus", "writer": "deepseek-reasoner"}
    llm_model_pref: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    # 用户级工具服务密钥（AES-GCM 加密；留空则回落到全局 settings）
    serper_api_key_enc: Mapped[str] = mapped_column(Text, default="")
    firecrawl_api_key_enc: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class UserPreference(Base):
    __tablename__ = "user_preferences"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    city: Mapped[str] = mapped_column(String(64), default="")
    industry: Mapped[str] = mapped_column(String(64), default="")
    salary_range: Mapped[str] = mapped_column(String(64), default="")
    work_type: Mapped[str] = mapped_column(String(32), default="")  # 全职/兼职/远程...
    raw: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )
