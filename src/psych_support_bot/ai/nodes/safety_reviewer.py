from psych_support_bot.ai.schemas.state import GraphState


def review_response(state: GraphState) -> GraphState:
    if state["risk_result"].needs_crisis_mode:
        state["generated_reply"].includes_action_step = True
    return state
