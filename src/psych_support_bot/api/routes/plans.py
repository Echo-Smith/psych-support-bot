from fastapi import APIRouter, HTTPException

from psych_support_bot.domain.plans.service import get_plan, list_plans

router = APIRouter(prefix="/v1/plans", tags=["plans"])


@router.get("")
def get_plans() -> dict[str, dict[str, object]]:
    return list_plans()


@router.get("/{plan_id}")
def get_plan_by_id(plan_id: str) -> dict[str, object]:
    try:
        return get_plan(plan_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Plan not found") from exc
