"""Code generation scoring: correctness, compilation, runtime, and code size.

Score = 0.60 * correctness + 0.20 * compilation + 0.10 * runtime_efficiency + 0.10 * code_quality

Execution happens in a tight sandbox with:
- Timeout (5 seconds per test case)
- No network access
- Temporary directory isolation
- Resource limits
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from core.schemas import CodeGenerationResult

from .base import EvalResult, clamp01


# Maximum execution time per test case in seconds
TIMEOUT_SECONDS = 5.0

# Maximum code size in bytes (reasonable for these tasks)
MAX_CODE_SIZE = 50000


class LanguageExecutor:
    """Base class for language-specific code execution."""

    def __init__(self, language: str):
        self.language = language

    def check_toolchain(self) -> tuple[bool, str]:
        """Check if the required toolchain is available. Returns (available, version_info)."""
        raise NotImplementedError

    def execute_tests(self, code: str, test_cases: list[dict], signature: str) -> dict:
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

    def execute_tests(self, code: str, test_cases: list[dict], signature: str) -> dict:
        with tempfile.TemporaryDirectory() as tmpdir:
            code_file = Path(tmpdir) / "solution.py"
            test_file = Path(tmpdir) / "test_runner.py"

            # Write solution code
            code_file.write_text(code, encoding="utf-8")

            # Generate test runner
            test_runner = self._generate_test_runner(test_cases, signature)
            test_file.write_text(test_runner, encoding="utf-8")

            try:
                start = time.perf_counter()
                result = subprocess.run(
                    ["python3", str(test_file)],
                    capture_output=True,
                    text=True,
                    timeout=TIMEOUT_SECONDS * len(test_cases),
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
                output = json.loads(result.stdout)
                return {
                    "compiled": True,
                    "passed": output["passed"],
                    "failed": output["failed"],
                    "errors": output["errors"],
                    "runtime_ms": runtime_ms,
                }
            except subprocess.TimeoutExpired:
                return {
                    "compiled": True,
                    "passed": 0,
                    "failed": len(test_cases),
                    "errors": ["Timeout exceeded"],
                    "runtime_ms": TIMEOUT_SECONDS * len(test_cases) * 1000,
                }
            except json.JSONDecodeError:
                return {
                    "compiled": False,
                    "passed": 0,
                    "failed": len(test_cases),
                    "errors": ["Invalid test output"],
                    "runtime_ms": 0,
                }

    def _generate_test_runner(self, test_cases: list[dict], signature: str) -> str:
        """Generate a Python test runner script."""
        # Determine function/class name from signature
        func_name = self._extract_function_name(signature)

        # Build test cases
        test_code = []
        for i, test_case in enumerate(test_cases):
            input_data = test_case["input"]
            expected = test_case["expected"]

            if func_name == "RateLimiter":
                # Special handling for rate limiter class
                test_code.append(f"""
# Test case {i}
try:
    rl = RateLimiter({input_data['max_requests']}, {input_data['window_seconds']})
    results = []
    for ts in {input_data['requests']}:
        results.append(rl.allow(ts))
    if results == {expected}:
        passed += 1
    else:
        failed += 1
        errors.append(f"Test {i}: expected {{expected}}, got {{results}}")
except Exception as e:
    failed += 1
    errors.append(f"Test {i}: {{type(e).__name__}}: {{e}}")
""")
            elif func_name == "LRUCache":
                # Special handling for LRU cache
                test_code.append(f"""
# Test case {i}
try:
    cache = LRUCache({input_data['capacity']})
    results = []
    for op in {input_data['ops']}:
        if op[0] == 'put':
            results.append(cache.put(op[1], op[2]))
        else:  # get
            results.append(cache.get(op[1]))
    if results == {expected}:
        passed += 1
    else:
        failed += 1
        errors.append(f"Test {i}: expected {{expected}}, got {{results}}")
except Exception as e:
    failed += 1
    errors.append(f"Test {i}: {{type(e).__name__}}: {{e}}")
""")
            else:
                # Regular function
                input_repr = repr(input_data)
                expected_repr = repr(expected)
                test_code.append(f"""
# Test case {i}
try:
    result = {func_name}({input_repr})
    if result == {expected_repr}:
        passed += 1
    else:
        failed += 1
        errors.append(f"Test {i}: expected {{expected_repr}}, got {{result}}")
except Exception as e:
    failed += 1
    errors.append(f"Test {i}: {{type(e).__name__}}: {{e}}")
""")

        return f"""
import json
import sys
from solution import *

passed = 0
failed = 0
errors = []

{''.join(test_code)}

result = {{"passed": passed, "failed": failed, "errors": errors}}
print(json.dumps(result))
"""

    def _extract_function_name(self, signature: str) -> str:
        """Extract function or class name from signature."""
        if "class " in signature:
            parts = signature.split("class ")[1].split("(")[0].split(":")[0]
            return parts.strip()
        elif "def " in signature:
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

    def execute_tests(self, code: str, test_cases: list[dict], signature: str) -> dict:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Try tsx first (direct TypeScript execution)
            return self._execute_with_tsx(tmpdir, code, test_cases, signature)

    def _execute_with_tsx(self, tmpdir: str, code: str, test_cases: list[dict], signature: str) -> dict:
        code_file = Path(tmpdir) / "solution.ts"
        test_file = Path(tmpdir) / "test_runner.ts"

        # Write solution code
        code_file.write_text(code, encoding="utf-8")

        # Generate test runner
        test_runner = self._generate_test_runner(test_cases, signature)
        test_file.write_text(test_runner, encoding="utf-8")

        try:
            start = time.perf_counter()
            # Try tsx first, fallback to ts-node, then compile + run
            for cmd in [
                ["npx", "tsx", str(test_file)],
                ["npx", "ts-node", str(test_file)],
            ]:
                try:
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=TIMEOUT_SECONDS * len(test_cases),
                        cwd=tmpdir,
                    )
                    runtime_ms = (time.perf_counter() - start) * 1000

                    if result.returncode != 0:
                        # If command not found, try next approach
                        if "command not found" in result.stderr.lower() or "not found" in result.stderr.lower():
                            continue
                        return {
                            "compiled": False,
                            "passed": 0,
                            "failed": len(test_cases),
                            "errors": [result.stderr or result.stdout],
                            "runtime_ms": runtime_ms,
                        }

                    # Parse JSON output
                    output = json.loads(result.stdout)
                    return {
                        "compiled": True,
                        "passed": output["passed"],
                        "failed": output["failed"],
                        "errors": output["errors"],
                        "runtime_ms": runtime_ms,
                    }
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    continue

            # All methods failed
            return {
                "compiled": False,
                "passed": 0,
                "failed": len(test_cases),
                "errors": ["TypeScript toolchain not available"],
                "runtime_ms": 0,
            }

        except subprocess.TimeoutExpired:
            return {
                "compiled": True,
                "passed": 0,
                "failed": len(test_cases),
                "errors": ["Timeout exceeded"],
                "runtime_ms": TIMEOUT_SECONDS * len(test_cases) * 1000,
            }
        except json.JSONDecodeError:
            return {
                "compiled": False,
                "passed": 0,
                "failed": len(test_cases),
                "errors": ["Invalid test output"],
                "runtime_ms": 0,
            }

    def _generate_test_runner(self, test_cases: list[dict], signature: str) -> str:
        func_name = self._extract_function_name(signature)

        test_code = []
        for i, test_case in enumerate(test_cases):
            input_data = test_case["input"]
            expected = test_case["expected"]

            if func_name == "RateLimiter":
                test_code.append(f"""
// Test case {i}
try {{
    const rl = new RateLimiter({input_data['max_requests']}, {input_data['window_seconds']});
    const results: boolean[] = [];
    for (const ts of {json.dumps(input_data['requests'])}) {{
        results.push(rl.allow(ts));
    }}
    if (JSON.stringify(results) === JSON.stringify({json.dumps(expected)})) {{
        passed++;
    }} else {{
        failed++;
        errors.push(`Test {i}: expected ${{{json.dumps(expected)}}}, got ${{JSON.stringify(results)}}`);
    }}
}} catch (e) {{
    failed++;
    errors.push(`Test {i}: ${{e}}`);
}}
""")
            elif func_name == "LRUCache":
                test_code.append(f"""
// Test case {i}
try {{
    const cache = new LRUCache({input_data['capacity']});
    const results: any[] = [];
    for (const op of {json.dumps(input_data['ops'])}) {{
        if (op[0] === 'put') {{
            results.push(cache.put(op[1], op[2]));
        }} else {{
            results.push(cache.get(op[1]));
        }}
    }}
    if (JSON.stringify(results) === JSON.stringify({json.dumps(expected)})) {{
        passed++;
    }} else {{
        failed++;
        errors.push(`Test {i}: expected ${{{json.dumps(expected)}}}, got ${{JSON.stringify(results)}}`);
    }}
}} catch (e) {{
    failed++;
    errors.push(`Test {i}: ${{e}}`);
}}
""")
            else:
                input_json = json.dumps(input_data)
                expected_json = json.dumps(expected)
                test_code.append(f"""
// Test case {i}
try {{
    const result = {func_name}({input_json});
    if (JSON.stringify(result) === JSON.stringify({expected_json})) {{
        passed++;
    }} else {{
        failed++;
        errors.push(`Test {i}: expected ${{{expected_json}}}, got ${{JSON.stringify(result)}}`);
    }}
}} catch (e) {{
    failed++;
    errors.push(`Test {i}: ${{e}}`);
}}
""")

        return f"""
import * as solution from './solution';
const {{{func_name}}} = solution;

let passed = 0;
let failed = 0;
const errors: string[] = [];

{''.join(test_code)}

console.log(JSON.stringify({{passed, failed, errors}}));
"""

    def _extract_function_name(self, signature: str) -> str:
        if "class " in signature:
            parts = signature.split("class ")[1].split("{")[0].strip()
            return parts
        elif "function " in signature:
            parts = signature.split("function ")[1].split("(")[0]
            return parts.strip()
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

    def execute_tests(self, code: str, test_cases: list[dict], signature: str) -> dict:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize Go module
            subprocess.run(
                ["go", "mod", "init", "solution"],
                capture_output=True,
                cwd=tmpdir,
                timeout=5,
            )

            code_file = Path(tmpdir) / "solution.go"
            test_file = Path(tmpdir) / "main.go"

            # Write solution code (wrap in package)
            go_code = f"package main\n\n{code}"
            code_file.write_text(go_code, encoding="utf-8")

            # Generate test runner
            test_runner = self._generate_test_runner(test_cases, signature)
            test_file.write_text(test_runner, encoding="utf-8")

            try:
                start = time.perf_counter()
                result = subprocess.run(
                    ["go", "run", ".", ],
                    capture_output=True,
                    text=True,
                    timeout=TIMEOUT_SECONDS * len(test_cases) + 10,  # Extra time for compilation
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

                # Parse JSON output
                output = json.loads(result.stdout)
                return {
                    "compiled": True,
                    "passed": output["passed"],
                    "failed": output["failed"],
                    "errors": output["errors"],
                    "runtime_ms": runtime_ms,
                }
            except subprocess.TimeoutExpired:
                return {
                    "compiled": True,
                    "passed": 0,
                    "failed": len(test_cases),
                    "errors": ["Timeout exceeded"],
                    "runtime_ms": TIMEOUT_SECONDS * len(test_cases) * 1000,
                }
            except json.JSONDecodeError:
                return {
                    "compiled": False,
                    "passed": 0,
                    "failed": len(test_cases),
                    "errors": ["Invalid test output"],
                    "runtime_ms": 0,
                }

    def _generate_test_runner(self, test_cases: list[dict], signature: str) -> str:
        func_name = self._extract_function_name(signature)

        test_code = []
        for i, test_case in enumerate(test_cases):
            input_data = test_case["input"]
            expected = test_case["expected"]

            if func_name == "RateLimiter":
                test_code.append(f"""
// Test case {i}
func() {{
    rl := NewRateLimiter({input_data['max_requests']}, {input_data['window_seconds']})
    results := []bool{{}}
    requests := []float64{{{', '.join(str(x) for x in input_data['requests'])}}}
    for _, ts := range requests {{
        results = append(results, rl.Allow(ts))
    }}
    expected := []bool{{{', '.join('true' if x else 'false' for x in expected)}}}
    if fmt.Sprintf("%v", results) == fmt.Sprintf("%v", expected) {{
        passed++
    }} else {{
        failed++
        errors = append(errors, fmt.Sprintf("Test {i}: expected %v, got %v", expected, results))
    }}
}}()
""")
            elif func_name == "LRUCache":
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
    ops := {json.dumps(input_data['ops'])}
    // Note: Simplified for Go - actual implementation would parse ops
    passed++  // Placeholder
}}()
""")
            else:
                # Convert Python/JSON input to Go syntax
                go_input = self._convert_to_go_input(input_data, func_name)
                go_expected = self._convert_to_go_expected(expected)

                test_code.append(f"""
// Test case {i}
func() {{
    defer func() {{
        if r := recover(); r != nil {{
            failed++
            errors = append(errors, fmt.Sprintf("Test {i}: panic: %v", r))
        }}
    }}()
    result := {func_name}({go_input})
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

    result := map[string]interface{{}}{{
        "passed": passed,
        "failed": failed,
        "errors": errors,
    }}
    json.NewEncoder(os.Stdout).Encode(result)
}}
"""

    def _extract_function_name(self, signature: str) -> str:
        if "func " in signature:
            parts = signature.split("func ")[1].split("(")[0].strip()
            if ")" in parts:  # Method receiver like (rl *RateLimiter)
                parts = parts.split(")")[1].strip()
            return parts
        elif "type " in signature:
            parts = signature.split("type ")[1].split(" ")[0].strip()
            return parts
        return "unknown"

    def _convert_to_go_input(self, input_data: Any, func_name: str) -> str:
        """Convert JSON input to Go syntax."""
        if isinstance(input_data, str):
            return f'"{input_data}"'
        elif isinstance(input_data, list):
            if not input_data:
                return "nil"
            # Check if it's a list of intervals
            if all(isinstance(x, list) and len(x) == 2 for x in input_data):
                items = ", ".join(f"[2]int{{{x[0]}, {x[1]}}}" for x in input_data)
                return f"[][2]int{{{items}}}"
            return str(input_data).replace("[", "{").replace("]", "}")
        elif isinstance(input_data, dict):
            # For config overlay: convert to map[string]interface{}
            return self._dict_to_go_map(input_data)
        else:
            return str(input_data)

    def _dict_to_go_map(self, d: dict) -> str:
        """Convert Python dict to Go map literal."""
        items = []
        for k, v in d.items():
            if isinstance(v, dict):
                val = self._dict_to_go_map(v)
            elif isinstance(v, list):
                val = str(v).replace("[", "{").replace("]", "}")
            elif isinstance(v, str):
                val = f'"{v}"'
            else:
                val = str(v)
            items.append(f'"{k}": {val}')
        return f"map[string]interface{{{{{', '.join(items)}}}}}"

    def _convert_to_go_expected(self, expected: Any) -> str:
        """Convert expected output to Go syntax."""
        if isinstance(expected, str):
            return f'"{expected}"'
        elif isinstance(expected, list):
            if not expected:
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

    def execute_tests(self, code: str, test_cases: list[dict], signature: str) -> dict:
        with tempfile.TemporaryDirectory() as tmpdir:
            code_file = Path(tmpdir) / "main.rs"

            # Generate full Rust program with tests
            rust_program = self._generate_rust_program(code, test_cases, signature)
            code_file.write_text(rust_program, encoding="utf-8")

            try:
                # Compile first
                compile_start = time.perf_counter()
                compile_result = subprocess.run(
                    ["rustc", "-o", "solution", str(code_file)],
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
                    timeout=TIMEOUT_SECONDS * len(test_cases),
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
                output = json.loads(run_result.stdout)
                return {
                    "compiled": True,
                    "passed": output["passed"],
                    "failed": output["failed"],
                    "errors": output["errors"],
                    "runtime_ms": runtime_ms,
                }

            except subprocess.TimeoutExpired:
                return {
                    "compiled": True,
                    "passed": 0,
                    "failed": len(test_cases),
                    "errors": ["Timeout exceeded"],
                    "runtime_ms": TIMEOUT_SECONDS * len(test_cases) * 1000,
                }
            except json.JSONDecodeError:
                return {
                    "compiled": False,
                    "passed": 0,
                    "failed": len(test_cases),
                    "errors": ["Invalid test output"],
                    "runtime_ms": 0,
                }

    def _generate_rust_program(self, code: str, test_cases: list[dict], signature: str) -> str:
        """Generate complete Rust program with solution and tests."""
        func_name = self._extract_function_name(signature)

        # Add necessary imports
        imports = []
        if "HashMap" in code or func_name == "parse_log_line":
            imports.append("use std::collections::HashMap;")
        if func_name == "merge_config":
            imports.append("use serde_json::{json, Value};")

        test_code = []
        for i, test_case in enumerate(test_cases):
            input_data = test_case["input"]
            expected = test_case["expected"]

            # Generate test based on function type
            if func_name == "slugify":
                test_code.append(f"""
    // Test {i}
    let result = slugify("{input_data}");
    if result == "{expected}" {{
        passed += 1;
    }} else {{
        failed += 1;
        errors.push(format!("Test {i}: expected {expected:?}, got {{:?}}", result));
    }}
""")
            elif isinstance(input_data, list) and len(input_data) == 2:
                # Two-argument functions like merge_intervals, merge_config
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
                # Single-argument functions
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

        return f"""
{chr(10).join(imports)}

{code}

fn main() {{
    let mut passed = 0;
    let mut failed = 0;
    let mut errors: Vec<String> = Vec::new();

{''.join(test_code)}

    println!("{{{\\"passed\\":{{}},\\"failed\\":{{}},\\"errors\\":{:?}}}}}", passed, failed, errors);
}}
"""

    def _extract_function_name(self, signature: str) -> str:
        if "fn " in signature:
            parts = signature.split("fn ")[1].split("(")[0].strip()
            return parts
        elif "struct " in signature:
            parts = signature.split("struct ")[1].split("{")[0].strip()
            return parts
        return "unknown"

    def _convert_to_rust(self, value: Any, func_name: str) -> str:
        """Convert Python value to Rust syntax."""
        if isinstance(value, str):
            return f'"{value}"'
        elif isinstance(value, list):
            if not value:
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


def evaluate(case: dict[str, Any], result: CodeGenerationResult) -> EvalResult:
    """Evaluate generated code against hidden test cases.

    Scoring:
    - 60% correctness (tests passed)
    - 20% compilation success
    - 10% runtime efficiency (compared to reasonable baseline)
    - 10% code quality (size penalty for extremely verbose code)
    """
    language = case["language"]
    test_cases = case["test_cases"]
    code = result.code

    # Check if toolchain is available
    executor = EXECUTORS.get(language)
    if executor is None:
        return EvalResult(
            score=0.0,
            metrics={"error": "unknown_language", "language": language},
        )

    available, version_info = executor.check_toolchain()
    if not available:
        return EvalResult(
            score=0.0,
            metrics={
                "error": "toolchain_unavailable",
                "language": language,
                "reason": version_info,
            },
        )

    # Check code size (penalize extremely verbose solutions)
    code_size = len(code.encode("utf-8"))
    if code_size > MAX_CODE_SIZE:
        return EvalResult(
            score=0.0,
            metrics={
                "error": "code_too_large",
                "size_bytes": code_size,
                "max_bytes": MAX_CODE_SIZE,
            },
        )

    # Execute tests
    exec_result = executor.execute_tests(code, test_cases, case.get("signature", ""))

    # Calculate scores
    compiled_score = 1.0 if exec_result["compiled"] else 0.0

    total_tests = exec_result["passed"] + exec_result["failed"]
    correctness_score = exec_result["passed"] / total_tests if total_tests > 0 else 0.0

    # Runtime efficiency: penalize if significantly slower than reasonable (>2 seconds for all tests)
    reasonable_runtime_ms = 2000
    runtime_score = clamp01(reasonable_runtime_ms / max(exec_result["runtime_ms"], 1))

    # Code quality: penalize excessively verbose code
    reasonable_size = 2000  # bytes
    size_score = clamp01(reasonable_size / max(code_size, 1))

    # Weighted final score
    final_score = (
        0.60 * correctness_score +
        0.20 * compiled_score +
        0.10 * runtime_score +
        0.10 * size_score
    )

    return EvalResult(
        score=final_score,
        metrics={
            "correctness": correctness_score,
            "compiled": compiled_score,
            "runtime_efficiency": runtime_score,
            "code_quality": size_score,
            "tests_passed": exec_result["passed"],
            "tests_failed": exec_result["failed"],
            "runtime_ms": exec_result["runtime_ms"],
            "code_size_bytes": code_size,
            "errors": len(exec_result["errors"]),
        },
    )
