"""Shared plumbing for building the developer-track challenge datasets.

Every family is defined once, in Python, with:

- one spec per language (the model-facing task description),
- the exact signature the model must implement,
- an ``io`` type declaration the test harness renders literals from,
- inputs plus a Python reference implementation.

Expected outputs are *computed* from the reference implementation rather than
typed by hand, so a dataset can't ship an answer key that disagrees with its own
spec. ``scripts/build_code_challenges.py --validate`` then runs a reference
solution in each target language through the real executors, which is what
catches a spec that only makes sense in Python.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

LANGUAGES = ("python", "typescript", "go", "rust")

# Appended to every code_efficiency spec. The timing rule is part of the task,
# so the model is told about it rather than being ambushed by the budget.
BUDGET_NOTE = """
This case is timed. The graders run your function once on a 200,000-element
input and compare the elapsed time against a budget; the obvious quadratic
solution is correct but far too slow to score. Aim for a single pass (or a
sort), not nested scans over the input.
"""


@dataclass
class Family:
    """One task, expressed once and emitted for every language."""

    name: str
    skill: str
    difficulty: str
    io: dict[str, Any]
    spec: str
    # Per-language: the required signature, plus any language-specific note
    # appended to the shared spec (ownership, naming conventions, ...).
    signatures: dict[str, str]
    notes: dict[str, str] = field(default_factory=dict)
    inputs: list[Any] = field(default_factory=list)
    reference: Callable[..., Any] | None = None
    # Reference solutions per language, used only by --validate.
    solutions: dict[str, str] = field(default_factory=dict)
    extras: dict[str, Any] = field(default_factory=dict)
    # Per-language extras, merged after `extras` (budgets, buggy code, ...).
    lang_extras: dict[str, dict[str, Any]] = field(default_factory=dict)

    def arg_count(self) -> int:
        return len(self.io.get("args", []))

    def test_cases(self) -> list[dict[str, Any]]:
        if self.reference is None:
            return []
        cases = []
        for value in self.inputs:
            args = value if self.arg_count() > 1 else [value]
            cases.append({"input": value, "expected": self.reference(*args)})
        return cases

    def case_id(self, language: str) -> str:
        return f"{self.name}_{language}"

    def to_cases(self) -> list[dict[str, Any]]:
        tests = self.test_cases()
        cases = []
        for language in LANGUAGES:
            spec = self.spec.strip()
            note = self.notes.get(language)
            if note:
                spec = f"{spec}\n\n{note.strip()}"
            case: dict[str, Any] = {
                "id": self.case_id(language),
                "language": language,
                "difficulty": self.difficulty,
                "task_family": self.name,
                "skill": self.skill,
                "spec": spec,
                "signature": self.signatures[language],
                "io": self.io,
            }
            case.update(self.extras)
            case.update(self.lang_extras.get(language, {}))
            if tests:
                case["test_cases"] = tests
            cases.append(case)
        return cases


def dedent_code(code: str) -> str:
    """Snippets are written as indented literals; ship them flush-left."""
    lines = code.strip("\n").rstrip().split("\n")
    indents = [len(l) - len(l.lstrip()) for l in lines if l.strip()]
    cut = min(indents) if indents else 0
    return "\n".join(l[cut:] if l.strip() else "" for l in lines)
