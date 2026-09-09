import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from starlette.concurrency import iterate_in_threadpool

from psych_support_bot.ai.schemas.messages import (
    ConversationRequest,
    ConversationResponse,
    MessageHistoryItem,
    RiskEventItem,
    SessionHistoryItem,
)
from psych_support_bot.api.auth import request_user_id
from psych_support_bot.infra.db.repositories import (
    get_session_messages,
    get_user_risk_events,
    get_user_sessions,
)
from psych_support_bot.infra.db.session import get_db_session
from psych_support_bot.services.conversation import conversation_service

router = APIRouter(prefix="/v1/conversations", tags=["conversations"])


@router.post("/respond", response_model=ConversationResponse)
def respond(
    payload: ConversationRequest,
    request: Request,
    session: Session = Depends(get_db_session),
) -> ConversationResponse:
    payload.user_id = request_user_id(request, payload.user_id)
    return conversation_service.respond(payload, session=session)


@router.post("/respond/stream")
async def respond_stream(
    payload: ConversationRequest,
    request: Request,
    session: Session = Depends(get_db_session),
) -> StreamingResponse:
    """LLM→TTS 句子级流式（SSE）。事件帧：data {type: sentence|revise|final}。

    - sentence：LLM 生成中切出的完整句（已过逐句规则扫描），前端可即时朗读/渲染
    - revise：全文 safety_reviewer 与已朗读内容不一致，前端停读并用 text 替换气泡
    - final：完整 ConversationResponse（结构化，与 /respond 同形状），收尾用
    同步服务生成器经 threadpool 驱动；X-Accel-Buffering:no 关代理缓冲保证逐帧下发。
    """
    payload.user_id = request_user_id(request, payload.user_id)
    gen = conversation_service.respond_stream(payload, session=session)

    async def _sse():
        async for event in iterate_in_threadpool(gen):
            etype = event.get("type")
            if etype == "final":
                data = {"type": "final", "response": event["response"].model_dump(mode="json")}
            else:
                data = {k: v for k, v in event.items()}
            yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        _sse(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/history", response_model=list[SessionHistoryItem])
def get_history(
    request: Request,
    user_id: str = "",
    limit: int = 20,
    session: Session = Depends(get_db_session),
) -> list[SessionHistoryItem]:
    user_id = request_user_id(request, user_id)
    records = get_user_sessions(session, user_id=user_id, limit=limit)
    return [
        SessionHistoryItem(
            session_id=record.id,
            mode=record.mode,
            risk_level=record.risk_level,
            summary=record.summary,
            created_at=record.created_at.isoformat(),
        )
        for record in records
    ]


@router.get("/{session_id}/messages", response_model=list[MessageHistoryItem])
def get_messages(
    session_id: str,
    session: Session = Depends(get_db_session),
) -> list[MessageHistoryItem]:
    records = get_session_messages(session, session_id=session_id)
    return [
        MessageHistoryItem(
            role=record.role,
            content=record.content,
            safety_flag=record.safety_flag,
            created_at=record.created_at.isoformat(),
        )
        for record in records
    ]


@router.get("/risk-events", response_model=list[RiskEventItem])
def get_risk_events(
    request: Request,
    user_id: str = "",
    limit: int = 20,
    session: Session = Depends(get_db_session),
) -> list[RiskEventItem]:
    user_id = request_user_id(request, user_id)
    records = get_user_risk_events(session, user_id=user_id, limit=limit)
    return [
        RiskEventItem(
            session_id=record.session_id,
            risk_level=record.risk_level,
            risk_reason=record.risk_reason,
            created_at=record.created_at.isoformat(),
        )
        for record in records
    ]
