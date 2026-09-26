"""LangGraph checkpointer 工厂：MySQL（官方 langgraph-checkpoint-mysql）为主，
开发环境可降级 SQLite / 内存。图状态持久化，上下文不再全量重放（v1 痛点）。
"""
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver

import app.core._compat  # noqa: F401  # 修复 pymysql/aiomysql bytes 转义，必须早于 checkpointer 写入
from app.core.config import settings
from app.core.logging import logger

# 黑板上的 Pydantic 结构化产物：显式登记 msgpack 白名单，避免反序列化告警
ALLOWED_MSGPACK_MODULES = [
    ("app.agents.graph.state", name)
    for name in ("Plan", "PlanStep", "ResumeProfile", "JobResult",
                 "JobSearchQuery", "CompanyResearch", "CriticResult")
]


def build_serde():
    """构造允许本项目产物类型的序列化器（langchain 消息类型本身在 SAFE 列表内）。"""
    try:
        from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
        return JsonPlusSerializer(allowed_msgpack_modules=ALLOWED_MSGPACK_MODULES)
    except Exception as exc:
        logger.warning("serde_build_failed", error=str(exc))
        return None


def _attach_serde(saver: BaseCheckpointSaver) -> BaseCheckpointSaver:
    serde = build_serde()
    if serde is not None:
        try:
            saver.serde = serde
        except Exception:
            pass
    return saver


class CheckpointManager:
    """管理 checkpointer 生命周期（MySQL saver 需要显式 setup/close）。"""

    def __init__(self) -> None:
        self._saver: BaseCheckpointSaver | None = None
        self._cm = None  # async context manager（MySQL / SQLite 持有连接池）

    @property
    def saver(self) -> BaseCheckpointSaver:
        return self._saver or InMemorySaver()

    async def start(self) -> BaseCheckpointSaver:
        url = settings.checkpoint_db_url or _to_mysql_dsn(settings.database_url)
        try:
            from langgraph.checkpoint.mysql import aio as mysql_aio

            saver_cls = getattr(mysql_aio, "AIOMySQLSaver", None) or getattr(
                mysql_aio, "AsyncMySQLSaver"
            )
            self._cm = saver_cls.from_conn_string(url)
            saver = await self._cm.__aenter__()
            await saver.setup()
            self._saver = _attach_serde(saver)
            logger.info("checkpointer_ready", backend="mysql")
        except Exception as exc:
            logger.warning("checkpointer_mysql_unavailable_fallback", error=str(exc))
            try:
                from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

                self._cm = AsyncSqliteSaver.from_conn_string("./.checkpoints.sqlite")
                saver = await self._cm.__aenter__()
                await saver.setup()
                self._saver = _attach_serde(saver)
                logger.info("checkpointer_ready", backend="sqlite")
            except Exception as exc2:
                logger.warning("checkpointer_sqlite_unavailable_fallback", error=str(exc2))
                self._saver = InMemorySaver(serde=build_serde())
        return self._saver

    async def stop(self) -> None:
        if self._cm is not None:
            try:
                await self._cm.__aexit__(None, None, None)
            except Exception:
                pass
        self._saver = None
        self._cm = None


def _to_mysql_dsn(sqlalchemy_url: str) -> str:
    """mysql+asyncmy://u:p@h:port/db → mysql://u:p@h:port/db（checkpoint 包约定）。"""
    if sqlalchemy_url.startswith("mysql+asyncmy://"):
        return "mysql://" + sqlalchemy_url[len("mysql+asyncmy://"):]
    if sqlalchemy_url.startswith("mysql://"):
        return sqlalchemy_url
    return "mysql://jobagent:jobagent@localhost:3306/jobagent"


checkpoint_manager = CheckpointManager()
