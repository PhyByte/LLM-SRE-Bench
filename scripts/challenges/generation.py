"""New code_generation families (the original six stay hand-written in the JSON)."""

from __future__ import annotations

import math

from .common import Family, dedent_code
from .generation_advanced import ADVANCED_FAMILIES


def _semver_key(version: str):
    core, _, pre = version.partition("-")
    parts = [int(p) for p in core.split(".") if p != ""]
    while len(parts) < 3:
        parts.append(0)
    return parts[:3], pre


def _compare_prerelease(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return 1  # no prerelease outranks any prerelease
    if not b:
        return -1
    left, right = a.split("."), b.split(".")
    for x, y in zip(left, right):
        x_num, y_num = x.isdigit(), y.isdigit()
        if x_num and y_num:
            if int(x) != int(y):
                return -1 if int(x) < int(y) else 1
        elif x_num != y_num:
            return -1 if x_num else 1
        elif x != y:
            return -1 if x < y else 1
    if len(left) == len(right):
        return 0
    return -1 if len(left) < len(right) else 1


def semver_compare(a: str, b: str) -> int:
    core_a, pre_a = _semver_key(a)
    core_b, pre_b = _semver_key(b)
    if core_a != core_b:
        return -1 if core_a < core_b else 1
    return _compare_prerelease(pre_a, pre_b)


def histogram_quantile(values: list[int], q: float) -> float:
    if not values:
        return -1.0
    q = min(max(q, 0.0), 1.0)
    ordered = sorted(values)
    rank = math.ceil(q * len(ordered))
    rank = min(max(rank, 1), len(ordered))
    return float(ordered[rank - 1])


SEMVER = Family(
    name="semver_compare",
    skill="parsing",
    difficulty="medium",
    io={"args": ["str", "str"], "returns": "int"},
    spec="""
Compare two semantic version strings. Return -1 if `a` sorts before `b`, 0 if
they are equal, and 1 if `a` sorts after `b`.

Rules:
- A version is `MAJOR.MINOR.PATCH` with an optional `-prerelease` suffix.
  Missing components count as 0, so "1.2" equals "1.2.0".
- Numeric components compare numerically, not as text: 1.10.0 is greater than
  1.9.0, and leading zeros are insignificant ("1.01.0" equals "1.1.0").
- A version with a prerelease sorts *before* the same version without one:
  "1.0.0-rc.1" is less than "1.0.0".
- Prereleases are dot-separated identifiers compared left to right. Two numeric
  identifiers compare numerically; a numeric identifier sorts before an
  alphanumeric one; two alphanumeric identifiers compare by ASCII order. If one
  prerelease is a prefix of the other, the shorter one sorts first.
""",
    signatures={
        "python": "def semver_compare(a: str, b: str) -> int:",
        "typescript": "function semverCompare(a: string, b: string): number {",
        "go": "func SemverCompare(a string, b string) int {",
        "rust": "fn semver_compare(a: &str, b: &str) -> i64 {",
    },
    inputs=[
        ["1.0.0", "1.0.0"],
        ["1.10.0", "1.9.0"],
        ["2.0.0", "10.0.0"],
        ["1.2", "1.2.0"],
        ["1.01.0", "1.1.0"],
        ["1.0.0-rc.1", "1.0.0"],
        ["1.0.0-alpha", "1.0.0-alpha.1"],
        ["1.0.0-alpha.1", "1.0.0-alpha.beta"],
        ["1.0.0-beta", "1.0.0-alpha"],
        ["1.0.0-1", "1.0.0-alpha"],
        ["3.4.5", "3.4.5"],
        ["0.9.9", "1.0.0-rc.1"],
    ],
    reference=semver_compare,
    solutions={
        "python": dedent_code('''
            def _parts(version: str):
                core, _, pre = version.partition("-")
                nums = [int(p) for p in core.split(".") if p != ""]
                while len(nums) < 3:
                    nums.append(0)
                return nums[:3], pre


            def _cmp_pre(a: str, b: str) -> int:
                if a == b:
                    return 0
                if not a:
                    return 1
                if not b:
                    return -1
                left, right = a.split("."), b.split(".")
                for x, y in zip(left, right):
                    xn, yn = x.isdigit(), y.isdigit()
                    if xn and yn:
                        if int(x) != int(y):
                            return -1 if int(x) < int(y) else 1
                    elif xn != yn:
                        return -1 if xn else 1
                    elif x != y:
                        return -1 if x < y else 1
                if len(left) == len(right):
                    return 0
                return -1 if len(left) < len(right) else 1


            def semver_compare(a: str, b: str) -> int:
                ca, pa = _parts(a)
                cb, pb = _parts(b)
                if ca != cb:
                    return -1 if ca < cb else 1
                return _cmp_pre(pa, pb)
        '''),
        "typescript": dedent_code('''
            function parts(version: string): [number[], string] {
                const dash = version.indexOf("-");
                const core = dash === -1 ? version : version.slice(0, dash);
                const pre = dash === -1 ? "" : version.slice(dash + 1);
                const nums = core.split(".").filter((p) => p !== "").map((p) => parseInt(p, 10));
                while (nums.length < 3) nums.push(0);
                return [nums.slice(0, 3), pre];
            }

            function isNum(value: string): boolean {
                return /^[0-9]+$/.test(value);
            }

            function cmpPre(a: string, b: string): number {
                if (a === b) return 0;
                if (a === "") return 1;
                if (b === "") return -1;
                const left = a.split("."), right = b.split(".");
                for (let i = 0; i < Math.min(left.length, right.length); i++) {
                    const x = left[i], y = right[i];
                    if (isNum(x) && isNum(y)) {
                        if (parseInt(x, 10) !== parseInt(y, 10)) return parseInt(x, 10) < parseInt(y, 10) ? -1 : 1;
                    } else if (isNum(x) !== isNum(y)) {
                        return isNum(x) ? -1 : 1;
                    } else if (x !== y) {
                        return x < y ? -1 : 1;
                    }
                }
                if (left.length === right.length) return 0;
                return left.length < right.length ? -1 : 1;
            }

            export function semverCompare(a: string, b: string): number {
                const [ca, pa] = parts(a);
                const [cb, pb] = parts(b);
                for (let i = 0; i < 3; i++) {
                    if (ca[i] !== cb[i]) return ca[i] < cb[i] ? -1 : 1;
                }
                return cmpPre(pa, pb);
            }
        '''),
        "go": dedent_code('''
            package main

            import (
                "strconv"
                "strings"
            )

            func semverParts(version string) ([3]int, string) {
                core, pre, _ := strings.Cut(version, "-")
                var nums [3]int
                for i, p := range strings.Split(core, ".") {
                    if i > 2 || p == "" {
                        continue
                    }
                    n, _ := strconv.Atoi(p)
                    nums[i] = n
                }
                return nums, pre
            }

            func isNumeric(s string) bool {
                if s == "" {
                    return false
                }
                for _, r := range s {
                    if r < '0' || r > '9' {
                        return false
                    }
                }
                return true
            }

            func cmpPre(a, b string) int {
                if a == b {
                    return 0
                }
                if a == "" {
                    return 1
                }
                if b == "" {
                    return -1
                }
                left := strings.Split(a, ".")
                right := strings.Split(b, ".")
                n := len(left)
                if len(right) < n {
                    n = len(right)
                }
                for i := 0; i < n; i++ {
                    x, y := left[i], right[i]
                    xn, yn := isNumeric(x), isNumeric(y)
                    switch {
                    case xn && yn:
                        xi, _ := strconv.Atoi(x)
                        yi, _ := strconv.Atoi(y)
                        if xi != yi {
                            if xi < yi {
                                return -1
                            }
                            return 1
                        }
                    case xn != yn:
                        if xn {
                            return -1
                        }
                        return 1
                    case x != y:
                        if x < y {
                            return -1
                        }
                        return 1
                    }
                }
                if len(left) == len(right) {
                    return 0
                }
                if len(left) < len(right) {
                    return -1
                }
                return 1
            }

            func SemverCompare(a string, b string) int {
                ca, pa := semverParts(a)
                cb, pb := semverParts(b)
                for i := 0; i < 3; i++ {
                    if ca[i] != cb[i] {
                        if ca[i] < cb[i] {
                            return -1
                        }
                        return 1
                    }
                }
                return cmpPre(pa, pb)
            }
        '''),
        "rust": dedent_code('''
            fn semver_parts(version: &str) -> ([i64; 3], String) {
                let (core, pre) = match version.find('-') {
                    Some(i) => (&version[..i], version[i + 1..].to_string()),
                    None => (version, String::new()),
                };
                let mut nums = [0i64; 3];
                for (i, part) in core.split('.').enumerate() {
                    if i > 2 || part.is_empty() {
                        continue;
                    }
                    nums[i] = part.parse::<i64>().unwrap_or(0);
                }
                (nums, pre)
            }

            fn is_numeric(s: &str) -> bool {
                !s.is_empty() && s.chars().all(|c| c.is_ascii_digit())
            }

            fn cmp_pre(a: &str, b: &str) -> i64 {
                if a == b {
                    return 0;
                }
                if a.is_empty() {
                    return 1;
                }
                if b.is_empty() {
                    return -1;
                }
                let left: Vec<&str> = a.split('.').collect();
                let right: Vec<&str> = b.split('.').collect();
                for i in 0..left.len().min(right.len()) {
                    let (x, y) = (left[i], right[i]);
                    if is_numeric(x) && is_numeric(y) {
                        let (xi, yi) = (x.parse::<i64>().unwrap(), y.parse::<i64>().unwrap());
                        if xi != yi {
                            return if xi < yi { -1 } else { 1 };
                        }
                    } else if is_numeric(x) != is_numeric(y) {
                        return if is_numeric(x) { -1 } else { 1 };
                    } else if x != y {
                        return if x < y { -1 } else { 1 };
                    }
                }
                if left.len() == right.len() {
                    0
                } else if left.len() < right.len() {
                    -1
                } else {
                    1
                }
            }

            fn semver_compare(a: &str, b: &str) -> i64 {
                let (ca, pa) = semver_parts(a);
                let (cb, pb) = semver_parts(b);
                for i in 0..3 {
                    if ca[i] != cb[i] {
                        return if ca[i] < cb[i] { -1 } else { 1 };
                    }
                }
                cmp_pre(&pa, &pb)
            }
        '''),
    },
)


QUANTILE = Family(
    name="histogram_quantile",
    skill="numeric",
    difficulty="easy",
    io={"args": ["list<int>", "float"], "returns": "float"},
    spec="""
Compute a nearest-rank quantile of a latency sample, the way a dashboard shows
p50/p95/p99.

Rules:
- Sort the values ascending. The rank is ceil(q * n), clamped into [1, n], and
  the result is the value at that 1-based rank.
- The input is not sorted, and must not be assumed sorted.
- Clamp q into [0.0, 1.0] before using it, so q = -1 behaves like q = 0 and
  q = 5 behaves like q = 1.
- An empty sample has no quantile: return -1.0.
- Return the value as a floating-point number.
""",
    signatures={
        "python": "def histogram_quantile(values: list[int], q: float) -> float:",
        "typescript": "function histogramQuantile(values: number[], q: number): number {",
        "go": "func HistogramQuantile(values []int, q float64) float64 {",
        "rust": "fn histogram_quantile(values: &[i64], q: f64) -> f64 {",
    },
    inputs=[
        [[10, 20, 30, 40, 50], 0.5],
        [[10, 20, 30, 40, 50], 0.9],
        [[10, 20, 30, 40, 50], 0.0],
        [[10, 20, 30, 40, 50], 1.0],
        [[30, 10, 50, 20, 40], 0.5],
        [[5], 0.99],
        [[], 0.5],
        [[1, 2, 3, 4], 0.75],
        [[7, 7, 7], 0.33],
        [[10, 20, 30], -1.0],
        [[10, 20, 30], 5.0],
        [[100, 200], 0.5],
    ],
    reference=histogram_quantile,
    solutions={
        "python": dedent_code('''
            import math


            def histogram_quantile(values: list[int], q: float) -> float:
                if not values:
                    return -1.0
                q = min(max(q, 0.0), 1.0)
                ordered = sorted(values)
                rank = min(max(math.ceil(q * len(ordered)), 1), len(ordered))
                return float(ordered[rank - 1])
        '''),
        "typescript": dedent_code('''
            export function histogramQuantile(values: number[], q: number): number {
                if (values.length === 0) return -1.0;
                const clamped = Math.min(Math.max(q, 0), 1);
                const ordered = [...values].sort((a, b) => a - b);
                let rank = Math.ceil(clamped * ordered.length);
                rank = Math.min(Math.max(rank, 1), ordered.length);
                return ordered[rank - 1];
            }
        '''),
        "go": dedent_code('''
            package main

            import (
                "math"
                "sort"
            )

            func HistogramQuantile(values []int, q float64) float64 {
                if len(values) == 0 {
                    return -1.0
                }
                if q < 0 {
                    q = 0
                }
                if q > 1 {
                    q = 1
                }
                ordered := append([]int(nil), values...)
                sort.Ints(ordered)
                rank := int(math.Ceil(q * float64(len(ordered))))
                if rank < 1 {
                    rank = 1
                }
                if rank > len(ordered) {
                    rank = len(ordered)
                }
                return float64(ordered[rank-1])
            }
        '''),
        "rust": dedent_code('''
            fn histogram_quantile(values: &[i64], q: f64) -> f64 {
                if values.is_empty() {
                    return -1.0;
                }
                let q = q.clamp(0.0, 1.0);
                let mut ordered = values.to_vec();
                ordered.sort();
                let mut rank = (q * ordered.len() as f64).ceil() as usize;
                if rank < 1 {
                    rank = 1;
                }
                if rank > ordered.len() {
                    rank = ordered.len();
                }
                ordered[rank - 1] as f64
            }
        '''),
    },
)


FAMILIES = [SEMVER, QUANTILE, *ADVANCED_FAMILIES]
