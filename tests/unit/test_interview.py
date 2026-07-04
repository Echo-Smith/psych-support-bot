from psych_support_bot.ai.interview import determine_interview_process


def test_open_exploration_message_uses_open_questioning() -> None:
    result = determine_interview_process(
        user_message="我现在很乱，不知道怎么解释自己的状态",
        mode="support",
        risk_level="low",
    )

    assert result["interview_stage"] == "exploration"
    assert result["question_strategy"] == "open"
    assert result["challenge_allowed"] is False


def test_pattern_message_uses_looping_questions() -> None:
    result = determine_interview_process(
        user_message="我每次开会前都会反复担心自己说错话",
        mode="support",
        risk_level="low",
    )

    assert result["interview_stage"] == "pattern_analysis"
    assert result["question_strategy"] == "looping"


def test_weak_pattern_without_conflict_stays_in_exploration() -> None:
    result = determine_interview_process(
        user_message="我最近一直觉得很累，下班后只想发呆",
        mode="support",
        risk_level="low",
    )

    assert result["interview_stage"] == "exploration"
    assert result["question_strategy"] == "open"
    assert result["challenge_allowed"] is False


def test_contradiction_message_allows_gentle_challenge() -> None:
    result = determine_interview_process(
        user_message="我明明知道这样没用，但是又总是停不下来",
        mode="support",
        risk_level="low",
    )

    assert result["interview_stage"] == "hypothesis_testing"
    assert result["question_strategy"] == "looping"
    assert result["challenge_allowed"] is True


def test_absolutist_message_uses_gentle_challenge() -> None:
    result = determine_interview_process(
        user_message="我永远都处理不好关系，根本不会有人理解我",
        mode="support",
        risk_level="low",
    )

    assert result["interview_stage"] == "hypothesis_testing"
    assert result["question_strategy"] == "gentle_challenge"
    assert result["challenge_allowed"] is True


def test_minimization_message_triggers_resistance_exploration() -> None:
    result = determine_interview_process(
        user_message="其实也没事，不严重，就是最近睡不着而已",
        mode="support",
        risk_level="low",
    )

    assert result["interview_stage"] == "resistance_exploration"
    assert result["question_strategy"] == "gentle_challenge"
    assert result["challenge_allowed"] is True


def test_exhaustion_plus_nonrelational_withdrawal_does_not_overchallenge() -> None:
    result = determine_interview_process(
        user_message="我最近总觉得很累，下班以后一句话都不想说",
        mode="support",
        risk_level="low",
    )

    assert result["interview_stage"] == "exploration"
    assert result["question_strategy"] == "open"
    assert result["challenge_allowed"] is False


def test_relational_withdrawal_can_still_trigger_gentle_challenge() -> None:
    result = determine_interview_process(
        user_message="每次他一问我怎么了，我就更不想说",
        mode="support",
        risk_level="low",
    )

    assert result["interview_stage"] == "resistance_exploration"
    assert result["question_strategy"] == "gentle_challenge"
    assert result["challenge_allowed"] is True


def test_pattern_plus_contradiction_prefers_looping_hypothesis_testing() -> None:
    result = determine_interview_process(
        user_message="我每次都说要早点睡，但是又总是停不下来刷手机",
        mode="support",
        risk_level="low",
    )

    assert result["interview_stage"] == "hypothesis_testing"
    assert result["question_strategy"] == "looping"
    assert result["challenge_allowed"] is True


def test_assessment_mode_prefers_structured_clarification() -> None:
    result = determine_interview_process(
        user_message="我想做焦虑测评",
        mode="assessment",
        risk_level="low",
    )

    assert result["interview_stage"] == "structured_assessment"
    assert result["question_strategy"] == "clarifying"


def test_critical_risk_forces_safety_process() -> None:
    result = determine_interview_process(
        user_message="I want to die tonight",
        mode="crisis",
        risk_level="critical",
    )

    assert result["interview_stage"] == "safety_stabilization"
    assert result["question_strategy"] == "directive"
    assert result["challenge_allowed"] is False
