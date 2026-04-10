from uuid import uuid4

from psych_support_bot.ai.graphs.conversation import conversation_graph
from psych_support_bot.ai.schemas.messages import (
    ConversationRequest,
    ConversationResponse,
)


class ConversationService:
    def respond(self, payload: ConversationRequest) -> ConversationResponse:
        session_id = payload.session_id or str(uuid4())
        state = {
            "user_id": payload.user_id,
            "session_id": session_id,
            "user_message": payload.message,
            "memory_summary": payload.memory_summary or "",
        }
        result = conversation_graph.invoke(state)
        return ConversationResponse(
            session_id=session_id,
            mode=result["mode"],
            risk=result["risk_result"],
            reply=result["generated_reply"],
            summary=result["session_summary"],
        )


conversation_service = ConversationService()
