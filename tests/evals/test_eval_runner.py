from psych_support_bot.evals.runner import run_eval_cases


def test_eval_runner_cases_pass() -> None:
    results = run_eval_cases()
    assert results
    assert all(bool(item["passed"]) for item in results)
