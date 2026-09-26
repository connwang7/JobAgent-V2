"""Synthesizer：汇总黑板成面向用户的最终回答（替代 v1 finish chain）。"""
import json

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agents.graph.events import emit, role_llm
from app.agents.graph.workers import _as_dict
from app.agents.prompts import synthesizer as sy_prompts
from app.core.logging import logger


def _blackboard_summary(state: dict) -> str:
    """把黑板上的结构化产物压成给 Synthesizer 的素材块（只保留关键信息，控制 token）。"""
    blocks: list[str] = []
    results: dict = state.get("results") or {}

    for step_id, r in sorted(results.items()):
        r = _as_dict(r)
        if not r.get("ok"):
            blocks.append(f"[{step_id}/{r.get('agent','')}] 执行失败：{r.get('error','未知错误')}")

    if state.get("resume_profile"):
        p = _as_dict(state["resume_profile"])
        blocks.append(
            "[简历画像] 技能: " + ", ".join(p.get("skills", []))
            + f"；经验 {p.get('experience_years')} 年\n分析：{p.get('raw_analysis', '')[:600]}"
        )

    jobs = state.get("job_results") or []
    if jobs:
        rows = [
            f"- {_as_dict(j).get('title','')} | {_as_dict(j).get('company','')} | "
            f"{_as_dict(j).get('location','')} | {_as_dict(j).get('salary_text','')} | {_as_dict(j).get('url','')}"
            for j in jobs[:10]
        ]
        blocks.append("[岗位结果]\n" + "\n".join(rows))

    if state.get("company_research"):
        r = _as_dict(state["company_research"])
        block = (
            f"[公司调研] {r.get('company','')}\n{r.get('overview','')[:600]}\n"
            f"近期动态：{'; '.join(r.get('recent_news', [])[:3])}"
        )
        # 来源 URL 必须带上：否则模型只能凭正文里的域名猜测，
        # 答案里的"来源"就成了不可点击的孤零零域名（WebResearcher 的核心承诺是带引用）
        sources = [s for s in (r.get("sources") or []) if s][:8]
        if sources:
            block += "\n来源链接（请在答案的引用处使用这些完整 URL）：\n" + "\n".join(
                f"- {s}" for s in sources
            )
        blocks.append(block)

    if state.get("cover_letter"):
        blocks.append("[求职信] 已生成（内容将单独展示给用户确认，此处不必重复全文）")

    return "\n\n".join(blocks) or "（黑板为空）"


async def synthesizer_node(state: dict) -> dict:
    context: dict = state.get("context", {})
    emit("agent_start", "Synthesizer", {"desc": "汇总结果"})

    try:
        llm = role_llm("synthesizer", context, streaming=True)
        reply = await llm.ainvoke([
            SystemMessage(content=sy_prompts.SYNTHESIZER_SYSTEM),
            HumanMessage(content=(
                f"用户请求：{state.get('user_input', '')}\n\n"
                f"本轮执行产物：\n{_blackboard_summary(state)}"
            )),
        ])
        content = reply.content
    except Exception as exc:
        # 不再静默兜底：把真实原因打进日志，并在答案里说明已降级，
        # 否则用户只会看到 "[简历画像] 技能: ..." 这类内部黑板文本，无从定位
        reason = str(exc).strip().replace("\n", " ")[:300]
        logger.error("synthesizer_failed", error=reason)
        content = (
            "⚠️ **本轮汇总失败**（已降级为原始执行产物）\n\n"
            f"```\n{reason}\n```\n\n"
            "> 常见原因：该模型名在你的 Base URL 上不存在。请到「系统设置 → 大模型配置」"
            "核对模型名并点「测试连接」。\n\n"
            "---\n\n" + _blackboard_summary(state)
        )

    return {
        "final_message": content,
        "messages": [AIMessage(content=content, name="Synthesizer")],
    }


def route_after_synthesizer(state: dict) -> str:
    """求职信存在且未质检 → Critic 闭环；否则直接 Finish。"""
    if state.get("cover_letter") and not state.get("critic"):
        return "critic"
    return "finish"
