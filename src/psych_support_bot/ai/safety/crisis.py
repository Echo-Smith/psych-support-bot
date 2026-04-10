from psych_support_bot.ai.schemas.messages import RiskResult


def build_crisis_reply(risk: RiskResult) -> str:
    if risk.risk_level == "critical":
        return (
            "I am very concerned that you may be in immediate danger. Please contact local emergency services, "
            "go to the nearest hospital now, or call a trusted person to stay with you immediately."
        )
    return (
        "I am concerned about your safety. If there is any immediate danger, contact a trusted person, "
        "local emergency services, or go to the nearest hospital now. If you can, do not stay alone."
    )
