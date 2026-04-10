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
    "end my life",
    "jump off",
    "overdose",
]

ELEVATED_RISK_KEYWORDS = [
    "hopeless",
    "cannot go on",
    "nothing matters",
    "panic attack",
    "not sleeping",
    "no point",
    "worthless",
    "stopped sleeping",
]

CRITICAL_RISK_KEYWORDS = [
    "tonight",
    "right now",
    "already took pills",
    "have a knife",
    "have a rope",
    "goodbye forever",
]

PSYCHOSIS_KEYWORDS = [
    "people are watching me",
    "someone is controlling me",
    "hearing voices",
    "seeing things",
]

MANIA_KEYWORDS = [
    "have not slept for days",
    "feel unstoppable",
    "spending all my money",
    "i do not need sleep",
]


def classify_message_risk(text: str) -> RiskResult:
    lowered = text.lower()
    if any(keyword in lowered for keyword in HIGH_RISK_KEYWORDS) and any(
        keyword in lowered for keyword in CRITICAL_RISK_KEYWORDS
    ):
        return RiskResult(
            risk_level="critical",
            risk_types=["safety", "immediate_danger"],
            needs_crisis_mode=True,
            reason="Critical self-harm or suicide timing/method language detected.",
        )
    if any(keyword in lowered for keyword in PSYCHOSIS_KEYWORDS):
        return RiskResult(
            risk_level="high",
            risk_types=["psychosis"],
            needs_crisis_mode=True,
            reason="Possible psychosis-related language detected.",
        )
    if any(keyword in lowered for keyword in MANIA_KEYWORDS):
        return RiskResult(
            risk_level="high",
            risk_types=["mania"],
            needs_crisis_mode=True,
            reason="Possible mania-related language detected.",
        )
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
