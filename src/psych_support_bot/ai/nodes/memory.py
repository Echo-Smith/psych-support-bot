from psych_support_bot.ai.schemas.state import GraphState


def load_memory_context(state: GraphState) -> GraphState:
    current = state.get("memory_summary") or "No long-term memory loaded yet."
    session = state.get("session_summary")

    if session:
        if current and current != "No long-term memory loaded yet.":
            state["memory_summary"] = f"{current} | Previous turn: {session}"
        else:
            state["memory_summary"] = session
    else:
        state["memory_summary"] = current

    return state
