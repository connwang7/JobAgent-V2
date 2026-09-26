from fastapi import APIRouter

from app.api.v1.routers import auth, job, letter, me, resume, run, session

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(session.router)
api_router.include_router(run.router)
api_router.include_router(resume.router)
api_router.include_router(job.router)
api_router.include_router(letter.router)
api_router.include_router(me.router)
