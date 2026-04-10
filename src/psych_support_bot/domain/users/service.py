from psych_support_bot.domain.users.schemas import UserProfilePayload


def build_profile_summary(payload: UserProfilePayload) -> str:
    parts = []
    if payload.primary_concerns:
        parts.append("concerns=" + ", ".join(payload.primary_concerns))
    if payload.goals:
        parts.append("goals=" + ", ".join(payload.goals))
    if payload.support_preferences:
        parts.append("preferences=" + ", ".join(payload.support_preferences))
    if payload.risk_notes:
        parts.append("risk_notes=" + payload.risk_notes)
    return " || ".join(parts)
