from psych_support_bot.domain.assessments.service import (
    build_progress_prefix,
    cooldown_days_for,
    detect_pause_request,
    detect_retest_override,
    format_trend_line,
)


def test_detect_pause_request_matches_zh_and_en() -> None:
    assert detect_pause_request("暂停")
    assert detect_pause_request("先停一下")
    assert detect_pause_request("pause")
    assert not detect_pause_request("3")
    # 算了/不想做了 are skip words, not pause words.
    assert not detect_pause_request("算了")


def test_detect_retest_override() -> None:
    assert detect_retest_override("我知道,我想重新测一遍")
    assert detect_retest_override("再测一次")
    assert not detect_retest_override("我想做抑郁量表")


def test_cooldown_windows_per_scale() -> None:
    assert cooldown_days_for("phq9") == 7
    assert cooldown_days_for("gad7") == 7
    assert cooldown_days_for("isi") == 14


def test_progress_prefix_bilingual() -> None:
    zh = build_progress_prefix("PHQ-9 抑郁筛查量表", 3, 9, "zh")
    assert "第 3/9 题" in zh
    en = build_progress_prefix("PHQ-9", 1, 9, "en")
    assert "[PHQ-9 · Question 1/9]" in en


def test_format_trend_line_directions() -> None:
    down = format_trend_line("zh", prev_score=15, days_since=7, new_score=11)
    assert "低了 4 分" in down
    up = format_trend_line("zh", prev_score=5, days_since=0, new_score=8)
    assert "高了 3 分" in up
    flat = format_trend_line("zh", prev_score=10, days_since=7, new_score=10)
    assert "基本持平" in flat
    en = format_trend_line("en", prev_score=10, days_since=6, new_score=6)
    assert "4 points lower" in en
