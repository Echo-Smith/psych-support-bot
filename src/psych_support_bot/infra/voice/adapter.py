"""语音 I/O 供应商适配层（STT / TTS）。

设计约束（用户决策 2026-09-08）：
- 与主 LLM（OPENAI_*）完全分离的配置块（VOICE_STT_* / VOICE_TTS_*），
  便于独立换模型供应商；STT 缺省回落 OPENAI_* 兼容旧行为，dots 模式必须显式配置。
- 供应商双模式 STT：
  - openai：multipart POST {base}/audio/transcriptions（OpenAI/兼容网关）
  - dots：chat completions + audio_url 内容块——dots 无 /audio/transcriptions，
    且只接受「模型服务可直接访问」的公网音频 URL，故服务端内存暂存音频、
    签发一次性下载 token（media_store），转写请求即拉即用
- TTS：OpenAI 兼容 POST {base}/audio/speech；dots 平台暂无 TTS 端点，
  未配置时路由返回 503、前端降级浏览器 SpeechSynthesis。
- 音频即转即弃：不落库、不写日志，转写文本走既有消息持久化边界。

安全（Mimosa 约束）：适配器对用户可见的 URL 输入（audio_url 的 host）
做 SSRF 防护——仅 http/https、拒绝环回/私有/保留地址。媒体托管 URL 由
服务端自签发（VOICE_MEDIA_PUBLIC_BASE_URL），不取自用户输入。
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
import websockets

from psych_support_bot.infra.config.settings import get_settings

logger = logging.getLogger(__name__)

# 单次转写音频上限（与路由层 25MB 一致；适配器再兜底一次）
MAX_AUDIO_BYTES = 25 * 1024 * 1024
# dots chat completions 转写输出的 max_tokens（转写文本上限，防思考烧穿预算）
_DOTS_STT_MAX_TOKENS = 1024
_REQUEST_TIMEOUT = 60.0


class VoiceNotConfigured(Exception):
    """所需语音端点未配置（路由层转 503，前端降级）。"""


class VoiceProviderError(Exception):
    """上游语音供应商调用失败（网络/HTTP/空响应）。"""


def validate_public_http_url(url: str) -> str:
    """SSRF 防护：仅 http/https/ws/wss 且 host 不得是环回/私有/保留地址。

    用于任何「可能受用户输入影响」的 URL 校验（dots audio_url 场景、
    MiniMax WS URL 自检）；纯服务端配置的 base_url 不经过此检查
    （部署方自担内网网关场景）。返回规范化 URL，不合法抛 VoiceProviderError。
    """
    try:
        parsed = urlparse(url)
    except ValueError as exc:
        raise VoiceProviderError(f"Invalid URL: {exc}") from exc
    if parsed.scheme not in {"http", "https", "ws", "wss"}:
        raise VoiceProviderError("Only http/https/ws/wss URLs are allowed")
    host = parsed.hostname or ""
    if not host:
        raise VoiceProviderError("URL has no host")
    if host in {"localhost"} or host.endswith(".localhost") or host.endswith(".local"):
        raise VoiceProviderError("Loopback/local hostnames are not allowed")
    try:
        # 允许的 host 也可以是 IP 字面量；域名解析结果在请求时仍可能指向
        # 内网（DNS rebinding），此处按字面量与解析双重校验。
        addr_info = ipaddress.ip_address(host)
    except ValueError:
        import socket

        try:
            resolved = {ai[4][0] for ai in socket.getaddrinfo(host, None)}
        except OSError as exc:
            raise VoiceProviderError(f"Cannot resolve host {host!r}") from exc
        for ip_text in resolved:
            if _is_forbidden_ip(ipaddress.ip_address(ip_text)):
                raise VoiceProviderError("Host resolves to a private/reserved address") from None
        return url
    if _is_forbidden_ip(addr_info):
        raise VoiceProviderError("Private/reserved IP addresses are not allowed")
    return url


def _is_forbidden_ip(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        addr.is_loopback
        or addr.is_private
        or addr.is_reserved
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_unspecified
    )


# ---------------------------------------------------------------------------
# 配置解析
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SttConfig:
    provider: str  # "openai" | "dots"
    base_url: str
    api_key: str
    model: str
    language: str


@dataclass(frozen=True)
class TtsConfig:
    provider: str  # "openai" | "minimax"
    base_url: str  # openai: REST base；minimax: ""（用 ws_url）
    ws_url: str  # minimax: wss://api.minimax.cn/ws/v1/t2a_v2_bidi
    api_key: str
    model: str
    voice: str
    language_boost: str = ""


def get_stt_config() -> SttConfig | None:
    s = get_settings()
    provider = (s.voice_stt_provider or "").strip().lower()
    if not provider:
        # 未显式配置 provider：仅有 OPENAI_* 配置时回落 openai 兼容模式
        # （旧部署行为兼容）；否则视为未配置语音。
        if s.openai_api_key:
            provider = "openai"
        else:
            return None
    if provider == "openai":
        base_url = s.voice_stt_base_url or s.openai_base_url
        api_key = s.voice_stt_api_key or s.openai_api_key
        model = s.voice_stt_model or "whisper-1"
        if not (base_url and api_key):
            return None
        return SttConfig(
            provider="openai",
            base_url=base_url.rstrip("/"),
            api_key=api_key,
            model=model,
            language=s.voice_stt_language,
        )
    if provider == "dots":
        # dots 模式必须全显式：不回落 OPENAI_*（网关语义不同，静默回落
        # 会把 multipart 请求打进 chat completions 端点）。
        base_url = s.voice_stt_base_url
        api_key = s.voice_stt_api_key
        model = s.voice_stt_model
        if not (base_url and api_key and model):
            return None
        return SttConfig(
            provider="dots",
            base_url=base_url.rstrip("/"),
            api_key=api_key,
            model=model,
            language=s.voice_stt_language,
        )
    return None


def get_tts_config() -> TtsConfig | None:
    s = get_settings()
    api_key = s.voice_tts_api_key
    if not api_key:
        return None
    provider = (s.voice_tts_provider or "").strip().lower()
    if not provider:
        # 缺省按 base_url 判定（旧行为兼容：配了 base_url 即 openai 兼容模式）
        provider = "openai" if s.voice_tts_base_url else ""
        if not provider:
            return None
    if provider == "openai":
        base_url = s.voice_tts_base_url
        if not base_url:
            return None
        return TtsConfig(
            provider="openai",
            base_url=base_url.rstrip("/"),
            ws_url="",
            api_key=api_key,
            model=s.voice_tts_model or "tts-1",
            voice=s.voice_tts_voice or "alloy",
        )
    if provider == "minimax":
        ws_url = (s.voice_tts_ws_url or "wss://api.minimax.cn/ws/v1/t2a_v2_bidi").strip()
        if not ws_url.startswith(("wss://", "ws://")):
            raise VoiceProviderError("VOICE_TTS_WS_URL must start with wss:// or ws://")
        return TtsConfig(
            provider="minimax",
            base_url="",
            ws_url=ws_url,
            api_key=api_key,
            model=s.voice_tts_model or "speech-2.8-hd",
            voice=s.voice_tts_voice or "male-qn-qingse",
            language_boost=s.voice_tts_language_boost or "",
        )
    return None


# ---------------------------------------------------------------------------
# STT
# ---------------------------------------------------------------------------


def transcribe(
    audio_bytes: bytes,
    filename: str,
    *,
    language_hint: str = "",
) -> str:
    """音频 → 文本。供应商由 VOICE_STT_PROVIDER 决定；失败抛 VoiceProviderError。"""
    if not audio_bytes:
        raise VoiceProviderError("Empty audio payload")
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise VoiceProviderError("Audio payload too large")
    config = get_stt_config()
    if config is None:
        raise VoiceNotConfigured("Voice STT is not configured")
    if config.provider == "openai":
        return _transcribe_openai(config, audio_bytes, filename, language_hint)
    if config.provider == "dots":
        return _transcribe_dots(config, audio_bytes, filename, language_hint)
    raise VoiceNotConfigured(f"Unknown STT provider: {config.provider}")


def _transcribe_openai(config: SttConfig, audio_bytes: bytes, filename: str, language_hint: str) -> str:
    """OpenAI 兼容 multipart /audio/transcriptions。"""
    data: dict[str, str] = {"model": config.model, "response_format": "json"}
    language = language_hint or config.language
    if language:
        data["language"] = language
    try:
        response = httpx.post(
            f"{config.base_url}/audio/transcriptions",
            headers={"Authorization": f"Bearer {config.api_key}"},
            files={"file": (filename, audio_bytes)},
            data=data,
            timeout=_REQUEST_TIMEOUT,
        )
    except httpx.HTTPError as exc:
        raise VoiceProviderError(f"STT request failed: {exc}") from exc
    if response.status_code >= 400:
        raise VoiceProviderError(f"STT upstream error {response.status_code}")
    try:
        text = (response.json() or {}).get("text", "")
    except ValueError as exc:
        raise VoiceProviderError("STT upstream returned non-JSON") from exc
    text = (text or "").strip()
    if not text:
        raise VoiceProviderError("STT upstream returned empty text")
    return text


def _transcribe_dots(config: SttConfig, audio_bytes: bytes, filename: str, language_hint: str) -> str:
    """dots chat completions + audio_url 内容块。

    dots 只接受模型服务可直接访问的公网 URL：音频先入 media_store（内存，
    单次下载即焚），以服务端自签发 URL 交给 dots 拉取。language 提示拼进
    转写指令文本。
    """
    from psych_support_bot.infra.voice import media_store

    media_url = media_store.issue_url(audio_bytes, filename)
    # 自签发 URL 也过一遍 SSRF 校验：公网 base 配置错误（内网地址）时
    # 宁可失败也不把内网地址暴露给上游。
    validate_public_http_url(media_url)
    instruction = (
        "请转写这段音频，只输出转写文本，不加任何解释。"
        if (language_hint or config.language) != "en"
        else ("Transcribe this audio. Output only the transcription text, no explanation.")
    )
    payload = {
        "model": config.model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "audio_url", "audio_url": {"url": media_url}},
                    {"type": "text", "text": instruction},
                ],
            }
        ],
        "stream": False,
        "max_tokens": _DOTS_STT_MAX_TOKENS,
    }
    try:
        response = httpx.post(
            f"{config.base_url}/chat/completions",
            headers={"Content-Type": "application/json", "api-key": config.api_key},
            json=payload,
            timeout=_REQUEST_TIMEOUT,
        )
    except httpx.HTTPError as exc:
        raise VoiceProviderError(f"STT request failed: {exc}") from exc
    finally:
        # 音频 URL 即用即焚：无论请求成败都销毁暂存（含失败重试由前端
        # 重新录音触发新上传，不复用旧音频）。
        media_store.discard_url(media_url)
    if response.status_code >= 400:
        raise VoiceProviderError(f"STT upstream error {response.status_code}")
    try:
        choices = response.json().get("choices") or []
        text = ((choices[0].get("message") or {}).get("content") or "").strip() if choices else ""
    except (ValueError, IndexError, KeyError) as exc:
        raise VoiceProviderError("STT upstream returned unexpected shape") from exc
    # dots 思考模型可能把 reasoning 混入 content：剥掉思维链痕迹
    text = _strip_reasoning_artifacts(text)
    if not text:
        raise VoiceProviderError("STT upstream returned empty text")
    return text


def _strip_reasoning_artifacts(text: str) -> str:
    """dots 思考模型的转写输出偶带思维链前缀；保守剥离已知标记。"""
    for marker in ("Thinking Process:", "**Transcription**:", "Transcription:"):
        idx = text.find(marker)
        if idx != -1:
            text = text[idx + len(marker) :]
    return text.strip().strip('"“”').strip()


# ---------------------------------------------------------------------------
# TTS
# ---------------------------------------------------------------------------


def synthesize(text: str, *, language: str = "") -> bytes:
    """文本 → mp3 音频。供应商由 VOICE_TTS_PROVIDER 决定；未配置抛 VoiceNotConfigured。

    同步接口（路由端点在线程池中运行）：minimax 走 asyncio.run 包裹的
    WS 会话，openai 走 REST。两类失败都收敛为 VoiceProviderError。
    """
    config = get_tts_config()
    if config is None:
        raise VoiceNotConfigured("Voice TTS is not configured")
    cleaned = (text or "").strip()
    if not cleaned:
        raise VoiceProviderError("Empty TTS input")
    if config.provider == "minimax":
        return _synthesize_minimax(config, cleaned)
    if config.provider == "openai":
        return _synthesize_openai(config, cleaned)
    raise VoiceNotConfigured(f"Unknown TTS provider: {config.provider}")


def _synthesize_openai(config: TtsConfig, cleaned: str) -> bytes:
    try:
        response = httpx.post(
            f"{config.base_url}/audio/speech",
            headers={"Authorization": f"Bearer {config.api_key}"},
            json={
                "model": config.model,
                "voice": config.voice,
                "input": cleaned,
                "response_format": "mp3",
                "speed": 0.95,
            },
            timeout=_REQUEST_TIMEOUT,
        )
    except httpx.HTTPError as exc:
        raise VoiceProviderError(f"TTS request failed: {exc}") from exc
    if response.status_code >= 400:
        raise VoiceProviderError(f"TTS upstream error {response.status_code}")
    audio = response.content or b""
    if not audio:
        raise VoiceProviderError("TTS upstream returned empty audio")
    return audio


# MiniMax T2A 双向流式（wss /ws/v1/t2a_v2_bidi）参数
_MINIMAX_SAMPLE_RATE = 32000
_MINIMAX_BITRATE = 128000
_MINIMAX_WS_OPEN_TIMEOUT = 10.0
_MINIMAX_WS_IDLE_TIMEOUT = 30.0
_MINIMAX_MAX_AUDIO_BYTES = 20 * 1024 * 1024  # 单次合成输出兜底上限


def _synthesize_minimax(config: TtsConfig, cleaned: str) -> bytes:
    """MiniMax speech TTS（双向流式 WebSocket）。

    事件流（platform.minimax.cn/docs api-reference/speech-t2a-websocket-bidi）：
    wss 握手（Bearer）→ connected_success → task_start（音色/音频参数）
    → task_started → task_continue（全文一次发送，服务端攒句）→
    task_continued 分块返回 hex 音频（is_final=true 表示本次音频结束）
    → task_finish → task_finished → 连接关闭。音频按序拼接为完整 mp3。
    """
    import json as _json

    # 配置自检：SSRF 约束同样适用于我们即将外连的 WS 地址
    validate_public_http_url(config.ws_url)

    async def _run() -> bytes:
        audio_chunks: list[bytes] = []
        async with websockets.connect(
            config.ws_url,
            additional_headers={"Authorization": f"Bearer {config.api_key}"},
            open_timeout=_MINIMAX_WS_OPEN_TIMEOUT,
            close_timeout=5,
        ) as ws:
            connected = _json.loads(await asyncio.wait_for(ws.recv(), _MINIMAX_WS_IDLE_TIMEOUT))
            if connected.get("event") != "connected_success":
                raise VoiceProviderError(f"MiniMax handshake failed: {connected.get('base_resp')}")

            await ws.send(
                _json.dumps(
                    {
                        "event": "task_start",
                        "model": config.model,
                        **({"language_boost": config.language_boost} if config.language_boost else {}),
                        "voice_setting": {"voice_id": config.voice, "speed": 0.95, "vol": 1, "pitch": 0},
                        "audio_setting": {
                            "sample_rate": _MINIMAX_SAMPLE_RATE,
                            "bitrate": _MINIMAX_BITRATE,
                            "format": "mp3",
                            "channel": 1,
                        },
                    }
                )
            )
            started = _json.loads(await asyncio.wait_for(ws.recv(), _MINIMAX_WS_IDLE_TIMEOUT))
            if started.get("event") != "task_started":
                raise VoiceProviderError(f"MiniMax task_start failed: {started.get('base_resp')}")

            await ws.send(_json.dumps({"event": "task_continue", "text": cleaned}))

            audio_done = False
            while not audio_done:
                message = _json.loads(await asyncio.wait_for(ws.recv(), _MINIMAX_WS_IDLE_TIMEOUT))
                base = message.get("base_resp") or {}
                status = base.get("status_code", 0)
                if status != 0:
                    raise VoiceProviderError(f"MiniMax TTS error {status}: {base.get('status_msg')}")
                data = message.get("data") or {}
                hex_audio = data.get("audio")
                if hex_audio:
                    audio_chunks.append(bytes.fromhex(hex_audio))
                    if sum(len(c) for c in audio_chunks) > _MINIMAX_MAX_AUDIO_BYTES:
                        raise VoiceProviderError("MiniMax TTS audio exceeds size cap") from None
                if message.get("is_final"):
                    audio_done = True

            await ws.send(_json.dumps({"event": "task_finish"}))
            # task_finished 到达前连接可能已被服务端关闭——尽力而为
            try:
                while True:
                    final = _json.loads(await asyncio.wait_for(ws.recv(), _MINIMAX_WS_IDLE_TIMEOUT))
                    if final.get("event") in {"task_finished", "task_failed"}:
                        break
            except (TimeoutError, websockets.ConnectionClosed):
                pass

        audio = b"".join(audio_chunks)
        if not audio:
            raise VoiceProviderError("MiniMax TTS returned empty audio")
        return audio

    try:
        return asyncio.run(_run())
    except VoiceProviderError:
        raise
    except (OSError, websockets.WebSocketException) as exc:
        raise VoiceProviderError(f"MiniMax WS failed: {exc}") from exc
    except ValueError as exc:
        # bytes.fromhex 对畸形分块的失败
        raise VoiceProviderError(f"MiniMax TTS malformed audio chunk: {exc}") from exc
