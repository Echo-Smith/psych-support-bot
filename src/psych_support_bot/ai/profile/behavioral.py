"""行为信号层：从现有对话数据中提取行为特征。

不创建画像信念——行为信号的用途是喂给好奇心注入，
在不确定时自然地问一句。信号本身带着噪声（网络延迟、
屏幕外的世界），所以不做推断，只做观察。

设计原则：
- 信号是观察，不是诊断
- 异常是对话入口，不是数据点
- 用户的解释才是真正的数据
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def detect_behavioral_signals(
    *,
    user_message: str,
    bot_message_timestamp: datetime | None = None,
    user_message_timestamp: datetime | None = None,
    recent_message_lengths: list[int] | None = None,
    session_hour: int = -1,
) -> list[dict[str, Any]]:
    """检测当前轮次的行为异常信号。

    返回信号列表，每个信号是 {"type": str, "detail": str, "question_zh": str, "question_en": str}。
    不做推断——只提供"可以问什么"的建议。
    """
    signals: list[dict[str, Any]] = []

    # 1. 回复延迟异常（>5 分钟，排除网络噪声的阈值）
    if bot_message_timestamp and user_message_timestamp:
        if bot_message_timestamp.tzinfo is None:
            bot_message_timestamp = bot_message_timestamp.replace(tzinfo=UTC)
        if user_message_timestamp.tzinfo is None:
            user_message_timestamp = user_message_timestamp.replace(tzinfo=UTC)
        latency = (user_message_timestamp - bot_message_timestamp).total_seconds()
        if 300 < latency < 3600:  # 5-60 分钟：可能是有意义的停顿
            signals.append({
                "type": "long_pause",
                "detail": f"{int(latency // 60)}min",
                "question_zh": "你刚才好像停了一会儿，是发生了什么吗？",
                "question_en": "You seem to have paused for a moment — did something happen?",
            })

    # 2. 消息长度突变（比近期平均短 60%+）
    if recent_message_lengths and len(recent_message_lengths) >= 3:
        avg_len = sum(recent_message_lengths) / len(recent_message_lengths)
        current_len = len(user_message or "")
        if avg_len > 20 and current_len < avg_len * 0.4 and current_len > 0:
            signals.append({
                "type": "short_message",
                "detail": f"{current_len} vs avg {int(avg_len)}",
                "question_zh": "你今天的回复比之前简短一些，是累了还是不太想聊这个？",
                "question_en": "Your message is shorter than usual — are you tired or not in the mood to talk about this?",
            })

    # 3. 深夜来访（23:00-05:00）
    if session_hour >= 23 or session_hour <= 4:
        signals.append({
            "type": "late_night",
            "detail": f"hour={session_hour}",
            "question_zh": "这么晚了还没休息，是睡不着还是有什么事在心里？",
            "question_en": "It's quite late — are you having trouble sleeping, or is something on your mind?",
        })

    # 限制每轮最多 1 个信号（不轰炸用户）
    return signals[:1] if signals else []
