"""HITL 中断节点（方案 6.7 节）：求职信落盘（生成 docx）前必须用户确认。"""
from langgraph.types import interrupt

from app.agents.graph.events import emit
from app.agents.graph.workers import _as_dict


async def hitl_node(state: dict) -> dict:
    """interrupt() 暂停图执行；用户 approve/reject 后经 Command(resume=...) 恢复。

    恢复值：True（确认，随后渲染 docx）或 False（拒绝，归档草稿）。
    """
    critic = _as_dict(state.get("critic"))
    payload = {
        "type": "cover_letter_confirm",
        "cover_letter": state.get("cover_letter", ""),
        "critic_scores": critic.get("scores", {}),
        "critic_suggestions": critic.get("suggestions", []),
        "revision_count": state.get("revision_count", 0),
    }
    emit("interrupt", "HITL", payload)

    decision = interrupt(payload)  # 暂停点由 MySQL checkpointer 持久化
    approved = bool(decision)

    return {"human_decision": approved}
