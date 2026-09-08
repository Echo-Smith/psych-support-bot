"""语音 I/O 路由（/v1/voice）。

- POST /transcribe：multipart 音频 → 转写文本。音频即转即弃（不落库、
  不写日志）；转写文本作为普通聊天消息的输入由前端走既有 /respond。
- POST /speak：文本 → audio/mpeg。未配置 503，前端降级浏览器朗读。
  危机回复照读（热线号码读出来更可达）。
- POST /speak/stream：同上但 chunked 流式返回（边合成边转），前端 MSE
  边下边播，感知延迟 ≈ 上游首块（实测 ~0.5s vs 整段 ~2s）。
- GET /status：前端探测（是否配置 STT/TTS），决定麦克风按钮显隐与朗读开关。

阻塞的上游调用走 asyncio.to_thread：适配层是同步 httpx / asyncio.run 包裹
的 WS 会话，事件循环内直调会卡死（minimax 路径还会 RuntimeError）。
"""

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import Response, StreamingResponse

from psych_support_bot.api.auth import request_user_id, require_auth
from psych_support_bot.infra.voice.adapter import (
    MAX_AUDIO_BYTES,
    VoiceNotConfigured,
    VoiceProviderError,
    get_stt_config,
    get_tts_config,
    synthesize,
    synthesize_stream,
    transcribe,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/voice", tags=["voice"])

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
        text = await asyncio.to_thread(transcribe, audio, filename)
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
        audio = await asyncio.to_thread(synthesize, text)
    except VoiceNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except VoiceProviderError as exc:
        logger.warning("Voice speak failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Speech synthesis failed: {exc}") from exc
    return Response(content=audio, media_type="audio/mpeg")


@router.post("/speak/stream")
async def speak_stream(request: Request, payload: dict[str, Any], _sub: str = Depends(require_auth)):
    """文本 → mp3 流（chunked）：上游音频块即产即转，前端边下边播。

    感知延迟 ≈ 上游首块到达时间（MiniMax 实测 ~0.5s），远低于整段合成。
    首个字节前的配置/校验错误仍返回 JSON 错误码；流出后中途失败只能
    截断（记日志），前端按已收音频播放。
    """
    text = str(payload.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="Empty text")
    if len(text) > _TTS_MAX_CHARS:
        raise HTTPException(status_code=422, detail=f"Text too long (max {_TTS_MAX_CHARS} chars)")
    # 配置校验前置：流开始后无法再改状态码
    if get_tts_config() is None:
        raise HTTPException(status_code=503, detail="Voice TTS is not configured")

    def _gen():
        try:
            yield from synthesize_stream(text)
        except VoiceProviderError as exc:
            # 流已开始：状态码不可改，截断表达（前端播放已收到的部分）
            logger.warning("Voice speak stream interrupted: %s", exc)

    return StreamingResponse(_gen(), media_type="audio/mpeg")
