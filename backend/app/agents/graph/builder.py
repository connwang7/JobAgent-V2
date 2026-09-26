"""图装配（方案 6.2 节）：

    Planner → Executor(Send 并行超步) ↺ → Synthesizer
                                        ├─ 有求职信 → Critic ↺(修订≤2) → HITL → Finish
                                        └─ 无求职信 → Finish
    Planner → ChatBot（闲聊短路）→ Finish
"""
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agents.graph.checkpoint import checkpoint_manager
from app.agents.graph.critic import critic_node, route_after_critic
from app.agents.graph.executor import executor_node, route_executor
from app.agents.graph.finish import finish_node
from app.agents.graph.hitl import hitl_node
from app.agents.graph.planner import planner_node, route_after_planner
from app.agents.graph.state import AgentState
from app.agents.graph.synthesizer import synthesizer_node, route_after_synthesizer
from app.agents.graph.workers import (
    chatbot_node, cover_letter_generator_node, job_searcher_node,
    resume_analyzer_node, revise_letter_node, web_researcher_node,
)

WORKER_NODES = ["ResumeAnalyzer", "JobSearcher", "WebResearcher", "CoverLetterGenerator"]


def build_graph(checkpointer=None) -> CompiledStateGraph:
    workflow = StateGraph(AgentState)

    workflow.add_node("planner", planner_node)
    workflow.add_node("executor", executor_node)
    workflow.add_node("ResumeAnalyzer", resume_analyzer_node)
    workflow.add_node("JobSearcher", job_searcher_node)
    workflow.add_node("WebResearcher", web_researcher_node)
    workflow.add_node("CoverLetterGenerator", cover_letter_generator_node)
    workflow.add_node("revise_letter", revise_letter_node)
    workflow.add_node("ChatBot", chatbot_node)
    workflow.add_node("synthesizer", synthesizer_node)
    workflow.add_node("critic", critic_node)
    workflow.add_node("hitl", hitl_node)
    workflow.add_node("finish", finish_node)

    workflow.add_edge(START, "planner")
    workflow.add_conditional_edges("planner", route_after_planner, ["executor", "ChatBot"])

    # Executor 超步：ready 步骤并行 Send；全部完成 → synthesizer
    workflow.add_conditional_edges(
        "executor", route_executor,
        [*WORKER_NODES, "synthesizer"],
    )
    # 各 Agent 完成后回到 executor 评估下一超步
    for node in WORKER_NODES:
        workflow.add_edge(node, "executor")

    workflow.add_edge("ChatBot", "finish")

    workflow.add_conditional_edges("synthesizer", route_after_synthesizer, ["critic", "finish"])
    workflow.add_conditional_edges("critic", route_after_critic, ["revise_letter", "hitl"])
    workflow.add_edge("revise_letter", "critic")
    workflow.add_edge("hitl", "finish")
    workflow.add_edge("finish", END)

    return workflow.compile(checkpointer=checkpointer)


# 进程级单例（checkpointer 由 main.py lifespan 注入后重建）
_graph: CompiledStateGraph | None = None


def get_graph() -> CompiledStateGraph:
    global _graph
    if _graph is None:
        _graph = build_graph(checkpointer=checkpoint_manager.saver)
    return _graph


def reset_graph() -> None:
    """checkpointer 就绪后调用，重建图单例。"""
    global _graph
    _graph = None
