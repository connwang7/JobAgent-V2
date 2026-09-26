"""回归：结构化输出的 schema 必须能被 langchain 绑定成 OpenAI response_format。

背景（真踩过的坑）：
`llm.with_structured_output(list[JobResult])` 会把裸泛型传给
`langchain_openai._convert_to_openai_response_format`，后者误判为「函数」并执行
`typing.get_type_hints(list[...])`，抛
`TypeError: list[...] is not a module, class, method, or function`。
JobSearcher 因此在"排序"一步必然失败（无 Serper Key 时它根本不执行，所以长期没被发现）。
"""
import pytest
from langchain_openai import ChatOpenAI

from app.agents.graph.state import JobRanking, JobResult


def _llm() -> ChatOpenAI:
    return ChatOpenAI(api_key="sk-test", model="gpt-4o-mini")


def test_job_ranking_is_bindable():
    assert _llm().with_structured_output(JobRanking) is not None


def test_bare_generic_schema_is_rejected():
    """固化约束：不要写回 `with_structured_output(list[X])`。"""
    with pytest.raises(TypeError):
        _llm().with_structured_output(list[JobResult])
