"""Root cause & summarization scoring.

Default (reference-based): a mix of self-contained ROUGE metrics and keyword
recall against the reference answer:

  score = 0.4 * ROUGE-L F1(summary)   — summary quality
        + 0.3 * ROUGE-1 F1(root cause) — root cause overlap
        + 0.3 * keyword recall         — did it name the important entities

When a judge callable is supplied (LLM-as-judge, configured via judge_model),
the judge's 0-10 grade replaces the blend:

  score = 0.7 * judge + 0.3 * reference blend
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, Callable, Optional

from core.schemas import JudgeResult, RootCauseResult
from core.utils import extract_json

from .base import EvalResult, clamp01

_TOKEN = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def _rouge_1_f1(candidate: str, reference: str) -> float:
    cand = Counter(_tokens(candidate))
    ref = Counter(_tokens(reference))
    if not cand or not ref:
        return 0.0
    overlap = sum((cand & ref).values())
    precision = overlap / sum(cand.values())
    recall = overlap / sum(ref.values())
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _lcs_length(a: list[str], b: list[str]) -> int:
    if not a or not b:
        return 0
    previous = [0] * (len(b) + 1)
    for token_a in a:
        current = [0] * (len(b) + 1)
        for j, token_b in enumerate(b, start=1):
            if token_a == token_b:
                current[j] = previous[j - 1] + 1
            else:
                current[j] = max(previous[j], current[j - 1])
        previous = current
    return previous[-1]


def _rouge_l_f1(candidate: str, reference: str) -> float:
    cand, ref = _tokens(candidate), _tokens(reference)
    if not cand or not ref:
        return 0.0
    lcs = _lcs_length(cand, ref)
    precision = lcs / len(cand)
    recall = lcs / len(ref)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def evaluate(
    case: dict[str, Any],
    result: RootCauseResult,
    judge: Optional[Callable[[str, str], str]] = None,
) -> EvalResult:
    rouge_l = _rouge_l_f1(result.summary, case["reference_summary"])
    rouge_1 = _rouge_1_f1(result.root_cause, case["reference_root_cause"])

    keywords = case.get("keywords", [])
    candidate_text = f"{result.root_cause} {result.summary}".lower()
    keyword_recall = (
        sum(1 for kw in keywords if kw.lower() in candidate_text) / len(keywords)
        if keywords
        else rouge_1
    )

    reference_blend = clamp01(0.4 * rouge_l + 0.3 * rouge_1 + 0.3 * keyword_recall)
    metrics = {
        "rouge_l_summary": rouge_l,
        "rouge_1_root_cause": rouge_1,
        "keyword_recall": keyword_recall,
    }

    if judge is None:
        return EvalResult(score=reference_blend, metrics=metrics)

    try:
        judge_text = judge(result.root_cause, result.summary)
        judge_result = JudgeResult.model_validate(extract_json(judge_text))
        judge_score = clamp01(judge_result.score / 10.0)
        metrics["judge_score"] = judge_score
        return EvalResult(score=clamp01(0.7 * judge_score + 0.3 * reference_blend), metrics=metrics)
    except Exception:
        # Judge unavailable or returned garbage: fall back to reference metrics.
        metrics["judge_score"] = -1.0
        return EvalResult(score=reference_blend, metrics=metrics)
