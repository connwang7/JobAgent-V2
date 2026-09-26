from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_session
from app.core.errors import NotFoundError
from app.models.user import User
from app.repositories.chat import RunRepository, SessionRepository
from app.schemas.common import ok
from app.schemas.run import ApproveRequest, RunOut
from app.services.orchestrator import orchestrator

router = APIRouter(prefix="/runs", tags=["run"])


@router.post("/{run_id}/approve")
async def approve(run_id: str, req: ApproveRequest,
                 user: User = Depends(get_current_user),
                 db: AsyncSession = Depends(get_session)):
    """HITL 中断确认：图从 checkpoint 恢复继续执行。"""
    run = await RunRepository(db).get(run_id)
    if not run:
        raise NotFoundError("run 不存在", code="RUN-404")
    session_row = await SessionRepository(db).get(run.session_id)
    if not session_row or session_row.user_id != user.id:
        raise NotFoundError("会话不存在", code="SESS-404")

    payload = await orchestrator.resume_run(session_row, user, run, req.approved)
    return ok(payload)


@router.get("/{run_id}/trace")
async def trace(run_id: str, user: User = Depends(get_current_user),
                db: AsyncSession = Depends(get_session)):
    """完整执行轨迹（agent_events 流水）。"""
    from app.repositories.chat import EventRepository
    run = await RunRepository(db).get(run_id)
    if not run:
        raise NotFoundError("run 不存在", code="RUN-404")
    session_row = await SessionRepository(db).get(run.session_id)
    if not session_row or session_row.user_id != user.id:
        raise NotFoundError("会话不存在", code="SESS-404")

    events = await EventRepository(db).list_by_run(run_id)
    return ok([
        {
            "seq": e.seq, "node_name": e.node_name, "event_type": e.event_type,
            "payload": e.payload, "latency_ms": e.latency_ms, "created_at": e.created_at,
        }
        for e in events
    ])


@router.get("/{run_id}")
async def get_run(run_id: str, user: User = Depends(get_current_user),
                  db: AsyncSession = Depends(get_session)):
    run = await RunRepository(db).get(run_id)
    if not run:
        raise NotFoundError("run 不存在", code="RUN-404")
    session_row = await SessionRepository(db).get(run.session_id)
    if not session_row or session_row.user_id != user.id:
        raise NotFoundError("会话不存在", code="SESS-404")
    return ok(RunOut.model_validate(run).model_dump())
