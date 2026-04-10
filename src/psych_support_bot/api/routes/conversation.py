from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from psych_support_bot.ai.schemas.messages import (
    ConversationRequest,
    ConversationResponse,
)
from psych_support_bot.services.conversation import conversation_service
from psych_support_bot.infra.db.session import get_db_session

router = APIRouter(prefix="/v1/conversations", tags=["conversations"])


@router.post("/respond", response_model=ConversationResponse)
def respond(
    payload: ConversationRequest,
    session: Session = Depends(get_db_session),
) -> ConversationResponse:
    return conversation_service.respond(payload, session=session)
