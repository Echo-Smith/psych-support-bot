from psych_support_bot.ai.schemas.state import GraphState


def write_summary(state: GraphState) -> GraphState:
    state["session_summary"] = (
        f"Mode={state['mode']}; risk={state['risk_result'].risk_level}; "
        f"message={state['user_message'][:120]}"
    )
    return state
