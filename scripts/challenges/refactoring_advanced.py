"""Harder code_refactoring families.

Same contract as ``refactoring.py``: code that already works, a goal for the
shape it should end up with, hidden tests proving the behavior survived, and a
handful of loose structural rules proving the model restructured rather than
reformatted.

These go past "replace the if-chain with a table". Each one is a named smell
with a different fix — a nesting pyramid that wants guard clauses, four passes
that want one, a hand-rolled sort that wants the library's, a block copied twice
that wants a helper — so a model has to recognise which refactor applies, not
reach for the single move that worked on the easy cases. The rules stay
alternative-friendly: they check that the smell is gone and the tool is present,
never that one particular implementation was written.
"""

from __future__ import annotations

from .common import Family, dedent_code

# ---------------------------------------------------------------------------
# Reference implementations (the behavior that must survive the refactor)
# ---------------------------------------------------------------------------

_KNOWN_ENVS = ("prod", "staging", "dev")


def deploy_gate(env: str, healthy: bool, approvals: int, frozen: bool) -> str:
    if env not in _KNOWN_ENVS:
        return "blocked: unknown env"
    if frozen and env == "prod":
        return "blocked: change freeze"
    if not healthy:
        return "blocked: unhealthy"
    if env == "prod" and approvals < 2:
        return "blocked: needs 2 approvals"
    if env == "staging" and approvals < 1:
        return "blocked: needs 1 approval"
    return "allowed"


_TRANSITIONS = {
    ("idle", "start"): "running",
    ("running", "pause"): "paused",
    ("running", "finish"): "done",
    ("running", "fail"): "failed",
    ("paused", "resume"): "running",
    ("paused", "cancel"): "cancelled",
    ("failed", "retry"): "running",
}
_STATES = ("idle", "running", "paused", "done", "failed", "cancelled")


def next_state(state: str, event: str) -> str:
    if state not in _STATES:
        return "invalid"
    return _TRANSITIONS.get((state, event), state)


def summarize_series(values: list[int]) -> str:
    if not values:
        return "n=0"
    smallest = values[0]
    largest = values[0]
    total = 0
    negatives = 0
    for value in values:
        if value < smallest:
            smallest = value
        if value > largest:
            largest = value
        total += value
        if value < 0:
            negatives += 1
    return f"n={len(values)} min={smallest} max={largest} sum={total} neg={negatives}"


def format_table_row(cells: list[str]) -> str:
    return " | ".join(cell.ljust(8) for cell in cells)


def _limit_problem(name: str, text: str, low: int, high: int) -> str:
    if not text or not text.isdigit():
        return f"{name} must be an integer"
    value = int(text)
    if value < low or value > high:
        return f"{name} out of range"
    return ""


def check_limits(port_text: str, timeout_text: str) -> str:
    problem = _limit_problem("port", port_text, 1, 65535)
    if problem:
        return problem
    return _limit_problem("timeout", timeout_text, 1, 3600)


def first_error_line(lines: list[str]) -> int:
    for index, line in enumerate(lines):
        if "ERROR" in line:
            return index
    return -1


def rank_services(names: list[str], scores: list[int]) -> list[str]:
    n = min(len(names), len(scores))
    order = sorted(range(n), key=lambda i: (-scores[i], names[i]))
    return [names[i] for i in order]


def bill_summary(units: int, rate_cents: int, discount_pct: int) -> str:
    if units < 0 or rate_cents < 0:
        return "invalid"
    subtotal = units * rate_cents
    if discount_pct <= 0:
        label, total = "no discount", subtotal
    elif discount_pct >= 100:
        label, total = "free", 0
    else:
        label, total = "discounted", subtotal - (subtotal * discount_pct) // 100
    return f"{label} subtotal={subtotal} total={total}"


def parse_kv(text: str) -> str:
    result: dict[str, str] = {}
    for piece in text.split(","):
        key, sep, value = piece.partition("=")
        if sep and key:
            result[key] = value
    return ";".join(f"{key}={result[key]}" for key in sorted(result))


def _range_piece(start: int, end: int) -> str:
    if start == end:
        return str(start)
    return str(start) + "-" + str(end)


def compact_ranges(values: list[int]) -> str:
    if not values:
        return ""
    parts = []
    start = values[0]
    end = values[0]
    for value in values[1:]:
        if value == end + 1:
            end = value
        else:
            parts.append(_range_piece(start, end))
            start = value
            end = value
    parts.append(_range_piece(start, end))
    return ",".join(parts)


# ---------------------------------------------------------------------------
# Families
# ---------------------------------------------------------------------------

DEPLOY_GATE = Family(
    name="deploy_gate",
    skill="guard_clauses",
    difficulty="hard",
    io={"args": ["str", "bool", "int", "bool"], "returns": "str"},
    spec="""
`deploy_gate` decides whether a deploy may proceed. The current version is
correct and every one of these rules must still hold, in this order:

1. An environment other than "prod", "staging" or "dev" gives
   "blocked: unknown env".
2. A change freeze blocks "prod" only: "blocked: change freeze".
3. An unhealthy target gives "blocked: unhealthy".
4. "prod" needs at least 2 approvals, otherwise "blocked: needs 2 approvals".
5. "staging" needs at least 1, otherwise "blocked: needs 1 approval".
6. Anything else is "allowed".

The logic is buried in a pyramid of nested conditionals, so reading rule 4 means
tracking four enclosing branches. Refactor it into a flat sequence of guard
clauses that reject early and return "allowed" at the end, keeping the order of
the checks exactly as it is.
""",
    signatures={
        "python": (
            "def deploy_gate(env: str, healthy: bool, approvals: int, frozen: bool) -> str:"
        ),
        "typescript": (
            "function deployGate(env: string, healthy: boolean, approvals: number, "
            "frozen: boolean): string {"
        ),
        "go": "func DeployGate(env string, healthy bool, approvals int, frozen bool) string {",
        "rust": (
            "fn deploy_gate(env: &str, healthy: bool, approvals: i64, frozen: bool) -> String {"
        ),
    },
    inputs=[
        ["prod", True, 2, False],
        ["prod", True, 1, False],
        ["prod", True, 5, True],
        ["prod", False, 5, False],
        ["prod", False, 0, True],
        ["staging", True, 0, False],
        ["staging", True, 1, False],
        ["staging", True, 3, True],
        ["dev", True, 0, False],
        ["dev", False, 0, False],
        ["qa", True, 5, False],
        ["", True, 5, False],
    ],
    reference=deploy_gate,
    extras={
        "goal": (
            "Flatten the nesting into guard clauses: each rejection returns "
            "immediately, and the success path is the last line."
        )
    },
    lang_extras={
        "python": {
            "original_code": dedent_code('''
                def deploy_gate(env: str, healthy: bool, approvals: int, frozen: bool) -> str:
                    if env == "prod" or env == "staging" or env == "dev":
                        if not (frozen and env == "prod"):
                            if healthy:
                                if env == "prod":
                                    if approvals < 2:
                                        return "blocked: needs 2 approvals"
                                    else:
                                        return "allowed"
                                else:
                                    if env == "staging":
                                        if approvals < 1:
                                            return "blocked: needs 1 approval"
                                        else:
                                            return "allowed"
                                    else:
                                        return "allowed"
                            else:
                                return "blocked: unhealthy"
                        else:
                            return "blocked: change freeze"
                    else:
                        return "blocked: unknown env"
            '''),
            "structure": {
                "max_matches": [
                    {
                        "pattern": r"\belse\b",
                        "max": 1,
                        "reason": "guard clauses return early instead of nesting an else",
                    }
                ],
                "max_lines": 22,
            },
        },
        "typescript": {
            "original_code": dedent_code('''
                function deployGate(env: string, healthy: boolean, approvals: number, frozen: boolean): string {
                    if (env === "prod" || env === "staging" || env === "dev") {
                        if (!(frozen && env === "prod")) {
                            if (healthy) {
                                if (env === "prod") {
                                    if (approvals < 2) {
                                        return "blocked: needs 2 approvals";
                                    } else {
                                        return "allowed";
                                    }
                                } else {
                                    if (env === "staging") {
                                        if (approvals < 1) {
                                            return "blocked: needs 1 approval";
                                        } else {
                                            return "allowed";
                                        }
                                    } else {
                                        return "allowed";
                                    }
                                }
                            } else {
                                return "blocked: unhealthy";
                            }
                        } else {
                            return "blocked: change freeze";
                        }
                    } else {
                        return "blocked: unknown env";
                    }
                }
            '''),
            "structure": {
                "max_matches": [
                    {
                        "pattern": r"\belse\b",
                        "max": 1,
                        "reason": "guard clauses return early instead of nesting an else",
                    }
                ],
                "max_lines": 24,
            },
        },
        "go": {
            "original_code": dedent_code('''
                func DeployGate(env string, healthy bool, approvals int, frozen bool) string {
                    if env == "prod" || env == "staging" || env == "dev" {
                        if !(frozen && env == "prod") {
                            if healthy {
                                if env == "prod" {
                                    if approvals < 2 {
                                        return "blocked: needs 2 approvals"
                                    } else {
                                        return "allowed"
                                    }
                                } else {
                                    if env == "staging" {
                                        if approvals < 1 {
                                            return "blocked: needs 1 approval"
                                        } else {
                                            return "allowed"
                                        }
                                    } else {
                                        return "allowed"
                                    }
                                }
                            } else {
                                return "blocked: unhealthy"
                            }
                        } else {
                            return "blocked: change freeze"
                        }
                    } else {
                        return "blocked: unknown env"
                    }
                }
            '''),
            "structure": {
                "max_matches": [
                    {
                        "pattern": r"\belse\b",
                        "max": 1,
                        "reason": "guard clauses return early instead of nesting an else",
                    }
                ],
                "max_lines": 26,
            },
        },
        "rust": {
            "original_code": dedent_code('''
                fn deploy_gate(env: &str, healthy: bool, approvals: i64, frozen: bool) -> String {
                    if env == "prod" || env == "staging" || env == "dev" {
                        if !(frozen && env == "prod") {
                            if healthy {
                                if env == "prod" {
                                    if approvals < 2 {
                                        return "blocked: needs 2 approvals".to_string();
                                    } else {
                                        return "allowed".to_string();
                                    }
                                } else {
                                    if env == "staging" {
                                        if approvals < 1 {
                                            return "blocked: needs 1 approval".to_string();
                                        } else {
                                            return "allowed".to_string();
                                        }
                                    } else {
                                        return "allowed".to_string();
                                    }
                                }
                            } else {
                                return "blocked: unhealthy".to_string();
                            }
                        } else {
                            return "blocked: change freeze".to_string();
                        }
                    } else {
                        return "blocked: unknown env".to_string();
                    }
                }
            '''),
            "structure": {
                "max_matches": [
                    {
                        "pattern": r"\belse\b",
                        "max": 1,
                        "reason": "guard clauses return early instead of nesting an else",
                    }
                ],
                "max_lines": 26,
            },
        },
    },
    solutions={
        "python": dedent_code('''
            def deploy_gate(env: str, healthy: bool, approvals: int, frozen: bool) -> str:
                if env not in ("prod", "staging", "dev"):
                    return "blocked: unknown env"
                if frozen and env == "prod":
                    return "blocked: change freeze"
                if not healthy:
                    return "blocked: unhealthy"
                if env == "prod" and approvals < 2:
                    return "blocked: needs 2 approvals"
                if env == "staging" and approvals < 1:
                    return "blocked: needs 1 approval"
                return "allowed"
        '''),
        "typescript": dedent_code('''
            export function deployGate(
                env: string,
                healthy: boolean,
                approvals: number,
                frozen: boolean,
            ): string {
                if (env !== "prod" && env !== "staging" && env !== "dev") {
                    return "blocked: unknown env";
                }
                if (frozen && env === "prod") return "blocked: change freeze";
                if (!healthy) return "blocked: unhealthy";
                if (env === "prod" && approvals < 2) return "blocked: needs 2 approvals";
                if (env === "staging" && approvals < 1) return "blocked: needs 1 approval";
                return "allowed";
            }
        '''),
        "go": dedent_code('''
            package main

            func DeployGate(env string, healthy bool, approvals int, frozen bool) string {
                if env != "prod" && env != "staging" && env != "dev" {
                    return "blocked: unknown env"
                }
                if frozen && env == "prod" {
                    return "blocked: change freeze"
                }
                if !healthy {
                    return "blocked: unhealthy"
                }
                if env == "prod" && approvals < 2 {
                    return "blocked: needs 2 approvals"
                }
                if env == "staging" && approvals < 1 {
                    return "blocked: needs 1 approval"
                }
                return "allowed"
            }
        '''),
        "rust": dedent_code('''
            fn deploy_gate(env: &str, healthy: bool, approvals: i64, frozen: bool) -> String {
                if env != "prod" && env != "staging" && env != "dev" {
                    return "blocked: unknown env".to_string();
                }
                if frozen && env == "prod" {
                    return "blocked: change freeze".to_string();
                }
                if !healthy {
                    return "blocked: unhealthy".to_string();
                }
                if env == "prod" && approvals < 2 {
                    return "blocked: needs 2 approvals".to_string();
                }
                if env == "staging" && approvals < 1 {
                    return "blocked: needs 1 approval".to_string();
                }
                "allowed".to_string()
            }
        '''),
    },
)


NEXT_STATE = Family(
    name="next_state",
    skill="state_machine",
    difficulty="hard",
    io={"args": ["str", "str"], "returns": "str"},
    spec="""
`next_state` advances a job's state machine. The behavior is correct and must
not change:

- Known states are idle, running, paused, done, failed and cancelled. Any other
  state returns "invalid".
- The transitions are: idle+start to running; running+pause to paused;
  running+finish to done; running+fail to failed; paused+resume to running;
  paused+cancel to cancelled; failed+retry to running.
- A known state with an event that has no transition stays where it is: the
  state itself is returned.

Today this is a chain of comparisons, one branch per transition, so adding a
transition means adding a branch. Refactor it so the transitions are *data* —
a table keyed by state and event, or the language's idiomatic match — leaving
only the unknown-state check and the lookup as control flow.
""",
    signatures={
        "python": "def next_state(state: str, event: str) -> str:",
        "typescript": "function nextState(state: string, event: string): string {",
        "go": "func NextState(state string, event string) string {",
        "rust": "fn next_state(state: &str, event: &str) -> String {",
    },
    inputs=[
        ["idle", "start"],
        ["idle", "finish"],
        ["running", "pause"],
        ["running", "finish"],
        ["running", "fail"],
        ["paused", "resume"],
        ["paused", "cancel"],
        ["failed", "retry"],
        ["done", "start"],
        ["cancelled", "retry"],
        ["sleeping", "start"],
        ["", ""],
    ],
    reference=next_state,
    extras={
        "goal": (
            "Turn the transition chain into a lookup table so a new transition "
            "is a new row, not a new branch."
        )
    },
    lang_extras={
        "python": {
            "original_code": dedent_code('''
                def next_state(state: str, event: str) -> str:
                    if state == "idle":
                        if event == "start":
                            return "running"
                        return state
                    elif state == "running":
                        if event == "pause":
                            return "paused"
                        elif event == "finish":
                            return "done"
                        elif event == "fail":
                            return "failed"
                        return state
                    elif state == "paused":
                        if event == "resume":
                            return "running"
                        elif event == "cancel":
                            return "cancelled"
                        return state
                    elif state == "failed":
                        if event == "retry":
                            return "running"
                        return state
                    elif state == "done":
                        return state
                    elif state == "cancelled":
                        return state
                    else:
                        return "invalid"
            '''),
            "structure": {
                "max_matches": [
                    {
                        "pattern": r"\bif\b|\belif\b",
                        "max": 3,
                        "reason": "the per-transition branches should be gone",
                    }
                ],
                "require_any": [
                    {
                        "patterns": [r"\{[^{}]*:", r"\bmatch\b", r"dict\("],
                        "reason": "the transitions should live in a table",
                    }
                ],
                "max_lines": 26,
            },
        },
        "typescript": {
            "original_code": dedent_code('''
                function nextState(state: string, event: string): string {
                    if (state === "idle") {
                        if (event === "start") return "running";
                        return state;
                    } else if (state === "running") {
                        if (event === "pause") return "paused";
                        else if (event === "finish") return "done";
                        else if (event === "fail") return "failed";
                        return state;
                    } else if (state === "paused") {
                        if (event === "resume") return "running";
                        else if (event === "cancel") return "cancelled";
                        return state;
                    } else if (state === "failed") {
                        if (event === "retry") return "running";
                        return state;
                    } else if (state === "done") {
                        return state;
                    } else if (state === "cancelled") {
                        return state;
                    }
                    return "invalid";
                }
            '''),
            "structure": {
                "max_matches": [
                    {
                        "pattern": r"\bif\b",
                        "max": 3,
                        "reason": "the per-transition branches should be gone",
                    }
                ],
                "require_any": [
                    {
                        "patterns": [r"Record<", r"new Map", r"\{[^{}]*:"],
                        "reason": "the transitions should live in a table",
                    }
                ],
                "max_lines": 26,
            },
        },
        "go": {
            "original_code": dedent_code('''
                func NextState(state string, event string) string {
                    if state == "idle" {
                        if event == "start" {
                            return "running"
                        }
                        return state
                    } else if state == "running" {
                        if event == "pause" {
                            return "paused"
                        } else if event == "finish" {
                            return "done"
                        } else if event == "fail" {
                            return "failed"
                        }
                        return state
                    } else if state == "paused" {
                        if event == "resume" {
                            return "running"
                        } else if event == "cancel" {
                            return "cancelled"
                        }
                        return state
                    } else if state == "failed" {
                        if event == "retry" {
                            return "running"
                        }
                        return state
                    } else if state == "done" {
                        return state
                    } else if state == "cancelled" {
                        return state
                    }
                    return "invalid"
                }
            '''),
            "structure": {
                "max_matches": [
                    {
                        "pattern": r"\bif\b",
                        "max": 3,
                        "reason": "the per-transition branches should be gone",
                    }
                ],
                "require_any": [
                    {
                        "patterns": [r"map\[string\]", r"\bswitch\b"],
                        "reason": "the transitions should live in a map or a switch",
                    }
                ],
                "max_lines": 30,
            },
        },
        "rust": {
            "original_code": dedent_code('''
                fn next_state(state: &str, event: &str) -> String {
                    if state == "idle" {
                        if event == "start" {
                            return "running".to_string();
                        }
                        return state.to_string();
                    } else if state == "running" {
                        if event == "pause" {
                            return "paused".to_string();
                        } else if event == "finish" {
                            return "done".to_string();
                        } else if event == "fail" {
                            return "failed".to_string();
                        }
                        return state.to_string();
                    } else if state == "paused" {
                        if event == "resume" {
                            return "running".to_string();
                        } else if event == "cancel" {
                            return "cancelled".to_string();
                        }
                        return state.to_string();
                    } else if state == "failed" {
                        if event == "retry" {
                            return "running".to_string();
                        }
                        return state.to_string();
                    } else if state == "done" {
                        return state.to_string();
                    } else if state == "cancelled" {
                        return state.to_string();
                    }
                    "invalid".to_string()
                }
            '''),
            "structure": {
                "max_matches": [
                    {
                        "pattern": r"\bif\b",
                        "max": 3,
                        "reason": "the per-transition branches should be gone",
                    }
                ],
                "require_any": [
                    {
                        "patterns": [r"\bmatch\b", r"HashMap"],
                        "reason": "the transitions should live in a match or a map",
                    }
                ],
                "max_lines": 30,
            },
        },
    },
    solutions={
        "python": dedent_code('''
            _STATES = ("idle", "running", "paused", "done", "failed", "cancelled")
            _TRANSITIONS = {
                ("idle", "start"): "running",
                ("running", "pause"): "paused",
                ("running", "finish"): "done",
                ("running", "fail"): "failed",
                ("paused", "resume"): "running",
                ("paused", "cancel"): "cancelled",
                ("failed", "retry"): "running",
            }


            def next_state(state: str, event: str) -> str:
                if state not in _STATES:
                    return "invalid"
                return _TRANSITIONS.get((state, event), state)
        '''),
        "typescript": dedent_code('''
            const STATES = ["idle", "running", "paused", "done", "failed", "cancelled"];
            const TRANSITIONS: Record<string, string> = {
                "idle|start": "running",
                "running|pause": "paused",
                "running|finish": "done",
                "running|fail": "failed",
                "paused|resume": "running",
                "paused|cancel": "cancelled",
                "failed|retry": "running",
            };

            export function nextState(state: string, event: string): string {
                if (!STATES.includes(state)) return "invalid";
                return TRANSITIONS[`${state}|${event}`] ?? state;
            }
        '''),
        "go": dedent_code('''
            package main

            var states = map[string]bool{
                "idle": true, "running": true, "paused": true,
                "done": true, "failed": true, "cancelled": true,
            }

            var transitions = map[string]string{
                "idle|start":     "running",
                "running|pause":  "paused",
                "running|finish": "done",
                "running|fail":   "failed",
                "paused|resume":  "running",
                "paused|cancel":  "cancelled",
                "failed|retry":   "running",
            }

            func NextState(state string, event string) string {
                if !states[state] {
                    return "invalid"
                }
                if next, ok := transitions[state+"|"+event]; ok {
                    return next
                }
                return state
            }
        '''),
        "rust": dedent_code('''
            fn next_state(state: &str, event: &str) -> String {
                let states = ["idle", "running", "paused", "done", "failed", "cancelled"];
                if !states.contains(&state) {
                    return "invalid".to_string();
                }
                let next = match (state, event) {
                    ("idle", "start") => "running",
                    ("running", "pause") => "paused",
                    ("running", "finish") => "done",
                    ("running", "fail") => "failed",
                    ("paused", "resume") => "running",
                    ("paused", "cancel") => "cancelled",
                    ("failed", "retry") => "running",
                    _ => state,
                };
                next.to_string()
            }
        '''),
    },
)


SUMMARIZE_SERIES = Family(
    name="summarize_series",
    skill="single_pass",
    difficulty="hard",
    io={"args": ["list<int>"], "returns": "str"},
    spec="""
`summarize_series` renders a one-line summary of a sample.

- An empty sample gives exactly "n=0".
- Otherwise the result is
  "n=<count> min=<smallest> max=<largest> sum=<total> neg=<how many are below zero>",
  with single spaces between the fields and no trailing space.

The current version walks the sample four separate times, once per statistic.
Refactor it to compute the whole summary in a single traversal (or with the
language's own aggregate helpers), without changing the output by a character.
""",
    signatures={
        "python": "def summarize_series(values: list[int]) -> str:",
        "typescript": "function summarizeSeries(values: number[]): string {",
        "go": "func SummarizeSeries(values []int) string {",
        "rust": "fn summarize_series(values: &[i64]) -> String {",
    },
    inputs=[
        [1, 2, 3],
        [-5, 0, 5],
        [],
        [7],
        [-1, -2, -3],
        [0, 0, 0],
        [10, -10, 20, -20],
        [100],
        [3, 1, 4, 1, 5, 9, 2, 6],
    ],
    reference=summarize_series,
    extras={
        "goal": (
            "One traversal instead of four, with the rendered output unchanged."
        )
    },
    lang_extras={
        "python": {
            "original_code": dedent_code('''
                def summarize_series(values: list[int]) -> str:
                    if len(values) == 0:
                        return "n=0"
                    smallest = values[0]
                    for value in values:
                        if value < smallest:
                            smallest = value
                    largest = values[0]
                    for value in values:
                        if value > largest:
                            largest = value
                    total = 0
                    for value in values:
                        total = total + value
                    negatives = 0
                    for value in values:
                        if value < 0:
                            negatives = negatives + 1
                    return f"n={len(values)} min={smallest} max={largest} sum={total} neg={negatives}"
            '''),
            "structure": {
                "max_matches": [
                    {
                        "pattern": r"\bfor\b|\bwhile\b",
                        "max": 1,
                        "reason": "the sample should be walked once, not once per statistic",
                    }
                ],
                "max_lines": 22,
            },
        },
        "typescript": {
            "original_code": dedent_code('''
                function summarizeSeries(values: number[]): string {
                    if (values.length === 0) return "n=0";
                    let smallest = values[0];
                    for (const value of values) {
                        if (value < smallest) smallest = value;
                    }
                    let largest = values[0];
                    for (const value of values) {
                        if (value > largest) largest = value;
                    }
                    let total = 0;
                    for (const value of values) {
                        total = total + value;
                    }
                    let negatives = 0;
                    for (const value of values) {
                        if (value < 0) negatives = negatives + 1;
                    }
                    return `n=${values.length} min=${smallest} max=${largest} sum=${total} neg=${negatives}`;
                }
            '''),
            "structure": {
                "max_matches": [
                    {
                        "pattern": r"\bfor\b|\bwhile\b",
                        "max": 1,
                        "reason": "the sample should be walked once, not once per statistic",
                    }
                ],
                "max_lines": 22,
            },
        },
        "go": {
            "original_code": dedent_code('''
                func SummarizeSeries(values []int) string {
                    if len(values) == 0 {
                        return "n=0"
                    }
                    smallest := values[0]
                    for _, value := range values {
                        if value < smallest {
                            smallest = value
                        }
                    }
                    largest := values[0]
                    for _, value := range values {
                        if value > largest {
                            largest = value
                        }
                    }
                    total := 0
                    for _, value := range values {
                        total = total + value
                    }
                    negatives := 0
                    for _, value := range values {
                        if value < 0 {
                            negatives = negatives + 1
                        }
                    }
                    return fmt.Sprintf("n=%d min=%d max=%d sum=%d neg=%d", len(values), smallest, largest, total, negatives)
                }
            '''),
            "structure": {
                "max_matches": [
                    {
                        "pattern": r"\bfor\b",
                        "max": 1,
                        "reason": "the sample should be walked once, not once per statistic",
                    }
                ],
                "max_lines": 26,
            },
        },
        "rust": {
            "original_code": dedent_code('''
                fn summarize_series(values: &[i64]) -> String {
                    if values.is_empty() {
                        return "n=0".to_string();
                    }
                    let mut smallest = values[0];
                    for &value in values {
                        if value < smallest {
                            smallest = value;
                        }
                    }
                    let mut largest = values[0];
                    for &value in values {
                        if value > largest {
                            largest = value;
                        }
                    }
                    let mut total: i64 = 0;
                    for &value in values {
                        total = total + value;
                    }
                    let mut negatives: i64 = 0;
                    for &value in values {
                        if value < 0 {
                            negatives = negatives + 1;
                        }
                    }
                    format!(
                        "n={} min={} max={} sum={} neg={}",
                        values.len(), smallest, largest, total, negatives
                    )
                }
            '''),
            "structure": {
                "max_matches": [
                    {
                        "pattern": r"\bfor\b|\bwhile\b",
                        "max": 1,
                        "reason": "the sample should be walked once, not once per statistic",
                    }
                ],
                "max_lines": 28,
            },
        },
    },
    solutions={
        "python": dedent_code('''
            def summarize_series(values: list[int]) -> str:
                if not values:
                    return "n=0"
                smallest = values[0]
                largest = values[0]
                total = 0
                negatives = 0
                for value in values:
                    if value < smallest:
                        smallest = value
                    if value > largest:
                        largest = value
                    total += value
                    if value < 0:
                        negatives += 1
                return f"n={len(values)} min={smallest} max={largest} sum={total} neg={negatives}"
        '''),
        "typescript": dedent_code('''
            export function summarizeSeries(values: number[]): string {
                if (values.length === 0) return "n=0";
                let smallest = values[0];
                let largest = values[0];
                let total = 0;
                let negatives = 0;
                for (const value of values) {
                    if (value < smallest) smallest = value;
                    if (value > largest) largest = value;
                    total += value;
                    if (value < 0) negatives += 1;
                }
                return `n=${values.length} min=${smallest} max=${largest} sum=${total} neg=${negatives}`;
            }
        '''),
        "go": dedent_code('''
            package main

            import "fmt"

            func SummarizeSeries(values []int) string {
                if len(values) == 0 {
                    return "n=0"
                }
                smallest, largest, total, negatives := values[0], values[0], 0, 0
                for _, value := range values {
                    if value < smallest {
                        smallest = value
                    }
                    if value > largest {
                        largest = value
                    }
                    total += value
                    if value < 0 {
                        negatives++
                    }
                }
                return fmt.Sprintf("n=%d min=%d max=%d sum=%d neg=%d", len(values), smallest, largest, total, negatives)
            }
        '''),
        "rust": dedent_code('''
            fn summarize_series(values: &[i64]) -> String {
                if values.is_empty() {
                    return "n=0".to_string();
                }
                let mut smallest = values[0];
                let mut largest = values[0];
                let mut total: i64 = 0;
                let mut negatives: i64 = 0;
                for &value in values {
                    if value < smallest {
                        smallest = value;
                    }
                    if value > largest {
                        largest = value;
                    }
                    total += value;
                    if value < 0 {
                        negatives += 1;
                    }
                }
                format!(
                    "n={} min={} max={} sum={} neg={}",
                    values.len(), smallest, largest, total, negatives
                )
            }
        '''),
    },
)


FORMAT_TABLE_ROW = Family(
    name="format_table_row",
    skill="string_building",
    difficulty="hard",
    io={"args": ["list<str>"], "returns": "str"},
    spec="""
`format_table_row` renders one row of a fixed-width text table.

- Every cell is padded on the right with spaces to a width of 8. A cell already
  8 characters or longer is left alone.
- Padded cells are joined with " | " (space, pipe, space) and there is no
  separator after the last cell, so the row never ends with " | ".
- An empty list of cells renders as the empty string.

The current version concatenates into an accumulator, pads with its own loop,
and special-cases the last index to avoid a trailing separator. Refactor it to
pad each cell and let the language's join do the separating, so the
last-element special case disappears.
""",
    signatures={
        "python": "def format_table_row(cells: list[str]) -> str:",
        "typescript": "function formatTableRow(cells: string[]): string {",
        "go": "func FormatTableRow(cells []string) string {",
        "rust": "fn format_table_row(cells: &[&str]) -> String {",
    },
    inputs=[
        ["a", "b"],
        ["one"],
        [],
        ["exactly8", "x"],
        ["averylongcell", "b"],
        ["", ""],
        ["svc", "prod", "ok"],
        ["12345678"],
    ],
    reference=format_table_row,
    extras={
        "goal": (
            "Pad each cell, then join — no accumulator, no last-index special "
            "case, no hand-written padding loop."
        )
    },
    lang_extras={
        "python": {
            "original_code": dedent_code('''
                def format_table_row(cells: list[str]) -> str:
                    out = ""
                    for index in range(len(cells)):
                        cell = cells[index]
                        padded = cell
                        while len(padded) < 8:
                            padded = padded + " "
                        out = out + padded
                        if index != len(cells) - 1:
                            out = out + " | "
                    return out
            '''),
            "structure": {
                "max_matches": [
                    {
                        "pattern": r"\bwhile\b",
                        "max": 0,
                        "reason": "padding is a library call, not a hand-written loop",
                    }
                ],
                "require_any": [
                    {
                        "patterns": [r"\.join\("],
                        "reason": "join should place the separators",
                    }
                ],
                "max_lines": 12,
            },
        },
        "typescript": {
            "original_code": dedent_code('''
                function formatTableRow(cells: string[]): string {
                    let out = "";
                    for (let index = 0; index < cells.length; index++) {
                        let padded = cells[index];
                        while (padded.length < 8) {
                            padded = padded + " ";
                        }
                        out = out + padded;
                        if (index !== cells.length - 1) {
                            out = out + " | ";
                        }
                    }
                    return out;
                }
            '''),
            "structure": {
                "max_matches": [
                    {
                        "pattern": r"\bwhile\b",
                        "max": 0,
                        "reason": "padding is a library call, not a hand-written loop",
                    }
                ],
                "require_any": [
                    {
                        "patterns": [r"\.join\("],
                        "reason": "join should place the separators",
                    }
                ],
                "max_lines": 12,
            },
        },
        "go": {
            "original_code": dedent_code('''
                func FormatTableRow(cells []string) string {
                    out := ""
                    for index := 0; index < len(cells); index++ {
                        padded := cells[index]
                        for len(padded) < 8 {
                            padded = padded + " "
                        }
                        out = out + padded
                        if index != len(cells)-1 {
                            out = out + " | "
                        }
                    }
                    return out
                }
            '''),
            "structure": {
                "max_matches": [
                    {
                        "pattern": r"\bfor\b",
                        "max": 1,
                        "reason": "padding is a library call, not a hand-written loop",
                    }
                ],
                "require_any": [
                    {
                        "patterns": [r"strings\.Join"],
                        "reason": "join should place the separators",
                    }
                ],
                "max_lines": 16,
            },
        },
        "rust": {
            "original_code": dedent_code('''
                fn format_table_row(cells: &[&str]) -> String {
                    let mut out = String::new();
                    for index in 0..cells.len() {
                        let mut padded = cells[index].to_string();
                        while padded.len() < 8 {
                            padded.push(' ');
                        }
                        out.push_str(&padded);
                        if index != cells.len() - 1 {
                            out.push_str(" | ");
                        }
                    }
                    out
                }
            '''),
            "structure": {
                "max_matches": [
                    {
                        "pattern": r"\bwhile\b",
                        "max": 0,
                        "reason": "padding is a library call, not a hand-written loop",
                    }
                ],
                "require_any": [
                    {
                        "patterns": [r"\.join\("],
                        "reason": "join should place the separators",
                    }
                ],
                "max_lines": 12,
            },
        },
    },
    solutions={
        "python": dedent_code('''
            def format_table_row(cells: list[str]) -> str:
                return " | ".join(cell.ljust(8) for cell in cells)
        '''),
        "typescript": dedent_code('''
            export function formatTableRow(cells: string[]): string {
                return cells.map((cell) => cell.padEnd(8)).join(" | ");
            }
        '''),
        "go": dedent_code('''
            package main

            import (
                "fmt"
                "strings"
            )

            func FormatTableRow(cells []string) string {
                padded := make([]string, len(cells))
                for i, cell := range cells {
                    padded[i] = fmt.Sprintf("%-8s", cell)
                }
                return strings.Join(padded, " | ")
            }
        '''),
        "rust": dedent_code('''
            fn format_table_row(cells: &[&str]) -> String {
                cells
                    .iter()
                    .map(|cell| format!("{:<8}", cell))
                    .collect::<Vec<String>>()
                    .join(" | ")
            }
        '''),
    },
)


CHECK_LIMITS = Family(
    name="check_limits",
    skill="extract_helper",
    difficulty="hard",
    io={"args": ["str", "str"], "returns": "str"},
    spec="""
`check_limits` validates two configuration values and reports the first
problem it finds.

- The port is checked first, then the timeout.
- A value that is empty or not made entirely of digits gives
  "<name> must be an integer".
- A port outside 1..65535, or a timeout outside 1..3600, gives
  "<name> out of range".
- `<name>` is "port" or "timeout".
- When both are fine the result is the empty string.

The two checks are the same logic written out twice, so the messages and the
rules live in two places. Refactor so that logic exists once, parameterised by
name and bounds, and `check_limits` just applies it to each value in order.
""",
    signatures={
        "python": "def check_limits(port_text: str, timeout_text: str) -> str:",
        "typescript": "function checkLimits(portText: string, timeoutText: string): string {",
        "go": "func CheckLimits(portText string, timeoutText string) string {",
        "rust": "fn check_limits(port_text: &str, timeout_text: &str) -> String {",
    },
    inputs=[
        ["8080", "30"],
        ["", "30"],
        ["80x", "30"],
        ["0", "30"],
        ["70000", "30"],
        ["8080", ""],
        ["8080", "abc"],
        ["8080", "0"],
        ["8080", "4000"],
        ["1", "3600"],
        ["65535", "1"],
        ["", ""],
    ],
    reference=check_limits,
    extras={
        "goal": (
            "Extract the duplicated check into one helper taking the field "
            "name and its bounds; call it twice."
        )
    },
    lang_extras={
        "python": {
            "original_code": dedent_code('''
                def check_limits(port_text: str, timeout_text: str) -> str:
                    if not port_text or not port_text.isdigit():
                        return "port must be an integer"
                    port = int(port_text)
                    if port < 1 or port > 65535:
                        return "port out of range"
                    if not timeout_text or not timeout_text.isdigit():
                        return "timeout must be an integer"
                    timeout = int(timeout_text)
                    if timeout < 1 or timeout > 3600:
                        return "timeout out of range"
                    return ""
            '''),
            "structure": {
                "max_matches": [
                    {
                        "pattern": r"must be an integer",
                        "max": 1,
                        "reason": "the message should be written once, in the shared check",
                    },
                    {
                        "pattern": r"out of range",
                        "max": 1,
                        "reason": "the message should be written once, in the shared check",
                    },
                ],
                "max_lines": 20,
            },
        },
        "typescript": {
            "original_code": dedent_code('''
                function checkLimits(portText: string, timeoutText: string): string {
                    if (portText.length === 0 || !/^[0-9]+$/.test(portText)) {
                        return "port must be an integer";
                    }
                    const port = parseInt(portText, 10);
                    if (port < 1 || port > 65535) {
                        return "port out of range";
                    }
                    if (timeoutText.length === 0 || !/^[0-9]+$/.test(timeoutText)) {
                        return "timeout must be an integer";
                    }
                    const timeout = parseInt(timeoutText, 10);
                    if (timeout < 1 || timeout > 3600) {
                        return "timeout out of range";
                    }
                    return "";
                }
            '''),
            "structure": {
                "max_matches": [
                    {
                        "pattern": r"must be an integer",
                        "max": 1,
                        "reason": "the message should be written once, in the shared check",
                    },
                    {
                        "pattern": r"out of range",
                        "max": 1,
                        "reason": "the message should be written once, in the shared check",
                    },
                ],
                "max_lines": 24,
            },
        },
        "go": {
            "original_code": dedent_code('''
                func CheckLimits(portText string, timeoutText string) string {
                    if len(portText) == 0 {
                        return "port must be an integer"
                    }
                    for _, ch := range portText {
                        if ch < '0' || ch > '9' {
                            return "port must be an integer"
                        }
                    }
                    port, err := strconv.Atoi(portText)
                    if err != nil || port < 1 || port > 65535 {
                        return "port out of range"
                    }
                    if len(timeoutText) == 0 {
                        return "timeout must be an integer"
                    }
                    for _, ch := range timeoutText {
                        if ch < '0' || ch > '9' {
                            return "timeout must be an integer"
                        }
                    }
                    timeout, err2 := strconv.Atoi(timeoutText)
                    if err2 != nil || timeout < 1 || timeout > 3600 {
                        return "timeout out of range"
                    }
                    return ""
                }
            '''),
            "structure": {
                "max_matches": [
                    {
                        "pattern": r"must be an integer",
                        "max": 2,
                        "reason": "the message should be written once, in the shared check",
                    },
                    {
                        "pattern": r"out of range",
                        "max": 1,
                        "reason": "the message should be written once, in the shared check",
                    },
                ],
                "max_lines": 32,
            },
        },
        "rust": {
            "original_code": dedent_code('''
                fn check_limits(port_text: &str, timeout_text: &str) -> String {
                    if port_text.is_empty() || !port_text.chars().all(|c| c.is_ascii_digit()) {
                        return "port must be an integer".to_string();
                    }
                    let port: i64 = port_text.parse().unwrap_or(-1);
                    if port < 1 || port > 65535 {
                        return "port out of range".to_string();
                    }
                    if timeout_text.is_empty() || !timeout_text.chars().all(|c| c.is_ascii_digit()) {
                        return "timeout must be an integer".to_string();
                    }
                    let timeout: i64 = timeout_text.parse().unwrap_or(-1);
                    if timeout < 1 || timeout > 3600 {
                        return "timeout out of range".to_string();
                    }
                    String::new()
                }
            '''),
            "structure": {
                "max_matches": [
                    {
                        "pattern": r"must be an integer",
                        "max": 1,
                        "reason": "the message should be written once, in the shared check",
                    },
                    {
                        "pattern": r"out of range",
                        "max": 1,
                        "reason": "the message should be written once, in the shared check",
                    },
                ],
                "max_lines": 24,
            },
        },
    },
    solutions={
        "python": dedent_code('''
            def _problem(name: str, text: str, low: int, high: int) -> str:
                if not text or not text.isdigit():
                    return f"{name} must be an integer"
                value = int(text)
                if value < low or value > high:
                    return f"{name} out of range"
                return ""


            def check_limits(port_text: str, timeout_text: str) -> str:
                problem = _problem("port", port_text, 1, 65535)
                if problem:
                    return problem
                return _problem("timeout", timeout_text, 1, 3600)
        '''),
        "typescript": dedent_code('''
            function problem(name: string, text: string, low: number, high: number): string {
                if (text.length === 0 || !/^[0-9]+$/.test(text)) {
                    return `${name} must be an integer`;
                }
                const value = parseInt(text, 10);
                if (value < low || value > high) return `${name} out of range`;
                return "";
            }

            export function checkLimits(portText: string, timeoutText: string): string {
                const first = problem("port", portText, 1, 65535);
                if (first !== "") return first;
                return problem("timeout", timeoutText, 1, 3600);
            }
        '''),
        "go": dedent_code('''
            package main

            import (
                "fmt"
                "strconv"
            )

            func limitProblem(name string, text string, low int, high int) string {
                if len(text) == 0 {
                    return fmt.Sprintf("%s must be an integer", name)
                }
                for _, ch := range text {
                    if ch < '0' || ch > '9' {
                        return fmt.Sprintf("%s must be an integer", name)
                    }
                }
                value, err := strconv.Atoi(text)
                if err != nil || value < low || value > high {
                    return fmt.Sprintf("%s out of range", name)
                }
                return ""
            }

            func CheckLimits(portText string, timeoutText string) string {
                if first := limitProblem("port", portText, 1, 65535); first != "" {
                    return first
                }
                return limitProblem("timeout", timeoutText, 1, 3600)
            }
        '''),
        "rust": dedent_code('''
            fn limit_problem(name: &str, text: &str, low: i64, high: i64) -> String {
                if text.is_empty() || !text.chars().all(|c| c.is_ascii_digit()) {
                    return format!("{} must be an integer", name);
                }
                let value: i64 = text.parse().unwrap_or(-1);
                if value < low || value > high {
                    return format!("{} out of range", name);
                }
                String::new()
            }

            fn check_limits(port_text: &str, timeout_text: &str) -> String {
                let first = limit_problem("port", port_text, 1, 65535);
                if !first.is_empty() {
                    return first;
                }
                limit_problem("timeout", timeout_text, 1, 3600)
            }
        '''),
    },
)


FIRST_ERROR_LINE = Family(
    name="first_error_line",
    skill="early_return",
    difficulty="hard",
    io={"args": ["list<str>"], "returns": "int"},
    spec="""
`first_error_line` returns the index of the first line containing the substring
"ERROR", or -1 when no line does.

- The match is a plain, case-sensitive substring test, so "ERRORS everywhere"
  counts and "error" does not.
- Indices are 0-based.
- An empty list gives -1.

The current version seeds a result variable with -1, walks every line to the
end, and guards each assignment with "only if we have not found one yet".
Refactor it to return as soon as it finds the line, so the sentinel variable and
its guard both disappear.
""",
    signatures={
        "python": "def first_error_line(lines: list[str]) -> int:",
        "typescript": "function firstErrorLine(lines: string[]): number {",
        "go": "func FirstErrorLine(lines []string) int {",
        "rust": "fn first_error_line(lines: &[&str]) -> i64 {",
    },
    inputs=[
        ["ok", "ERROR bad", "ERROR worse"],
        ["ok", "fine"],
        [],
        ["ERROR first"],
        ["error lowercase"],
        ["a", "b", "c ERROR"],
        ["ERRORS everywhere"],
        ["", "ERROR"],
    ],
    reference=first_error_line,
    extras={
        "goal": (
            "Return the index as soon as it is known; drop the sentinel "
            "variable and the 'have we already found one' guard."
        )
    },
    lang_extras={
        "python": {
            "original_code": dedent_code('''
                def first_error_line(lines: list[str]) -> int:
                    result = -1
                    for index in range(len(lines)):
                        line = lines[index]
                        if "ERROR" in line:
                            if result == -1:
                                result = index
                    return result
            '''),
            "structure": {
                "max_matches": [
                    {
                        "pattern": r"\bif\b",
                        "max": 1,
                        "reason": "the 'not found yet' guard should be gone",
                    }
                ],
                "max_lines": 10,
            },
        },
        "typescript": {
            "original_code": dedent_code('''
                function firstErrorLine(lines: string[]): number {
                    let result = -1;
                    for (let index = 0; index < lines.length; index++) {
                        const line = lines[index];
                        if (line.includes("ERROR")) {
                            if (result === -1) {
                                result = index;
                            }
                        }
                    }
                    return result;
                }
            '''),
            "structure": {
                "max_matches": [
                    {
                        "pattern": r"\bif\b",
                        "max": 1,
                        "reason": "the 'not found yet' guard should be gone",
                    }
                ],
                "max_lines": 12,
            },
        },
        "go": {
            "original_code": dedent_code('''
                func FirstErrorLine(lines []string) int {
                    result := -1
                    for index := 0; index < len(lines); index++ {
                        line := lines[index]
                        if strings.Contains(line, "ERROR") {
                            if result == -1 {
                                result = index
                            }
                        }
                    }
                    return result
                }
            '''),
            "structure": {
                "max_matches": [
                    {
                        "pattern": r"\bif\b",
                        "max": 1,
                        "reason": "the 'not found yet' guard should be gone",
                    }
                ],
                "max_lines": 16,
            },
        },
        "rust": {
            "original_code": dedent_code('''
                fn first_error_line(lines: &[&str]) -> i64 {
                    let mut result: i64 = -1;
                    for index in 0..lines.len() {
                        let line = lines[index];
                        if line.contains("ERROR") {
                            if result == -1 {
                                result = index as i64;
                            }
                        }
                    }
                    result
                }
            '''),
            "structure": {
                "max_matches": [
                    {
                        "pattern": r"\bif\b",
                        "max": 1,
                        "reason": "the 'not found yet' guard should be gone",
                    }
                ],
                "max_lines": 12,
            },
        },
    },
    solutions={
        "python": dedent_code('''
            def first_error_line(lines: list[str]) -> int:
                for index, line in enumerate(lines):
                    if "ERROR" in line:
                        return index
                return -1
        '''),
        "typescript": dedent_code('''
            export function firstErrorLine(lines: string[]): number {
                for (let index = 0; index < lines.length; index++) {
                    if (lines[index].includes("ERROR")) return index;
                }
                return -1;
            }
        '''),
        "go": dedent_code('''
            package main

            import "strings"

            func FirstErrorLine(lines []string) int {
                for index, line := range lines {
                    if strings.Contains(line, "ERROR") {
                        return index
                    }
                }
                return -1
            }
        '''),
        "rust": dedent_code('''
            fn first_error_line(lines: &[&str]) -> i64 {
                for (index, line) in lines.iter().enumerate() {
                    if line.contains("ERROR") {
                        return index as i64;
                    }
                }
                -1
            }
        '''),
    },
)


RANK_SERVICES = Family(
    name="rank_services",
    skill="use_library_sort",
    difficulty="hard",
    io={"args": ["list<str>", "list<int>"], "returns": "list<str>"},
    spec="""
`rank_services` orders services for a leaderboard.

- `names` and `scores` are parallel arrays of the same length.
- The result is the names ordered by score descending; services on the same
  score are ordered by name ascending, so the ranking is deterministic.
- An empty input gives an empty result.

The current version is a hand-written bubble sort over two parallel arrays,
with the tie-break spelled out as a swap condition. Refactor it to use the
language's own sort with a comparator (or key) expressing "score descending,
then name ascending", keeping the result identical.
""",
    signatures={
        "python": "def rank_services(names: list[str], scores: list[int]) -> list[str]:",
        "typescript": "function rankServices(names: string[], scores: number[]): string[] {",
        "go": "func RankServices(names []string, scores []int) []string {",
        "rust": "fn rank_services(names: &[&str], scores: &[i64]) -> Vec<String> {",
    },
    inputs=[
        [["a", "b", "c"], [3, 1, 2]],
        [["b", "a"], [5, 5]],
        [[], []],
        [["x"], [0]],
        [["a", "b", "c"], [1, 1, 1]],
        [["zeta", "alpha", "mid"], [2, 2, 9]],
        [["a", "b"], [-1, -2]],
        [["p", "q", "r", "s"], [4, 4, 1, 9]],
    ],
    reference=rank_services,
    extras={
        "goal": (
            "Replace the hand-rolled bubble sort with the standard library "
            "sort plus a comparator for the two-level ordering."
        )
    },
    lang_extras={
        "python": {
            "original_code": dedent_code('''
                def rank_services(names: list[str], scores: list[int]) -> list[str]:
                    n = min(len(names), len(scores))
                    out_names = [names[i] for i in range(n)]
                    out_scores = [scores[i] for i in range(n)]
                    for i in range(n):
                        for j in range(n - 1 - i):
                            swap = False
                            if out_scores[j] < out_scores[j + 1]:
                                swap = True
                            elif out_scores[j] == out_scores[j + 1] and out_names[j] > out_names[j + 1]:
                                swap = True
                            if swap:
                                out_scores[j], out_scores[j + 1] = out_scores[j + 1], out_scores[j]
                                out_names[j], out_names[j + 1] = out_names[j + 1], out_names[j]
                    return out_names
            '''),
            "structure": {
                "max_matches": [
                    {
                        "pattern": r"\bfor\b",
                        "max": 2,
                        "reason": "the nested comparison loops should be gone",
                    }
                ],
                "require_any": [
                    {
                        "patterns": [r"sorted\(", r"\.sort\("],
                        "reason": "the library sort should do the ordering",
                    }
                ],
                "max_lines": 16,
            },
        },
        "typescript": {
            "original_code": dedent_code('''
                function rankServices(names: string[], scores: number[]): string[] {
                    const n = Math.min(names.length, scores.length);
                    const outNames: string[] = [];
                    const outScores: number[] = [];
                    for (let i = 0; i < n; i++) {
                        outNames.push(names[i]);
                        outScores.push(scores[i]);
                    }
                    for (let i = 0; i < n; i++) {
                        for (let j = 0; j < n - 1 - i; j++) {
                            let swap = false;
                            if (outScores[j] < outScores[j + 1]) {
                                swap = true;
                            } else if (outScores[j] === outScores[j + 1] && outNames[j] > outNames[j + 1]) {
                                swap = true;
                            }
                            if (swap) {
                                const tmpScore = outScores[j];
                                outScores[j] = outScores[j + 1];
                                outScores[j + 1] = tmpScore;
                                const tmpName = outNames[j];
                                outNames[j] = outNames[j + 1];
                                outNames[j + 1] = tmpName;
                            }
                        }
                    }
                    return outNames;
                }
            '''),
            "structure": {
                "max_matches": [
                    {
                        "pattern": r"\bfor\b",
                        "max": 1,
                        "reason": "the nested comparison loops should be gone",
                    }
                ],
                "require_any": [
                    {
                        "patterns": [r"\.sort\("],
                        "reason": "the library sort should do the ordering",
                    }
                ],
                "max_lines": 16,
            },
        },
        "go": {
            "original_code": dedent_code('''
                func RankServices(names []string, scores []int) []string {
                    n := len(names)
                    if len(scores) < n {
                        n = len(scores)
                    }
                    outNames := make([]string, n)
                    outScores := make([]int, n)
                    for i := 0; i < n; i++ {
                        outNames[i] = names[i]
                        outScores[i] = scores[i]
                    }
                    for i := 0; i < n; i++ {
                        for j := 0; j < n-1-i; j++ {
                            swap := false
                            if outScores[j] < outScores[j+1] {
                                swap = true
                            } else if outScores[j] == outScores[j+1] && outNames[j] > outNames[j+1] {
                                swap = true
                            }
                            if swap {
                                outScores[j], outScores[j+1] = outScores[j+1], outScores[j]
                                outNames[j], outNames[j+1] = outNames[j+1], outNames[j]
                            }
                        }
                    }
                    return outNames
                }
            '''),
            "structure": {
                "max_matches": [
                    {
                        "pattern": r"\bfor\b",
                        "max": 2,
                        "reason": "the nested comparison loops should be gone",
                    }
                ],
                "require_any": [
                    {
                        "patterns": [r"sort\."],
                        "reason": "the library sort should do the ordering",
                    }
                ],
                "max_lines": 26,
            },
        },
        "rust": {
            "original_code": dedent_code('''
                fn rank_services(names: &[&str], scores: &[i64]) -> Vec<String> {
                    let n = names.len().min(scores.len());
                    let mut out_names: Vec<String> = Vec::new();
                    let mut out_scores: Vec<i64> = Vec::new();
                    for i in 0..n {
                        out_names.push(names[i].to_string());
                        out_scores.push(scores[i]);
                    }
                    for i in 0..n {
                        for j in 0..(n - 1 - i) {
                            let mut swap = false;
                            if out_scores[j] < out_scores[j + 1] {
                                swap = true;
                            } else if out_scores[j] == out_scores[j + 1] && out_names[j] > out_names[j + 1] {
                                swap = true;
                            }
                            if swap {
                                out_scores.swap(j, j + 1);
                                out_names.swap(j, j + 1);
                            }
                        }
                    }
                    out_names
                }
            '''),
            "structure": {
                "max_matches": [
                    {
                        "pattern": r"\bfor\b",
                        "max": 1,
                        "reason": "the nested comparison loops should be gone",
                    }
                ],
                "require_any": [
                    {
                        "patterns": [r"\.sort"],
                        "reason": "the library sort should do the ordering",
                    }
                ],
                "max_lines": 14,
            },
        },
    },
    solutions={
        "python": dedent_code('''
            def rank_services(names: list[str], scores: list[int]) -> list[str]:
                n = min(len(names), len(scores))
                order = sorted(range(n), key=lambda i: (-scores[i], names[i]))
                return [names[i] for i in order]
        '''),
        "typescript": dedent_code('''
            export function rankServices(names: string[], scores: number[]): string[] {
                const n = Math.min(names.length, scores.length);
                const order = Array.from({ length: n }, (_unused, i) => i);
                order.sort((a, b) => {
                    if (scores[a] !== scores[b]) return scores[b] - scores[a];
                    return names[a] < names[b] ? -1 : names[a] > names[b] ? 1 : 0;
                });
                return order.map((i) => names[i]);
            }
        '''),
        "go": dedent_code('''
            package main

            import "sort"

            func RankServices(names []string, scores []int) []string {
                n := len(names)
                if len(scores) < n {
                    n = len(scores)
                }
                order := make([]int, n)
                for i := range order {
                    order[i] = i
                }
                sort.SliceStable(order, func(a, b int) bool {
                    x, y := order[a], order[b]
                    if scores[x] != scores[y] {
                        return scores[x] > scores[y]
                    }
                    return names[x] < names[y]
                })
                out := make([]string, n)
                for i, index := range order {
                    out[i] = names[index]
                }
                return out
            }
        '''),
        "rust": dedent_code('''
            fn rank_services(names: &[&str], scores: &[i64]) -> Vec<String> {
                let n = names.len().min(scores.len());
                let mut order: Vec<usize> = (0..n).collect();
                order.sort_by(|&a, &b| scores[b].cmp(&scores[a]).then(names[a].cmp(names[b])));
                order.into_iter().map(|i| names[i].to_string()).collect()
            }
        '''),
    },
)


BILL_SUMMARY = Family(
    name="bill_summary",
    skill="hoist_duplication",
    difficulty="hard",
    io={"args": ["int", "int", "int"], "returns": "str"},
    spec="""
`bill_summary` renders an invoice line. The behavior is correct and must not
change:

- Negative units or a negative rate give exactly "invalid".
- The subtotal is units multiplied by the rate in cents.
- A discount of 0 or less is labelled "no discount" and the total equals the
  subtotal.
- A discount of 100 or more is labelled "free" and the total is 0.
- Anything in between is labelled "discounted" and the total is the subtotal
  minus (subtotal * discount) / 100 using *integer* division that truncates
  toward zero.
- The result is "<label> subtotal=<subtotal> total=<total>".

The subtotal expression is recomputed inside every branch. Refactor so it is
computed once, before the branches, and each branch only decides the label and
the total.
""",
    signatures={
        "python": "def bill_summary(units: int, rate_cents: int, discount_pct: int) -> str:",
        "typescript": (
            "function billSummary(units: number, rateCents: number, "
            "discountPct: number): string {"
        ),
        "go": "func BillSummary(units int, rateCents int, discountPct int) string {",
        "rust": "fn bill_summary(units: i64, rate_cents: i64, discount_pct: i64) -> String {",
    },
    inputs=[
        [100, 250, 0],
        [100, 250, 10],
        [100, 250, 100],
        [100, 250, 150],
        [0, 500, 20],
        [-1, 10, 0],
        [10, -5, 0],
        [3, 333, 33],
        [1, 1, -5],
        [7, 100, 99],
    ],
    reference=bill_summary,
    extras={
        "goal": (
            "Compute the subtotal once, above the branches; leave each branch "
            "responsible only for the label and the total."
        )
    },
    lang_extras={
        "python": {
            "original_code": dedent_code('''
                def bill_summary(units: int, rate_cents: int, discount_pct: int) -> str:
                    if units < 0 or rate_cents < 0:
                        return "invalid"
                    if discount_pct <= 0:
                        return "no discount subtotal=" + str(units * rate_cents) + " total=" + str(units * rate_cents)
                    if discount_pct >= 100:
                        return "free subtotal=" + str(units * rate_cents) + " total=0"
                    discounted = units * rate_cents - (units * rate_cents * discount_pct) // 100
                    return "discounted subtotal=" + str(units * rate_cents) + " total=" + str(discounted)
            '''),
            "structure": {
                "max_matches": [
                    {
                        "pattern": r"units \* rate_cents",
                        "max": 1,
                        "reason": "the subtotal should be computed once and reused",
                    }
                ],
                "max_lines": 18,
            },
        },
        "typescript": {
            "original_code": dedent_code('''
                function billSummary(units: number, rateCents: number, discountPct: number): string {
                    if (units < 0 || rateCents < 0) return "invalid";
                    if (discountPct <= 0) {
                        return `no discount subtotal=${units * rateCents} total=${units * rateCents}`;
                    }
                    if (discountPct >= 100) {
                        return `free subtotal=${units * rateCents} total=0`;
                    }
                    const total = units * rateCents - Math.trunc((units * rateCents * discountPct) / 100);
                    return `discounted subtotal=${units * rateCents} total=${total}`;
                }
            '''),
            "structure": {
                "max_matches": [
                    {
                        "pattern": r"units \* rateCents",
                        "max": 1,
                        "reason": "the subtotal should be computed once and reused",
                    }
                ],
                "max_lines": 18,
            },
        },
        "go": {
            "original_code": dedent_code('''
                func BillSummary(units int, rateCents int, discountPct int) string {
                    if units < 0 || rateCents < 0 {
                        return "invalid"
                    }
                    if discountPct <= 0 {
                        return fmt.Sprintf("no discount subtotal=%d total=%d", units*rateCents, units*rateCents)
                    }
                    if discountPct >= 100 {
                        return fmt.Sprintf("free subtotal=%d total=0", units*rateCents)
                    }
                    total := units*rateCents - (units*rateCents*discountPct)/100
                    return fmt.Sprintf("discounted subtotal=%d total=%d", units*rateCents, total)
                }
            '''),
            "structure": {
                "max_matches": [
                    {
                        "pattern": r"units\*rateCents|units \* rateCents",
                        "max": 1,
                        "reason": "the subtotal should be computed once and reused",
                    }
                ],
                "max_lines": 22,
            },
        },
        "rust": {
            "original_code": dedent_code('''
                fn bill_summary(units: i64, rate_cents: i64, discount_pct: i64) -> String {
                    if units < 0 || rate_cents < 0 {
                        return "invalid".to_string();
                    }
                    if discount_pct <= 0 {
                        return format!(
                            "no discount subtotal={} total={}",
                            units * rate_cents,
                            units * rate_cents
                        );
                    }
                    if discount_pct >= 100 {
                        return format!("free subtotal={} total=0", units * rate_cents);
                    }
                    let total = units * rate_cents - (units * rate_cents * discount_pct) / 100;
                    return format!("discounted subtotal={} total={}", units * rate_cents, total);
                }
            '''),
            "structure": {
                "max_matches": [
                    {
                        "pattern": r"units \* rate_cents",
                        "max": 1,
                        "reason": "the subtotal should be computed once and reused",
                    }
                ],
                "max_lines": 22,
            },
        },
    },
    solutions={
        "python": dedent_code('''
            def bill_summary(units: int, rate_cents: int, discount_pct: int) -> str:
                if units < 0 or rate_cents < 0:
                    return "invalid"
                subtotal = units * rate_cents
                if discount_pct <= 0:
                    label, total = "no discount", subtotal
                elif discount_pct >= 100:
                    label, total = "free", 0
                else:
                    label, total = "discounted", subtotal - (subtotal * discount_pct) // 100
                return f"{label} subtotal={subtotal} total={total}"
        '''),
        "typescript": dedent_code('''
            export function billSummary(
                units: number,
                rateCents: number,
                discountPct: number,
            ): string {
                if (units < 0 || rateCents < 0) return "invalid";
                const subtotal = units * rateCents;
                let label = "discounted";
                let total = subtotal - Math.trunc((subtotal * discountPct) / 100);
                if (discountPct <= 0) {
                    label = "no discount";
                    total = subtotal;
                } else if (discountPct >= 100) {
                    label = "free";
                    total = 0;
                }
                return `${label} subtotal=${subtotal} total=${total}`;
            }
        '''),
        "go": dedent_code('''
            package main

            import "fmt"

            func BillSummary(units int, rateCents int, discountPct int) string {
                if units < 0 || rateCents < 0 {
                    return "invalid"
                }
                subtotal := units * rateCents
                label := "discounted"
                total := subtotal - (subtotal*discountPct)/100
                if discountPct <= 0 {
                    label, total = "no discount", subtotal
                } else if discountPct >= 100 {
                    label, total = "free", 0
                }
                return fmt.Sprintf("%s subtotal=%d total=%d", label, subtotal, total)
            }
        '''),
        "rust": dedent_code('''
            fn bill_summary(units: i64, rate_cents: i64, discount_pct: i64) -> String {
                if units < 0 || rate_cents < 0 {
                    return "invalid".to_string();
                }
                let subtotal = units * rate_cents;
                let (label, total) = if discount_pct <= 0 {
                    ("no discount", subtotal)
                } else if discount_pct >= 100 {
                    ("free", 0)
                } else {
                    ("discounted", subtotal - (subtotal * discount_pct) / 100)
                };
                format!("{} subtotal={} total={}", label, subtotal, total)
            }
        '''),
    },
)


PARSE_KV = Family(
    name="parse_kv",
    skill="use_library_split",
    difficulty="hard",
    io={"args": ["str"], "returns": "str"},
    spec="""
`parse_kv` reads a comma-separated `key=value` string and renders it back in a
canonical form.

- Pairs are separated by commas; within a pair, the key ends at the **first**
  `=`, so "k=v=w" has key "k" and value "v=w".
- A pair with no `=`, or with an empty key, is dropped. An empty value is kept,
  so "a=" is the key "a" with an empty value.
- When a key repeats, the last value wins.
- The result lists the surviving pairs as "key=value", sorted by key ascending
  and joined with ";". No pairs gives the empty string.

The current version walks the string one character at a time, tracking indexes
by hand to find the separators. Refactor it to split on the separators with the
language's own string functions, keeping the behavior identical.
""",
    signatures={
        "python": "def parse_kv(text: str) -> str:",
        "typescript": "function parseKv(text: string): string {",
        "go": "func ParseKv(text string) string {",
        "rust": "fn parse_kv(text: &str) -> String {",
    },
    inputs=[
        "a=1,b=2",
        "",
        "a=1,a=2",
        "noequals",
        "=novalue",
        "a=",
        "b=2,a=1",
        "x=1,,y=2",
        "k=v=w",
        "a=1,b",
        "z=26,y=25,x=24",
    ],
    reference=parse_kv,
    extras={
        "goal": (
            "Split on the separators with the standard library instead of "
            "walking indexes by hand."
        )
    },
    lang_extras={
        "python": {
            "original_code": dedent_code('''
                def parse_kv(text: str) -> str:
                    result = {}
                    index = 0
                    length = len(text)
                    while index < length:
                        end = index
                        while end < length and text[end] != ",":
                            end = end + 1
                        piece = text[index:end]
                        equals = -1
                        position = 0
                        while position < len(piece):
                            if piece[position] == "=" and equals == -1:
                                equals = position
                            position = position + 1
                        if equals > 0:
                            result[piece[0:equals]] = piece[equals + 1:]
                        index = end + 1
                    keys = sorted(result)
                    out = ""
                    for key in keys:
                        if out != "":
                            out = out + ";"
                        out = out + key + "=" + result[key]
                    return out
            '''),
            "structure": {
                "max_matches": [
                    {
                        "pattern": r"\bwhile\b",
                        "max": 0,
                        "reason": "hand-rolled index scanning should be gone",
                    }
                ],
                "require_any": [
                    {
                        "patterns": [r"\.split\(", r"\.partition\("],
                        "reason": "the standard split should find the separators",
                    }
                ],
                "max_lines": 20,
            },
        },
        "typescript": {
            "original_code": dedent_code('''
                function parseKv(text: string): string {
                    const result: Record<string, string> = {};
                    let index = 0;
                    while (index < text.length) {
                        let end = index;
                        while (end < text.length && text[end] !== ",") {
                            end = end + 1;
                        }
                        const piece = text.slice(index, end);
                        let equals = -1;
                        let position = 0;
                        while (position < piece.length) {
                            if (piece[position] === "=" && equals === -1) {
                                equals = position;
                            }
                            position = position + 1;
                        }
                        if (equals > 0) {
                            result[piece.slice(0, equals)] = piece.slice(equals + 1);
                        }
                        index = end + 1;
                    }
                    const keys = Object.keys(result).sort();
                    let out = "";
                    for (const key of keys) {
                        if (out !== "") out = out + ";";
                        out = out + key + "=" + result[key];
                    }
                    return out;
                }
            '''),
            "structure": {
                "max_matches": [
                    {
                        "pattern": r"\bwhile\b",
                        "max": 0,
                        "reason": "hand-rolled index scanning should be gone",
                    }
                ],
                "require_any": [
                    {
                        "patterns": [r"\.split\("],
                        "reason": "the standard split should find the separators",
                    }
                ],
                "max_lines": 22,
            },
        },
        "go": {
            "original_code": dedent_code('''
                func ParseKv(text string) string {
                    result := map[string]string{}
                    index := 0
                    for index < len(text) {
                        end := index
                        for end < len(text) && text[end] != ',' {
                            end = end + 1
                        }
                        piece := text[index:end]
                        equals := -1
                        position := 0
                        for position < len(piece) {
                            if piece[position] == '=' && equals == -1 {
                                equals = position
                            }
                            position = position + 1
                        }
                        if equals > 0 {
                            result[piece[0:equals]] = piece[equals+1:]
                        }
                        index = end + 1
                    }
                    keys := make([]string, 0, len(result))
                    for key := range result {
                        keys = append(keys, key)
                    }
                    sort.Strings(keys)
                    out := ""
                    for _, key := range keys {
                        if out != "" {
                            out = out + ";"
                        }
                        out = out + key + "=" + result[key]
                    }
                    return out
                }
            '''),
            "structure": {
                "max_matches": [
                    {
                        "pattern": r"\bfor\b",
                        "max": 3,
                        "reason": "hand-rolled index scanning should be gone",
                    }
                ],
                "require_any": [
                    {
                        "patterns": [r"strings\.Split"],
                        "reason": "the standard split should find the separators",
                    }
                ],
                "max_lines": 30,
            },
        },
        "rust": {
            "original_code": dedent_code('''
                use std::collections::BTreeMap;

                fn parse_kv(text: &str) -> String {
                    let bytes = text.as_bytes();
                    let mut result: BTreeMap<String, String> = BTreeMap::new();
                    let mut index = 0usize;
                    while index < bytes.len() {
                        let mut end = index;
                        while end < bytes.len() && bytes[end] != b',' {
                            end += 1;
                        }
                        let piece = &text[index..end];
                        let mut equals: i64 = -1;
                        let mut position = 0usize;
                        while position < piece.len() {
                            if piece.as_bytes()[position] == b'=' && equals == -1 {
                                equals = position as i64;
                            }
                            position += 1;
                        }
                        if equals > 0 {
                            let cut = equals as usize;
                            result.insert(piece[..cut].to_string(), piece[cut + 1..].to_string());
                        }
                        index = end + 1;
                    }
                    let mut out = String::new();
                    for (key, value) in &result {
                        if !out.is_empty() {
                            out.push(';');
                        }
                        out.push_str(key);
                        out.push('=');
                        out.push_str(value);
                    }
                    out
                }
            '''),
            "structure": {
                "max_matches": [
                    {
                        "pattern": r"\bwhile\b",
                        "max": 0,
                        "reason": "hand-rolled index scanning should be gone",
                    }
                ],
                "require_any": [
                    {
                        "patterns": [r"\.split", r"split_once"],
                        "reason": "the standard split should find the separators",
                    }
                ],
                "max_lines": 24,
            },
        },
    },
    solutions={
        "python": dedent_code('''
            def parse_kv(text: str) -> str:
                result = {}
                for piece in text.split(","):
                    key, sep, value = piece.partition("=")
                    if sep and key:
                        result[key] = value
                return ";".join(f"{key}={result[key]}" for key in sorted(result))
        '''),
        "typescript": dedent_code('''
            export function parseKv(text: string): string {
                const result: Record<string, string> = {};
                for (const piece of text.split(",")) {
                    const equals = piece.indexOf("=");
                    if (equals > 0) {
                        result[piece.slice(0, equals)] = piece.slice(equals + 1);
                    }
                }
                return Object.keys(result)
                    .sort()
                    .map((key) => `${key}=${result[key]}`)
                    .join(";");
            }
        '''),
        "go": dedent_code('''
            package main

            import (
                "sort"
                "strings"
            )

            func ParseKv(text string) string {
                result := map[string]string{}
                for _, piece := range strings.Split(text, ",") {
                    parts := strings.SplitN(piece, "=", 2)
                    if len(parts) == 2 && parts[0] != "" {
                        result[parts[0]] = parts[1]
                    }
                }
                keys := make([]string, 0, len(result))
                for key := range result {
                    keys = append(keys, key)
                }
                sort.Strings(keys)
                pairs := make([]string, 0, len(keys))
                for _, key := range keys {
                    pairs = append(pairs, key+"="+result[key])
                }
                return strings.Join(pairs, ";")
            }
        '''),
        "rust": dedent_code('''
            use std::collections::BTreeMap;

            fn parse_kv(text: &str) -> String {
                let mut result: BTreeMap<String, String> = BTreeMap::new();
                for piece in text.split(',') {
                    if let Some((key, value)) = piece.split_once('=') {
                        if !key.is_empty() {
                            result.insert(key.to_string(), value.to_string());
                        }
                    }
                }
                result
                    .iter()
                    .map(|(key, value)| format!("{}={}", key, value))
                    .collect::<Vec<String>>()
                    .join(";")
            }
        '''),
    },
)


COMPACT_RANGES = Family(
    name="compact_ranges",
    skill="extract_helper",
    difficulty="hard",
    io={"args": ["list<int>"], "returns": "str"},
    spec="""
`compact_ranges` collapses a sorted list of distinct integers into range
notation.

- Consecutive values collapse into "first-last"; a value with no neighbour
  stands alone.
- Pieces are joined with commas, in order: [1, 2, 3, 5, 7, 8, 9] renders as
  "1-3,5,7-9".
- A run of exactly two, like [1, 2], still renders as "1-2".
- Negative values are written as they are, so [-3, -2, -1] renders as "-3--1".
- An empty list gives the empty string.

The block that turns a finished run into text is written out twice — once when
a run ends inside the loop, once for the final run after it. Refactor so that
formatting exists in exactly one place and both call sites use it.
""",
    signatures={
        "python": "def compact_ranges(values: list[int]) -> str:",
        "typescript": "function compactRanges(values: number[]): string {",
        "go": "func CompactRanges(values []int) string {",
        "rust": "fn compact_ranges(values: &[i64]) -> String {",
    },
    inputs=[
        [1, 2, 3, 5, 7, 8, 9],
        [],
        [4],
        [1, 2],
        [1, 3, 5],
        [1, 2, 3, 4, 5],
        [-3, -2, -1, 4],
        [0],
        [10, 11, 13, 14],
    ],
    reference=compact_ranges,
    extras={
        "goal": (
            "Extract the run-formatting into one helper and call it from both "
            "places instead of duplicating the branch."
        )
    },
    lang_extras={
        "python": {
            "original_code": dedent_code('''
                def compact_ranges(values: list[int]) -> str:
                    if not values:
                        return ""
                    parts = []
                    start = values[0]
                    end = values[0]
                    for value in values[1:]:
                        if value == end + 1:
                            end = value
                        else:
                            if start == end:
                                parts.append(str(start))
                            else:
                                parts.append(str(start) + "-" + str(end))
                            start = value
                            end = value
                    if start == end:
                        parts.append(str(start))
                    else:
                        parts.append(str(start) + "-" + str(end))
                    return ",".join(parts)
            '''),
            "structure": {
                "max_matches": [
                    {
                        "pattern": r"start == end",
                        "max": 1,
                        "reason": "the run-formatting branch should exist in one place",
                    }
                ],
                "max_lines": 24,
            },
        },
        "typescript": {
            "original_code": dedent_code('''
                function compactRanges(values: number[]): string {
                    if (values.length === 0) return "";
                    const parts: string[] = [];
                    let start = values[0];
                    let end = values[0];
                    for (let i = 1; i < values.length; i++) {
                        const value = values[i];
                        if (value === end + 1) {
                            end = value;
                        } else {
                            if (start === end) {
                                parts.push(String(start));
                            } else {
                                parts.push(String(start) + "-" + String(end));
                            }
                            start = value;
                            end = value;
                        }
                    }
                    if (start === end) {
                        parts.push(String(start));
                    } else {
                        parts.push(String(start) + "-" + String(end));
                    }
                    return parts.join(",");
                }
            '''),
            "structure": {
                "max_matches": [
                    {
                        "pattern": r"start === end",
                        "max": 1,
                        "reason": "the run-formatting branch should exist in one place",
                    }
                ],
                "max_lines": 26,
            },
        },
        "go": {
            "original_code": dedent_code('''
                func CompactRanges(values []int) string {
                    if len(values) == 0 {
                        return ""
                    }
                    parts := []string{}
                    start := values[0]
                    end := values[0]
                    for i := 1; i < len(values); i++ {
                        value := values[i]
                        if value == end+1 {
                            end = value
                        } else {
                            if start == end {
                                parts = append(parts, strconv.Itoa(start))
                            } else {
                                parts = append(parts, strconv.Itoa(start)+"-"+strconv.Itoa(end))
                            }
                            start = value
                            end = value
                        }
                    }
                    if start == end {
                        parts = append(parts, strconv.Itoa(start))
                    } else {
                        parts = append(parts, strconv.Itoa(start)+"-"+strconv.Itoa(end))
                    }
                    return strings.Join(parts, ",")
                }
            '''),
            "structure": {
                "max_matches": [
                    {
                        "pattern": r"start == end",
                        "max": 1,
                        "reason": "the run-formatting branch should exist in one place",
                    }
                ],
                "max_lines": 32,
            },
        },
        "rust": {
            "original_code": dedent_code('''
                fn compact_ranges(values: &[i64]) -> String {
                    if values.is_empty() {
                        return String::new();
                    }
                    let mut parts: Vec<String> = Vec::new();
                    let mut start = values[0];
                    let mut end = values[0];
                    for &value in &values[1..] {
                        if value == end + 1 {
                            end = value;
                        } else {
                            if start == end {
                                parts.push(start.to_string());
                            } else {
                                parts.push(format!("{}-{}", start, end));
                            }
                            start = value;
                            end = value;
                        }
                    }
                    if start == end {
                        parts.push(start.to_string());
                    } else {
                        parts.push(format!("{}-{}", start, end));
                    }
                    parts.join(",")
                }
            '''),
            "structure": {
                "max_matches": [
                    {
                        "pattern": r"start == end",
                        "max": 1,
                        "reason": "the run-formatting branch should exist in one place",
                    }
                ],
                "max_lines": 28,
            },
        },
    },
    solutions={
        "python": dedent_code('''
            def _piece(start: int, end: int) -> str:
                if start == end:
                    return str(start)
                return str(start) + "-" + str(end)


            def compact_ranges(values: list[int]) -> str:
                if not values:
                    return ""
                parts = []
                start = values[0]
                end = values[0]
                for value in values[1:]:
                    if value == end + 1:
                        end = value
                    else:
                        parts.append(_piece(start, end))
                        start = value
                        end = value
                parts.append(_piece(start, end))
                return ",".join(parts)
        '''),
        "typescript": dedent_code('''
            function piece(start: number, end: number): string {
                return start === end ? String(start) : `${start}-${end}`;
            }

            export function compactRanges(values: number[]): string {
                if (values.length === 0) return "";
                const parts: string[] = [];
                let start = values[0];
                let end = values[0];
                for (let i = 1; i < values.length; i++) {
                    if (values[i] === end + 1) {
                        end = values[i];
                    } else {
                        parts.push(piece(start, end));
                        start = values[i];
                        end = values[i];
                    }
                }
                parts.push(piece(start, end));
                return parts.join(",");
            }
        '''),
        "go": dedent_code('''
            package main

            import (
                "strconv"
                "strings"
            )

            func rangePiece(start int, end int) string {
                if start == end {
                    return strconv.Itoa(start)
                }
                return strconv.Itoa(start) + "-" + strconv.Itoa(end)
            }

            func CompactRanges(values []int) string {
                if len(values) == 0 {
                    return ""
                }
                parts := []string{}
                start, end := values[0], values[0]
                for i := 1; i < len(values); i++ {
                    if values[i] == end+1 {
                        end = values[i]
                    } else {
                        parts = append(parts, rangePiece(start, end))
                        start, end = values[i], values[i]
                    }
                }
                parts = append(parts, rangePiece(start, end))
                return strings.Join(parts, ",")
            }
        '''),
        "rust": dedent_code('''
            fn range_piece(start: i64, end: i64) -> String {
                if start == end {
                    start.to_string()
                } else {
                    format!("{}-{}", start, end)
                }
            }

            fn compact_ranges(values: &[i64]) -> String {
                if values.is_empty() {
                    return String::new();
                }
                let mut parts: Vec<String> = Vec::new();
                let mut start = values[0];
                let mut end = values[0];
                for &value in &values[1..] {
                    if value == end + 1 {
                        end = value;
                    } else {
                        parts.push(range_piece(start, end));
                        start = value;
                        end = value;
                    }
                }
                parts.push(range_piece(start, end));
                parts.join(",")
            }
        '''),
    },
)


ADVANCED_FAMILIES = [
    DEPLOY_GATE,
    NEXT_STATE,
    SUMMARIZE_SERIES,
    FORMAT_TABLE_ROW,
    CHECK_LIMITS,
    FIRST_ERROR_LINE,
    RANK_SERVICES,
    BILL_SUMMARY,
    PARSE_KV,
    COMPACT_RANGES,
]
