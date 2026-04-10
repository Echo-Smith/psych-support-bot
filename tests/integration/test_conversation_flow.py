from psych_support_bot.ai.schemas.messages import ConversationRequest
from psych_support_bot.infra.db.init_db import init_db
from psych_support_bot.infra.db.session import SessionLocal
from psych_support_bot.services.conversation import conversation_service


init_db()


def test_support_flow_returns_response() -> None:
    with SessionLocal() as session:
        result = conversation_service.respond(
            ConversationRequest(
                user_id="test-user", message="I feel stressed and want support"
            ),
            session=session,
        )

    assert result.mode in {
        "support",
        "assessment",
        "intervention",
        "planning",
        "crisis",
    }
    assert result.reply.text
    assert result.risk.risk_level in {"low", "elevated", "high", "critical"}


def test_crisis_flow_triggers_high_risk() -> None:
    with SessionLocal() as session:
        result = conversation_service.respond(
            ConversationRequest(
                user_id="test-user", message="I want to die and hurt myself"
            ),
            session=session,
        )

    assert result.mode == "crisis"
    assert result.risk.needs_crisis_mode is True
