"""认证服务：注册/登录/刷新（JWT 双 token + refresh 轮换 + 登录限流）。"""
from app.core.cache import rate_limit
from app.core.errors import AuthError
from app.core.logging import logger
from app.core.security import (
    create_access_token, create_refresh_token, decode_token, hash_password, verify_password,
)
from app.core.config import settings
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.auth import LoginRequest, RegisterRequest, TokenPair


async def register(repo: UserRepository, req: RegisterRequest) -> User:
    if await repo.get_by_email(req.email):
        raise AuthError("该邮箱已注册", code="AUTH-002")
    user = await repo.add(User(
        email=req.email,
        password_hash=hash_password(req.password),
        nickname=req.nickname or req.email.split("@")[0],
    ))
    logger.info("user_registered", user_id=user.id)
    return user


async def login(repo: UserRepository, req: LoginRequest) -> tuple[User, TokenPair]:
    # 登录接口单独更严的限流阈值（方案 4.3）
    allowed = await rate_limit(f"login:{req.email}", max_hits=10, window_seconds=300)
    if not allowed:
        raise AuthError("尝试过于频繁，请稍后再试", code="AUTH-003",
                        http_status=429)

    user = await repo.get_by_email(req.email)
    if not user or not verify_password(req.password, user.password_hash):
        raise AuthError("邮箱或密码错误", code="AUTH-004")
    if not user.is_active:
        raise AuthError("账号已被禁用", code="AUTH-005")

    return user, _issue_tokens(user)


async def refresh(repo: UserRepository, refresh_token: str) -> TokenPair:
    """refresh token 轮换：校验旧 refresh 并签发新对。"""
    user_id = decode_token(refresh_token, "refresh")
    if not user_id:
        raise AuthError("refresh token 无效或已过期", code="AUTH-006")
    user = await repo.get(int(user_id))
    if not user or not user.is_active:
        raise AuthError("用户不存在", code="AUTH-007")
    return _issue_tokens(user)


def _issue_tokens(user: User) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
        expires_in=settings.access_token_expire_minutes * 60,
    )
