"""Executor 调度逻辑单测（不依赖 LLM / DB）。"""
from app.agents.graph.executor import all_done, ready_steps
from app.agents.graph.planner import _context_block, route_after_planner
from app.agents.graph.state import Plan, PlanStep, merge_step_results, RESET_KEY


def _plan() -> Plan:
    return Plan(steps=[
        PlanStep(id="s1", agent="ResumeAnalyzer", description="分析简历"),
        PlanStep(id="s2", agent="JobSearcher", description="搜岗位", depends_on=["s1"]),
        PlanStep(id="s3", agent="WebResearcher", description="调研", depends_on=["s1"]),
    ])


def test_ready_steps_first_superstep():
    ready = ready_steps(_plan(), {})
    assert [s.id for s in ready] == ["s1"]


def test_parallel_after_s1():
    # s1 完成后，s2 与 s3 无相互依赖 → 同一超步并行
    ready = ready_steps(_plan(), {"s1": {"ok": True}})
    assert sorted(s.id for s in ready) == ["s2", "s3"]


def test_all_done():
    assert all_done(_plan(), {"s1": {}, "s2": {}, "s3": {}})
    assert not all_done(_plan(), {"s1": {}})


def test_route_after_planner():
    assert route_after_planner({"plan": Plan(steps=[], is_simple_chat=True)}) == "ChatBot"
    assert route_after_planner({"plan": _plan()}) == "executor"
    assert route_after_planner({}) == "ChatBot"


def test_merge_reset_and_accumulate():
    assert merge_step_results({"a": 1}, {RESET_KEY: True}) == {}
    assert merge_step_results({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}


def test_context_block_web_search_available():
    """联网可用：要求真的检索；不可用：要求给出可操作提示，禁止假装检索。"""
    ok = _context_block({"web_search": True, "web_search_available": True})
    assert "WebSearcher" in ok and "必须" in ok

    bad = _context_block({"web_search": True, "web_search_available": False})
    assert "Serper" in bad
    assert "WebSearcher" in bad and "不要规划" in bad


def test_context_block_ignores_web_search_when_off():
    block = _context_block({"web_search": False, "web_search_available": False})
    assert "Serper" not in block


def test_context_block_lists_available_resumes():
    block = _context_block({
        "resume_ready": False,
        "available_resumes": [{"id": 1, "version": 2, "filename": "cv.pdf", "status": "ready"}],
    })
    assert "cv.pdf" in block and "回形针" in block
