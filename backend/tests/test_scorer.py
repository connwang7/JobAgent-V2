from app.matching.scorer import (
    extract_required_years, match_experience, match_skills, score_match,
)
from app.agents.graph.state import ResumeProfile


def test_match_skills_covers_and_missing():
    ms = match_skills(["Python", "LangGraph", "MySQL"], ["python", "RAG", "MySQL"])
    assert "python" in ms.covered  # 大小写归一
    assert "RAG" in ms.missing
    assert 0 < ms.score < 1


def test_match_skills_alias():
    # "熟悉 Python 开发" ≈ "Python"
    ms = match_skills(["熟悉Python开发"], ["Python"])
    assert ms.covered == ["Python"]
    assert ms.score == 1.0


def test_match_experience():
    ok = match_experience(5.0, 3.0)
    assert ok.score == 1.0
    short = match_experience(1.5, 3.0)
    assert short.score == 0.5
    unknown = match_experience(2.0, None)
    assert unknown.score == 0.7


def test_extract_required_years():
    assert extract_required_years("要求 3 年以上经验") == 3.0
    assert extract_required_years("3-5年经验") == 3.0


def test_score_match_weighted_and_explainable():
    profile = ResumeProfile(skills=["Python", "LLM"], experience_years=4.0, highlights=[])
    ms = score_match(profile, ["Python", "LLM"], "要求 3 年以上经验", semantic_score=0.8)
    # 技能 1.0*0.5 + 经验 1.0*0.3 + 语义 0.8*0.2 = 0.96
    assert abs(ms.overall - 0.96) < 1e-6
    assert ms.skill_match.missing == []
