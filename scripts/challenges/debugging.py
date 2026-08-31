"""code_debugging: a plausible implementation that is subtly wrong.

The model gets the broken code and the symptom a colleague reported, and has to
return a corrected implementation. Scoring is the same execution as
code_generation — the hidden tests include the inputs that trip the seeded bug
as well as the ones the buggy version already handles, so "rewrite it from
scratch" and "find the two-line fix" both score, and a cosmetic edit does not.
"""

from __future__ import annotations

from .common import Family, dedent_code
from .debugging_advanced import ADVANCED_FAMILIES


def median_of(values: list[int]) -> float:
    if not values:
        return -1.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def merge_sorted(a: list[int], b: list[int]) -> list[int]:
    out: list[int] = []
    i = j = 0
    while i < len(a) and j < len(b):
        if a[i] <= b[j]:
            out.append(a[i])
            i += 1
        else:
            out.append(b[j])
            j += 1
    out.extend(a[i:])
    out.extend(b[j:])
    return out


def normalize_path(path: str) -> str:
    stack: list[str] = []
    for part in path.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if stack:
                stack.pop()
            continue
        stack.append(part)
    return "/" + "/".join(stack)


MEDIAN = Family(
    name="median_of",
    skill="statistics",
    difficulty="easy",
    io={"args": ["list<int>"], "returns": "float"},
    spec="""
`median_of` should return the median of a sample of latencies:

- Sort the values first; the caller passes them in arrival order.
- For an odd count, the median is the middle value.
- For an even count, it is the mean of the two middle values (so [1, 2, 3, 4]
  has median 2.5, a value that is not in the sample).
- An empty sample has no median: return -1.0.
""",
    signatures={
        "python": "def median_of(values: list[int]) -> float:",
        "typescript": "function medianOf(values: number[]): number {",
        "go": "func MedianOf(values []int) float64 {",
        "rust": "fn median_of(values: &[i64]) -> f64 {",
    },
    inputs=[
        [1, 2, 3],
        [1, 2, 3, 4],
        [4, 1, 3, 2],
        [],
        [7],
        [5, 5, 5, 5],
        [10, 2],
        [9, 1, 8, 2, 7],
        [100, 1, 50, 2],
    ],
    reference=median_of,
    extras={
        "symptom": (
            "The p50 panel disagrees with the p50 our metrics backend reports. "
            "It is always a value that appears in the sample, even when the "
            "sample has an even number of points, and the number changes when "
            "the same points arrive in a different order."
        )
    },
    lang_extras={
        "python": {"buggy_code": dedent_code('''
            def median_of(values: list[int]) -> float:
                if not values:
                    return -1.0
                middle = len(values) // 2
                return float(values[middle])
        ''')},
        "typescript": {"buggy_code": dedent_code('''
            function medianOf(values: number[]): number {
                if (values.length === 0) {
                    return -1.0;
                }
                const middle = Math.floor(values.length / 2);
                return values[middle];
            }
        ''')},
        "go": {"buggy_code": dedent_code('''
            func MedianOf(values []int) float64 {
                if len(values) == 0 {
                    return -1.0
                }
                middle := len(values) / 2
                return float64(values[middle])
            }
        ''')},
        "rust": {"buggy_code": dedent_code('''
            fn median_of(values: &[i64]) -> f64 {
                if values.is_empty() {
                    return -1.0;
                }
                let middle = values.len() / 2;
                values[middle] as f64
            }
        ''')},
    },
    solutions={
        "python": dedent_code('''
            def median_of(values: list[int]) -> float:
                if not values:
                    return -1.0
                ordered = sorted(values)
                mid = len(ordered) // 2
                if len(ordered) % 2 == 1:
                    return float(ordered[mid])
                return (ordered[mid - 1] + ordered[mid]) / 2.0
        '''),
        "typescript": dedent_code('''
            export function medianOf(values: number[]): number {
                if (values.length === 0) return -1.0;
                const ordered = [...values].sort((a, b) => a - b);
                const mid = Math.floor(ordered.length / 2);
                if (ordered.length % 2 === 1) return ordered[mid];
                return (ordered[mid - 1] + ordered[mid]) / 2;
            }
        '''),
        "go": dedent_code('''
            package main

            import "sort"

            func MedianOf(values []int) float64 {
                if len(values) == 0 {
                    return -1.0
                }
                ordered := append([]int(nil), values...)
                sort.Ints(ordered)
                mid := len(ordered) / 2
                if len(ordered)%2 == 1 {
                    return float64(ordered[mid])
                }
                return float64(ordered[mid-1]+ordered[mid]) / 2.0
            }
        '''),
        "rust": dedent_code('''
            fn median_of(values: &[i64]) -> f64 {
                if values.is_empty() {
                    return -1.0;
                }
                let mut ordered = values.to_vec();
                ordered.sort();
                let mid = ordered.len() / 2;
                if ordered.len() % 2 == 1 {
                    ordered[mid] as f64
                } else {
                    (ordered[mid - 1] + ordered[mid]) as f64 / 2.0
                }
            }
        '''),
    },
)


MERGE_SORTED = Family(
    name="merge_sorted",
    skill="merging",
    difficulty="easy",
    io={"args": ["list<int>", "list<int>"], "returns": "list<int>"},
    spec="""
`merge_sorted` merges two already-sorted ascending lists into one sorted list.

- Every element of both inputs appears in the output; duplicates are kept.
- The output length is always len(a) + len(b).
- Either input may be empty.
- The inputs must not be modified.
""",
    signatures={
        "python": "def merge_sorted(a: list[int], b: list[int]) -> list[int]:",
        "typescript": "function mergeSorted(a: number[], b: number[]): number[] {",
        "go": "func MergeSorted(a []int, b []int) []int {",
        "rust": "fn merge_sorted(a: &[i64], b: &[i64]) -> Vec<i64> {",
    },
    inputs=[
        [[1, 3, 5], [2, 4, 6]],
        [[1, 2], [3, 4, 5, 6]],
        [[1, 2, 3], []],
        [[], [1, 2, 3]],
        [[], []],
        [[5, 5], [5, 5]],
        [[1], [2]],
        [[9], [1, 2, 3, 4]],
        [[1, 4, 7], [2, 3]],
    ],
    reference=merge_sorted,
    extras={
        "symptom": (
            "Merged batches are short: the reader reports fewer records than "
            "the two input batches contain together, and the highest-keyed "
            "records are the ones missing. It only happens for some batch pairs."
        )
    },
    lang_extras={
        "python": {"buggy_code": dedent_code('''
            def merge_sorted(a: list[int], b: list[int]) -> list[int]:
                out: list[int] = []
                i = 0
                j = 0
                while i < len(a) and j < len(b):
                    if a[i] <= b[j]:
                        out.append(a[i])
                        i += 1
                    else:
                        out.append(b[j])
                        j += 1
                while i < len(a):
                    out.append(a[i])
                    i += 1
                return out
        ''')},
        "typescript": {"buggy_code": dedent_code('''
            function mergeSorted(a: number[], b: number[]): number[] {
                const out: number[] = [];
                let i = 0;
                let j = 0;
                while (i < a.length && j < b.length) {
                    if (a[i] <= b[j]) {
                        out.push(a[i]);
                        i++;
                    } else {
                        out.push(b[j]);
                        j++;
                    }
                }
                while (i < a.length) {
                    out.push(a[i]);
                    i++;
                }
                return out;
            }
        ''')},
        "go": {"buggy_code": dedent_code('''
            func MergeSorted(a []int, b []int) []int {
                out := []int{}
                i, j := 0, 0
                for i < len(a) && j < len(b) {
                    if a[i] <= b[j] {
                        out = append(out, a[i])
                        i++
                    } else {
                        out = append(out, b[j])
                        j++
                    }
                }
                for i < len(a) {
                    out = append(out, a[i])
                    i++
                }
                return out
            }
        ''')},
        "rust": {"buggy_code": dedent_code('''
            fn merge_sorted(a: &[i64], b: &[i64]) -> Vec<i64> {
                let mut out = Vec::new();
                let mut i = 0;
                let mut j = 0;
                while i < a.len() && j < b.len() {
                    if a[i] <= b[j] {
                        out.push(a[i]);
                        i += 1;
                    } else {
                        out.push(b[j]);
                        j += 1;
                    }
                }
                while i < a.len() {
                    out.push(a[i]);
                    i += 1;
                }
                out
            }
        ''')},
    },
    solutions={
        "python": dedent_code('''
            def merge_sorted(a: list[int], b: list[int]) -> list[int]:
                out: list[int] = []
                i = j = 0
                while i < len(a) and j < len(b):
                    if a[i] <= b[j]:
                        out.append(a[i])
                        i += 1
                    else:
                        out.append(b[j])
                        j += 1
                out.extend(a[i:])
                out.extend(b[j:])
                return out
        '''),
        "typescript": dedent_code('''
            export function mergeSorted(a: number[], b: number[]): number[] {
                const out: number[] = [];
                let i = 0;
                let j = 0;
                while (i < a.length && j < b.length) {
                    if (a[i] <= b[j]) out.push(a[i++]);
                    else out.push(b[j++]);
                }
                while (i < a.length) out.push(a[i++]);
                while (j < b.length) out.push(b[j++]);
                return out;
            }
        '''),
        "go": dedent_code('''
            package main

            func MergeSorted(a []int, b []int) []int {
                out := make([]int, 0, len(a)+len(b))
                i, j := 0, 0
                for i < len(a) && j < len(b) {
                    if a[i] <= b[j] {
                        out = append(out, a[i])
                        i++
                    } else {
                        out = append(out, b[j])
                        j++
                    }
                }
                out = append(out, a[i:]...)
                out = append(out, b[j:]...)
                return out
            }
        '''),
        "rust": dedent_code('''
            fn merge_sorted(a: &[i64], b: &[i64]) -> Vec<i64> {
                let mut out = Vec::with_capacity(a.len() + b.len());
                let (mut i, mut j) = (0, 0);
                while i < a.len() && j < b.len() {
                    if a[i] <= b[j] {
                        out.push(a[i]);
                        i += 1;
                    } else {
                        out.push(b[j]);
                        j += 1;
                    }
                }
                out.extend_from_slice(&a[i..]);
                out.extend_from_slice(&b[j..]);
                out
            }
        '''),
    },
)


NORMALIZE_PATH = Family(
    name="normalize_path",
    skill="string_state",
    difficulty="medium",
    io={"args": ["str"], "returns": "str"},
    spec="""
`normalize_path` canonicalizes an absolute filesystem path.

- Collapse repeated slashes: "//a//b" becomes "/a/b".
- Drop "." segments.
- ".." removes the previous segment, and at the root it is a no-op: "/../.."
  is "/", never an error and never a path above the root.
- The result starts with "/" and has no trailing slash, except the root itself
  which is exactly "/".
""",
    signatures={
        "python": "def normalize_path(path: str) -> str:",
        "typescript": "function normalizePath(path: string): string {",
        "go": "func NormalizePath(path string) string {",
        "rust": "fn normalize_path(path: &str) -> String {",
    },
    inputs=[
        "/a/b/../c",
        "/../..",
        "/a/./b/",
        "//a//b",
        "/",
        "/a/b/c/../../d",
        "/.",
        "/a/..",
        "/a/b/../../../c",
        "/etc//conf.d/./nginx/../nginx.conf",
    ],
    reference=normalize_path,

    lang_extras={
        "python": {
            "buggy_code": dedent_code('''
            def normalize_path(path: str) -> str:
                stack: list[str] = []
                for part in path.split("/"):
                    if part == "..":
                        stack.pop()
                    elif part != "." and part != "":
                        stack.append(part)
                return "/" + "/".join(stack)
        '''''),
            "symptom": (
                "The config loader crashes on some requests instead of "
                "returning a path. The stack trace points at this function, and "
                "the paths that trigger it all contain more '..' segments than "
                "directories."
            ),
        },
        "typescript": {
            "buggy_code": dedent_code('''
                function normalizePath(path: string): string {
                    const stack: string[] = [];
                    for (const part of path.split("/")) {
                        if (part === "..") {
                            stack.pop();
                        } else if (part !== "." && part !== "") {
                            stack.push(part);
                        }
                    }
                    return "/" + stack.join("/") + (path.endsWith("/") ? "/" : "");
                }
            '''),
            "symptom": (
                "The cache holds two entries for the same file whenever the "
                "caller passed a path with a trailing slash, and the root path "
                "comes back looking wrong entirely."
            ),
        },
        "go": {
            "buggy_code": dedent_code('''
            func NormalizePath(path string) string {
                stack := []string{}
                for _, part := range strings.Split(path, "/") {
                    if part == ".." {
                        stack = stack[:len(stack)-1]
                    } else if part != "." && part != "" {
                        stack = append(stack, part)
                    }
                }
                return "/" + strings.Join(stack, "/")
            }
        '''''),
            "symptom": (
                "The config loader crashes on some requests instead of "
                "returning a path. The stack trace points at this function, and "
                "the paths that trigger it all contain more '..' segments than "
                "directories."
            ),
        },
        "rust": {
            "buggy_code": dedent_code('''
            fn normalize_path(path: &str) -> String {
                let mut stack: Vec<&str> = Vec::new();
                for part in path.split('/') {
                    if part == ".." {
                        stack.pop().unwrap();
                    } else if part != "." && !part.is_empty() {
                        stack.push(part);
                    }
                }
                format!("/{}", stack.join("/"))
            }
        '''''),
            "symptom": (
                "The config loader crashes on some requests instead of "
                "returning a path. The stack trace points at this function, and "
                "the paths that trigger it all contain more '..' segments than "
                "directories."
            ),
        },
    },
    solutions={
        "python": dedent_code('''
            def normalize_path(path: str) -> str:
                stack: list[str] = []
                for part in path.split("/"):
                    if part in ("", "."):
                        continue
                    if part == "..":
                        if stack:
                            stack.pop()
                        continue
                    stack.append(part)
                return "/" + "/".join(stack)
        '''),
        "typescript": dedent_code('''
            export function normalizePath(path: string): string {
                const stack: string[] = [];
                for (const part of path.split("/")) {
                    if (part === "" || part === ".") continue;
                    if (part === "..") {
                        stack.pop();
                        continue;
                    }
                    stack.push(part);
                }
                return "/" + stack.join("/");
            }
        '''),
        "go": dedent_code('''
            package main

            import "strings"

            func NormalizePath(path string) string {
                stack := []string{}
                for _, part := range strings.Split(path, "/") {
                    if part == "" || part == "." {
                        continue
                    }
                    if part == ".." {
                        if len(stack) > 0 {
                            stack = stack[:len(stack)-1]
                        }
                        continue
                    }
                    stack = append(stack, part)
                }
                return "/" + strings.Join(stack, "/")
            }
        '''),
        "rust": dedent_code('''
            fn normalize_path(path: &str) -> String {
                let mut stack: Vec<&str> = Vec::new();
                for part in path.split('/') {
                    if part.is_empty() || part == "." {
                        continue;
                    }
                    if part == ".." {
                        stack.pop();
                        continue;
                    }
                    stack.push(part);
                }
                format!("/{}", stack.join("/"))
            }
        '''),
    },
)


FAMILIES = [MEDIAN, MERGE_SORTED, NORMALIZE_PATH, *ADVANCED_FAMILIES]
