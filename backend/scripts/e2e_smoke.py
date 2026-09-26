"""端到端验证：用假 LLM 跑通整张图。

验证链路：Planner(DAG) → Executor(Send 并行 s2/s3) → CoverLetterGenerator
        → Synthesizer → Critic → HITL interrupt → 恢复 → Finish
不依赖真实 LLM / MySQL / Redis（无网络调用）。
"""
import asyncio

from langchain_core.messages import AIMessage
from app.agents.graph.checkpoint import build_serde
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

import app.agents.graph.builder as builder
import app.agents.graph.critic as critic_mod
import app.agents.graph.planner as planner_mod
import app.agents.graph.synthesizer as synth_mod
import app.agents.graph.workers as workers_mod
from app.agents.graph.state import (
    CompanyResearch, CriticResult, JobResult, JobSearchQuery, Plan, PlanStep, ResumeProfile,
)

RESUME_TEXT = "张三｜5 年 Python/LLM 开发经验｜硕士｜A 公司算法工程师"
LETTER = "尊敬的 HR：我具备 5 年 Python 与大模型研发经验……"


class ScriptedLLM:
    """按调用顺序返回预置结果：结构化输出走 with_structured_output，文本走 ainvoke。"""

    def __init__(self, outputs: list):
        self.outputs = list(outputs)
        self.i = 0

    def _next(self):
        if self.i >= len(self.outputs):
            raise RuntimeError(f"假 LLM 输出已用尽（第 {self.i + 1} 次调用）")
        v = self.outputs[self.i]
        self.i += 1
        return v

    def with_structured_output(self, schema, **kwargs):
        outer = self

        class _Structured:
            async def ainvoke(self, *args, **kw):
                return outer._next()
        return _Structured()

    async def ainvoke(self, *args, **kwargs):
        v = self._next()
        return AIMessage(content=v if isinstance(v, str) else str(v))


class FakeToolResult:
    ok = True
    error = ""
    data = [{
        "job_posting_id": 1, "title": "LLM 算法工程师", "company": "Acme",
        "location": "北京", "snippet": "要求 Python、LLM", "url": "https://example.com/j/1",
        "date": "",
    }]


async def run_case(name: str, outputs: list, thread_id: str) -> dict:
    """跑一次完整编排，返回 (事件序列, 最终状态)。"""
    llm = ScriptedLLM(outputs)

    for mod in (planner_mod, workers_mod, synth_mod, critic_mod):
        mod.role_llm = lambda role, context: llm
    workers_mod.job_search_tool = type("T", (), {
        "arun": staticmethod(lambda payload: asyncio.sleep(0, result=FakeToolResult()))
    })()
    workers_mod.deep_research = lambda goal, context: asyncio.sleep(0, result=outputs[-1]["research"])

    graph = builder.build_graph(checkpointer=InMemorySaver(serde=build_serde()))
    config = {"configurable": {"thread_id": thread_id}}
    initial = {
        "user_input": "帮我找北京的大模型岗位，并针对最匹配的写求职信",
        "context": {"resume_text": RESUME_TEXT, "resume_ready": True, "user_id": 1},
        "results": {"__reset__": True},
        "revision_count": 0,
    }

    seen: list[str] = []
    async for mode, chunk in graph.astream(initial, config, stream_mode=["custom", "updates"]):
        if mode == "custom":
            seen.append(f"{chunk['type']}@{chunk['node']}")
        elif "__interrupt__" in (chunk or {}):
            seen.append("INTERRUPTED")

    snap = await graph.aget_state(config)
    print(f"\n=== {name} 事件序列 ===")
    print(" → ".join(seen))
    return {"seen": seen, "values": snap.values, "graph": graph, "config": config}


async def main() -> None:
    profile = ResumeProfile(skills=["Python", "LLM"], experience_years=5.0,
                            highlights=["主导 RAG 系统"], raw_analysis="画像完成")
    jobs = [JobResult(job_posting_id=1, title="LLM 算法工程师", company="Acme",
                      location="北京", url="https://example.com/j/1")]
    research = CompanyResearch(company="Acme", overview="AI 公司", sources=["https://a.com"])
    plan = Plan(steps=[
        PlanStep(id="s1", agent="ResumeAnalyzer", description="分析简历"),
        PlanStep(id="s2", agent="JobSearcher", description="搜北京 LLM 岗位", depends_on=["s1"]),
        PlanStep(id="s3", agent="WebResearcher", description="调研头部公司", depends_on=["s1"]),
        PlanStep(id="s4", agent="CoverLetterGenerator", description="写求职信",
                 depends_on=["s2", "s3"]),
    ])
    LETTER_V1 = "尊敬的 HR：我具备 5 年 Python 与大模型研发经验……（v1）"
    LETTER_V2 = "尊敬的 HR：我具备 5 年 Python 与大模型研发经验……（v2 修订版）"

    # ---------- 场景 1：Critic 一次通过 ----------
    case1 = await run_case("场景1 · Critic 一次通过", [
        plan, profile,
        JobSearchQuery(keywords="LLM 算法工程师", location="北京", limit=5), jobs,
        LETTER_V1, "为您找到 1 个北京 LLM 岗位。",
        CriticResult(scores={"relevance": 8, "professionalism": 8, "truthfulness": 9,
                             "conciseness": 8}, passed=True, suggestions=[]),
        {"research": research},
    ], thread_id="e2e-1")

    v = case1["values"]
    results = v.get("results", {})
    print("\n=== 场景1 黑板产物 ===")
    print("完成步骤:", sorted(results.keys()))
    print("画像技能:", v.get("resume_profile").skills if v.get("resume_profile") else None)
    print("岗位数:", len(v.get("job_results") or []))
    print("调研公司:", v.get("company_research").company if v.get("company_research") else None)
    print("求职信:", (v.get("cover_letter") or "")[:34], "…")
    print("Critic passed:", v.get("critic").passed if v.get("critic") else None)
    print("最终回答:", v.get("final_message"))

    ok1 = (
        all(k in results for k in ("s1", "s2", "s3", "s4"))
        and all(r.get("ok") for r in results.values())
        and "INTERRUPTED" in case1["seen"]
        and bool(v.get("cover_letter"))
        and v.get("revision_count", 0) == 0
    )
    print("编排正确性:", "✅ 通过" if ok1 else "❌ 未通过")

    resumed = await case1["graph"].ainvoke(Command(resume=True), case1["config"])
    print("HITL 恢复 human_decision:", resumed.get("human_decision"))

    # ---------- 场景 2：Critic 未通过 → 修订 → 复检通过 ----------
    case2 = await run_case("场景2 · Critic 未通过触发修订", [
        plan, profile,
        JobSearchQuery(keywords="LLM 算法工程师", location="北京", limit=5), jobs,
        LETTER_V1, "为您找到 1 个北京 LLM 岗位。",
        CriticResult(scores={"relevance": 5, "professionalism": 7, "truthfulness": 6,
                             "conciseness": 7}, passed=False,
                     suggestions=["补充量化成果", "删除简历中不存在的经历"]),
        LETTER_V2,
        CriticResult(scores={"relevance": 8, "professionalism": 8, "truthfulness": 9,
                             "conciseness": 8}, passed=True, suggestions=[]),
        {"research": research},
    ], thread_id="e2e-2")

    v2 = case2["values"]
    print("\n=== 场景2 黑板产物 ===")
    print("修订次数:", v2.get("revision_count"))
    print("最终求职信:", (v2.get("cover_letter") or "")[:34], "…")
    print("Critic passed:", v2.get("critic").passed if v2.get("critic") else None)
    revised = (v2.get("cover_letter") or "").endswith("（v2 修订版）")
    ok2 = (
        v2.get("revision_count") == 1
        and revised
        and v2.get("critic").passed is True
        and "INTERRUPTED" in case2["seen"]
    )
    print("修订闭环:", "✅ 通过" if ok2 else f"❌ 未通过 (revision_count={v2.get('revision_count')})")

    print("\n总结:", "✅ 全部通过" if ok1 and ok2 else "❌ 存在未通过项")


if __name__ == "__main__":
    asyncio.run(main())
