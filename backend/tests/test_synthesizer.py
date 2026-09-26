"""Synthesizer 素材拼装单测（不依赖 LLM）。"""
from app.agents.graph.state import CompanyResearch
from app.agents.graph.synthesizer import _blackboard_summary


def test_research_sources_are_passed_through():
    """来源 URL 必须进入综合素材，否则答案里只剩不可点击的域名。"""
    state = {
        "company_research": CompanyResearch(
            company="某公司",
            overview="概览",
            recent_news=["动态A"],
            sources=["https://www.chinadaily.com.cn/a", "https://36kr.com/p/1"],
        ),
    }
    out = _blackboard_summary(state)
    assert "https://www.chinadaily.com.cn/a" in out
    assert "https://36kr.com/p/1" in out
    assert "来源链接" in out


def test_failed_artifacts_surface_with_error():
    state = {"results": {"s1": {"agent": "WebResearcher", "ok": False, "error": "未配置 Serper"}}}
    out = _blackboard_summary(state)
    assert "执行失败" in out and "未配置 Serper" in out
