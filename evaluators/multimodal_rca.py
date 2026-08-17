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

Three verdicts are possible, and telling them apart is most of the task:
a service name, "none" (the system is healthy), and "unknown" (something is
wrong but this evidence does not show what). The last of these is scored on
cases drawn from the faults the dataset builder's signal gate rejected — real
injected faults whose culprit is buried in every channel. They measure whether a
model knows when it cannot tell, which is the failure mode that makes RCA
tooling dangerous: an "all clear" or a confident wrong service both read as
answers, and both send someone to the wrong place at 3am. Grounding is not
scored on a correct abstention, since a case whose premise is that no modality
localizes the fault has no correct set of modalities to cite.
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
    answered = _normalize(result.culprit_service)

    # "Insufficient evidence" cases: a fault was injected, but the screen found
    # it buried in every channel. Two answers are acceptable — "unknown", which
    # is the calibrated response, and the true culprit, because the screen is a
    # crude ranking and a model that genuinely localizes the fault has not made
    # a mistake. What is penalized is the third option: confidently naming some
    # other service, which is the behaviour that makes RCA tooling dangerous.
    abstention = "true_culprit" in truth
    if abstention:
        culprit_ok = answered in {
            _normalize(truth["culprit_service"]),
            _normalize(truth["true_culprit"]),
        }
        # Fault type follows whichever verdict was given, so a correct
        # localization isn't docked for naming the fault it just identified.
        acceptable_types = {truth["fault_type"].strip().lower()}
        if answered == _normalize(truth["true_culprit"]):
            acceptable_types.add(truth["true_fault_type"].strip().lower())
        fault_ok = result.fault_type.strip().lower() in acceptable_types
    else:
        culprit_ok = answered == _normalize(truth["culprit_service"])
        fault_ok = result.fault_type.strip().lower() == truth["fault_type"].strip().lower()

    cited = {e.modality for e in result.evidence}
    if not abstention:
        grounding = _f1(cited, set(truth["informative_modalities"]))
    elif answered == _normalize(truth["true_culprit"]):
        # It found the culprit the screen could not, so its citations are
        # evidence of that, not false positives against an empty expectation.
        grounding = 1.0 if cited else 0.0
    elif culprit_ok:
        # A correct "unknown" is not graded on grounding. The premise of these
        # cases is that no modality localizes the fault, so there is no correct
        # set to cite: scoring it would mean docking a model 0.25 for describing
        # what it saw while abstaining, which is exactly the behaviour we want.
        # The weight is conceded rather than redistributed so a case's ceiling
        # stays comparable with the solvable ones.
        grounding = 1.0
    else:
        # Named some other service. Nothing it cites can ground a culprit the
        # evidence does not support, and staying silent shouldn't earn the
        # empty-expectation full marks that _f1 would hand back.
        grounding = 0.0

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

    metrics = {
        "culprit_correct": float(culprit_ok),
        "fault_type_correct": float(fault_ok),
        "modality_grounding_f1": grounding,
        "evidence_recall": evidence_recall,
    }
    if abstention:
        # Tracked separately so the reports can show how often a model invented
        # a culprit rather than admitting the evidence was insufficient.
        metrics["abstention_case"] = 1.0
        metrics["confidently_wrong"] = float(not culprit_ok)

    return EvalResult(score=clamp01(score), metrics=metrics)
