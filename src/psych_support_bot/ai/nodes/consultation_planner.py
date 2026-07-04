from psych_support_bot.ai.consultation import (
    consultation_agent_labels,
    should_trigger_multidisciplinary_consultation,
)
from psych_support_bot.ai.interview import determine_interview_process
from psych_support_bot.ai.schemas.state import GraphState


def plan_consultation(state: GraphState) -> GraphState:
    required = should_trigger_multidisciplinary_consultation(
        user_message=state["user_message"],
        mode=state["mode"],
        risk_level=state["risk_result"].risk_level,
    )
    state["consultation_required"] = required
    state["consultation_agents"] = consultation_agent_labels() if required else []
    state["consultation_notes"] = ""
    state["consultation_opinions"] = []
    interview_process = determine_interview_process(
        user_message=state["user_message"],
        mode=state["mode"],
        risk_level=state["risk_result"].risk_level,
    )
    state["interview_stage"] = str(interview_process["interview_stage"])
    state["question_strategy"] = str(interview_process["question_strategy"])
    state["challenge_allowed"] = bool(interview_process["challenge_allowed"])
    state["loop_hint"] = str(interview_process["loop_hint"])
    return state
