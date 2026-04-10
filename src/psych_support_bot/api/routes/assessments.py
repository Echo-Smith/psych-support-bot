from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from psych_support_bot.domain.assessments.schemas import AssessmentScore, AssessmentType
from psych_support_bot.domain.assessments.service import build_assessment_score
from psych_support_bot.infra.db.repositories import save_assessment
from psych_support_bot.infra.db.session import get_db_session

router = APIRouter(prefix="/v1/assessments", tags=["assessments"])


class AssessmentRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    assessment_type: AssessmentType
    score: int = Field(..., ge=0)


@router.post("", response_model=AssessmentScore)
def create_assessment(
    payload: AssessmentRequest,
    session: Session = Depends(get_db_session),
) -> AssessmentScore:
    assessment = build_assessment_score(payload.assessment_type, payload.score)
    save_assessment(session, payload.user_id, assessment)
    return assessment
