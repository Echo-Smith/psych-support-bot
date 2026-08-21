from psych_support_bot.infra.db.models import CheckinRecord


def build_weekly_summary(
    checkins: list[CheckinRecord],
    *,
    trend_status: str = "",
) -> str:
    """Build a human-readable weekly summary from check-in records.

    B3.6: When trend_status indicates "needs_attention" or "monitor",
    the summary includes a visible alert flag so the user (and clinician)
    knows to pay closer attention.
    """
    if not checkins:
        return "No check-in data is available yet for this week."

    avg_mood = sum(item.mood_score for item in checkins) / len(checkins)
    avg_anxiety = sum(item.anxiety_score for item in checkins) / len(checkins)
    avg_sleep = sum(item.sleep_hours for item in checkins) / len(checkins)
    avg_energy = sum(item.energy_score for item in checkins) / len(checkins)

    summary = (
        "Weekly summary: "
        f"average mood {avg_mood:.1f}/10, average anxiety {avg_anxiety:.1f}/10, "
        f"average sleep {avg_sleep:.1f} hours, average energy {avg_energy:.1f}/10."
    )

    # B3.6: Append attention flag based on trend analysis
    if trend_status == "needs_attention":
        summary += " ⚠️ Needs attention: multiple indicators are worsening."
    elif trend_status == "monitor":
        summary += " 📊 Monitor: mood or anxiety trend is declining."

    return summary
