from psych_support_bot.ai.routers.intent import detect_mode


def test_detect_mode_routes_chinese_assessment() -> None:
    assert detect_mode("我想做个焦虑量表测评") == "assessment"


def test_detect_mode_routes_chinese_intervention() -> None:
    assert detect_mode("带我做一个呼吸练习") == "intervention"


def test_detect_mode_routes_chinese_planning() -> None:
    assert detect_mode("帮我定一个接下来三天的计划") == "planning"


def test_detect_mode_defaults_to_support() -> None:
    assert detect_mode("我只是想聊聊最近压力很大") == "support"


def test_detect_mode_routes_chinese_help() -> None:
    assert detect_mode("我需要紧急帮助") == "crisis"


def test_detect_mode_routes_chinese_refusal() -> None:
    assert detect_mode("我不想做测评") == "support"
