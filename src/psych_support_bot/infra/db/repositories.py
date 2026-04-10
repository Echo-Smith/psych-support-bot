from __future__ import annotations

from datetime import date

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from psych_support_bot.ai.schemas.messages import ConversationResponse
from psych_support_bot.domain.assessments.schemas import AssessmentScore
from psych_support_bot.domain.checkins.schemas import DailyCheckin
from psych_support_bot.infra.db.models import (
    AssessmentRecord,
    CheckinRecord,
    ConversationSession,
    Message,
    RiskEvent,
    User,
    WeeklyReportRecord,
)


def ensure_user(session: Session, user_id: str) -> User:
    user = session.get(User, user_id)
    if user is None:
        user = User(id=user_id)
        session.add(user)
        session.flush()
    return user


def get_latest_summary(session: Session, user_id: str) -> str:
    stmt = (
        select(ConversationSession.summary)
        .where(ConversationSession.user_id == user_id)
        .order_by(desc(ConversationSession.created_at))
        .limit(1)
    )
    return session.execute(stmt).scalar_one_or_none() or ""


def get_recent_messages(session: Session, user_id: str, limit: int = 6) -> list[str]:
    session_ids_stmt = (
        select(ConversationSession.id)
        .where(ConversationSession.user_id == user_id)
        .order_by(desc(ConversationSession.created_at))
        .limit(3)
    )
    session_ids = list(session.execute(session_ids_stmt).scalars())
    if not session_ids:
        return []

    stmt = (
        select(Message.content)
        .where(Message.session_id.in_(session_ids))
        .order_by(desc(Message.created_at))
        .limit(limit)
    )
    return list(session.execute(stmt).scalars())


def get_user_sessions(
    session: Session, user_id: str, limit: int = 20
) -> list[ConversationSession]:
    stmt = (
        select(ConversationSession)
        .where(ConversationSession.user_id == user_id)
        .order_by(desc(ConversationSession.created_at))
        .limit(limit)
    )
    return list(session.execute(stmt).scalars())


def get_session_messages(session: Session, session_id: str) -> list[Message]:
    stmt = (
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at)
    )
    return list(session.execute(stmt).scalars())


def get_user_risk_events(
    session: Session, user_id: str, limit: int = 20
) -> list[RiskEvent]:
    stmt = (
        select(RiskEvent)
        .where(RiskEvent.user_id == user_id)
        .order_by(desc(RiskEvent.created_at))
        .limit(limit)
    )
    return list(session.execute(stmt).scalars())


def get_recent_assessment_summary(session: Session, user_id: str) -> str:
    stmt = (
        select(AssessmentRecord)
        .where(AssessmentRecord.user_id == user_id)
        .order_by(desc(AssessmentRecord.created_at))
        .limit(3)
    )
    records = list(session.execute(stmt).scalars())
    if not records:
        return ""
    return "; ".join(
        f"{record.assessment_type}:{record.score}({record.severity_band})"
        for record in records
    )


def build_memory_snapshot(session: Session, user_id: str) -> str:
    latest_summary = get_latest_summary(session, user_id)
    recent_messages = get_recent_messages(session, user_id)
    assessment_summary = get_recent_assessment_summary(session, user_id)
    recent_checkins = get_recent_checkins(session, user_id, limit=3)

    checkin_summary = ""
    if recent_checkins:
        avg_mood = sum(item.mood_score for item in recent_checkins) / len(
            recent_checkins
        )
        avg_anxiety = sum(item.anxiety_score for item in recent_checkins) / len(
            recent_checkins
        )
        checkin_summary = (
            f"recent check-ins mood={avg_mood:.1f}/10 anxiety={avg_anxiety:.1f}/10"
        )

    recent_excerpt = (
        " | ".join(reversed(recent_messages[-3:])) if recent_messages else ""
    )
    pieces = [
        piece
        for piece in [
            latest_summary,
            assessment_summary,
            checkin_summary,
            recent_excerpt,
        ]
        if piece
    ]
    return " || ".join(pieces)


def save_conversation_result(
    session: Session,
    response: ConversationResponse,
    user_message: str,
    user_id: str,
) -> None:
    ensure_user(session, user_id)
    session.merge(
        ConversationSession(
            id=response.session_id,
            user_id=user_id,
            mode=response.mode,
            risk_level=response.risk.risk_level,
            summary=response.summary,
        )
    )
    session.add(
        Message(
            session_id=response.session_id,
            role="user",
            content=user_message,
            safety_flag=response.risk.needs_crisis_mode,
        )
    )
    session.add(
        Message(
            session_id=response.session_id,
            role="assistant",
            content=response.reply.text,
            safety_flag=response.risk.needs_crisis_mode,
        )
    )
    if response.risk.risk_level in {"high", "critical"}:
        session.add(
            RiskEvent(
                user_id=user_id,
                session_id=response.session_id,
                risk_level=response.risk.risk_level,
                risk_reason=response.risk.reason,
            )
        )
    session.commit()


def save_assessment(
    session: Session, user_id: str, assessment: AssessmentScore
) -> AssessmentRecord:
    ensure_user(session, user_id)
    record = AssessmentRecord(
        user_id=user_id,
        assessment_type=assessment.assessment_type,
        score=assessment.score,
        severity_band=assessment.severity_band,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def save_checkin(
    session: Session, user_id: str, checkin: DailyCheckin
) -> CheckinRecord:
    ensure_user(session, user_id)
    record = CheckinRecord(
        user_id=user_id,
        checkin_date=date.today(),
        mood_score=checkin.mood_score,
        anxiety_score=checkin.anxiety_score,
        sleep_hours=checkin.sleep_hours,
        energy_score=checkin.energy_score,
        note=checkin.note or "",
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def get_recent_checkins(
    session: Session, user_id: str, limit: int = 7
) -> list[CheckinRecord]:
    stmt = (
        select(CheckinRecord)
        .where(CheckinRecord.user_id == user_id)
        .order_by(desc(CheckinRecord.checkin_date), desc(CheckinRecord.created_at))
        .limit(limit)
    )
    return list(session.execute(stmt).scalars())


def save_weekly_report(
    session: Session, user_id: str, summary: str
) -> WeeklyReportRecord:
    record = WeeklyReportRecord(user_id=user_id, summary=summary)
    session.add(record)
    session.commit()
    session.refresh(record)
    return record
