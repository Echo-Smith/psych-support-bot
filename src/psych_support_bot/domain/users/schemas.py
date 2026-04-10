from pydantic import BaseModel, Field


class UserProfilePayload(BaseModel):
    user_id: str = Field(..., min_length=1)
    display_name: str = ""
    primary_concerns: list[str] = Field(default_factory=list)
    goals: list[str] = Field(default_factory=list)
    support_preferences: list[str] = Field(default_factory=list)
    risk_notes: str = ""


class UserProfileResponse(UserProfilePayload):
    updated_at: str
