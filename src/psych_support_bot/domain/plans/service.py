from psych_support_bot.domain.plans.templates import PLAN_TEMPLATES


def list_plans() -> dict[str, dict[str, object]]:
    return PLAN_TEMPLATES


def get_plan(plan_id: str) -> dict[str, object]:
    return PLAN_TEMPLATES[plan_id]
