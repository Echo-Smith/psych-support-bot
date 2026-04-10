from uuid import uuid4
from typing import Any, cast

from sqlalchemy.orm import Session

from psych_support_bot.ai.graphs.conversation import conversation_graph
from psych_support_bot.ai.schemas.messages import (
    ConversationRequest,
    ConversationResponse,
    GeneratedReply,
    RiskResult,
)
from psych_support_bot.ai.schemas.state import GraphState
from psych_support_bot.infra.db.repositories import (
    build_memory_snapshot,
    save_conversation_result,
)
from psych_support_bot.infra.telemetry.tracing import timed_call


class ConversationService:
    def respond(
        self,
        payload: ConversationRequest,
        session: Session,
    ) -> ConversationResponse:
        session_id = payload.session_id or str(uuid4())
        memory_summary = payload.memory_summary or build_memory_snapshot(
            session, payload.user_id
        )
        state: GraphState = {
            "user_id": payload.user_id,
            "session_id": session_id,
            "user_message": payload.message,
            "memory_summary": memory_summary,
            "knowledge_context": "",
            "mode": "support",
            "risk_result": RiskResult(
                risk_level="low",
                risk_types=[],
                needs_crisis_mode=False,
                reason="",
            ),
            "generated_reply": GeneratedReply(
                text="",
                style="support",
                includes_action_step=True,
            ),
            "session_summary": "",
        }
        result, _trace = timed_call(
            "conversation_graph.invoke",
            lambda: cast(GraphState, conversation_graph.invoke(cast(Any, state))),
        )
        response = ConversationResponse(
            session_id=session_id,
            mode=result["mode"],
            risk=result["risk_result"],
            reply=result["generated_reply"],
            summary=result["session_summary"],
        )
        save_conversation_result(
            session=session,
            response=response,
            user_message=payload.message,
            user_id=payload.user_id,
        )
        return response


conversation_service = ConversationService()
