from psych_support_bot.domain.assessments.schemas import AssessmentType


def _frequency_options() -> list[dict[str, object]]:
    return [
        {"value": 0, "label": "完全没有"},
        {"value": 1, "label": "几天"},
        {"value": 2, "label": "一半以上天数"},
        {"value": 3, "label": "几乎每天"},
    ]


QUESTIONNAIRES: dict[AssessmentType, dict[str, object]] = {
    "phq9": {
        "code": "phq9",
        "title": "PHQ-9 抑郁筛查量表",
        "timeframe": "请根据过去两周的整体情况作答",
        "purpose": "用于筛查抑郁相关症状，以及这些症状对日常生活的影响。",
        "instructions": [
            "请根据过去两周的平均体验作答，而不是只按最好或最差的一天来判断。",
            "即使没有一个选项完全贴切，也请选择最接近的那个。",
            "这是一份筛查工具，不等同于临床诊断。",
        ],
        "options": _frequency_options(),
        "items": [
            "做事时提不起兴趣，或者感受不到乐趣",
            "感到情绪低落、沮丧或绝望",
            "入睡困难、睡不安稳，或者睡得太多",
            "感到疲惫，或精力不足",
            "食欲很差，或者吃得过多",
            "觉得自己很糟，或者觉得自己让自己或家人失望了",
            "难以专注于事情，比如看书或看电视时难以集中注意力",
            "动作或说话变得很慢，或者烦躁不安到别人都能注意到",
            "觉得不如死了算了，或者有伤害自己的想法",
        ],
        "min_score": 0,
        "max_score": 27,
        "item_max_score": 3,
    },
    "gad7": {
        "code": "gad7",
        "title": "GAD-7 焦虑筛查量表",
        "timeframe": "请根据过去两周的整体情况作答",
        "purpose": "用于筛查焦虑相关症状，例如过度担心、紧张和坐立不安。",
        "instructions": [
            "请根据过去两周的体验作答。",
            "想一想这些感受在日常生活中出现的频率。",
            "这份工具用于筛查和自我了解，不等同于诊断。",
        ],
        "options": _frequency_options(),
        "items": [
            "感到紧张、焦虑或心里发慌",
            "无法停止或控制担忧",
            "对各种不同的事情担心过多",
            "很难放松下来",
            "坐立不安，难以安静坐着",
            "容易烦躁或恼怒",
            "感到好像有什么可怕的事情要发生",
        ],
        "min_score": 0,
        "max_score": 21,
        "item_max_score": 3,
    },
    "isi": {
        "code": "isi",
        "title": "ISI 失眠严重程度量表",
        "timeframe": "请根据过去两周的整体情况作答",
        "purpose": "用于筛查睡眠困难的严重程度，以及它对白天生活的影响。",
        "instructions": [
            "请根据过去两周的整体睡眠情况作答，不要只按某一个晚上来判断。",
            "尽量同时考虑夜间睡眠困难和白天受影响的程度。",
            "这是一份筛查工具，不能单独用于诊断睡眠障碍。",
        ],
        "options": [
            {"value": 0, "label": "没有"},
            {"value": 1, "label": "轻度"},
            {"value": 2, "label": "中度"},
            {"value": 3, "label": "重度"},
            {"value": 4, "label": "非常严重"},
        ],
        "items": [
            "入睡困难的程度",
            "睡眠维持困难（半夜容易醒）的程度",
            "过早醒来的问题程度",
            "你对自己目前睡眠状况的满意程度如何？",
            "你认为睡眠问题对生活质量的影响，别人能明显看出来吗？",
            "你对当前睡眠问题有多担心或多苦恼？",
            "你认为睡眠问题对日常功能的干扰程度有多大？",
        ],
        "min_score": 0,
        "max_score": 28,
        "item_max_score": 4,
    },
}
