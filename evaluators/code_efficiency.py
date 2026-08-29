"""code_efficiency scoring: correct first, then fast enough.

Score = 0.45 * correctness + 0.15 * compilation + 0.35 * (perf x correctness) + 0.05 * code_quality

``perf`` compares the in-language timing of the workload call against the
case's per-language budget: full credit at or under the budget, then a decay
that reaches zero at 8x the budget. A quadratic solution passes the small
correctness tests and compiles, so it can still score in the low 60s of the
correctness+compilation half — it simply cannot earn the perf third.
"""

from __future__ import annotations

from typing import Any

from core.schemas import CodeGenerationResult

from .base import EvalResult, clamp01
from .code_exec import ExecutionOutcome, run_case, score_execution

# Elapsed time, as a multiple of the budget, at which perf credit hits zero.
PERF_ZERO_AT = 8.0


def perf_score(elapsed_ms: float | None, budget_ms: float | None) -> float:
    """1.0 within budget, decaying to 0 at PERF_ZERO_AT times the budget."""
    if not budget_ms or budget_ms <= 0:
        return 0.0
    if elapsed_ms is None:
        # No timing means the workload never completed (timeout, crash, or a
        # runner that died before printing) — no credit.
        return 0.0
    if elapsed_ms <= budget_ms:
        return 1.0
    over = elapsed_ms / budget_ms
    return clamp01((PERF_ZERO_AT - over) / (PERF_ZERO_AT - 1.0))


def evaluate(case: dict[str, Any], result: CodeGenerationResult) -> EvalResult:
    outcome: ExecutionOutcome = run_case(case, result.code)
    if outcome.failure is not None:
        return EvalResult(score=0.0, metrics=outcome.failure)

    budget = case.get("time_budget_ms")
    # Speed only counts for an answer that is right: returning a constant is
    # extremely fast and must not collect the perf third for it.
    raw_perf = perf_score(outcome.elapsed_ms, budget)
    performance = raw_perf * outcome.correctness
    return score_execution(
        outcome,
        weights={
            "correctness": 0.45,
            "compiled": 0.15,
            "perf": 0.35,
            "code_quality": 0.05,
        },
        extra_components={"perf": performance},
        extra_metrics={
            "time_budget_ms": budget,
            "within_budget": 1.0 if raw_perf >= 1.0 else 0.0,
        },
    )
