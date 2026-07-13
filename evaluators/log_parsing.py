"""Log parsing scoring: template accuracy + token-level F1.

Score = 0.5 * exact template accuracy + 0.5 * mean token F1, comparing the
predicted template for each line to the ground truth after normalization
(lowercase, collapsed whitespace, unified <*> placeholders).
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from core.schemas import LogParsingResult

from .base import EvalResult

_PLACEHOLDER = re.compile(r"<[^<>\s]{0,16}>|\{\}|\{\w+\}")


def _normalize(template: str) -> str:
    normalized = _PLACEHOLDER.sub("<*>", template)
    normalized = re.sub(r"\s+", " ", normalized.strip().lower())
    # Loghub ground truth keeps constant fragments inside variable tokens
    # ("blk_<*>", "/<*>:<*>"); models usually wildcard the whole token.
    # Collapse any token containing a placeholder to <*> on both sides so
    # placeholder style doesn't decide the score — structure does.
    tokens = ["<*>" if "<*>" in token else token for token in normalized.split()]
    return " ".join(tokens)


def _token_f1(predicted: str, truth: str) -> float:
    pred_tokens = Counter(predicted.split())
    truth_tokens = Counter(truth.split())
    if not pred_tokens and not truth_tokens:
        return 1.0
    common = sum((pred_tokens & truth_tokens).values())
    total = sum(pred_tokens.values()) + sum(truth_tokens.values())
    if total == 0:
        return 0.0
    return 2 * common / total


def evaluate(case: dict[str, Any], result: LogParsingResult) -> EvalResult:
    truths = [_normalize(t) for t in case["templates"]]
    predictions = [_normalize(t) for t in result.templates]

    exact_matches = 0
    f1_scores: list[float] = []
    for i, truth in enumerate(truths):
        predicted = predictions[i] if i < len(predictions) else ""
        if predicted == truth:
            exact_matches += 1
        f1_scores.append(_token_f1(predicted, truth))

    accuracy = exact_matches / len(truths)
    mean_f1 = sum(f1_scores) / len(f1_scores)
    return EvalResult(
        score=0.5 * accuracy + 0.5 * mean_f1,
        metrics={"template_accuracy": accuracy, "token_f1": mean_f1},
    )
