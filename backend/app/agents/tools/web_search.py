"""web_search：Serper API（升级重试 + 超时，TTL 30min）。"""
from typing import ClassVar

import httpx
from pydantic import BaseModel, Field
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.agents.tools.adapters import BaseToolAdapter
from app.core.config import settings
from app.core.user_context import get_tool_key

SEARCH_TIMEOUT = 15.0


class WebSearchInput(BaseModel):
    query: str = Field(min_length=1, max_length=256)
    num_results: int = Field(default=8, ge=1, le=20)


class WebSearchAdapter(BaseToolAdapter):
    name: ClassVar[str] = "web_search"
    input_schema: ClassVar[type[WebSearchInput]] = WebSearchInput
    cache_ttl: ClassVar[int | None] = 1800  # 30min

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.TransportError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    async def _fetch(self, query: str, num_results: int) -> list[dict]:
        async with httpx.AsyncClient(timeout=SEARCH_TIMEOUT) as client:
            resp = await client.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": get_tool_key("serper") or settings.serper_api_key},
                json={"q": query, "num": num_results},
            )
            resp.raise_for_status()
            return resp.json().get("organic", [])

    async def _arun(self, payload: WebSearchInput) -> list[dict]:
        items = await self._fetch(payload.query, payload.num_results)
        return [
            {
                "title": it.get("title", ""),
                "link": it.get("link", ""),
                "snippet": it.get("snippet", ""),
                "date": it.get("date", ""),
            }
            for it in items
        ]


web_search = WebSearchAdapter()
