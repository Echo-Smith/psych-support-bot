"""Tests for B3.5: daily_steps in plan templates and B3.6: weekly summary alert."""

from datetime import date, timedelta

from psych_support_bot.domain.plans.templates import PLAN_TEMPLATES
from psych_support_bot.domain.reports.service import build_weekly_summary
from psych_support_bot.infra.db.models import CheckinRecord


# ---------------------------------------------------------------------------
# B3.5: daily_steps
# ---------------------------------------------------------------------------


def test_all_templates_have_daily_steps():
    """Every plan template must include a non-empty daily_steps list."""
    for plan_id, template in PLAN_TEMPLATES.items():
        assert "daily_steps" in template, f"{plan_id} missing daily_steps"
        steps = template["daily_steps"]
        assert isinstance(steps, list) and len(steps) > 0, f"{plan_id} has empty daily_steps"


def test_daily_steps_count_matches_days():
    """daily_steps length should match the template's declared days."""
    for plan_id, template in PLAN_TEMPLATES.items():
        expected = template["days"]
        actual = len(template["daily_steps"])
        assert actual == expected, (
            f"{plan_id}: days={expected} but daily_steps has {actual} entries"
        )


def test_daily_steps_are_strings():
    """Each step should be a non-empty string."""
    for plan_id, template in PLAN_TEMPLATES.items():
        for i, step in enumerate(template["daily_steps"]):
            assert isinstance(step, str) and len(step) > 5, (
                f"{plan_id} step[{i}] is not a valid string: {step!r}"
            )


# ---------------------------------------------------------------------------
# B3.6: weekly summary with trend alert
# ---------------------------------------------------------------------------


def _make_checkin(
    *,
    user_id: str = "test-user",
    days_ago: int = 0,
    mood: int = 6,
    anxiety: int = 4,
    sleep: float = 7.0,
    energy: int = 6,
) -> CheckinRecord:
    """Create a CheckinRecord for testing without DB."""
    return CheckinRecord(
        user_id=user_id,
        checkin_date=date.today() - timedelta(days=days_ago),  # noqa: DTZ011
        mood_score=mood,
        anxiety_score=anxiety,
        sleep_hours=sleep,
        energy_score=energy,
    )


def test_summary_without_trend_status():
    """When no trend_status is provided, summary should NOT contain alert flags."""
    checkins = [_make_checkin(days_ago=i) for i in range(7)]
    summary = build_weekly_summary(checkins)
    assert "Weekly summary:" in summary
    assert "⚠️" not in summary
    assert "📊" not in summary


def test_summary_needs_attention():
    """needs_attention trend should append the warning flag."""
    checkins = [_make_checkin(days_ago=i) for i in range(7)]
    summary = build_weekly_summary(checkins, trend_status="needs_attention")
    assert "⚠️ Needs attention" in summary


def test_summary_monitor():
    """monitor trend should append the monitor flag."""
    checkins = [_make_checkin(days_ago=i) for i in range(7)]
    summary = build_weekly_summary(checkins, trend_status="monitor")
    assert "📊 Monitor" in summary


def test_summary_stable_no_flag():
    """stable trend should NOT append any flag."""
    checkins = [_make_checkin(days_ago=i) for i in range(7)]
    summary = build_weekly_summary(checkins, trend_status="stable")
    assert "⚠️" not in summary
    assert "📊" not in summary


def test_summary_empty_checkins():
    """Empty check-in list should return the no-data message."""
    summary = build_weekly_summary([], trend_status="needs_attention")
    assert "No check-in data" in summary
