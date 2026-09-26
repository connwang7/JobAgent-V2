"""分层多模型路由（方案 6.10 节）。

角色→模型映射；用户可在设置页覆盖（users.llm_model_pref）。
统一走 OpenAI 兼容协议；Critic 与生成器异模型，避免同源偏见。
"""
from functools import lru_cache
from typing import Any, ClassVar

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessageChunk
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.core.logging import logger
from app.core.security import decrypt_secret


class ChatOpenAIWithReasoning(ChatOpenAI):
    """把 OpenAI 兼容端点返回的 `reasoning_content` 接回 additional_kwargs。

    langchain-openai 只保留标准字段，非标准的 reasoning_content / reasoning 会被**直接丢弃**
    （见其 _convert_delta_to_message_chunk 的文档字符串："are not extracted"）。
    后果：流式时思考过程整段消失，orchestrator 的 extract_reasoning() 永远抽不到内容，
    前端「深度思考」开关看起来完全无效——即使模型（如 deepseek-v4.1-flash）确实返回了推理。

    这里在 chunk 转换后补回该字段，仅用于「深度思考」角色，避免未开启时也冒出思考块。
    """

    REASONING_FIELDS: ClassVar[tuple[str, ...]] = ("reasoning_content", "reasoning", "thinking")

    def _convert_chunk_to_generation_chunk(  # type: ignore[override]
        self, chunk: dict, default_chunk_class: type, base_generation_info: dict | None
    ):
        gen = super()._convert_chunk_to_generation_chunk(
            chunk, default_chunk_class, base_generation_info
        )
        if gen is None or not isinstance(gen.message, AIMessageChunk):
            return gen
        choices = chunk.get("choices") or (chunk.get("chunk") or {}).get("choices") or []
        if not choices:
            return gen
        delta = choices[0].get("delta") or {}
        for field in self.REASONING_FIELDS:
            value = delta.get(field)
            if isinstance(value, str) and value:
                gen.message.additional_kwargs[field] = value
                break
        return gen

ROLE_MODEL_MAP: dict[str, dict[str, Any]] = {
    "planner":     {"model": settings.llm_model_planner, "temperature": 0.1},
    "worker":      {"model": settings.llm_model_worker,  "temperature": 0.3},
    "writer":      {"model": settings.llm_model_writer,  "temperature": 0.5},
    "critic":      {"model": settings.llm_model_critic,  "temperature": 0.1},
    "synthesizer": {"model": settings.llm_model_worker,  "temperature": 0.3},
    # 「深度思考」开启时的推理模型（temperature 稍高以保留推理链）
    "thinking":    {"model": settings.llm_model_thinking, "temperature": 0.6},
}

# 前端设置页展示顺序（thinking 单列，便于用户单独指定推理模型）
ROLE_ORDER = ["planner", "worker", "writer", "critic", "thinking"]


def _resolve(role: str, user_pref: dict | None) -> tuple[dict[str, Any], str, str]:
    """返回 (模型参数, api_key, base_url)。用户覆盖优先。"""
    params = dict(ROLE_MODEL_MAP.get(role, ROLE_MODEL_MAP["worker"]))
    api_key = settings.llm_api_key
    base_url = settings.llm_base_url

    if role == "critic" and settings.critic_base_url:
        # critic 走异源模型端点
        base_url = settings.critic_base_url
        api_key = settings.critic_api_key or api_key

    if user_pref:
        if user_pref.get(role):
            params["model"] = user_pref[role]
        elif role in ("synthesizer", "thinking") and user_pref.get("worker"):
            # 设置页没有单独的 synthesizer 项，thinking 也可能留空：
            # 用户只改了 worker 时这两者必须跟着走，否则会继续用默认模型
            # （qwen-plus / deepseek-reasoner）打到不支持它的端点 → 404，
            # 表现为「汇总退化成黑板原文」或「开启深度思考就报错」
            params["model"] = user_pref["worker"]
        if user_pref.get("_api_key"):
            api_key = user_pref["_api_key"]
        if user_pref.get("_base_url"):
            base_url = user_pref["_base_url"]

    return params, api_key, base_url


@lru_cache(maxsize=128)
def _cached_llm(role: str, model: str, temperature: float, api_key: str,
                base_url: str, streaming: bool = False) -> BaseChatModel:
    # streaming=True 时 ChatOpenAI 内部走流式接口并逐块触发 on_llm_new_token，
    # LangGraph 的 stream_mode="messages" 才能拿到增量 chunk。
    # 不开的话 ainvoke 只在结束时产出一个完整 chunk → 前端表现为"一次性出全文"。
    # 「深度思考」角色额外挂上 reasoning 解析（否则思考过程会被 SDK 丢弃）。
    cls = ChatOpenAIWithReasoning if role == "thinking" else ChatOpenAI
    return cls(
        model=model,
        temperature=temperature,
        api_key=api_key,
        base_url=base_url,
        timeout=120,
        max_retries=2,
        streaming=streaming,
    )


def default_models() -> dict[str, str]:
    """各角色的系统默认模型（设置页"恢复默认"参考）。"""
    return {role: cfg["model"] for role, cfg in ROLE_MODEL_MAP.items()}


def effective_models(user_pref: dict | None = None) -> dict[str, str]:
    """各角色当前实际生效的模型（用户覆盖优先）。"""
    pref = dict(user_pref or {})
    return {role: _resolve(role, pref)[0]["model"] for role in ROLE_MODEL_MAP}

def get_llm_for_role(
    role: str,
    user_pref: dict | None = None,
    user_api_key_enc: str = "",
    user_base_url: str = "",
    streaming: bool = False,
) -> BaseChatModel:
    """按角色获取 LLM。用户级配置（加密 key 解密仅在内存中发生）优先于全局默认。

    user_pref 形如 {"writer": "deepseek-reasoner", ...}；
    user_api_key_enc/user_base_url 为 users 表中的用户级配置。

    streaming=True 用于「产出用户可见文本」的节点（synthesizer / ChatBot），
    使 token 可以逐块下发；结构化输出（with_structured_output）的节点保持 False。
    """
    pref = dict(user_pref or {})
    if user_api_key_enc:
        try:
            pref["_api_key"] = decrypt_secret(user_api_key_enc)
        except Exception:
            logger.warning("user_llm_key_decrypt_failed", role=role)
    if user_base_url:
        pref["_base_url"] = user_base_url

    params, api_key, base_url = _resolve(role, pref)
    if not api_key:
        # 提前给出可执行的提示，避免 OpenAI SDK 抛出 "Missing credentials" 之类难懂的错误
        raise RuntimeError(
            "未配置大模型 API Key：请在「系统设置 → 大模型配置」填写并保存（或用「测试连接」验证），"
            "也可在服务端 .env 设置 LLM_API_KEY"
        )
    return _cached_llm(role, params["model"], params["temperature"], api_key,
                       base_url, streaming)
