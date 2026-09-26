"""scrape_website：FireCrawl 为主，正文截断 10k，TTL 24h。"""
from typing import ClassVar

import httpx
from pydantic import BaseModel, Field
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.agents.tools.adapters import BaseToolAdapter
from app.core.config import settings
from app.core.user_context import get_tool_key

SCRAPE_TIMEOUT = 45.0
MAX_CONTENT_CHARS = 10_000


class ScrapeInput(BaseModel):
    url: str = Field(min_length=8, max_length=2048)


class ScraperAdapter(BaseToolAdapter):
    name: ClassVar[str] = "scrape_website"
    input_schema: ClassVar[type[ScrapeInput]] = ScrapeInput
    cache_ttl: ClassVar[int | None] = 86400  # 24h

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.TransportError)),
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def _arun(self, payload: ScrapeInput) -> str:
        async with httpx.AsyncClient(timeout=SCRAPE_TIMEOUT) as client:
            resp = await client.post(
                "https://api.firecrawl.dev/v1/scrape",
                headers={"Authorization": f"Bearer {get_tool_key('firecrawl') or settings.firecrawl_api_key}"},
                json={"url": payload.url, "formats": ["markdown"]},
            )
            resp.raise_for_status()
            data = resp.json().get("data", {})
            content = data.get("markdown") or data.get("content") or ""
        return content[:MAX_CONTENT_CHARS]


scrape_website = ScraperAdapter()
