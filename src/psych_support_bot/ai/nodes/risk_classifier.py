import logging
import re

from psych_support_bot.ai.safety.rules import classify_message_risk
from psych_support_bot.ai.schemas.messages import RiskResult
from psych_support_bot.ai.schemas.state import GraphState
from psych_support_bot.infra.telemetry.tracing import trace_span, update_span_output

logger = logging.getLogger(__name__)

# Patterns to detect previous elevated risk in memory_summary.
# Memory snapshot contains recent messages and risk info; we look for
# signs that the previous turn was classified as elevated distress.
_PREV_ELEVATED_PATTERNS = [
    # Risk level markers in session summary format
    r"risk\s*=\s*elevated",
    r"risk_level.*elevated",
    # Elevated distress keywords appearing in recent message excerpts
    # (these overlap with ELEVATED_RISK_KEYWORDS from rules.py)
    r"绝望|没有希望|没意义|撑不住|扛不住|快崩溃|睡不着|失眠|惊恐发作|喘不过气",
    r"hopeless|panic attack|worthless|not sleeping|better off dead",
]

_PREV_ELEVATED_REGEX = [re.compile(p, re.IGNORECASE) for p in _PREV_ELEVATED_PATTERNS]


def _has_previous_elevated(memory_summary: str) -> bool:
    """Check if memory_summary indicates the previous turn was elevated risk."""
    if not memory_summary:
        return False
    return any(pattern.search(memory_summary) for pattern in _PREV_ELEVATED_REGEX)


def classify_risk(state: GraphState) -> GraphState:
    with trace_span(
        "node.risk_classifier",
        input={"user_message": state["user_message"], "memory_summary": state.get("memory_summary", "")},
    ) as obs:
        risk_result = classify_message_risk(state["user_message"])
        state["risk_result"] = RiskResult(**risk_result.model_dump())

        # B2.2: Cross-turn risk tracking
        # If the current turn is elevated AND the previous turn was also elevated,
        # automatically upgrade to high risk. Persistent elevated distress across
        # consecutive turns signals accumulating risk that warrants closer attention.
        if risk_result.risk_level == "elevated":
            memory_summary = state.get("memory_summary", "")
            if _has_previous_elevated(memory_summary):
                state["risk_result"] = RiskResult(
                    risk_level="high",
                    risk_types=[*risk_result.risk_types, "cumulative_elevated"],
                    needs_crisis_mode=True,
                    reason=(
                        "Consecutive elevated distress across turns; "
                        "upgraded to high risk for safety. Original: " + risk_result.reason
                    ),
                )
                logger.info("Cross-turn risk upgrade: elevated -> high (consecutive elevated detected)")

        # Safety floor from recent screening results (e.g. a PHQ-9 run whose
        # item-9 answer set needs_safety_followup). A single turn without any
        # matching keyword must not downgrade below a recent clinical signal;
        # severity >= high also arms crisis mode like a direct detection would.
        # NOTE: applied *before* the mode switch below so a floor of high
        # routes into crisis mode exactly like a natively detected signal.
        floor = str(state.get("safety_floor_risk_level") or "").strip()
        if floor in {"elevated", "high", "critical"}:
            severity = {"low": 0, "elevated": 1, "high": 2, "critical": 3}
            current = state["risk_result"]
            if severity[current.risk_level] < severity[floor]:
                state["risk_result"] = RiskResult(
                    risk_level=floor,
                    risk_types=[*current.risk_types, "recent_screening_flag"],
                    needs_crisis_mode=current.needs_crisis_mode or severity[floor] >= 2,
                    reason=(
                        "Safety floor applied: recent screening flagged safety follow-up. "
                        "Original: " + current.reason
                    ),
                )
                logger.info(
                    "Safety floor applied: %s -> %s (recent screening flag)",
                    current.risk_level,
                    floor,
                )

        if state["risk_result"].needs_crisis_mode:
            state["mode"] = "crisis"

        update_span_output(obs, {
            "risk_level": state["risk_result"].risk_level,
            "risk_types": state["risk_result"].risk_types,
            "needs_crisis_mode": state["risk_result"].needs_crisis_mode,
            "mode": state["mode"],
        })
    return state
