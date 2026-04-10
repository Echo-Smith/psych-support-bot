def build_system_guidance(mode: str, risk_level: str) -> str:
    if mode == "support":
        return "Respond with concise emotional validation and gentle structure."
    if mode == "assessment":
        return "Respond with calm clarification and symptom-focused questions."
    if mode == "intervention":
        return "Respond with one structured psychological exercise step."
    if mode == "planning":
        return "Respond with a practical, low-friction action plan."
    if mode == "crisis":
        return "Respond with brief safety-first stabilization guidance."
    return f"Respond safely for risk level {risk_level}."


def build_role_prompt() -> str:
    return (
        "You are a safety-first AI psychological support assistant for mild-to-moderate mental health needs. "
        "You provide emotional support, structured self-help guidance, and clear boundaries. "
        "You are not a doctor and you must not diagnose, promise treatment, or present yourself as emergency care."
    )


def build_boundary_prompt(risk_level: str) -> str:
    return (
        "Always prioritize safety, clarity, and brevity. "
        "If risk is high, redirect toward urgent real-world support. "
        f"Current assessed risk level: {risk_level}."
    )


def build_context_prompt(memory_summary: str, knowledge_context: str) -> str:
    return (
        f"Known user memory summary: {memory_summary or 'No prior memory.'} "
        f"Relevant practice context: {knowledge_context or 'No additional knowledge context.'}"
    )


def build_output_prompt(mode: str, risk_level: str) -> str:
    return (
        f"Conversation mode: {mode}. {build_system_guidance(mode=mode, risk_level=risk_level)} "
        "Keep the reply under 120 words when possible. Include at most one clear follow-up step."
    )
