"""Anomaly detection scoring: precision / recall / F1 over per-line labels."""

from __future__ import annotations

from typing import Any

from sklearn.metrics import precision_recall_fscore_support

from core.schemas import AnomalyDetectionResult

from .base import EvalResult


def evaluate(case: dict[str, Any], result: AnomalyDetectionResult) -> EvalResult:
    n_lines = len(case["logs"])
    truth_set = set(case["anomalous_indices"])
    predicted_set = {i for i in result.anomalous_indices if 0 <= i < n_lines}

    y_true = [1 if i in truth_set else 0 for i in range(n_lines)]
    y_pred = [1 if i in predicted_set else 0 for i in range(n_lines)]

    if not truth_set:
        # No anomalies to find: perfect if the model also predicted none.
        value = 1.0 if not predicted_set else 0.0
        return EvalResult(score=value, metrics={"precision": value, "recall": value, "f1": value})

    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="binary", zero_division=0
    )
    return EvalResult(
        score=float(f1),
        metrics={"precision": float(precision), "recall": float(recall), "f1": float(f1)},
    )
