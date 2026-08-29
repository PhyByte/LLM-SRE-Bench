"""code_efficiency: correct is necessary, fast enough is the point.

Each family ships small correctness tests plus one *workload*: a 200k-element
input the test runner generates in-language from a seeded LCG, timed inside the
process so compilation and input generation stay out of the measurement. A
quadratic answer still passes the small tests and still compiles — it just
misses the budget, which is exactly the signal this category exists for.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from evaluators.code_exec import workload_inputs  # noqa: E402

from .common import Family, dedent_code  # noqa: E402


def count_pairs(values: list[int], target: int) -> int:
    seen: dict[int, int] = {}
    total = 0
    for value in values:
        total += seen.get(target - value, 0)
        seen[value] = seen.get(value, 0) + 1
    return total


def max_window_sum(values: list[int], k: int) -> int:
    if k <= 0 or len(values) < k:
        return -1
    window = sum(values[:k])
    best = window
    for i in range(k, len(values)):
        window += values[i] - values[i - k]
        best = max(best, window)
    return best


def top_k_frequent(values: list[int], k: int) -> list[int]:
    if k <= 0:
        return []
    counts = Counter(values)
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [value for value, _ in ordered[:k]]


def _with_expected(workload: dict, reference) -> dict:
    """Fill in the workload's answer key from the reference implementation."""
    materialized = workload_inputs(workload)
    args = [materialized[name] for name in workload["call_args"]]
    return {**workload, "expected": reference(*args)}


COUNT_PAIRS_WORKLOAD = _with_expected(
    {
        "seed": 20260817,
        "arrays": [{"name": "values", "n": 200000, "mod": 1000003, "offset": 1}],
        "scalars": {"target": 1000004},
        "call_args": ["values", "target"],
    },
    count_pairs,
)

WINDOW_WORKLOAD = _with_expected(
    {
        "seed": 991733,
        "arrays": [{"name": "values", "n": 200000, "mod": 1000, "offset": 0}],
        "scalars": {"k": 50000},
        "call_args": ["values", "k"],
    },
    max_window_sum,
)

TOPK_WORKLOAD = _with_expected(
    {
        "seed": 570241,
        "arrays": [{"name": "values", "n": 200000, "mod": 5000, "offset": 0}],
        "scalars": {"k": 10},
        "call_args": ["values", "k"],
    },
    top_k_frequent,
)


_BUDGET_NOTE = """
This case is timed. The graders run your function once on a 200,000-element
input and compare the elapsed time against a budget; the obvious quadratic
solution is correct but far too slow to score. Aim for a single pass (or a
sort), not nested scans over the input.
"""


COUNT_PAIRS = Family(
    name="count_pairs",
    skill="hashing",
    difficulty="medium",
    io={"args": ["list<int>", "int"], "returns": "int"},
    spec="""
Count how many index pairs (i, j) with i < j satisfy values[i] + values[j] == target.

Rules:
- Count pairs of *positions*, not pairs of distinct values: [3, 3, 3] with
  target 6 has three pairs.
- The input is unsorted and may contain duplicates.
- Return 0 when there is no such pair, and 0 for inputs shorter than 2.
"""
    + _BUDGET_NOTE,
    signatures={
        "python": "def count_pairs(values: list[int], target: int) -> int:",
        "typescript": "function countPairs(values: number[], target: number): number {",
        "go": "func CountPairs(values []int, target int) int {",
        "rust": "fn count_pairs(values: &[i64], target: i64) -> i64 {",
    },
    inputs=[
        [[1, 2, 3, 4], 5],
        [[3, 3, 3], 6],
        [[1, 1, 1, 1], 2],
        [[5], 5],
        [[], 0],
        [[0, 0, 0], 0],
        [[10, -10, 20, -20], 0],
        [[7, 8, 9], 100],
    ],
    reference=count_pairs,
    extras={"workload": COUNT_PAIRS_WORKLOAD},
    lang_extras={
        "python": {"time_budget_ms": 250},
        "typescript": {"time_budget_ms": 250},
        "go": {"time_budget_ms": 120},
        "rust": {"time_budget_ms": 160},
    },
    solutions={
        "python": dedent_code('''
            def count_pairs(values: list[int], target: int) -> int:
                seen: dict[int, int] = {}
                total = 0
                for value in values:
                    total += seen.get(target - value, 0)
                    seen[value] = seen.get(value, 0) + 1
                return total
        '''),
        "typescript": dedent_code('''
            export function countPairs(values: number[], target: number): number {
                const seen = new Map<number, number>();
                let total = 0;
                for (const value of values) {
                    total += seen.get(target - value) ?? 0;
                    seen.set(value, (seen.get(value) ?? 0) + 1);
                }
                return total;
            }
        '''),
        "go": dedent_code('''
            package main

            func CountPairs(values []int, target int) int {
                seen := make(map[int]int, len(values))
                total := 0
                for _, value := range values {
                    total += seen[target-value]
                    seen[value]++
                }
                return total
            }
        '''),
        "rust": dedent_code('''
            use std::collections::HashMap;

            fn count_pairs(values: &[i64], target: i64) -> i64 {
                let mut seen: HashMap<i64, i64> = HashMap::new();
                let mut total = 0;
                for &value in values {
                    total += seen.get(&(target - value)).copied().unwrap_or(0);
                    *seen.entry(value).or_insert(0) += 1;
                }
                total
            }
        '''),
    },
)


MAX_WINDOW_SUM = Family(
    name="max_window_sum",
    skill="sliding_window",
    difficulty="medium",
    io={"args": ["list<int>", "int"], "returns": "int"},
    spec="""
Return the largest sum of any k consecutive values — the "worst k-sample burst"
question you ask of a metric series.

Rules:
- Windows are contiguous and of exactly length k.
- Return -1 if k <= 0 or if the series is shorter than k.
- Values may be zero; the series is not sorted.
"""
    + _BUDGET_NOTE,
    signatures={
        "python": "def max_window_sum(values: list[int], k: int) -> int:",
        "typescript": "function maxWindowSum(values: number[], k: number): number {",
        "go": "func MaxWindowSum(values []int, k int) int {",
        "rust": "fn max_window_sum(values: &[i64], k: i64) -> i64 {",
    },
    inputs=[
        [[1, 2, 3, 4, 5], 2],
        [[1, 2, 3, 4, 5], 5],
        [[5, 1, 1, 1, 5], 1],
        [[4, 4, 4], 4],
        [[], 1],
        [[9, 9, 9], 0],
        [[2, 0, 7, 1, 0, 8], 3],
        [[6], 1],
    ],
    reference=max_window_sum,
    extras={"workload": WINDOW_WORKLOAD},
    lang_extras={
        "python": {"time_budget_ms": 120},
        "typescript": {"time_budget_ms": 60},
        "go": {"time_budget_ms": 25},
        "rust": {"time_budget_ms": 25},
    },
    solutions={
        "python": dedent_code('''
            def max_window_sum(values: list[int], k: int) -> int:
                if k <= 0 or len(values) < k:
                    return -1
                window = sum(values[:k])
                best = window
                for i in range(k, len(values)):
                    window += values[i] - values[i - k]
                    if window > best:
                        best = window
                return best
        '''),
        "typescript": dedent_code('''
            export function maxWindowSum(values: number[], k: number): number {
                if (k <= 0 || values.length < k) return -1;
                let window = 0;
                for (let i = 0; i < k; i++) window += values[i];
                let best = window;
                for (let i = k; i < values.length; i++) {
                    window += values[i] - values[i - k];
                    if (window > best) best = window;
                }
                return best;
            }
        '''),
        "go": dedent_code('''
            package main

            func MaxWindowSum(values []int, k int) int {
                if k <= 0 || len(values) < k {
                    return -1
                }
                window := 0
                for i := 0; i < k; i++ {
                    window += values[i]
                }
                best := window
                for i := k; i < len(values); i++ {
                    window += values[i] - values[i-k]
                    if window > best {
                        best = window
                    }
                }
                return best
            }
        '''),
        "rust": dedent_code('''
            fn max_window_sum(values: &[i64], k: i64) -> i64 {
                if k <= 0 || (values.len() as i64) < k {
                    return -1;
                }
                let k = k as usize;
                let mut window: i64 = values[..k].iter().sum();
                let mut best = window;
                for i in k..values.len() {
                    window += values[i] - values[i - k];
                    if window > best {
                        best = window;
                    }
                }
                best
            }
        '''),
    },
)


TOP_K_FREQUENT = Family(
    name="top_k_frequent",
    skill="counting",
    difficulty="medium",
    io={"args": ["list<int>", "int"], "returns": "list<int>"},
    spec="""
Return the k most frequent values, most frequent first — the "top talkers"
query you run over a stream of status codes or client ids.

Rules:
- Ties are broken by the smaller value first, so the answer is deterministic.
- Return every distinct value when k is larger than the number of distinct
  values, and an empty list when k <= 0 or the input is empty.
- The result holds the values themselves, not their counts.
"""
    + _BUDGET_NOTE,
    signatures={
        "python": "def top_k_frequent(values: list[int], k: int) -> list[int]:",
        "typescript": "function topKFrequent(values: number[], k: number): number[] {",
        "go": "func TopKFrequent(values []int, k int) []int {",
        "rust": "fn top_k_frequent(values: &[i64], k: i64) -> Vec<i64> {",
    },
    inputs=[
        [[1, 1, 2, 2, 3], 2],
        [[4, 4, 4, 1, 1, 2], 1],
        [[5, 3, 1], 2],
        [[7, 7, 7], 5],
        [[], 3],
        [[9, 9, 8, 8], 0],
        [[2, 2, 3, 3, 1, 1], 3],
        [[6, 5, 6, 5, 4], 2],
    ],
    reference=top_k_frequent,
    extras={"workload": TOPK_WORKLOAD},
    lang_extras={
        "python": {"time_budget_ms": 200},
        "typescript": {"time_budget_ms": 150},
        "go": {"time_budget_ms": 100},
        "rust": {"time_budget_ms": 80},
    },
    solutions={
        "python": dedent_code('''
            def top_k_frequent(values: list[int], k: int) -> list[int]:
                if k <= 0:
                    return []
                counts: dict[int, int] = {}
                for value in values:
                    counts[value] = counts.get(value, 0) + 1
                ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
                return [value for value, _ in ordered[:k]]
        '''),
        "typescript": dedent_code('''
            export function topKFrequent(values: number[], k: number): number[] {
                if (k <= 0) return [];
                const counts = new Map<number, number>();
                for (const value of values) counts.set(value, (counts.get(value) ?? 0) + 1);
                const ordered = [...counts.entries()].sort(
                    (a, b) => (b[1] - a[1]) || (a[0] - b[0]),
                );
                return ordered.slice(0, k).map(([value]) => value);
            }
        '''),
        "go": dedent_code('''
            package main

            import "sort"

            func TopKFrequent(values []int, k int) []int {
                if k <= 0 {
                    return []int{}
                }
                counts := make(map[int]int, len(values))
                for _, value := range values {
                    counts[value]++
                }
                distinct := make([]int, 0, len(counts))
                for value := range counts {
                    distinct = append(distinct, value)
                }
                sort.Slice(distinct, func(i, j int) bool {
                    if counts[distinct[i]] != counts[distinct[j]] {
                        return counts[distinct[i]] > counts[distinct[j]]
                    }
                    return distinct[i] < distinct[j]
                })
                if k > len(distinct) {
                    k = len(distinct)
                }
                return distinct[:k]
            }
        '''),
        "rust": dedent_code('''
            use std::collections::HashMap;

            fn top_k_frequent(values: &[i64], k: i64) -> Vec<i64> {
                if k <= 0 {
                    return Vec::new();
                }
                let mut counts: HashMap<i64, i64> = HashMap::new();
                for &value in values {
                    *counts.entry(value).or_insert(0) += 1;
                }
                let mut distinct: Vec<(i64, i64)> = counts.into_iter().collect();
                distinct.sort_by(|a, b| b.1.cmp(&a.1).then(a.0.cmp(&b.0)));
                distinct.into_iter().take(k as usize).map(|(v, _)| v).collect()
            }
        '''),
    },
)


FAMILIES = [COUNT_PAIRS, MAX_WINDOW_SUM, TOP_K_FREQUENT]
