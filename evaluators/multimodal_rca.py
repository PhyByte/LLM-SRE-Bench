"""Multi-modal RCA scoring.

Four components, weighted:

  0.40 culprit localization  exact match on the service (normalized), else 0
  0.25 fault-type accuracy   exact match against the closed vocabulary
  0.25 modality grounding    F1 of cited modalities vs the ones measured to
                             carry signal for this incident
  0.10 evidence quality      keyword recall over the ground-truth markers

Modality grounding is the component that makes this category multi-modal rather
than "root cause with extra text". Each case records which modalities actually
localize its fault — measured by the dataset builder's screening pass, not
asserted — so citing a modality that shows nothing costs precision. Answering
"cite all three" therefore caps grounding well below 1.0, and a model that reads
the CPU series for a CPU fault beats one that name-drops every source.

Localization is deliberately all-or-nothing: naming the wrong service is the
failure that matters in an incident, and partial credit for "close" would reward
plausible-sounding misdirection.
"""

from __future__ import annotations

import re
from typing import Any

from core.schemas import MultiModalRCAResult

from .base import EvalResult, clamp01

WEIGHT_CULPRIT = 0.40
WEIGHT_FAULT_TYPE = 0.25
WEIGHT_GROUNDING = 0.25
WEIGHT_EVIDENCE = 0.10


def _normalize(name: str) -> str:
    """Fold the harmless ways a model may render a service name.

    'Frontend', 'frontend-service' and 'frontend' should all match; a genuinely
    different service still won't.
    """
    lowered = re.sub(r"[^a-z0-9]+", "", name.lower())
    for suffix in ("service", "svc"):
        if lowered.endswith(suffix) and len(lowered) > len(suffix):
            lowered = lowered[: -len(suffix)]
    return lowered


def _f1(predicted: set[str], expected: set[str]) -> float:
    if not expected:
        # No modality carries signal (the healthy case): citing nothing is
        # correct, and every citation is a false positive.
        return 1.0 if not predicted else 0.0
    if not predicted:
        return 0.0
    hits = len(predicted & expected)
    if not hits:
        return 0.0
    precision = hits / len(predicted)
    recall = hits / len(expected)
    return 2 * precision * recall / (precision + recall)


def evaluate(case: dict[str, Any], result: MultiModalRCAResult) -> EvalResult:
    truth = case["ground_truth"]

    culprit_ok = _normalize(result.culprit_service) == _normalize(truth["culprit_service"])
    fault_ok = result.fault_type.strip().lower() == truth["fault_type"].strip().lower()

    cited = {e.modality for e in result.evidence}
    grounding = _f1(cited, set(truth["informative_modalities"]))

    keywords = truth.get("evidence_keywords", [])
    haystack = " ".join(
        [result.culprit_service, result.fault_type, result.summary]
        + [e.observation for e in result.evidence]
    ).lower()
    evidence_recall = (
        sum(1 for kw in keywords if kw.lower() in haystack) / len(keywords) if keywords else 1.0
    )

    score = (
        WEIGHT_CULPRIT * float(culprit_ok)
        + WEIGHT_FAULT_TYPE * float(fault_ok)
        + WEIGHT_GROUNDING * grounding
        + WEIGHT_EVIDENCE * evidence_recall
    )

    return EvalResult(
        score=clamp01(score),
        metrics={
            "culprit_correct": float(culprit_ok),
            "fault_type_correct": float(fault_ok),
            "modality_grounding_f1": grounding,
            "evidence_recall": evidence_recall,
        },
    )
