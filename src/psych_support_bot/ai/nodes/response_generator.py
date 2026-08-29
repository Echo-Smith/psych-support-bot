import logging
import re

from psych_support_bot.ai.consultation import consultation_agent_descriptions
from psych_support_bot.ai.prompts.templates import build_crisis_safety_prompt
from psych_support_bot.ai.safety.crisis import build_crisis_reply
from psych_support_bot.ai.schemas.messages import GeneratedReply
from psych_support_bot.ai.schemas.state import GraphState
from psych_support_bot.infra.llm.generation import (
    generate_clinically_bounded_reply,
    generate_multidisciplinary_consultation,
)
from psych_support_bot.infra.telemetry.tracing import trace_span, update_span_output

logger = logging.getLogger(__name__)

# Verbatim-repeat guard: when the freshly generated reply is byte-identical
# to the previous bot turn (Langfuse 巡检 2026-08-28 发现两轮不同输入产出
# 完全相同的回复), append a differentiated follow-up so consecutive turns
# never read as a copied message. Template (critical) replies are exempt —
# they are intentionally fixed.
_ZH_REPEAT_FOLLOWUP = (
    "\n\n换个角度说——此刻你的身体有什么感觉？是紧绷、发沉，还是别样的感受？"
)
_EN_REPEAT_FOLLOWUP = (
    "\n\nLet's take a different angle — what do you notice in your body right "
    "now: tension, heaviness, or something else?"
)


def _dedupe_reply(reply_text: str, previous_reply: str, expected_language: str) -> str:
    stripped = reply_text.strip()
    if not previous_reply or not stripped or stripped != previous_reply.strip():
        return reply_text
    followup = _ZH_REPEAT_FOLLOWUP if expected_language == "zh" else _EN_REPEAT_FOLLOWUP
    logger.warning("Reply identical to previous turn; appending differentiated follow-up.")
    return reply_text + followup


def _split_reply_messages(text: str) -> list[str]:
    """Split a generated reply into IM-style bubble messages (max 3).

    Returns an empty list when the reply cannot be meaningfully split,
    so callers fall back to rendering ``text`` as a single bubble.
    """
    parts = [p.strip() for p in re.split(r"\n\s*\n", text or "") if p.strip()]
    if len(parts) <= 1:
        return []
    if len(parts) > 3:
        parts = [*parts[:2], "\n\n".join(parts[2:])]
    return parts


def _inject_refusal_context(state: GraphState) -> None:
    """B3.3: If user has refused exercises before, inject context into loop_hint.

    This tells the LLM not to repeat recommendations for topics the user
    has already declined, improving personalization.
    """
    refusal_history = state.get("refusal_history", [])
    if not refusal_history:
        return
    refused_topics = ", ".join(refusal_history)
    existing_hint = state.get("loop_hint", "")
    refusal_note = (
        f"User has previously declined exercises related to: {refused_topics}. "
        "Do not recommend the same types of exercises again. "
        "Offer a different approach or explore why the previous suggestion did not fit."
    )
    state["loop_hint"] = refusal_note + " " + existing_hint if existing_hint else refusal_note


def generate_response(state: GraphState) -> GraphState:
    with trace_span(
        "node.response_generator",
        input={
            "user_message": state["user_message"],
            "mode": state["mode"],
            "risk_level": state["risk_result"].risk_level,
            "consultation_required": state.get("consultation_required", False),
        },
    ) as gen_obs:
        state["fallback_used"] = False
        risk_level = state["risk_result"].risk_level
        # Quiet mode is honored on ordinary support paths only; the crisis
        # paths below deliberately ignore it so safety resources still flow.
        no_question_mode = bool(state.get("no_question_mode", False))

        # B3.3: Inject refusal history into loop_hint before LLM generation
        _inject_refusal_context(state)

        # Only critical risk uses pure template reply (imminent danger)
        # High risk now goes through LLM with crisis safety prompt injected
        if risk_level == "critical":
            reply_text = build_crisis_reply(state["risk_result"], user_message=state["user_message"], expected_language=state.get("expected_language", ""))
            state["consultation_opinions"] = []
        elif state["mode"] == "crisis" and risk_level == "high":
            # High-risk crisis: use LLM with crisis safety guidance
            try:
                reply_text = generate_clinically_bounded_reply(
                    user_message=state["user_message"],
                    mode="crisis",
                    risk_level="high",
                    memory_summary=state.get("memory_summary", ""),
                    knowledge_context=build_crisis_safety_prompt(),
                    consultation_required=False,
                    consultation_agents=[],
                    consultation_framework="",
                    interview_stage="engagement",
                    question_strategy="open",
                    challenge_allowed=False,
                    loop_hint="Prioritize safety, validation, and gentle redirection to support resources.",
                    expected_language=state.get("expected_language", ""),
                )
                state["consultation_opinions"] = []
            except Exception:
                logger.exception("LLM generation failed for high-risk; using crisis template fallback.")
                state["fallback_used"] = True
                reply_text = build_crisis_reply(state["risk_result"], user_message=state["user_message"], expected_language=state.get("expected_language", ""))
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
                        loop_hint=state.get("loop_hint", "Start broad, reflect, then narrow."),
                        expected_language=state.get("expected_language", ""),
                        no_question_mode=no_question_mode,
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
                        loop_hint=state.get("loop_hint", "Start broad, reflect, then narrow."),
                        expected_language=state.get("expected_language", ""),
                        no_question_mode=no_question_mode,
                    )
                    state["consultation_opinions"] = []
            except Exception:
                logger.exception("LLM generation failed; using template fallback.")
                state["fallback_used"] = True
                is_zh = state.get("expected_language", "") == "zh" or (
                    not state.get("expected_language")
                    and any("\u4e00" <= char <= "\u9fff" for char in state.get("user_message", ""))
                )
                if is_zh:
                    reply_text = (
                        "我在这里陪你。虽然我现在遇到了一些技术困难，"
                        "但我仍然想支持你。我们可以先慢下来，聊一聊你现在的感受。"
                    )
                else:
                    reply_text = (
                        "I am here with you. Although I am experiencing some technical difficulty, "
                        "I still want to support you. Let us slow down and talk about how you are feeling right now."
                    )

        # LLM-generated paths guard against verbatim repeats of the previous
        # turn; the critical template reply is intentionally fixed.
        if risk_level != "critical":
            reply_text = _dedupe_reply(
                reply_text,
                state.get("last_bot_reply", ""),
                state.get("expected_language", ""),
            )

        state["generated_reply"] = GeneratedReply(
            text=reply_text,
            style=state["mode"],
            includes_action_step=True,
            # Crisis replies keep hotline resources in one intact bubble.
            messages=_split_reply_messages(reply_text) if risk_level in {"low", "elevated"} else [],
        )
        state["consultation_notes"] = (
            f"{len(state.get('consultation_opinions', []))} agents consulted; stage={state.get('interview_stage', 'engagement')}; question={state.get('question_strategy', 'open')}"
            if state.get("consultation_required")
            else f"single response path; stage={state.get('interview_stage', 'engagement')}; question={state.get('question_strategy', 'open')}"
        )
        update_span_output(gen_obs, {
            "reply_text": reply_text[:200],
            "fallback_used": state["fallback_used"],
            "consultation_notes": state["consultation_notes"],
        })
    return state
