"""启动时收敛被中断的后台任务状态。

进程内降级任务（`dispatch_or_inline` 的 inline 分支）在服务重启 / 事件循环关停时
会被取消，数据库里就会残留 `status='pending'/'parsing'` 的记录 ——
前端永远显示"解析中"，用户不知道发生了什么。

设计取舍：
- 只在本进程启动时跑一次，此时**旧的 inline 任务必然已经不在运行**。
- 但若 broker 可达，说明可能存在真正的 Celery 队列/worker，那些记录的归属权不在我们手里，
  此时一律不动（宁可留着，也不要误标 failed）。
- 再加一道时间保护：只处理创建超过 `STUCK_AFTER` 的记录，避免误伤刚入队的任务。
"""
from datetime import datetime, timedelta

from sqlalchemy import select, update

from app.core.db import AsyncSessionLocal
from app.core.logging import logger
from app.models.resume import Resume

STUCK_AFTER = timedelta(minutes=10)

STUCK_MESSAGE = "解析任务被中断（服务重启或进程退出），请点「重新解析」重试"


async def fail_stuck_resumes() -> int:
    """把卡住的简历统一标为 failed 并写明原因，返回处理条数。"""
    from app.workers.dispatch import broker_reachable

    if broker_reachable():
        logger.info("resume_reconcile_skipped_broker_up")
        return 0

    cutoff = datetime.utcnow() - STUCK_AFTER
    async with AsyncSessionLocal() as db:
        ids = (
            await db.execute(
                select(Resume.id).where(
                    Resume.status.in_(("pending", "parsing")),
                    Resume.created_at < cutoff,
                )
            )
        ).scalars().all()
        if not ids:
            return 0
        await db.execute(
            update(Resume)
            .where(Resume.id.in_(ids))
            .values(status="failed", error=STUCK_MESSAGE)
        )
        await db.commit()

    logger.warning("stuck_resumes_marked_failed", count=len(ids), sample=list(ids)[:20])
    return len(ids)
