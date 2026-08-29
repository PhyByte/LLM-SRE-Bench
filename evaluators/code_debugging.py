"""code_debugging scoring: did the fix actually fix it?

Score = 0.70 * correctness + 0.20 * compilation + 0.10 * code_quality

where correctness = 0.5 * all tests + 0.5 * the tests the bug actually breaks.

The hidden tests deliberately include inputs the buggy version already handled,
because a fix that breaks them is not a fix. But scoring the whole set equally
would pay most of the correctness weight for changing nothing — how much
depends only on how many tests happen to touch the bug. So the tests the
shipped buggy version fails (recorded per case and per language at dataset
build time) are scored as their own half: returning the code unchanged earns
the first half and none of the second.

Runtime speed is not scored — these are small functions and the interesting
failure is behavioral.
"""

from __future__ import annotations

from typing import Any

from core.schemas import CodeGenerationResult

from .base import EvalResult
from .code_exec import run_case, score_execution


def evaluate(case: dict[str, Any], result: CodeGenerationResult) -> EvalResult:
    outcome = run_case(case, result.code)
    if outcome.failure is not None:
        return EvalResult(score=0.0, metrics=outcome.failure)

    metrics: dict[str, Any] = {}
    # Returning the prompt's code verbatim is a distinctive non-answer; flag it
    # so a run's reports can tell "did not fix" from "fixed it wrong".
    if result.code.strip() == case.get("buggy_code", "").strip():
        metrics["unchanged_code"] = 1.0

    regression = case.get("regression_indices") or []
    regression_rate = outcome.pass_rate_over(regression)
    if regression_rate is None:
        # No per-test detail (compile error, panic, timeout) — the overall rate
        # is the only honest number available.
        correctness = outcome.correctness
    else:
        correctness = 0.5 * outcome.correctness + 0.5 * regression_rate
        metrics["bug_tests_passed"] = regression_rate

    return score_execution(
        outcome,
        weights={"correctness": 0.70, "compiled": 0.20, "code_quality": 0.10},
        extra_components={"correctness": correctness},
        extra_metrics=metrics,
    )
