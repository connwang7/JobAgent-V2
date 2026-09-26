"""任务分发回归测试（不需要 Redis / Celery / DB）。

背景：`task.delay()` 在 broker 挂掉时会阻塞 ~108 秒重连，若发生在 async 端点里
会把整个事件循环冻住（现象：前端上传简历一直转圈、全站接口一起卡死）。
这里锁死三条不变量：
  1. broker 不可达时，`dispatch_or_inline` 必须**快速返回**并走 inline 降级；
  2. broker 不可达时**绝不调用** `task.delay()`（那正是 108 秒的那条路）；
  3. 降级任务确实会被调度到当前事件循环上执行（不是被丢掉）。
"""
import asyncio
import time

from app.workers import dispatch as d


class _FakeTask:
    """模拟 celery 任务对象（只需要 name + delay）。"""

    name = "fake_task"

    def __init__(self):
        self.called = 0

    def delay(self, *args):  # pragma: no cover - broker 挂掉时不该被走到
        self.called += 1
        return None


def test_broker_probe_is_fast_when_down(monkeypatch):
    """预检本身必须是"秒级"的，不能退化成上百秒重连。"""
    d._probe_cache = None
    monkeypatch.setattr(d.settings, "celery_broker_url", "redis://127.0.0.1:6399/1")

    t0 = time.monotonic()
    reachable = d.broker_reachable(timeout=0.2)
    elapsed = time.monotonic() - t0

    assert reachable is False
    assert elapsed < 3.0, f"预检耗时 {elapsed:.2f}s，过慢"


def test_dispatch_falls_back_inline_fast(monkeypatch):
    """broker 不可达 → 立刻 inline 降级，且不碰 task.delay()。"""
    d._probe_cache = None
    monkeypatch.setattr(d.settings, "celery_broker_url", "redis://127.0.0.1:6399/1")

    task = _FakeTask()
    ran: list[int] = []

    async def impl(arg: int) -> str:
        ran.append(arg)
        return "ok"

    async def main() -> tuple[str, float]:
        t0 = time.monotonic()
        mode = await d.dispatch_or_inline(task, impl, 7)
        return mode, time.monotonic() - t0

    mode, elapsed = asyncio.run(main())

    assert mode == "inline"
    assert task.called == 0, "broker 不可达时不应该尝试 publish"
    assert elapsed < 3.0, f"dispatch 耗时 {elapsed:.2f}s，说明又在同步重连"


def test_dispatch_inline_runs_and_returns_immediately(monkeypatch):
    """inline 分支：立刻返回，任务在后台跑完。"""
    d._probe_cache = None
    monkeypatch.setattr(d.settings, "celery_broker_url", "redis://127.0.0.1:6399/1")

    ran: list[str] = []

    async def impl() -> str:
        await asyncio.sleep(0.05)
        ran.append("done")
        return "ok"

    async def main() -> str:
        mode = await d.dispatch_or_inline(_FakeTask(), impl)
        assert ran == [], "dispatch 不应等待任务完成"
        await asyncio.sleep(0.2)
        return mode

    assert asyncio.run(main()) == "inline"
    assert ran == ["done"]


def test_probe_result_is_cached(monkeypatch):
    """预检结果短期内复用，避免每次上传都付 DNS/connect 代价。"""
    d._probe_cache = None
    monkeypatch.setattr(d.settings, "celery_broker_url", "redis://127.0.0.1:6399/1")

    assert d.broker_reachable(timeout=0.2) is False
    cached_at = d._probe_cache
    assert cached_at is not None

    # 第二次直接命中缓存，不应再发起连接（把超时设成 0 也不会抛）
    assert d.broker_reachable(timeout=0) is False
    assert d._probe_cache == cached_at


def test_broker_endpoint_parsing(monkeypatch):
    monkeypatch.setattr(d.settings, "celery_broker_url", "redis://cache.internal:6380/1")
    assert d.broker_endpoint() == ("cache.internal", 6380)

    monkeypatch.setattr(d.settings, "celery_broker_url", "redis://localhost/1")
    assert d.broker_endpoint() == ("localhost", 6379)


def test_memory_broker_is_always_reachable(monkeypatch):
    monkeypatch.setattr(d.settings, "celery_broker_url", "memory://")
    assert d.broker_endpoint(), "memory broker 也应能解析出 host/port"
    assert d.broker_reachable() is True
