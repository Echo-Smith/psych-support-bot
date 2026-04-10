from typing import Literal

from pydantic import BaseModel, Field

ConversationMode = Literal[
    "support", "assessment", "intervention", "planning", "crisis"
]
RiskLevel = Literal["low", "elevated", "high", "critical"]


class ConversationRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    session_id: str | None = None
    memory_summary: str | None = None


class RiskResult(BaseModel):
    risk_level: RiskLevel
    risk_types: list[str] = Field(default_factory=list)
    needs_crisis_mode: bool = False
    reason: str


class GeneratedReply(BaseModel):
    text: str
    style: ConversationMode
    includes_action_step: bool = True


class ConversationResponse(BaseModel):
    session_id: str
    mode: ConversationMode
    risk: RiskResult
    reply: GeneratedReply
    summary: str
