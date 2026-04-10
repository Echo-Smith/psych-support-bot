from psych_support_bot.ai.schemas.state import GraphState
from psych_support_bot.ai.tools.knowledge_base import get_knowledge_context


def load_knowledge_context(state: GraphState) -> GraphState:
    state["knowledge_context"] = get_knowledge_context(
        mode=state["mode"],
        risk_level=state["risk_result"].risk_level,
    )
    return state
