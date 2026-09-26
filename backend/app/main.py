"""FastAPI 入口：lifespan 管理 checkpointer / Qdrant collection / 建表。"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.errors import AppError, app_error_handler, http_exception_handler, unhandled_exception_handler
from app.core.logging import logger, setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    # 图状态持久化（MySQL checkpointer，开发自动降级）
    from app.agents.graph import reset_graph
    from app.agents.graph.checkpoint import checkpoint_manager
    await checkpoint_manager.start()
    reset_graph()

    # 开发环境自动建表（生产走 alembic upgrade head）
    if settings.debug:
        from app.core.db import engine
        from app.models import Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("dev_schema_created")

    try:
        from app.matching.retriever import ensure_collection
        await ensure_collection()
    except Exception as exc:
        logger.warning("qdrant_unavailable", error=str(exc))

    # 上次运行被中断的解析任务会停在 pending/parsing，启动时收敛掉，
    # 否则前端会一直显示"解析中"（原因见 app/workers/reconcile.py）
    try:
        from app.workers.reconcile import fail_stuck_resumes
        await fail_stuck_resumes()
    except Exception as exc:
        logger.warning("resume_reconcile_failed", error=str(exc))

    yield
    await checkpoint_manager.stop()
    from app.core.db import engine
    await engine.dispose()


app = FastAPI(
    title=f"{settings.app_name} API",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)


@app.get("/healthz", tags=["meta"])
async def healthz():
    return {"status": "ok"}
