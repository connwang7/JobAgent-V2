from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, user_repo
from app.core.config import settings
from app.core.db import get_session
from app.core.security import decrypt_secret, encrypt_secret, mask_secret
from app.core.user_context import set_user_tool_keys
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.auth import (
    LLMConfigOut, LLMConfigUpdate, LLMTestResult,
    LoginRequest, RefreshRequest, RegisterRequest, UserOut,
)
from app.schemas.common import ok
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=201)
async def register(req: RegisterRequest, repo: UserRepository = Depends(user_repo)):
    user = await auth_service.register(repo, req)
    return ok(UserOut.model_validate(user).model_dump(), "注册成功")


@router.post("/login")
async def login(req: LoginRequest, repo: UserRepository = Depends(user_repo)):
    user, tokens = await auth_service.login(repo, req)
    return ok({
        "user": UserOut.model_validate(user).model_dump(),
        **tokens.model_dump(),
    })


@router.post("/refresh")
async def refresh(req: RefreshRequest, repo: UserRepository = Depends(user_repo)):
    tokens = await auth_service.refresh(repo, req.refresh_token)
    return ok(tokens.model_dump())


@router.put("/llm-config")
async def update_llm_config(
    req: LLMConfigUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """用户级配置：LLM + 工具服务密钥，全部 AES-GCM 加密入库，日志全脱敏。

    保存后**立即生效**，无需重启服务（工具调用每次从库解密后经内存 contextvars 使用）。
    """
    if req.clear_api_key:
        user.llm_api_key_enc = ""
    elif req.api_key:
        user.llm_api_key_enc = encrypt_secret(req.api_key)

    if req.base_url:
        user.llm_base_url = req.base_url
    if req.model_pref:
        user.llm_model_pref = req.model_pref

    if req.clear_serper:
        user.serper_api_key_enc = ""
    elif req.serper_api_key:
        user.serper_api_key_enc = encrypt_secret(req.serper_api_key)

    if req.clear_firecrawl:
        user.firecrawl_api_key_enc = ""
    elif req.firecrawl_api_key:
        user.firecrawl_api_key_enc = encrypt_secret(req.firecrawl_api_key)

    await session.commit()

    # 当前请求上下文立即刷新（后续请求由 get_current_user 依赖注入）
    set_user_tool_keys({
        "llm": decrypt_secret(user.llm_api_key_enc),
        "llm_base_url": user.llm_base_url or "",
        "serper": decrypt_secret(user.serper_api_key_enc),
        "firecrawl": decrypt_secret(user.firecrawl_api_key_enc),
    })
    return ok(_build_config_out(user).model_dump(), "配置已保存并立即生效")


def _build_config_out(user: User) -> LLMConfigOut:
    from app.agents.llm.model_router import default_models, effective_models
    from app.matching.embedding import embedding_ready

    pref = user.llm_model_pref or {}
    ready, hint = embedding_ready(user)
    web_ready = bool(user.serper_api_key_enc or settings.serper_api_key)
    return LLMConfigOut(
        base_url=user.llm_base_url or "",
        base_url_effective=user.llm_base_url or settings.llm_base_url,
        model_pref=pref,
        models=effective_models(pref),
        defaults=default_models(),
        api_key_set=bool(user.llm_api_key_enc),
        api_key_masked=mask_secret(user.llm_api_key_enc),
        serper_set=bool(user.serper_api_key_enc),
        serper_masked=mask_secret(user.serper_api_key_enc),
        firecrawl_set=bool(user.firecrawl_api_key_enc),
        firecrawl_masked=mask_secret(user.firecrawl_api_key_enc),
        embedding_ready=ready,
        embedding_hint=hint,
        web_search_ready=web_ready,
        web_search_hint=(
            "" if web_ready
            else "未配置 Serper API Key，联网搜索与岗位搜索不可用；到 设置 → 工具密钥 填入后生效。"
        ),
    )


@router.get("/llm-config")
async def get_llm_config(user: User = Depends(get_current_user)):
    """设置页回显：模型清单 + 密钥掩码，绝不返回明文。"""
    return ok(_build_config_out(user).model_dump())


@router.delete("/llm-config")
async def clear_llm_config(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """清空全部用户级密钥（LLM / Serper / FireCrawl），回落到服务端 .env。"""
    user.llm_api_key_enc = ""
    user.serper_api_key_enc = ""
    user.firecrawl_api_key_enc = ""
    user.llm_model_pref = {}
    await session.commit()
    set_user_tool_keys({})
    return ok(_build_config_out(user).model_dump(), "已清除用户级配置，回落服务端默认")


@router.post("/llm-config/test")
async def test_llm_config(user: User = Depends(get_current_user)):
    """用当前用户配置真实调用一次大模型，返回连通性 / 延迟 / 实际模型。

    失败也返回 200（ok=false + error），便于设置页直接展示原因。
    """
    import asyncio
    import time as _time

    from langchain_core.messages import HumanMessage

    from app.agents.llm.model_router import get_llm_for_role

    api_key = decrypt_secret(user.llm_api_key_enc)
    if not api_key and not settings.llm_api_key:
        return ok(LLMTestResult(
            ok=False, error="未配置大模型 API Key（用户级与服务端均为空）",
        ).model_dump())

    start = _time.monotonic()
    try:
        llm = get_llm_for_role(
            "worker",
            user_pref=user.llm_model_pref or {},
            user_api_key_enc=user.llm_api_key_enc or "",
            user_base_url=user.llm_base_url or "",
        )
        reply = await asyncio.wait_for(
            llm.ainvoke([HumanMessage(content="回复两个字：可用")]), timeout=30,
        )
        content = str(getattr(reply, "content", ""))[:100]
        return ok(LLMTestResult(
            ok=True,
            model=getattr(llm, "model_name", "") or (user.llm_model_pref or {}).get("worker", ""),
            base_url=getattr(llm, "openai_api_base", "") or settings.llm_base_url,
            latency_ms=int((_time.monotonic() - start) * 1000),
            reply=content,
        ).model_dump())
    except asyncio.TimeoutError:
        return ok(LLMTestResult(ok=False, error="调用超时（30s），请检查 Base URL 是否可达").model_dump())
    except Exception as exc:
        return ok(LLMTestResult(ok=False, error=str(exc)[:300]).model_dump())
