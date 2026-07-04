from psych_support_bot.ai.schemas.messages import ConversationMode
from psych_support_bot.ai.utils.text_matching import (
    _contains_keyword,
    _normalize_text,
)

HELP_KEYWORDS = [
    "how are you",
    "what can you do",
    "who are you",
    "hello",
    "hi",
    "hey",
    "how do you work",
    "怎么用",
    "你能做什么",
    "你是谁",
    "你好",
    "嗨",
]
REFUSAL_KEYWORDS = [
    "skip",
    "pass",
    "don't want",
    "不想做了",
    "不想做",
    "跳过",
    "算了",
    "不要",
    "跳过这题",
]
CRISIS_KEYWORDS = [
    "suicide",
    "kill myself",
    "end my life",
    "want to die",
    "self-harm",
    "help me",
    "emergency",
    "crisis",
    "救命",
    "紧急帮助",
    "危机干预",
    "有人吗救救我",
]
PLANNING_KEYWORDS = [
    "plan",
    "next step",
    "schedule",
    "计划",
    "下一步",
    "安排",
    "怎么做",
    "怎么开始",
    "行动计划",
]
INTERVENTION_KEYWORDS = [
    "exercise",
    "breath",
    "breathing exercise",
    "thought record",
    "relaxation",
    "calming exercise",
    "grounding",
    "cbt",
    "act",
    "dbt",
    "panic attack",
    "panic",
    "练习",
    "呼吸",
    "呼吸练习",
    "呼吸法",
    "带我做",
    "教我一个方法",
    "缓解焦虑",
    "放松",
    "想法记录",
    "认知行为",
    "技巧",
    "惊恐发作",
]
ASSESSMENT_KEYWORDS = [
    "assessment",
    "screen",
    "score",
    "评估",
    "测评",
    "量表",
    "测试",
    "筛查",
    "问卷",
    "打分",
    "phq",
    "gad",
]


def detect_mode(text: str) -> ConversationMode:
    normalized, compact = _normalize_text(text)
    stripped = normalized.strip()

    if stripped in {"hello", "hi", "hey", "你好", "嗨"}:
        return "support"
    if any(
        _contains_keyword(normalized, compact, keyword) for keyword in REFUSAL_KEYWORDS
    ):
        return "support"
    if any(
        _contains_keyword(normalized, compact, keyword) for keyword in CRISIS_KEYWORDS
    ):
        return "crisis"
    if any(
        _contains_keyword(normalized, compact, keyword)
        for keyword in INTERVENTION_KEYWORDS
    ):
        return "intervention"
    if any(
        _contains_keyword(normalized, compact, keyword) for keyword in PLANNING_KEYWORDS
    ):
        return "planning"
    if any(
        _contains_keyword(normalized, compact, keyword)
        for keyword in ASSESSMENT_KEYWORDS
    ):
        return "assessment"
    if any(
        _contains_keyword(normalized, compact, keyword) for keyword in HELP_KEYWORDS
    ):
        return "support"
    return "support"
