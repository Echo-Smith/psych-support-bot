"""语音 I/O 供应商适配层（STT / TTS）。

设计约束（用户决策 2026-09-08）：
- 与主 LLM（OPENAI_*）完全分离的配置块（VOICE_STT_* / VOICE_TTS_*），
  便于独立换模型供应商；STT 缺省回落 OPENAI_* 兼容旧行为，dots 模式必须显式配置。
- 供应商双模式 STT：
  - openai：multipart POST {base}/audio/transcriptions（OpenAI/兼容网关）
  - dots：chat completions + audio_url 内容块——dots 无 /audio/transcriptions；
    audio_url 直接用 base64 data URI 内联（实测网关支持），音频随请求
    即发即逝，无需公网可达的托管 URL，也不落任何服务端状态
- TTS：OpenAI 兼容 POST {base}/audio/speech；dots 平台暂无 TTS 端点，
  未配置时路由返回 503、前端降级浏览器 SpeechSynthesis。
- STT 上下文词表（VOICE_STT_PROMPT，缺省内置心理陪伴高频词）：openai 走
  whisper prompt 字段、dots 拼进转写指令，偏向领域专名识别；minimax
  /speech_to_text 无该参数不透传。
- 音频即转即弃：不落库、不写日志，转写文本走既有消息持久化边界。

安全（Mimosa 约束）：适配器对外连的 URL（MiniMax WS 地址）做 SSRF 防护——
仅 ws/wss、拒绝环回/私有/保留地址；纯服务端配置的 base_url 不经过此检查
（部署方自担内网网关场景）。audio_url 为服务端自构造的 data URI，无外拉取。
"""

from __future__ import annotations

import asyncio
import base64
import ipaddress
import logging
import threading
import time
from collections import OrderedDict
from collections.abc import Iterator
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
import websockets

from psych_support_bot.infra.config.settings import get_settings

logger = logging.getLogger(__name__)

# 单次转写音频上限（与路由层 25MB 一致；适配器再兜底一次）
MAX_AUDIO_BYTES = 25 * 1024 * 1024
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
    provider: str  # "openai" | "dots" | "minimax"
    base_url: str
    api_key: str
    model: str
    language: str
    prompt: str = ""  # 上下文词表（空=用内置）；off/-/none=禁用


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
            prompt=s.voice_stt_prompt,
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
            prompt=s.voice_stt_prompt,
        )
    if provider == "minimax":
        # minimax ASR：Bearer + multipart /speech_to_text。凭据必须显式，
        # base_url 缺省用国内站（与 TTS 的 ws 默认域名一致）。
        api_key = s.voice_stt_api_key
        if not api_key:
            return None
        base_url = s.voice_stt_base_url or "https://api.minimax.cn/v1"
        return SttConfig(
            provider="minimax",
            base_url=base_url.rstrip("/"),
            api_key=api_key,
            model=s.voice_stt_model or "asr-1.0",
            language=s.voice_stt_language,
            prompt=s.voice_stt_prompt,
        )
    return None


# ---------------------------------------------------------------------------
# STT 上下文词表（借鉴 WhisperLiveKit 的 per-session context 注入）
# ---------------------------------------------------------------------------

# 心理陪伴领域高频词：治疗技术 + 症状体感词。空格分隔的短词表，
# 长度受控（whisper prompt 是"前文续写"语义，词表过长反而稀释偏向效果）。
_STT_PROMPT_ZH = (
    "心理咨询 正念 冥想 呼吸练习 放松 焦虑 恐慌 心悸 胸闷 头晕 出汗"
    " 失眠 抑郁 情绪 压力 创伤 着陆练习 安全岛 认知行为 肌肉放松 躯体化"
)
_STT_PROMPT_EN = (
    "counseling therapy mindfulness meditation breathing exercise relaxation "
    "anxiety panic palpitations dizziness insomnia depression stress trauma "
    "grounding safe place CBT somatic"
)


def _stt_prompt_for(config: SttConfig, language: str) -> str:
    """上下文词表解析：显式配置覆盖内置；off/-/none 禁用；未配置按语种选内置。"""
    p = (config.prompt or "").strip()
    if p.lower() in {"off", "-", "none"}:
        return ""
    if p:
        return p
    return _STT_PROMPT_EN if language == "en" else _STT_PROMPT_ZH


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
            model=s.voice_tts_model or "speech-2.8-turbo",
            voice=s.voice_tts_voice or "Chinese (Mandarin)_Warm_Bestie",
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
    if config.provider == "minimax":
        return _transcribe_minimax(config, audio_bytes, filename, language_hint)
    raise VoiceNotConfigured(f"Unknown STT provider: {config.provider}")


def _transcribe_openai(config: SttConfig, audio_bytes: bytes, filename: str, language_hint: str) -> str:
    """OpenAI 兼容 multipart /audio/transcriptions。"""
    data: dict[str, str] = {"model": config.model, "response_format": "json"}
    language = language_hint or config.language
    if language:
        data["language"] = language
    # whisper 的 prompt 是"前文续写"语义：领域词表放这里可偏向解码选词
    prompt = _stt_prompt_for(config, language)
    if prompt:
        data["prompt"] = prompt
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


def _audio_media_type(filename: str) -> str:
    """按扩展名推断 data URI 的 MIME（MediaRecorder 输出 + 常见录音格式）。"""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return {
        "webm": "audio/webm",
        "ogg": "audio/ogg",
        "oga": "audio/ogg",
        "opus": "audio/ogg",
        "mp3": "audio/mpeg",
        "mpeg": "audio/mpeg",
        "mp4": "audio/mp4",
        "m4a": "audio/mp4",
        "aac": "audio/aac",
        "wav": "audio/wav",
        "wave": "audio/wav",
    }.get(ext, "audio/webm")


def _transcribe_dots(config: SttConfig, audio_bytes: bytes, filename: str, language_hint: str) -> str:
    """dots chat completions + audio_url 内容块（base64 data URI 内联）。

    audio_url 用 data URI 直接内嵌音频（实测 dots 网关支持，2026-09-08）：
    转写请求即发即逝，无公网托管 URL、无服务端暂存状态。language 提示
    拼进转写指令文本。
    """
    mime = _audio_media_type(filename)
    encoded = base64.b64encode(audio_bytes).decode("ascii")
    media_url = f"data:{mime};base64,{encoded}"
    language = language_hint or config.language
    instruction = (
        "Transcribe this audio. Output only the transcription text, no explanation."
        if language == "en"
        else "请转写这段音频，只输出转写文本，不加任何解释。"
    )
    # dots 无 prompt 字段：词表拼进转写指令（chat 模型对"可能用词"提示受领良好）
    prompt = _stt_prompt_for(config, language)
    if prompt:
        instruction += (
            f" The speaker may use these terms: {prompt}."
            if language == "en"
            else f"讲话者可能用到这些词：{prompt}。"
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
        # dots 是 reasoning 模型：思考模式烧 2-4s 且 reasoning_content 与正文
        # 共享 max_tokens 预算。实测（2026-09-09）chat_template_kwargs 与
        # reasoning_effort 均可关思考——转写 2.5s+ → 0.6s，快 4 倍。两参并传
        # 兼容网关任一版本的参数解析。
        "reasoning_effort": "none",
        "chat_template_kwargs": {"enable_thinking": False},
        # 思考已关：纯转写文本预算足够（旧值 1024 是给共享思考留的）
        "max_tokens": 512,
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


def _transcribe_minimax(config: SttConfig, audio_bytes: bytes, filename: str, language_hint: str) -> str:
    """MiniMax 语音转文字：multipart POST {base}/speech_to_text（Bearer）。

    平台文档（platform.minimax.io/docs/api-reference/speech-to-text）：
    form 字段 model（asr-1.0）+ file + response_format=json；可选 language
    提示（BCP-47）。响应 {"text": ..., "duration": ...}；MiniMax 风格的
    base_resp.status_code 非 0 视为上游错误。上下文词表不发送：该端点
    无 prompt 参数（未知字段有被严格网关拒绝的风险），词表仅 openai/dots 生效。
    """
    data: dict[str, str] = {"model": config.model, "response_format": "json", "stream": "false"}
    language = language_hint or config.language
    if language:
        data["language"] = language
    try:
        response = httpx.post(
            f"{config.base_url}/speech_to_text",
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
        body = response.json() or {}
    except ValueError as exc:
        raise VoiceProviderError("STT upstream returned non-JSON") from exc
    base = body.get("base_resp") or {}
    status = base.get("status_code", 0)
    if status not in (0, None):
        raise VoiceProviderError(f"MiniMax ASR error {status}: {base.get('status_msg')}")
    text = (body.get("text") or "").strip()
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


# TTS 文本缓存：练习须知等固定文案每次 offer 都原文重读，属纯重复支出。
# 进程内 LRU + TTL，key 含供应商配置（换音色/模型即失效）；只缓存成功
# 路径，错误每次照实抛出。内存态即可——重启清零，无需持久化。
_TTS_CACHE_MAX_ENTRIES = 64
_TTS_CACHE_TTL_SECONDS = 30 * 60
_tts_cache_lock = threading.Lock()
_tts_cache: OrderedDict[tuple, tuple[float, bytes]] = OrderedDict()


def _tts_cache_get(key: tuple) -> bytes | None:
    with _tts_cache_lock:
        entry = _tts_cache.get(key)
        if entry is None:
            return None
        stored_at, audio = entry
        if time.monotonic() - stored_at > _TTS_CACHE_TTL_SECONDS:
            del _tts_cache[key]
            return None
        # LRU 触碰：移到末尾
        _tts_cache.move_to_end(key)
        return audio


def _tts_cache_put(key: tuple, audio: bytes) -> None:
    with _tts_cache_lock:
        _tts_cache[key] = (time.monotonic(), audio)
        _tts_cache.move_to_end(key)
        while len(_tts_cache) > _TTS_CACHE_MAX_ENTRIES:
            _tts_cache.popitem(last=False)


def _reset_tts_cache_for_tests() -> None:
    with _tts_cache_lock:
        _tts_cache.clear()


def synthesize(text: str, *, language: str = "") -> bytes:
    """文本 → mp3 音频。供应商由 VOICE_TTS_PROVIDER 决定；未配置抛 VoiceNotConfigured。

    同步接口（路由端点在线程池中运行）：minimax 走 asyncio.run 包裹的
    WS 会话，openai 走 REST。两类失败都收敛为 VoiceProviderError。
    相同文本 + 相同合成配置直接返回缓存音频（练习须知等重复文案零成本）。
    """
    config = get_tts_config()
    if config is None:
        raise VoiceNotConfigured("Voice TTS is not configured")
    cleaned = (text or "").strip()
    if not cleaned:
        raise VoiceProviderError("Empty TTS input")
    cache_key = (
        config.provider,
        config.model,
        config.voice,
        config.language_boost,
        language,
        cleaned,
    )
    cached = _tts_cache_get(cache_key)
    if cached is not None:
        return cached
    if config.provider == "minimax":
        audio = _synthesize_minimax(config, cleaned)
    elif config.provider == "openai":
        audio = _synthesize_openai(config, cleaned)
    else:
        raise VoiceNotConfigured(f"Unknown TTS provider: {config.provider}")
    _tts_cache_put(cache_key, audio)
    return audio


def synthesize_stream(text: str, *, language: str = "") -> Iterator[bytes]:
    """文本 → mp3 音频块流（边合成边出，流式播放用）。错误语义同 synthesize。

    命中文本缓存时一次性产出完整音频；未命中则透传上游分块，全部收完后
    写入缓存。openai REST 无分块语义，整段作为单块产出。
    """
    config = get_tts_config()
    if config is None:
        raise VoiceNotConfigured("Voice TTS is not configured")
    cleaned = (text or "").strip()
    if not cleaned:
        raise VoiceProviderError("Empty TTS input")
    cache_key = (
        config.provider,
        config.model,
        config.voice,
        config.language_boost,
        language,
        cleaned,
    )
    cached = _tts_cache_get(cache_key)
    if cached is not None:
        yield cached
        return
    if config.provider == "minimax":
        chunks: list[bytes] = []
        for chunk in _minimax_stream(config, cleaned):
            chunks.append(chunk)
            yield chunk
    elif config.provider == "openai":
        audio = _synthesize_openai(config, cleaned)
        chunks = [audio]
        yield audio
    else:
        raise VoiceNotConfigured(f"Unknown TTS provider: {config.provider}")
    _tts_cache_put(cache_key, b"".join(chunks))


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
                "speed": 1.05,
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
# 64kbps：语音陪伴内容与 128k 听感无差别，传输量减半（移动网络受益最大）
_MINIMAX_BITRATE = 64000
_MINIMAX_WS_OPEN_TIMEOUT = 10.0
_MINIMAX_WS_IDLE_TIMEOUT = 30.0
_MINIMAX_MAX_AUDIO_BYTES = 20 * 1024 * 1024  # 单次合成输出兜底上限


async def _run_minimax_session(config: TtsConfig, cleaned: str, emit) -> None:
    """MiniMax T2A bidi 会话：每收到一块音频调 emit(bytes)，结束语义同前。

    task_finish 在 task_continue 后立即发送（服务端先合成完缓冲中的全部
    文本，之后才回 task_finished）；is_final 只是「当前句」音频结束，
    task_finished 才是会话终点，期间所有 task_continued 块照常交出。
    """
    import json as _json

    # 配置自检：SSRF 约束同样适用于我们即将外连的 WS 地址
    validate_public_http_url(config.ws_url)

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
                    "voice_setting": {"voice_id": config.voice, "speed": 1.05, "vol": 1, "pitch": 0},
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
        # task_finish 立即发送：服务端会先合成完缓冲中的全部文本再回
        # task_finished（平台文档事件流程第 3/6 步）。
        await ws.send(_json.dumps({"event": "task_finish"}))

        audio_done = False
        emitted = 0
        while not audio_done:
            message = _json.loads(await asyncio.wait_for(ws.recv(), _MINIMAX_WS_IDLE_TIMEOUT))
            base = message.get("base_resp") or {}
            status = base.get("status_code", 0)
            if status != 0:
                raise VoiceProviderError(f"MiniMax TTS error {status}: {base.get('status_msg')}")
            event = message.get("event")
            data = message.get("data") or {}
            hex_audio = data.get("audio")
            if hex_audio:
                chunk = bytes.fromhex(hex_audio)
                emitted += len(chunk)
                if emitted > _MINIMAX_MAX_AUDIO_BYTES:
                    raise VoiceProviderError("MiniMax TTS audio exceeds size cap") from None
                emit(chunk)
            if event in ("task_finished", "task_failed"):
                audio_done = True


def _minimax_stream(config: TtsConfig, cleaned: str) -> Iterator[bytes]:
    """同步生成器：后台线程驱动 WS 会话，音频块即产即交（边合成边播用）。"""
    import queue as _queue
    import threading

    q: _queue.Queue = _queue.Queue()

    def _worker() -> None:
        try:
            asyncio.run(_run_minimax_session(config, cleaned, q.put))
        except BaseException as exc:  # 线程边界：异常作为队列结果上抛
            q.put(exc)
        finally:
            q.put(None)

    threading.Thread(target=_worker, daemon=True).start()
    while True:
        item = q.get()
        if item is None:
            return
        if isinstance(item, VoiceProviderError):
            raise item
        if isinstance(item, (OSError, websockets.WebSocketException)):
            raise VoiceProviderError(f"MiniMax WS failed: {item}") from item
        if isinstance(item, ValueError):
            # bytes.fromhex 对畸形分块的失败
            raise VoiceProviderError(f"MiniMax TTS malformed audio chunk: {item}") from item
        if isinstance(item, BaseException):
            raise item
        yield item


def _synthesize_minimax(config: TtsConfig, cleaned: str) -> bytes:
    """MiniMax speech TTS（双向流式 WebSocket），整段聚合返回。"""
    audio = b"".join(_minimax_stream(config, cleaned))
    if not audio:
        raise VoiceProviderError("MiniMax TTS returned empty audio")
    return audio
