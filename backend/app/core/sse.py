"""SSE 事件协议（方案 3.2 节）。"""
from dataclasses import dataclass, field
from typing import Any

import json


@dataclass
class SSEEvent:
    event: str
    data: dict[str, Any] = field(default_factory=dict)

    def encode(self) -> str:
        return f"event: {self.event}\ndata: {json.dumps(self.data, ensure_ascii=False, default=str)}\n\n"


# 事件类型常量
EVENT_STATUS = "status"          # 阶段状态（规划中 / 检索中 / 撰写中…）
EVENT_PLAN = "plan"
EVENT_AGENT_START = "agent_start"
EVENT_TOOL_CALL = "tool_call"
EVENT_THINKING = "thinking"      # 模型思考增量（reasoning_content）
EVENT_THINKING_DONE = "thinking_done"
EVENT_TOKEN = "token"
EVENT_INTERRUPT = "interrupt"
EVENT_FINAL = "final"
EVENT_ERROR = "error"


def sse_response_headers() -> dict[str, str]:
    return {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
