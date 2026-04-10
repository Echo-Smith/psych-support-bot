from psych_support_bot.infra.config.settings import get_settings


def tracing_config() -> dict[str, str]:
    settings = get_settings()
    return {
        "host": settings.langfuse_host,
        "public_key": settings.langfuse_public_key,
        "configured": str(
            bool(settings.langfuse_public_key and settings.langfuse_secret_key)
        ).lower(),
    }
