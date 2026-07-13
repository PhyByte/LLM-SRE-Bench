"""Common evaluation result type and category dispatch."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from pydantic import BaseModel


@dataclass
class EvalResult:
    """Score is normalized to [0, 1]; metrics hold the per-category detail."""

    score: float
    metrics: dict[str, float] = field(default_factory=dict)


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def get_evaluator(category: str) -> Callable[[dict[str, Any], BaseModel], EvalResult]:
    from . import (
        anomaly_detection,
        log_parsing,
        metrics_timeseries,
        pattern_correlation,
        root_cause,
    )

    evaluators = {
        "log_parsing": log_parsing.evaluate,
        "anomaly_detection": anomaly_detection.evaluate,
        "pattern_correlation": pattern_correlation.evaluate,
        "metrics_timeseries": metrics_timeseries.evaluate,
        "root_cause": root_cause.evaluate,
    }
    return evaluators[category]
