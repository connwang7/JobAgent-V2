from pydantic import BaseModel


class PreferenceUpdate(BaseModel):
    city: str = ""
    industry: str = ""
    salary_range: str = ""
    work_type: str = ""
    raw: dict | None = None


class PreferenceOut(BaseModel):
    city: str = ""
    industry: str = ""
    salary_range: str = ""
    work_type: str = ""
    raw: dict | None = None
