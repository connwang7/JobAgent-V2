"""Embedding：自托管 TEI (BGE-M3) 优先，其次专用 Embedding 配置，DashScope 兜底。

凭证解析顺序：
1. TEI_ENDPOINT（自托管，无需 Key）
2. 用户级/服务端专用 Embedding Key（EMBEDDING_API_KEY）
3. 复用对话 LLM 凭证 —— **仅当其 endpoint 是 DashScope**。
   第三方中转站（如 aiaaa.cc）大多不提供向量模型，盲目复用会每条消息都报
   `model_not_found: text-embedding-v3` 404；此时应明确判定"向量服务不可用"，
   让长期记忆等功能静默降级，而不是反复打无效请求。

失败后会短时间缓存"不可用"状态（默认 5 分钟），避免每条消息都重试一次注定失败的调用。
"""
import time

import httpx

from app.core.config import settings
from app.core.logging import logger
from app.core.net import is_local_endpoint
from app.core.user_context import get_tool_key

DASHSCOPE_HOST = "dashscope.aliyuncs.com"
# 调用失败后的冷却时间（秒）：期间直接判定不可用，不再发起请求
FAILURE_COOLDOWN_SECONDS = 300


def _usable_endpoint(api_key: str, base_url: str) -> tuple[str, str] | None:
    """对话凭证能否用于向量模型：Key 存在且 endpoint 是 DashScope。"""
    if not api_key:
        return None
    if api_key and DASHSCOPE_HOST in (base_url or ""):
        return api_key, base_url
    return None


def _resolve_credentials() -> tuple[str, str] | None:
    """返回 (api_key, base_url)；无法确定可用的向量服务时返回 None。"""
    # 1) 用户级专用 Embedding 配置（预留；当前设置页未单独采集）
    emb_key = get_tool_key("embedding")
    if emb_key:
        return emb_key, get_tool_key("embedding_base_url") or settings.embedding_base_url
    # 2) 服务端专用 Embedding 配置
    if settings.embedding_api_key:
        return settings.embedding_api_key, settings.embedding_base_url
    # 3) 复用对话凭证：仅 DashScope（其兼容模式原生支持 embedding 模型）
    api_key = get_tool_key("llm") or settings.llm_api_key
    base_url = get_tool_key("llm_base_url") or settings.llm_base_url
    return _usable_endpoint(api_key, base_url)


def embedding_ready(user=None) -> tuple[bool, str]:
    """设置页用：判断当前是否具备生成向量（人岗匹配/长期记忆）的条件。"""
    if settings.tei_endpoint:
        return True, f"使用自托管 TEI：{settings.tei_endpoint}"
    emb_key = get_tool_key("embedding") or settings.embedding_api_key
    if emb_key:
        return True, f"使用专用 Embedding 配置（{settings.embedding_model}）"
    api_key = get_tool_key("llm") or settings.llm_api_key
    base_url = get_tool_key("llm_base_url") or settings.llm_base_url
    if _usable_endpoint(api_key, base_url):
        return True, f"使用 DashScope 对话凭证调 Embedding（{settings.embedding_model}）"
    if api_key:
        host = (base_url or "").split("//")[-1].rstrip("/") or "当前对话端点"
        return False, (
            f"对话端点（{host}）未提供向量模型，长期记忆与人岗匹配暂不可用（对话不受影响）。"
            "可在服务端 .env 配置 EMBEDDING_API_KEY（默认走阿里云 DashScope）开启。"
        )
    return False, "未配置大模型 Key，人岗匹配与长期记忆将不可用（其余功能正常）"


class EmbeddingClient:
    def __init__(self) -> None:
        self._tei = settings.tei_endpoint.rstrip("/") if settings.tei_endpoint else ""
        self._fail_until = 0.0  # 失败冷却：期间直接判定不可用

    def _mark_failure(self, reason: str) -> None:
        self._fail_until = time.monotonic() + FAILURE_COOLDOWN_SECONDS
        logger.warning("embedding_marked_unavailable", error=reason,
                       cooldown_seconds=FAILURE_COOLDOWN_SECONDS)

    def _in_cooldown(self) -> bool:
        return time.monotonic() < self._fail_until

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self._tei:
            return await self._embed_tei(texts)
        if self._in_cooldown():
            raise RuntimeError(
                "向量服务暂不可用（近期调用失败，冷却中）；长期记忆功能已临时降级，不影响对话"
            )
        creds = _resolve_credentials()
        if creds is None:
            # 不发起注定失败的请求，由调用方降级处理（不中断主流程）
            raise RuntimeError(
                "未配置可用的 Embedding 服务（TEI_ENDPOINT / EMBEDDING_API_KEY），"
                "且对话端点非 DashScope，无法生成向量"
            )
        try:
            return await self._embed_openai_compatible(texts, *creds)
        except Exception as exc:
            self._mark_failure(str(exc))
            raise

    async def _embed_tei(self, texts: list[str]) -> list[list[float]]:
        try:
            # TEI 常见于本机/内网自托管：这类端点半不能走系统代理
            async with httpx.AsyncClient(timeout=30,
                                         trust_env=not is_local_endpoint(self._tei)) as client:
                resp = await client.post(f"{self._tei}/embed", json={"inputs": texts})
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            self._mark_failure(str(exc))
            raise

    async def _embed_openai_compatible(self, texts: list[str],
                                       api_key: str, base_url: str) -> list[list[float]]:
        import openai

        client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url)
        kwargs: dict = {"model": settings.embedding_model, "input": texts}
        # dimensions 仅部分服务支持（DashScope 支持；SiliconFlow 的 BGE 模型传了会 400）
        if settings.embedding_dimensions and settings.embedding_dimensions > 0:
            kwargs["dimensions"] = settings.embedding_dimensions
        resp = await client.embeddings.create(**kwargs)
        return [d.embedding for d in resp.data]

    async def embed_query(self, text: str) -> list[float]:
        vecs = await self.embed([text])
        return vecs[0]


_embedding_client: EmbeddingClient | None = None


def get_embedding_client() -> EmbeddingClient:
    global _embedding_client
    if _embedding_client is None:
        _embedding_client = EmbeddingClient()
    return _embedding_client
