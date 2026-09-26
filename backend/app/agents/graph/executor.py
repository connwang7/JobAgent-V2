"""Executor 超步调度（方案 6.5 节）：LangGraph Send API 并行分发。

无依赖的 Step 并行 Send 到对应 Agent 节点；全部完成后进入 Synthesizer。
"""
from langgraph.types import Send

from app.agents.graph.state import Plan, PlanStep


def _payload_for(step: PlanStep, state: dict) -> dict:
    """Send 载荷：该步骤所需的黑板字段 + 上下文。"""
    resume_profile = state.get("resume_profile")
    job_results = state.get("job_results") or []
    company_research = state.get("company_research")
    critic = state.get("critic")
    return {
        "step": step.model_dump(),
        "user_input": state.get("user_input", ""),
        "context": state.get("context", {}),
        "resume_profile": resume_profile.model_dump() if resume_profile else None,
        "job_results": [j.model_dump() for j in job_results],
        "company_research": company_research.model_dump() if company_research else None,
        "cover_letter": state.get("cover_letter"),
        "critic": critic.model_dump() if critic else None,
        "revision_count": state.get("revision_count", 0),
    }


def ready_steps(plan: Plan, results: dict) -> list[PlanStep]:
    completed = set((results or {}).keys())
    return [
        s for s in plan.steps
        if s.id not in completed and set(s.depends_on) <= completed
    ]


def all_done(plan: Plan, results: dict) -> bool:
    completed = set((results or {}).keys())
    return all(s.id in completed for s in plan.steps)


def route_executor(state: dict):
    """Executor 条件路由：并行 Send 或进入 Synthesizer。"""
    plan: Plan = state["plan"]
    results: dict = state.get("results") or {}

    ready = ready_steps(plan, results)
    if ready:
        return [Send(s.agent, _payload_for(s, state)) for s in ready]
    # 全部完成（或依赖无法满足的残余）→ 汇总
    return "synthesizer"


def executor_node(state: dict) -> dict:
    """Executor 节点本体：仅作为调度锚点，路由逻辑在 route_executor。"""
    return {}
