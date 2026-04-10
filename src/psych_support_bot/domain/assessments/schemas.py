from typing import Literal

from pydantic import BaseModel, Field

AssessmentType = Literal["phq9", "gad7", "isi"]


class AssessmentScore(BaseModel):
    assessment_type: AssessmentType
    score: int = Field(..., ge=0)
    severity_band: str
