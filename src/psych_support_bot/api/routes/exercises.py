from fastapi import APIRouter, HTTPException

from psych_support_bot.ai.tools.exercises import get_exercise_by_tag, list_all_exercises

router = APIRouter(prefix="/v1/exercises", tags=["exercises"])


@router.get("")
def list_exercises() -> dict[str, list[str]]:
    return list_all_exercises()


@router.get("/{exercise_tag}")
def get_exercise(exercise_tag: str) -> dict:
    exercise = get_exercise_by_tag(exercise_tag)
    if exercise is None:
        raise HTTPException(status_code=404, detail="Exercise not found")
    return exercise
