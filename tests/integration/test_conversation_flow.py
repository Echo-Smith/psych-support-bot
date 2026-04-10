from psych_support_bot.ai.schemas.messages import ConversationRequest
from psych_support_bot.services.conversation import conversation_service


def test_support_flow_returns_response() -> None:
    result = conversation_service.respond(
        ConversationRequest(
            user_id="test-user", message="I feel stressed and want support"
        )
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
    result = conversation_service.respond(
        ConversationRequest(
            user_id="test-user", message="I want to die and hurt myself"
        )
    )

    assert result.mode == "crisis"
    assert result.risk.needs_crisis_mode is True
