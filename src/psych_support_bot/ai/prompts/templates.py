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
