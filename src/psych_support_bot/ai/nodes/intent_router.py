from psych_support_bot.ai.routers.intent import detect_mode
from psych_support_bot.ai.schemas.state import GraphState


def route_intent(state: GraphState) -> GraphState:
    if state.get("mode") == "crisis":
        return state
    state["mode"] = detect_mode(state["user_message"])
    return state
