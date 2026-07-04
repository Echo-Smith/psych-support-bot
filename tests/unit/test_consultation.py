from psych_support_bot.ai.consultation import (
    consultation_agent_labels,
    should_trigger_multidisciplinary_consultation,
)


def test_consultation_agent_labels_exposes_all_agents() -> None:
    labels = consultation_agent_labels()

    assert labels == [
        "CBT Agent",
        "Psychodynamic Agent",
        "Humanistic Agent",
        "ACT Agent",
        "DBT Agent",
    ]


def test_assessment_mode_requires_consultation() -> None:
    assert should_trigger_multidisciplinary_consultation(
        user_message="我想做一个焦虑测评",
        mode="assessment",
        risk_level="low",
    )


def test_support_message_with_treatment_keywords_requires_consultation() -> None:
    assert should_trigger_multidisciplinary_consultation(
        user_message="请从不同流派会诊一下我的治疗方向",
        mode="support",
        risk_level="low",
    )


def test_high_risk_message_skips_consultation() -> None:
    assert not should_trigger_multidisciplinary_consultation(
        user_message="I want treatment because I might hurt myself tonight",
        mode="intervention",
        risk_level="critical",
    )
