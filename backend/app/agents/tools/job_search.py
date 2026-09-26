"""job_search：Serper 检索 + 结果先落库 job_postings 再返回（修复 v1 直接丢弃的问题）。"""
from datetime import datetime
from typing import ClassVar

import httpx
from pydantic import BaseModel, Field
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.agents.tools.adapters import BaseToolAdapter
from app.core.config import settings
from app.core.user_context import get_tool_key
from app.core.db import AsyncSessionLocal


class JobSearchToolInput(BaseModel):
    """严格校验入参（v1 中这些参数实际未生效、全部拼进 query 的问题在此修复）。"""
    keywords: str = Field(min_length=1, max_length=128)
    location: str = Field(default="", max_length=64)
    employment_type: str = Field(default="", max_length=32)
    remote: bool = False
    limit: int = Field(default=10, ge=1, le=20)


def _parse_company(title: str) -> str:
    """从 'Senior X Engineer at Acme' 类标题提取公司名。"""
    for sep in (" at ", " - ", " | ", " – "):
        if sep in title:
            return title.split(sep)[-1].strip()
    return ""


class JobSearchAdapter(BaseToolAdapter):
    name: ClassVar[str] = "job_search"
    input_schema: ClassVar[type[JobSearchToolInput]] = JobSearchToolInput
    cache_ttl: ClassVar[int | None] = 3600  # 1h

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.TransportError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    async def _fetch(self, query: str, num_results: int) -> list[dict]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": get_tool_key("serper") or settings.serper_api_key},
                json={"q": query, "num": num_results},
            )
            resp.raise_for_status()
            return resp.json().get("organic", [])

    async def _arun(self, payload: JobSearchToolInput) -> list[dict]:
        # 组装查询（与 v1 兼容，但参数经过校验、结构化）
        query = f"招聘 {payload.keywords}"
        if payload.location:
            query += f" {payload.location}"
        if payload.employment_type:
            query += f" {payload.employment_type}"
        if payload.remote:
            query += " 远程"

        items = await self._fetch(query, payload.limit)
        now = datetime.utcnow()

        # —— 先落库再返回：按 url 去重，同一岗位多次抓取只更新 ——
        saved: list[dict] = []
        async with AsyncSessionLocal() as db:
            from app.models.job import JobPosting
            from app.repositories.job import JobRepository

            repo = JobRepository(db)
            for it in items:
                url = it.get("link", "")
                if not url:
                    continue
                title = it.get("title", "")
                posting = await repo.get_by_url(url)
                if posting is None:
                    posting = JobPosting(
                        source="serper",
                        title=title,
                        company=_parse_company(title),
                        location=payload.location,
                        employment_type=payload.employment_type,
                        description=it.get("snippet", ""),
                        url=url,
                        posted_at=None,
                        raw={"search_query": query, "date": it.get("date", "")},
                        fetched_at=now,
                    )
                    db.add(posting)
                else:
                    posting.fetched_at = now
                    posting.title = title or posting.title
                await db.flush()
                saved.append(
                    {
                        "job_posting_id": posting.id,
                        "title": posting.title,
                        "company": posting.company,
                        "location": posting.location,
                        "salary_text": posting.salary_text,
                        "snippet": it.get("snippet", ""),
                        "url": url,
                        "date": it.get("date", ""),
                    }
                )
            await db.commit()

        return saved


job_search = JobSearchAdapter()
