from psych_support_bot.ai.schemas.messages import ConversationMode


def detect_mode(text: str) -> ConversationMode:
    lowered = text.lower()
    if any(keyword in lowered for keyword in ["plan", "next step", "schedule"]):
        return "planning"
    if any(keyword in lowered for keyword in ["exercise", "breath", "cbt", "act"]):
        return "intervention"
    if any(keyword in lowered for keyword in ["assessment", "screen", "score", "test"]):
        return "assessment"
    return "support"
