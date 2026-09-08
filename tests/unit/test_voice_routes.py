"""语音路由契约测试（TestClient，mock 适配器，无真实网络）。

覆盖：/status 探测、/transcribe 格式与大小校验、/speak 长度校验与
未配置 503。AUTH_ENABLED=false（游客直进）与既有集成测试同口径。
"""

import pytest
from fastapi.testclient import TestClient

from psych_support_bot.app import create_app


@pytest.fixture(autouse=True)
def _isolated_voice_env(monkeypatch):
    """隔离仓库 .env 与上一个用例残留：语音配置默认全空（未配置态）。"""
    # 空字符串覆盖而非 delenv：env var 优先级高于 .env 文件值——
    # 开发机的 .env 可能带真实语音 key（pydantic-settings 会读 env_file），
    # delenv 挡不住它，空串才能强制「未配置」基线。
    for var in (
        "VOICE_STT_PROVIDER",
        "VOICE_STT_BASE_URL",
        "VOICE_STT_API_KEY",
        "VOICE_STT_MODEL",
        "VOICE_TTS_PROVIDER",
        "VOICE_TTS_BASE_URL",
        "VOICE_TTS_API_KEY",
        "VOICE_TTS_MODEL",
        "VOICE_TTS_VOICE",
        "VOICE_TTS_WS_URL",
        "VOICE_TTS_LANGUAGE_BOOST",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
    ):
        monkeypatch.setenv(var, "")
    from psych_support_bot.infra.config.settings import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def client():
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def test_voice_status_contract(client, monkeypatch):
    monkeypatch.setenv("VOICE_STT_PROVIDER", "openai")
    monkeypatch.setenv("VOICE_STT_BASE_URL", "https://stt.example.com/v1")
    monkeypatch.setenv("VOICE_STT_API_KEY", "k" * 8)
    monkeypatch.delenv("VOICE_TTS_BASE_URL", raising=False)
    monkeypatch.delenv("VOICE_TTS_API_KEY", raising=False)
    from psych_support_bot.infra.config.settings import get_settings

    get_settings.cache_clear()
    data = client.get("/v1/voice/status").json()
    assert data == {"stt": True, "tts": False}


def test_voice_status_all_unconfigured(client, monkeypatch):
    # 空字符串覆盖（env var 优先于 .env 文件值）：get_stt_config 对空串视为未配置
    monkeypatch.setenv("VOICE_STT_PROVIDER", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    from psych_support_bot.infra.config.settings import get_settings

    get_settings.cache_clear()
    data = client.get("/v1/voice/status").json()
    assert data == {"stt": False, "tts": False}


def test_transcribe_rejects_unsupported_type(client):
    res = client.post(
        "/v1/voice/transcribe",
        files={"file": ("x.txt", b"not audio", "text/plain")},
    )
    assert res.status_code == 422


def test_transcribe_rejects_empty_and_oversize(client):
    res = client.post(
        "/v1/voice/transcribe",
        files={"file": ("a.webm", b"", "audio/webm")},
    )
    assert res.status_code == 422
    res = client.post(
        "/v1/voice/transcribe",
        files={"file": ("a.webm", b"x" * (26 * 1024 * 1024), "audio/webm")},
    )
    assert res.status_code == 413


def test_transcribe_unconfigured_returns_503(client, monkeypatch):
    monkeypatch.setenv("VOICE_STT_PROVIDER", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    from psych_support_bot.infra.config.settings import get_settings

    get_settings.cache_clear()
    res = client.post(
        "/v1/voice/transcribe",
        files={"file": ("a.webm", b"audio", "audio/webm")},
    )
    assert res.status_code == 503


def test_transcribe_success_contract(client, monkeypatch):
    monkeypatch.setenv("VOICE_STT_PROVIDER", "openai")
    monkeypatch.setenv("VOICE_STT_BASE_URL", "https://stt.example.com/v1")
    monkeypatch.setenv("VOICE_STT_API_KEY", "k" * 8)
    from psych_support_bot.infra.config.settings import get_settings

    get_settings.cache_clear()

    import httpx

    def fake_post(url, **kwargs):
        return httpx.Response(200, json={"text": "带我做接地练习"}, request=httpx.Request("POST", url))

    monkeypatch.setattr("psych_support_bot.infra.voice.adapter.httpx.post", fake_post)
    res = client.post(
        "/v1/voice/transcribe",
        files={"file": ("a.webm", b"audio", "audio/webm")},
    )
    assert res.status_code == 200
    assert res.json() == {"text": "带我做接地练习"}


def test_speak_contract_and_validation(client, monkeypatch):
    monkeypatch.delenv("VOICE_TTS_BASE_URL", raising=False)
    monkeypatch.delenv("VOICE_TTS_API_KEY", raising=False)
    from psych_support_bot.infra.config.settings import get_settings

    get_settings.cache_clear()

    # 空文本 422
    assert client.post("/v1/voice/speak", json={"text": "  "}).status_code == 422
    # 超长 422
    assert client.post("/v1/voice/speak", json={"text": "长" * 1500}).status_code == 422
    # 未配置 503
    assert client.post("/v1/voice/speak", json={"text": "你好"}).status_code == 503


def test_speak_success_returns_audio(client, monkeypatch):
    # 显式 openai 路径（adapter 测试可能残留 VOICE_TTS_PROVIDER=minimax）
    monkeypatch.setenv("VOICE_TTS_PROVIDER", "openai")
    monkeypatch.setenv("VOICE_TTS_BASE_URL", "https://tts.example.com/v1")
    monkeypatch.setenv("VOICE_TTS_API_KEY", "k" * 8)
    from psych_support_bot.infra.config.settings import get_settings

    get_settings.cache_clear()

    import httpx

    monkeypatch.setattr(
        "psych_support_bot.infra.voice.adapter.httpx.post",
        lambda url, **kw: httpx.Response(200, content=b"ID3", request=httpx.Request("POST", url)),
    )
    res = client.post("/v1/voice/speak", json={"text": "你好"})
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("audio/mpeg")


def test_tmp_media_endpoint_removed(client):
    # dots STT 已改为 base64 data URI 内联，无鉴权的 /tmp 拉取端点不复存在
    assert client.get("/v1/voice/tmp/deadbeef").status_code == 404
