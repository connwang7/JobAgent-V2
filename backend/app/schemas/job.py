from datetime import datetime

from pydantic import BaseModel


class JobOut(BaseModel):
    id: int
    title: str
    company: str
    location: str
    employment_type: str
    salary_text: str
    url: str
    posted_at: datetime | None = None
    fetched_at: datetime | None = None

    model_config = {"from_attributes": True}


class MatchOut(BaseModel):
    job: JobOut
    overall_score: float
    skill_match: dict | None = None
    skill_gaps: dict | None = None
    experience_match: dict | None = None


class JobSearchQuery(BaseModel):
    keyword: str = ""
    company: str = ""
    location: str = ""
    limit: int = 20
    offset: int = 0
