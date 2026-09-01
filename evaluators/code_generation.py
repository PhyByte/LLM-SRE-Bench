"""Code generation scoring: correctness, compilation, runtime, and code size.

Score = 0.60 * correctness + 0.20 * compilation + 0.10 * runtime_efficiency + 0.10 * code_quality

The sandbox, the language executors and the test-runner generation all live in
``evaluators/code_exec.py``; this module only turns an execution result into a
score. The other code-writing categories (``code_debugging``,
``code_refactoring``, ``code_efficiency``) score the same execution differently.
"""

from __future__ import annotations

from typing import Any

from core.schemas import CodeGenerationResult

from .base import EvalResult
from .code_exec import run_case, score_execution


def evaluate(case: dict[str, Any], result: CodeGenerationResult) -> EvalResult:
    """Evaluate generated code against hidden test cases.

    Scoring:
    - 60% correctness (tests passed)
    - 20% compilation success
    - 10% runtime efficiency (compared to reasonable baseline)
    - 10% code quality (size penalty for extremely verbose code)
    """
    outcome = run_case(case, result.code)
    if outcome.failure is not None:
        return EvalResult(score=0.0, metrics=outcome.failure)

    return score_execution(
        outcome,
        weights={
            "correctness": 0.60,
            "compiled": 0.20,
            "runtime_efficiency": 0.10,
            "code_quality": 0.10,
        },
    )
