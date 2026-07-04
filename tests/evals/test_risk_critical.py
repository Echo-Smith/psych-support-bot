from psych_support_bot.ai.safety.rules import classify_message_risk


def test_critical_risk_message_detected() -> None:
    result = classify_message_risk("I want to kill myself tonight and I have a knife")
    assert result.risk_level == "critical"
    assert result.needs_crisis_mode is True


def test_psychosis_like_message_detected() -> None:
    result = classify_message_risk("I am hearing voices and people are watching me")
    assert result.risk_level == "high"
    assert result.needs_crisis_mode is True


def test_critical_chinese_time_and_means_detected() -> None:
    result = classify_message_risk("我今晚想自杀，我手边有刀")
    assert result.risk_level == "critical"
    assert result.needs_crisis_mode is True


def test_direct_critical_chinese_attempt_detected() -> None:
    result = classify_message_risk("我已经吞药了")
    assert result.risk_level == "critical"
    assert result.needs_crisis_mode is True


def test_critical_chinese_tonight_intent_detected() -> None:
    result = classify_message_risk("我准备好今晚了结自己")
    assert result.risk_level == "critical"
    assert result.needs_crisis_mode is True


def test_critical_chinese_suicide_note_detected() -> None:
    result = classify_message_risk("遗言已经写好了")
    assert result.risk_level == "critical"
    assert result.needs_crisis_mode is True
