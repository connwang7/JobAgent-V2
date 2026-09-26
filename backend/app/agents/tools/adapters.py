"""工具适配器基类（方案 8.1/8.2 节）。

所有工具统一：Pydantic 严格入参校验、Redis 结果缓存、出站超时与重试、
调用全量记录（由节点侧 emit agent_events）。
"""
import hashlib
import json
import time
from abc import ABC, abstractmethod
from typing import Any, ClassVar

from pydantic import BaseModel

from app.core.cache import cache_get_json, cache_set_json
from app.core.logging import logger


class ToolResult(BaseModel):
    ok: bool
    data: Any = None
    error: str = ""
    cached: bool = False
    latency_ms: int = 0


class BaseToolAdapter(ABC):
    name: ClassVar[str]
    input_schema: ClassVar[type[BaseModel]]
    cache_ttl: ClassVar[int | None] = None  # 秒；None 不缓存
    rate_limit: ClassVar[tuple[int, int] | None] = None  # (max_calls, window_seconds)

    @abstractmethod
    async def _arun(self, payload: BaseModel) -> Any:
        """子类实现具体调用。"""

    async def arun(self, payload: dict | BaseModel) -> ToolResult:
        start = time.monotonic()
        try:
            parsed = payload if isinstance(payload, BaseModel) else self.input_schema(**payload)
        except Exception as exc:
            return ToolResult(ok=False, error=f"参数校验失败: {exc}")

        cache_key = None
        if self.cache_ttl:
            digest = hashlib.sha256(
                f"{self.name}:{parsed.model_dump_json()}".encode()
            ).hexdigest()
            cache_key = f"toolcache:{digest}"
            cached = await cache_get_json(cache_key)
            if cached is not None:
                return ToolResult(
                    ok=True, data=cached, cached=True,
                    latency_ms=int((time.monotonic() - start) * 1000),
                )

        try:
            data = await self._arun(parsed)
            if cache_key:
                await cache_set_json(cache_key, data, self.cache_ttl)
            return ToolResult(
                ok=True, data=data,
                latency_ms=int((time.monotonic() - start) * 1000),
            )
        except Exception as exc:
            logger.error("tool_failed", tool=self.name, error=str(exc))
            return ToolResult(
                ok=False, error=str(exc),
                latency_ms=int((time.monotonic() - start) * 1000),
            )

    def args_digest(self, payload: dict | BaseModel) -> str:
        """脱敏参数摘要，用于 agent_events / SSE tool_call 事件。"""
        raw = payload.model_dump_json() if isinstance(payload, BaseModel) else json.dumps(payload, ensure_ascii=True, default=str)
        return raw[:200]
