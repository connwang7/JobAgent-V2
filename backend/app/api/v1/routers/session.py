from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_session
from app.core.errors import NotFoundError
from app.core.sse import SSEEvent, sse_response_headers
from app.models.chat import Session
from app.models.user import User
from app.repositories.chat import MessageRepository, SessionRepository
from app.schemas.common import ok
from app.schemas.session import (
    ChatRequest, SessionCreate, SessionOut, SessionResumeUpdate,
)
from app.services.orchestrator import orchestrator

router = APIRouter(prefix="/sessions", tags=["session"])


async def _owned_session(session_id: str, user: User, db: AsyncSession) -> Session:
    row = await SessionRepository(db).get(session_id)
    if not row or row.user_id != user.id:
        raise NotFoundError("会话不存在", code="SESS-404")
    return row


@router.get("")
async def list_sessions(user: User = Depends(get_current_user),
                        db: AsyncSession = Depends(get_session)):
    rows = await SessionRepository(db).list_by_user(user.id)
    return ok([SessionOut.model_validate(r).model_dump() for r in rows])


@router.post("", status_code=201)
async def create_session(req: SessionCreate, user: User = Depends(get_current_user),
                         db: AsyncSession = Depends(get_session)):
    row = await SessionRepository(db).add(Session(
        user_id=user.id, title=req.title or "新会话", resume_id=req.resume_id,
    ))
    await db.commit()
    return ok(SessionOut.model_validate(row).model_dump())


@router.delete("/{session_id}")
async def delete_session(session_id: str, user: User = Depends(get_current_user),
                         db: AsyncSession = Depends(get_session)):
    row = await _owned_session(session_id, user, db)
    await SessionRepository(db).delete(row)
    await db.commit()
    return ok()


@router.get("/{session_id}/messages")
async def list_messages(session_id: str, user: User = Depends(get_current_user),
                        db: AsyncSession = Depends(get_session)):
    await _owned_session(session_id, user, db)
    rows = await MessageRepository(db).list_by_session(session_id)
    return ok([
        {
            "id": r.id, "role": r.role, "agent_name": r.agent_name,
            "content": r.content, "refs": r.refs, "created_at": r.created_at,
        }
        for r in rows
    ])


@router.put("/{session_id}/resume")
async def bind_resume(session_id: str, req: SessionResumeUpdate,
                      user: User = Depends(get_current_user),
                      db: AsyncSession = Depends(get_session)):
    """把简历中心里已有的简历关联到本会话（或传 resume_id=null 取消关联）。

    没有这个接口时，用户只能在会话里"重新上传一份 PDF"，简历中心里的历史版本
    就永远用不上——这正是"看不到已有简历"的根因。
    """
    session_row = await _owned_session(session_id, user, db)
    if req.resume_id is not None:
        from app.models.resume import Resume
        resume = await db.get(Resume, req.resume_id)
        if resume is None or resume.user_id != user.id:
            raise NotFoundError("简历不存在或无权使用", code="RES-404")
    session_row.resume_id = req.resume_id
    await db.commit()
    return ok(SessionOut.model_validate(session_row).model_dump())


@router.post("/{session_id}/chat")
async def chat(session_id: str, req: ChatRequest,
               user: User = Depends(get_current_user),
               db: AsyncSession = Depends(get_session)):
    """发起对话：SSE 流式响应（方案 3.2 事件协议）。"""
    session_row = await _owned_session(session_id, user, db)

    # 用户显式携带参考简历：校验归属后绑定到会话（此后本会话始终带上该简历）
    if req.resume_id is not None and req.resume_id != session_row.resume_id:
        from app.models.resume import Resume
        resume = await db.get(Resume, req.resume_id)
        if resume is None or resume.user_id != user.id:
            from app.core.errors import NotFoundError
            raise NotFoundError("参考简历不存在或无权使用", code="RES-404")
        session_row.resume_id = req.resume_id
        await db.commit()

    async def event_stream():
        async for ev in orchestrator.chat_stream(
            session_row, user, req.content,
            deep_thinking=req.deep_thinking, web_search=req.web_search,
        ):
            yield ev.encode()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers=sse_response_headers(),
    )
