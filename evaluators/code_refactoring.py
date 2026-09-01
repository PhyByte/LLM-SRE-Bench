"""code_refactoring scoring: behavior preserved, shape improved.

Score = 0.40 * correctness + 0.10 * compilation + 0.50 * (structure x correctness)

The hidden tests are the same ones the original code already passes, so
correctness here means "you did not break it" — worth real credit, but it
cannot be the bulk of the score, or handing the code back unchanged would rank
close to an actual refactor. The structure component is what
separates a real refactor from a reformat: a small set of per-case rules that
check the branch chain is gone, the table or loop is there, and the function
got shorter. Rules are deliberately loose and alternative-friendly — a Go
``switch`` and a Go ``map`` both satisfy the severity_rank rule — so several
idiomatic refactors score full marks and only "left it as it was" fails.
"""

from __future__ import annotations

import re
from typing import Any

from core.schemas import CodeGenerationResult

from .base import EvalResult, clamp01
from .code_exec import run_case, score_execution


def _strip_comments(code: str) -> str:
    """Rules describe code, not prose about code."""
    without_block = re.sub(r"/\*.*?\*/", "", code, flags=re.DOTALL)
    without_docstrings = re.sub(r'"""[\s\S]*?"""', "", without_block)
    lines = []
    for line in without_docstrings.split("\n"):
        line = re.sub(r"(#|//).*$", "", line)
        lines.append(line)
    return "\n".join(lines)


def structure_report(code: str, structure: dict[str, Any]) -> list[dict[str, Any]]:
    """Evaluate each structural rule, returning one entry per rule."""
    cleaned = _strip_comments(code)
    results: list[dict[str, Any]] = []

    for rule in structure.get("max_matches", []):
        count = len(re.findall(rule["pattern"], cleaned))
        results.append(
            {
                "rule": f"at most {rule['max']} x /{rule['pattern']}/",
                "reason": rule.get("reason", ""),
                "passed": count <= rule["max"],
                "observed": count,
            }
        )

    for rule in structure.get("require_any", []):
        hit = any(re.search(pattern, cleaned) for pattern in rule["patterns"])
        results.append(
            {
                "rule": f"any of {rule['patterns']}",
                "reason": rule.get("reason", ""),
                "passed": hit,
            }
        )

    for rule in structure.get("forbid", []):
        results.append(
            {
                "rule": f"none of /{rule['pattern']}/",
                "reason": rule.get("reason", ""),
                "passed": re.search(rule["pattern"], cleaned) is None,
            }
        )

    max_lines = structure.get("max_lines")
    if max_lines:
        count = len([line for line in cleaned.split("\n") if line.strip()])
        results.append(
            {
                "rule": f"at most {max_lines} non-blank lines",
                "reason": "a refactor should not be longer than what it replaced",
                "passed": count <= max_lines,
                "observed": count,
            }
        )
    return results


def check_structure(code: str, structure: dict[str, Any]) -> float:
    """Fraction of the structural rules the code satisfies."""
    report = structure_report(code, structure)
    if not report:
        return 1.0
    return sum(1 for rule in report if rule["passed"]) / len(report)


def evaluate(case: dict[str, Any], result: CodeGenerationResult) -> EvalResult:
    outcome = run_case(case, result.code)
    if outcome.failure is not None:
        return EvalResult(score=0.0, metrics=outcome.failure)

    structure = case.get("structure", {})
    report = structure_report(result.code, structure)
    rules_satisfied = clamp01(check_structure(result.code, structure))

    # Structural credit is scaled by correctness. Otherwise a stub that
    # implements nothing scores well on "no branch chain, few lines" — the
    # rules describe the shape of *working* code, not of any short function.
    structure_score = rules_satisfied * outcome.correctness

    metrics: dict[str, Any] = {
        "rules_total": len(report),
        "rules_passed": sum(1 for rule in report if rule["passed"]),
        "rules_satisfied": rules_satisfied,
    }
    if result.code.strip() == case.get("original_code", "").strip():
        metrics["unchanged_code"] = 1.0

    return score_execution(
        outcome,
        weights={"correctness": 0.40, "compiled": 0.10, "structure": 0.50},
        extra_components={"structure": structure_score},
        extra_metrics=metrics,
    )
