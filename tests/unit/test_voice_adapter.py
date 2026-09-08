"""语音 I/O 适配层单测。

覆盖：配置解析（openai/dots/未配置/回落）、SSRF 防护、openai/dots STT
调用（mock httpx）、TTS 调用与未配置 503 语义。不发真实网络请求。

凭据值经 _fake_key() 现场生成（非硬编码），仅用于断言配置透传。
"""

import base64
import secrets

import httpx
import pytest

from psych_support_bot.infra.config.settings import get_settings
from psych_support_bot.infra.voice.adapter import (
    VoiceNotConfigured,
    VoiceProviderError,
    get_stt_config,
    get_tts_config,
    synthesize,
    transcribe,
    validate_public_http_url,
)


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _fake_key(prefix: str = "test") -> str:
    """现场生成假凭据（单测专用，无真实密钥）。"""
    return f"{prefix}-{secrets.token_hex(8)}"


@pytest.fixture()
def stt_key() -> str:
    return _fake_key("stt")


@pytest.fixture()
def tts_key() -> str:
    return _fake_key("tts")


@pytest.fixture()
def dots_key() -> str:
    return _fake_key("dots")


def _configure(stt_key: str = "", tts_key: str = "", **overrides) -> None:
    """直接改环境变量（get_settings 已被 cache_clear，重新构造生效）。"""
    import os

    defaults = {
        "VOICE_STT_PROVIDER": "openai",
        "VOICE_STT_BASE_URL": "https://stt.example.com/v1",
        "VOICE_STT_API_KEY": stt_key,
        "VOICE_STT_MODEL": "whisper-1",
        # 显式钉住 provider：开发机 .env 可能带真实 minimax 配置，
        # 不钉会把 openai 用例的 mock 请求路由到 WS 路径。
        "VOICE_TTS_PROVIDER": "openai",
        "VOICE_TTS_BASE_URL": "https://tts.example.com/v1",
        "VOICE_TTS_API_KEY": tts_key,
        "VOICE_TTS_MODEL": "tts-1",
        "VOICE_TTS_VOICE": "alloy",
        "OPENAI_API_KEY": "",
        "OPENAI_BASE_URL": "",
    }
    defaults.update(overrides)
    for key, value in defaults.items():
        os.environ[key] = value


# ---------------------------------------------------------------------------
# 配置解析
# ---------------------------------------------------------------------------


def test_stt_config_explicit_openai(stt_key) -> None:
    _configure(stt_key=stt_key)
    config = get_stt_config()
    assert config is not None
    assert config.provider == "openai"
    assert config.model == "whisper-1"
    assert config.api_key == stt_key


def test_stt_config_dots_mode_requires_explicit_config(dots_key) -> None:
    _configure(VOICE_STT_PROVIDER="dots", VOICE_STT_BASE_URL="", VOICE_STT_API_KEY="", VOICE_STT_MODEL="")
    # dots 模式不回落 OPENAI_*：配置不全即视为未配置（宁可麦克风隐藏，
    # 不可把 multipart 请求静默打进 chat completions 端点）。
    assert get_stt_config() is None


def test_stt_config_falls_back_to_openai_when_unconfigured(stt_key) -> None:
    import os

    _configure(VOICE_STT_PROVIDER="", VOICE_STT_BASE_URL="", VOICE_STT_API_KEY="")
    # 上面 OPENAI_API_KEY 置空 → 全空 → 未配置
    assert get_stt_config() is None
    os.environ["OPENAI_API_KEY"] = stt_key
    os.environ["OPENAI_BASE_URL"] = "https://api.main.com/v1"
    get_settings.cache_clear()  # get_settings 已缓存第一次构造，需清缓存重读
    config = get_stt_config()
    assert config is not None and config.provider == "openai"
    assert config.api_key == stt_key


def test_stt_unconfigured_when_nothing_set(stt_key) -> None:
    _configure(VOICE_STT_PROVIDER="", VOICE_STT_BASE_URL="", VOICE_STT_API_KEY="")
    assert get_stt_config() is None


def test_tts_config(tts_key) -> None:
    _configure(tts_key=tts_key)
    config = get_tts_config()
    assert config is not None
    assert config.voice == "alloy"


def test_tts_unconfigured() -> None:
    _configure(VOICE_TTS_BASE_URL="", VOICE_TTS_API_KEY="")
    assert get_tts_config() is None


# ---------------------------------------------------------------------------
# SSRF 防护
# ---------------------------------------------------------------------------


def test_ssrf_rejects_loopback_and_private() -> None:
    for bad in (
        "http://localhost:8000/v1/voice/tmp/x",
        "http://127.0.0.1/v1/voice/tmp/x",
        "http://10.0.0.5/x",
        "http://192.168.1.1/x",
        "http://172.16.0.1/x",
        "file:///etc/passwd",
        "ftp://example.com/x",
        "http://169.254.169.254/latest/meta-data",
        "http://[::1]/x",
    ):
        with pytest.raises(VoiceProviderError):
            validate_public_http_url(bad)


def test_ssrf_rejects_host_resolving_to_private(monkeypatch) -> None:
    import socket

    def fake_getaddrinfo(host, *args, **kwargs):
        if host == "rebind.example.com":
            return [(2, 1, 6, "", ("127.0.0.1", 0))]
        raise OSError("no resolve")

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    with pytest.raises(VoiceProviderError):
        validate_public_http_url("https://rebind.example.com/v1/voice/tmp/x")


def test_ssrf_accepts_public_https() -> None:
    # example.com 真实可解析为公网 IP；断言校验通过并原样返回。
    url = validate_public_http_url("https://storage.googleapis.com/example.mp3")
    assert url.startswith("https://")


# ---------------------------------------------------------------------------
# STT 调用（mock httpx）
# ---------------------------------------------------------------------------


def test_transcribe_openai_success(monkeypatch, stt_key) -> None:
    _configure(stt_key=stt_key)

    def fake_post(url, **kwargs):
        assert url.endswith("/audio/transcriptions")
        assert kwargs["headers"]["Authorization"] == f"Bearer {stt_key}"
        assert kwargs["data"]["model"] == "whisper-1"
        return httpx.Response(200, json={"text": " 我现在心跳很快 "}, request=httpx.Request("POST", url))

    monkeypatch.setattr("psych_support_bot.infra.voice.adapter.httpx.post", fake_post)
    assert transcribe(b"audio", "a.webm") == "我现在心跳很快"


def test_transcribe_unconfigured_raises_not_configured() -> None:
    _configure(VOICE_STT_PROVIDER="", VOICE_STT_BASE_URL="", VOICE_STT_API_KEY="")
    with pytest.raises(VoiceNotConfigured):
        transcribe(b"audio", "a.webm")


def test_transcribe_openai_upstream_error(stt_key, monkeypatch) -> None:
    _configure(stt_key=stt_key)
    monkeypatch.setattr(
        "psych_support_bot.infra.voice.adapter.httpx.post",
        lambda url, **kw: httpx.Response(500, request=httpx.Request("POST", url)),
    )
    with pytest.raises(VoiceProviderError):
        transcribe(b"audio", "a.webm")


def test_transcribe_minimax_success(monkeypatch, tts_key) -> None:
    _configure(
        stt_key=tts_key,
        VOICE_STT_PROVIDER="minimax",
        VOICE_STT_BASE_URL="",
        VOICE_STT_MODEL="",
    )
    config = get_stt_config()
    assert config is not None and config.provider == "minimax"
    # base_url/model 缺省值：国内站 + asr-1.0
    assert config.base_url == "https://api.minimax.cn/v1"
    assert config.model == "asr-1.0"

    def fake_post(url, **kwargs):
        assert url == "https://api.minimax.cn/v1/speech_to_text"
        assert kwargs["headers"]["Authorization"] == f"Bearer {tts_key}"
        assert kwargs["data"]["model"] == "asr-1.0"
        assert kwargs["data"]["language"] == "zh"
        filename, content = kwargs["files"]["file"][0], kwargs["files"]["file"][1]
        assert filename == "a.m4a" and content == b"audio"
        return httpx.Response(
            200,
            json={"text": " 我现在心跳很快 ", "duration": 2.1, "base_resp": {"status_code": 0}},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr("psych_support_bot.infra.voice.adapter.httpx.post", fake_post)
    assert transcribe(b"audio", "a.m4a") == "我现在心跳很快"


def test_transcribe_minimax_upstream_error(monkeypatch, tts_key) -> None:
    _configure(
        stt_key=tts_key,
        VOICE_STT_PROVIDER="minimax",
        VOICE_STT_MODEL="",
    )

    def fake_post(url, **kwargs):
        # MiniMax 风格业务错误：HTTP 200 但 base_resp.status_code 非 0
        return httpx.Response(
            200,
            json={"base_resp": {"status_code": 1004, "status_msg": "invalid params"}},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr("psych_support_bot.infra.voice.adapter.httpx.post", fake_post)
    with pytest.raises(VoiceProviderError):
        transcribe(b"audio", "a.m4a")


def test_transcribe_minimax_requires_key() -> None:
    _configure(VOICE_STT_PROVIDER="minimax", VOICE_STT_API_KEY="")
    assert get_stt_config() is None


def test_transcribe_dots_mode_full_flow(monkeypatch, dots_key) -> None:

    _configure(
        stt_key=dots_key,
        VOICE_STT_PROVIDER="dots",
        VOICE_STT_BASE_URL="https://dots.example.com/v1",
        VOICE_STT_MODEL="dots3-note-prev",
    )

    captured: dict = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        if url.endswith("/chat/completions"):
            audio_url = kwargs["json"]["messages"][0]["content"][0]["audio_url"]["url"]
            # audio_url 为 base64 data URI 内联：header + 可逆解码
            scheme, b64 = audio_url.split(";base64,", 1)
            assert scheme == "data:audio/webm"
            assert base64.b64decode(b64) == b"audio-bytes"
            assert kwargs["headers"]["api-key"] == dots_key
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": "我心跳好快。"}}]},
                request=httpx.Request("POST", url),
            )
        raise AssertionError(url)

    monkeypatch.setattr("psych_support_bot.infra.voice.adapter.httpx.post", fake_post)
    assert transcribe(b"audio-bytes", "a.webm") == "我心跳好快。"
    assert captured["url"].endswith("/chat/completions")


def test_transcribe_dots_media_type_by_extension(monkeypatch, dots_key) -> None:
    _configure(
        stt_key=dots_key,
        VOICE_STT_PROVIDER="dots",
        VOICE_STT_BASE_URL="https://dots.example.com/v1",
        VOICE_STT_MODEL="m",
    )
    mimes: list[str] = []

    def fake_post(url, **kwargs):
        audio_url = kwargs["json"]["messages"][0]["content"][0]["audio_url"]["url"]
        mimes.append(audio_url.split(";base64,", 1)[0])
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "好"}}]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr("psych_support_bot.infra.voice.adapter.httpx.post", fake_post)
    transcribe(b"a", "clip.m4a")
    transcribe(b"a", "note.mp3")
    transcribe(b"a", "noext")
    assert mimes == ["data:audio/mp4", "data:audio/mpeg", "data:audio/webm"]


def test_transcribe_dots_upstream_error(monkeypatch, dots_key) -> None:

    _configure(
        stt_key=dots_key,
        VOICE_STT_PROVIDER="dots",
        VOICE_STT_BASE_URL="https://dots.example.com/v1",
        VOICE_STT_MODEL="m",
    )

    def fake_post(url, **kwargs):
        return httpx.Response(502, request=httpx.Request("POST", url))

    monkeypatch.setattr("psych_support_bot.infra.voice.adapter.httpx.post", fake_post)
    with pytest.raises(VoiceProviderError):
        transcribe(b"audio-bytes", "a.webm")


# ---------------------------------------------------------------------------
# TTS 调用
# ---------------------------------------------------------------------------


def test_synthesize_success(monkeypatch, tts_key) -> None:
    _configure(tts_key=tts_key)

    def fake_post(url, **kwargs):
        assert url.endswith("/audio/speech")
        assert kwargs["json"]["input"].strip()
        assert kwargs["json"]["response_format"] == "mp3"
        return httpx.Response(200, content=b"ID3mp3bytes", request=httpx.Request("POST", url))

    monkeypatch.setattr("psych_support_bot.infra.voice.adapter.httpx.post", fake_post)
    assert synthesize("你好") == b"ID3mp3bytes"


def test_synthesize_unconfigured() -> None:
    _configure(VOICE_TTS_BASE_URL="", VOICE_TTS_API_KEY="")
    with pytest.raises(VoiceNotConfigured):
        synthesize("你好")


def test_synthesize_rejects_empty_text(tts_key) -> None:
    _configure(tts_key=tts_key)
    with pytest.raises(VoiceProviderError):
        synthesize("   ")


# ---------------------------------------------------------------------------
# MiniMax TTS（wss /ws/v1/t2a_v2_bidi，mock websockets）
# ---------------------------------------------------------------------------


class _FakeWebSocket:
    """按脚本回放的假 WS：recv 依次弹出（dict→json 帧，Exception→抛出）。"""

    def __init__(self, script: list) -> None:
        self._script = list(script)
        self.sent: list[dict] = []

    async def send(self, raw: str) -> None:
        import json as _json

        self.sent.append(_json.loads(raw))

    async def recv(self) -> str:
        import json as _json

        if not self._script:
            raise TimeoutError("script exhausted")
        item = self._script.pop(0)
        if isinstance(item, Exception):
            raise item
        return _json.dumps(item)

    async def __aenter__(self) -> "_FakeWebSocket":
        return self

    async def __aexit__(self, *args) -> None:
        return None


def _configure_minimax(tts_key: str, ws_url: str = "wss://api.minimax.cn/ws/v1/t2a_v2_bidi", **overrides) -> None:

    _configure(
        tts_key=tts_key,
        VOICE_TTS_PROVIDER="minimax",
        VOICE_TTS_WS_URL=ws_url,
        VOICE_TTS_MODEL="speech-2.8-hd",
        VOICE_TTS_VOICE="male-qn-qingse",
        **overrides,
    )


def test_tts_config_minimax(tts_key) -> None:
    _configure_minimax(tts_key)
    config = get_tts_config()
    assert config is not None and config.provider == "minimax"
    assert config.model == "speech-2.8-hd"
    assert config.voice == "male-qn-qingse"


def test_tts_config_minimax_requires_key() -> None:
    _configure(VOICE_TTS_PROVIDER="minimax", VOICE_TTS_API_KEY="", VOICE_TTS_BASE_URL="")
    assert get_tts_config() is None


def test_synthesize_minimax_success(monkeypatch, tts_key) -> None:
    _configure_minimax(tts_key)
    hex_a = b"chunk-a".hex()
    hex_b = b"chunk-b".hex()
    fake = _FakeWebSocket(
        [
            {"event": "connected_success", "base_resp": {"status_code": 0}},
            {"event": "task_started", "base_resp": {"status_code": 0}},
            {"data": {"audio": hex_a}, "is_final": False, "base_resp": {"status_code": 0}},
            {"data": {"audio": hex_b}, "is_final": True, "base_resp": {"status_code": 0}},
            {"event": "task_finished", "base_resp": {"status_code": 0}},
        ]
    )

    def fake_connect(url, **kwargs):
        assert url == "wss://api.minimax.cn/ws/v1/t2a_v2_bidi"
        assert kwargs["additional_headers"]["Authorization"] == f"Bearer {tts_key}"
        return fake

    import psych_support_bot.infra.voice.adapter as _adapter

    monkeypatch.setattr(_adapter.websockets, "connect", fake_connect)
    assert synthesize("慢慢来") == b"chunk-a" + b"chunk-b"
    events = [frame.get("event") for frame in fake.sent]
    assert events[0] == "task_start"
    assert events[1] == "task_continue"
    assert fake.sent[1]["text"] == "慢慢来"
    assert events[-1] == "task_finish"


def test_synthesize_minimax_task_failed(monkeypatch, tts_key) -> None:
    _configure_minimax(tts_key)
    fake = _FakeWebSocket(
        [
            {"event": "connected_success", "base_resp": {"status_code": 0}},
            {"event": "task_started", "base_resp": {"status_code": 0}},
            {"event": "task_failed", "base_resp": {"status_code": 1004, "status_msg": "bad voice"}},
        ]
    )

    def fake_connect(url, **kwargs):
        return fake

    import psych_support_bot.infra.voice.adapter as _adapter

    monkeypatch.setattr(_adapter.websockets, "connect", fake_connect)
    with pytest.raises(VoiceProviderError):
        synthesize("你好")


def test_synthesize_minimax_handshake_failure(monkeypatch, tts_key) -> None:
    _configure_minimax(tts_key)
    fake = _FakeWebSocket([{"event": "connected_failed", "base_resp": {"status_code": 401}}])

    def fake_connect(url, **kwargs):
        return fake

    import psych_support_bot.infra.voice.adapter as _adapter

    monkeypatch.setattr(_adapter.websockets, "connect", fake_connect)
    with pytest.raises(VoiceProviderError):
        synthesize("你好")


def test_synthesize_minimax_ws_url_ssrf_guard(tts_key) -> None:
    """WS URL 指向内网/环回时拒绝外连（SSRF 约束对 wss 同样生效）。"""
    import websockets

    for bad in (
        "wss://127.0.0.1/ws/v1/t2a_v2_bidi",
        "wss://10.0.0.9/ws/v1/t2a_v2_bidi",
        "ws://localhost/ws/v1/t2a_v2_bidi",
    ):
        _configure_minimax(tts_key, ws_url=bad)
        with pytest.raises(VoiceProviderError):
            synthesize("你好")  # validate 在建连前抛出，不会触达 fake connect
    del websockets
