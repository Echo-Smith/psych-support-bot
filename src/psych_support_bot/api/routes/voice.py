"""语音 I/O 路由（/v1/voice）。

- POST /transcribe：multipart 音频 → 转写文本。音频即转即弃（不落库、
  不写日志）；转写文本作为普通聊天消息的输入由前端走既有 /respond。
- POST /speak：文本 → audio/mpeg（OpenAI 兼容）。未配置 503，前端降级
  浏览器朗读。危机回复照读（热线号码读出来更可达）。
- GET /status：前端探测（是否配置 STT/TTS），决定麦克风按钮显隐与朗读开关。
- GET /tmp/{token}：dots STT 的一次性音频下载端点（模型拉取用；单次
  有效 + TTL）。须鉴权吗？——不给：模型侧无凭据可带，安全性由 token
  不可枚举 + 单次有效 + 短 TTL 保证，且该端点只出音频、不落任何状态。
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import Response

from psych_support_bot.api.auth import request_user_id, require_auth
from psych_support_bot.infra.voice import media_store
from psych_support_bot.infra.voice.adapter import (
    MAX_AUDIO_BYTES,
    VoiceNotConfigured,
    VoiceProviderError,
    get_stt_config,
    get_tts_config,
    synthesize,
    transcribe,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/voice", tags=["voice"])

# 公开路由（dots 模型侧拉取用，无凭据设计见 fetch_tmp_media docstring）
public_router = APIRouter(prefix="/v1/voice", tags=["voice"], include_in_schema=False)

# 允许的音频格式（MediaRecorder 常见输出 + 常见手机录音格式）
_ALLOWED_AUDIO_TYPES = {
    "audio/webm",
    "audio/ogg",
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/m4a",
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/x-m4a",
    "audio/aac",
}

# TTS 输入上限（一次朗读一段回复，1000 字符远超三气泡上限）
_TTS_MAX_CHARS = 1000


def _voice_user_id(request: Request, declared: str | None) -> str:
    """与 /v1/conversations 同口径的用户身份（AUTH_ENABLED 时 token 为准）。"""

    class _Payload:
        user_id = declared or ""

    return request_user_id(request, _Payload())


@router.get("/status")
def voice_status(request: Request, _sub: str = Depends(require_auth)) -> dict[str, bool]:
    return {
        "stt": get_stt_config() is not None,
        "tts": get_tts_config() is not None,
    }


@router.post("/transcribe")
async def transcribe_audio(request: Request, file: UploadFile, _sub: str = Depends(require_auth)) -> dict[str, Any]:
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type and content_type not in _ALLOWED_AUDIO_TYPES:
        raise HTTPException(status_code=422, detail=f"Unsupported audio type: {content_type}")
    audio = await file.read()
    if not audio:
        raise HTTPException(status_code=422, detail="Empty audio file")
    if len(audio) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Audio file too large (max 25MB)")
    filename = file.filename or "audio.webm"
    try:
        text = transcribe(audio, filename)
    except VoiceNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except VoiceProviderError as exc:
        logger.warning("Voice transcribe failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Transcription failed: {exc}") from exc
    return {"text": text}


@router.post("/speak")
async def speak_text(request: Request, payload: dict[str, Any], _sub: str = Depends(require_auth)) -> Response:
    text = str(payload.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="Empty text")
    if len(text) > _TTS_MAX_CHARS:
        raise HTTPException(status_code=422, detail=f"Text too long (max {_TTS_MAX_CHARS} chars)")
    try:
        audio = synthesize(text)
    except VoiceNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except VoiceProviderError as exc:
        logger.warning("Voice speak failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Speech synthesis failed: {exc}") from exc
    return Response(content=audio, media_type="audio/mpeg")


@public_router.get("/tmp/{token}")
def fetch_tmp_media(token: str) -> Response:
    """dots STT 一次性音频下载（模型侧拉取；无凭据设计，见模块 docstring）。"""
    entry = media_store.consume(token)
    if entry is None:
        raise HTTPException(status_code=404, detail="Media not found or expired")
    audio, filename = entry
    return Response(
        content=audio,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )
