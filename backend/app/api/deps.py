"""API 依赖注入：当前用户、各类 repository 工厂。"""
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.errors import AuthError
from app.core.security import decode_token, decrypt_secret
from app.core.user_context import set_user_tool_keys
from app.models.user import User
from app.repositories.user import UserRepository

bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    session: AsyncSession = Depends(get_session),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> User:
    if credentials is None:
        raise AuthError("缺少认证凭证", code="AUTH-101")
    user_id = decode_token(credentials.credentials, "access")
    if not user_id:
        raise AuthError("access token 无效或已过期", code="AUTH-102")
    user = await UserRepository(session).get(int(user_id))
    if not user or not user.is_active:
        raise AuthError("用户不存在或已禁用", code="AUTH-103")
    # 把该用户的密钥解密后放入请求上下文（仅内存，不落日志、不进 prompt）
    # llm 凭证仅在 endpoint 为 DashScope 时供 embedding 复用（见 matching/embedding.py）
    set_user_tool_keys({
        "llm": decrypt_secret(user.llm_api_key_enc or ""),
        "llm_base_url": user.llm_base_url or "",
        "serper": decrypt_secret(user.serper_api_key_enc or ""),
        "firecrawl": decrypt_secret(user.firecrawl_api_key_enc or ""),
    })
    return user


def user_repo(session: AsyncSession = Depends(get_session)) -> UserRepository:
    return UserRepository(session)
