"""节点公共工具：SSE 事件发射（LangGraph custom stream）、角色 LLM 获取、计时。"""
import time
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel

from app.agents.llm.model_router import get_llm_for_role


def emit(event_type: str, node_name: str, payload: dict[str, Any] | None = None,
         latency_ms: int = 0) -> None:
    """通过 LangGraph custom stream writer 发布事件。

    orchestrator 以 stream_mode="custom" 接收 → 持久化 agent_events + 推送 SSE。
    在无图上下文（单测/CLI）中静默失败。
    """
    try:
        from langgraph.config import get_stream_writer
        writer = get_stream_writer()
        if writer is not None:
            writer({
                "type": event_type,
                "node": node_name,
                "payload": payload or {},
                "latency_ms": latency_ms,
            })
    except Exception:
        pass


def role_llm(role: str, context: dict, streaming: bool = False) -> BaseChatModel:
    """按角色 + 用户级配置获取 LLM。

    若本轮开启了「深度思考」（context["deep_thinking"]），生成类角色改用推理模型，
    以便前端能拿到 reasoning_content 形式的思考过程。

    streaming=True 仅在产出用户可见文本的节点使用（synthesizer / ChatBot），
    让 token 逐块下发；其余节点（尤其是 with_structured_output 的）保持非流式。
    """
    if context.get("deep_thinking") and role in ("worker", "synthesizer"):
        role = "thinking"
    return get_llm_for_role(
        role,
        user_pref=context.get("llm_pref"),
        user_api_key_enc=context.get("llm_api_key_enc", ""),
        user_base_url=context.get("llm_base_url", ""),
        streaming=streaming,
    )


THINKING_FIELD_CANDIDATES = ("reasoning_content", "reasoning", "thinking")


def extract_reasoning(msg_chunk: Any) -> str:
    """从流式 chunk 里取出推理内容（DeepSeek/DashScope 放在 additional_kwargs）。"""
    for holder in (getattr(msg_chunk, "additional_kwargs", None),
                   getattr(msg_chunk, "response_metadata", None)):
        if isinstance(holder, dict):
            for key in THINKING_FIELD_CANDIDATES:
                val = holder.get(key)
                if isinstance(val, str) and val:
                    return val
    # 部分实现把它放在 content 的 list 分片里
    content = getattr(msg_chunk, "content", None)
    if isinstance(content, list):
        parts = [
            p.get("thinking") or p.get("reasoning_content")
            for p in content
            if isinstance(p, dict) and p.get("type") in ("thinking", "reasoning")
        ]
        return "".join(p for p in parts if p)
    return ""


class Timer:
    """简单计时器：with Timer() as t: ... t.ms"""

    def __enter__(self) -> "Timer":
        self.start = time.monotonic()
        return self

    def __exit__(self, *exc) -> None:
        self.ms = int((time.monotonic() - self.start) * 1000)

    ms: int = 0
