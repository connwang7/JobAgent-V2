"""当前用户资料相关出入参。"""
from pydantic import BaseModel, Field, field_validator


class ProfileUpdate(BaseModel):
    nickname: str = Field(default="", max_length=64)

    @field_validator("nickname")
    @classmethod
    def _strip(cls, v: str) -> str:
        return (v or "").strip()


class PasswordChange(BaseModel):
    old_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)


class ProfileStats(BaseModel):
    """设置页账号卡片的概览计数。"""

    sessions: int = 0
    resumes: int = 0
    letters: int = 0
    memories: int = 0


class ProfileOut(BaseModel):
    id: int
    email: str
    nickname: str
    is_active: bool
    created_at: str
    stats: ProfileStats
