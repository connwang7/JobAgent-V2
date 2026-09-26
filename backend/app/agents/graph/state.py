"""State 黑板设计（方案 6.3 节）。

一切 Agent 间通信走 Pydantic 结构化产物（artifact），图状态即共享黑板，
Agent 只读写自己负责的字段。
"""
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


# ---------- 结构化产物（artifact） ----------

class PlanStep(BaseModel):
    id: str
    agent: Literal["ResumeAnalyzer", "JobSearcher", "WebResearcher",
                   "CoverLetterGenerator", "ChatBot"]
    description: str
    depends_on: list[str] = Field(default_factory=list)


class Plan(BaseModel):
    steps: list[PlanStep]
    is_simple_chat: bool = False  # 闲聊直连 ChatBot，跳过编排


class ResumeProfile(BaseModel):
    """结构化简历画像（替代 v1 的整段文本）。"""
    basic: dict = Field(default_factory=dict)
    skills: list[str] = Field(default_factory=list)
    experience_years: float = 0.0
    highlights: list[str] = Field(default_factory=list)
    raw_analysis: str = ""  # 供展示的叙事分析


class JobResult(BaseModel):
    job_posting_id: int | None = None
    title: str = ""
    company: str = ""
    location: str = ""
    url: str = ""
    salary_text: str = ""
    match_reason: str = ""  # 为什么推荐该岗位（一句话）


class JobRanking(BaseModel):
    """排序结果的外层包装。

    `with_structured_output(list[JobResult])` 会直接把裸泛型交给
    `langchain_openai._convert_to_openai_response_format`，它误判为「函数」并调用
    `typing.get_type_hints(list[...])`，抛
    `TypeError: list[...] is not a module, class, method, or function`。
    所以结构化输出**必须**用一个具名 BaseModel 包住列表。
    """
    jobs: list[JobResult] = Field(default_factory=list)


class CompanyResearch(BaseModel):
    company: str = ""
    overview: str = ""
    culture: str = ""
    tech_stack: list[str] = Field(default_factory=list)
    recent_news: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)  # 引用来源 URL，抑制编造


class CriticResult(BaseModel):
    scores: dict[str, float] = Field(default_factory=dict)  # 针对性/专业度/真实性/简洁度
    passed: bool = False
    suggestions: list[str] = Field(default_factory=list)


class JobSearchQuery(BaseModel):
    """JobSearcher 第一步结构化输出：搜索参数（v1 参数未生效的问题在此修复）。"""
    keywords: str = Field(description="岗位关键词，如 '大模型 LLM 算法工程师'")
    location: str = Field(default="", description="城市，如 '北京'；不限则留空")
    employment_type: str = Field(default="", description="全职/实习/兼职等；不限留空")
    remote: bool = Field(default=False, description="是否只看远程")
    limit: int = Field(default=10, ge=1, le=20)


# ---------- results 字段 reducer：dict 合并；planner 写入 __reset__ 归零 ----------

RESET_KEY = "__reset__"


def merge_step_results(old: dict | None, new: dict | None) -> dict:
    old = old or {}
    new = new or {}
    if new.get(RESET_KEY):
        return {k: v for k, v in new.items() if k != RESET_KEY}
    return {**old, **new}


class AgentState(TypedDict, total=False):
    user_input: str
    messages: Annotated[list[BaseMessage], add_messages]

    # —— 计划与执行进度 ——
    plan: Plan
    # step_id → artifact 摘要（含 error），由 reducer 合并；跨轮次由 planner 重置
    results: Annotated[dict[str, Any], merge_step_results]

    # —— 黑板字段：各 Agent 只写自己负责的 ——
    resume_profile: ResumeProfile
    job_results: list[JobResult]
    company_research: CompanyResearch
    cover_letter: str
    critic: CriticResult
    revision_count: int
    human_decision: bool
    final_message: str

    # —— 上下文（服务层注入，非用户输入） ——
    context: dict  # user_id / resume_id / run_id / preferences / memories ...


def make_initial_state(user_input: str, context: dict) -> AgentState:
    return {
        "user_input": user_input,
        "context": context,
        "revision_count": 0,
        "results": {RESET_KEY: True},
    }
