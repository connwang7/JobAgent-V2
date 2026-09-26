"""图装配正确性检查（不需要 LLM 调用，仅验证图结构可编译）。"""
from app.agents.graph.builder import build_graph


def test_graph_compiles_and_has_expected_nodes():
    graph = build_graph(checkpointer=None)
    nodes = set(graph.nodes)
    for expected in {
        "planner", "executor", "ResumeAnalyzer", "JobSearcher", "WebResearcher",
        "CoverLetterGenerator", "revise_letter", "ChatBot", "synthesizer",
        "critic", "hitl", "finish", "__start__",
    }:
        assert expected in nodes, expected
