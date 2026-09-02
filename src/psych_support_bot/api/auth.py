"""JWT 认证基础设施：密码哈希、token 签发/校验、路由守卫。

设计要点：
- 密码哈希用标准库 pbkdf2_hmac（SHA-256，600k 迭代），零新增重依赖；
  存储格式 ``pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>``。
- JWT 用 pyjwt（HS256），claims: sub / exp / iat，TTL 7 天。
- require_auth 守卫挂在各数据路由上：AUTH_ENABLED=false 时是 no-op
  （面板登录 UI 尚未上线，本地开发与既有测试不携带 token），
  true 时无/坏 token 一律 401。user_id 的权威来源是 JWT sub——
  路由不得再接受请求参数里的 user_id 自报值做越权数据访问。
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

import jwt as pyjwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from psych_support_bot.infra.config.settings import get_settings

PBKDF2_ITERATIONS = 600_000
TOKEN_TTL_DAYS = 7
_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, iterations, salt, expected = stored.split("$")
        if scheme != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), int(iterations))
        return hmac.compare_digest(digest.hex(), expected)
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: str) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {"sub": user_id, "iat": now, "exp": now + timedelta(days=TOKEN_TTL_DAYS)}
    return pyjwt.encode(payload, settings.jwt_secret_key, algorithm=_ALGORITHM)


def decode_access_token(token: str) -> str:
    """校验并返回 sub（user_id）；任何失败统一以 401 呈现，不泄漏原因细节。"""
    settings = get_settings()
    try:
        payload = pyjwt.decode(token, settings.jwt_secret_key, algorithms=[_ALGORITHM])
    except pyjwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return str(sub)


# auto_error=False 让缺失头也走我们的统一 401 JSON，而非 FastAPI 默认 403。
_bearer_scheme = HTTPBearer(auto_error=False)


def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> str:
    """数据路由守卫：AUTH_ENABLED=false 时 no-op 返回空串；true 时返回 JWT sub。

    返回值即当前认证用户——后续各端点把数据查询的 user_id 收敛到这个值，
    即完成"认证 → 归属校验"的闭环（防止伪造埋点归属/跨用户读取）。
    """
    settings = get_settings()
    if not settings.auth_enabled:
        return ""
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return decode_access_token(credentials.credentials)
