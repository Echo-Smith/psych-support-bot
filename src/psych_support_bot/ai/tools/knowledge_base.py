from psych_support_bot.ai.knowledge.index import (
    detect_topics,
    retrieve_knowledge_entries,
)

KNOWLEDGE_SNIPPETS = {
    "support": [
        "Validate emotion before offering suggestions.",
        "Use plain-language psychoeducation to explain common stress, anxiety, sleep, or mood reactions.",
        "Offer reassurance and one manageable next step, not a treatment sequence.",
    ],
    "assessment": [
        "Clarify duration, frequency, severity, and impact on daily functioning.",
        "Use non-diagnostic language and simple explanation rather than medicalized framing.",
        "Ask at most one or two focused follow-up questions.",
    ],
    "intervention": [
        "Only offer a skill when the user clearly wants one.",
        "Prefer light grounding, calming, or self-observation over therapy-heavy protocols.",
        "Keep practice steps concrete, brief, and low pressure.",
    ],
    "planning": [
        "Translate insight into a low-friction action for today.",
        "Prefer actions that increase stability, rest, and self-kindness.",
        "Keep plans realistic enough to complete under stress.",
    ],
    "crisis": [
        "Use short, direct safety-oriented language.",
        "Do not explore causes deeply during crisis routing.",
        "Encourage real-world support and urgent care if danger is immediate.",
    ],
}


def _render_entry(entry_id: str, title: str, summary: str, action_hint: str) -> str:
    rendered = f"{entry_id}: {title}. {summary}"
    if action_hint:
        rendered += f" Action hint: {action_hint}"
    return rendered


def _grouped_entries_text(entries: list) -> list[str]:
    learning_entries = [entry for entry in entries if entry.source == "active_learning"]
    # active_learning 已单独渲染进 Synthesized takeaways 时不再重复进
    # Psychoeducation notes——同一 entry 双区渲染既冗余又挤占预算。
    psychoeducation_sources = {"psychoeducation", "foundation"} | (
        set() if learning_entries else {"active_learning"}
    )
    psychoeducation_entries = [entry for entry in entries if entry.source in psychoeducation_sources]
    grounded_entries = [
        entry for entry in entries if entry.source not in {"active_learning", "psychoeducation", "foundation"}
    ]
    sections: list[str] = []

    if learning_entries:
        rendered_learning = [
            _render_entry(entry.entry_id, entry.title, entry.summary, entry.action_hint)
            for entry in learning_entries[:2]
        ]
        sections.append("Synthesized takeaways: " + " ".join(rendered_learning))

    if psychoeducation_entries:
        rendered_psychoeducation = [
            _render_entry(entry.entry_id, entry.title, entry.summary, entry.action_hint)
            for entry in psychoeducation_entries[:3]
        ]
        sections.append("Psychoeducation notes: " + " ".join(rendered_psychoeducation))

    if grounded_entries:
        rendered_grounded = [
            _render_entry(entry.entry_id, entry.title, entry.summary, entry.action_hint)
            for entry in grounded_entries[:5]
        ]
        sections.append("Grounded references: " + " ".join(rendered_grounded))

    return sections


def get_knowledge_context(mode: str, risk_level: str, user_message: str = "") -> str:
    topics = detect_topics(user_message)
    entries = retrieve_knowledge_entries(user_message, mode, risk_level, limit=5)
    base_snippets = KNOWLEDGE_SNIPPETS.get(mode, [])

    sections = [
        f"Risk level: {risk_level}.",
        f"Mode: {mode}.",
        f"Practice guidance: {' '.join(base_snippets)}",
    ]
    if topics:
        sections.append(f"Detected topics: {', '.join(topics)}.")
    if entries:
        sections.extend(_grouped_entries_text(entries))
    if not entries:
        # 商业化指标：无知识命中（prompt 走结构化兜底框架）的触发率是
        # "是否值得投语义检索"的决策依据，走 Langfuse 事件不落库。
        _emit_fallback_metric(mode, topics)
    return _clip_context(" ".join(sections).strip())


# 知识区总量预算（字符）。命中条目多时截断尾部——检索已按相关性排序，
# 截尾损失最小。防外部语料一次命中多条（单条可达数百字符）挤占回复预算。
KNOWLEDGE_CONTEXT_BUDGET = 2400


def _clip_context(context: str, budget: int = KNOWLEDGE_CONTEXT_BUDGET) -> str:
    if len(context) <= budget:
        return context
    return context[: budget - 1].rstrip() + "…"


def _emit_fallback_metric(mode: str, topics: list[str]) -> None:
    try:
        from psych_support_bot.infra.telemetry.tracing import get_langfuse

        client = get_langfuse()
        if client is not None:
            client.create_event(name="knowledge_fallback", metadata={"mode": mode, "topics": topics})
    except Exception:  # noqa: BLE001 – 观测失败不影响对话主流程
        pass
