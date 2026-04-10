from psych_support_bot.infra.db.models import CheckinRecord


def build_weekly_summary(checkins: list[CheckinRecord]) -> str:
    if not checkins:
        return "No check-in data is available yet for this week."

    avg_mood = sum(item.mood_score for item in checkins) / len(checkins)
    avg_anxiety = sum(item.anxiety_score for item in checkins) / len(checkins)
    avg_sleep = sum(item.sleep_hours for item in checkins) / len(checkins)
    avg_energy = sum(item.energy_score for item in checkins) / len(checkins)
    return (
        "Weekly summary: "
        f"average mood {avg_mood:.1f}/10, average anxiety {avg_anxiety:.1f}/10, "
        f"average sleep {avg_sleep:.1f} hours, average energy {avg_energy:.1f}/10."
    )
