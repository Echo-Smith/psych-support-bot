from psych_support_bot.evals.runner import run_eval_cases


def test_eval_runner_cases_pass() -> None:
    results = run_eval_cases()
    assert results
    failed = [r for r in results if not r["passed"]]
    for item in failed:
        print(f"FAILED: {item['name']} got_mode={item['mode']} got_risk={item['risk']}")
    assert all(bool(item["passed"]) for item in results)
