from psych_support_bot.ai.schemas.state import GraphState


def load_memory_context(state: GraphState) -> GraphState:
    summary = state.get("memory_summary") or "No long-term memory loaded yet."
    state["memory_summary"] = summary
    return state
