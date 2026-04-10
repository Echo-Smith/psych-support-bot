from collections.abc import Callable
from time import perf_counter

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


def trace_event(
    name: str, metadata: dict[str, object] | None = None
) -> dict[str, object]:
    return {
        "event": name,
        "metadata": metadata or {},
        **tracing_config(),
    }


def timed_call(
    name: str, callback: Callable[[], object]
) -> tuple[object, dict[str, object]]:
    started = perf_counter()
    result = callback()
    elapsed_ms = round((perf_counter() - started) * 1000, 2)
    return result, trace_event(name, {"elapsed_ms": elapsed_ms})
