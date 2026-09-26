"""各 Agent 工作节点（方案 6.4 节）。

结构化优先：LLM 决定参数（结构化输出），代码决定工具调用 —— 无自由文本协议、
无消息历史扫描（直接读黑板字段，token 开销大幅低于 v1）。
"""
import json

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agents.graph.events import emit, role_llm
from app.agents.graph.state import (
    CompanyResearch, JobRanking, JobResult, JobSearchQuery, ResumeProfile,
)
from app.agents.prompts import cover_letter as cl_prompts
from app.agents.prompts import job_searcher as js_prompts
from app.agents.prompts import resume_analyzer as ra_prompts
from app.agents.prompts import synthesizer as sy_prompts
from app.agents.subgraphs.deep_research import deep_research
from app.agents.tools import job_search as job_search_tool
from app.core.logging import logger


def _as_dict(obj) -> dict:
    """黑板字段可能是 Pydantic 模型（全量状态）或 dict（Send 载荷），统一转 dict。"""
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    try:
        return obj.model_dump()
    except AttributeError:
        return {}


def _error_artifact(step: dict, message: str) -> dict:
    return {"results": {step["id"]: {"agent": step["agent"], "ok": False, "error": message}}}


def _ok_artifact(step: dict, summary: str = "") -> dict:
    return {"results": {step["id"]: {"agent": step["agent"], "ok": True, "summary": summary}}}


NO_SERPER_HINT = (
    "联网搜索未生效：当前未配置搜索服务密钥（Serper）。"
    "请到 设置 → 工具密钥 填入 Serper API Key 后重试。"
)


# ---------------- ResumeAnalyzer ----------------

async def resume_analyzer_node(state: dict) -> dict:
    step: dict = state["step"]
    context: dict = state.get("context", {})
    emit("agent_start", "ResumeAnalyzer", {"desc": step.get("description", "")})

    resume_text = (context.get("resume_text") or "").strip()
    if not resume_text:
        return _error_artifact(step, "未找到可用简历，请先在简历中心上传")

    try:
        llm = role_llm("worker", context)
        model = llm.with_structured_output(ResumeProfile)
        profile: ResumeProfile = await model.ainvoke([
            SystemMessage(content=ra_prompts.RESUME_ANALYZER_SYSTEM),
            HumanMessage(content=f"简历全文：\n{resume_text[:12000]}"),
        ])
    except Exception as exc:
        logger.error("resume_analyzer_failed", error=str(exc))
        return _error_artifact(step, f"简历分析失败: {exc}")

    return {
        "resume_profile": profile,
        **_ok_artifact(step, f"画像抽取完成：{len(profile.skills)} 项技能 / {profile.experience_years} 年经验"),
    }


# ---------------- JobSearcher ----------------

async def job_searcher_node(state: dict) -> dict:
    step: dict = state["step"]
    context: dict = state.get("context", {})
    emit("agent_start", "JobSearcher", {"desc": step.get("description", "")})

    # 岗位搜索同样依赖 Serper；无 Key 时给出可操作提示，而非静默失败
    if context.get("web_search_available") is False:
        return _error_artifact(
            step,
            "岗位搜索未生效：当前未配置搜索服务密钥（Serper）。"
            "请到 设置 → 工具密钥 填入 Serper API Key 后重试。",
        )

    try:
        llm = role_llm("worker", context)

        # 1) 结构化搜索参数（修复 v1 参数不生效）
        query_model = llm.with_structured_output(JobSearchQuery)
        profile_block = ""
        if state.get("resume_profile"):
            p = state["resume_profile"]
            profile_block = f"简历画像：技能={p['skills']}，经验={p['experience_years']}年\n"
        query: JobSearchQuery = await query_model.ainvoke(
            f"{js_prompts.JOB_QUERY_SYSTEM}\n\n{profile_block}任务：{step.get('description', state.get('user_input', ''))}"
        )

        # 2) 工具调用（先落库再返回）
        emit("tool_call", "JobSearcher", {
            "tool": "job_search",
            "args_digest": f"keywords={query.keywords} location={query.location} limit={query.limit}",
        })
        search_result = await job_search_tool.arun(query.model_dump())
        if not search_result.ok or not search_result.data:
            # 兜底：Serper 对「关键词+城市+全职+远程」这类叠加条件的长查询偶发返回 0 条。
            # 放宽到「关键词+城市」再试一次，避免整步直接判死。
            relaxed = {
                "keywords": query.keywords,
                "location": query.location,
                "limit": query.limit,
            }
            if relaxed != query.model_dump():
                search_result = await job_search_tool.arun(relaxed)
        if not search_result.ok or not search_result.data:
            return _error_artifact(step, f"岗位搜索失败: {search_result.error or '无结果'}")

        # 3) 结构化筛选排序（外层必须包具名模型，裸 list[...] 会被 langchain 当函数解析而报错）
        rank_model = llm.with_structured_output(JobRanking)
        profile_json = json.dumps(_as_dict(state.get("resume_profile")), ensure_ascii=False)
        ranking: JobRanking = await rank_model.ainvoke(
            f"{js_prompts.JOB_RANK_SYSTEM.format(limit=query.limit)}\n\n"
            + (f"简历画像：{profile_json}\n" if state.get("resume_profile") else "")
            + f"原始岗位列表（JSON）：\n{json.dumps(search_result.data, ensure_ascii=False)}"
        )
        jobs: list[JobResult] = ranking.jobs
    except Exception as exc:
        logger.error("job_searcher_failed", error=str(exc))
        return _error_artifact(step, f"岗位搜索失败: {exc}")

    return {
        "job_results": jobs,
        **_ok_artifact(step, f"检索到 {len(jobs)} 个相关岗位"),
    }


# ---------------- WebResearcher ----------------

async def web_researcher_node(state: dict) -> dict:
    step: dict = state["step"]
    context: dict = state.get("context", {})
    emit("agent_start", "WebResearcher", {"desc": step.get("description", "")})

    # 没有 Serper Key 时直接给出可操作提示，避免无谓的 403 与"假检索"
    if context.get("web_search_available") is False:
        return _error_artifact(step, NO_SERPER_HINT)

    # 研究目标：步骤描述 + 黑板中的公司线索
    companies = [_as_dict(j).get("company", "") for j in (state.get("job_results") or [])]
    companies = [c for c in companies if c][:3]
    goal = step.get("description", state.get("user_input", ""))
    if companies:
        goal = f"{goal}（重点关注公司：{('、'.join(companies))}）"

    try:
        research: CompanyResearch = await deep_research(goal, context)
    except Exception as exc:
        logger.error("web_researcher_failed", error=str(exc))
        return _error_artifact(step, f"深度调研失败: {exc}")

    return {
        "company_research": research,
        **_ok_artifact(step, f"调研完成：{research.company or '目标'}，引用 {len(research.sources)} 个来源"),
    }


# ---------------- CoverLetterGenerator ----------------

def _letter_context_block(state: dict) -> str:
    blocks: list[str] = []
    if state.get("resume_profile"):
        p = _as_dict(state.get("resume_profile"))
        blocks.append(
            f"【简历画像】\n技能：{', '.join(p.get('skills', []))}\n经验年限：{p.get('experience_years')}\n"
            f"亮点：\n- " + "\n- ".join(p.get("highlights", []))
        )
    jobs = state.get("job_results") or []
    if jobs:
        top = _as_dict(jobs[0])
        blocks.append(
            f"【目标岗位】\n职位：{top.get('title', '')}\n公司：{top.get('company', '')}\n"
            f"地点：{top.get('location', '')}\n链接：{top.get('url', '')}"
        )
    if state.get("company_research"):
        r = _as_dict(state.get("company_research"))
        blocks.append(
            f"【公司调研】\n{r.get('overview', '')[:500]}\n技术栈：{', '.join(r.get('tech_stack', [])[:10])}"
        )
    return "\n\n".join(blocks)


async def cover_letter_generator_node(state: dict) -> dict:
    step: dict = state["step"]
    context: dict = state.get("context", {})
    emit("agent_start", "CoverLetterGenerator", {"desc": step.get("description", "")})

    if not state.get("resume_profile"):
        return _error_artifact(step, "缺少简历画像，无法撰写求职信")

    try:
        llm = role_llm("writer", context)
        letter: str = await llm.ainvoke([
            SystemMessage(content=cl_prompts.WRITER_SYSTEM),
            HumanMessage(content=_letter_context_block(state)),
        ])
        letter = letter.content.strip()
    except Exception as exc:
        logger.error("cover_letter_generator_failed", error=str(exc))
        return _error_artifact(step, f"求职信生成失败: {exc}")

    return {
        "cover_letter": letter,
        **_ok_artifact(step, "求职信初稿完成"),
    }


async def revise_letter_node(state: dict) -> dict:
    """Critic 未达标时的修订节点：质检意见回注重写（≤2 次）。"""
    context: dict = state.get("context", {})
    emit("agent_start", "CoverLetterGenerator", {"desc": "根据质检意见修订求职信"})

    critic = _as_dict(state.get("critic"))
    suggestions = "\n".join(f"- {s}" for s in critic.get("suggestions", []))
    revision_hint = (
        f"质检评分：{json.dumps(critic.get('scores', {}), ensure_ascii=False)}（未达标）。\n"
        f"质检意见：\n{suggestions}"
    )

    try:
        llm = role_llm("writer", context)
        letter: str = await llm.ainvoke([
            SystemMessage(content=cl_prompts.WRITER_REVISION_SYSTEM.format(
                revision_hint=revision_hint,
                original_letter=state.get("cover_letter", ""),
            )),
            HumanMessage(content=_letter_context_block(state)),
        ])
        letter = letter.content.strip()
    except Exception as exc:
        logger.error("revise_letter_failed", error=str(exc))
        return {"cover_letter": state.get("cover_letter", "")}  # 保留旧稿进入 HITL

    return {"cover_letter": letter, "revision_count": state.get("revision_count", 0) + 1}


# ---------------- ChatBot（闲聊短路） ----------------

def _resume_context_block(state: dict) -> str:
    """ChatBot 用的简历上下文：画像优先，全文截断兜底（会话显式绑定简历时才有）。"""
    blocks: list[str] = []
    profile = _as_dict(state.get("resume_profile"))
    if profile:
        lines = [f"技能：{', '.join(profile.get('skills', []))}",
                 f"经验年限：{profile.get('experience_years')}"]
        highlights = profile.get("highlights") or []
        if highlights:
            lines.append("亮点：\n- " + "\n- ".join(highlights))
        blocks.append("【简历画像】\n" + "\n".join(lines))
    resume_text = (_as_dict(state.get("context")).get("resume_text") or "").strip()
    if resume_text:
        blocks.append(f"【简历全文（截断）】\n{resume_text[:4000]}")
    return "\n\n".join(blocks)


async def chatbot_node(state: dict) -> dict:
    context: dict = state.get("context", {})
    memories = context.get("memories") or []
    system = sy_prompts.CHATBOT_SYSTEM
    if memories:
        system += "\n\n用户长期记忆（自然参考，不必复述）：" + "；".join(memories[:5])

    # 会话显式绑定简历时，让 ChatBot 真正"看得到"简历，
    # 否则用户问"你能看到我的参考简历吗"会得到否定回答
    resume_block = _resume_context_block(state)
    if resume_block:
        system += "\n\n用户为本会话关联了参考简历，回答简历相关问题时以下面内容为准：\n" + resume_block
    else:
        available = context.get("available_resumes") or []
        if available:
            listing = "；".join(
                f"v{r.get('version')} {r.get('filename')}"
                + ("（已就绪）" if r.get("status") == "ready" else f"（{r.get('status')}）")
                for r in available
            )
            system += (
                "\n\n【本会话尚未关联简历】用户「简历中心」里已有这些版本：" + listing +
                "。若用户想分析或使用简历，不要回答「看不到」，"
                "直接告诉他：在输入框左侧点回形针可以选择关联其中一份，或上传新的 PDF；"
                "关联后你就能读取并分析。"
            )

    emit("agent_start", "ChatBot", {"desc": "对话回复"})

    # 联网开关的"诚实提示"必须出现在**答案**里：Planner 的约束不进 ChatBot 的 prompt，
    # 只在计划阶段提示的话，用户点开开关后看到的仍是普通回答（开关形同无效）。
    if context.get("web_search"):
        if context.get("web_search_available", True):
            system += (
                "\n\n用户已开启「联网搜索」，但本轮走的是直接对话（未触发检索）。"
                "若问题涉及实时/最新信息，请明确说明，并提示用户把问题问得更具体以便触发检索。"
            )
        else:
            system += (
                "\n\n用户开启了「联网搜索」，但当前**没有配置搜索服务密钥（Serper）**，无法联网。"
                "请务必在回答**开头第一句**原样说明："
                "「联网搜索未生效：到 设置 → 工具密钥 填入 Serper API Key 后可用」，"
                "然后基于已有知识作答，不要假装检索过、不要编造来源。"
            )

    try:
        llm = role_llm("worker", context, streaming=True)
        msgs = list(state.get("messages", []))
        user_turns = [m for m in msgs if isinstance(m, HumanMessage)]
        logger.info(
            "chatbot_prompt",
            n_messages=len(msgs),
            n_user_turns=len(user_turns),
            last_user=(getattr(user_turns[-1], "content", "") if user_turns else "")[:60],
        )
        reply = await llm.ainvoke([SystemMessage(content=system)] + msgs)
        content = reply.content
    except Exception as exc:
        # 不再吞掉原因：把真实错误透出，便于用户去设置页定位（Key / Base URL / 模型名）
        reason = str(exc).strip().replace("\n", " ")[:300]
        logger.error("chatbot_failed", error=reason)
        content = (
            "⚠️ **对话生成失败**\n\n"
            f"```\n{reason}\n```\n\n"
            "> 请到「系统设置 → 大模型配置」检查 API Key、Base URL 与模型名，"
            "并点「测试连接」确认可用后重试。"
        )

    return {
        "final_message": content,
        "messages": [AIMessage(content=content, name="ChatBot")],
    }
