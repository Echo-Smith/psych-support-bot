from psych_support_bot.ai.schemas.state import GraphState


def write_summary(state: GraphState) -> GraphState:
    mode = state["mode"]
    risk = state["risk_result"].risk_level
    reply_text = state["generated_reply"].text[:200]
    topics = state.get("topics")
    user_msg = state["user_message"]
    consultation_required = state.get("consultation_required", False)
    consultation_agents = state.get("consultation_agents", [])
    consultation_opinions = state.get("consultation_opinions", [])
    interview_stage = state.get("interview_stage", "engagement")
    question_strategy = state.get("question_strategy", "open")
    consultation_suffix = ""
    if consultation_required:
        consultation_suffix = f", consultation={consultation_agents}, opinions={len(consultation_opinions)}"
    process_suffix = f", stage={interview_stage}, question={question_strategy}"

    if topics:
        summary = (
            f"User (mode={mode}, risk={risk}, topics={topics}{consultation_suffix}{process_suffix}): {user_msg[:100]}. "
            f"Bot replied ({len(state['generated_reply'].text)} chars): {reply_text}"
        )
    else:
        summary = (
            f"User (mode={mode}, risk={risk}{consultation_suffix}{process_suffix}): {user_msg[:100]}. "
            f"Bot replied ({len(state['generated_reply'].text)} chars): {reply_text}"
        )

    state["session_summary"] = summary
    return state
