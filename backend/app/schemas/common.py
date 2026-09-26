"""统一响应包络与通用模型。"""
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Envelope(BaseModel, Generic[T]):
    code: str = "OK"
    data: T | None = None
    message: str = "ok"


def ok(data: Any = None, message: str = "ok") -> dict:
    return {"code": "OK", "data": data, "message": message}
