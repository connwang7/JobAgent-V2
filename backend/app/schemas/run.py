from datetime import datetime

from pydantic import BaseModel


class LetterOut(BaseModel):
    id: str
    resume_id: int | None
    job_posting_id: int | None
    session_id: str | None
    content: str
    version: int
    critic_score: dict | None = None
    status: str
    file_key: str = ""
    created_at: datetime

    model_config = {"from_attributes": True}


class TraceEventOut(BaseModel):
    seq: int
    node_name: str
    event_type: str
    payload: dict | None = None
    latency_ms: int
    created_at: datetime

    model_config = {"from_attributes": True}


class RunOut(BaseModel):
    id: str
    session_id: str
    status: str
    plan: dict | None = None
    error: str = ""
    started_at: datetime
    finished_at: datetime | None = None

    model_config = {"from_attributes": True}


class ApproveRequest(BaseModel):
    approved: bool = True
    comment: str = ""
