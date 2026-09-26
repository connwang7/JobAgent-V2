"""Critic 反思闭环（方案 6.6 节）：结构化评分 + 修订建议，≤2 次防震荡。"""
import json

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.graph.events import emit, role_llm
from app.agents.graph.state import CriticResult
from app.agents.graph.workers import _as_dict
from app.agents.prompts import cover_letter as cl_prompts
from app.core.logging import logger

MAX_REVISIONS = 2


async def critic_node(state: dict) -> dict:
    context: dict = state.get("context", {})
    emit("agent_start", "Critic", {"desc": "求职信质检"})

    profile = _as_dict(state.get("resume_profile"))
    jobs = state.get("job_results") or []
    top_job = _as_dict(jobs[0]) if jobs else {}
    research = _as_dict(state.get("company_research"))

    evidence = (
        f"【简历画像（真实性核查依据）】\n{json.dumps(profile, ensure_ascii=False)}\n\n"
        f"【目标岗位】\n{json.dumps(top_job, ensure_ascii=False)}\n\n"
        f"【公司调研】\n{json.dumps(research, ensure_ascii=False)[:1500]}\n\n"
        f"【待检求职信】\n{state.get('cover_letter', '')}"
    )

    try:
        llm = role_llm("critic", context)  # 与生成器异模型，避免同源偏见
        model = llm.with_structured_output(CriticResult)
        result: CriticResult = await model.ainvoke([
            SystemMessage(content=cl_prompts.CRITIC_SYSTEM),
            HumanMessage(content=evidence),
        ])
    except Exception as exc:
        logger.error("critic_failed", error=str(exc))
        # 质检失败不阻塞流程：放行进入 HITL（用户人工把关）
        result = CriticResult(scores={}, passed=True, suggestions=[f"自动质检失败：{exc}"])

    emit("critic", "Critic", {"scores": result.scores, "passed": result.passed,
                              "suggestions": result.suggestions})
    return {"critic": result}


def route_after_critic(state: dict) -> str:
    critic: CriticResult | None = state.get("critic")
    revisions = state.get("revision_count", 0)
    if critic and not critic.passed and revisions < MAX_REVISIONS:
        return "revise_letter"
    return "hitl"
