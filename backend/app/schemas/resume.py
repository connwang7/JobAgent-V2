from datetime import datetime

from pydantic import BaseModel


class ResumeOut(BaseModel):
    id: int
    filename: str
    file_size: int
    version: int
    status: str
    error: str = ""
    created_at: datetime

    model_config = {"from_attributes": True}


class ResumeProfileOut(BaseModel):
    resume_id: int
    status: str
    profile: dict | None = None


class ResumeEventOut(BaseModel):
    """简历操作时间线的一行（前端按 created_at 升序渲染）。"""
    id: int
    event: str          # uploaded / reparse_requested / parse_started / ...
    detail: str = ""
    created_at: datetime

    model_config = {"from_attributes": True}
