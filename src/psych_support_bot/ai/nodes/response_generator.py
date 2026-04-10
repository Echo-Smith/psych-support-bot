from psych_support_bot.ai.prompts.templates import build_system_guidance
from psych_support_bot.ai.schemas.messages import GeneratedReply
from psych_support_bot.ai.schemas.state import GraphState


def generate_response(state: GraphState) -> GraphState:
    guidance = build_system_guidance(
        mode=state["mode"], risk_level=state["risk_result"].risk_level
    )

    if state["mode"] == "crisis":
        reply_text = (
            "I am concerned about your safety. If there is any immediate danger, contact a trusted person, "
            "local emergency services, or go to the nearest hospital now. If you can, do not stay alone."
        )
    else:
        reply_text = (
            f"{guidance} I hear that this has been hard for you. "
            "Let us focus on one manageable step today: name the strongest feeling and what triggered it most recently."
        )

    state["generated_reply"] = GeneratedReply(
        text=reply_text,
        style=state["mode"],
        includes_action_step=True,
    )
    return state
