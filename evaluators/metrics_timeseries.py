"""Time-series anomaly scoring: point-wise P/R/F1 with +/-1 index tolerance."""

from __future__ import annotations

from typing import Any

from core.schemas import TimeSeriesResult

from .base import EvalResult

_TOLERANCE = 1


def evaluate(case: dict[str, Any], result: TimeSeriesResult) -> EvalResult:
    n = len(case["values"])
    truth = sorted(set(case["anomalous_indices"]))
    predicted = sorted({i for i in result.anomalous_indices if 0 <= i < n})

    if not truth:
        value = 1.0 if not predicted else 0.0
        return EvalResult(score=value, metrics={"precision": value, "recall": value, "f1": value})

    unmatched_truth = set(truth)
    true_positives = 0
    for p in predicted:
        match = next((t for t in sorted(unmatched_truth) if abs(t - p) <= _TOLERANCE), None)
        if match is not None:
            unmatched_truth.discard(match)
            true_positives += 1

    precision = true_positives / len(predicted) if predicted else 0.0
    recall = true_positives / len(truth)
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    return EvalResult(score=f1, metrics={"precision": precision, "recall": recall, "f1": f1})
