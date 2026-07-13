"""Efficiency & consistency scoring, derived from the task-category runs.

  score = 0.4 * latency score     max(0, 1 - avg_latency / 20s)
        + 0.3 * token score       max(0, 1 - avg_total_tokens / 4000)
        + 0.3 * consistency       max(0, 1 - mean per-case score stddev / 25)

Latency and token budgets are deliberately generous defaults for single
log-analysis calls; adjust the constants if your workload differs. Cached
responses keep their originally measured latency, so re-runs stay comparable.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from typing import TYPE_CHECKING

from .base import EvalResult, clamp01

if TYPE_CHECKING:
    from core.runner import RunRecord

LATENCY_BUDGET_S = 20.0
TOKEN_BUDGET = 4000.0
STDDEV_BUDGET = 25.0  # score points (0-100 scale)


def evaluate(records: list["RunRecord"]) -> EvalResult:
    valid = [r for r in records if r.error is None]
    if not valid:
        return EvalResult(score=0.0, metrics={})

    latencies = [r.latency_s for r in valid]
    avg_latency = statistics.fmean(latencies)
    latency_score = clamp01(1 - avg_latency / LATENCY_BUDGET_S)

    token_counts = [r.total_tokens for r in valid if r.total_tokens is not None]
    if token_counts:
        avg_tokens = statistics.fmean(token_counts)
        token_score = clamp01(1 - avg_tokens / TOKEN_BUDGET)
    else:
        avg_tokens = -1.0
        token_score = 0.5  # provider reports no usage: neutral

    by_case: dict[tuple[str, str], list[float]] = defaultdict(list)
    for r in valid:
        by_case[(r.category, r.case_id)].append(r.score * 100)
    stddevs = [statistics.pstdev(scores) for scores in by_case.values() if len(scores) > 1]
    mean_stddev = statistics.fmean(stddevs) if stddevs else 0.0
    consistency_score = clamp01(1 - mean_stddev / STDDEV_BUDGET)

    return EvalResult(
        score=0.4 * latency_score + 0.3 * token_score + 0.3 * consistency_score,
        metrics={
            "avg_latency_s": avg_latency,
            "avg_total_tokens": avg_tokens,
            "score_stddev": mean_stddev,
            "latency_score": latency_score,
            "token_score": token_score,
            "consistency_score": consistency_score,
        },
    )
