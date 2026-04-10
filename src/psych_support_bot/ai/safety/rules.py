from psych_support_bot.ai.schemas.messages import RiskResult

HIGH_RISK_KEYWORDS = [
    "suicide",
    "kill myself",
    "self-harm",
    "hurt myself",
    "hurt someone",
    "hallucination",
    "voices",
    "want to die",
]

ELEVATED_RISK_KEYWORDS = [
    "hopeless",
    "cannot go on",
    "nothing matters",
    "panic attack",
    "not sleeping",
]


def classify_message_risk(text: str) -> RiskResult:
    lowered = text.lower()
    if any(keyword in lowered for keyword in HIGH_RISK_KEYWORDS):
        return RiskResult(
            risk_level="high",
            risk_types=["safety"],
            needs_crisis_mode=True,
            reason="High-risk safety language detected.",
        )
    if any(keyword in lowered for keyword in ELEVATED_RISK_KEYWORDS):
        return RiskResult(
            risk_level="elevated",
            risk_types=["distress"],
            needs_crisis_mode=False,
            reason="Elevated distress language detected.",
        )
    return RiskResult(
        risk_level="low",
        risk_types=[],
        needs_crisis_mode=False,
        reason="No obvious high-risk language detected.",
    )
