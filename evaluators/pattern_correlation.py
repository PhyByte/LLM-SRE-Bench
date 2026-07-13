"""Pattern & correlation scoring.

Pattern coverage: an expected pattern counts as found when at least half of
its keywords appear in a single predicted pattern's name + description.
Correlation accuracy: an expected (cause -> effect) pair counts as found when
some predicted correlation's cause text matches a keyword of the expected
cause pattern and its effect text matches a keyword of the expected effect
pattern.

Score = 0.6 * pattern coverage + 0.4 * correlation accuracy
(pattern coverage only, when the case defines no correlations).
"""

from __future__ import annotations

import math
from typing import Any

from core.schemas import PatternCorrelationResult

from .base import EvalResult


def _keyword_hits(keywords: list[str], text: str) -> int:
    lowered = text.lower()
    return sum(1 for kw in keywords if kw.lower() in lowered)


def _pattern_matches(expected: dict[str, Any], text: str) -> bool:
    keywords = expected["keywords"]
    required = max(1, math.ceil(len(keywords) / 2))
    return _keyword_hits(keywords, text) >= required


def evaluate(case: dict[str, Any], result: PatternCorrelationResult) -> EvalResult:
    predicted_texts = [f"{p.name} {p.description}" for p in result.patterns]

    expected_patterns = case["expected_patterns"]
    found = sum(
        1
        for expected in expected_patterns
        if any(_pattern_matches(expected, text) for text in predicted_texts)
    )
    coverage = found / len(expected_patterns)

    expected_correlations = case.get("expected_correlations", [])
    if not expected_correlations:
        return EvalResult(score=coverage, metrics={"pattern_coverage": coverage})

    keywords_by_name = {p["name"]: p["keywords"] for p in expected_patterns}
    matched_correlations = 0
    for expected in expected_correlations:
        cause_keywords = keywords_by_name.get(expected["cause"], [expected["cause"]])
        effect_keywords = keywords_by_name.get(expected["effect"], [expected["effect"]])
        for predicted in result.correlations:
            if _keyword_hits(cause_keywords, predicted.cause) >= 1 and _keyword_hits(
                effect_keywords, predicted.effect
            ) >= 1:
                matched_correlations += 1
                break
    correlation_accuracy = matched_correlations / len(expected_correlations)

    return EvalResult(
        score=0.6 * coverage + 0.4 * correlation_accuracy,
        metrics={
            "pattern_coverage": coverage,
            "correlation_accuracy": correlation_accuracy,
        },
    )
