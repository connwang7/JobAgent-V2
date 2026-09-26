from app.core.security import (
    create_access_token, create_refresh_token, decode_token,
    encrypt_secret, decrypt_secret, hash_password, verify_password,
)


def test_password_hash_and_verify():
    h = hash_password("secret-pass")
    assert h.startswith("$2")
    assert verify_password("secret-pass", h)
    assert not verify_password("wrong", h)


def test_jwt_pair_types():
    access = create_access_token("42")
    refresh = create_refresh_token("42")
    assert decode_token(access, "access") == "42"
    # access token 不能用 refresh 类型解码（防混用）
    assert decode_token(access, "refresh") is None
    assert decode_token(refresh, "refresh") == "42"
    assert decode_token("garbage", "access") is None


def test_aes_gcm_roundtrip():
    enc = encrypt_secret("sk-test-key")
    assert enc and enc != "sk-test-key"
    assert decrypt_secret(enc) == "sk-test-key"
    assert decrypt_secret("") == ""
