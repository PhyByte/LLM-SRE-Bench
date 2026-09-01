"""Harder code_efficiency families.

Same contract as ``efficiency.py`` — small correctness tests plus one timed
200k-element workload — but chosen so the naive answer is not merely slower, it
is a different algorithm. Every family here has an obvious O(n^2) (or O(n*k))
solution that a model reaches for by default and an intended O(n) / O(n log n)
one, so the budget separates "knows the trick" from "wrote something correct".
"""

from __future__ import annotations

import bisect
import heapq
import sys
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from evaluators.code_exec import workload_inputs  # noqa: E402

from .common import BUDGET_NOTE, Family, dedent_code  # noqa: E402


def _with_expected(workload: dict, reference) -> dict:
    """Fill in the workload's answer key from the reference implementation."""
    materialized = workload_inputs(workload)
    args = [materialized[name] for name in workload["call_args"]]
    return {**workload, "expected": reference(*args)}


# ---------------------------------------------------------------------------
# Reference implementations. These also compute the workload answer keys, so
# they have to be the fast versions themselves.
# ---------------------------------------------------------------------------


def count_inversions(values: list[int]) -> int:
    def sort_count(arr: list[int]) -> tuple[list[int], int]:
        if len(arr) < 2:
            return arr, 0
        mid = len(arr) // 2
        left, a = sort_count(arr[:mid])
        right, b = sort_count(arr[mid:])
        merged: list[int] = []
        total = a + b
        i = j = 0
        while i < len(left) and j < len(right):
            if left[i] <= right[j]:
                merged.append(left[i])
                i += 1
            else:
                merged.append(right[j])
                j += 1
                total += len(left) - i
        merged.extend(left[i:])
        merged.extend(right[j:])
        return merged, total

    return sort_count(list(values))[1]


def longest_unique_run(values: list[int]) -> int:
    last: dict[int, int] = {}
    best = 0
    start = 0
    for i, value in enumerate(values):
        seen_at = last.get(value)
        if seen_at is not None and seen_at >= start:
            start = seen_at + 1
        last[value] = i
        if i - start + 1 > best:
            best = i - start + 1
    return best


def largest_rectangle(heights: list[int]) -> int:
    stack: list[int] = []
    best = 0
    n = len(heights)
    for i in range(n + 1):
        h = heights[i] if i < n else 0
        while stack and heights[stack[-1]] >= h:
            top = stack.pop()
            left = stack[-1] if stack else -1
            area = heights[top] * (i - left - 1)
            if area > best:
                best = area
        stack.append(i)
    return best


def window_max_total(values: list[int], k: int) -> int:
    if k <= 0 or len(values) < k:
        return -1
    window: deque[int] = deque()
    total = 0
    for i, value in enumerate(values):
        while window and values[window[-1]] <= value:
            window.pop()
        window.append(i)
        if window[0] <= i - k:
            window.popleft()
        if i >= k - 1:
            total += values[window[0]]
    return total


def longest_increasing_run(values: list[int]) -> int:
    tails: list[int] = []
    for value in values:
        index = bisect.bisect_left(tails, value)
        if index == len(tails):
            tails.append(value)
        else:
            tails[index] = value
    return len(tails)


def trapped_water(heights: list[int]) -> int:
    if len(heights) < 3:
        return 0
    left, right = 0, len(heights) - 1
    left_max, right_max = heights[left], heights[right]
    total = 0
    while left < right:
        if left_max <= right_max:
            left += 1
            if heights[left] > left_max:
                left_max = heights[left]
            else:
                total += left_max - heights[left]
        else:
            right -= 1
            if heights[right] > right_max:
                right_max = heights[right]
            else:
                total += right_max - heights[right]
    return total


def distinct_window_total(values: list[int], k: int) -> int:
    if k <= 0 or len(values) < k:
        return -1
    counts: dict[int, int] = {}
    distinct = 0
    total = 0
    for i, value in enumerate(values):
        if counts.get(value, 0) == 0:
            distinct += 1
        counts[value] = counts.get(value, 0) + 1
        if i >= k:
            leaving = values[i - k]
            counts[leaving] -= 1
            if counts[leaving] == 0:
                distinct -= 1
        if i >= k - 1:
            total += distinct
    return total


def min_rooms(starts: list[int], durations: list[int]) -> int:
    n = min(len(starts), len(durations))
    if n == 0:
        return 0
    begins = sorted(starts[:n])
    ends = sorted(starts[i] + durations[i] for i in range(n))
    best = 0
    active = 0
    j = 0
    for i in range(n):
        while j < n and ends[j] <= begins[i]:
            active -= 1
            j += 1
        active += 1
        if active > best:
            best = active
    return best


def running_median_sum(values: list[int]) -> int:
    low: list[int] = []  # max-heap via negation
    high: list[int] = []  # min-heap
    total = 0
    for value in values:
        if low and value > -low[0]:
            heapq.heappush(high, value)
        else:
            heapq.heappush(low, -value)
        if len(low) > len(high) + 1:
            heapq.heappush(high, -heapq.heappop(low))
        elif len(high) > len(low):
            heapq.heappush(low, -heapq.heappop(high))
        total += -low[0]
    return total


def max_xor_pair(values: list[int]) -> int:
    if len(values) < 2:
        return 0
    top = max(values)
    if top <= 0:
        return 0
    high = 0
    while (1 << (high + 1)) <= top:
        high += 1
    best = 0
    mask = 0
    for bit in range(high, -1, -1):
        mask |= 1 << bit
        prefixes = {value & mask for value in values}
        candidate = best | (1 << bit)
        for prefix in prefixes:
            if (candidate ^ prefix) in prefixes:
                best = candidate
                break
    return best


# ---------------------------------------------------------------------------
# Workloads
# ---------------------------------------------------------------------------

INVERSIONS_WORKLOAD = _with_expected(
    {
        "seed": 33107711,
        "arrays": [{"name": "values", "n": 200000, "mod": 100000, "offset": 0}],
        "call_args": ["values"],
    },
    count_inversions,
)

UNIQUE_RUN_WORKLOAD = _with_expected(
    {
        "seed": 6620391,
        "arrays": [{"name": "values", "n": 200000, "mod": 64, "offset": 0}],
        "call_args": ["values"],
    },
    longest_unique_run,
)

RECTANGLE_WORKLOAD = _with_expected(
    {
        "seed": 41180923,
        "arrays": [{"name": "heights", "n": 200000, "mod": 1000, "offset": 0}],
        "call_args": ["heights"],
    },
    largest_rectangle,
)

WINDOW_MAX_WORKLOAD = _with_expected(
    {
        "seed": 7712849,
        "arrays": [{"name": "values", "n": 200000, "mod": 1000, "offset": 0}],
        "scalars": {"k": 5000},
        "call_args": ["values", "k"],
    },
    window_max_total,
)

INCREASING_RUN_WORKLOAD = _with_expected(
    {
        "seed": 9930277,
        "arrays": [{"name": "values", "n": 200000, "mod": 1000000, "offset": 0}],
        "call_args": ["values"],
    },
    longest_increasing_run,
)

WATER_WORKLOAD = _with_expected(
    {
        "seed": 15583307,
        "arrays": [{"name": "heights", "n": 200000, "mod": 1000, "offset": 0}],
        "call_args": ["heights"],
    },
    trapped_water,
)

DISTINCT_WINDOW_WORKLOAD = _with_expected(
    {
        "seed": 28840111,
        # mod well above k so each window holds a different number of distinct
        # values; a narrower range would make every window saturate at `mod`.
        "arrays": [{"name": "values", "n": 200000, "mod": 5000, "offset": 0}],
        "scalars": {"k": 2000},
        "call_args": ["values", "k"],
    },
    distinct_window_total,
)

ROOMS_WORKLOAD = _with_expected(
    {
        "seed": 51004493,
        "arrays": [
            {"name": "starts", "n": 200000, "mod": 1000000, "offset": 0},
            {"name": "durations", "n": 200000, "mod": 1000, "offset": 1},
        ],
        "call_args": ["starts", "durations"],
    },
    min_rooms,
)

MEDIAN_WORKLOAD = _with_expected(
    {
        "seed": 60221399,
        "arrays": [{"name": "values", "n": 200000, "mod": 1000, "offset": 0}],
        "call_args": ["values"],
    },
    running_median_sum,
)

XOR_WORKLOAD = _with_expected(
    {
        "seed": 77300281,
        "arrays": [{"name": "values", "n": 200000, "mod": 1048576, "offset": 0}],
        "call_args": ["values"],
    },
    max_xor_pair,
)


# ---------------------------------------------------------------------------
# Families
# ---------------------------------------------------------------------------

COUNT_INVERSIONS = Family(
    name="count_inversions",
    skill="divide_and_conquer",
    difficulty="hard",
    io={"args": ["list<int>"], "returns": "int"},
    spec="""
Count the inversions in a series: the number of index pairs (i, j) with i < j
and values[i] > values[j]. It is the standard measure of how far a list is from
sorted, and the same count a merge sort accumulates on its way through.

Rules:
- Compare positions, not distinct values: equal values are not an inversion.
- A sorted series has 0 inversions; a strictly descending series of length n has
  n * (n - 1) / 2.
- Return 0 for series shorter than 2.
- The count can exceed a 32-bit integer on the timed input, so accumulate it in
  a 64-bit-safe way.
"""
    + BUDGET_NOTE,
    signatures={
        "python": "def count_inversions(values: list[int]) -> int:",
        "typescript": "function countInversions(values: number[]): number {",
        "go": "func CountInversions(values []int) int {",
        "rust": "fn count_inversions(values: &[i64]) -> i64 {",
    },
    inputs=[
        [1, 2, 3, 4],
        [4, 3, 2, 1],
        [2, 2, 2],
        [1],
        [],
        [5, 1, 4, 2, 3],
        [10, 10, 9, 9],
        [3, 1, 2],
    ],
    reference=count_inversions,
    extras={"workload": INVERSIONS_WORKLOAD},
    lang_extras={
        "python": {"time_budget_ms": 1800},
        "typescript": {"time_budget_ms": 280},
        "go": {"time_budget_ms": 220},
        "rust": {"time_budget_ms": 200},
    },
    solutions={
        "python": dedent_code('''
            def count_inversions(values: list[int]) -> int:
                def sort_count(arr):
                    if len(arr) < 2:
                        return arr, 0
                    mid = len(arr) // 2
                    left, a = sort_count(arr[:mid])
                    right, b = sort_count(arr[mid:])
                    merged = []
                    total = a + b
                    i = j = 0
                    while i < len(left) and j < len(right):
                        if left[i] <= right[j]:
                            merged.append(left[i])
                            i += 1
                        else:
                            merged.append(right[j])
                            j += 1
                            total += len(left) - i
                    merged.extend(left[i:])
                    merged.extend(right[j:])
                    return merged, total

                return sort_count(list(values))[1]
        '''),
        "typescript": dedent_code('''
            function sortCount(arr: number[]): [number[], number] {
                if (arr.length < 2) return [arr, 0];
                const mid = Math.floor(arr.length / 2);
                const [left, a] = sortCount(arr.slice(0, mid));
                const [right, b] = sortCount(arr.slice(mid));
                const merged: number[] = new Array(arr.length);
                let total = a + b;
                let i = 0, j = 0, w = 0;
                while (i < left.length && j < right.length) {
                    if (left[i] <= right[j]) {
                        merged[w++] = left[i++];
                    } else {
                        merged[w++] = right[j++];
                        total += left.length - i;
                    }
                }
                while (i < left.length) merged[w++] = left[i++];
                while (j < right.length) merged[w++] = right[j++];
                return [merged, total];
            }

            export function countInversions(values: number[]): number {
                return sortCount(values.slice())[1];
            }
        '''),
        "go": dedent_code('''
            package main

            func sortCount(arr []int) ([]int, int) {
                if len(arr) < 2 {
                    return arr, 0
                }
                mid := len(arr) / 2
                left, a := sortCount(append([]int(nil), arr[:mid]...))
                right, b := sortCount(append([]int(nil), arr[mid:]...))
                merged := make([]int, 0, len(arr))
                total := a + b
                i, j := 0, 0
                for i < len(left) && j < len(right) {
                    if left[i] <= right[j] {
                        merged = append(merged, left[i])
                        i++
                    } else {
                        merged = append(merged, right[j])
                        j++
                        total += len(left) - i
                    }
                }
                merged = append(merged, left[i:]...)
                merged = append(merged, right[j:]...)
                return merged, total
            }

            func CountInversions(values []int) int {
                _, total := sortCount(append([]int(nil), values...))
                return total
            }
        '''),
        "rust": dedent_code('''
            fn sort_count(arr: &[i64]) -> (Vec<i64>, i64) {
                if arr.len() < 2 {
                    return (arr.to_vec(), 0);
                }
                let mid = arr.len() / 2;
                let (left, a) = sort_count(&arr[..mid]);
                let (right, b) = sort_count(&arr[mid..]);
                let mut merged: Vec<i64> = Vec::with_capacity(arr.len());
                let mut total = a + b;
                let (mut i, mut j) = (0usize, 0usize);
                while i < left.len() && j < right.len() {
                    if left[i] <= right[j] {
                        merged.push(left[i]);
                        i += 1;
                    } else {
                        merged.push(right[j]);
                        j += 1;
                        total += (left.len() - i) as i64;
                    }
                }
                while i < left.len() {
                    merged.push(left[i]);
                    i += 1;
                }
                while j < right.len() {
                    merged.push(right[j]);
                    j += 1;
                }
                (merged, total)
            }

            fn count_inversions(values: &[i64]) -> i64 {
                sort_count(values).1
            }
        '''),
    },
)


LONGEST_UNIQUE_RUN = Family(
    name="longest_unique_run",
    skill="sliding_window",
    difficulty="hard",
    io={"args": ["list<int>"], "returns": "int"},
    spec="""
Return the length of the longest contiguous stretch in which no value repeats —
the longest window of a request log where every client id is different.

Rules:
- The stretch must be contiguous.
- Return 0 for an empty series.
- A series with no repeats at all is entirely one stretch, so the answer is its
  length.
"""
    + BUDGET_NOTE,
    signatures={
        "python": "def longest_unique_run(values: list[int]) -> int:",
        "typescript": "function longestUniqueRun(values: number[]): number {",
        "go": "func LongestUniqueRun(values []int) int {",
        "rust": "fn longest_unique_run(values: &[i64]) -> i64 {",
    },
    inputs=[
        [1, 2, 3, 1, 2],
        [1, 1, 1, 1],
        [],
        [7],
        [1, 2, 3, 4, 5],
        [4, 5, 4, 5, 4],
        [9, 8, 9, 7, 6, 8],
        [0, 0, 1, 2, 3, 0],
    ],
    reference=longest_unique_run,
    extras={"workload": UNIQUE_RUN_WORKLOAD},
    lang_extras={
        "python": {"time_budget_ms": 90},
        "typescript": {"time_budget_ms": 50},
        "go": {"time_budget_ms": 40},
        "rust": {"time_budget_ms": 35},
    },
    solutions={
        "python": dedent_code('''
            def longest_unique_run(values: list[int]) -> int:
                last = {}
                best = 0
                start = 0
                for i, value in enumerate(values):
                    seen_at = last.get(value)
                    if seen_at is not None and seen_at >= start:
                        start = seen_at + 1
                    last[value] = i
                    if i - start + 1 > best:
                        best = i - start + 1
                return best
        '''),
        "typescript": dedent_code('''
            export function longestUniqueRun(values: number[]): number {
                const last = new Map<number, number>();
                let best = 0;
                let start = 0;
                for (let i = 0; i < values.length; i++) {
                    const seenAt = last.get(values[i]);
                    if (seenAt !== undefined && seenAt >= start) start = seenAt + 1;
                    last.set(values[i], i);
                    if (i - start + 1 > best) best = i - start + 1;
                }
                return best;
            }
        '''),
        "go": dedent_code('''
            package main

            func LongestUniqueRun(values []int) int {
                last := make(map[int]int, len(values))
                best := 0
                start := 0
                for i, value := range values {
                    if seenAt, ok := last[value]; ok && seenAt >= start {
                        start = seenAt + 1
                    }
                    last[value] = i
                    if i-start+1 > best {
                        best = i - start + 1
                    }
                }
                return best
            }
        '''),
        "rust": dedent_code('''
            use std::collections::HashMap;

            fn longest_unique_run(values: &[i64]) -> i64 {
                let mut last: HashMap<i64, usize> = HashMap::new();
                let mut best: i64 = 0;
                let mut start: usize = 0;
                for (i, &value) in values.iter().enumerate() {
                    if let Some(&seen_at) = last.get(&value) {
                        if seen_at >= start {
                            start = seen_at + 1;
                        }
                    }
                    last.insert(value, i);
                    let span = (i - start + 1) as i64;
                    if span > best {
                        best = span;
                    }
                }
                best
            }
        '''),
    },
)


LARGEST_RECTANGLE = Family(
    name="largest_rectangle",
    skill="monotonic_stack",
    difficulty="hard",
    io={"args": ["list<int>"], "returns": "int"},
    spec="""
Given bar heights standing side by side, each one unit wide, return the area of
the largest axis-aligned rectangle that fits entirely inside the histogram.

Rules:
- The rectangle spans a contiguous range of bars and its height is the smallest
  bar in that range, so the area is (smallest height) * (number of bars).
- Heights are non-negative and may repeat.
- Return 0 for an empty histogram.
"""
    + BUDGET_NOTE,
    signatures={
        "python": "def largest_rectangle(heights: list[int]) -> int:",
        "typescript": "function largestRectangle(heights: number[]): number {",
        "go": "func LargestRectangle(heights []int) int {",
        "rust": "fn largest_rectangle(heights: &[i64]) -> i64 {",
    },
    inputs=[
        [2, 1, 5, 6, 2, 3],
        [2, 2],
        [],
        [5],
        [0, 0, 0],
        [1, 2, 3, 4, 5],
        [5, 4, 3, 2, 1],
        [3, 1, 3, 1, 3],
    ],
    reference=largest_rectangle,
    extras={"workload": RECTANGLE_WORKLOAD},
    lang_extras={
        "python": {"time_budget_ms": 170},
        "typescript": {"time_budget_ms": 40},
        "go": {"time_budget_ms": 25},
        "rust": {"time_budget_ms": 25},
    },
    solutions={
        "python": dedent_code('''
            def largest_rectangle(heights: list[int]) -> int:
                stack = []
                best = 0
                n = len(heights)
                for i in range(n + 1):
                    h = heights[i] if i < n else 0
                    while stack and heights[stack[-1]] >= h:
                        top = stack.pop()
                        left = stack[-1] if stack else -1
                        area = heights[top] * (i - left - 1)
                        if area > best:
                            best = area
                    stack.append(i)
                return best
        '''),
        "typescript": dedent_code('''
            export function largestRectangle(heights: number[]): number {
                const stack: number[] = [];
                let best = 0;
                const n = heights.length;
                for (let i = 0; i <= n; i++) {
                    const h = i < n ? heights[i] : 0;
                    while (stack.length > 0 && heights[stack[stack.length - 1]] >= h) {
                        const top = stack.pop() as number;
                        const left = stack.length > 0 ? stack[stack.length - 1] : -1;
                        const area = heights[top] * (i - left - 1);
                        if (area > best) best = area;
                    }
                    stack.push(i);
                }
                return best;
            }
        '''),
        "go": dedent_code('''
            package main

            func LargestRectangle(heights []int) int {
                stack := make([]int, 0, len(heights)+1)
                best := 0
                n := len(heights)
                for i := 0; i <= n; i++ {
                    h := 0
                    if i < n {
                        h = heights[i]
                    }
                    for len(stack) > 0 && heights[stack[len(stack)-1]] >= h {
                        top := stack[len(stack)-1]
                        stack = stack[:len(stack)-1]
                        left := -1
                        if len(stack) > 0 {
                            left = stack[len(stack)-1]
                        }
                        area := heights[top] * (i - left - 1)
                        if area > best {
                            best = area
                        }
                    }
                    stack = append(stack, i)
                }
                return best
            }
        '''),
        "rust": dedent_code('''
            fn largest_rectangle(heights: &[i64]) -> i64 {
                let n = heights.len();
                let mut stack: Vec<usize> = Vec::with_capacity(n + 1);
                let mut best: i64 = 0;
                for i in 0..=n {
                    let h = if i < n { heights[i] } else { 0 };
                    while let Some(&top) = stack.last() {
                        if heights[top] < h {
                            break;
                        }
                        stack.pop();
                        let left = match stack.last() {
                            Some(&x) => x as i64,
                            None => -1,
                        };
                        let area = heights[top] * (i as i64 - left - 1);
                        if area > best {
                            best = area;
                        }
                    }
                    stack.push(i);
                }
                best
            }
        '''),
    },
)


WINDOW_MAX_TOTAL = Family(
    name="window_max_total",
    skill="monotonic_deque",
    difficulty="hard",
    io={"args": ["list<int>", "int"], "returns": "int"},
    spec="""
Slide a window of exactly k samples across the series and add up the maximum of
each window position — the total of the per-window peaks a rolling-max alert
would have fired on.

Rules:
- Windows are contiguous and of exactly length k, so a series of length n has
  n - k + 1 of them.
- Return -1 if k <= 0 or if the series is shorter than k.
- Recomputing the maximum of every window from scratch is the slow answer; the
  intended one visits each element a constant number of times.
"""
    + BUDGET_NOTE,
    signatures={
        "python": "def window_max_total(values: list[int], k: int) -> int:",
        "typescript": "function windowMaxTotal(values: number[], k: number): number {",
        "go": "func WindowMaxTotal(values []int, k int) int {",
        "rust": "fn window_max_total(values: &[i64], k: i64) -> i64 {",
    },
    inputs=[
        [[1, 3, 2, 5, 4], 2],
        [[1, 3, 2, 5, 4], 5],
        [[4, 4, 4], 1],
        [[], 1],
        [[7, 2], 0],
        [[1, 2], 3],
        [[9, 1, 1, 1, 9], 3],
        [[5, 4, 3, 2, 1], 2],
    ],
    reference=window_max_total,
    extras={"workload": WINDOW_MAX_WORKLOAD},
    lang_extras={
        "python": {"time_budget_ms": 180},
        "typescript": {"time_budget_ms": 40},
        "go": {"time_budget_ms": 30},
        "rust": {"time_budget_ms": 30},
    },
    solutions={
        "python": dedent_code('''
            from collections import deque


            def window_max_total(values: list[int], k: int) -> int:
                if k <= 0 or len(values) < k:
                    return -1
                window = deque()
                total = 0
                for i, value in enumerate(values):
                    while window and values[window[-1]] <= value:
                        window.pop()
                    window.append(i)
                    if window[0] <= i - k:
                        window.popleft()
                    if i >= k - 1:
                        total += values[window[0]]
                return total
        '''),
        "typescript": dedent_code('''
            export function windowMaxTotal(values: number[], k: number): number {
                if (k <= 0 || values.length < k) return -1;
                const window = new Int32Array(values.length);
                let head = 0, tail = 0;
                let total = 0;
                for (let i = 0; i < values.length; i++) {
                    while (tail > head && values[window[tail - 1]] <= values[i]) tail--;
                    window[tail++] = i;
                    if (window[head] <= i - k) head++;
                    if (i >= k - 1) total += values[window[head]];
                }
                return total;
            }
        '''),
        "go": dedent_code('''
            package main

            func WindowMaxTotal(values []int, k int) int {
                if k <= 0 || len(values) < k {
                    return -1
                }
                window := make([]int, 0, len(values))
                total := 0
                for i, value := range values {
                    for len(window) > 0 && values[window[len(window)-1]] <= value {
                        window = window[:len(window)-1]
                    }
                    window = append(window, i)
                    if window[0] <= i-k {
                        window = window[1:]
                    }
                    if i >= k-1 {
                        total += values[window[0]]
                    }
                }
                return total
            }
        '''),
        "rust": dedent_code('''
            use std::collections::VecDeque;

            fn window_max_total(values: &[i64], k: i64) -> i64 {
                if k <= 0 || (values.len() as i64) < k {
                    return -1;
                }
                let k = k as usize;
                let mut window: VecDeque<usize> = VecDeque::new();
                let mut total: i64 = 0;
                for i in 0..values.len() {
                    while let Some(&back) = window.back() {
                        if values[back] <= values[i] {
                            window.pop_back();
                        } else {
                            break;
                        }
                    }
                    window.push_back(i);
                    if let Some(&front) = window.front() {
                        if front + k <= i {
                            window.pop_front();
                        }
                    }
                    if i + 1 >= k {
                        total += values[*window.front().unwrap()];
                    }
                }
                total
            }
        '''),
    },
)


LONGEST_INCREASING_RUN = Family(
    name="longest_increasing_run",
    skill="dynamic_programming",
    difficulty="hard",
    io={"args": ["list<int>"], "returns": "int"},
    spec="""
Return the length of the longest strictly increasing subsequence: pick values
left to right, skipping as many as you like, so that each kept value is strictly
greater than the previous one.

Rules:
- The picked values keep their original order but need not be adjacent.
- Strictly increasing, so equal values cannot both be kept.
- Return 0 for an empty series.
- The straightforward "compare against every earlier element" answer is
  quadratic; the intended one is O(n log n).
"""
    + BUDGET_NOTE,
    signatures={
        "python": "def longest_increasing_run(values: list[int]) -> int:",
        "typescript": "function longestIncreasingRun(values: number[]): number {",
        "go": "func LongestIncreasingRun(values []int) int {",
        "rust": "fn longest_increasing_run(values: &[i64]) -> i64 {",
    },
    inputs=[
        [1, 2, 3, 4],
        [4, 3, 2, 1],
        [],
        [2, 2, 2],
        [10, 9, 2, 5, 3, 7, 101, 18],
        [7],
        [1, 3, 2, 4, 3, 5],
        [0, 8, 4, 12, 2, 10, 6, 14],
    ],
    reference=longest_increasing_run,
    extras={"workload": INCREASING_RUN_WORKLOAD},
    lang_extras={
        "python": {"time_budget_ms": 160},
        "typescript": {"time_budget_ms": 70},
        "go": {"time_budget_ms": 70},
        "rust": {"time_budget_ms": 40},
    },
    solutions={
        "python": dedent_code('''
            import bisect


            def longest_increasing_run(values: list[int]) -> int:
                tails = []
                for value in values:
                    index = bisect.bisect_left(tails, value)
                    if index == len(tails):
                        tails.append(value)
                    else:
                        tails[index] = value
                return len(tails)
        '''),
        "typescript": dedent_code('''
            export function longestIncreasingRun(values: number[]): number {
                const tails: number[] = [];
                for (const value of values) {
                    let lo = 0, hi = tails.length;
                    while (lo < hi) {
                        const mid = (lo + hi) >> 1;
                        if (tails[mid] < value) lo = mid + 1;
                        else hi = mid;
                    }
                    if (lo === tails.length) tails.push(value);
                    else tails[lo] = value;
                }
                return tails.length;
            }
        '''),
        "go": dedent_code('''
            package main

            func LongestIncreasingRun(values []int) int {
                tails := make([]int, 0, len(values))
                for _, value := range values {
                    lo, hi := 0, len(tails)
                    for lo < hi {
                        mid := (lo + hi) / 2
                        if tails[mid] < value {
                            lo = mid + 1
                        } else {
                            hi = mid
                        }
                    }
                    if lo == len(tails) {
                        tails = append(tails, value)
                    } else {
                        tails[lo] = value
                    }
                }
                return len(tails)
            }
        '''),
        "rust": dedent_code('''
            fn longest_increasing_run(values: &[i64]) -> i64 {
                let mut tails: Vec<i64> = Vec::new();
                for &value in values {
                    let mut lo = 0usize;
                    let mut hi = tails.len();
                    while lo < hi {
                        let mid = (lo + hi) / 2;
                        if tails[mid] < value {
                            lo = mid + 1;
                        } else {
                            hi = mid;
                        }
                    }
                    if lo == tails.len() {
                        tails.push(value);
                    } else {
                        tails[lo] = value;
                    }
                }
                tails.len() as i64
            }
        '''),
    },
)


TRAPPED_WATER = Family(
    name="trapped_water",
    skill="two_pointers",
    difficulty="hard",
    io={"args": ["list<int>"], "returns": "int"},
    spec="""
Given a skyline of bar heights, each one unit wide, return how many units of
water are trapped between the bars after rain.

Rules:
- Water above a bar is limited by the tallest bar to its left and the tallest to
  its right: it holds min(tallest_left, tallest_right) - own_height, when that
  is positive.
- Water runs off the ends, so nothing is trapped outside the outermost bars.
- Return 0 when fewer than 3 bars are given.
- Scanning left and right for every bar is the quadratic answer; a single pass
  from both ends is enough.
"""
    + BUDGET_NOTE,
    signatures={
        "python": "def trapped_water(heights: list[int]) -> int:",
        "typescript": "function trappedWater(heights: number[]): number {",
        "go": "func TrappedWater(heights []int) int {",
        "rust": "fn trapped_water(heights: &[i64]) -> i64 {",
    },
    inputs=[
        [0, 1, 0, 2, 1, 0, 1, 3, 2, 1, 2, 1],
        [4, 2, 0, 3, 2, 5],
        [1, 2, 3],
        [3, 2, 1],
        [],
        [5, 5],
        [2, 0, 2],
        [0, 0, 0, 0],
    ],
    reference=trapped_water,
    extras={"workload": WATER_WORKLOAD},
    lang_extras={
        "python": {"time_budget_ms": 80},
        "typescript": {"time_budget_ms": 30},
        "go": {"time_budget_ms": 25},
        "rust": {"time_budget_ms": 25},
    },
    solutions={
        "python": dedent_code('''
            def trapped_water(heights: list[int]) -> int:
                if len(heights) < 3:
                    return 0
                left, right = 0, len(heights) - 1
                left_max, right_max = heights[left], heights[right]
                total = 0
                while left < right:
                    if left_max <= right_max:
                        left += 1
                        if heights[left] > left_max:
                            left_max = heights[left]
                        else:
                            total += left_max - heights[left]
                    else:
                        right -= 1
                        if heights[right] > right_max:
                            right_max = heights[right]
                        else:
                            total += right_max - heights[right]
                return total
        '''),
        "typescript": dedent_code('''
            export function trappedWater(heights: number[]): number {
                if (heights.length < 3) return 0;
                let left = 0, right = heights.length - 1;
                let leftMax = heights[left], rightMax = heights[right];
                let total = 0;
                while (left < right) {
                    if (leftMax <= rightMax) {
                        left++;
                        if (heights[left] > leftMax) leftMax = heights[left];
                        else total += leftMax - heights[left];
                    } else {
                        right--;
                        if (heights[right] > rightMax) rightMax = heights[right];
                        else total += rightMax - heights[right];
                    }
                }
                return total;
            }
        '''),
        "go": dedent_code('''
            package main

            func TrappedWater(heights []int) int {
                if len(heights) < 3 {
                    return 0
                }
                left, right := 0, len(heights)-1
                leftMax, rightMax := heights[left], heights[right]
                total := 0
                for left < right {
                    if leftMax <= rightMax {
                        left++
                        if heights[left] > leftMax {
                            leftMax = heights[left]
                        } else {
                            total += leftMax - heights[left]
                        }
                    } else {
                        right--
                        if heights[right] > rightMax {
                            rightMax = heights[right]
                        } else {
                            total += rightMax - heights[right]
                        }
                    }
                }
                return total
            }
        '''),
        "rust": dedent_code('''
            fn trapped_water(heights: &[i64]) -> i64 {
                if heights.len() < 3 {
                    return 0;
                }
                let mut left = 0usize;
                let mut right = heights.len() - 1;
                let mut left_max = heights[left];
                let mut right_max = heights[right];
                let mut total: i64 = 0;
                while left < right {
                    if left_max <= right_max {
                        left += 1;
                        if heights[left] > left_max {
                            left_max = heights[left];
                        } else {
                            total += left_max - heights[left];
                        }
                    } else {
                        right -= 1;
                        if heights[right] > right_max {
                            right_max = heights[right];
                        } else {
                            total += right_max - heights[right];
                        }
                    }
                }
                total
            }
        '''),
    },
)


DISTINCT_WINDOW_TOTAL = Family(
    name="distinct_window_total",
    skill="hashing",
    difficulty="hard",
    io={"args": ["list<int>", "int"], "returns": "int"},
    spec="""
Slide a window of exactly k samples across the series and add up how many
*distinct* values each window position holds — the cardinality curve you would
plot for a rolling "unique clients per interval" panel.

Rules:
- Windows are contiguous and of exactly length k, so a series of length n has
  n - k + 1 of them.
- Each window contributes its number of distinct values, not its length.
- Return -1 if k <= 0 or if the series is shorter than k.
- Counting each window from scratch is O(n*k) and too slow; maintain the counts
  incrementally as the window moves.
"""
    + BUDGET_NOTE,
    signatures={
        "python": "def distinct_window_total(values: list[int], k: int) -> int:",
        "typescript": "function distinctWindowTotal(values: number[], k: number): number {",
        "go": "func DistinctWindowTotal(values []int, k int) int {",
        "rust": "fn distinct_window_total(values: &[i64], k: i64) -> i64 {",
    },
    inputs=[
        [[1, 2, 1, 3], 2],
        [[1, 1, 1, 1], 2],
        [[1, 2, 3, 4], 4],
        [[], 1],
        [[5, 6], 0],
        [[1, 2], 5],
        [[4, 4, 5, 5, 6], 3],
        [[9, 9, 9], 1],
    ],
    reference=distinct_window_total,
    extras={"workload": DISTINCT_WINDOW_WORKLOAD},
    lang_extras={
        "python": {"time_budget_ms": 250},
        "typescript": {"time_budget_ms": 90},
        "go": {"time_budget_ms": 50},
        "rust": {"time_budget_ms": 35},
    },
    solutions={
        "python": dedent_code('''
            def distinct_window_total(values: list[int], k: int) -> int:
                if k <= 0 or len(values) < k:
                    return -1
                counts = {}
                distinct = 0
                total = 0
                for i, value in enumerate(values):
                    if counts.get(value, 0) == 0:
                        distinct += 1
                    counts[value] = counts.get(value, 0) + 1
                    if i >= k:
                        leaving = values[i - k]
                        counts[leaving] -= 1
                        if counts[leaving] == 0:
                            distinct -= 1
                    if i >= k - 1:
                        total += distinct
                return total
        '''),
        "typescript": dedent_code('''
            export function distinctWindowTotal(values: number[], k: number): number {
                if (k <= 0 || values.length < k) return -1;
                const counts = new Map<number, number>();
                let distinct = 0;
                let total = 0;
                for (let i = 0; i < values.length; i++) {
                    const current = counts.get(values[i]) ?? 0;
                    if (current === 0) distinct++;
                    counts.set(values[i], current + 1);
                    if (i >= k) {
                        const leaving = values[i - k];
                        const left = (counts.get(leaving) ?? 0) - 1;
                        counts.set(leaving, left);
                        if (left === 0) distinct--;
                    }
                    if (i >= k - 1) total += distinct;
                }
                return total;
            }
        '''),
        "go": dedent_code('''
            package main

            func DistinctWindowTotal(values []int, k int) int {
                if k <= 0 || len(values) < k {
                    return -1
                }
                counts := make(map[int]int)
                distinct := 0
                total := 0
                for i, value := range values {
                    if counts[value] == 0 {
                        distinct++
                    }
                    counts[value]++
                    if i >= k {
                        leaving := values[i-k]
                        counts[leaving]--
                        if counts[leaving] == 0 {
                            distinct--
                        }
                    }
                    if i >= k-1 {
                        total += distinct
                    }
                }
                return total
            }
        '''),
        "rust": dedent_code('''
            use std::collections::HashMap;

            fn distinct_window_total(values: &[i64], k: i64) -> i64 {
                if k <= 0 || (values.len() as i64) < k {
                    return -1;
                }
                let k = k as usize;
                let mut counts: HashMap<i64, i64> = HashMap::new();
                let mut distinct: i64 = 0;
                let mut total: i64 = 0;
                for i in 0..values.len() {
                    let entry = counts.entry(values[i]).or_insert(0);
                    if *entry == 0 {
                        distinct += 1;
                    }
                    *entry += 1;
                    if i >= k {
                        let leaving = counts.entry(values[i - k]).or_insert(0);
                        *leaving -= 1;
                        if *leaving == 0 {
                            distinct -= 1;
                        }
                    }
                    if i + 1 >= k {
                        total += distinct;
                    }
                }
                total
            }
        '''),
    },
)


MIN_ROOMS = Family(
    name="min_rooms",
    skill="sweep_line",
    difficulty="hard",
    io={"args": ["list<int>", "list<int>"], "returns": "int"},
    spec="""
Meeting i starts at starts[i] and runs for durations[i], occupying the
half-open interval [start, start + duration). Return the smallest number of
rooms needed to hold every meeting, which is the largest number that overlap at
any instant.

Rules:
- `starts` and `durations` are parallel arrays of the same length.
- Intervals are half-open: a meeting ending exactly when another starts does not
  need a second room.
- A zero-length meeting overlaps nothing.
- Return 0 when there are no meetings.
- Comparing every pair of meetings is the quadratic answer; sorting the
  boundaries and sweeping them is not.
"""
    + BUDGET_NOTE,
    signatures={
        "python": "def min_rooms(starts: list[int], durations: list[int]) -> int:",
        "typescript": "function minRooms(starts: number[], durations: number[]): number {",
        "go": "func MinRooms(starts []int, durations []int) int {",
        "rust": "fn min_rooms(starts: &[i64], durations: &[i64]) -> i64 {",
    },
    inputs=[
        [[0, 5, 15], [10, 15, 10]],
        [[0, 10, 20], [10, 10, 10]],
        [[], []],
        [[5], [0]],
        [[1, 1, 1], [5, 5, 5]],
        [[0, 1, 2, 3], [1, 1, 1, 1]],
        [[0, 2, 4], [5, 5, 5]],
        [[7, 3, 1], [2, 2, 2]],
    ],
    reference=min_rooms,
    extras={"workload": ROOMS_WORKLOAD},
    lang_extras={
        "python": {"time_budget_ms": 480},
        "typescript": {"time_budget_ms": 550},
        "go": {"time_budget_ms": 130},
        "rust": {"time_budget_ms": 60},
    },
    solutions={
        "python": dedent_code('''
            def min_rooms(starts: list[int], durations: list[int]) -> int:
                n = min(len(starts), len(durations))
                if n == 0:
                    return 0
                begins = sorted(starts[:n])
                ends = sorted(starts[i] + durations[i] for i in range(n))
                best = 0
                active = 0
                j = 0
                for i in range(n):
                    while j < n and ends[j] <= begins[i]:
                        active -= 1
                        j += 1
                    active += 1
                    if active > best:
                        best = active
                return best
        '''),
        "typescript": dedent_code('''
            export function minRooms(starts: number[], durations: number[]): number {
                const n = Math.min(starts.length, durations.length);
                if (n === 0) return 0;
                const begins = starts.slice(0, n).sort((a, b) => a - b);
                const ends: number[] = new Array(n);
                for (let i = 0; i < n; i++) ends[i] = starts[i] + durations[i];
                ends.sort((a, b) => a - b);
                let best = 0, active = 0, j = 0;
                for (let i = 0; i < n; i++) {
                    while (j < n && ends[j] <= begins[i]) {
                        active--;
                        j++;
                    }
                    active++;
                    if (active > best) best = active;
                }
                return best;
            }
        '''),
        "go": dedent_code('''
            package main

            import "sort"

            func MinRooms(starts []int, durations []int) int {
                n := len(starts)
                if len(durations) < n {
                    n = len(durations)
                }
                if n == 0 {
                    return 0
                }
                begins := make([]int, n)
                ends := make([]int, n)
                for i := 0; i < n; i++ {
                    begins[i] = starts[i]
                    ends[i] = starts[i] + durations[i]
                }
                sort.Ints(begins)
                sort.Ints(ends)
                best, active, j := 0, 0, 0
                for i := 0; i < n; i++ {
                    for j < n && ends[j] <= begins[i] {
                        active--
                        j++
                    }
                    active++
                    if active > best {
                        best = active
                    }
                }
                return best
            }
        '''),
        "rust": dedent_code('''
            fn min_rooms(starts: &[i64], durations: &[i64]) -> i64 {
                let n = starts.len().min(durations.len());
                if n == 0 {
                    return 0;
                }
                let mut begins: Vec<i64> = starts[..n].to_vec();
                let mut ends: Vec<i64> = (0..n).map(|i| starts[i] + durations[i]).collect();
                begins.sort_unstable();
                ends.sort_unstable();
                let mut best: i64 = 0;
                let mut active: i64 = 0;
                let mut j = 0usize;
                for i in 0..n {
                    while j < n && ends[j] <= begins[i] {
                        active -= 1;
                        j += 1;
                    }
                    active += 1;
                    if active > best {
                        best = active;
                    }
                }
                best
            }
        '''),
    },
)


RUNNING_MEDIAN_SUM = Family(
    name="running_median_sum",
    skill="heaps",
    difficulty="hard",
    io={"args": ["list<int>"], "returns": "int"},
    spec="""
Stream the series one value at a time. After each value, take the median of
everything seen so far and add it to a running total; return that total.

Rules:
- With an odd count the median is the middle value of the sorted prefix.
- With an even count, take the *lower* of the two middle values, so the answer
  stays an integer and is fully determined.
- Return 0 for an empty series.
- Re-sorting the prefix after every value is the slow answer; keeping the two
  halves in heaps is not.
"""
    + BUDGET_NOTE,
    signatures={
        "python": "def running_median_sum(values: list[int]) -> int:",
        "typescript": "function runningMedianSum(values: number[]): number {",
        "go": "func RunningMedianSum(values []int) int {",
        "rust": "fn running_median_sum(values: &[i64]) -> i64 {",
    },
    inputs=[
        [1, 2, 3],
        [3, 2, 1],
        [],
        [5],
        [1, 1, 1, 1],
        [10, 20, 30, 40],
        [4, 1, 7, 2, 9],
        [2, 2, 3, 3],
    ],
    reference=running_median_sum,
    extras={"workload": MEDIAN_WORKLOAD},
    lang_extras={
        "python": {"time_budget_ms": 400},
        "typescript": {"time_budget_ms": 280},
        "go": {"time_budget_ms": 120},
        "rust": {"time_budget_ms": 50},
    },
    solutions={
        "python": dedent_code('''
            import heapq


            def running_median_sum(values: list[int]) -> int:
                low = []
                high = []
                total = 0
                for value in values:
                    if low and value > -low[0]:
                        heapq.heappush(high, value)
                    else:
                        heapq.heappush(low, -value)
                    if len(low) > len(high) + 1:
                        heapq.heappush(high, -heapq.heappop(low))
                    elif len(high) > len(low):
                        heapq.heappush(low, -heapq.heappop(high))
                    total += -low[0]
                return total
        '''),
        "typescript": dedent_code('''
            class Heap {
                private data: number[] = [];
                constructor(private less: (a: number, b: number) => boolean) {}
                get size(): number { return this.data.length; }
                peek(): number { return this.data[0]; }
                push(value: number): void {
                    const d = this.data;
                    d.push(value);
                    let i = d.length - 1;
                    while (i > 0) {
                        const p = (i - 1) >> 1;
                        if (!this.less(d[i], d[p])) break;
                        [d[i], d[p]] = [d[p], d[i]];
                        i = p;
                    }
                }
                pop(): number {
                    const d = this.data;
                    const top = d[0];
                    const last = d.pop() as number;
                    if (d.length > 0) {
                        d[0] = last;
                        let i = 0;
                        for (;;) {
                            const l = 2 * i + 1, r = 2 * i + 2;
                            let best = i;
                            if (l < d.length && this.less(d[l], d[best])) best = l;
                            if (r < d.length && this.less(d[r], d[best])) best = r;
                            if (best === i) break;
                            [d[i], d[best]] = [d[best], d[i]];
                            i = best;
                        }
                    }
                    return top;
                }
            }

            export function runningMedianSum(values: number[]): number {
                const low = new Heap((a, b) => a > b);
                const high = new Heap((a, b) => a < b);
                let total = 0;
                for (const value of values) {
                    if (low.size > 0 && value > low.peek()) high.push(value);
                    else low.push(value);
                    if (low.size > high.size + 1) high.push(low.pop());
                    else if (high.size > low.size) low.push(high.pop());
                    total += low.peek();
                }
                return total;
            }
        '''),
        "go": dedent_code('''
            package main

            func heapPush(h []int, v int, less func(a, b int) bool) []int {
                h = append(h, v)
                i := len(h) - 1
                for i > 0 {
                    p := (i - 1) / 2
                    if !less(h[i], h[p]) {
                        break
                    }
                    h[i], h[p] = h[p], h[i]
                    i = p
                }
                return h
            }

            func heapPop(h []int, less func(a, b int) bool) (int, []int) {
                top := h[0]
                last := len(h) - 1
                h[0] = h[last]
                h = h[:last]
                i := 0
                for {
                    l, r := 2*i+1, 2*i+2
                    best := i
                    if l < len(h) && less(h[l], h[best]) {
                        best = l
                    }
                    if r < len(h) && less(h[r], h[best]) {
                        best = r
                    }
                    if best == i {
                        break
                    }
                    h[i], h[best] = h[best], h[i]
                    i = best
                }
                return top, h
            }

            func RunningMedianSum(values []int) int {
                maxHeap := func(a, b int) bool { return a > b }
                minHeap := func(a, b int) bool { return a < b }
                low := make([]int, 0, len(values))
                high := make([]int, 0, len(values))
                total := 0
                for _, value := range values {
                    if len(low) > 0 && value > low[0] {
                        high = heapPush(high, value, minHeap)
                    } else {
                        low = heapPush(low, value, maxHeap)
                    }
                    if len(low) > len(high)+1 {
                        var moved int
                        moved, low = heapPop(low, maxHeap)
                        high = heapPush(high, moved, minHeap)
                    } else if len(high) > len(low) {
                        var moved int
                        moved, high = heapPop(high, minHeap)
                        low = heapPush(low, moved, maxHeap)
                    }
                    total += low[0]
                }
                return total
            }
        '''),
        "rust": dedent_code('''
            use std::cmp::Reverse;
            use std::collections::BinaryHeap;

            fn running_median_sum(values: &[i64]) -> i64 {
                let mut low: BinaryHeap<i64> = BinaryHeap::new();
                let mut high: BinaryHeap<Reverse<i64>> = BinaryHeap::new();
                let mut total: i64 = 0;
                for &value in values {
                    match low.peek() {
                        Some(&top) if value > top => high.push(Reverse(value)),
                        _ => low.push(value),
                    }
                    if low.len() > high.len() + 1 {
                        let moved = low.pop().unwrap();
                        high.push(Reverse(moved));
                    } else if high.len() > low.len() {
                        let Reverse(moved) = high.pop().unwrap();
                        low.push(moved);
                    }
                    total += *low.peek().unwrap();
                }
                total
            }
        '''),
    },
)


MAX_XOR_PAIR = Family(
    name="max_xor_pair",
    skill="bit_manipulation",
    difficulty="hard",
    io={"args": ["list<int>"], "returns": "int"},
    spec="""
Return the largest value of `values[i] XOR values[j]` over all index pairs with
i < j, using bitwise exclusive-or.

Rules:
- All values are non-negative.
- Return 0 when fewer than 2 values are given, and 0 when every value is equal
  (a value XOR itself is 0).
- Trying every pair is quadratic and too slow; decide the answer one bit at a
  time, from the highest bit down, checking whether that bit is achievable.
"""
    + BUDGET_NOTE,
    signatures={
        "python": "def max_xor_pair(values: list[int]) -> int:",
        "typescript": "function maxXorPair(values: number[]): number {",
        "go": "func MaxXorPair(values []int) int {",
        "rust": "fn max_xor_pair(values: &[i64]) -> i64 {",
    },
    inputs=[
        [3, 10, 5, 25, 2, 8],
        [0, 0, 0],
        [],
        [7],
        [1, 2],
        [8, 1, 2, 12, 7, 6],
        [5, 5, 5, 5],
        [1, 3, 7, 15],
    ],
    reference=max_xor_pair,
    extras={"workload": XOR_WORKLOAD},
    lang_extras={
        "python": {"time_budget_ms": 1100},
        "typescript": {"time_budget_ms": 700},
        "go": {"time_budget_ms": 250},
        "rust": {"time_budget_ms": 200},
    },
    solutions={
        "python": dedent_code('''
            def max_xor_pair(values: list[int]) -> int:
                if len(values) < 2:
                    return 0
                top = max(values)
                if top <= 0:
                    return 0
                high = 0
                while (1 << (high + 1)) <= top:
                    high += 1
                best = 0
                mask = 0
                for bit in range(high, -1, -1):
                    mask |= 1 << bit
                    prefixes = {value & mask for value in values}
                    candidate = best | (1 << bit)
                    for prefix in prefixes:
                        if (candidate ^ prefix) in prefixes:
                            best = candidate
                            break
                return best
        '''),
        "typescript": dedent_code('''
            export function maxXorPair(values: number[]): number {
                if (values.length < 2) return 0;
                let top = 0;
                for (const value of values) if (value > top) top = value;
                if (top <= 0) return 0;
                let high = 0;
                while (Math.pow(2, high + 1) <= top) high++;
                let best = 0;
                let mask = 0;
                for (let bit = high; bit >= 0; bit--) {
                    mask |= 1 << bit;
                    const prefixes = new Set<number>();
                    for (const value of values) prefixes.add(value & mask);
                    const candidate = best | (1 << bit);
                    for (const prefix of prefixes) {
                        if (prefixes.has(candidate ^ prefix)) {
                            best = candidate;
                            break;
                        }
                    }
                }
                return best;
            }
        '''),
        "go": dedent_code('''
            package main

            func MaxXorPair(values []int) int {
                if len(values) < 2 {
                    return 0
                }
                top := 0
                for _, value := range values {
                    if value > top {
                        top = value
                    }
                }
                if top <= 0 {
                    return 0
                }
                high := 0
                for (1 << (high + 1)) <= top {
                    high++
                }
                best := 0
                mask := 0
                for bit := high; bit >= 0; bit-- {
                    mask |= 1 << bit
                    prefixes := make(map[int]struct{}, len(values))
                    for _, value := range values {
                        prefixes[value&mask] = struct{}{}
                    }
                    candidate := best | (1 << bit)
                    for prefix := range prefixes {
                        if _, ok := prefixes[candidate^prefix]; ok {
                            best = candidate
                            break
                        }
                    }
                }
                return best
            }
        '''),
        "rust": dedent_code('''
            use std::collections::HashSet;

            fn max_xor_pair(values: &[i64]) -> i64 {
                if values.len() < 2 {
                    return 0;
                }
                let top = *values.iter().max().unwrap();
                if top <= 0 {
                    return 0;
                }
                let mut high = 0i64;
                while (1i64 << (high + 1)) <= top {
                    high += 1;
                }
                let mut best = 0i64;
                let mut mask = 0i64;
                for bit in (0..=high).rev() {
                    mask |= 1i64 << bit;
                    let prefixes: HashSet<i64> = values.iter().map(|&v| v & mask).collect();
                    let candidate = best | (1i64 << bit);
                    if prefixes.iter().any(|&p| prefixes.contains(&(candidate ^ p))) {
                        best = candidate;
                    }
                }
                best
            }
        '''),
    },
)


ADVANCED_FAMILIES = [
    COUNT_INVERSIONS,
    LONGEST_UNIQUE_RUN,
    LARGEST_RECTANGLE,
    WINDOW_MAX_TOTAL,
    LONGEST_INCREASING_RUN,
    TRAPPED_WATER,
    DISTINCT_WINDOW_TOTAL,
    MIN_ROOMS,
    RUNNING_MEDIAN_SUM,
    MAX_XOR_PAIR,
]
