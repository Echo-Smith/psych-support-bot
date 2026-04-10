from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from psych_support_bot.domain.checkins.schemas import DailyCheckin
from psych_support_bot.infra.db.repositories import save_checkin
from psych_support_bot.infra.db.session import get_db_session

router = APIRouter(prefix="/v1/checkins", tags=["checkins"])


@router.post("", response_model=DailyCheckin)
def create_checkin(
    payload: DailyCheckin,
    user_id: str,
    session: Session = Depends(get_db_session),
) -> DailyCheckin:
    save_checkin(session, user_id, payload)
    return payload
