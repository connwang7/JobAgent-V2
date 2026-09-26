"""请求级上下文：承载"当前用户的工具密钥"。

用户级 Serper / FireCrawl Key 在内存中使用（contextvars），
不落日志、不进 prompt；未配置时回落到全局 settings。
"""
from contextvars import ContextVar

_user_tool_keys: ContextVar[dict[str, str]] = ContextVar("user_tool_keys", default={})


def set_user_tool_keys(keys: dict[str, str]) -> None:
    _user_tool_keys.set(keys or {})


def get_tool_key(name: str) -> str:
    """取当前用户级工具密钥；无则返回空串（调用方回落到全局配置）。"""
    return _user_tool_keys.get().get(name, "") or ""


def clear_user_tool_keys() -> None:
    _user_tool_keys.set({})
