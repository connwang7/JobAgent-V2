"""认证与加密：JWT 双 token、bcrypt 密码哈希、AES-GCM 用户密钥加密。"""
import base64
import os
import time
from typing import Any

import bcrypt
import jwt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings

# ---------- 密码 ----------

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


# ---------- JWT ----------

def _create_token(subject: str, token_type: str, expires_seconds: int) -> str:
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_seconds,
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def create_access_token(user_id: str) -> str:
    return _create_token(user_id, "access", settings.access_token_expire_minutes * 60)


def create_refresh_token(user_id: str) -> str:
    return _create_token(user_id, "refresh", settings.refresh_token_expire_days * 86400)


def decode_token(token: str, expected_type: str) -> str | None:
    """校验并返回 user_id；无效或类型不匹配返回 None。"""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    if payload.get("type") != expected_type:
        return None
    return payload.get("sub")


# ---------- AES-GCM 用户级 API Key 加解密 ----------

def _aes_key() -> bytes:
    return bytes.fromhex(settings.kms_master_key)


def encrypt_secret(plaintext: str) -> str:
    """输出 base64(nonce + ciphertext)。解密只发生在调用 LLM 的内存中。"""
    if not plaintext:
        return ""
    aes = AESGCM(_aes_key())
    nonce = os.urandom(12)
    ct = aes.encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ct).decode("ascii")


def decrypt_secret(encrypted: str) -> str:
    if not encrypted:
        return ""
    aes = AESGCM(_aes_key())
    raw = base64.b64decode(encrypted)
    return aes.decrypt(raw[:12], raw[12:], None).decode("utf-8")


def mask_secret(encrypted: str, head: int = 4, tail: int = 4) -> str:
    """把已加密的密钥解密后做掩码回显（如 `sk-a****wxyz`），用于设置页展示。

    解密失败（换过 KMS_MASTER_KEY）返回 "****"，绝不抛出。
    """
    if not encrypted:
        return ""
    try:
        plain = decrypt_secret(encrypted)
    except Exception:
        return "****"
    if not plain:
        return ""
    if len(plain) <= head + tail:
        return plain[:2] + "*" * max(len(plain) - 2, 0)
    return f"{plain[:head]}{'*' * 8}{plain[-tail:]}"
