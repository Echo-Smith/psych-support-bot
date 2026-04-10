from psych_support_bot.ai.safety.rules import classify_message_risk


def test_critical_risk_message_detected() -> None:
    result = classify_message_risk("I want to kill myself tonight and I have a knife")
    assert result.risk_level == "critical"
    assert result.needs_crisis_mode is True


def test_psychosis_like_message_detected() -> None:
    result = classify_message_risk("I am hearing voices and people are watching me")
    assert result.risk_level == "high"
    assert result.needs_crisis_mode is True
