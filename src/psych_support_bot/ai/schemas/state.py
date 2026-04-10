from typing import TypedDict

from psych_support_bot.ai.schemas.messages import (
    ConversationMode,
    GeneratedReply,
    RiskResult,
)


class GraphState(TypedDict):
    user_id: str
    session_id: str
    user_message: str
    memory_summary: str
    knowledge_context: str
    mode: ConversationMode
    risk_result: RiskResult
    generated_reply: GeneratedReply
    session_summary: str
