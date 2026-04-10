from psych_support_bot.infra.telemetry.tracing import timed_call, trace_event


def test_trace_event_has_metadata() -> None:
    event = trace_event("demo", {"x": 1})
    assert event["event"] == "demo"
    assert event["metadata"]["x"] == 1


def test_timed_call_returns_result_and_trace() -> None:
    result, trace = timed_call("calc", lambda: 42)
    assert result == 42
    assert trace["event"] == "calc"
    assert "elapsed_ms" in trace["metadata"]
