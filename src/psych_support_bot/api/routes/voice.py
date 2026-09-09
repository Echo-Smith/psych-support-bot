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
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import Response, StreamingResponse

from psych_support_bot.api.auth import decode_access_token, request_user_id, require_auth
from psych_support_bot.infra.config.settings import get_settings
from psych_support_bot.infra.voice.adapter import (
    MAX_AUDIO_BYTES,
    _MINIMAX_BITRATE,
    _MINIMAX_SAMPLE_RATE,
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


# ---------------------------------------------------------------------------
# P1：整轮单会话全双工 TTS（WS）
# 浏览器开一条 WS，LLM 流式产出的每个句子以 {"type":"say"} 推入；服务器用
# 同一个 MiniMax bidi 会话逐句 task_continue，音频块实时回推
# {"type":"audio","b64"}，sentence_end 为分句边界。全文结束发
# {"type":"end"} → 上游合成残留后回 {"type":"round_end"}。
# 打断：{"type":"abort"} → task_cancel。鉴权走 query token（浏览器 WS 无法
# 自定义 Header）。音频仍经服务器（key 不出服务端），但一条会话服务整轮，
# 消除句间 HTTP 往返与 WS 握手成本。
# ---------------------------------------------------------------------------

ws_router = APIRouter(prefix="/v1/voice", tags=["voice"])


@ws_router.websocket("/tts/live")
async def tts_live(websocket: WebSocket, token: str = Query(default="")):
    settings = get_settings()
    if settings.auth_enabled:
        try:
            decode_access_token(token)
        except Exception:
            await websocket.close(code=4401)
            return

    config = get_tts_config()
    await websocket.accept()
    if config is None or config.provider != "minimax":
        logger.warning("TTS live: TTS not configured, closing")
        await websocket.send_json({"type": "error", "detail": "TTS not configured"})
        await websocket.close()
        return

    import websockets as mm_lib

    text_q: asyncio.Queue = asyncio.Queue()

    async def read_client() -> None:
        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    msg = json.loads(raw)
                except ValueError:
                    continue
                t = msg.get("type")
                if t == "say":
                    text = str(msg.get("text") or "").strip()
                    if text:
                        await text_q.put(text)
                elif t == "end":
                    await text_q.put(None)
                    return
                elif t == "abort":
                    await text_q.put("__abort__")
                    return
        except Exception:
            pass
        finally:
            await text_q.put(None)

    try:
        async with mm_lib.connect(
            config.ws_url,
            additional_headers={"Authorization": f"Bearer {config.api_key}"},
            open_timeout=10,
            close_timeout=5,
        ) as mmws:
            logger.info("TTS live: upstream connected")
            await websocket.send_json({"type": "ready"})
            # 上游任务开启（音色/音频参数与整段合成路径一致；64kbps 减半传输）
            await mmws.send(json.dumps({
                "event": "task_start",
                "model": config.model,
                **({"language_boost": config.language_boost} if config.language_boost else {}),
                "voice_setting": {"voice_id": config.voice, "speed": 1.05, "vol": 1, "pitch": 0},
                "audio_setting": {
                    "sample_rate": _MINIMAX_SAMPLE_RATE,
                    "bitrate": _MINIMAX_BITRATE,
                    "format": "mp3",
                    "channel": 1,
                },
            }))
            started = json.loads(await asyncio.wait_for(mmws.recv(), timeout=15))
            # 网关可能重复推 connected_success（实测每次 task_start 响应前
            # 都有一条）；跳过直到看到 task_started 或明确失败。
            while started.get("event") not in ("task_started", "task_failed") and started.get("base_resp", {}).get("status_code", 0) == 0:
                started = json.loads(await asyncio.wait_for(mmws.recv(), timeout=15))
            if started.get("event") != "task_started":
                base = started.get("base_resp") or {}
                logger.warning("TTS live task_start failed: %s", base)
                await websocket.send_json({"type": "round_end"})
                return
            # 客户端读取循环与上游音频泵并行：say 逐句喂入，音频块实时回推
            reader_task = asyncio.ensure_future(read_client())

            async def client_to_mm() -> None:
                # 客户端句子 → MiniMax task_continue；end → task_finish；
                # abort → task_cancel
                sent_finish = False
                while True:
                    item = await text_q.get()
                    if item == "__abort__":
                        await mmws.send(json.dumps({"event": "task_cancel"}))
                        return
                    if item is None:
                        if not sent_finish:
                            await mmws.send(json.dumps({"event": "task_finish"}))
                            sent_finish = True
                        return
                    await mmws.send(json.dumps({"event": "task_continue", "text": item}))

            ct = asyncio.ensure_future(client_to_mm())
            while True:
                raw = await asyncio.wait_for(mmws.recv(), timeout=120)
                msg = json.loads(raw)
                base = msg.get("base_resp") or {}
                status = base.get("status_code", 0)
                if status != 0:
                    logger.warning("TTS live upstream error %s: %s", status, base.get("status_msg"))
                    await websocket.send_json({"type": "round_end"})
                    return
                event = msg.get("event")
                data = msg.get("data") or {}
                if data.get("audio"):
                    await websocket.send_json({"type": "audio", "b64": data["audio"]})
                if msg.get("is_final"):
                    # 句级边界：前端以此切分播放单元（sentence_start/end 事件
                    # 名沿用语义）。会话不终态，下一句 task_continue 继续喂。
                    await websocket.send_json({"type": "sentence_end"})
                if event in ("task_finished", "task_failed"):
                    await websocket.send_json({"type": "round_end"})
                    return
    except WebSocketDisconnect:
        logger.info("TTS live: client disconnected")
    except Exception as exc:  # noqa: BLE001 — WS 会话任一端故障都优雅关闭
        logger.warning("TTS live session ended: %s", exc, exc_info=True)
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
