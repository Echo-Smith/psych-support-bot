from psych_support_bot.ai.safety.rules import classify_message_risk


def test_high_risk_message_detected() -> None:
    result = classify_message_risk("I want to kill myself tonight")
    assert result.risk_level == "high"
    assert result.needs_crisis_mode is True


def test_elevated_message_detected() -> None:
    result = classify_message_risk("I feel hopeless and cannot go on")
    assert result.risk_level == "elevated"
    assert result.needs_crisis_mode is False
