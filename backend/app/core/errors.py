"""统一业务错误与错误码分域（AUTH-xxxx / SESSION-xxxx / AGENT-xxxx ...）。"""
from typing import Any

from fastapi import HTTPException, status
from fastapi.responses import JSONResponse


class AppError(Exception):
    """业务错误基类。code 形如 'AUTH-001'。"""

    def __init__(self, code: str, message: str, http_status: int = status.HTTP_400_BAD_REQUEST,
                 data: Any = None):
        self.code = code
        self.message = message
        self.http_status = http_status
        self.data = data
        super().__init__(message)


class AuthError(AppError):
    def __init__(self, message: str, code: str = "AUTH-001",
                 http_status: int = status.HTTP_401_UNAUTHORIZED):
        super().__init__(code, message, http_status)


class NotFoundError(AppError):
    def __init__(self, message: str, code: str = "RES-404",
                 http_status: int = status.HTTP_404_NOT_FOUND):
        super().__init__(code, message, http_status)


class ValidationError(AppError):
    def __init__(self, message: str, code: str = "VAL-400"):
        super().__init__(code, message, status.HTTP_400_BAD_REQUEST)


class AgentError(AppError):
    def __init__(self, message: str, code: str = "AGENT-500",
                 http_status: int = status.HTTP_500_INTERNAL_SERVER_ERROR):
        super().__init__(code, message, http_status)


class DependencyUnavailableError(AppError):
    """外部依赖（向量库 / Embedding / 检索服务）不可用。

    这类失败是**可降级**的：不应表现为 500 + "internal server error"，
    而要给出可操作的提示（换个入口 / 怎么修），前端直接把 message 展示给用户。
    """

    def __init__(self, message: str, code: str = "DEP-503",
                 http_status: int = status.HTTP_503_SERVICE_UNAVAILABLE):
        super().__init__(code, message, http_status)


def error_response(exc: AppError) -> JSONResponse:
    """统一响应包络 {code, data, message}。"""
    return JSONResponse(
        status_code=exc.http_status,
        content={"code": exc.code, "data": exc.data, "message": exc.message},
    )


async def app_error_handler(_: Any, exc: AppError) -> JSONResponse:
    return error_response(exc)


async def http_exception_handler(_: Any, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": f"HTTP-{exc.status_code}", "data": None, "message": str(exc.detail)},
    )


async def unhandled_exception_handler(_: Any, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"code": "SYS-500", "data": None, "message": "internal server error"},
    )
