from psych_support_bot.domain.assessments.service import (
    build_questionnaire_session_view,
)


def test_questionnaire_session_view_exposes_next_item() -> None:
    view = build_questionnaire_session_view(
        session_id="session-1",
        user_id="user-1",
        assessment_type="phq9",
        answers=[0, 1],
        status="in_progress",
    )

    assert view.current_index == 2
    assert view.total_items == 9
    assert view.next_item is not None
    assert view.next_item.index == 2


def test_completed_questionnaire_session_view_hides_next_item() -> None:
    view = build_questionnaire_session_view(
        session_id="session-1",
        user_id="user-1",
        assessment_type="gad7",
        answers=[1, 1, 1, 1, 1, 1, 1],
        status="completed",
    )

    assert view.current_index == 7
    assert view.next_item is None
