"""ORM 基类。"""
from datetime import datetime

from sqlalchemy import DateTime, Text
from sqlalchemy.dialects.mysql import JSON as MySQLJSON, LONGTEXT
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    pass


# MySQL 上使用原生 LONGTEXT / JSON；本地轻量库（SQLite）自动降级为 TEXT / JSON，
# 保证无 MySQL 环境下也能建表启动，生产 MySQL 行为不变。
LongText = Text().with_variant(LONGTEXT, "mysql")
JsonType = JSON().with_variant(MySQLJSON, "mysql")


# 说明：默认时间用 Python 端生成而非 server_default ——
# server_default 插入后对象上读不到值（需额外 SELECT 回读，异步下会触发 MissingGreenlet）。
def _utcnow() -> datetime:
    return datetime.utcnow()


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
