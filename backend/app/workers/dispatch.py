"""任务分发：优先走 Celery；Redis/worker 不可用时降级为**进程内异步执行**。

本地开发常见场景是"只起了后端、没起 Redis + Celery"。
若直接 `.delay()` 抛错就把状态标成 failed，用户上传简历会莫名其妙失败。

有两个坑（都踩过）：

1. **不能同步调用 `task.delay()`**。它是阻塞 IO；broker（Redis）连不上时，
   kombu 会按 broker_connection_max_retries 反复重连 —— 实测要 **~108 秒**才抛错。
   这段阻塞发生在 `async def` 端点的调用栈里，会把**整个事件循环**冻住，
   表现就是"点了上传一直转圈，而且全站接口一起卡死"。
   → 所以这里先做一次 TCP 预检（~0.4s），并且真正 publish 时丢到线程里。

2. **降级必须调度到当前运行的事件循环**，不能另起线程 `asyncio.run()` ——
   模块级 async 引擎的连接池绑定在原循环上，换循环会抛
   `RuntimeError: got Future attached to a different loop`。
"""
import asyncio
import socket
import time
import traceback
from collections.abc import Callable, Coroutine
from typing import Any
from urllib.parse import urlparse

from app.core.config import settings
from app.core.logging import logger

#: 强引用后台任务，防止被 GC 提前回收（asyncio 只持弱引用）
_BACKGROUND: set[asyncio.Task] = set()

_DEFAULT_PORTS = {"redis": 6379, "rediss": 6379, "amqp": 5672, "amqps": 5671, "memory": 0}

#: 探测结果缓存（秒）。一次上传只付一次 DNS/connect 代价；
#: 缓存时间很短，所以 Redis 起来/挂掉后最多 5 秒就会走对分支。
_PROBE_TTL = 5.0
_probe_cache: tuple[float, bool] | None = None


def broker_endpoint() -> tuple[str, int]:
    """从 broker URL 解析出 host/port，解析不出来时回落到 redis 默认值。"""
    parsed = urlparse(settings.celery_broker_url)
    scheme = (parsed.scheme or "redis").split("+")[0]
    host = parsed.hostname or "localhost"
    port = parsed.port or _DEFAULT_PORTS.get(scheme, 6379)
    return host, port


def broker_reachable(timeout: float = 0.4) -> bool:
    """TCP 预检：broker 端口能否在 timeout 内建连（结果缓存 `_PROBE_TTL` 秒）。

    工程取舍：预检成功不代表 publish 一定成功（仍会 try/except 兜底），
    但预检失败就**一定**不要走 Celery —— 那正是 108 秒卡死的那条路。
    """
    global _probe_cache

    if settings.celery_broker_url.startswith("memory://"):
        return True

    now = time.monotonic()
    if _probe_cache is not None and now - _probe_cache[0] < _PROBE_TTL:
        return _probe_cache[1]

    host, port = broker_endpoint()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            ok = True
    except OSError:
        ok = False

    _probe_cache = (now, ok)
    return ok


def _spawn_inline(task_name: str, coro: Coroutine[Any, Any, Any]) -> str:
    """把协程挂到当前事件循环上后台跑，立刻返回（不 await）。"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # 非请求上下文（如 CLI 脚本）：调用方自行处理
        logger.error("inline_dispatch_no_running_loop", task=task_name)
        return "skipped"

    bg = loop.create_task(coro, name=f"inline:{task_name}")
    _BACKGROUND.add(bg)

    def _done(t: asyncio.Task) -> None:
        _BACKGROUND.discard(t)
        if t.cancelled():
            # 进程退出 / 事件循环关停时会被取消，属于预期情况
            logger.warning("inline_task_cancelled", task=task_name)
            return
        try:
            t.result()
        except Exception:
            logger.error("inline_task_failed", task=task_name, traceback=traceback.format_exc())

    bg.add_done_callback(_done)
    return "inline"


async def dispatch_or_inline(task: Any, async_impl: Callable[..., Coroutine[Any, Any, Any]],
                             *args: Any, **kwargs: Any) -> str:
    """返回 "celery" / "inline" / "skipped"，便于调用方日志区分。

    **必须在 async 上下文里 await**：publish 走线程池，避免阻塞事件循环。

    `*args` 同时给 Celery 任务和进程内实现（两者都要能接）；
    `**kwargs` **只给进程内实现** —— Celery 任务经 `.delay()` 只能拿到 args，
    worker 侧拿不到 kwargs。所以 impl 的相关参数要有能表达"我在 Celery 里跑"的默认值，
    例如 `run_parse_resume(resume_id, parse_mode="celery")`。
    """
    name = getattr(task, "name", str(task))

    if broker_reachable():
        try:
            # delay() 是同步阻塞调用（含网络重连），放线程里执行，绝不卡事件循环
            await asyncio.to_thread(task.delay, *args)
            return "celery"
        except Exception as exc:
            logger.warning("celery_publish_failed_fallback_inline",
                           task=name, error=str(exc)[:200])
    else:
        host, port = broker_endpoint()
        logger.info("celery_broker_unreachable_fallback_inline",
                    task=name, host=host, port=port)

    return _spawn_inline(name, async_impl(*args, **kwargs))
