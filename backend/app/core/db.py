"""SQLAlchemy 2.0 异步引擎与会话管理。"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.core._compat  # noqa: F401  # 必须先于任何 aiomysql 使用：修复 pymysql/aiomysql bytes 转义
from app.core.config import settings

engine = create_async_engine(settings.database_url, pool_pre_ping=True, pool_recycle=3600, echo=False)

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
