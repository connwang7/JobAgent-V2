from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_session
from app.models.user import User
from app.repositories.letter import LetterRepository
from app.schemas.common import ok
from app.schemas.run import ApproveRequest
from app.services import letter as letter_service

router = APIRouter(prefix="/letters", tags=["letter"])


@router.get("")
async def list_letters(user: User = Depends(get_current_user),
                       db: AsyncSession = Depends(get_session)):
    rows = await letter_service.list_by_user(LetterRepository(db), user.id)
    return ok([{
        "id": r.id, "resume_id": r.resume_id, "job_posting_id": r.job_posting_id,
        "content": r.content, "version": r.version, "critic_score": r.critic_score,
        "status": r.status, "created_at": r.created_at,
    } for r in rows])


@router.get("/{letter_id}")
async def get_letter(letter_id: str, user: User = Depends(get_current_user),
                     db: AsyncSession = Depends(get_session)):
    letter = await letter_service.get_owned(LetterRepository(db), user.id, letter_id)
    return ok({
        "id": letter.id, "content": letter.content, "status": letter.status,
        "critic_score": letter.critic_score, "version": letter.version,
        "file_key": letter.file_key, "created_at": letter.created_at,
    })


@router.post("/{letter_id}/confirm")
async def confirm_letter(letter_id: str, req: ApproveRequest,
                         user: User = Depends(get_current_user),
                         db: AsyncSession = Depends(get_session)):
    repo = LetterRepository(db)
    letter = await letter_service.get_owned(repo, user.id, letter_id)
    letter = await letter_service.confirm(db, repo, letter, req.approved)
    return ok({"id": letter.id, "status": letter.status})


@router.get("/{letter_id}/download")
async def download_letter(letter_id: str, user: User = Depends(get_current_user),
                          db: AsyncSession = Depends(get_session)):
    letter = await letter_service.get_owned(LetterRepository(db), user.id, letter_id)
    url = await letter_service.download_url(letter)
    return ok({"url": url})
