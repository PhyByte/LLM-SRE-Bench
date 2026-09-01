"""code_review scoring: did the review catch the defects that matter?

Score = 0.65 * defect recall + 0.20 * precision + 0.15 * localization

Each case ships a snippet with seeded defects and, per defect, a set of
keyword alternatives. A finding matches a defect when its text contains any of
them, so the model is free to word the review however it likes but has to name
the actual mechanism ("expired entries are still served", "no backoff between
retries") rather than gesture at the line.

Precision has a two-finding allowance: a reviewer noting a couple of extra
nits is not penalized, but padding the report with speculation is. An empty
review scores zero on every component — "found nothing" is not precision.
Nothing is executed for this category.
"""

from __future__ import annotations

import re
from typing import Any

from core.schemas import CodeReviewResult

from .base import EvalResult, clamp01

# Extra findings tolerated before precision starts to cost anything.
EXTRA_FINDING_ALLOWANCE = 2

# A reported line this far from the seeded one still counts as located.
LINE_TOLERANCE = 2

_NON_WORD = re.compile(r"[^a-z0-9]+")


def normalize(text: str) -> str:
    """Lowercase, punctuation-free text so keyword matching is wording-agnostic."""
    return _NON_WORD.sub(" ", text.lower()).strip()


def _finding_text(finding: Any) -> str:
    parts = [finding.issue]
    if getattr(finding, "severity", None):
        parts.append(str(finding.severity))
    return normalize(" ".join(p for p in parts if p))


def keyword_matches(keyword: str, text: str) -> bool:
    """Match a keyword at a word boundary, allowing a longer word to follow.

    "leak" matches "leaking" and "never evict" matches "never evicted", but
    "ms" no longer matches inside "problems" — plain substring matching made
    short keywords fire on unrelated findings.
    """
    keyword = normalize(keyword)
    if not keyword:
        return False
    return re.search(r"\b" + re.escape(keyword), text) is not None


def match_findings(findings: list[Any], defects: list[dict]) -> dict[int, int]:
    """Greedily assign findings to defects. Returns {defect index: finding index}."""
    texts = [_finding_text(finding) for finding in findings]
    assigned: dict[int, int] = {}
    used: set[int] = set()
    for defect_index, defect in enumerate(defects):
        keywords = defect.get("keywords_any", [])
        for finding_index, text in enumerate(texts):
            if finding_index in used:
                continue
            if any(keyword_matches(keyword, text) for keyword in keywords):
                assigned[defect_index] = finding_index
                used.add(finding_index)
                break
    return assigned


def evaluate(case: dict[str, Any], result: CodeReviewResult) -> EvalResult:
    defects = case.get("defects", [])
    findings = result.findings
    if not defects:
        return EvalResult(score=0.0, metrics={"error": "case_has_no_defects"})

    assigned = match_findings(findings, defects)
    recall = len(assigned) / len(defects)

    if findings:
        unmatched = max(len(findings) - len(assigned) - EXTRA_FINDING_ALLOWANCE, 0)
        precision = clamp01(1.0 - unmatched / len(defects))
    else:
        # An empty review is not a precise one. Without this, "report nothing"
        # would bank the full precision component for saying nothing at all.
        precision = 0.0

    located = 0
    for defect_index, finding_index in assigned.items():
        reported = findings[finding_index].line
        if reported is not None and abs(reported - defects[defect_index]["line"]) <= LINE_TOLERANCE:
            located += 1
    localization = located / len(assigned) if assigned else 0.0

    # Reported for analysis only: agreeing on severity is not part of the score,
    # since reasonable reviewers disagree about it.
    severity_agreement = 0
    for defect_index, finding_index in assigned.items():
        expected = str(defects[defect_index].get("severity", "")).lower()
        actual = str(findings[finding_index].severity or "").lower()
        if expected and expected == actual:
            severity_agreement += 1

    score = 0.65 * recall + 0.20 * precision + 0.15 * localization
    return EvalResult(
        score=clamp01(score),
        metrics={
            "recall": recall,
            "precision": precision,
            "localization": localization,
            "defects_found": len(assigned),
            "defects_total": len(defects),
            "findings_reported": len(findings),
            "severity_agreement": (
                severity_agreement / len(assigned) if assigned else 0.0
            ),
            "missed": ",".join(
                defect["id"]
                for index, defect in enumerate(defects)
                if index not in assigned
            ),
        },
    )
