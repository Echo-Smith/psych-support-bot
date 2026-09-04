from psych_support_bot.ai.prompts.templates import (
    build_consultation_synthesis_prompt,
    build_output_prompt,
    build_process_prompt,
)


def test_output_prompt_support_mode_allows_flexible_shape() -> None:
    """批次3 共情化：support 形态弹性化（1-3 条），保留无标签与单问号契约。"""
    prompt = build_output_prompt(
        mode="support",
        risk_level="low",
        user_message="我最近状态很乱",
    )

    assert "ONE to THREE short conversational messages" in prompt
    assert "No labels, headings, numbering, or meta words like '回应', '工作性假设', '下一问'" in prompt
    assert "At most ONE question" in prompt
    assert "must not appear in consecutive replies" in prompt


def test_output_prompt_non_support_keeps_three_part_skeleton() -> None:
    """assessment/planning/intervention 保留三段式（采集与教学需要结构）。"""
    prompt = build_output_prompt(
        mode="assessment",
        risk_level="low",
        user_message="我想做个评估",
    )

    assert "EXACTLY three short conversational messages" in prompt


def test_process_prompt_mentions_structure_and_gentle_challenge() -> None:
    prompt = build_process_prompt(
        interview_stage="hypothesis_testing",
        question_strategy="gentle_challenge",
        challenge_allowed=True,
        loop_hint="Test the absolute claim against exceptions.",
        expected_language="en",
    )

    assert "three short unlabeled conversational messages" in prompt
    assert "Gentle challenge is allowed" in prompt
    assert "Do not stack multiple questions" in prompt


def test_consultation_synthesis_prompt_requires_unlabeled_messages() -> None:
    prompt = build_consultation_synthesis_prompt(
        mode="support",
        risk_level="low",
        memory_summary="",
        knowledge_context="",
        consultation_framework="- Agent A",
        consultation_opinions="[Agent A]\n观察: x\n形成: y\n下一步: z",
        user_message="我总觉得自己不行",
        interview_stage="hypothesis_testing",
        question_strategy="gentle_challenge",
        challenge_allowed=True,
        loop_hint="Test the user's conclusion against evidence and exceptions.",
    )

    assert "three short unlabeled conversational messages" in prompt
    assert "must use the labels" not in prompt


def test_output_prompt_quiet_mode_suppresses_questions() -> None:
    prompt = build_output_prompt(
        mode="support",
        risk_level="low",
        user_message="我只想安静待一会儿",
        no_question_mode=True,
    )

    assert "QUIET MODE OVERRIDE" in prompt
    assert "Omit every question this turn" in prompt
    # 默认三段式说明被静音分支替换
    assert "EXACTLY three short conversational messages" not in prompt
    assert "Omit Message 3" not in prompt


def test_process_prompt_quiet_mode_forbids_challenge() -> None:
    prompt = build_process_prompt(
        interview_stage="hypothesis_testing",
        question_strategy="gentle_challenge",
        challenge_allowed=True,
        loop_hint="Test the absolute claim against exceptions.",
        expected_language="en",
        no_question_mode=True,
    )

    assert "do not probe" in prompt
    assert "Gentle challenge is allowed" not in prompt
