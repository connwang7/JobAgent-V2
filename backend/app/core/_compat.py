"""第三方库兼容性补丁（在应用启动最早期 import）。

1) PyMySQL >= 1.2 把 `escape_bytes_prefixed` 设成了哨兵字符串
   `"DO NOT IMPORT THIS!!!"`（官方注释：给 aiomysql 兼容期的占位），
   而 aiomysql 0.3.x 的 `Connection.escape()` 对 bytes 参数仍然调用它，
   导致任何 bytes 参数（langgraph checkpoint blob 写入）都会抛
   `TypeError: 'str' object is not callable`。
   这里恢复 PyMySQL 1.1.x 的真实实现，并同时修补两个模块
   （aiomysql 是 `from ... import` 按名引用，必须改它自己的命名空间）。
"""
from pymysql.converters import escape_bytes as _escape_bytes

_escape_table = [chr(i) for i in range(256)]
_escape_table[0] = "\\0"
_escape_table[ord("\n")] = "\\n"
_escape_table[ord("\r")] = "\\r"
_escape_table[ord("\\")] = "\\\\"
_escape_table[ord("'")] = "\\'"
_escape_table[ord('"')] = '\\"'
_escape_table[ord("\032")] = "\\Z"


def escape_bytes_prefixed(value, mapping=None):
    """bytes 参数转义为 `_binary'...'`（与 PyMySQL 1.1.x 行为一致）。"""
    return "_binary'%s'" % value.decode("ascii", "surrogateescape").translate(_escape_table)


def apply() -> None:
    try:
        import pymysql.converters as pc
        import aiomysql.connection as ac

        if not callable(getattr(pc, "escape_bytes_prefixed", None)):
            pc.escape_bytes_prefixed = escape_bytes_prefixed
        if not callable(getattr(ac, "escape_bytes_prefixed", None)):
            ac.escape_bytes_prefixed = escape_bytes_prefixed
    except Exception:  # pragma: no cover - 兼容层永不阻断启动
        from app.core.logging import logger
        logger.warning("pymysql_compat_patch_failed")


apply()
