"""dots STT 的临时音频托管（内存，单次下载即焚，TTL 过期）。

隐私边界：音频不落库、不写盘、不进日志。仅在 dots 模式转写请求的
存续期（issue_url → 模型拉取）内驻留内存；模型拉取（一次性 token）
或 TTL 到期即销毁。token 为 secrets 级随机串，不可枚举。
"""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass

from psych_support_bot.infra.config.settings import get_settings
from psych_support_bot.infra.voice.adapter import VoiceProviderError


@dataclass
class _MediaEntry:
    audio: bytes
    filename: str
    expires_at: float


_lock = threading.Lock()
_store: dict[str, _MediaEntry] = {}


def _ttl_seconds() -> int:
    ttl = get_settings().voice_media_ttl_seconds
    return ttl if ttl > 0 else 120


def issue_url(audio: bytes, filename: str) -> str:
    """暂存音频并签发一次性下载 URL（{public_base}/v1/voice/tmp/{token}）。"""
    settings = get_settings()
    public_base = (settings.voice_media_public_base_url or "").strip().rstrip("/")
    if not public_base:
        raise VoiceProviderError("VOICE_MEDIA_PUBLIC_BASE_URL is required for dots STT (model must fetch the audio)")
    token = secrets.token_urlsafe(32)
    with _lock:
        _purge_expired()
        _store[token] = _MediaEntry(
            audio=audio,
            filename=filename,
            expires_at=time.monotonic() + _ttl_seconds(),
        )
    return f"{public_base}/v1/voice/tmp/{token}"


def consume(token: str) -> tuple[bytes, str] | None:
    """取走音频（单次有效）：命中返回 (audio, filename) 并立即销毁条目；
    不存在/过期返回 None。供下载端点调用。"""
    with _lock:
        _purge_expired()
        entry = _store.pop(token, None)
    if entry is None:
        return None
    return entry.audio, entry.filename


def discard_url(media_url: str) -> None:
    """按 URL 主动销毁（转写请求结束后调用，无论成败）。"""
    token = media_url.rstrip("/").rsplit("/", 1)[-1]
    with _lock:
        _store.pop(token, None)


def _purge_expired() -> None:
    now = time.monotonic()
    expired = [token for token, entry in _store.items() if entry.expires_at <= now]
    for token in expired:
        _store.pop(token, None)


def reset_for_tests() -> None:
    with _lock:
        _store.clear()
