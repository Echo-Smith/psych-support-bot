from fastapi import APIRouter

from psych_support_bot.infra.config.settings import get_settings
from psych_support_bot.infra.telemetry.tracing import tracing_config

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/info")
def system_info() -> dict[str, object]:
    settings = get_settings()
    return {
        "app_name": settings.app_name,
        "environment": settings.environment,
        "default_model": settings.openai_model,
        "workflow": settings.default_conversation_mode,
        "tracing": tracing_config(),
    }
