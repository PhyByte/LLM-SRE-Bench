"""Shared sandboxed execution for every code-writing category.

The developer track has several categories that all end the same way: take the
code a model wrote, compile it, and run it against hidden tests. That machinery
lives here so ``code_generation``, ``code_debugging``, ``code_refactoring`` and
``code_efficiency`` share one sandbox, one set of language executors, and one
way of turning JSON test data into a test runner in the target language.

Execution happens in a tight sandbox with:
- Timeout (5 seconds per test case, or the case's own budget)
- No network access
- Temporary directory isolation
- Resource limits

Two harness styles are supported:

``HarnessSpec.kind`` in {"function", "rate_limiter", "lru_cache", ...}
    Hand-written per-family harnesses (the original six task families). The
    JSON ``input`` is rendered into a call by family-specific converters.

``HarnessSpec.io`` set (recommended for new cases)
    Type-directed rendering. The case declares the argument and return types
    (``{"args": ["list<int>", "int"], "returns": "int"}``) and one renderer per
    language turns JSON values into correctly typed literals. Adding a task
    family then needs dataset entries only, no evaluator changes.

``HarnessSpec.workload`` set (code_efficiency)
    The test runner *generates* its own large input in-language from a seeded
    LCG, so a 200k-element array never has to be embedded as a source literal.
    The expected answer is a scalar computed by the reference implementation at
    dataset build time.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .base import EvalResult, clamp01


# Maximum execution time per test case in seconds
TIMEOUT_SECONDS = 5.0

# Maximum code size in bytes (reasonable for these tasks)
MAX_CODE_SIZE = 50000

# Wall-clock ceiling for a code_efficiency case. Generous enough that a
# correct-but-sluggish solution still finishes and earns partial credit,
# tight enough that a quadratic one is cut off rather than run for hours.
WORKLOAD_TIMEOUT_SECONDS = 20.0

# Task families whose JSON "input" is a list of positional args (not one list arg).
_MULTI_ARG_FUNCS = {
    "merge_config",
    "mergeConfig",
    "MergeConfig",
}


def _is_multi_arg_input(func_name: str, input_data: Any) -> bool:
    return (
        func_name in _MULTI_ARG_FUNCS
        and isinstance(input_data, list)
        and len(input_data) >= 2
    )


def _ensure_ts_exports(code: str) -> str:
    """Models often omit `export`; the test runner imports the module.

    Only rewrite top-level (column-0) declarations so we don't inject
    ``export`` inside function bodies (e.g. ``const merged = ...``).
    """
    if re.search(r"^export\b", code, re.MULTILINE):
        return code
    code = re.sub(
        r"^(async\s+)?function\s+",
        r"export \1function ",
        code,
        flags=re.MULTILINE,
    )
    code = re.sub(r"^class\s+", "export class ", code, flags=re.MULTILINE)
    code = re.sub(
        r"^(const|let|var)\s+",
        r"export \1 ",
        code,
        flags=re.MULTILINE,
    )
    return code


def _ensure_go_wrapper(code: str) -> str:
    """Ensure package main + imports for common stdlib symbols models use."""
    stripped = code.strip()
    body = stripped
    if body.startswith("package "):
        # Keep existing package / imports if present.
        if "\nimport " in body or body.startswith("import ") or "\nimport(" in body:
            return body
        rest = body.split("\n", 1)[1] if "\n" in body else ""
    else:
        rest = body

    needed: list[str] = []
    for pkg, needle in (
        ("strings", "strings."),
        ("regexp", "regexp."),
        ("fmt", "fmt."),
        ("sort", "sort."),
        ("strconv", "strconv."),
        ("bytes", "bytes."),
        ("unicode", "unicode."),
        ("time", "time."),
    ):
        if needle in rest and f'"{pkg}"' not in stripped:
            needed.append(f'"{pkg}"')

    parts = ["package main", ""]
    if needed:
        parts.append("import (")
        parts.extend(f"\t{p}" for p in needed)
        parts.append(")")
        parts.append("")
    parts.append(rest)
    return "\n".join(parts)


def _task_kind(signature: str, func_name: str) -> str:
    """Classify the case from signature / extracted name."""
    lowered = signature.lower()
    if "ratelimiter" in lowered.replace(" ", "") or func_name in {
        "RateLimiter",
        "NewRateLimiter",
    }:
        return "rate_limiter"
    if "lrucache" in lowered.replace(" ", "") or func_name in {
        "LRUCache",
        "NewLRUCache",
    }:
        return "lru_cache"
    if func_name in _MULTI_ARG_FUNCS:
        return "config_overlay"
    return "function"


# ---------------------------------------------------------------------------
# Harness specification
# ---------------------------------------------------------------------------


@dataclass
class HarnessSpec:
    """How to call the model's code for one dataset case.

    ``io`` and ``workload`` are the new, data-driven paths; a case with neither
    falls back to the original per-family harnesses keyed off ``signature``.
    """

    signature: str = ""
    io: Optional[dict[str, Any]] = None
    workload: Optional[dict[str, Any]] = None
    time_budget_ms: Optional[float] = None
    timeout_s: Optional[float] = None

    @property
    def arg_types(self) -> list[str]:
        return list((self.io or {}).get("args", []))

    @property
    def return_type(self) -> str:
        return (self.io or {}).get("returns", "json")

    @property
    def typed(self) -> bool:
        return self.io is not None


def harness_from_case(case: dict[str, Any]) -> HarnessSpec:
    """Build a harness spec from a dataset case."""
    return HarnessSpec(
        signature=case.get("signature", ""),
        io=case.get("io"),
        workload=case.get("workload"),
        time_budget_ms=case.get("time_budget_ms"),
        timeout_s=case.get("timeout_s"),
    )


# ---------------------------------------------------------------------------
# Type-directed literal rendering
#
# Type grammar (dataset "io" field):
#   int | float | str | bool
#   list<T> | pair<T,T> | map<str,T>
# ---------------------------------------------------------------------------


def _split_type(type_str: str) -> tuple[str, list[str]]:
    """"list<pair<int,int>>" -> ("list", ["pair<int,int>"])."""
    type_str = type_str.strip()
    if "<" not in type_str:
        return type_str, []
    head, rest = type_str.split("<", 1)
    inner = rest.rsplit(">", 1)[0]
    parts: list[str] = []
    depth = 0
    current = ""
    for char in inner:
        if char == "," and depth == 0:
            parts.append(current)
            current = ""
            continue
        if char == "<":
            depth += 1
        elif char == ">":
            depth -= 1
        current += char
    parts.append(current)
    return head.strip(), [p.strip() for p in parts]


def _base_kind(type_str: str) -> str:
    return _split_type(type_str)[0]


_GO_SCALAR_TYPES = {"int": "int", "float": "float64", "str": "string", "bool": "bool"}


def go_type(type_str: str) -> str:
    head, args = _split_type(type_str)
    if head in _GO_SCALAR_TYPES:
        return _GO_SCALAR_TYPES[head]
    if head == "list":
        return "[]" + go_type(args[0])
    if head == "pair":
        return f"[2]{go_type(args[0])}"
    if head == "map":
        return f"map[string]{go_type(args[1])}"
    raise ValueError(f"unsupported io type for go: {type_str!r}")


def go_literal(type_str: str, value: Any, elide: bool = False) -> str:
    head, args = _split_type(type_str)
    if head == "str":
        return json.dumps(value)
    if head == "int":
        return str(int(value))
    if head == "float":
        return repr(float(value))
    if head == "bool":
        return "true" if value else "false"
    prefix = "" if elide else go_type(type_str)
    if head in ("list", "pair"):
        items = ", ".join(go_literal(args[0], v, elide=True) for v in value)
        return f"{prefix}{{{items}}}"
    if head == "map":
        items = ", ".join(
            f"{json.dumps(k)}: {go_literal(args[1], v, elide=True)}"
            for k, v in sorted(value.items())
        )
        return f"{prefix}{{{items}}}"
    raise ValueError(f"unsupported io type for go: {type_str!r}")


def _rust_scalar(head: str, value: Any, suffix: bool) -> str:
    if head == "str":
        return json.dumps(value)
    if head == "int":
        return f"{int(value)}i64" if suffix else str(int(value))
    if head == "float":
        return f"{float(value):.10}f64" if suffix else repr(float(value))
    if head == "bool":
        return "true" if value else "false"
    raise ValueError(f"unsupported io scalar for rust: {head!r}")


def rust_arg_literal(type_str: str, value: Any, nested: bool = False) -> str:
    """Render a call argument. Slices are passed by reference (``&[..]``)."""
    head, args = _split_type(type_str)
    if head in ("str", "int", "float", "bool"):
        return _rust_scalar(head, value, suffix=False)
    if head == "pair":
        return "(" + ", ".join(rust_arg_literal(args[0], v, True) for v in value) + ")"
    if head == "list":
        items = ", ".join(rust_arg_literal(args[0], v, True) for v in value)
        if nested:
            return f"vec![{items}]"
        if not value:
            return f"&[] as &[{rust_slice_element_type(args[0])}]"
        return f"&[{items}]"
    if head == "map":
        if not value:
            return f"&HashMap::<String, {rust_owned_type(args[1])}>::new()"
        items = ", ".join(
            f"({json.dumps(k)}.to_string(), {rust_arg_literal(args[1], v, True)})"
            for k, v in sorted(value.items())
        )
        return f"&HashMap::from([{items}])"
    raise ValueError(f"unsupported io type for rust: {type_str!r}")


def rust_already_imports(code: str, path: str, name: str) -> bool:
    """Does ``code`` already bring ``path::name`` into scope?

    Re-importing a name that is already in scope is a hard compile error in
    Rust, and imports are routinely written grouped —
    ``use std::collections::{HashMap, HashSet};`` — so a substring test for the
    single-name form silently misses them and the harness emits a duplicate.
    """
    pattern = rf"use\s+{re.escape(path)}::(?:\{{[^}}]*\b{name}\b[^}}]*\}}|{name}\b)"
    return re.search(pattern, code) is not None


def rust_slice_element_type(type_str: str) -> str:
    """Element type of a slice *argument*: strings are borrowed, not owned.

    ``&["a", "b"]`` is a ``&[&str]``, so an empty list of strings has to be
    cast to ``&[&str]`` and not to ``&[String]``.
    """
    if _base_kind(type_str) == "str":
        return "&str"
    return rust_owned_type(type_str)


def rust_owned_type(type_str: str) -> str:
    head, args = _split_type(type_str)
    mapping = {"int": "i64", "float": "f64", "str": "String", "bool": "bool"}
    if head in mapping:
        return mapping[head]
    if head == "list":
        return f"Vec<{rust_owned_type(args[0])}>"
    if head == "pair":
        inner = rust_owned_type(args[0])
        return f"({inner}, {inner})"
    if head == "map":
        return f"HashMap<String, {rust_owned_type(args[1])}>"
    raise ValueError(f"unsupported io type for rust: {type_str!r}")


def rust_expected_literal(type_str: str, value: Any) -> str:
    """Render an expected value for ``{:?}`` comparison against the result."""
    head, args = _split_type(type_str)
    if head in ("str", "int", "float", "bool"):
        return _rust_scalar(head, value, suffix=True)
    if head == "pair":
        return "(" + ", ".join(rust_expected_literal(args[0], v) for v in value) + ")"
    if head == "list":
        items = ", ".join(rust_expected_literal(args[0], v) for v in value)
        if not value:
            return f"Vec::<{rust_owned_type(args[0])}>::new()"
        return f"vec![{items}]"
    raise ValueError(f"unsupported io expected type for rust: {type_str!r}")


def rust_map_expected_pairs(type_str: str, value: dict) -> str:
    """Map results are compared as a sorted Vec of stringified pairs.

    HashMap iteration order is random, so ``{:?}`` on a map is not stable. Both
    sides are normalized to ``Vec<(String, String)>`` and sorted; stringifying
    the value also makes the comparison agnostic to whether the model returned
    ``i64``, ``f64`` or ``String`` values.
    """
    _, args = _split_type(type_str)
    items = []
    for key, val in sorted(value.items()):
        if _base_kind(args[1]) == "str":
            rendered = json.dumps(val)
        elif _base_kind(args[1]) == "bool":
            rendered = json.dumps("true" if val else "false")
        else:
            rendered = json.dumps(str(val))
        items.append(f"({json.dumps(key)}.to_string(), {rendered}.to_string())")
    return f"vec![{', '.join(items)}]"


# ---------------------------------------------------------------------------
# Workload generation (code_efficiency)
#
# The runner builds its own large input in-language from a Park-Miller LCG so
# a 200k-element array never has to be embedded as a source literal, and every
# language sees byte-identical data. x*48271 stays below 2^53, so the same
# recurrence is exact in float64 (TypeScript) as in int64.
# ---------------------------------------------------------------------------


def split_args(input_data: Any, arg_types: list[str]) -> list[Any]:
    """One declared argument means ``input`` is that argument, not a list of them."""
    if len(arg_types) <= 1:
        return [input_data]
    return list(input_data)


def workload_values(array_spec: dict[str, Any], seed: int) -> list[int]:
    """The reference implementation of the in-language generator."""
    modulus = int(array_spec.get("mod", 1000))
    offset = int(array_spec.get("offset", 0))
    x = seed % 2147483647
    if x <= 0:
        x += 2147483646
    out: list[int] = []
    for _ in range(int(array_spec["n"])):
        x = (x * 48271) % 2147483647
        out.append(x % modulus + offset)
    return out


def workload_inputs(workload: dict[str, Any]) -> dict[str, Any]:
    """Materialize every generated array plus the scalar parameters."""
    values: dict[str, Any] = {}
    seed = int(workload.get("seed", 12345))
    for index, array_spec in enumerate(workload.get("arrays", [])):
        values[array_spec["name"]] = workload_values(array_spec, seed + index * 7919)
    values.update(workload.get("scalars", {}))
    return values


def parse_runner_output(stdout: str | bytes | None) -> Optional[dict[str, Any]]:
    """Read the last JSON object a test runner printed.

    Runners print one JSON line at the end; workload runners print a second,
    earlier line holding the small-test results so those survive a timeout on
    the big call. Scanning backwards for the last parseable line also means a
    stray ``print`` inside the model's own code no longer breaks parsing.
    """
    if stdout is None:
        return None
    if isinstance(stdout, bytes):
        stdout = stdout.decode("utf-8", "replace")
    for line in reversed(stdout.strip().split("\n")):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and "passed" in parsed:
            return parsed
    return None


def timeout_outcome(
    exc: subprocess.TimeoutExpired, test_cases: list[dict], timeout_s: float
) -> dict[str, Any]:
    """Build a result for a run the sandbox had to kill.

    If the runner already reported the small tests before the timed workload
    hung, those results are kept: a correct-but-quadratic answer should lose
    the speed component, not its correctness.
    """
    partial = parse_runner_output(getattr(exc, "stdout", None)) or {}
    passed = int(partial.get("passed", 0))
    failed = max(len(test_cases) + 1 - passed, 1)
    errors = list(partial.get("errors") or [])
    errors.append("Timeout exceeded")
    return {
        "compiled": True,
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "runtime_ms": timeout_s * 1000,
        "elapsed_ms": None,
    }



class LanguageExecutor:
    """Base class for language-specific code execution."""

    def __init__(self, language: str):
        self.language = language

    def check_toolchain(self) -> tuple[bool, str]:
        """Check if the required toolchain is available. Returns (available, version_info)."""
        raise NotImplementedError

    @staticmethod
    def timeout_for(test_cases: list[dict], harness: HarnessSpec) -> float:
        """Seconds allowed for the whole run (compilation excluded)."""
        if harness.timeout_s:
            return float(harness.timeout_s)
        if harness.workload is not None:
            return WORKLOAD_TIMEOUT_SECONDS
        return TIMEOUT_SECONDS * max(len(test_cases), 1)

    def execute_tests(self, code: str, test_cases: list[dict], harness: HarnessSpec) -> dict:
        """Execute test cases and return results.

        Returns dict with:
        - compiled: bool (whether code compiled/loaded successfully)
        - passed: int (number of tests passed)
        - failed: int (number of tests failed)
        - errors: list[str] (compilation or runtime errors)
        - runtime_ms: float (total execution time)
        """
        raise NotImplementedError


class PythonExecutor(LanguageExecutor):
    def __init__(self):
        super().__init__("python")

    def check_toolchain(self) -> tuple[bool, str]:
        try:
            result = subprocess.run(
                ["python3", "--version"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                return True, result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return False, "python3 not found"

    def execute_tests(self, code: str, test_cases: list[dict], harness: HarnessSpec) -> dict:
        with tempfile.TemporaryDirectory() as tmpdir:
            code_file = Path(tmpdir) / "solution.py"
            test_file = Path(tmpdir) / "test_runner.py"

            # Write solution code
            code_file.write_text(code, encoding="utf-8")

            # Generate test runner
            test_runner = self._generate_test_runner(test_cases, harness)
            test_file.write_text(test_runner, encoding="utf-8")

            try:
                start = time.perf_counter()
                result = subprocess.run(
                    ["python3", str(test_file)],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_for(test_cases, harness),
                    cwd=tmpdir,
                )
                runtime_ms = (time.perf_counter() - start) * 1000

                if result.returncode != 0:
                    return {
                        "compiled": False,
                        "passed": 0,
                        "failed": len(test_cases),
                        "errors": [result.stderr or result.stdout],
                        "runtime_ms": runtime_ms,
                    }

                # Parse JSON output from test runner
                output = parse_runner_output(result.stdout)
                if output is None:
                    return {
                        "compiled": False,
                        "passed": 0,
                        "failed": len(test_cases),
                        "errors": ["Invalid test output"],
                        "runtime_ms": runtime_ms,
                    }
                return {
                    "compiled": True,
                    "passed": output["passed"],
                    "failed": output["failed"],
                    "errors": output["errors"],
                    "runtime_ms": runtime_ms,
                    "elapsed_ms": output.get("elapsed_ms"),
                }
            except subprocess.TimeoutExpired as exc:
                return timeout_outcome(
                    exc, test_cases, self.timeout_for(test_cases, harness)
                )
            except json.JSONDecodeError:
                return {
                    "compiled": False,
                    "passed": 0,
                    "failed": len(test_cases),
                    "errors": ["Invalid test output"],
                    "runtime_ms": 0,
                }

    def _generate_test_runner(self, test_cases: list[dict], harness: HarnessSpec) -> str:
        """Generate a Python test runner script."""
        func_name = self._extract_function_name(harness.signature)
        kind = _task_kind(harness.signature, func_name)

        if harness.workload is not None:
            return self._generate_workload_runner(test_cases, harness, func_name)
        if harness.typed:
            return self._generate_typed_runner(test_cases, harness, func_name)

        test_code = []
        for i, test_case in enumerate(test_cases):
            input_data = test_case["input"]
            expected = test_case["expected"]
            expected_lit = repr(expected)

            if kind == "rate_limiter":
                test_code.append(f"""
# Test case {i}
try:
    rl = RateLimiter({input_data['max_requests']}, {input_data['window_seconds']})
    results = []
    for ts in {repr(input_data['requests'])}:
        results.append(rl.allow(ts))
    if _equal(results, {expected_lit}):
        passed += 1
    else:
        failed += 1
        errors.append(f"Test {i}: expected {expected_lit}, got {{results!r}}")
except Exception as e:
    failed += 1
    errors.append(f"Test {i}: {{type(e).__name__}}: {{e}}")
""")
            elif kind == "lru_cache":
                test_code.append(f"""
# Test case {i}
try:
    cache = LRUCache({input_data['capacity']})
    results = []
    for op in {repr(input_data['ops'])}:
        if op[0] == 'put':
            results.append(cache.put(op[1], op[2]))
        else:
            results.append(cache.get(op[1]))
    if _equal(results, {expected_lit}):
        passed += 1
    else:
        failed += 1
        errors.append(f"Test {i}: expected {expected_lit}, got {{results!r}}")
except Exception as e:
    failed += 1
    errors.append(f"Test {i}: {{type(e).__name__}}: {{e}}")
""")
            else:
                if _is_multi_arg_input(func_name, input_data):
                    call = f"{func_name}({', '.join(repr(a) for a in input_data)})"
                else:
                    call = f"{func_name}({repr(input_data)})"
                test_code.append(f"""
# Test case {i}
try:
    result = {call}
    if _equal(result, {expected_lit}):
        passed += 1
    else:
        failed += 1
        errors.append(f"Test {i}: expected {expected_lit}, got {{result!r}}")
except Exception as e:
    failed += 1
    errors.append(f"Test {i}: {{type(e).__name__}}: {{e}}")
""")

        return f"""
import json
from solution import *

def _equal(a, b):
    # Normalize tuples/lists and JSON scalars so (1, 2) matches [1, 2].
    return json.loads(json.dumps(a)) == json.loads(json.dumps(b))

passed = 0
failed = 0
errors = []

{''.join(test_code)}

print(json.dumps({{"passed": passed, "failed": failed, "errors": errors}}))
"""

    # -- typed / workload harnesses -----------------------------------------

    def _typed_blocks(
        self, test_cases: list[dict], harness: HarnessSpec, func_name: str
    ) -> list[str]:
        arg_types = harness.arg_types
        is_float = _base_kind(harness.return_type) == "float"
        blocks = []
        for i, test_case in enumerate(test_cases):
            args = split_args(test_case["input"], arg_types)
            call = f"{func_name}({', '.join(repr(a) for a in args)})"
            expected_lit = repr(test_case["expected"])
            check = "_close" if is_float else "_equal"
            # The literal is bound to a name rather than spliced into the
            # message f-string: an expected value containing a double quote
            # would otherwise close that f-string and break the whole runner.
            blocks.append(f"""
# Test case {i}
try:
    _expected = {expected_lit}
    result = {call}
    if {check}(result, _expected):
        passed += 1
    else:
        failed += 1
        errors.append(f"Test {i}: expected {{_expected!r}}, got {{result!r}}")
except Exception as e:
    failed += 1
    errors.append(f"Test {i}: {{type(e).__name__}}: {{e}}")
""")
        return blocks

    def _workload_block(self, harness: HarnessSpec, func_name: str, index: int) -> str:
        workload = harness.workload or {}
        seed = int(workload.get("seed", 12345))
        setup = []
        for offset_index, array_spec in enumerate(workload.get("arrays", [])):
            setup.append(
                f"{array_spec['name']} = _gen({int(array_spec['n'])}, "
                f"{seed + offset_index * 7919}, {int(array_spec.get('mod', 1000))}, "
                f"{int(array_spec.get('offset', 0))})"
            )
        scalars = workload.get("scalars", {})
        call_args = ", ".join(
            name if name not in scalars else repr(scalars[name])
            for name in workload["call_args"]
        )
        expected_lit = repr(workload["expected"])
        check = "_close" if _base_kind(harness.return_type) == "float" else "_equal"
        setup_code = "\n".join(f"    {line}" for line in setup)
        return f"""
# Test case {index} (workload)
try:
{setup_code}
    _expected = {expected_lit}
    _start = time.perf_counter()
    result = {func_name}({call_args})
    elapsed_ms = (time.perf_counter() - _start) * 1000
    if {check}(result, _expected):
        passed += 1
    else:
        failed += 1
        errors.append(f"Workload: expected {{_expected!r}}, got {{result!r}}")
except Exception as e:
    failed += 1
    errors.append(f"Workload: {{type(e).__name__}}: {{e}}")
"""

    def _generate_typed_runner(
        self, test_cases: list[dict], harness: HarnessSpec, func_name: str
    ) -> str:
        return self._assemble(self._typed_blocks(test_cases, harness, func_name))

    # Report the small tests before the timed workload starts, so a correct but
    # too-slow answer keeps its correctness credit if the sandbox kills it.
    # Explicitly flushed: stdout to a pipe is block-buffered.
    _CHECKPOINT = (
        '\nprint(json.dumps({"passed": passed, "failed": failed, '
        '"errors": errors, "elapsed_ms": None}), flush=True)\n'
    )

    def _generate_workload_runner(
        self, test_cases: list[dict], harness: HarnessSpec, func_name: str
    ) -> str:
        blocks = self._typed_blocks(test_cases, harness, func_name)
        blocks.append(self._CHECKPOINT)
        blocks.append(self._workload_block(harness, func_name, len(blocks) - 1))
        return self._assemble(blocks)

    @staticmethod
    def _assemble(blocks: list[str]) -> str:
        return f"""
import json
import time
from solution import *


def _gen(n, seed, m, offset):
    x = seed % 2147483647
    if x <= 0:
        x += 2147483646
    out = []
    for _ in range(n):
        x = (x * 48271) % 2147483647
        out.append(x % m + offset)
    return out


def _equal(a, b):
    return json.loads(json.dumps(a)) == json.loads(json.dumps(b))


def _close(a, b):
    try:
        return abs(float(a) - float(b)) <= 1e-6
    except (TypeError, ValueError):
        return False


passed = 0
failed = 0
errors = []
elapsed_ms = None

{''.join(blocks)}

print(json.dumps({{"passed": passed, "failed": failed, "errors": errors, "elapsed_ms": elapsed_ms}}))
"""

    def _extract_function_name(self, signature: str) -> str:
        """Extract function or class name from signature."""
        if "class " in signature:
            parts = signature.split("class ")[1].split("(")[0].split(":")[0]
            return parts.strip()
        if "def " in signature:
            parts = signature.split("def ")[1].split("(")[0]
            return parts.strip()
        return "unknown"


class TypeScriptExecutor(LanguageExecutor):
    def __init__(self):
        super().__init__("typescript")

    def check_toolchain(self) -> tuple[bool, str]:
        try:
            # Check for Node.js and TypeScript compiler
            node_result = subprocess.run(
                ["node", "--version"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if node_result.returncode != 0:
                return False, "node not found"

            # Check if tsx is available (TypeScript executor)
            tsx_result = subprocess.run(
                ["npx", "tsx", "--version"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if tsx_result.returncode == 0:
                return True, f"node {node_result.stdout.strip()}, tsx available"

            # Fallback: check for tsc
            tsc_result = subprocess.run(
                ["npx", "tsc", "--version"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if tsc_result.returncode == 0:
                return True, f"node {node_result.stdout.strip()}, tsc {tsc_result.stdout.strip()}"

            return False, "tsx or tsc not found (install with: npm install -g tsx)"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False, "node or npm not found"

    def execute_tests(self, code: str, test_cases: list[dict], harness: HarnessSpec) -> dict:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Try tsx first (direct TypeScript execution)
            return self._execute_with_tsx(tmpdir, code, test_cases, harness)

    def _execute_with_tsx(self, tmpdir: str, code: str, test_cases: list[dict], harness: HarnessSpec) -> dict:
        code_file = Path(tmpdir) / "solution.ts"
        test_file = Path(tmpdir) / "test_runner.ts"

        # Models often omit `export`; the runner imports the module by name.
        code_file.write_text(_ensure_ts_exports(code), encoding="utf-8")

        test_runner = self._generate_test_runner(test_cases, harness)
        test_file.write_text(test_runner, encoding="utf-8")

        try:
            start = time.perf_counter()
            for cmd in [
                ["npx", "tsx", str(test_file)],
                ["npx", "ts-node", str(test_file)],
            ]:
                try:
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=self.timeout_for(test_cases, harness),
                        cwd=tmpdir,
                    )
                    runtime_ms = (time.perf_counter() - start) * 1000

                    if result.returncode != 0:
                        if "command not found" in result.stderr.lower() or "not found" in result.stderr.lower():
                            continue
                        return {
                            "compiled": False,
                            "passed": 0,
                            "failed": len(test_cases),
                            "errors": [result.stderr or result.stdout],
                            "runtime_ms": runtime_ms,
                        }

                    output = parse_runner_output(result.stdout)
                    if output is None:
                        return {
                            "compiled": False,
                            "passed": 0,
                            "failed": len(test_cases),
                            "errors": ["Invalid test output"],
                            "runtime_ms": runtime_ms,
                        }
                    return {
                        "compiled": True,
                        "passed": output["passed"],
                        "failed": output["failed"],
                        "errors": output["errors"],
                        "runtime_ms": runtime_ms,
                        "elapsed_ms": output.get("elapsed_ms"),
                    }
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    continue

            return {
                "compiled": False,
                "passed": 0,
                "failed": len(test_cases),
                "errors": ["TypeScript toolchain not available"],
                "runtime_ms": 0,
            }

        except subprocess.TimeoutExpired as exc:
            return timeout_outcome(exc, test_cases, self.timeout_for(test_cases, harness))
        except json.JSONDecodeError:
            return {
                "compiled": False,
                "passed": 0,
                "failed": len(test_cases),
                "errors": ["Invalid test output"],
                "runtime_ms": 0,
            }

    def _generate_test_runner(self, test_cases: list[dict], harness: HarnessSpec) -> str:
        func_name = self._extract_function_name(harness.signature)
        kind = _task_kind(harness.signature, func_name)

        if harness.workload is not None:
            return self._generate_workload_runner(test_cases, harness, func_name)
        if harness.typed:
            return self._generate_typed_runner(test_cases, harness, func_name)

        test_code = []
        for i, test_case in enumerate(test_cases):
            input_data = test_case["input"]
            expected = test_case["expected"]
            expected_json = json.dumps(expected)

            if kind == "rate_limiter":
                test_code.append(f"""
// Test case {i}
try {{
    const rl = new RateLimiter({input_data['max_requests']}, {input_data['window_seconds']});
    const results: boolean[] = [];
    for (const ts of {json.dumps(input_data['requests'])}) {{
        results.push(rl.allow(ts));
    }}
    if (JSON.stringify(results) === JSON.stringify({expected_json})) {{
        passed++;
    }} else {{
        failed++;
        errors.push(`Test {i}: expected ${{JSON.stringify({expected_json})}}, got ${{JSON.stringify(results)}}`);
    }}
}} catch (e) {{
    failed++;
    errors.push(`Test {i}: ${{e}}`);
}}
""")
            elif kind == "lru_cache":
                test_code.append(f"""
// Test case {i}
try {{
    const cache = new LRUCache({input_data['capacity']});
    const results: any[] = [];
    for (const op of {json.dumps(input_data['ops'])}) {{
        if (op[0] === 'put') {{
            results.push(cache.put(op[1], op[2]) ?? null);
        }} else {{
            results.push(cache.get(op[1]));
        }}
    }}
    if (JSON.stringify(results) === JSON.stringify({expected_json})) {{
        passed++;
    }} else {{
        failed++;
        errors.push(`Test {i}: expected ${{JSON.stringify({expected_json})}}, got ${{JSON.stringify(results)}}`);
    }}
}} catch (e) {{
    failed++;
    errors.push(`Test {i}: ${{e}}`);
}}
""")
            else:
                if _is_multi_arg_input(func_name, input_data):
                    args = ", ".join(json.dumps(a) for a in input_data)
                    call = f"{func_name}({args})"
                else:
                    call = f"{func_name}({json.dumps(input_data)})"
                test_code.append(f"""
// Test case {i}
try {{
    const result = {call};
    if (JSON.stringify(result) === JSON.stringify({expected_json})) {{
        passed++;
    }} else {{
        failed++;
        errors.push(`Test {i}: expected ${{JSON.stringify({expected_json})}}, got ${{JSON.stringify(result)}}`);
    }}
}} catch (e) {{
    failed++;
    errors.push(`Test {i}: ${{e}}`);
}}
""")

        return f"""
import * as solution from './solution';
const {{{func_name}}} = solution as any;

let passed = 0;
let failed = 0;
const errors: string[] = [];

{''.join(test_code)}

console.log(JSON.stringify({{passed, failed, errors}}));
"""

    # -- typed / workload harnesses -----------------------------------------

    def _typed_blocks(
        self, test_cases: list[dict], harness: HarnessSpec, func_name: str
    ) -> list[str]:
        arg_types = harness.arg_types
        is_float = _base_kind(harness.return_type) == "float"
        blocks = []
        for i, test_case in enumerate(test_cases):
            args = split_args(test_case["input"], arg_types)
            call = f"{func_name}({', '.join(json.dumps(a) for a in args)})"
            expected_json = json.dumps(test_case["expected"])
            check = (
                f"Math.abs(Number(result) - {expected_json}) <= 1e-6"
                if is_float
                else f"stable(result) === stable({expected_json})"
            )
            blocks.append(f"""
// Test case {i}
try {{
    const result = {call};
    if ({check}) {{
        passed++;
    }} else {{
        failed++;
        errors.push(`Test {i}: expected {expected_json}, got ${{stable(result)}}`);
    }}
}} catch (e) {{
    failed++;
    errors.push(`Test {i}: ${{e}}`);
}}
""")
        return blocks

    def _workload_block(self, harness: HarnessSpec, func_name: str, index: int) -> str:
        workload = harness.workload or {}
        seed = int(workload.get("seed", 12345))
        setup = []
        for offset_index, array_spec in enumerate(workload.get("arrays", [])):
            setup.append(
                f"const {array_spec['name']} = gen({int(array_spec['n'])}, "
                f"{seed + offset_index * 7919}, {int(array_spec.get('mod', 1000))}, "
                f"{int(array_spec.get('offset', 0))});"
            )
        scalars = workload.get("scalars", {})
        call_args = ", ".join(
            name if name not in scalars else json.dumps(scalars[name])
            for name in workload["call_args"]
        )
        expected_json = json.dumps(workload["expected"])
        check = (
            f"Math.abs(Number(result) - {expected_json}) <= 1e-6"
            if _base_kind(harness.return_type) == "float"
            else f"stable(result) === stable({expected_json})"
        )
        setup_code = "\n".join(f"    {line}" for line in setup)
        return f"""
// Test case {index} (workload)
try {{
{setup_code}
    const started = performance.now();
    const result = {func_name}({call_args});
    elapsedMs = performance.now() - started;
    if ({check}) {{
        passed++;
    }} else {{
        failed++;
        errors.push(`Workload: expected {expected_json}, got ${{stable(result)}}`);
    }}
}} catch (e) {{
    failed++;
    errors.push(`Workload: ${{e}}`);
}}
"""

    def _generate_typed_runner(
        self, test_cases: list[dict], harness: HarnessSpec, func_name: str
    ) -> str:
        return self._assemble(func_name, self._typed_blocks(test_cases, harness, func_name))

    # See PythonExecutor._CHECKPOINT. writeSync, because a piped console.log can
    # still be buffered when the process is killed.
    _CHECKPOINT = (
        "\nrequire('fs').writeSync(1, JSON.stringify("
        "{passed, failed, errors, elapsed_ms: null}) + '\\n');\n"
    )

    def _generate_workload_runner(
        self, test_cases: list[dict], harness: HarnessSpec, func_name: str
    ) -> str:
        blocks = self._typed_blocks(test_cases, harness, func_name)
        blocks.append(self._CHECKPOINT)
        blocks.append(self._workload_block(harness, func_name, len(blocks) - 1))
        return self._assemble(func_name, blocks)

    @staticmethod
    def _assemble(func_name: str, blocks: list[str]) -> str:
        return f"""
import * as solution from './solution';
const {{{func_name}}} = solution as any;

function gen(n: number, seed: number, m: number, offset: number): number[] {{
    let x = seed % 2147483647;
    if (x <= 0) x += 2147483646;
    const out: number[] = [];
    for (let i = 0; i < n; i++) {{
        x = (x * 48271) % 2147483647;
        out.push((x % m) + offset);
    }}
    return out;
}}

// Key order must not decide a comparison, so objects are stringified sorted.
function stable(value: any): string {{
    if (value === null || typeof value !== 'object') return JSON.stringify(value) ?? 'null';
    if (Array.isArray(value)) return '[' + value.map(stable).join(',') + ']';
    const keys = Object.keys(value).sort();
    return '{{' + keys.map((k) => JSON.stringify(k) + ':' + stable(value[k])).join(',') + '}}';
}}

let passed = 0;
let failed = 0;
const errors: string[] = [];
let elapsedMs: number | null = null;

{''.join(blocks)}

console.log(JSON.stringify({{passed, failed, errors, elapsed_ms: elapsedMs}}));
"""

    def _extract_function_name(self, signature: str) -> str:
        if "class " in signature:
            return signature.split("class ")[1].split("{")[0].strip()
        if "function " in signature:
            return signature.split("function ")[1].split("(")[0].strip()
        return "unknown"


class GoExecutor(LanguageExecutor):
    def __init__(self):
        super().__init__("go")

    def check_toolchain(self) -> tuple[bool, str]:
        try:
            result = subprocess.run(
                ["go", "version"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                return True, result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return False, "go not found"

    def execute_tests(self, code: str, test_cases: list[dict], harness: HarnessSpec) -> dict:
        with tempfile.TemporaryDirectory() as tmpdir:
            subprocess.run(
                ["go", "mod", "init", "solution"],
                capture_output=True,
                cwd=tmpdir,
                timeout=5,
            )

            code_file = Path(tmpdir) / "solution.go"
            test_file = Path(tmpdir) / "main.go"

            code_file.write_text(_ensure_go_wrapper(code), encoding="utf-8")

            test_runner = self._generate_test_runner(test_cases, harness)
            test_file.write_text(test_runner, encoding="utf-8")

            try:
                start = time.perf_counter()
                result = subprocess.run(
                    ["go", "run", "."],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_for(test_cases, harness) + 15,
                    cwd=tmpdir,
                )
                runtime_ms = (time.perf_counter() - start) * 1000

                if result.returncode != 0:
                    return {
                        "compiled": False,
                        "passed": 0,
                        "failed": len(test_cases),
                        "errors": [result.stderr or result.stdout],
                        "runtime_ms": runtime_ms,
                    }

                output = parse_runner_output(result.stdout)
                if output is None:
                    return {
                        "compiled": False,
                        "passed": 0,
                        "failed": len(test_cases),
                        "errors": ["Invalid test output"],
                        "runtime_ms": runtime_ms,
                    }
                return {
                    "compiled": True,
                    "passed": output["passed"],
                    "failed": output["failed"],
                    "errors": output["errors"],
                    "runtime_ms": runtime_ms,
                    "elapsed_ms": output.get("elapsed_ms"),
                }
            except subprocess.TimeoutExpired as exc:
                return timeout_outcome(
                    exc, test_cases, self.timeout_for(test_cases, harness)
                )
            except json.JSONDecodeError:
                return {
                    "compiled": False,
                    "passed": 0,
                    "failed": len(test_cases),
                    "errors": ["Invalid test output"],
                    "runtime_ms": 0,
                }

    def _generate_test_runner(self, test_cases: list[dict], harness: HarnessSpec) -> str:
        func_name = self._extract_function_name(harness.signature)
        kind = _task_kind(harness.signature, func_name)

        if harness.workload is not None:
            return self._generate_workload_runner(test_cases, harness, func_name)
        if harness.typed:
            return self._generate_typed_runner(test_cases, harness, func_name)

        test_code = []
        for i, test_case in enumerate(test_cases):
            input_data = test_case["input"]
            expected = test_case["expected"]

            if kind == "rate_limiter":
                bools = ", ".join("true" if x else "false" for x in expected)
                reqs = ", ".join(str(x) for x in input_data["requests"])
                test_code.append(f"""
    // Test case {i}
    func() {{
        defer func() {{
            if r := recover(); r != nil {{
                failed++
                errors = append(errors, fmt.Sprintf("Test {i}: panic: %v", r))
            }}
        }}()
        rl := NewRateLimiter({input_data['max_requests']}, {input_data['window_seconds']})
        results := []bool{{}}
        for _, ts := range []float64{{{reqs}}} {{
            results = append(results, rl.Allow(ts))
        }}
        expected := []bool{{{bools}}}
        if fmt.Sprintf("%v", results) == fmt.Sprintf("%v", expected) {{
            passed++
        }} else {{
            failed++
            errors = append(errors, fmt.Sprintf("Test {i}: expected %v, got %v", expected, results))
        }}
    }}()
""")
            elif kind == "lru_cache":
                # Drive ops in generated Go so we don't need a JSON op parser.
                op_lines = []
                for op in input_data["ops"]:
                    if op[0] == "put":
                        op_lines.append(
                            f'\t\tcache.Put("{op[1]}", {op[2]})\n'
                            f'\t\tresults = append(results, []interface{{}}{{nil, false}})'
                        )
                    else:
                        op_lines.append(
                            f'\t\tv, ok = cache.Get("{op[1]}")\n'
                            f'\t\tresults = append(results, []interface{{}}{{v, ok}})'
                        )
                # Build expected as fmt.Sprintf("%v") would render it.
                exp_parts = []
                for item in expected:
                    if isinstance(item, list) and len(item) == 2:
                        a, b = item
                        a_go = "<nil>" if a is None else str(a)
                        b_go = "true" if b else "false"
                        exp_parts.append(f"[{a_go} {b_go}]")
                    else:
                        exp_parts.append(str(item))
                expected_fmt = "[" + " ".join(exp_parts) + "]"
                test_code.append(f"""
    // Test case {i}
    func() {{
        defer func() {{
            if r := recover(); r != nil {{
                failed++
                errors = append(errors, fmt.Sprintf("Test {i}: panic: %v", r))
            }}
        }}()
        cache := NewLRUCache({input_data['capacity']})
        var results []interface{{}}
        var v int
        var ok bool
{chr(10).join(op_lines)}
        if fmt.Sprintf("%v", results) == "{expected_fmt}" {{
            passed++
        }} else {{
            failed++
            errors = append(errors, fmt.Sprintf("Test {i}: expected {expected_fmt}, got %v", results))
        }}
    }}()
""")
            else:
                if _is_multi_arg_input(func_name, input_data):
                    go_input = ", ".join(
                        self._convert_to_go_input(a, func_name) for a in input_data
                    )
                else:
                    go_input = self._convert_to_go_input(input_data, func_name)
                go_expected = self._convert_to_go_expected(expected, func_name)
                call_name = func_name
                test_code.append(f"""
    // Test case {i}
    func() {{
        defer func() {{
            if r := recover(); r != nil {{
                failed++
                errors = append(errors, fmt.Sprintf("Test {i}: panic: %v", r))
            }}
        }}()
        result := {call_name}({go_input})
        expected := {go_expected}
        if fmt.Sprintf("%v", result) == fmt.Sprintf("%v", expected) {{
            passed++
        }} else {{
            failed++
            errors = append(errors, fmt.Sprintf("Test {i}: expected %v, got %v", expected, result))
        }}
    }}()
""")

        return f"""package main

import (
    "encoding/json"
    "fmt"
    "os"
)

func main() {{
    passed := 0
    failed := 0
    errors := []string{{}}

{''.join(test_code)}

    _ = json.NewEncoder(os.Stdout).Encode(map[string]interface{{}}{{
        "passed": passed,
        "failed": failed,
        "errors": errors,
    }})
}}
"""

    # -- typed / workload harnesses -----------------------------------------

    def _compare_expr(self, harness: HarnessSpec) -> str:
        """Go comparison for the declared return type.

        Everything but floats is compared through ``encoding/json``, which
        renders map keys in sorted order and is indifferent to whether the
        model returned ``[]int``, ``[]int64`` or ``[]interface{}``.
        """
        if _base_kind(harness.return_type) == "float":
            return "math.Abs(result-expected) <= 1e-6"
        return "jsonEq(result, expected)"

    def _typed_blocks(
        self, test_cases: list[dict], harness: HarnessSpec, func_name: str
    ) -> list[str]:
        arg_types = harness.arg_types
        compare = self._compare_expr(harness)
        blocks = []
        for i, test_case in enumerate(test_cases):
            args = split_args(test_case["input"], arg_types)
            rendered = ", ".join(
                go_literal(arg_type, value) for arg_type, value in zip(arg_types, args)
            )
            expected = go_literal(harness.return_type, test_case["expected"])
            blocks.append(f"""
    // Test case {i}
    func() {{
        defer func() {{
            if r := recover(); r != nil {{
                failed++
                errors = append(errors, fmt.Sprintf("Test {i}: panic: %v", r))
            }}
        }}()
        result := {func_name}({rendered})
        expected := {expected}
        if {compare} {{
            passed++
        }} else {{
            failed++
            errors = append(errors, fmt.Sprintf("Test {i}: expected %v, got %v", expected, result))
        }}
    }}()
""")
        return blocks

    def _workload_block(self, harness: HarnessSpec, func_name: str, index: int) -> str:
        workload = harness.workload or {}
        seed = int(workload.get("seed", 12345))
        setup = []
        for offset_index, array_spec in enumerate(workload.get("arrays", [])):
            setup.append(
                f"        {array_spec['name']} := genArray({int(array_spec['n'])}, "
                f"{seed + offset_index * 7919}, {int(array_spec.get('mod', 1000))}, "
                f"{int(array_spec.get('offset', 0))})"
            )
        scalars = workload.get("scalars", {})
        call_args = ", ".join(
            name if name not in scalars else str(int(scalars[name]))
            for name in workload["call_args"]
        )
        expected = go_literal(harness.return_type, workload["expected"])
        compare = self._compare_expr(harness)
        return f"""
    // Test case {index} (workload)
    func() {{
        defer func() {{
            if r := recover(); r != nil {{
                failed++
                errors = append(errors, fmt.Sprintf("Workload: panic: %v", r))
            }}
        }}()
{chr(10).join(setup)}
        started := time.Now()
        result := {func_name}({call_args})
        elapsed := float64(time.Since(started).Microseconds()) / 1000.0
        elapsedMs = &elapsed
        expected := {expected}
        if {compare} {{
            passed++
        }} else {{
            failed++
            errors = append(errors, fmt.Sprintf("Workload: expected %v, got %v", expected, result))
        }}
    }}()
"""

    def _generate_typed_runner(
        self, test_cases: list[dict], harness: HarnessSpec, func_name: str
    ) -> str:
        blocks = self._typed_blocks(test_cases, harness, func_name)
        return self._assemble(blocks, harness, workload=False)

    # See PythonExecutor._CHECKPOINT. os.Stdout is unbuffered.
    _CHECKPOINT = """
    _ = json.NewEncoder(os.Stdout).Encode(map[string]interface{}{
        "passed": passed, "failed": failed, "errors": errors, "elapsed_ms": elapsedMs,
    })
"""

    def _generate_workload_runner(
        self, test_cases: list[dict], harness: HarnessSpec, func_name: str
    ) -> str:
        blocks = self._typed_blocks(test_cases, harness, func_name)
        blocks.append(self._CHECKPOINT)
        blocks.append(self._workload_block(harness, func_name, len(blocks) - 1))
        return self._assemble(blocks, harness, workload=True)

    @staticmethod
    def _assemble(blocks: list[str], harness: HarnessSpec, workload: bool) -> str:
        # Go rejects unused imports, so only pull in what these blocks touch.
        imports = ['    "encoding/json"', '    "fmt"', '    "os"']
        if _base_kind(harness.return_type) == "float":
            imports.append('    "math"')
        if workload:
            imports.append('    "time"')
        generator = """
func genArray(n, seed, m, offset int) []int {
    x := seed % 2147483647
    if x <= 0 {
        x += 2147483646
    }
    out := make([]int, 0, n)
    for i := 0; i < n; i++ {
        x = (x * 48271) % 2147483647
        out = append(out, x%m+offset)
    }
    return out
}
""" if workload else ""
        return f"""package main

import (
{chr(10).join(sorted(imports))}
)
{generator}
// A nil slice and an empty slice are the same answer here.
func jsonEq(a, b interface{{}}) bool {{
    x, err1 := json.Marshal(a)
    y, err2 := json.Marshal(b)
    if err1 != nil || err2 != nil {{
        return false
    }}
    left, right := string(x), string(y)
    if left == "null" {{
        left = "[]"
    }}
    if right == "null" {{
        right = "[]"
    }}
    return left == right
}}

func main() {{
    passed := 0
    failed := 0
    errors := []string{{}}
    var elapsedMs *float64

{''.join(blocks)}

    _ = json.NewEncoder(os.Stdout).Encode(map[string]interface{{}}{{
        "passed":     passed,
        "failed":     failed,
        "errors":     errors,
        "elapsed_ms": elapsedMs,
    }})
}}
"""

    def _extract_function_name(self, signature: str) -> str:
        if "type " in signature and "struct" in signature:
            return signature.split("type ")[1].split(" ")[0].strip()
        if "func " in signature:
            parts = signature.split("func ")[1].split("(")[0].strip()
            if ")" in parts:
                parts = parts.split(")")[-1].strip()
            return parts
        return "unknown"

    def _convert_to_go_input(self, input_data: Any, func_name: str) -> str:
        """Convert JSON input to Go syntax."""
        if isinstance(input_data, str):
            return f'"{input_data}"'
        elif isinstance(input_data, list):
            if not input_data:
                if func_name in ("MergeIntervals", "merge_intervals"):
                    return "[][2]int{}"
                return "nil"
            # Check if it's a list of intervals
            if all(isinstance(x, list) and len(x) == 2 for x in input_data):
                items = ", ".join(f"[2]int{{{x[0]}, {x[1]}}}" for x in input_data)
                return f"[][2]int{{{items}}}"
            return str(input_data).replace("[", "{").replace("]", "}")
        elif isinstance(input_data, dict):
            return self._dict_to_go_map(input_data)
        else:
            return str(input_data)

    def _dict_to_go_map(self, d: dict) -> str:
        """Convert Python dict to Go map[string]interface{} literal."""
        items = []
        for k, v in d.items():
            if isinstance(v, dict):
                val = self._dict_to_go_map(v)
            elif isinstance(v, list):
                if not v:
                    val = "nil"
                else:
                    parts = []
                    for item in v:
                        if isinstance(item, str):
                            parts.append(f'"{item}"')
                        elif isinstance(item, dict):
                            parts.append(self._dict_to_go_map(item))
                        else:
                            parts.append(str(item).lower() if isinstance(item, bool) else str(item))
                    val = f"[]interface{{}}{{{', '.join(parts)}}}"
            elif isinstance(v, str):
                val = f'"{v}"'
            elif isinstance(v, bool):
                val = "true" if v else "false"
            elif v is None:
                val = "nil"
            else:
                val = str(v)
            items.append(f'"{k}": {val}')
        return f"map[string]interface{{}}{{{', '.join(items)}}}"

    def _convert_to_go_expected(self, expected: Any, func_name: str = "") -> str:
        """Convert expected output to Go syntax."""
        if isinstance(expected, str):
            return f'"{expected}"'
        elif isinstance(expected, list):
            if not expected:
                if func_name in ("MergeIntervals", "merge_intervals"):
                    return "[][2]int{}"
                return "nil"
            if all(isinstance(x, list) and len(x) == 2 for x in expected):
                items = ", ".join(f"[2]int{{{x[0]}, {x[1]}}}" for x in expected)
                return f"[][2]int{{{items}}}"
            return str(expected).replace("[", "{").replace("]", "}")
        elif isinstance(expected, dict):
            return self._dict_to_go_map(expected)
        else:
            return str(expected)


class RustExecutor(LanguageExecutor):
    def __init__(self):
        super().__init__("rust")

    def check_toolchain(self) -> tuple[bool, str]:
        try:
            result = subprocess.run(
                ["rustc", "--version"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                return True, result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return False, "rustc not found"

    def execute_tests(self, code: str, test_cases: list[dict], harness: HarnessSpec) -> dict:
        with tempfile.TemporaryDirectory() as tmpdir:
            code_file = Path(tmpdir) / "main.rs"

            # Generate full Rust program with tests
            rust_program = self._generate_rust_program(code, test_cases, harness)
            code_file.write_text(rust_program, encoding="utf-8")

            try:
                # Compile first
                compile_start = time.perf_counter()
                # Debug builds are an order of magnitude slower, which would
                # make the code_efficiency budgets meaningless; optimize those.
                rustc_cmd = ["rustc", "-o", "solution", str(code_file)]
                if harness.workload is not None:
                    rustc_cmd.insert(1, "-O")
                compile_result = subprocess.run(
                    rustc_cmd,
                    capture_output=True,
                    text=True,
                    timeout=30,  # Rust compilation can be slow
                    cwd=tmpdir,
                )
                compile_time = time.perf_counter() - compile_start

                if compile_result.returncode != 0:
                    return {
                        "compiled": False,
                        "passed": 0,
                        "failed": len(test_cases),
                        "errors": [compile_result.stderr],
                        "runtime_ms": compile_time * 1000,
                    }

                # Run compiled binary
                run_start = time.perf_counter()
                run_result = subprocess.run(
                    ["./solution"],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_for(test_cases, harness),
                    cwd=tmpdir,
                )
                runtime_ms = (time.perf_counter() - run_start) * 1000

                if run_result.returncode != 0:
                    return {
                        "compiled": True,
                        "passed": 0,
                        "failed": len(test_cases),
                        "errors": [run_result.stderr or run_result.stdout],
                        "runtime_ms": runtime_ms,
                    }

                # Parse JSON output
                output = parse_runner_output(run_result.stdout)
                if output is None:
                    return {
                        "compiled": True,
                        "passed": 0,
                        "failed": len(test_cases),
                        "errors": ["Invalid test output"],
                        "runtime_ms": runtime_ms,
                    }
                return {
                    "compiled": True,
                    "passed": output["passed"],
                    "failed": output["failed"],
                    "errors": output["errors"],
                    "runtime_ms": runtime_ms,
                    "elapsed_ms": output.get("elapsed_ms"),
                }

            except subprocess.TimeoutExpired as exc:
                return timeout_outcome(
                    exc, test_cases, self.timeout_for(test_cases, harness)
                )
            except json.JSONDecodeError:
                return {
                    "compiled": False,
                    "passed": 0,
                    "failed": len(test_cases),
                    "errors": ["Invalid test output"],
                    "runtime_ms": 0,
                }

    @staticmethod
    def _escape_rust_str(value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"')

    def _generate_rust_program(self, code: str, test_cases: list[dict], harness: HarnessSpec) -> str:
        """Generate complete Rust program with solution and tests."""
        func_name = self._extract_function_name(harness.signature)
        kind = _task_kind(harness.signature, func_name)

        if harness.workload is not None:
            return self._generate_workload_program(code, test_cases, harness, func_name)
        if harness.typed:
            return self._generate_typed_program(code, test_cases, harness, func_name)

        imports = []
        needs_hashmap = "HashMap" in code or func_name == "parse_log_line" or kind == "lru_cache"
        if needs_hashmap and not rust_already_imports(code, "std::collections", "HashMap"):
            imports.append("use std::collections::HashMap;")
        if func_name == "merge_config":
            # serde_json requires cargo; keep a note in imports for compile errors
            # to be clear. Prefer HashMap-free compile of other tasks via rustc.
            imports.append("use serde_json::{json, Value};")

        test_code = []
        for i, test_case in enumerate(test_cases):
            input_data = test_case["input"]
            expected = test_case["expected"]

            if func_name == "slugify" or (
                kind == "function" and func_name == "slugify"
            ):
                esc_input = self._escape_rust_str(str(input_data))
                esc_expected = self._escape_rust_str(str(expected))
                test_code.append(f"""
    // Test {i}
    let result = slugify("{esc_input}");
    if result == "{esc_expected}" {{
        passed += 1;
    }} else {{
        failed += 1;
        errors.push(format!("Test {i}: expected {{:?}}, got {{:?}}", "{esc_expected}", result));
    }}
""")
            elif kind == "rate_limiter":
                reqs = ", ".join(str(x) for x in input_data["requests"])
                exp = ", ".join("true" if x else "false" for x in expected)
                test_code.append(f"""
    // Test {i}
    {{
        let mut rl = RateLimiter::new({input_data['max_requests']}, {input_data['window_seconds']});
        let results: Vec<bool> = vec![{reqs}].into_iter().map(|ts| rl.allow(ts)).collect();
        let expected = vec![{exp}];
        if results == expected {{
            passed += 1;
        }} else {{
            failed += 1;
            errors.push(format!("Test {i}: expected {{:?}}, got {{:?}}", expected, results));
        }}
    }}
""")
            elif kind == "lru_cache":
                op_lines = []
                for op in input_data["ops"]:
                    if op[0] == "put":
                        op_lines.append(
                            f'        cache.put("{op[1]}".to_string(), {op[2]});\n'
                            f"        results.push(None);"
                        )
                    else:
                        op_lines.append(
                            f'        results.push(cache.get("{op[1]}"));'
                        )
                exp_items = []
                for v in expected:
                    if v is None:
                        exp_items.append("None")
                    else:
                        exp_items.append(f"Some({v})")
                test_code.append(f"""
    // Test {i}
    {{
        let mut cache = LRUCache::new({input_data['capacity']});
        let mut results: Vec<Option<i32>> = Vec::new();
{chr(10).join(op_lines)}
        let expected: Vec<Option<i32>> = vec![{', '.join(exp_items)}];
        if results == expected {{
            passed += 1;
        }} else {{
            failed += 1;
            errors.push(format!("Test {i}: expected {{:?}}, got {{:?}}", expected, results));
        }}
    }}
""")
            elif func_name == "merge_config" and isinstance(input_data, list) and len(input_data) == 2:
                rust_input1 = self._convert_to_rust(input_data[0], func_name)
                rust_input2 = self._convert_to_rust(input_data[1], func_name)
                rust_expected = self._convert_to_rust(expected, func_name)
                test_code.append(f"""
    // Test {i}
    let result = {func_name}({rust_input1}, {rust_input2});
    if format!("{{:?}}", result) == format!("{{:?}}", {rust_expected}) {{
        passed += 1;
    }} else {{
        failed += 1;
        errors.push(format!("Test {i}: expected {{:?}}, got {{:?}}", {rust_expected}, result));
    }}
""")
            else:
                rust_input = self._convert_to_rust(input_data, func_name)
                rust_expected = self._convert_to_rust(expected, func_name)
                test_code.append(f"""
    // Test {i}
    let result = {func_name}({rust_input});
    if format!("{{:?}}", result) == format!("{{:?}}", {rust_expected}) {{
        passed += 1;
    }} else {{
        failed += 1;
        errors.push(format!("Test {i}: expected {{:?}}, got {{:?}}", {rust_expected}, result));
    }}
""")

        header = "\n".join(imports)
        body = f"""
{header}

{code}

fn main() {{
    let mut passed = 0;
    let mut failed = 0;
    let mut errors: Vec<String> = Vec::new();

{''.join(test_code)}
"""
        # Regular (non-f) string so {{ }} are literal Rust format escapes.
        footer = """
    println!("{{\\"passed\\":{},\\"failed\\":{},\\"errors\\":{:?}}}", passed, failed, errors);
}
"""
        return body + footer

    # -- typed / workload harnesses -----------------------------------------

    def _typed_case_block(
        self,
        harness: HarnessSpec,
        func_name: str,
        label: str,
        call: str,
        expected: Any,
        timed: bool = False,
    ) -> str:
        """One Rust test scope: call, compare, report."""
        return_kind = _base_kind(harness.return_type)
        if return_kind == "map":
            expected_decl = (
                f"        let mut expected: Vec<(String, String)> = "
                f"{rust_map_expected_pairs(harness.return_type, expected)};\n"
                f"        expected.sort();\n"
                "        let mut got: Vec<(String, String)> = result\n"
                "            .iter()\n"
                "            .map(|(k, v)| (k.to_string(), v.to_string()))\n"
                "            .collect();\n"
                "        got.sort();"
            )
            check = "got == expected"
            got_expr = "got"
        elif return_kind == "float":
            expected_decl = (
                f"        let expected = {rust_expected_literal(harness.return_type, expected)};"
            )
            check = "(result - expected).abs() <= 1e-6"
            got_expr = "result"
        else:
            expected_decl = (
                f"        let expected = {rust_expected_literal(harness.return_type, expected)};"
            )
            check = 'format!("{:?}", result) == format!("{:?}", expected)'
            got_expr = "result"

        if timed:
            call_lines = (
                "        let started = Instant::now();\n"
                f"        let result = {call};\n"
                "        elapsed_ms = format!(\"{:.3}\", started.elapsed().as_secs_f64() * 1000.0);"
            )
        else:
            call_lines = f"        let result = {call};"

        return f"""
    // {label}
    {{
{call_lines}
{expected_decl}
        if {check} {{
            passed += 1;
        }} else {{
            failed += 1;
            errors.push(format!("{label}: expected {{:?}}, got {{:?}}", expected, {got_expr}));
        }}
    }}
"""

    def _typed_blocks(
        self, test_cases: list[dict], harness: HarnessSpec, func_name: str
    ) -> list[str]:
        arg_types = harness.arg_types
        blocks = []
        for i, test_case in enumerate(test_cases):
            args = split_args(test_case["input"], arg_types)
            rendered = ", ".join(
                rust_arg_literal(arg_type, value)
                for arg_type, value in zip(arg_types, args)
            )
            blocks.append(
                self._typed_case_block(
                    harness,
                    func_name,
                    f"Test {i}",
                    f"{func_name}({rendered})",
                    test_case["expected"],
                )
            )
        return blocks

    def _workload_block(self, harness: HarnessSpec, func_name: str, index: int) -> str:
        workload = harness.workload or {}
        seed = int(workload.get("seed", 12345))
        setup = []
        for offset_index, array_spec in enumerate(workload.get("arrays", [])):
            setup.append(
                f"        let {array_spec['name']} = gen_array({int(array_spec['n'])}, "
                f"{seed + offset_index * 7919}, {int(array_spec.get('mod', 1000))}, "
                f"{int(array_spec.get('offset', 0))});"
            )
        scalars = workload.get("scalars", {})
        call_args = ", ".join(
            f"&{name}" if name not in scalars else str(int(scalars[name]))
            for name in workload["call_args"]
        )
        block = self._typed_case_block(
            harness,
            func_name,
            "Workload",
            f"{func_name}({call_args})",
            workload["expected"],
            timed=True,
        )
        # Generated arrays have to exist before the call inside the same scope.
        return block.replace("    {\n", "    {\n" + "\n".join(setup) + "\n", 1)

    def _generate_typed_program(
        self, code: str, test_cases: list[dict], harness: HarnessSpec, func_name: str
    ) -> str:
        return self._assemble(code, self._typed_blocks(test_cases, harness, func_name), harness, False)

    # See PythonExecutor._CHECKPOINT. println! flushes on the newline.
    _CHECKPOINT = (
        '\n    println!("{{\\"passed\\":{},\\"failed\\":{},\\"errors\\":{:?},'
        '\\"elapsed_ms\\":null}}", passed, failed, errors);\n'
    )

    def _generate_workload_program(
        self, code: str, test_cases: list[dict], harness: HarnessSpec, func_name: str
    ) -> str:
        blocks = self._typed_blocks(test_cases, harness, func_name)
        blocks.append(self._CHECKPOINT)
        blocks.append(self._workload_block(harness, func_name, len(blocks) - 1))
        return self._assemble(code, blocks, harness, True)

    @staticmethod
    def _assemble(code: str, blocks: list[str], harness: HarnessSpec, workload: bool) -> str:
        types = [*harness.arg_types, harness.return_type]
        imports = []
        # The model's own code may already import these; a second `use` of the
        # same name is a hard compile error in Rust, not a warning.
        needs_hashmap = any(_base_kind(t) == "map" for t in types) or "HashMap" in code
        if needs_hashmap and not rust_already_imports(code, "std::collections", "HashMap"):
            imports.append("use std::collections::HashMap;")
        if workload and not rust_already_imports(code, "std::time", "Instant"):
            imports.append("use std::time::Instant;")
        generator = """
fn gen_array(n: usize, seed: i64, m: i64, offset: i64) -> Vec<i64> {
    let mut x = seed % 2147483647;
    if x <= 0 {
        x += 2147483646;
    }
    let mut out = Vec::with_capacity(n);
    for _ in 0..n {
        x = (x * 48271) % 2147483647;
        out.push(x % m + offset);
    }
    out
}
""" if workload else ""

        header = "\n".join(imports)
        body = (
            f"{header}\n\n{code}\n{generator}\n"
            "fn main() {\n"
            "    let mut passed = 0;\n"
            "    let mut failed = 0;\n"
            "    let mut errors: Vec<String> = Vec::new();\n"
            "    #[allow(unused_mut, unused_assignments)]\n"
            "    let mut elapsed_ms = String::from(\"null\");\n"
            f"{''.join(blocks)}"
        )
        # Regular (non-f) string so {{ }} stay literal Rust format escapes.
        footer = """
    println!("{{\\"passed\\":{},\\"failed\\":{},\\"errors\\":{:?},\\"elapsed_ms\\":{}}}", passed, failed, errors, elapsed_ms);
}
"""
        return body + footer

    def _extract_function_name(self, signature: str) -> str:
        if "struct " in signature:
            return signature.split("struct ")[1].split("{")[0].strip()
        if "fn " in signature:
            return signature.split("fn ")[1].split("(")[0].strip()
        return "unknown"

    def _convert_to_rust(self, value: Any, func_name: str) -> str:
        """Convert Python value to Rust syntax."""
        if isinstance(value, str):
            return f'"{value}"'
        elif isinstance(value, list):
            if not value:
                if func_name == "merge_intervals":
                    return "Vec::<(i32, i32)>::new()"
                if func_name == "parse_log_line":
                    return "HashMap::<String, String>::new()"
                return "vec![]"
            # Check for intervals
            if all(isinstance(x, list) and len(x) == 2 for x in value):
                items = ", ".join(f"({x[0]}, {x[1]})" for x in value)
                return f"vec![{items}]"
            return f"vec!{str(value).replace('[', '[').replace(']', ']')}"
        elif isinstance(value, dict):
            # For merge_config, use serde_json::json! macro
            if func_name == "merge_config":
                return f"json!({json.dumps(value)})"
            # For parse_log_line result
            items = [f'("{k}".to_string(), "{v}".to_string())' for k, v in value.items()]
            return f"HashMap::from([{', '.join(items)}])"
        else:
            return str(value).lower() if isinstance(value, bool) else str(value)


# Language executor registry
EXECUTORS: dict[str, LanguageExecutor] = {
    "python": PythonExecutor(),
    "typescript": TypeScriptExecutor(),
    "go": GoExecutor(),
    "rust": RustExecutor(),
}



# ---------------------------------------------------------------------------
# Running a dataset case and turning the result into a score
# ---------------------------------------------------------------------------

# A solution that takes longer than this over the whole test set is treated as
# slow; used only for the small runtime_efficiency component.
REASONABLE_RUNTIME_MS = 2000.0

# Byte size above which code starts losing the code_quality component.
REASONABLE_SIZE_BYTES = 2000


_TEST_INDEX = re.compile(r"^Test (\d+):")


def failed_test_indices(errors: list[str]) -> set[int]:
    """Which test cases failed, from the runner's own ``Test N: ...`` messages.

    Used by code_debugging to tell "passes the tests the bug never touched"
    apart from "actually fixed the bug".
    """
    indices = set()
    for error in errors:
        match = _TEST_INDEX.match(str(error).strip())
        if match:
            indices.add(int(match.group(1)))
    return indices


@dataclass
class ExecutionOutcome:
    """What happened when one model answer was compiled and run."""

    language: str = ""
    code_size: int = 0
    compiled: bool = False
    passed: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)
    runtime_ms: float = 0.0
    # In-language timing of the workload call, when the case has one. Excludes
    # compilation and input generation, so it is comparable to a time budget.
    elapsed_ms: Optional[float] = None
    # Set when the case never ran at all (no toolchain, oversized answer);
    # the caller should score 0 and report these metrics as-is.
    failure: Optional[dict[str, Any]] = None

    @property
    def total_tests(self) -> int:
        return self.passed + self.failed

    @property
    def correctness(self) -> float:
        return self.passed / self.total_tests if self.total_tests else 0.0

    def pass_rate_over(self, indices: list[int]) -> Optional[float]:
        """Pass rate across a chosen subset of the test cases.

        Returns None when the failures cannot be attributed — a compile error,
        a panic that took the process down, or a timeout reports no per-test
        detail — so the caller can fall back rather than assume a pass.
        """
        if not indices:
            return None
        if not self.compiled or self.passed == 0:
            return 0.0
        failed = failed_test_indices(self.errors)
        if len(failed) != self.failed:
            return None
        return sum(1 for index in indices if index not in failed) / len(indices)


def run_case(case: dict[str, Any], code: str) -> ExecutionOutcome:
    """Compile and run ``code`` against one dataset case's hidden tests."""
    language = case["language"]
    executor = EXECUTORS.get(language)
    if executor is None:
        return ExecutionOutcome(
            language=language,
            failure={"error": "unknown_language", "language": language},
        )

    available, version_info = executor.check_toolchain()
    if not available:
        return ExecutionOutcome(
            language=language,
            failure={
                "error": "toolchain_unavailable",
                "language": language,
                "reason": version_info,
            },
        )

    code_size = len(code.encode("utf-8"))
    if code_size > MAX_CODE_SIZE:
        return ExecutionOutcome(
            language=language,
            code_size=code_size,
            failure={
                "error": "code_too_large",
                "size_bytes": code_size,
                "max_bytes": MAX_CODE_SIZE,
            },
        )

    harness = harness_from_case(case)
    result = executor.execute_tests(code, case.get("test_cases", []), harness)
    return ExecutionOutcome(
        language=language,
        code_size=code_size,
        compiled=bool(result["compiled"]),
        passed=int(result["passed"]),
        failed=int(result["failed"]),
        errors=list(result.get("errors") or []),
        runtime_ms=float(result.get("runtime_ms") or 0.0),
        elapsed_ms=result.get("elapsed_ms"),
    )


def score_execution(
    outcome: ExecutionOutcome,
    weights: dict[str, float],
    extra_components: Optional[dict[str, float]] = None,
    extra_metrics: Optional[dict[str, Any]] = None,
) -> EvalResult:
    """Weighted score over correctness / compilation / speed / size.

    ``extra_components`` lets a category add its own dimension (the efficiency
    category adds ``perf``, refactoring adds ``structure``) and weight it.
    """
    components: dict[str, float] = {
        "correctness": outcome.correctness,
        "compiled": 1.0 if outcome.compiled else 0.0,
        "runtime_efficiency": clamp01(
            REASONABLE_RUNTIME_MS / max(outcome.runtime_ms, 1.0)
        ),
        "code_quality": clamp01(REASONABLE_SIZE_BYTES / max(outcome.code_size, 1)),
    }
    components.update(extra_components or {})

    missing = [name for name in weights if name not in components]
    if missing:
        raise KeyError(f"no value for weighted component(s): {missing}")

    score = sum(components[name] * weight for name, weight in weights.items())

    metrics: dict[str, Any] = {
        **{name: components[name] for name in weights},
        "tests_passed": outcome.passed,
        "tests_failed": outcome.failed,
        "runtime_ms": outcome.runtime_ms,
        "code_size_bytes": outcome.code_size,
        "errors": len(outcome.errors),
    }
    if outcome.elapsed_ms is not None:
        metrics["elapsed_ms"] = outcome.elapsed_ms
    metrics.update(extra_metrics or {})
    return EvalResult(score=clamp01(score), metrics=metrics)
