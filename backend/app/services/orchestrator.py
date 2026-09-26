"""编排服务：图的入口/出口，SSE 事件翻译、agent_events 落库、HITL 恢复。

替代 v1 的 app.py execute_chat_conversation + custom_callback_handler。
"""
import time
from collections.abc import AsyncGenerator

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage
from langgraph.types import Command
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph import get_graph
from app.agents.graph.events import extract_reasoning
from app.core.config import settings
from app.core.db import AsyncSessionLocal
from app.core.errors import AgentError, NotFoundError
from app.core.logging import logger
from app.core.security import decrypt_secret
from app.core.user_context import get_tool_key
from app.core.sse import (
    EVENT_AGENT_START, EVENT_ERROR, EVENT_FINAL, EVENT_INTERRUPT,
    EVENT_PLAN, EVENT_STATUS, EVENT_THINKING, EVENT_THINKING_DONE,
    EVENT_TOKEN, EVENT_TOOL_CALL, SSEEvent,
)
from app.models.chat import AgentEvent, AgentRun, Message, Session
from app.models.user import User
from app.repositories.chat import EventRepository, MessageRepository, RunRepository
from app.repositories.resume import ResumeRepository
from app.repositories.user import PreferenceRepository
from app.services import letter as letter_service
from app.services.memory import inject_memories

# 这些节点的 LLM 输出被视为最终答案，向用户流式输出 token
TOKEN_STREAM_NODES = {"synthesizer", "ChatBot"}


class OrchestratorService:
    """一个实例持有编译后的图（进程级复用）。"""

    # ---------- 对话主流程（SSE） ----------

    async def chat_stream(self, session_row: Session, user: User, content: str,
                          deep_thinking: bool = False, web_search: bool = False
                          ) -> AsyncGenerator[SSEEvent, None]:
        run_id: str | None = None
        interrupted = False
        thinking_started = False
        answer_started = False
        start = time.monotonic()
        try:
            async with AsyncSessionLocal() as db:
                # 1) 持久化用户消息 + 创建 run
                await MessageRepository(db).add(Message(
                    session_id=session_row.id, role="user", content=content,
                ))
                if session_row.title == "新会话":
                    session_row.title = content[:30]
                run = await RunRepository(db).add(AgentRun(
                    session_id=session_row.id, thread_id=session_row.id, status="running",
                ))
                await db.commit()
                run_id = run.id

                # 2) 组装上下文（黑板外的服务层注入）
                context = await self._build_context(db, user, session_row, content)
                context["deep_thinking"] = deep_thinking
                context["web_search"] = web_search

            yield SSEEvent(EVENT_STATUS, {
                "phase": "planning",
                "deep_thinking": deep_thinking,
                "web_search": web_search,
            })

            # 3) 图执行（流式）
            graph = get_graph()
            config = {
                "configurable": {"thread_id": session_row.id},
                "recursion_limit": 40,
            }
            initial = {
                "user_input": content,
                "context": context,
                "revision_count": 0,
                "results": {"__reset__": True},
                "messages": [HumanMessage(content=content)],
            }

            async for mode, chunk in graph.astream(
                initial, config, stream_mode=["custom", "messages", "updates"],
            ):
                if mode == "custom":
                    async for ev in self._handle_custom_event(
                        session_row, run_id, chunk
                    ):
                        if ev.event == EVENT_INTERRUPT:
                            interrupted = True
                        yield ev
                elif mode == "messages":
                    msg_chunk, metadata = chunk
                    node = (metadata or {}).get("langgraph_node", "")
                    if node not in TOKEN_STREAM_NODES:
                        continue
                    # 推理内容优先下发，前端渲染成"思考过程"折叠块
                    reasoning = extract_reasoning(msg_chunk)
                    if reasoning:
                        if answer_started:
                            continue  # 已开始出答案，忽略滞后的 reasoning
                        thinking_started = True
                        yield SSEEvent(EVENT_THINKING, {"content": reasoning})
                    body = getattr(msg_chunk, "content", "")
                    if body:
                        if thinking_started and not answer_started:
                            answer_started = True
                            yield SSEEvent(EVENT_THINKING_DONE, {
                                "elapsed_ms": int((time.monotonic() - start) * 1000),
                            })
                        # 防重复：LangGraph v1 的 messages 流在流式 token 全部发完后，
                        # 还会通过 on_llm_end（聚合结果）与节点输出回放把**整段消息**再发一遍，
                        # 且其 message.id 与流式 chunk 不同，自带 dedupe 失效。
                        # 表现：前端把全文叠加两遍。这里 answer 开始后只接受流式 chunk，
                        # 非 chunk 的整段 AIMessage（重放）直接丢弃；
                        # 若模型非流式（没有 chunk），answer_started 为 False，整段消息仍会下发一次。
                        if answer_started and not isinstance(msg_chunk, AIMessageChunk):
                            continue
                        answer_started = True
                        yield SSEEvent(EVENT_TOKEN, {"content": body})
                elif mode == "updates":
                    if "__interrupt__" in (chunk or {}):
                        interrupted = True

            if thinking_started and not answer_started:
                yield SSEEvent(EVENT_THINKING_DONE, {
                    "elapsed_ms": int((time.monotonic() - start) * 1000),
                })

            # 4) 收尾：终态入库 + final 事件
            final_refs: dict = {}
            final_message = ""
            snapshot = await graph.aget_state(config)
            if snapshot and snapshot.values:
                values = snapshot.values
                final_message = values.get("final_message", "")
                jobs = values.get("job_results") or []
                final_refs["job_posting_ids"] = [
                    j.job_posting_id if hasattr(j, "job_posting_id") else j.get("job_posting_id")
                    for j in jobs[:10]
                ]

            async with AsyncSessionLocal() as db:
                if final_message:
                    await MessageRepository(db).add(Message(
                        session_id=session_row.id, role="assistant",
                        agent_name="Synthesizer", content=final_message, refs=final_refs or None,
                    ))
                await self._finish_run(db, run_id,
                                       status="awaiting_human" if interrupted else "done")
                await db.commit()

            yield SSEEvent(EVENT_FINAL, {
                "run_id": run_id,
                "status": "awaiting_human" if interrupted else "done",
                "refs": final_refs,
            })
            logger.info("run_finished", run_id=run_id, interrupted=interrupted,
                        latency_ms=int((time.monotonic() - start) * 1000))

        except Exception as exc:
            import traceback
            logger.error("run_failed", run_id=run_id, error=str(exc),
                         traceback=traceback.format_exc())
            if run_id:
                async with AsyncSessionLocal() as db:
                    await self._finish_run(db, run_id, status="error", error=str(exc))
                    await db.commit()
            yield SSEEvent(EVENT_ERROR, {"code": "AGENT-001", "message": str(exc)})

    # ---------- HITL 确认/拒绝 ----------

    async def resume_run(self, session_row: Session, user: User, run: AgentRun,
                         approved: bool) -> dict:
        """用户确认后从 checkpoint 恢复图执行（Command(resume=...)）。"""
        if run.status != "awaiting_human":
            raise AgentError(f"run 状态为 {run.status}，无需确认", code="RUN-001")

        graph = get_graph()
        config = {"configurable": {"thread_id": run.thread_id}, "recursion_limit": 20}

        # 恢复执行（finish 节点收尾）
        await graph.ainvoke(Command(resume=approved), config)

        # 落地求职信状态 + 渲染任务
        letter = None
        async with AsyncSessionLocal() as db:
            from app.repositories.letter import LetterRepository
            from app.models.letter import CoverLetter
            from sqlalchemy import select
            result = await db.execute(
                select(CoverLetter)
                .where(CoverLetter.session_id == session_row.id,
                       CoverLetter.status == "awaiting_confirm")
                .order_by(CoverLetter.created_at.desc())
            )
            letter = result.scalars().first()
            if letter:
                letter = await letter_service.confirm(db, LetterRepository(db), letter, approved)

            await MessageRepository(db).add(Message(
                session_id=session_row.id, role="assistant", agent_name="HITL",
                content="✅ 求职信已确认，正在生成 Word 文档，可在「求职信管理」下载。"
                        if approved else "已按您的要求放弃本次求职信草稿。",
            ))
            await self._finish_run(db, run.id, status="done")
            await db.commit()

        payload = {"run_id": run.id, "approved": approved}
        if letter:
            payload["letter_id"] = letter.id
            if approved and letter.file_key:
                payload["download_url"] = ""
        return payload

    # ---------- 内部 ----------

    async def _build_context(self, db: AsyncSession, user: User,
                             session_row: Session, user_input: str) -> dict:
        """图节点所需的上下文（避免节点直接依赖请求层）。"""
        # 简历严格会话级：只有会话显式绑定了 resume_id 才注入，
        # 不再兜底"全用户最新一份"——否则用户没传文件也会被默认带上参考简历
        resume = None
        if session_row.resume_id:
            resume = await ResumeRepository(db).get(session_row.resume_id)
            if resume is not None and resume.user_id != user.id:
                resume = None  # 越权防御：别人的简历不可用

        prefs = await PreferenceRepository(db).get_by_user(user.id)
        memories = await inject_memories(user.id, user_input)

        # 简历中心里可供关联的版本（只报元数据，不注入正文）。
        # 没绑简历时，模型至少能告诉用户"你中心里有这几份，点回形针即可关联"，
        # 而不是回答"我看不到简历"。
        available: list[dict] = []
        if resume is None:
            for r in (await ResumeRepository(db).list_by_user(user.id))[:5]:
                available.append({
                    "id": r.id, "version": r.version,
                    "filename": r.filename, "status": r.status,
                })

        return {
            "user_id": user.id,
            "run_id": None,  # run 创建后事件持久化走独立会话
            "resume_id": resume.id if resume else None,
            "resume_text": (resume.parsed_text or "") if resume else "",
            "resume_ready": bool(resume and resume.profile),
            "available_resumes": available,
            # 「联网搜索」是否真的可用：只有配了 Serper Key（用户级优先，其次服务端）才为 True。
            # Planner 依赖它决定"真检索"还是"给出未配置提示"，避免开关点了却静默无效。
            "web_search_available": bool(self._serper_key(user)),
            "preferences": (
                {k: getattr(prefs, k) for k in ("city", "industry", "salary_range", "work_type")}
                if prefs else {}
            ),
            "memories": memories,
            "llm_pref": user.llm_model_pref or {},
            "llm_api_key_enc": user.llm_api_key_enc or "",
            "llm_base_url": user.llm_base_url or "",
        }

    @staticmethod
    def _serper_key(user: User) -> str:
        """取当前用户可用的 Serper Key（请求上下文 > 用户库 > 服务端 .env）。"""
        return (
            get_tool_key("serper")
            or decrypt_secret(user.serper_api_key_enc or "")
            or settings.serper_api_key
            or ""
        )

    async def _handle_custom_event(self, session_row: Session, run_id: str,
                                   event: dict) -> AsyncGenerator[SSEEvent, None]:
        """custom 事件 → agent_events 落库 + SSE 翻译。"""
        event_type = event.get("type", "unknown")
        node = event.get("node", "")
        payload = event.get("payload", {})
        latency = event.get("latency_ms", 0)

        sse_type_map = {
            "plan": EVENT_PLAN,
            "agent_start": EVENT_AGENT_START,
            "tool_call": EVENT_TOOL_CALL,
            "critic": "critic",
            "interrupt": EVENT_INTERRUPT,
            "final": EVENT_FINAL,
        }

        # 持久化轨迹
        async with AsyncSessionLocal() as db:
            event_repo = EventRepository(db)
            seq = await event_repo.next_seq(run_id)
            await event_repo.add(AgentEvent(
                run_id=run_id, seq=seq, node_name=node,
                event_type=event_type, payload=payload, latency_ms=latency,
            ))
            if event_type == "plan":
                run_repo = RunRepository(db)
                run = await run_repo.get(run_id)
                if run:
                    run.plan = payload
            await db.commit()

        # HITL 中断：创建待确认求职信草稿
        if event_type == "interrupt":
            letter_id = await self._create_letter_on_interrupt(session_row, payload)
            payload = {**payload, "run_id": run_id, "letter_id": letter_id}

        # 图的 Finish 节点也会发 final：只入轨迹、不下发。
        # 真正的终态由 chat_stream 在**落库之后**统一发（带 run_id/status/refs），
        # 否则前端会收到两个 final，且前面那个早于消息落库，读到的是旧数据。
        if event_type == "final":
            return

        yield SSEEvent(sse_type_map.get(event_type, event_type), payload)

    async def _create_letter_on_interrupt(self, session_row: Session,
                                          payload: dict) -> str | None:
        """interrupt 发生时创建 awaiting_confirm 草稿，供前端展示与确认。"""
        try:
            graph = get_graph()
            snapshot = await graph.aget_state(
                {"configurable": {"thread_id": session_row.id}}
            )
            values = (snapshot.values if snapshot else {}) or {}
            jobs = values.get("job_results") or []
            top_job = None
            if jobs:
                j = jobs[0]
                top_job = j.job_posting_id if hasattr(j, "job_posting_id") else j.get("job_posting_id")

            async with AsyncSessionLocal() as db:
                letter = await letter_service.create_from_run(
                    db,
                    user_id=session_row.user_id,
                    resume_id=session_row.resume_id,
                    job_posting_id=top_job,
                    session_id=session_row.id,
                    content=payload.get("cover_letter", ""),
                    critic={
                        "scores": payload.get("critic_scores", {}),
                        "suggestions": payload.get("critic_suggestions", []),
                        "revisions": payload.get("revision_count", 0),
                    },
                )
                return letter.id
        except Exception as exc:
            logger.error("letter_create_on_interrupt_failed", error=str(exc))
            return None

    async def _finish_run(self, db: AsyncSession, run_id: str, status: str,
                          error: str = "") -> None:
        from datetime import datetime
        run = await RunRepository(db).get(run_id)
        if run:
            run.status = status
            run.error = error
            run.finished_at = datetime.utcnow()


orchestrator = OrchestratorService()
