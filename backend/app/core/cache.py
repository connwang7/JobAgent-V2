"""Redis 客户端与工具结果缓存 / 登录限流（令牌桶）。"""
import json
from typing import Any

import redis.asyncio as aioredis

from app.core.config import settings

_pool: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    global _pool
    if _pool is None:
        _pool = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _pool


async def cache_get_json(key: str) -> Any | None:
    try:
        raw = await get_redis().get(key)
        return json.loads(raw) if raw else None
    except Exception:
        return None


async def cache_set_json(key: str, value: Any, ttl_seconds: int) -> None:
    try:
        await get_redis().set(key, json.dumps(value, ensure_ascii=False), ex=ttl_seconds)
    except Exception:
        pass  # 缓存失败不影响主流程


async def rate_limit(bucket: str, max_hits: int, window_seconds: int) -> bool:
    """简单固定窗口限流。返回 True 表示放行。"""
    try:
        r = get_redis()
        current = await r.incr(f"rl:{bucket}")
        if current == 1:
            await r.expire(f"rl:{bucket}", window_seconds)
        return current <= max_hits
    except Exception:
        return True  # Redis 不可用时降级放行
