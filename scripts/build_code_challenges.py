#!/usr/bin/env python3
"""Build (and validate) the developer-track challenge datasets.

    python scripts/build_code_challenges.py            # write datasets/data/*.json
    python scripts/build_code_challenges.py --validate # also run every reference
                                                       # solution through the real
                                                       # executors

Validation is the point of this script existing. Expected outputs come from a
Python reference implementation, and ``--validate`` then compiles and runs a
reference solution *in each target language* against those same expectations, so
a spec that only holds in Python, a mis-rendered literal, or a bad answer key
fails here rather than silently costing every model points.

It additionally asserts the properties each category depends on:

- code_debugging: the shipped buggy code must actually fail its own tests.
- code_refactoring: the shipped original must pass the tests (behavior is
  preserved by definition) and must *fail* the structural rules the clean
  solution satisfies.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from challenges import debugging, efficiency, generation, refactoring, review  # noqa: E402

DATA_DIR = ROOT / "datasets" / "data"

# The six original code_generation families predate this builder and stay in the
# JSON as hand-written cases; they only gain a skill tag here.
LEGACY_SKILLS = {
    "slugify": "text_processing",
    "interval_merge": "algorithms",
    "rate_limiter": "state_management",
    "config_overlay": "recursion",
    "lru_cache": "data_structures",
    "log_parser": "parsing",
}


def build_code_generation() -> list[dict]:
    existing = json.loads((DATA_DIR / "code_generation.json").read_text(encoding="utf-8"))
    kept = []
    for case in existing:
        family = case.get("task_family")
        if family not in LEGACY_SKILLS:
            continue  # regenerated below
        case["skill"] = LEGACY_SKILLS[family]
        kept.append(case)
    for family in generation.FAMILIES:
        kept.extend(family.to_cases())
    return kept


def build_code_debugging() -> list[dict]:
    """Record, per case, which tests the shipped buggy version actually fails.

    The evaluator scores those separately from the rest, so this cannot be a
    hand-maintained list: it is measured by running the buggy code through the
    real executor for that language. Needs the toolchains installed; without
    them the field is left off and the evaluator falls back to the plain pass
    rate.
    """
    from evaluators.code_exec import failed_test_indices, run_case

    cases = [c for f in debugging.FAMILIES for c in f.to_cases()]
    for case in cases:
        outcome = run_case(case, case["buggy_code"])
        if outcome.failure is not None or not outcome.compiled:
            print(f"  ! {case['id']}: could not run the buggy code, skipping "
                  f"regression_indices ({outcome.failure or 'compile error'})")
            continue
        indices = sorted(failed_test_indices(outcome.errors))
        if not indices and outcome.passed == 0:
            # Nothing was reported per test and nothing passed: the process
            # died before it could report (a Rust panic takes the whole binary
            # with it), so the bug breaks every test.
            indices = list(range(len(case["test_cases"])))
        if not indices:
            raise ValueError(
                f"{case['id']}: the buggy code passes every test — the seeded "
                "bug is not observable, so this case cannot be scored"
            )
        case["regression_indices"] = indices
    return cases


def build_all() -> dict[str, list[dict]]:
    return {
        "code_generation": build_code_generation(),
        "code_efficiency": [c for f in efficiency.FAMILIES for c in f.to_cases()],
        "code_debugging": build_code_debugging(),
        "code_refactoring": [c for f in refactoring.FAMILIES for c in f.to_cases()],
        "code_review": review.build_cases(),
    }


def write(datasets: dict[str, list[dict]]) -> None:
    for name, cases in datasets.items():
        path = DATA_DIR / f"{name}.json"
        path.write_text(json.dumps(cases, indent=2) + "\n", encoding="utf-8")
        by_language: dict[str, int] = {}
        for case in cases:
            by_language[case["language"]] = by_language.get(case["language"], 0) + 1
        spread = ", ".join(f"{k}={v}" for k, v in sorted(by_language.items()))
        print(f"wrote {path.relative_to(ROOT)}: {len(cases)} cases ({spread})")


def validate() -> int:
    """Run every reference solution through the real executors."""
    from evaluators.code_exec import run_case
    from evaluators.code_refactoring import check_structure

    failures = 0

    def report(label: str, ok: bool, detail: str = "") -> None:
        nonlocal failures
        if not ok:
            failures += 1
        print(f"{'  ok  ' if ok else ' FAIL '} {label}{(' — ' + detail) if detail else ''}")

    families = [
        ("code_generation", generation.FAMILIES),
        ("code_efficiency", efficiency.FAMILIES),
        ("code_debugging", debugging.FAMILIES),
        ("code_refactoring", refactoring.FAMILIES),
    ]
    # Validate the cases as they are on disk, so --check also covers fields the
    # writer measured (code_debugging's regression_indices).
    stored = {
        category: {c["id"]: c for c in json.loads((DATA_DIR / f"{category}.json").read_text())}
        for category, _ in families
    }
    for category, family_list in families:
        for family in family_list:
            for case in family.to_cases():
                case = stored[category].get(case["id"], case)
                solution = family.solutions[case["language"]]
                outcome = run_case(case, solution)
                ok = outcome.failure is None and outcome.failed == 0 and outcome.passed > 0
                detail = ""
                if not ok:
                    detail = str(outcome.failure or outcome.errors[:1])[:300]
                elif outcome.elapsed_ms is not None:
                    detail = (
                        f"workload {outcome.elapsed_ms:.1f}ms of "
                        f"{case['time_budget_ms']}ms budget"
                    )
                report(f"{category}/{case['id']} reference", ok, detail)

                if category == "code_debugging":
                    buggy = run_case(case, case["buggy_code"])
                    recorded = case.get("regression_indices") or []
                    report(
                        f"{category}/{case['id']} buggy code fails",
                        buggy.failed > 0 and bool(recorded),
                        f"fails {buggy.failed}, recorded {len(recorded)} bug test(s)",
                    )
                if category == "code_refactoring":
                    original = run_case(case, case["original_code"])
                    report(
                        f"{category}/{case['id']} original passes tests",
                        original.failure is None and original.failed == 0,
                        str(original.errors[:1])[:200] if original.failed else "",
                    )
                    before = check_structure(case["original_code"], case["structure"])
                    after = check_structure(solution, case["structure"])
                    report(
                        f"{category}/{case['id']} structure discriminates",
                        before < 1.0 and after == 1.0,
                        f"original={before:.2f} refactored={after:.2f}",
                    )

    for case in review.build_cases():
        lines = case["code"].split("\n")
        ok = all(1 <= d["line"] <= len(lines) for d in case["defects"])
        report(f"code_review/{case['id']} defect lines", ok)

    print(f"\n{'all checks passed' if not failures else f'{failures} check(s) failed'}")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Run every reference solution through the language executors.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate only; do not rewrite the dataset files.",
    )
    args = parser.parse_args()

    if not args.check:
        write(build_all())
    if args.validate or args.check:
        return validate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
