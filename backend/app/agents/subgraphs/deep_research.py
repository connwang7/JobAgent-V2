"""WebResearcher 深度研究子图（方案 6.8 节）。

search → assess(信息缺口评估) → 缺失且轮次<3 → 补搜(改写query) ↺
      → 覆盖或轮次耗尽 → synthesize(带引用来源的汇总)

实现为受控异步函数（循环次数硬上限），可整体被 Celery 异步任务复用。
"""
from pydantic import BaseModel, Field

from app.agents.llm.model_router import get_llm_for_role
from app.agents.prompts import web_researcher as prompts
from app.agents.tools import web_search, scrape_website
from app.core.injection_guard import wrap_untrusted


from app.agents.graph.state import CompanyResearch


class ResearchQuery(BaseModel):
    query: str = Field(min_length=1, max_length=128)


class ResearchAssessment(BaseModel):
    covered: bool = False
    missing_aspects: list[str] = Field(default_factory=list)
    next_query: str = ""


MAX_ROUNDS = 3
MAX_SCRAPE_PER_ROUND = 1  # 每轮最多精读 1 个页面，控制耗时


async def deep_research(goal: str, context: dict) -> CompanyResearch:
    """多轮 搜索-评估-补搜，最终带引用综合。"""
    llm = get_llm_for_role(
        "worker",
        context.get("llm_pref"),
        context.get("llm_api_key_enc", ""),
        context.get("llm_base_url", ""),
    )

    # 首轮查询规划
    q_model = llm.with_structured_output(ResearchQuery)
    current_query = (await q_model.ainvoke(
        f"研究目标：{goal}\n{prompts.RESEARCH_PLAN_SYSTEM}"
    )).query

    collected: list[dict] = []  # {title, link, snippet, content?}
    seen_urls: set[str] = set()

    for round_no in range(MAX_ROUNDS):
        result = await web_search.arun({"query": current_query, "num_results": 8})
        if result.ok and result.data:
            for item in result.data:
                if item.get("link") and item["link"] not in seen_urls:
                    seen_urls.add(item["link"])
                    collected.append(dict(item))

        # 精读 1 个最有希望的结果（补充正文，提高综合质量）
        if result.ok and result.data:
            best = result.data[0]
            scraped = await scrape_website.arun({"url": best.get("link", "")})
            if scraped.ok and scraped.data:
                for c in collected:
                    if c.get("link") == best.get("link"):
                        c["content"] = str(scraped.data)[:4000]
                        break

        # 信息缺口评估
        results_block = "\n\n".join(
            f"[{i+1}] {c.get('title','')}\nURL: {c.get('link','')}\n摘要: {c.get('snippet','')}\n"
            + (f"正文: {c['content'][:1500]}" if c.get("content") else "")
            for i, c in enumerate(collected)
        )
        assess_model = llm.with_structured_output(ResearchAssessment)
        assessment: ResearchAssessment = await assess_model.ainvoke(
            f"研究目标：{goal}\n\n已收集的搜索结果：\n{wrap_untrusted(results_block)}\n\n"
            f"当前为第 {round_no + 1}/{MAX_ROUNDS} 轮。\n{prompts.RESEARCH_ASSESS_SYSTEM}"
        )

        if assessment.covered or not assessment.next_query or round_no == MAX_ROUNDS - 1:
            break
        current_query = assessment.next_query

    # 综合（强制引用来源，抑制编造）
    final_block = "\n\n".join(
        f"[{i+1}] {c.get('title','')} ({c.get('link','')})\n"
        f"{c.get('snippet','')}\n{(c.get('content') or '')[:2000]}"
        for i, c in enumerate(collected)
    )
    synth_model = llm.with_structured_output(CompanyResearch)
    research: CompanyResearch = await synth_model.ainvoke(
        prompts.RESEARCH_SYNTH_SYSTEM.format(results_block=wrap_untrusted(final_block))
        + f"\n\n研究目标：{goal}"
    )
    if not research.sources:
        research.sources = [c["link"] for c in collected[:8] if c.get("link")]
    return research
