"""结构化匹配评分（方案 7.2 节）：可解释，与"让 LLM 直接打分"的本质区别。

总分 = 加权(技能匹配度 0.5, 经验匹配度 0.3, 语义相关度 0.2)
"""
import re

from pydantic import BaseModel, Field

from app.agents.graph.state import ResumeProfile


class SkillMatch(BaseModel):
    covered: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    score: float = 0.0  # 0-1


class ExperienceMatch(BaseModel):
    required_years: float | None = None
    actual_years: float = 0.0
    score: float = 0.0  # 0-1
    note: str = ""


class MatchScore(BaseModel):
    overall: float
    skill_match: SkillMatch
    experience_match: ExperienceMatch
    semantic_score: float = 0.0

    @property
    def passed_hard_filter(self) -> bool:
        return True


WEIGHT_SKILL = 0.5
WEIGHT_EXPERIENCE = 0.3
WEIGHT_SEMANTIC = 0.2

# 常见技能别名归一（解决 "Python" ≈ "熟悉 Python 开发"）
SKILL_ALIASES: dict[str, set[str]] = {
    "python": {"python", "python3", "python开发", "熟悉python"},
    "javascript": {"javascript", "js", "es6"},
    "typescript": {"typescript", "ts"},
    "机器学习": {"机器学习", "machine learning", "ml"},
    "深度学习": {"深度学习", "deep learning", "dl"},
    "大模型": {"大模型", "llm", "large language model", "大语言模型"},
    "nlp": {"nlp", "自然语言处理", "natural language processing"},
    "cv": {"cv", "计算机视觉", "computer vision"},
    "docker": {"docker", "容器"},
    "kubernetes": {"kubernetes", "k8s"},
    "sql": {"sql", "mysql", "数据库"},
}


# JD/简历里常见的修饰词，归一时剔除（"熟悉 Python 开发" → "python"）
FILLERS = ("熟悉", "精通", "熟练", "掌握", "了解", "具备", "使用", "者优先", "优先",
           "开发", "经验", "编程", "技能", "能力", "framework", "skills", "skill")


def _normalize(skill: str) -> str:
    return re.sub(r"\s+", "", skill.strip().lower())


def _canonical(skill: str) -> str:
    """去掉修饰词后的技能主体。"""
    s = _normalize(skill)
    for filler in FILLERS:
        s = s.replace(filler, "")
    return s or _normalize(skill)


def _alias_key(normalized: str) -> str | None:
    for canonical, aliases in SKILL_ALIASES.items():
        if normalized in aliases:
            return canonical
    return None


def _hit(req_canon: str, resume_canons: set[str], resume_keys: set[str]) -> bool:
    """单条技能是否命中：精确 → 别名 → 包含（长度≥3，解决 "Python"≈"熟悉 Python 开发"）。"""
    if not req_canon:
        return False
    if req_canon in resume_canons or req_canon in resume_keys:
        return True
    alias = _alias_key(req_canon)
    if alias and (alias in resume_keys or alias in resume_canons):
        return True
    if len(req_canon) >= 3:
        for c in resume_canons:
            if req_canon in c or c in req_canon:
                return True
    return False


def match_skills(resume_skills: list[str], jd_required: list[str]) -> SkillMatch:
    """简历 skills 与 JD required_skills 集合比对（含别名归一与包含匹配）。"""
    resume_canons = {_canonical(s) for s in resume_skills if s.strip()}
    resume_keys = {_alias_key(c) or c for c in resume_canons}

    covered: list[str] = []
    missing: list[str] = []
    for req in jd_required:
        if not req.strip():
            continue
        hit = _hit(_canonical(req), resume_canons, resume_keys)
        (covered if hit else missing).append(req)

    score = len(covered) / len(jd_required) if jd_required else 0.5
    return SkillMatch(covered=covered, missing=missing, score=round(min(score, 1.0), 4))


def match_experience(profile_years: float, required_years: float | None) -> ExperienceMatch:
    """JD 要求年限 vs 画像经验年限。"""
    if required_years is None:
        return ExperienceMatch(
            actual_years=profile_years, score=0.7, note="JD 未明确年限要求"
        )
    if profile_years >= required_years:
        return ExperienceMatch(
            required_years=required_years, actual_years=profile_years,
            score=1.0, note=f"满足 {required_years} 年要求",
        )
    # 差距线性惩罚
    ratio = profile_years / required_years if required_years > 0 else 0.0
    return ExperienceMatch(
        required_years=required_years, actual_years=profile_years,
        score=round(max(ratio, 0.0), 4),
        note=f"JD 要求 {required_years} 年，画像 {profile_years} 年",
    )


def extract_required_years(text: str) -> float | None:
    """从 JD 文本抽取年限要求（"3年以上"、"3-5年"取下限）。"""
    m = re.search(r"(\d+)\s*[-~到至]\s*(\d+)\s*年", text)
    if m:
        return float(m.group(1))
    m = re.search(r"(\d+)\s*\+?\s*年(?:以上)?", text)
    if m:
        return float(m.group(1))
    return None


def score_match(profile: ResumeProfile, jd_required_skills: list[str],
                jd_text: str, semantic_score: float) -> MatchScore:
    """总分 = 技能×0.5 + 经验×0.3 + 语义×0.2。全部维度可解释入库。"""
    skill = match_skills(profile.skills, jd_required_skills)
    exp = match_experience(profile.experience_years, extract_required_years(jd_text))
    overall = (
        WEIGHT_SKILL * skill.score
        + WEIGHT_EXPERIENCE * exp.score
        + WEIGHT_SEMANTIC * semantic_score
    )
    return MatchScore(
        overall=round(min(overall, 1.0), 4),
        skill_match=skill,
        experience_match=exp,
        semantic_score=round(semantic_score, 4),
    )
