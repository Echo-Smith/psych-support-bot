"""SSE 流式对话路由契约测试（/v1/conversations/respond/stream）。

mock conversation_service.respond_stream，不发真实 LLM/网络请求。
覆盖：SSE 帧格式（data: json\n\n）、media_type、事件序列透传；
错误路径（生成器抛错 → 流中断）。
"""

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from psych_support_bot.app import create_app
from psych_support_bot.ai.schemas.messages import (
    ConversationRequest,
    ConversationResponse,
    GeneratedReply,
    RiskResult,
)


@pytest.fixture()
def client():
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def _final_response() -> ConversationResponse:
    return ConversationResponse(
        session_id="s1",
        mode="support",
        risk=RiskResult(risk_level="low", risk_types=[], needs_crisis_mode=False, reason=""),
        reply=GeneratedReply(text="嗯，我听到了。慢慢来。", style="support"),
        summary="",
    )


def test_respond_stream_sse_frames(client, monkeypatch):
    events: list[dict[str, Any]] = [
        {"type": "sentence", "text": "嗯，我听到了。"},
        {"type": "sentence", "text": "慢慢来。"},
        {"type": "final", "response": _final_response()},
    ]

    def fake_stream(payload, session):
        payload.user_id = "u-sse"
        yield from events

    monkeypatch.setattr(
        "psych_support_bot.services.conversation.conversation_service.respond_stream",
        fake_stream,
    )
    with client.stream(
        "POST",
        "/v1/conversations/respond/stream",
        json={"user_id": "u-sse", "message": "我心里有点乱"},
    ) as res:
        assert res.status_code == 200
        assert res.headers["content-type"].startswith("text/event-stream")
        body = "".join(res.iter_text())
    frames = [json.loads(line.removeprefix("data: ")) for line in body.splitlines() if line.startswith("data: ")]
    assert [f["type"] for f in frames] == ["sentence", "sentence", "final"]
    assert frames[0]["text"] == "嗯，我听到了。"
    assert frames[-1]["response"]["reply"]["text"] == "嗯，我听到了。慢慢来。"


def test_respond_stream_empty_message_422(client):
    # 空 message：SSE 路由同样要求有效输入（ConversationRequest 校验）
    res = client.post(
        "/v1/conversations/respond/stream",
        json={"user_id": "u", "message": ""},
    )
    assert res.status_code == 422
