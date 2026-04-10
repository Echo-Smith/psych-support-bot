KNOWLEDGE_SNIPPETS = {
    "support": [
        "Validate emotion before offering suggestions.",
        "Reflect the user's distress in plain language.",
        "End with one manageable next step, not a long checklist.",
    ],
    "assessment": [
        "Clarify duration, frequency, severity, and impact on daily functioning.",
        "Use non-diagnostic language and encourage professional evaluation when symptoms persist.",
        "Ask at most one or two focused follow-up questions.",
    ],
    "intervention": [
        "Offer exactly one structured skill at a time.",
        "Prefer CBT, ACT, DBT, or behavioral activation techniques.",
        "Keep practice steps concrete and brief.",
    ],
    "planning": [
        "Translate insight into a low-friction action for today.",
        "Prefer actions that reduce avoidance and increase stability.",
        "Keep plans realistic enough to complete under stress.",
    ],
    "crisis": [
        "Use short, direct safety-oriented language.",
        "Do not explore causes deeply during crisis routing.",
        "Encourage real-world support and urgent care if danger is immediate.",
    ],
}


def get_knowledge_context(mode: str, risk_level: str) -> str:
    snippets = KNOWLEDGE_SNIPPETS.get(mode, [])
    joined = " ".join(snippets)
    return f"Risk level: {risk_level}. Practice guidance: {joined}".strip()
