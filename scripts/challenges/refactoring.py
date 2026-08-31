"""code_refactoring: keep the behavior, lose the mess.

Each case ships code that already works and a goal for the shape it should
have. Execution against the hidden tests proves the behavior survived; a small
set of per-language structural rules proves the model actually restructured the
code instead of returning it with new formatting. The rules are deliberately
loose — they check for the *absence of the chain* and the *presence of a table
or a loop*, not for one blessed implementation.
"""

from __future__ import annotations

from .common import Family, dedent_code
from .refactoring_advanced import ADVANCED_FAMILIES

_RANKS = {
    "debug": 10,
    "info": 20,
    "notice": 25,
    "warn": 30,
    "warning": 30,
    "error": 40,
    "critical": 50,
    "fatal": 50,
}


def severity_rank(level: str) -> int:
    return _RANKS.get(level.strip().lower(), 0)


def format_bytes(n: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    index = 0
    scale = 1
    while index < len(units) - 1 and n >= scale * 1024:
        scale *= 1024
        index += 1
    if index == 0:
        return f"{n} B"
    value = (n * 10 // scale) / 10
    return f"{value:.1f} {units[index]}"


def dedupe_preserving_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


SEVERITY_RANK = Family(
    name="severity_rank",
    skill="branch_collapse",
    difficulty="easy",
    io={"args": ["str"], "returns": "int"},
    spec="""
`severity_rank` maps a log level name to a numeric rank. The current version
works and must keep working exactly as it does today:

- debug 10, info 20, notice 25, warn 30, warning 30, error 40, critical 50,
  fatal 50, and 0 for anything else.
- The input is trimmed of surrounding whitespace and matched case-insensitively.

Refactor it so the level-to-rank mapping is data, not control flow: one lookup
(a dictionary/map/table, or the language's idiomatic match) instead of a chain
of comparisons. Adding a level later should mean adding one entry.
""",
    signatures={
        "python": "def severity_rank(level: str) -> int:",
        "typescript": "function severityRank(level: string): number {",
        "go": "func SeverityRank(level string) int {",
        "rust": "fn severity_rank(level: &str) -> i64 {",
    },
    inputs=[
        "debug",
        "INFO",
        " notice ",
        "warn",
        "Warning",
        "error",
        "critical",
        "FATAL",
        "trace",
        "",
        "  ",
        "Error",
    ],
    reference=severity_rank,
    extras={
        "goal": (
            "Replace the comparison chain with a single data-driven lookup, so "
            "adding a level is a one-line data change."
        )
    },
    lang_extras={
        "python": {
            "original_code": dedent_code('''
                def severity_rank(level: str) -> int:
                    normalized = level.strip().lower()
                    if normalized == "debug":
                        return 10
                    elif normalized == "info":
                        return 20
                    elif normalized == "notice":
                        return 25
                    elif normalized == "warn":
                        return 30
                    elif normalized == "warning":
                        return 30
                    elif normalized == "error":
                        return 40
                    elif normalized == "critical":
                        return 50
                    elif normalized == "fatal":
                        return 50
                    else:
                        return 0
            '''),
            "structure": {
                "max_matches": [
                    {
                        "pattern": r"\bif\b|\belif\b",
                        "max": 2,
                        "reason": "the comparison chain should be gone",
                    }
                ],
                "require_any": [
                    {
                        "patterns": [r"\{[^{}]*:", r"\bmatch\b", r"dict\("],
                        "reason": "the levels should live in a lookup table",
                    }
                ],
                "max_lines": 20,
            },
        },
        "typescript": {
            "original_code": dedent_code('''
                function severityRank(level: string): number {
                    const normalized = level.trim().toLowerCase();
                    if (normalized === "debug") {
                        return 10;
                    } else if (normalized === "info") {
                        return 20;
                    } else if (normalized === "notice") {
                        return 25;
                    } else if (normalized === "warn") {
                        return 30;
                    } else if (normalized === "warning") {
                        return 30;
                    } else if (normalized === "error") {
                        return 40;
                    } else if (normalized === "critical") {
                        return 50;
                    } else if (normalized === "fatal") {
                        return 50;
                    } else {
                        return 0;
                    }
                }
            '''),
            "structure": {
                "max_matches": [
                    {
                        "pattern": r"\bif\b",
                        "max": 2,
                        "reason": "the comparison chain should be gone",
                    }
                ],
                "require_any": [
                    {
                        "patterns": [r"Record<", r"\{[^{}]*:", r"new Map"],
                        "reason": "the levels should live in a lookup table",
                    }
                ],
                "max_lines": 20,
            },
        },
        "go": {
            "original_code": dedent_code('''
                func SeverityRank(level string) int {
                    normalized := strings.ToLower(strings.TrimSpace(level))
                    if normalized == "debug" {
                        return 10
                    } else if normalized == "info" {
                        return 20
                    } else if normalized == "notice" {
                        return 25
                    } else if normalized == "warn" {
                        return 30
                    } else if normalized == "warning" {
                        return 30
                    } else if normalized == "error" {
                        return 40
                    } else if normalized == "critical" {
                        return 50
                    } else if normalized == "fatal" {
                        return 50
                    }
                    return 0
                }
            '''),
            "structure": {
                "max_matches": [
                    {
                        "pattern": r"\bif\b",
                        "max": 2,
                        "reason": "the comparison chain should be gone",
                    }
                ],
                "require_any": [
                    {
                        "patterns": [r"map\[string\]", r"\bswitch\b"],
                        "reason": "the levels should live in a map or a switch",
                    }
                ],
                "max_lines": 22,
            },
        },
        "rust": {
            "original_code": dedent_code('''
                fn severity_rank(level: &str) -> i64 {
                    let normalized = level.trim().to_lowercase();
                    if normalized == "debug" {
                        return 10;
                    } else if normalized == "info" {
                        return 20;
                    } else if normalized == "notice" {
                        return 25;
                    } else if normalized == "warn" {
                        return 30;
                    } else if normalized == "warning" {
                        return 30;
                    } else if normalized == "error" {
                        return 40;
                    } else if normalized == "critical" {
                        return 50;
                    } else if normalized == "fatal" {
                        return 50;
                    }
                    0
                }
            '''),
            "structure": {
                "max_matches": [
                    {
                        "pattern": r"\bif\b",
                        "max": 2,
                        "reason": "the comparison chain should be gone",
                    }
                ],
                "require_any": [
                    {
                        "patterns": [r"\bmatch\b", r"HashMap"],
                        "reason": "the levels should live in a match or a map",
                    }
                ],
                "max_lines": 22,
            },
        },
    },
    solutions={
        "python": dedent_code('''
            _RANKS = {
                "debug": 10,
                "info": 20,
                "notice": 25,
                "warn": 30,
                "warning": 30,
                "error": 40,
                "critical": 50,
                "fatal": 50,
            }


            def severity_rank(level: str) -> int:
                return _RANKS.get(level.strip().lower(), 0)
        '''),
        "typescript": dedent_code('''
            const RANKS: Record<string, number> = {
                debug: 10,
                info: 20,
                notice: 25,
                warn: 30,
                warning: 30,
                error: 40,
                critical: 50,
                fatal: 50,
            };

            export function severityRank(level: string): number {
                return RANKS[level.trim().toLowerCase()] ?? 0;
            }
        '''),
        "go": dedent_code('''
            package main

            import "strings"

            var ranks = map[string]int{
                "debug":    10,
                "info":     20,
                "notice":   25,
                "warn":     30,
                "warning":  30,
                "error":    40,
                "critical": 50,
                "fatal":    50,
            }

            func SeverityRank(level string) int {
                return ranks[strings.ToLower(strings.TrimSpace(level))]
            }
        '''),
        "rust": dedent_code('''
            fn severity_rank(level: &str) -> i64 {
                match level.trim().to_lowercase().as_str() {
                    "debug" => 10,
                    "info" => 20,
                    "notice" => 25,
                    "warn" | "warning" => 30,
                    "error" => 40,
                    "critical" | "fatal" => 50,
                    _ => 0,
                }
            }
        '''),
    },
)


FORMAT_BYTES = Family(
    name="format_bytes",
    skill="duplication",
    difficulty="medium",
    io={"args": ["int"], "returns": "str"},
    spec="""
`format_bytes` renders a byte count the way a UI does. Behavior must not
change:

- Units are B, KB, MB, GB, TB, each 1024 of the previous one. Values of 1024 TB
  and above stay in TB.
- Below 1024 the result is the whole number followed by " B", with no decimal:
  512 renders as "512 B".
- Otherwise the value is truncated (never rounded up) to one decimal place and
  followed by a space and the unit: 1536 renders as "1.5 KB", and 1048575
  renders as "1023.9 KB".

Refactor the copy-pasted per-unit blocks into one loop over a unit table. The
scaling arithmetic should appear once, not once per unit.
""",
    signatures={
        "python": "def format_bytes(n: int) -> str:",
        "typescript": "function formatBytes(n: number): string {",
        "go": "func FormatBytes(n int) string {",
        "rust": "fn format_bytes(n: i64) -> String {",
    },
    inputs=[
        0,
        5,
        512,
        1023,
        1024,
        1536,
        1048575,
        1048576,
        1572864,
        1073741824,
        1099511627776,
        2199023255552,
    ],
    reference=format_bytes,
    extras={
        "goal": (
            "Collapse the repeated per-unit branches into one loop over a unit "
            "table so the scaling arithmetic exists in exactly one place."
        )
    },
    lang_extras={
        "python": {
            "original_code": dedent_code('''
                def format_bytes(n: int) -> str:
                    if n < 1024:
                        return f"{n} B"
                    if n < 1024 * 1024:
                        value = (n * 10 // 1024) / 10
                        return f"{value:.1f} KB"
                    if n < 1024 * 1024 * 1024:
                        value = (n * 10 // (1024 * 1024)) / 10
                        return f"{value:.1f} MB"
                    if n < 1024 * 1024 * 1024 * 1024:
                        value = (n * 10 // (1024 * 1024 * 1024)) / 10
                        return f"{value:.1f} GB"
                    value = (n * 10 // (1024 * 1024 * 1024 * 1024)) / 10
                    return f"{value:.1f} TB"
            '''),
            "structure": {
                "max_matches": [
                    {
                        "pattern": r'"KB"|\bKB\b',
                        "max": 2,
                        "reason": "each unit should be named once, in a table",
                    },
                    {
                        "pattern": r"\bif\b",
                        "max": 3,
                        "reason": "the per-unit branches should be gone",
                    },
                ],
                "require_any": [
                    {
                        "patterns": [r"\bfor\b", r"\bwhile\b"],
                        "reason": "one loop should walk the unit table",
                    }
                ],
                "max_lines": 25,
            },
        },
        "typescript": {
            "original_code": dedent_code('''
                function formatBytes(n: number): string {
                    if (n < 1024) {
                        return `${n} B`;
                    }
                    if (n < 1024 * 1024) {
                        const value = Math.floor((n * 10) / 1024) / 10;
                        return `${value.toFixed(1)} KB`;
                    }
                    if (n < 1024 * 1024 * 1024) {
                        const value = Math.floor((n * 10) / (1024 * 1024)) / 10;
                        return `${value.toFixed(1)} MB`;
                    }
                    if (n < 1024 * 1024 * 1024 * 1024) {
                        const value = Math.floor((n * 10) / (1024 * 1024 * 1024)) / 10;
                        return `${value.toFixed(1)} GB`;
                    }
                    const value = Math.floor((n * 10) / (1024 * 1024 * 1024 * 1024)) / 10;
                    return `${value.toFixed(1)} TB`;
                }
            '''),
            "structure": {
                "max_matches": [
                    {
                        "pattern": r"\bKB\b",
                        "max": 2,
                        "reason": "each unit should be named once, in a table",
                    },
                    {
                        "pattern": r"\bif\b",
                        "max": 3,
                        "reason": "the per-unit branches should be gone",
                    },
                ],
                "require_any": [
                    {
                        "patterns": [r"\bfor\b", r"\bwhile\b"],
                        "reason": "one loop should walk the unit table",
                    }
                ],
                "max_lines": 25,
            },
        },
        "go": {
            "original_code": dedent_code('''
                func FormatBytes(n int) string {
                    if n < 1024 {
                        return fmt.Sprintf("%d B", n)
                    }
                    if n < 1024*1024 {
                        value := float64(n*10/1024) / 10
                        return fmt.Sprintf("%.1f KB", value)
                    }
                    if n < 1024*1024*1024 {
                        value := float64(n*10/(1024*1024)) / 10
                        return fmt.Sprintf("%.1f MB", value)
                    }
                    if n < 1024*1024*1024*1024 {
                        value := float64(n*10/(1024*1024*1024)) / 10
                        return fmt.Sprintf("%.1f GB", value)
                    }
                    value := float64(n*10/(1024*1024*1024*1024)) / 10
                    return fmt.Sprintf("%.1f TB", value)
                }
            '''),
            "structure": {
                "max_matches": [
                    {
                        "pattern": r"\bKB\b",
                        "max": 2,
                        "reason": "each unit should be named once, in a table",
                    },
                    {
                        "pattern": r"\bif\b",
                        "max": 3,
                        "reason": "the per-unit branches should be gone",
                    },
                ],
                "require_any": [
                    {"patterns": [r"\bfor\b"], "reason": "one loop should walk the unit table"}
                ],
                "max_lines": 25,
            },
        },
        "rust": {
            "original_code": dedent_code('''
                fn format_bytes(n: i64) -> String {
                    if n < 1024 {
                        return format!("{} B", n);
                    }
                    if n < 1024 * 1024 {
                        let value = (n * 10 / 1024) as f64 / 10.0;
                        return format!("{:.1} KB", value);
                    }
                    if n < 1024 * 1024 * 1024 {
                        let value = (n * 10 / (1024 * 1024)) as f64 / 10.0;
                        return format!("{:.1} MB", value);
                    }
                    if n < 1024 * 1024 * 1024 * 1024 {
                        let value = (n * 10 / (1024 * 1024 * 1024)) as f64 / 10.0;
                        return format!("{:.1} GB", value);
                    }
                    let value = (n * 10 / (1024 * 1024 * 1024 * 1024)) as f64 / 10.0;
                    format!("{:.1} TB", value)
                }
            '''),
            "structure": {
                "max_matches": [
                    {
                        "pattern": r"\bKB\b",
                        "max": 2,
                        "reason": "each unit should be named once, in a table",
                    },
                    {
                        "pattern": r"\bif\b",
                        "max": 3,
                        "reason": "the per-unit branches should be gone",
                    },
                ],
                "require_any": [
                    {
                        "patterns": [r"\bfor\b", r"\bwhile\b", r"\.iter\("],
                        "reason": "one loop should walk the unit table",
                    }
                ],
                "max_lines": 25,
            },
        },
    },
    solutions={
        "python": dedent_code('''
            def format_bytes(n: int) -> str:
                units = ["B", "KB", "MB", "GB", "TB"]
                index = 0
                scale = 1
                while index < len(units) - 1 and n >= scale * 1024:
                    scale *= 1024
                    index += 1
                if index == 0:
                    return f"{n} B"
                value = (n * 10 // scale) / 10
                return f"{value:.1f} {units[index]}"
        '''),
        "typescript": dedent_code('''
            export function formatBytes(n: number): string {
                const units = ["B", "KB", "MB", "GB", "TB"];
                let index = 0;
                let scale = 1;
                while (index < units.length - 1 && n >= scale * 1024) {
                    scale *= 1024;
                    index += 1;
                }
                if (index === 0) return `${n} B`;
                const value = Math.floor((n * 10) / scale) / 10;
                return `${value.toFixed(1)} ${units[index]}`;
            }
        '''),
        "go": dedent_code('''
            package main

            import "fmt"

            func FormatBytes(n int) string {
                units := []string{"B", "KB", "MB", "GB", "TB"}
                index, scale := 0, 1
                for index < len(units)-1 && n >= scale*1024 {
                    scale *= 1024
                    index++
                }
                if index == 0 {
                    return fmt.Sprintf("%d B", n)
                }
                value := float64(n*10/scale) / 10
                return fmt.Sprintf("%.1f %s", value, units[index])
            }
        '''),
        "rust": dedent_code('''
            fn format_bytes(n: i64) -> String {
                let units = ["B", "KB", "MB", "GB", "TB"];
                let mut index = 0;
                let mut scale: i64 = 1;
                while index < units.len() - 1 && n >= scale * 1024 {
                    scale *= 1024;
                    index += 1;
                }
                if index == 0 {
                    return format!("{} B", n);
                }
                let value = (n * 10 / scale) as f64 / 10.0;
                format!("{:.1} {}", value, units[index])
            }
        '''),
    },
)


DEDUPE = Family(
    name="dedupe_preserving_order",
    skill="complexity",
    difficulty="easy",
    io={"args": ["list<str>"], "returns": "list<str>"},
    spec="""
`dedupe_preserving_order` removes duplicate entries while keeping the first
occurrence of each, in order. Behavior must not change:

- The first occurrence of a value stays where it is; later ones are dropped.
- Comparison is exact (case-sensitive, no trimming).
- An empty input returns an empty list.

The current version re-scans everything it has kept for every element, which is
quadratic on the alert streams this runs against. Refactor it into a single
pass using a set or map for membership.
""",
    signatures={
        "python": "def dedupe_preserving_order(items: list[str]) -> list[str]:",
        "typescript": "function dedupePreservingOrder(items: string[]): string[] {",
        "go": "func DedupePreservingOrder(items []string) []string {",
        "rust": "fn dedupe_preserving_order(items: &[&str]) -> Vec<String> {",
    },
    inputs=[
        ["a", "b", "a", "c", "b"],
        ["x", "x", "x"],
        [],
        ["one"],
        ["A", "a", "A"],
        ["p", "q", "r"],
        ["", "", "z"],
        ["node-1", "node-2", "node-1", "node-3", "node-2", "node-1"],
    ],
    reference=dedupe_preserving_order,
    extras={
        "goal": (
            "Replace the nested membership scan with a single pass backed by a "
            "set or map, preserving first-occurrence order."
        )
    },
    lang_extras={
        "python": {
            "original_code": dedent_code('''
                def dedupe_preserving_order(items: list[str]) -> list[str]:
                    out: list[str] = []
                    for item in items:
                        duplicate = False
                        for existing in out:
                            if existing == item:
                                duplicate = True
                        if not duplicate:
                            out.append(item)
                    return out
            '''),
            "structure": {
                "max_matches": [
                    {"pattern": r"\bfor\b", "max": 1, "reason": "one pass, not nested scans"}
                ],
                "require_any": [
                    {
                        "patterns": [r"\bset\(", r"\bdict\b", r"fromkeys", r"\{\}"],
                        "reason": "membership should be a set or map lookup",
                    }
                ],
                "max_lines": 15,
            },
        },
        "typescript": {
            "original_code": dedent_code('''
                function dedupePreservingOrder(items: string[]): string[] {
                    const out: string[] = [];
                    for (const item of items) {
                        let duplicate = false;
                        for (const existing of out) {
                            if (existing === item) {
                                duplicate = true;
                            }
                        }
                        if (!duplicate) {
                            out.push(item);
                        }
                    }
                    return out;
                }
            '''),
            "structure": {
                "max_matches": [
                    {"pattern": r"\bfor\b", "max": 1, "reason": "one pass, not nested scans"}
                ],
                "require_any": [
                    {
                        "patterns": [r"\bSet\b", r"\bMap\b"],
                        "reason": "membership should be a Set or Map lookup",
                    }
                ],
                "max_lines": 15,
            },
        },
        "go": {
            "original_code": dedent_code('''
                func DedupePreservingOrder(items []string) []string {
                    out := []string{}
                    for _, item := range items {
                        duplicate := false
                        for _, existing := range out {
                            if existing == item {
                                duplicate = true
                            }
                        }
                        if !duplicate {
                            out = append(out, item)
                        }
                    }
                    return out
                }
            '''),
            "structure": {
                "max_matches": [
                    {"pattern": r"\bfor\b", "max": 1, "reason": "one pass, not nested scans"}
                ],
                "require_any": [
                    {
                        "patterns": [r"map\[string\]"],
                        "reason": "membership should be a map lookup",
                    }
                ],
                "max_lines": 16,
            },
        },
        "rust": {
            "original_code": dedent_code('''
                fn dedupe_preserving_order(items: &[&str]) -> Vec<String> {
                    let mut out: Vec<String> = Vec::new();
                    for item in items {
                        let mut duplicate = false;
                        for existing in &out {
                            if existing == item {
                                duplicate = true;
                            }
                        }
                        if !duplicate {
                            out.push(item.to_string());
                        }
                    }
                    out
                }
            '''),
            "structure": {
                "max_matches": [
                    {"pattern": r"\bfor\b", "max": 1, "reason": "one pass, not nested scans"}
                ],
                "require_any": [
                    {
                        "patterns": [r"HashSet", r"HashMap", r"BTreeSet"],
                        "reason": "membership should be a set or map lookup",
                    }
                ],
                "max_lines": 16,
            },
        },
    },
    solutions={
        "python": dedent_code('''
            def dedupe_preserving_order(items: list[str]) -> list[str]:
                seen: set[str] = set()
                out: list[str] = []
                for item in items:
                    if item not in seen:
                        seen.add(item)
                        out.append(item)
                return out
        '''),
        "typescript": dedent_code('''
            export function dedupePreservingOrder(items: string[]): string[] {
                const seen = new Set<string>();
                const out: string[] = [];
                for (const item of items) {
                    if (!seen.has(item)) {
                        seen.add(item);
                        out.push(item);
                    }
                }
                return out;
            }
        '''),
        "go": dedent_code('''
            package main

            func DedupePreservingOrder(items []string) []string {
                seen := make(map[string]struct{}, len(items))
                out := []string{}
                for _, item := range items {
                    if _, ok := seen[item]; !ok {
                        seen[item] = struct{}{}
                        out = append(out, item)
                    }
                }
                return out
            }
        '''),
        "rust": dedent_code('''
            use std::collections::HashSet;

            fn dedupe_preserving_order(items: &[&str]) -> Vec<String> {
                let mut seen: HashSet<&str> = HashSet::new();
                let mut out: Vec<String> = Vec::new();
                for item in items {
                    if seen.insert(item) {
                        out.push(item.to_string());
                    }
                }
                out
            }
        '''),
    },
)


FAMILIES = [SEVERITY_RANK, FORMAT_BYTES, DEDUPE, *ADVANCED_FAMILIES]
