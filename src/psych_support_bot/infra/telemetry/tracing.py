from collections.abc import Callable
from time import perf_counter
from typing import TypedDict

from psych_support_bot.infra.config.settings import get_settings


class TraceEvent(TypedDict):
    event: str
    metadata: dict[str, object]
    host: str
    public_key: str
    configured: str


def tracing_config() -> dict[str, str]:
    settings = get_settings()
    return {
        "host": settings.langfuse_host,
        "public_key": settings.langfuse_public_key,
        "configured": str(
            bool(settings.langfuse_public_key and settings.langfuse_secret_key)
        ).lower(),
    }


def trace_event(name: str, metadata: dict[str, object] | None = None) -> TraceEvent:
    return TraceEvent(
        event=name,
        metadata=metadata or {},
        **tracing_config(),
    )


def timed_call(name: str, callback: Callable[[], object]) -> tuple[object, TraceEvent]:
    started = perf_counter()
    result = callback()
    elapsed_ms = round((perf_counter() - started) * 1000, 2)
    return result, trace_event(name, {"elapsed_ms": elapsed_ms})
