from pydantic import BaseModel, Field


class DailyCheckin(BaseModel):
    mood_score: int = Field(..., ge=0, le=10)
    anxiety_score: int = Field(..., ge=0, le=10)
    sleep_hours: float = Field(..., ge=0, le=24)
    energy_score: int = Field(..., ge=0, le=10)
    note: str | None = None
