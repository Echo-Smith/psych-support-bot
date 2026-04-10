from fastapi import APIRouter

from psych_support_bot.ai.schemas.messages import (
    ConversationRequest,
    ConversationResponse,
)
from psych_support_bot.services.conversation import conversation_service

router = APIRouter(prefix="/v1/conversations", tags=["conversations"])


@router.post("/respond", response_model=ConversationResponse)
def respond(payload: ConversationRequest) -> ConversationResponse:
    return conversation_service.respond(payload)
