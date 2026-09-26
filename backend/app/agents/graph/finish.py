"""Finish：收尾。数据落库（消息/求职信/匹配引用）由 orchestrator 服务负责，节点只发终态事件。"""
from app.agents.graph.events import emit


async def finish_node(state: dict) -> dict:
    refs: dict = {}
    jobs = state.get("job_results") or []
    if jobs:
        refs["job_posting_ids"] = [
            j.job_posting_id if hasattr(j, "job_posting_id") else j.get("job_posting_id")
            for j in jobs[:10]
        ]
    if state.get("cover_letter"):
        refs["cover_letter"] = state.get("cover_letter", "")[:200]  # 全文由 letter 记录承载

    emit("final", "Finish", {
        "refs": refs,
        "human_decision": state.get("human_decision"),
        "revision_count": state.get("revision_count", 0),
    })
    return {}
