"""Planner 节点：意图理解 + 任务 DAG 生成（结构化输出，替代 v1 关键词路由）。"""
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.graph.events import emit, role_llm
from app.agents.graph.state import Plan, PlanStep, RESET_KEY
from app.agents.prompts.planner import build_planner_prompt
from app.core.logging import logger

FALLBACK_PLAN = Plan(steps=[], is_simple_chat=True)


def _context_block(context: dict) -> str:
    parts: list[str] = []
    prefs = context.get("preferences") or {}
    if prefs:
        parts.append(f"用户求职偏好：{prefs}")
    if context.get("resume_ready"):
        parts.append("用户已上传简历（ResumeAnalyzer 可用）。")
    else:
        parts.append("用户尚未上传简历（ResumeAnalyzer 不可用；CoverLetterGenerator 需要简历画像，也不可用）。")
        available = context.get("available_resumes") or []
        if available:
            listing = "；".join(
                f"v{r.get('version')} {r.get('filename')}（{'已就绪' if r.get('status') == 'ready' else r.get('status')}）"
                for r in available
            )
            parts.append(
                "注意：用户「简历中心」里已有这些简历版本：" + listing +
                "。若用户想分析/使用简历，不要回答看不到，"
                "应告诉用户可在输入框左侧点回形针选择关联其中一份（或直接上传新的 PDF）。"
            )
    memories = context.get("memories") or []
    if memories:
        parts.append("用户长期记忆（注意参考）：" + "；".join(memories[:5]))
    if context.get("web_search"):
        if context.get("web_search_available", True):
            parts.append(
                "用户已开启「联网搜索」：必须包含一个 WebSearcher 步骤，"
                "并在答案中标注来源，禁止仅凭已有知识作答。"
            )
        else:
            parts.append(
                "用户开启了「联网搜索」，但当前**没有配置搜索服务密钥（Serper）**，本轮无法联网："
                "不要规划 WebSearcher 步骤，也不得假装检索过。请在回答开头用一句话说明"
                "「联网搜索未生效：到 设置 → 工具密钥 填入 Serper API Key 后可用」，再基于已有知识作答。"
            )
    if context.get("deep_thinking"):
        parts.append("用户已开启「深度思考」：请把任务拆得更细，必要时增加 CompanyResearcher 步骤。")
    return "\n".join(parts) or "（无额外上下文）"


async def planner_node(state: dict) -> dict:
    context: dict = state.get("context", {})
    user_input: str = state.get("user_input", "")

    emit("agent_start", "Planner", {"desc": "解析用户意图，生成执行计划"})
    try:
        llm = role_llm("planner", context)
        plan_model = llm.with_structured_output(Plan)
        plan: Plan = await plan_model.ainvoke([
            SystemMessage(content=build_planner_prompt(_context_block(context))),
            HumanMessage(content=user_input),
        ])
        # 防御：规划了不可用 agent 或空计划 → 退化为 ChatBot
        if not plan.is_simple_chat and not plan.steps:
            plan = FALLBACK_PLAN
        # 「联网搜索」是硬承诺：即便 LLM 判成闲聊，也必须真的检索，
        # 否则用户点开开关却什么都没发生（开关形同无效）
        if (context.get("web_search") and context.get("web_search_available", True)
                and plan.is_simple_chat):
            plan = Plan(
                steps=[PlanStep(id="s1", agent="WebResearcher",
                                description=(user_input or "检索用户提到的信息")[:80])],
                is_simple_chat=False,
            )
    except Exception as exc:
        logger.error("planner_failed", error=str(exc))
        plan = FALLBACK_PLAN

    emit("plan", "Planner", {
        "steps": [s.model_dump() for s in plan.steps],
        "is_simple_chat": plan.is_simple_chat,
    })
    # 新一轮执行：重置 results 黑板
    return {"plan": plan, "results": {RESET_KEY: True}}


def route_after_planner(state: dict) -> str:
    plan: Plan | None = state.get("plan")
    if plan is None or plan.is_simple_chat or not plan.steps:
        return "ChatBot"
    return "executor"
