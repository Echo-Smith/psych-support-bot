import pytest
from fastapi import HTTPException

from psych_support_bot.domain.assessments.schemas import AssessmentAnswerSet
from psych_support_bot.domain.assessments.service import (
    build_assessment_result,
    detect_questionnaire_request,
    questionnaire_guide,
    score_from_answers,
)


def test_questionnaire_guide_exposes_instructions() -> None:
    guide = questionnaire_guide("gad7")

    assert guide.code == "gad7"
    assert guide.instructions
    assert len(guide.items) == 7


def test_score_from_answers_validates_length() -> None:
    with pytest.raises(HTTPException):
        score_from_answers("phq9", AssessmentAnswerSet(answers=[0, 1]))


def test_score_from_answers_validates_range() -> None:
    with pytest.raises(HTTPException):
        score_from_answers("gad7", AssessmentAnswerSet(answers=[0, 1, 2, 3, 4, 0, 1]))


def test_assessment_result_interprets_phq9_safety_signal() -> None:
    result = build_assessment_result(
        "phq9",
        answers=AssessmentAnswerSet(answers=[0, 1, 1, 1, 0, 0, 1, 0, 1]),
    )

    assert result.score == 5
    assert result.severity_band == "mild"
    assert result.interpretation.needs_safety_followup is True


def test_assessment_result_supports_isi_boundaries() -> None:
    result = build_assessment_result("isi", score=15, language="en")

    assert result.severity_band == "moderate"
    assert "sleep" in result.interpretation.functional_impact.lower()


def test_detect_questionnaire_request_supports_natural_chinese_phrases() -> None:
    assert detect_questionnaire_request("我想测一下抑郁程度") == "phq9"
    assert detect_questionnaire_request("我想做焦虑量表") == "gad7"
    assert detect_questionnaire_request("我想做失眠量表") == "isi"


def test_questionnaire_guide_is_localized_for_chinese_ui() -> None:
    guide = questionnaire_guide("phq9")

    assert "抑郁" in guide.title
    assert "过去两周" in guide.timeframe
    assert guide.options[0].label == "完全没有"
    assert any("做事时提不起兴趣" in item for item in guide.items)
