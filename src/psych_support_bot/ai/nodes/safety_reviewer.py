from psych_support_bot.ai.prompts.templates import (
    build_boundary_prompt,
    build_context_prompt,
    build_output_prompt,
    build_role_prompt,
    build_system_guidance,
)
from psych_support_bot.ai.schemas.state import GraphState


def _build_leak_markers() -> tuple[str, ...]:
    role_text = build_role_prompt()
    boundary_text = build_boundary_prompt(risk_level="low")
    context_text = build_context_prompt(memory_summary="", knowledge_context="")
    output_text = build_output_prompt(
        mode="support", risk_level="low", user_message="hello"
    )
    system_guidance_text = build_system_guidance(mode="support", risk_level="low")

    markers: list[str] = []

    if "You are a safety-first" in role_text:
        markers.append("You are a safety-first")
    if "You are a safety-first" in role_text:
        markers.append("You are a safety-first AI")
    for marker in [
        "Conversation mode:",
        "Current assessed risk level:",
        "Known user memory summary:",
        "Relevant practice context:",
    ]:
        if marker in boundary_text or marker in context_text or marker in output_text:
            markers.append(marker)
    if "Respond with" in system_guidance_text or "Respond with" in output_text:
        markers.append("Respond with")

    extra_markers = [
        "System prompt",
        "You are a safety-first",
        "You are a safety-first AI psychological support assistant",
        "Conversation mode:",
        "Current assessed risk",
        "Current assessed risk level",
        "Known user memory summary:",
        "Relevant practice context:",
        "Relevant practice context",
        "Respond with",
        "系统提示",
        "你是一个安全优先的",
        "对话模式：",
        "当前评估风险",
        "已知用户记忆摘要：",
        "相关实践背景：",
        "请以",
    ]
    for m in extra_markers:
        if m not in markers:
            markers.append(m)

    return tuple(markers)


LEAK_MARKERS: tuple[str, ...] = _build_leak_markers()


def review_response(state: GraphState) -> GraphState:
    text = state["generated_reply"].text
    if any(marker in text for marker in LEAK_MARKERS):
        text = "I am here with you. Let us slow this down and focus on one small next step together."
        if any("\u4e00" <= char <= "\u9fff" for char in state["user_message"]):
            text = "我在这里陪你。我们先把节奏放慢一点，只聚焦眼前一个小步骤。"
        state["generated_reply"].text = text
    if state["risk_result"].needs_crisis_mode:
        state["generated_reply"].includes_action_step = True
    return state
