from psych_support_bot.ai.prompts.templates import build_system_guidance
from psych_support_bot.ai.schemas.messages import GeneratedReply
from psych_support_bot.ai.schemas.state import GraphState
from psych_support_bot.infra.llm.generation import generate_clinically_bounded_reply


def generate_response(state: GraphState) -> GraphState:
    if state["mode"] == "crisis":
        reply_text = (
            "I am concerned about your safety. If there is any immediate danger, contact a trusted person, "
            "local emergency services, or go to the nearest hospital now. If you can, do not stay alone."
        )
    else:
        guidance = build_system_guidance(
            mode=state["mode"], risk_level=state["risk_result"].risk_level
        )
        fallback_text = (
            f"{guidance} I hear that this has been hard for you. "
            "Let us focus on one manageable step today: name the strongest feeling and what triggered it most recently."
        )
        try:
            reply_text = generate_clinically_bounded_reply(
                user_message=state["user_message"],
                mode=state["mode"],
                risk_level=state["risk_result"].risk_level,
                memory_summary=state.get("memory_summary", ""),
                knowledge_context=state.get("knowledge_context", ""),
            )
        except Exception:
            reply_text = fallback_text

    state["generated_reply"] = GeneratedReply(
        text=reply_text,
        style=state["mode"],
        includes_action_step=True,
    )
    return state
