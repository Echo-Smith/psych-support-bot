import logging

from psych_support_bot.ai.consultation import consultation_agent_descriptions
from psych_support_bot.ai.schemas.messages import GeneratedReply
from psych_support_bot.ai.schemas.state import GraphState
from psych_support_bot.ai.safety.crisis import build_crisis_reply
from psych_support_bot.infra.llm.generation import (
    generate_clinically_bounded_reply,
    generate_multidisciplinary_consultation,
)

logger = logging.getLogger(__name__)


def generate_response(state: GraphState) -> GraphState:
    state["fallback_used"] = False
    if state["mode"] == "crisis":
        reply_text = build_crisis_reply(
            state["risk_result"], user_message=state["user_message"]
        )
    else:
        try:
            if state.get("consultation_required", False):
                reply_text, opinions = generate_multidisciplinary_consultation(
                    user_message=state["user_message"],
                    mode=state["mode"],
                    risk_level=state["risk_result"].risk_level,
                    memory_summary=state.get("memory_summary", ""),
                    knowledge_context=state.get("knowledge_context", ""),
                    consultation_framework=consultation_agent_descriptions(),
                    interview_stage=state.get("interview_stage", "engagement"),
                    question_strategy=state.get("question_strategy", "open"),
                    challenge_allowed=bool(state.get("challenge_allowed", False)),
                    loop_hint=state.get(
                        "loop_hint", "Start broad, reflect, then narrow."
                    ),
                )
                state["consultation_opinions"] = opinions
            else:
                reply_text = generate_clinically_bounded_reply(
                    user_message=state["user_message"],
                    mode=state["mode"],
                    risk_level=state["risk_result"].risk_level,
                    memory_summary=state.get("memory_summary", ""),
                    knowledge_context=state.get("knowledge_context", ""),
                    consultation_required=False,
                    consultation_agents=[],
                    consultation_framework="",
                    interview_stage=state.get("interview_stage", "engagement"),
                    question_strategy=state.get("question_strategy", "open"),
                    challenge_allowed=bool(state.get("challenge_allowed", False)),
                    loop_hint=state.get(
                        "loop_hint", "Start broad, reflect, then narrow."
                    ),
                )
                state["consultation_opinions"] = []
        except Exception as exc:
            logger.exception("LLM generation failed with no template fallback.")
            raise RuntimeError("LLM generation failed") from exc
            state["fallback_used"] = True

    state["generated_reply"] = GeneratedReply(
        text=reply_text,
        style=state["mode"],
        includes_action_step=True,
    )
    state["consultation_notes"] = (
        f"{len(state.get('consultation_opinions', []))} agents consulted; stage={state.get('interview_stage', 'engagement')}; question={state.get('question_strategy', 'open')}"
        if state.get("consultation_required")
        else f"single response path; stage={state.get('interview_stage', 'engagement')}; question={state.get('question_strategy', 'open')}"
    )
    return state
