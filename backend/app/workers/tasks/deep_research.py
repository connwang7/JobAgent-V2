"""deep_research：WebResearcher 深度研究循环异步化，避免阻塞 API 请求。

进度事件经 Redis Pub/Sub → API 进程 → SSE（方案 4.4）。
"""
from app.core.logging import logger
from app.workers.celery_app import celery_app


@celery_app.task(name="deep_research", bind=True, max_retries=1)
def deep_research_task(self, goal: str, context: dict | None = None) -> dict:
    import asyncio

    async def _run() -> dict:
        from app.agents.subgraphs.deep_research import deep_research

        research = await deep_research(goal, context or {})
        result = research.model_dump()

        # Redis Pub/Sub 广播，供 SSE 侧桥接
        try:
            from app.core.cache import get_redis
            import json
            await get_redis().publish(
                "agent_events",
                json.dumps({"type": "deep_research_done", "goal": goal}, ensure_ascii=False),
            )
        except Exception:
            pass
        return result

    return asyncio.run(_run())
