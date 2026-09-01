"""Harder code_debugging families.

Same contract as ``debugging.py``: a plausible implementation, a colleague's
symptom report, and hidden tests that include both the inputs the bug breaks and
the ones it already handles.

What makes these harder is *where* the bug hides. Each one is correct on the
inputs a developer would try first and wrong only on a narrow class — an exact
window boundary, an odd-length input, a nested interval, a non-byte-aligned
prefix — so skimming the code and running the happy path both miss it. The
builder measures which tests each buggy version actually fails, so a case whose
bug stopped being observable fails the build rather than silently paying out.
"""

from __future__ import annotations

from .common import Family, dedent_code

# ---------------------------------------------------------------------------
# Reference implementations
# ---------------------------------------------------------------------------


def lower_bound(values: list[int], target: int) -> int:
    lo, hi = 0, len(values)
    while lo < hi:
        mid = (lo + hi) // 2
        if values[mid] < target:
            lo = mid + 1
        else:
            hi = mid
    return lo


def parse_duration(text: str) -> int:
    total = 0
    number = 0
    seen_digit = False
    for ch in text:
        if "0" <= ch <= "9":
            number = number * 10 + (ord(ch) - 48)
            seen_digit = True
        elif ch in ("h", "m", "s"):
            if not seen_digit:
                return -1
            scale = 3600 if ch == "h" else (60 if ch == "m" else 1)
            total += number * scale
            number = 0
            seen_digit = False
        else:
            return -1
    return -1 if seen_digit else total


def covered_seconds(starts: list[int], ends: list[int]) -> int:
    n = min(len(starts), len(ends))
    spans = sorted((starts[i], ends[i]) for i in range(n) if ends[i] > starts[i])
    total = 0
    have = False
    cur_start = 0
    cur_end = 0
    for start, end in spans:
        if not have:
            cur_start, cur_end = start, end
            have = True
        elif start <= cur_end:
            if end > cur_end:
                cur_end = end
        else:
            total += cur_end - cur_start
            cur_start, cur_end = start, end
    if have:
        total += cur_end - cur_start
    return total


def luhn_valid(digits: str) -> bool:
    if not digits:
        return False
    for ch in digits:
        if ch < "0" or ch > "9":
            return False
    total = 0
    double = False
    for ch in reversed(digits):
        value = ord(ch) - 48
        if double:
            value *= 2
            if value > 9:
                value -= 9
        total += value
        double = not double
    return total % 10 == 0


def _ipv4(text: str) -> int | None:
    parts = text.split(".")
    if len(parts) != 4:
        return None
    total = 0
    for part in parts:
        if not part or len(part) > 3:
            return None
        for ch in part:
            if ch < "0" or ch > "9":
                return None
        value = int(part)
        if value > 255:
            return None
        total = total * 256 + value
    return total


def ip_in_cidr(ip: str, cidr: str) -> bool:
    base, sep, prefix_text = cidr.partition("/")
    if not sep or not prefix_text:
        return False
    for ch in prefix_text:
        if ch < "0" or ch > "9":
            return False
    prefix = int(prefix_text)
    if prefix > 32:
        return False
    left = _ipv4(ip)
    right = _ipv4(base)
    if left is None or right is None:
        return False
    if prefix == 0:
        return True
    mask = (0xFFFFFFFF << (32 - prefix)) & 0xFFFFFFFF
    return (left & mask) == (right & mask)


def sliding_rate_limit(timestamps: list[int], window: int, limit: int) -> int:
    if window <= 0 or limit <= 0:
        return 0
    allowed: list[int] = []
    head = 0
    count = 0
    for stamp in timestamps:
        while head < len(allowed) and allowed[head] <= stamp - window:
            head += 1
        if len(allowed) - head < limit:
            allowed.append(stamp)
            count += 1
    return count


def counter_increase(values: list[int]) -> int:
    total = 0
    for i in range(1, len(values)):
        if values[i] >= values[i - 1]:
            total += values[i] - values[i - 1]
        else:
            total += values[i]
    return total


def version_bump(version: str, part: str) -> str:
    fields = version.split(".")
    if len(fields) != 3:
        return ""
    numbers = []
    for field in fields:
        if not field:
            return ""
        for ch in field:
            if ch < "0" or ch > "9":
                return ""
        numbers.append(int(field))
    major, minor, patch = numbers
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    if part == "patch":
        return f"{major}.{minor}.{patch + 1}"
    return ""


def csv_field(text: str) -> str:
    if any(ch in text for ch in (",", '"', "\n")):
        return '"' + text.replace('"', '""') + '"'
    return text


_SIZE_UNITS = {
    "": 1,
    "K": 1000,
    "Ki": 1024,
    "M": 1000000,
    "Mi": 1048576,
    "G": 1000000000,
    "Gi": 1073741824,
}


def parse_size(text: str) -> int:
    end = 0
    while end < len(text) and "0" <= text[end] <= "9":
        end += 1
    if end == 0:
        return -1
    suffix = text[end:]
    if suffix not in _SIZE_UNITS:
        return -1
    return int(text[:end]) * _SIZE_UNITS[suffix]


# ---------------------------------------------------------------------------
# Families
# ---------------------------------------------------------------------------

LOWER_BOUND = Family(
    name="lower_bound",
    skill="binary_search",
    difficulty="hard",
    io={"args": ["list<int>", "int"], "returns": "int"},
    spec="""
`lower_bound` finds where a value belongs in a sorted index.

- `values` is sorted ascending and may contain duplicates.
- Return the index of the *first* element greater than or equal to `target`.
- If every element is smaller than `target`, return the length of the list, so
  the result is always a valid insertion point.
- An empty list returns 0.
""",
    signatures={
        "python": "def lower_bound(values: list[int], target: int) -> int:",
        "typescript": "function lowerBound(values: number[], target: number): number {",
        "go": "func LowerBound(values []int, target int) int {",
        "rust": "fn lower_bound(values: &[i64], target: i64) -> i64 {",
    },
    inputs=[
        [[1, 3, 5, 7], 5],
        [[1, 3, 5, 7], 4],
        [[1, 1, 1, 1], 1],
        [[], 5],
        [[2, 4, 6], 1],
        [[2, 4, 6], 7],
        [[1, 2, 2, 2, 3], 2],
        [[5], 5],
        [[5], 4],
    ],
    reference=lower_bound,
    extras={
        "symptom": (
            "Range scans over our sorted index drop rows. Asking for everything "
            "from a value that is present skips the first matching row, and if "
            "the value is present several times it skips all of them. Asking "
            "from a value that is not in the index returns the right rows."
        )
    },
    lang_extras={
        "python": {"buggy_code": dedent_code('''
            def lower_bound(values: list[int], target: int) -> int:
                lo, hi = 0, len(values)
                while lo < hi:
                    mid = (lo + hi) // 2
                    if values[mid] <= target:
                        lo = mid + 1
                    else:
                        hi = mid
                return lo
        ''')},
        "typescript": {"buggy_code": dedent_code('''
            function lowerBound(values: number[], target: number): number {
                let lo = 0;
                let hi = values.length;
                while (lo < hi) {
                    const mid = (lo + hi) >> 1;
                    if (values[mid] <= target) {
                        lo = mid + 1;
                    } else {
                        hi = mid;
                    }
                }
                return lo;
            }
        ''')},
        "go": {"buggy_code": dedent_code('''
            func LowerBound(values []int, target int) int {
                lo, hi := 0, len(values)
                for lo < hi {
                    mid := (lo + hi) / 2
                    if values[mid] <= target {
                        lo = mid + 1
                    } else {
                        hi = mid
                    }
                }
                return lo
            }
        ''')},
        "rust": {"buggy_code": dedent_code('''
            fn lower_bound(values: &[i64], target: i64) -> i64 {
                let mut lo = 0usize;
                let mut hi = values.len();
                while lo < hi {
                    let mid = (lo + hi) / 2;
                    if values[mid] <= target {
                        lo = mid + 1;
                    } else {
                        hi = mid;
                    }
                }
                lo as i64
            }
        ''')},
    },
    solutions={
        "python": dedent_code('''
            def lower_bound(values: list[int], target: int) -> int:
                lo, hi = 0, len(values)
                while lo < hi:
                    mid = (lo + hi) // 2
                    if values[mid] < target:
                        lo = mid + 1
                    else:
                        hi = mid
                return lo
        '''),
        "typescript": dedent_code('''
            export function lowerBound(values: number[], target: number): number {
                let lo = 0;
                let hi = values.length;
                while (lo < hi) {
                    const mid = (lo + hi) >> 1;
                    if (values[mid] < target) {
                        lo = mid + 1;
                    } else {
                        hi = mid;
                    }
                }
                return lo;
            }
        '''),
        "go": dedent_code('''
            package main

            func LowerBound(values []int, target int) int {
                lo, hi := 0, len(values)
                for lo < hi {
                    mid := (lo + hi) / 2
                    if values[mid] < target {
                        lo = mid + 1
                    } else {
                        hi = mid
                    }
                }
                return lo
            }
        '''),
        "rust": dedent_code('''
            fn lower_bound(values: &[i64], target: i64) -> i64 {
                let mut lo = 0usize;
                let mut hi = values.len();
                while lo < hi {
                    let mid = (lo + hi) / 2;
                    if values[mid] < target {
                        lo = mid + 1;
                    } else {
                        hi = mid;
                    }
                }
                lo as i64
            }
        '''),
    },
)


PARSE_DURATION = Family(
    name="parse_duration",
    skill="parsing",
    difficulty="hard",
    io={"args": ["str"], "returns": "int"},
    spec="""
`parse_duration` turns a Go-style duration string into a whole number of
seconds.

- The input is a sequence of `<digits><unit>` pairs with no separators, where
  the unit is `h`, `m`, or `s`: "45s", "90m", "1h30m", "1h2m3s".
- Numbers may have more than one digit, and the same unit may appear more than
  once; every pair contributes to the total.
- The empty string is zero seconds.
- Anything malformed returns -1: an unknown unit character, a unit with no
  number in front of it, or trailing digits with no unit.
""",
    signatures={
        "python": "def parse_duration(text: str) -> int:",
        "typescript": "function parseDuration(text: string): number {",
        "go": "func ParseDuration(text string) int {",
        "rust": "fn parse_duration(text: &str) -> i64 {",
    },
    inputs=[
        "1h30m",
        "45s",
        "2h",
        "1h2m3s",
        "",
        "90m",
        "10h",
        "1m30s",
        "5x",
        "h",
        "30",
    ],
    reference=parse_duration,
    extras={
        "symptom": (
            "Timeouts configured as a single unit behave, but compound ones do "
            "not: a job configured with \"1h30m\" gives up after thirty minutes, "
            "and \"1m30s\" after thirty seconds. It looks like only the last "
            "part of the string is taken into account."
        )
    },
    lang_extras={
        "python": {"buggy_code": dedent_code('''
            def parse_duration(text: str) -> int:
                total = 0
                number = 0
                seen_digit = False
                for ch in text:
                    if "0" <= ch <= "9":
                        number = number * 10 + (ord(ch) - 48)
                        seen_digit = True
                    elif ch in ("h", "m", "s"):
                        if not seen_digit:
                            return -1
                        scale = 3600 if ch == "h" else (60 if ch == "m" else 1)
                        total = number * scale
                        number = 0
                        seen_digit = False
                    else:
                        return -1
                return -1 if seen_digit else total
        ''')},
        "typescript": {"buggy_code": dedent_code('''
            function parseDuration(text: string): number {
                let total = 0;
                let number = 0;
                let seenDigit = false;
                for (const ch of text) {
                    if (ch >= "0" && ch <= "9") {
                        number = number * 10 + (ch.charCodeAt(0) - 48);
                        seenDigit = true;
                    } else if (ch === "h" || ch === "m" || ch === "s") {
                        if (!seenDigit) return -1;
                        const scale = ch === "h" ? 3600 : ch === "m" ? 60 : 1;
                        total = number * scale;
                        number = 0;
                        seenDigit = false;
                    } else {
                        return -1;
                    }
                }
                return seenDigit ? -1 : total;
            }
        ''')},
        "go": {"buggy_code": dedent_code('''
            func ParseDuration(text string) int {
                total, number := 0, 0
                seenDigit := false
                for _, ch := range text {
                    if ch >= '0' && ch <= '9' {
                        number = number*10 + int(ch-'0')
                        seenDigit = true
                    } else if ch == 'h' || ch == 'm' || ch == 's' {
                        if !seenDigit {
                            return -1
                        }
                        scale := 1
                        if ch == 'h' {
                            scale = 3600
                        } else if ch == 'm' {
                            scale = 60
                        }
                        total = number * scale
                        number = 0
                        seenDigit = false
                    } else {
                        return -1
                    }
                }
                if seenDigit {
                    return -1
                }
                return total
            }
        ''')},
        "rust": {"buggy_code": dedent_code('''
            fn parse_duration(text: &str) -> i64 {
                let mut total: i64 = 0;
                let mut number: i64 = 0;
                let mut seen_digit = false;
                for ch in text.chars() {
                    if ch.is_ascii_digit() {
                        number = number * 10 + (ch as i64 - '0' as i64);
                        seen_digit = true;
                    } else if ch == 'h' || ch == 'm' || ch == 's' {
                        if !seen_digit {
                            return -1;
                        }
                        let scale = if ch == 'h' { 3600 } else if ch == 'm' { 60 } else { 1 };
                        total = number * scale;
                        number = 0;
                        seen_digit = false;
                    } else {
                        return -1;
                    }
                }
                if seen_digit { -1 } else { total }
            }
        ''')},
    },
    solutions={
        "python": dedent_code('''
            def parse_duration(text: str) -> int:
                total = 0
                number = 0
                seen_digit = False
                for ch in text:
                    if "0" <= ch <= "9":
                        number = number * 10 + (ord(ch) - 48)
                        seen_digit = True
                    elif ch in ("h", "m", "s"):
                        if not seen_digit:
                            return -1
                        scale = 3600 if ch == "h" else (60 if ch == "m" else 1)
                        total += number * scale
                        number = 0
                        seen_digit = False
                    else:
                        return -1
                return -1 if seen_digit else total
        '''),
        "typescript": dedent_code('''
            export function parseDuration(text: string): number {
                let total = 0;
                let number = 0;
                let seenDigit = false;
                for (const ch of text) {
                    if (ch >= "0" && ch <= "9") {
                        number = number * 10 + (ch.charCodeAt(0) - 48);
                        seenDigit = true;
                    } else if (ch === "h" || ch === "m" || ch === "s") {
                        if (!seenDigit) return -1;
                        const scale = ch === "h" ? 3600 : ch === "m" ? 60 : 1;
                        total += number * scale;
                        number = 0;
                        seenDigit = false;
                    } else {
                        return -1;
                    }
                }
                return seenDigit ? -1 : total;
            }
        '''),
        "go": dedent_code('''
            package main

            func ParseDuration(text string) int {
                total, number := 0, 0
                seenDigit := false
                for _, ch := range text {
                    if ch >= '0' && ch <= '9' {
                        number = number*10 + int(ch-'0')
                        seenDigit = true
                    } else if ch == 'h' || ch == 'm' || ch == 's' {
                        if !seenDigit {
                            return -1
                        }
                        scale := 1
                        if ch == 'h' {
                            scale = 3600
                        } else if ch == 'm' {
                            scale = 60
                        }
                        total += number * scale
                        number = 0
                        seenDigit = false
                    } else {
                        return -1
                    }
                }
                if seenDigit {
                    return -1
                }
                return total
            }
        '''),
        "rust": dedent_code('''
            fn parse_duration(text: &str) -> i64 {
                let mut total: i64 = 0;
                let mut number: i64 = 0;
                let mut seen_digit = false;
                for ch in text.chars() {
                    if ch.is_ascii_digit() {
                        number = number * 10 + (ch as i64 - '0' as i64);
                        seen_digit = true;
                    } else if ch == 'h' || ch == 'm' || ch == 's' {
                        if !seen_digit {
                            return -1;
                        }
                        let scale = if ch == 'h' { 3600 } else if ch == 'm' { 60 } else { 1 };
                        total += number * scale;
                        number = 0;
                        seen_digit = false;
                    } else {
                        return -1;
                    }
                }
                if seen_digit { -1 } else { total }
            }
        '''),
    },
)


COVERED_SECONDS = Family(
    name="covered_seconds",
    skill="intervals",
    difficulty="hard",
    io={"args": ["list<int>", "list<int>"], "returns": "int"},
    spec="""
`covered_seconds` measures how long a service was down, given overlapping
incident windows from several alerting sources.

- Incident i covers the half-open interval [starts[i], ends[i]); `starts` and
  `ends` are parallel arrays of the same length.
- Return the total length of the *union* of the intervals, counting overlapping
  time once.
- The incidents arrive in no particular order and may overlap, touch, or sit
  entirely inside one another.
- Intervals with ends[i] <= starts[i] cover nothing.
- No incidents means 0.
""",
    signatures={
        "python": "def covered_seconds(starts: list[int], ends: list[int]) -> int:",
        "typescript": "function coveredSeconds(starts: number[], ends: number[]): number {",
        "go": "func CoveredSeconds(starts []int, ends []int) int {",
        "rust": "fn covered_seconds(starts: &[i64], ends: &[i64]) -> i64 {",
    },
    inputs=[
        [[0, 5], [10, 15]],
        [[0, 2], [10, 5]],
        [[0, 20], [10, 30]],
        [[], []],
        [[5], [5]],
        [[0, 1, 2], [10, 10, 10]],
        [[0, 3, 1], [2, 5, 10]],
        [[0, 1], [100, 2]],
        [[100], [200]],
        [[10, 0], [20, 30]],
    ],
    reference=covered_seconds,
    extras={
        "symptom": (
            "Our monthly downtime number came out lower than the longest single "
            "incident that month. It is only wrong when one alerting source "
            "opened a short window inside a longer one that another source had "
            "already opened; plain overlaps and back-to-back windows add up "
            "correctly."
        )
    },
    lang_extras={
        "python": {"buggy_code": dedent_code('''
            def covered_seconds(starts: list[int], ends: list[int]) -> int:
                n = min(len(starts), len(ends))
                spans = sorted((starts[i], ends[i]) for i in range(n) if ends[i] > starts[i])
                total = 0
                have = False
                cur_start = 0
                cur_end = 0
                for start, end in spans:
                    if not have:
                        cur_start, cur_end = start, end
                        have = True
                    elif start <= cur_end:
                        cur_end = end
                    else:
                        total += cur_end - cur_start
                        cur_start, cur_end = start, end
                if have:
                    total += cur_end - cur_start
                return total
        ''')},
        "typescript": {"buggy_code": dedent_code('''
            function coveredSeconds(starts: number[], ends: number[]): number {
                const n = Math.min(starts.length, ends.length);
                const spans: Array<[number, number]> = [];
                for (let i = 0; i < n; i++) {
                    if (ends[i] > starts[i]) spans.push([starts[i], ends[i]]);
                }
                spans.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
                let total = 0;
                let have = false;
                let curStart = 0;
                let curEnd = 0;
                for (const [start, end] of spans) {
                    if (!have) {
                        curStart = start;
                        curEnd = end;
                        have = true;
                    } else if (start <= curEnd) {
                        curEnd = end;
                    } else {
                        total += curEnd - curStart;
                        curStart = start;
                        curEnd = end;
                    }
                }
                if (have) total += curEnd - curStart;
                return total;
            }
        ''')},
        "go": {"buggy_code": dedent_code('''
            import "sort"

            func CoveredSeconds(starts []int, ends []int) int {
                n := len(starts)
                if len(ends) < n {
                    n = len(ends)
                }
                type span struct{ start, end int }
                spans := make([]span, 0, n)
                for i := 0; i < n; i++ {
                    if ends[i] > starts[i] {
                        spans = append(spans, span{starts[i], ends[i]})
                    }
                }
                sort.Slice(spans, func(i, j int) bool {
                    if spans[i].start != spans[j].start {
                        return spans[i].start < spans[j].start
                    }
                    return spans[i].end < spans[j].end
                })
                total, curStart, curEnd := 0, 0, 0
                have := false
                for _, s := range spans {
                    if !have {
                        curStart, curEnd = s.start, s.end
                        have = true
                    } else if s.start <= curEnd {
                        curEnd = s.end
                    } else {
                        total += curEnd - curStart
                        curStart, curEnd = s.start, s.end
                    }
                }
                if have {
                    total += curEnd - curStart
                }
                return total
            }
        ''')},
        "rust": {"buggy_code": dedent_code('''
            fn covered_seconds(starts: &[i64], ends: &[i64]) -> i64 {
                let n = starts.len().min(ends.len());
                let mut spans: Vec<(i64, i64)> = (0..n)
                    .filter(|&i| ends[i] > starts[i])
                    .map(|i| (starts[i], ends[i]))
                    .collect();
                spans.sort_unstable();
                let mut total: i64 = 0;
                let mut have = false;
                let mut cur_start: i64 = 0;
                let mut cur_end: i64 = 0;
                for (start, end) in spans {
                    if !have {
                        cur_start = start;
                        cur_end = end;
                        have = true;
                    } else if start <= cur_end {
                        cur_end = end;
                    } else {
                        total += cur_end - cur_start;
                        cur_start = start;
                        cur_end = end;
                    }
                }
                if have {
                    total += cur_end - cur_start;
                }
                total
            }
        ''')},
    },
    solutions={
        "python": dedent_code('''
            def covered_seconds(starts: list[int], ends: list[int]) -> int:
                n = min(len(starts), len(ends))
                spans = sorted((starts[i], ends[i]) for i in range(n) if ends[i] > starts[i])
                total = 0
                have = False
                cur_start = 0
                cur_end = 0
                for start, end in spans:
                    if not have:
                        cur_start, cur_end = start, end
                        have = True
                    elif start <= cur_end:
                        if end > cur_end:
                            cur_end = end
                    else:
                        total += cur_end - cur_start
                        cur_start, cur_end = start, end
                if have:
                    total += cur_end - cur_start
                return total
        '''),
        "typescript": dedent_code('''
            export function coveredSeconds(starts: number[], ends: number[]): number {
                const n = Math.min(starts.length, ends.length);
                const spans: Array<[number, number]> = [];
                for (let i = 0; i < n; i++) {
                    if (ends[i] > starts[i]) spans.push([starts[i], ends[i]]);
                }
                spans.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
                let total = 0;
                let have = false;
                let curStart = 0;
                let curEnd = 0;
                for (const [start, end] of spans) {
                    if (!have) {
                        curStart = start;
                        curEnd = end;
                        have = true;
                    } else if (start <= curEnd) {
                        if (end > curEnd) curEnd = end;
                    } else {
                        total += curEnd - curStart;
                        curStart = start;
                        curEnd = end;
                    }
                }
                if (have) total += curEnd - curStart;
                return total;
            }
        '''),
        "go": dedent_code('''
            package main

            import "sort"

            func CoveredSeconds(starts []int, ends []int) int {
                n := len(starts)
                if len(ends) < n {
                    n = len(ends)
                }
                type span struct{ start, end int }
                spans := make([]span, 0, n)
                for i := 0; i < n; i++ {
                    if ends[i] > starts[i] {
                        spans = append(spans, span{starts[i], ends[i]})
                    }
                }
                sort.Slice(spans, func(i, j int) bool {
                    if spans[i].start != spans[j].start {
                        return spans[i].start < spans[j].start
                    }
                    return spans[i].end < spans[j].end
                })
                total, curStart, curEnd := 0, 0, 0
                have := false
                for _, s := range spans {
                    if !have {
                        curStart, curEnd = s.start, s.end
                        have = true
                    } else if s.start <= curEnd {
                        if s.end > curEnd {
                            curEnd = s.end
                        }
                    } else {
                        total += curEnd - curStart
                        curStart, curEnd = s.start, s.end
                    }
                }
                if have {
                    total += curEnd - curStart
                }
                return total
            }
        '''),
        "rust": dedent_code('''
            fn covered_seconds(starts: &[i64], ends: &[i64]) -> i64 {
                let n = starts.len().min(ends.len());
                let mut spans: Vec<(i64, i64)> = (0..n)
                    .filter(|&i| ends[i] > starts[i])
                    .map(|i| (starts[i], ends[i]))
                    .collect();
                spans.sort_unstable();
                let mut total: i64 = 0;
                let mut have = false;
                let mut cur_start: i64 = 0;
                let mut cur_end: i64 = 0;
                for (start, end) in spans {
                    if !have {
                        cur_start = start;
                        cur_end = end;
                        have = true;
                    } else if start <= cur_end {
                        if end > cur_end {
                            cur_end = end;
                        }
                    } else {
                        total += cur_end - cur_start;
                        cur_start = start;
                        cur_end = end;
                    }
                }
                if have {
                    total += cur_end - cur_start;
                }
                total
            }
        '''),
    },
)


LUHN_VALID = Family(
    name="luhn_valid",
    skill="validation",
    difficulty="hard",
    io={"args": ["str"], "returns": "bool"},
    spec="""
`luhn_valid` checks a number against the Luhn checksum used by payment cards.

The algorithm works from the **rightmost** digit leftwards:

- Leave the rightmost digit as it is, double the next one to its left, leave the
  next, and so on — every second digit counting from the right is doubled.
- A doubled digit greater than 9 has 9 subtracted from it (so 8 doubles to 16,
  which counts as 7).
- Sum every resulting digit; the number is valid when that sum is a multiple
  of 10.

Return false for the empty string and for anything containing a non-digit.
""",
    signatures={
        "python": "def luhn_valid(digits: str) -> bool:",
        "typescript": "function luhnValid(digits: string): boolean {",
        "go": "func LuhnValid(digits string) bool {",
        "rust": "fn luhn_valid(digits: &str) -> bool {",
    },
    inputs=[
        "4539578763621486",
        "4539578763621487",
        "79927398713",
        "79927398710",
        "378282246310005",
        "0",
        "18",
        "",
        "12a4",
        "6011111111111117",
    ],
    reference=luhn_valid,
    extras={
        "symptom": (
            "Card validation rejects real cards. Our 15-digit Amex test numbers "
            "validate fine, but every 16-digit Visa and Mastercard we try is "
            "rejected — and a couple of deliberately corrupted 16-digit numbers "
            "are accepted. It behaves as if the doubling starts from the wrong "
            "end for even-length numbers."
        )
    },
    lang_extras={
        "python": {"buggy_code": dedent_code('''
            def luhn_valid(digits: str) -> bool:
                if not digits:
                    return False
                for ch in digits:
                    if ch < "0" or ch > "9":
                        return False
                total = 0
                for index, ch in enumerate(digits):
                    value = ord(ch) - 48
                    if index % 2 == 1:
                        value *= 2
                        if value > 9:
                            value -= 9
                    total += value
                return total % 10 == 0
        ''')},
        "typescript": {"buggy_code": dedent_code('''
            function luhnValid(digits: string): boolean {
                if (digits.length === 0) return false;
                for (const ch of digits) {
                    if (ch < "0" || ch > "9") return false;
                }
                let total = 0;
                for (let index = 0; index < digits.length; index++) {
                    let value = digits.charCodeAt(index) - 48;
                    if (index % 2 === 1) {
                        value *= 2;
                        if (value > 9) value -= 9;
                    }
                    total += value;
                }
                return total % 10 === 0;
            }
        ''')},
        "go": {"buggy_code": dedent_code('''
            func LuhnValid(digits string) bool {
                if len(digits) == 0 {
                    return false
                }
                for _, ch := range digits {
                    if ch < '0' || ch > '9' {
                        return false
                    }
                }
                total := 0
                for index := 0; index < len(digits); index++ {
                    value := int(digits[index] - '0')
                    if index%2 == 1 {
                        value *= 2
                        if value > 9 {
                            value -= 9
                        }
                    }
                    total += value
                }
                return total%10 == 0
            }
        ''')},
        "rust": {"buggy_code": dedent_code('''
            fn luhn_valid(digits: &str) -> bool {
                if digits.is_empty() {
                    return false;
                }
                if !digits.chars().all(|c| c.is_ascii_digit()) {
                    return false;
                }
                let mut total: i64 = 0;
                for (index, ch) in digits.chars().enumerate() {
                    let mut value = ch as i64 - '0' as i64;
                    if index % 2 == 1 {
                        value *= 2;
                        if value > 9 {
                            value -= 9;
                        }
                    }
                    total += value;
                }
                total % 10 == 0
            }
        ''')},
    },
    solutions={
        "python": dedent_code('''
            def luhn_valid(digits: str) -> bool:
                if not digits:
                    return False
                for ch in digits:
                    if ch < "0" or ch > "9":
                        return False
                total = 0
                double = False
                for ch in reversed(digits):
                    value = ord(ch) - 48
                    if double:
                        value *= 2
                        if value > 9:
                            value -= 9
                    total += value
                    double = not double
                return total % 10 == 0
        '''),
        "typescript": dedent_code('''
            export function luhnValid(digits: string): boolean {
                if (digits.length === 0) return false;
                for (const ch of digits) {
                    if (ch < "0" || ch > "9") return false;
                }
                let total = 0;
                let double = false;
                for (let index = digits.length - 1; index >= 0; index--) {
                    let value = digits.charCodeAt(index) - 48;
                    if (double) {
                        value *= 2;
                        if (value > 9) value -= 9;
                    }
                    total += value;
                    double = !double;
                }
                return total % 10 === 0;
            }
        '''),
        "go": dedent_code('''
            package main

            func LuhnValid(digits string) bool {
                if len(digits) == 0 {
                    return false
                }
                for _, ch := range digits {
                    if ch < '0' || ch > '9' {
                        return false
                    }
                }
                total := 0
                double := false
                for index := len(digits) - 1; index >= 0; index-- {
                    value := int(digits[index] - '0')
                    if double {
                        value *= 2
                        if value > 9 {
                            value -= 9
                        }
                    }
                    total += value
                    double = !double
                }
                return total%10 == 0
            }
        '''),
        "rust": dedent_code('''
            fn luhn_valid(digits: &str) -> bool {
                if digits.is_empty() {
                    return false;
                }
                if !digits.chars().all(|c| c.is_ascii_digit()) {
                    return false;
                }
                let mut total: i64 = 0;
                let mut double = false;
                for ch in digits.chars().rev() {
                    let mut value = ch as i64 - '0' as i64;
                    if double {
                        value *= 2;
                        if value > 9 {
                            value -= 9;
                        }
                    }
                    total += value;
                    double = !double;
                }
                total % 10 == 0
            }
        '''),
    },
)


IP_IN_CIDR = Family(
    name="ip_in_cidr",
    skill="networking",
    difficulty="hard",
    io={"args": ["str", "str"], "returns": "bool"},
    spec="""
`ip_in_cidr` decides whether an IPv4 address falls inside a CIDR block.

- `cidr` is "A.B.C.D/prefix" with a prefix between 0 and 32.
- The address is inside the block when its first `prefix` **bits** match the
  block's. A prefix is not always a whole number of octets: /12 and /23 are as
  legal as /8 and /24.
- /0 matches every address; /32 matches exactly one.
- Return false for a malformed address or block: a missing "/", a prefix above
  32 or made of non-digits, or an address that is not four decimal octets in
  0-255.
""",
    signatures={
        "python": "def ip_in_cidr(ip: str, cidr: str) -> bool:",
        "typescript": "function ipInCidr(ip: string, cidr: string): boolean {",
        "go": "func IpInCidr(ip string, cidr string) bool {",
        "rust": "fn ip_in_cidr(ip: &str, cidr: &str) -> bool {",
    },
    inputs=[
        ["10.1.2.3", "10.0.0.0/8"],
        ["11.1.2.3", "10.0.0.0/8"],
        ["10.16.0.1", "10.0.0.0/12"],
        ["10.15.255.255", "10.0.0.0/12"],
        ["192.168.1.5", "192.168.1.0/24"],
        ["192.168.2.5", "192.168.1.0/24"],
        ["203.0.113.9", "203.0.112.0/23"],
        ["203.0.114.9", "203.0.112.0/23"],
        ["1.2.3.4", "0.0.0.0/0"],
        ["10.0.0.1", "10.0.0.1/32"],
        ["10.0.0.2", "10.0.0.1/32"],
        ["10.0.0.1", "10.0.0.0/33"],
        ["10.0.0.300", "10.0.0.0/8"],
        ["10.0.0.1", "10.0.0.0"],
    ],
    reference=ip_in_cidr,
    extras={
        "symptom": (
            "Our allow-list lets through addresses it should not. The blocks we "
            "wrote as /8, /16, /24 and /32 behave exactly right, but a /12 "
            "block is matching addresses well outside its range — 10.16.0.1 is "
            "accepted for 10.0.0.0/12. Malformed input is still rejected "
            "properly."
        )
    },
    lang_extras={
        "python": {"buggy_code": dedent_code('''
            def _ipv4(text: str):
                parts = text.split(".")
                if len(parts) != 4:
                    return None
                total = 0
                for part in parts:
                    if not part or len(part) > 3:
                        return None
                    for ch in part:
                        if ch < "0" or ch > "9":
                            return None
                    value = int(part)
                    if value > 255:
                        return None
                    total = total * 256 + value
                return total


            def ip_in_cidr(ip: str, cidr: str) -> bool:
                base, sep, prefix_text = cidr.partition("/")
                if not sep or not prefix_text:
                    return False
                for ch in prefix_text:
                    if ch < "0" or ch > "9":
                        return False
                prefix = int(prefix_text)
                if prefix > 32:
                    return False
                if _ipv4(ip) is None or _ipv4(base) is None:
                    return False
                whole_octets = prefix // 8
                left = ip.split(".")
                right = base.split(".")
                for i in range(whole_octets):
                    if left[i] != right[i]:
                        return False
                return True
        ''')},
        "typescript": {"buggy_code": dedent_code('''
            function ipv4(text: string): number | null {
                const parts = text.split(".");
                if (parts.length !== 4) return null;
                let total = 0;
                for (const part of parts) {
                    if (part.length === 0 || part.length > 3) return null;
                    if (!/^[0-9]+$/.test(part)) return null;
                    const value = parseInt(part, 10);
                    if (value > 255) return null;
                    total = total * 256 + value;
                }
                return total;
            }

            function ipInCidr(ip: string, cidr: string): boolean {
                const slash = cidr.indexOf("/");
                if (slash < 0) return false;
                const base = cidr.slice(0, slash);
                const prefixText = cidr.slice(slash + 1);
                if (!/^[0-9]+$/.test(prefixText)) return false;
                const prefix = parseInt(prefixText, 10);
                if (prefix > 32) return false;
                if (ipv4(ip) === null || ipv4(base) === null) return false;
                const wholeOctets = Math.floor(prefix / 8);
                const left = ip.split(".");
                const right = base.split(".");
                for (let i = 0; i < wholeOctets; i++) {
                    if (left[i] !== right[i]) return false;
                }
                return true;
            }
        ''')},
        "go": {"buggy_code": dedent_code('''
            import (
                "strconv"
                "strings"
            )

            func parseIPv4(text string) (uint32, bool) {
                parts := strings.Split(text, ".")
                if len(parts) != 4 {
                    return 0, false
                }
                var total uint32
                for _, part := range parts {
                    if len(part) == 0 || len(part) > 3 {
                        return 0, false
                    }
                    for _, ch := range part {
                        if ch < '0' || ch > '9' {
                            return 0, false
                        }
                    }
                    value, err := strconv.Atoi(part)
                    if err != nil || value > 255 {
                        return 0, false
                    }
                    total = total*256 + uint32(value)
                }
                return total, true
            }

            func IpInCidr(ip string, cidr string) bool {
                slash := strings.Index(cidr, "/")
                if slash < 0 {
                    return false
                }
                base := cidr[:slash]
                prefixText := cidr[slash+1:]
                if len(prefixText) == 0 {
                    return false
                }
                for _, ch := range prefixText {
                    if ch < '0' || ch > '9' {
                        return false
                    }
                }
                prefix, err := strconv.Atoi(prefixText)
                if err != nil || prefix > 32 {
                    return false
                }
                if _, ok := parseIPv4(ip); !ok {
                    return false
                }
                if _, ok := parseIPv4(base); !ok {
                    return false
                }
                wholeOctets := prefix / 8
                left := strings.Split(ip, ".")
                right := strings.Split(base, ".")
                for i := 0; i < wholeOctets; i++ {
                    if left[i] != right[i] {
                        return false
                    }
                }
                return true
            }
        ''')},
        "rust": {"buggy_code": dedent_code('''
            fn parse_ipv4(text: &str) -> Option<u32> {
                let parts: Vec<&str> = text.split('.').collect();
                if parts.len() != 4 {
                    return None;
                }
                let mut total: u32 = 0;
                for part in parts {
                    if part.is_empty() || part.len() > 3 {
                        return None;
                    }
                    if !part.chars().all(|c| c.is_ascii_digit()) {
                        return None;
                    }
                    let value: u32 = part.parse().ok()?;
                    if value > 255 {
                        return None;
                    }
                    total = total * 256 + value;
                }
                Some(total)
            }

            fn ip_in_cidr(ip: &str, cidr: &str) -> bool {
                let (base, prefix_text) = match cidr.split_once('/') {
                    Some(pair) => pair,
                    None => return false,
                };
                if prefix_text.is_empty() || !prefix_text.chars().all(|c| c.is_ascii_digit()) {
                    return false;
                }
                let prefix: u32 = match prefix_text.parse() {
                    Ok(value) => value,
                    Err(_) => return false,
                };
                if prefix > 32 {
                    return false;
                }
                if parse_ipv4(ip).is_none() || parse_ipv4(base).is_none() {
                    return false;
                }
                let whole_octets = (prefix / 8) as usize;
                let left: Vec<&str> = ip.split('.').collect();
                let right: Vec<&str> = base.split('.').collect();
                for i in 0..whole_octets {
                    if left[i] != right[i] {
                        return false;
                    }
                }
                true
            }
        ''')},
    },
    solutions={
        "python": dedent_code('''
            def _ipv4(text: str):
                parts = text.split(".")
                if len(parts) != 4:
                    return None
                total = 0
                for part in parts:
                    if not part or len(part) > 3:
                        return None
                    for ch in part:
                        if ch < "0" or ch > "9":
                            return None
                    value = int(part)
                    if value > 255:
                        return None
                    total = total * 256 + value
                return total


            def ip_in_cidr(ip: str, cidr: str) -> bool:
                base, sep, prefix_text = cidr.partition("/")
                if not sep or not prefix_text:
                    return False
                for ch in prefix_text:
                    if ch < "0" or ch > "9":
                        return False
                prefix = int(prefix_text)
                if prefix > 32:
                    return False
                left = _ipv4(ip)
                right = _ipv4(base)
                if left is None or right is None:
                    return False
                if prefix == 0:
                    return True
                mask = (0xFFFFFFFF << (32 - prefix)) & 0xFFFFFFFF
                return (left & mask) == (right & mask)
        '''),
        "typescript": dedent_code('''
            function ipv4(text: string): number | null {
                const parts = text.split(".");
                if (parts.length !== 4) return null;
                let total = 0;
                for (const part of parts) {
                    if (part.length === 0 || part.length > 3) return null;
                    if (!/^[0-9]+$/.test(part)) return null;
                    const value = parseInt(part, 10);
                    if (value > 255) return null;
                    total = total * 256 + value;
                }
                return total;
            }

            export function ipInCidr(ip: string, cidr: string): boolean {
                const slash = cidr.indexOf("/");
                if (slash < 0) return false;
                const base = cidr.slice(0, slash);
                const prefixText = cidr.slice(slash + 1);
                if (!/^[0-9]+$/.test(prefixText)) return false;
                const prefix = parseInt(prefixText, 10);
                if (prefix > 32) return false;
                const left = ipv4(ip);
                const right = ipv4(base);
                if (left === null || right === null) return false;
                if (prefix === 0) return true;
                const mask = (0xFFFFFFFF << (32 - prefix)) >>> 0;
                return ((left & mask) >>> 0) === ((right & mask) >>> 0);
            }
        '''),
        "go": dedent_code('''
            package main

            import (
                "strconv"
                "strings"
            )

            func parseIPv4(text string) (uint32, bool) {
                parts := strings.Split(text, ".")
                if len(parts) != 4 {
                    return 0, false
                }
                var total uint32
                for _, part := range parts {
                    if len(part) == 0 || len(part) > 3 {
                        return 0, false
                    }
                    for _, ch := range part {
                        if ch < '0' || ch > '9' {
                            return 0, false
                        }
                    }
                    value, err := strconv.Atoi(part)
                    if err != nil || value > 255 {
                        return 0, false
                    }
                    total = total*256 + uint32(value)
                }
                return total, true
            }

            func IpInCidr(ip string, cidr string) bool {
                slash := strings.Index(cidr, "/")
                if slash < 0 {
                    return false
                }
                base := cidr[:slash]
                prefixText := cidr[slash+1:]
                if len(prefixText) == 0 {
                    return false
                }
                for _, ch := range prefixText {
                    if ch < '0' || ch > '9' {
                        return false
                    }
                }
                prefix, err := strconv.Atoi(prefixText)
                if err != nil || prefix > 32 {
                    return false
                }
                left, okLeft := parseIPv4(ip)
                right, okRight := parseIPv4(base)
                if !okLeft || !okRight {
                    return false
                }
                if prefix == 0 {
                    return true
                }
                mask := uint32(0xFFFFFFFF) << uint(32-prefix)
                return (left & mask) == (right & mask)
            }
        '''),
        "rust": dedent_code('''
            fn parse_ipv4(text: &str) -> Option<u32> {
                let parts: Vec<&str> = text.split('.').collect();
                if parts.len() != 4 {
                    return None;
                }
                let mut total: u32 = 0;
                for part in parts {
                    if part.is_empty() || part.len() > 3 {
                        return None;
                    }
                    if !part.chars().all(|c| c.is_ascii_digit()) {
                        return None;
                    }
                    let value: u32 = part.parse().ok()?;
                    if value > 255 {
                        return None;
                    }
                    total = total * 256 + value;
                }
                Some(total)
            }

            fn ip_in_cidr(ip: &str, cidr: &str) -> bool {
                let (base, prefix_text) = match cidr.split_once('/') {
                    Some(pair) => pair,
                    None => return false,
                };
                if prefix_text.is_empty() || !prefix_text.chars().all(|c| c.is_ascii_digit()) {
                    return false;
                }
                let prefix: u32 = match prefix_text.parse() {
                    Ok(value) => value,
                    Err(_) => return false,
                };
                if prefix > 32 {
                    return false;
                }
                let (left, right) = match (parse_ipv4(ip), parse_ipv4(base)) {
                    (Some(a), Some(b)) => (a, b),
                    _ => return false,
                };
                if prefix == 0 {
                    return true;
                }
                let mask: u32 = u32::MAX << (32 - prefix);
                (left & mask) == (right & mask)
            }
        '''),
    },
)


SLIDING_RATE_LIMIT = Family(
    name="sliding_rate_limit",
    skill="rate_limiting",
    difficulty="hard",
    io={"args": ["list<int>", "int", "int"], "returns": "int"},
    spec="""
`sliding_rate_limit` replays a request log through a sliding-window limiter and
reports how many requests were let through.

- `timestamps` are millisecond arrival times in non-decreasing order.
- Process them in order, remembering the times of the requests you **allowed**.
- A request at time t is allowed when fewer than `limit` previously allowed
  requests fall inside the window, which is the half-open range
  (t - window, t]. An allowed request at exactly t - window has expired and no
  longer counts.
- Return the number of allowed requests.
- Return 0 if `window` or `limit` is not positive.
""",
    signatures={
        "python": "def sliding_rate_limit(timestamps: list[int], window: int, limit: int) -> int:",
        "typescript": (
            "function slidingRateLimit(timestamps: number[], window: number, "
            "limit: number): number {"
        ),
        "go": "func SlidingRateLimit(timestamps []int, window int, limit int) int {",
        "rust": "fn sliding_rate_limit(timestamps: &[i64], window: i64, limit: i64) -> i64 {",
    },
    inputs=[
        [[0, 1000, 2000], 1000, 1],
        [[0, 500, 1000], 1000, 2],
        [[0, 1, 2, 3], 10, 2],
        [[], 100, 5],
        [[5, 5, 5], 10, 0],
        [[1, 2, 3], 0, 5],
        [[0, 100, 200, 300], 250, 2],
        [[10, 20, 30, 40, 50], 25, 3],
        [[0, 0, 0, 0], 1000, 2],
        [[0, 999, 1000, 1001], 1000, 1],
    ],
    reference=sliding_rate_limit,
    extras={
        "symptom": (
            "A client pacing itself at exactly the configured rate still gets "
            "429s. If it sends one request every 1000ms against a "
            "1-per-1000ms limit, only the first is allowed. Pacing slightly "
            "slower works, and bursty traffic is throttled correctly."
        )
    },
    lang_extras={
        "python": {"buggy_code": dedent_code('''
            def sliding_rate_limit(timestamps: list[int], window: int, limit: int) -> int:
                if window <= 0 or limit <= 0:
                    return 0
                allowed = []
                head = 0
                count = 0
                for stamp in timestamps:
                    while head < len(allowed) and allowed[head] < stamp - window:
                        head += 1
                    if len(allowed) - head < limit:
                        allowed.append(stamp)
                        count += 1
                return count
        ''')},
        "typescript": {"buggy_code": dedent_code('''
            function slidingRateLimit(timestamps: number[], window: number, limit: number): number {
                if (window <= 0 || limit <= 0) return 0;
                const allowed: number[] = [];
                let head = 0;
                let count = 0;
                for (const stamp of timestamps) {
                    while (head < allowed.length && allowed[head] < stamp - window) head++;
                    if (allowed.length - head < limit) {
                        allowed.push(stamp);
                        count++;
                    }
                }
                return count;
            }
        ''')},
        "go": {"buggy_code": dedent_code('''
            func SlidingRateLimit(timestamps []int, window int, limit int) int {
                if window <= 0 || limit <= 0 {
                    return 0
                }
                allowed := make([]int, 0, len(timestamps))
                head, count := 0, 0
                for _, stamp := range timestamps {
                    for head < len(allowed) && allowed[head] < stamp-window {
                        head++
                    }
                    if len(allowed)-head < limit {
                        allowed = append(allowed, stamp)
                        count++
                    }
                }
                return count
            }
        ''')},
        "rust": {"buggy_code": dedent_code('''
            fn sliding_rate_limit(timestamps: &[i64], window: i64, limit: i64) -> i64 {
                if window <= 0 || limit <= 0 {
                    return 0;
                }
                let mut allowed: Vec<i64> = Vec::new();
                let mut head = 0usize;
                let mut count: i64 = 0;
                for &stamp in timestamps {
                    while head < allowed.len() && allowed[head] < stamp - window {
                        head += 1;
                    }
                    if ((allowed.len() - head) as i64) < limit {
                        allowed.push(stamp);
                        count += 1;
                    }
                }
                count
            }
        ''')},
    },
    solutions={
        "python": dedent_code('''
            def sliding_rate_limit(timestamps: list[int], window: int, limit: int) -> int:
                if window <= 0 or limit <= 0:
                    return 0
                allowed = []
                head = 0
                count = 0
                for stamp in timestamps:
                    while head < len(allowed) and allowed[head] <= stamp - window:
                        head += 1
                    if len(allowed) - head < limit:
                        allowed.append(stamp)
                        count += 1
                return count
        '''),
        "typescript": dedent_code('''
            export function slidingRateLimit(
                timestamps: number[],
                window: number,
                limit: number,
            ): number {
                if (window <= 0 || limit <= 0) return 0;
                const allowed: number[] = [];
                let head = 0;
                let count = 0;
                for (const stamp of timestamps) {
                    while (head < allowed.length && allowed[head] <= stamp - window) head++;
                    if (allowed.length - head < limit) {
                        allowed.push(stamp);
                        count++;
                    }
                }
                return count;
            }
        '''),
        "go": dedent_code('''
            package main

            func SlidingRateLimit(timestamps []int, window int, limit int) int {
                if window <= 0 || limit <= 0 {
                    return 0
                }
                allowed := make([]int, 0, len(timestamps))
                head, count := 0, 0
                for _, stamp := range timestamps {
                    for head < len(allowed) && allowed[head] <= stamp-window {
                        head++
                    }
                    if len(allowed)-head < limit {
                        allowed = append(allowed, stamp)
                        count++
                    }
                }
                return count
            }
        '''),
        "rust": dedent_code('''
            fn sliding_rate_limit(timestamps: &[i64], window: i64, limit: i64) -> i64 {
                if window <= 0 || limit <= 0 {
                    return 0;
                }
                let mut allowed: Vec<i64> = Vec::new();
                let mut head = 0usize;
                let mut count: i64 = 0;
                for &stamp in timestamps {
                    while head < allowed.len() && allowed[head] <= stamp - window {
                        head += 1;
                    }
                    if ((allowed.len() - head) as i64) < limit {
                        allowed.push(stamp);
                        count += 1;
                    }
                }
                count
            }
        '''),
    },
)


COUNTER_INCREASE = Family(
    name="counter_increase",
    skill="metrics",
    difficulty="hard",
    io={"args": ["list<int>"], "returns": "int"},
    spec="""
`counter_increase` totals the real increase of a monotonic counter across a
series of scrapes, the way a metrics backend computes `increase()`.

- `values` are successive readings, oldest first.
- A counter only ever goes up while the process lives, so a reading that is
  **strictly lower** than the one before it means the process restarted and the
  counter reset to 0. In that case the whole new reading is fresh increase.
- Two consecutive equal readings mean nothing happened between them: that is an
  increase of 0, not a reset.
- Fewer than two readings means 0.
""",
    signatures={
        "python": "def counter_increase(values: list[int]) -> int:",
        "typescript": "function counterIncrease(values: number[]): number {",
        "go": "func CounterIncrease(values []int) int {",
        "rust": "fn counter_increase(values: &[i64]) -> i64 {",
    },
    inputs=[
        [0, 5, 10],
        [5, 5, 5],
        [10, 3, 8],
        [],
        [7],
        [0, 0, 0, 1],
        [100, 100, 200],
        [3, 2, 2, 4],
        [1, 2, 3, 4, 5],
        [50, 50, 40, 40, 45],
    ],
    reference=counter_increase,
    extras={
        "symptom": (
            "Request-rate graphs spike on idle services. A service that served "
            "nothing for a few scrapes shows an enormous burst instead of a "
            "flat zero, and the size of the fake burst is exactly the counter's "
            "current value. Genuine restarts and steadily rising counters are "
            "reported correctly."
        )
    },
    lang_extras={
        "python": {"buggy_code": dedent_code('''
            def counter_increase(values: list[int]) -> int:
                total = 0
                for i in range(1, len(values)):
                    if values[i] > values[i - 1]:
                        total += values[i] - values[i - 1]
                    else:
                        total += values[i]
                return total
        ''')},
        "typescript": {"buggy_code": dedent_code('''
            function counterIncrease(values: number[]): number {
                let total = 0;
                for (let i = 1; i < values.length; i++) {
                    if (values[i] > values[i - 1]) {
                        total += values[i] - values[i - 1];
                    } else {
                        total += values[i];
                    }
                }
                return total;
            }
        ''')},
        "go": {"buggy_code": dedent_code('''
            func CounterIncrease(values []int) int {
                total := 0
                for i := 1; i < len(values); i++ {
                    if values[i] > values[i-1] {
                        total += values[i] - values[i-1]
                    } else {
                        total += values[i]
                    }
                }
                return total
            }
        ''')},
        "rust": {"buggy_code": dedent_code('''
            fn counter_increase(values: &[i64]) -> i64 {
                let mut total: i64 = 0;
                for i in 1..values.len() {
                    if values[i] > values[i - 1] {
                        total += values[i] - values[i - 1];
                    } else {
                        total += values[i];
                    }
                }
                total
            }
        ''')},
    },
    solutions={
        "python": dedent_code('''
            def counter_increase(values: list[int]) -> int:
                total = 0
                for i in range(1, len(values)):
                    if values[i] >= values[i - 1]:
                        total += values[i] - values[i - 1]
                    else:
                        total += values[i]
                return total
        '''),
        "typescript": dedent_code('''
            export function counterIncrease(values: number[]): number {
                let total = 0;
                for (let i = 1; i < values.length; i++) {
                    if (values[i] >= values[i - 1]) {
                        total += values[i] - values[i - 1];
                    } else {
                        total += values[i];
                    }
                }
                return total;
            }
        '''),
        "go": dedent_code('''
            package main

            func CounterIncrease(values []int) int {
                total := 0
                for i := 1; i < len(values); i++ {
                    if values[i] >= values[i-1] {
                        total += values[i] - values[i-1]
                    } else {
                        total += values[i]
                    }
                }
                return total
            }
        '''),
        "rust": dedent_code('''
            fn counter_increase(values: &[i64]) -> i64 {
                let mut total: i64 = 0;
                for i in 1..values.len() {
                    if values[i] >= values[i - 1] {
                        total += values[i] - values[i - 1];
                    } else {
                        total += values[i];
                    }
                }
                total
            }
        '''),
    },
)


VERSION_BUMP = Family(
    name="version_bump",
    skill="versioning",
    difficulty="hard",
    io={"args": ["str", "str"], "returns": "str"},
    spec="""
`version_bump` raises one component of a `MAJOR.MINOR.PATCH` version.

- `part` is "major", "minor", or "patch".
- Raising a component **resets every component below it to zero**: bumping the
  major of 1.2.3 gives 2.0.0, and bumping its minor gives 1.3.0.
- Bumping the patch leaves major and minor alone.
- Return the empty string for anything invalid: a version that is not exactly
  three non-empty runs of digits, or an unknown `part`.
""",
    signatures={
        "python": "def version_bump(version: str, part: str) -> str:",
        "typescript": "function versionBump(version: string, part: string): string {",
        "go": "func VersionBump(version string, part string) string {",
        "rust": "fn version_bump(version: &str, part: &str) -> String {",
    },
    inputs=[
        ["1.2.3", "major"],
        ["1.2.0", "major"],
        ["1.2.3", "minor"],
        ["1.2.3", "patch"],
        ["0.0.0", "major"],
        ["1.2", "patch"],
        ["1.2.3", "build"],
        ["a.b.c", "major"],
        ["10.4.9", "minor"],
        ["1..3", "patch"],
    ],
    reference=version_bump,
    extras={
        "symptom": (
            "Release tags come out wrong, but only for releases cut from a "
            "version with patch releases behind it. Bumping the major of 1.2.0 "
            "correctly gives 2.0.0, while bumping the major of 1.2.3 gives "
            "2.0.3 and the tag collides with an old build."
        )
    },
    lang_extras={
        "python": {"buggy_code": dedent_code('''
            def version_bump(version: str, part: str) -> str:
                fields = version.split(".")
                if len(fields) != 3:
                    return ""
                numbers = []
                for field in fields:
                    if not field:
                        return ""
                    for ch in field:
                        if ch < "0" or ch > "9":
                            return ""
                    numbers.append(int(field))
                major, minor, patch = numbers
                if part == "major":
                    return f"{major + 1}.0.{patch}"
                if part == "minor":
                    return f"{major}.{minor + 1}.{patch}"
                if part == "patch":
                    return f"{major}.{minor}.{patch + 1}"
                return ""
        ''')},
        "typescript": {"buggy_code": dedent_code('''
            function versionBump(version: string, part: string): string {
                const fields = version.split(".");
                if (fields.length !== 3) return "";
                const numbers: number[] = [];
                for (const field of fields) {
                    if (field.length === 0 || !/^[0-9]+$/.test(field)) return "";
                    numbers.push(parseInt(field, 10));
                }
                const [major, minor, patch] = numbers;
                if (part === "major") return `${major + 1}.0.${patch}`;
                if (part === "minor") return `${major}.${minor + 1}.${patch}`;
                if (part === "patch") return `${major}.${minor}.${patch + 1}`;
                return "";
            }
        ''')},
        "go": {"buggy_code": dedent_code('''
            import (
                "fmt"
                "strconv"
                "strings"
            )

            func VersionBump(version string, part string) string {
                fields := strings.Split(version, ".")
                if len(fields) != 3 {
                    return ""
                }
                numbers := make([]int, 0, 3)
                for _, field := range fields {
                    if len(field) == 0 {
                        return ""
                    }
                    for _, ch := range field {
                        if ch < '0' || ch > '9' {
                            return ""
                        }
                    }
                    value, err := strconv.Atoi(field)
                    if err != nil {
                        return ""
                    }
                    numbers = append(numbers, value)
                }
                major, minor, patch := numbers[0], numbers[1], numbers[2]
                switch part {
                case "major":
                    return fmt.Sprintf("%d.0.%d", major+1, patch)
                case "minor":
                    return fmt.Sprintf("%d.%d.%d", major, minor+1, patch)
                case "patch":
                    return fmt.Sprintf("%d.%d.%d", major, minor, patch+1)
                }
                return ""
            }
        ''')},
        "rust": {"buggy_code": dedent_code('''
            fn version_bump(version: &str, part: &str) -> String {
                let fields: Vec<&str> = version.split('.').collect();
                if fields.len() != 3 {
                    return String::new();
                }
                let mut numbers: Vec<i64> = Vec::with_capacity(3);
                for field in fields {
                    if field.is_empty() || !field.chars().all(|c| c.is_ascii_digit()) {
                        return String::new();
                    }
                    match field.parse::<i64>() {
                        Ok(value) => numbers.push(value),
                        Err(_) => return String::new(),
                    }
                }
                let (major, minor, patch) = (numbers[0], numbers[1], numbers[2]);
                match part {
                    "major" => format!("{}.0.{}", major + 1, patch),
                    "minor" => format!("{}.{}.{}", major, minor + 1, patch),
                    "patch" => format!("{}.{}.{}", major, minor, patch + 1),
                    _ => String::new(),
                }
            }
        ''')},
    },
    solutions={
        "python": dedent_code('''
            def version_bump(version: str, part: str) -> str:
                fields = version.split(".")
                if len(fields) != 3:
                    return ""
                numbers = []
                for field in fields:
                    if not field:
                        return ""
                    for ch in field:
                        if ch < "0" or ch > "9":
                            return ""
                    numbers.append(int(field))
                major, minor, patch = numbers
                if part == "major":
                    return f"{major + 1}.0.0"
                if part == "minor":
                    return f"{major}.{minor + 1}.0"
                if part == "patch":
                    return f"{major}.{minor}.{patch + 1}"
                return ""
        '''),
        "typescript": dedent_code('''
            export function versionBump(version: string, part: string): string {
                const fields = version.split(".");
                if (fields.length !== 3) return "";
                const numbers: number[] = [];
                for (const field of fields) {
                    if (field.length === 0 || !/^[0-9]+$/.test(field)) return "";
                    numbers.push(parseInt(field, 10));
                }
                const [major, minor, patch] = numbers;
                if (part === "major") return `${major + 1}.0.0`;
                if (part === "minor") return `${major}.${minor + 1}.0`;
                if (part === "patch") return `${major}.${minor}.${patch + 1}`;
                return "";
            }
        '''),
        "go": dedent_code('''
            package main

            import (
                "fmt"
                "strconv"
                "strings"
            )

            func VersionBump(version string, part string) string {
                fields := strings.Split(version, ".")
                if len(fields) != 3 {
                    return ""
                }
                numbers := make([]int, 0, 3)
                for _, field := range fields {
                    if len(field) == 0 {
                        return ""
                    }
                    for _, ch := range field {
                        if ch < '0' || ch > '9' {
                            return ""
                        }
                    }
                    value, err := strconv.Atoi(field)
                    if err != nil {
                        return ""
                    }
                    numbers = append(numbers, value)
                }
                major, minor, patch := numbers[0], numbers[1], numbers[2]
                switch part {
                case "major":
                    return fmt.Sprintf("%d.0.0", major+1)
                case "minor":
                    return fmt.Sprintf("%d.%d.0", major, minor+1)
                case "patch":
                    return fmt.Sprintf("%d.%d.%d", major, minor, patch+1)
                }
                return ""
            }
        '''),
        "rust": dedent_code('''
            fn version_bump(version: &str, part: &str) -> String {
                let fields: Vec<&str> = version.split('.').collect();
                if fields.len() != 3 {
                    return String::new();
                }
                let mut numbers: Vec<i64> = Vec::with_capacity(3);
                for field in fields {
                    if field.is_empty() || !field.chars().all(|c| c.is_ascii_digit()) {
                        return String::new();
                    }
                    match field.parse::<i64>() {
                        Ok(value) => numbers.push(value),
                        Err(_) => return String::new(),
                    }
                }
                let (major, minor, patch) = (numbers[0], numbers[1], numbers[2]);
                match part {
                    "major" => format!("{}.0.0", major + 1),
                    "minor" => format!("{}.{}.0", major, minor + 1),
                    "patch" => format!("{}.{}.{}", major, minor, patch + 1),
                    _ => String::new(),
                }
            }
        '''),
    },
)


CSV_FIELD = Family(
    name="csv_field",
    skill="escaping",
    difficulty="hard",
    io={"args": ["str"], "returns": "str"},
    spec="""
`csv_field` renders one value as an RFC 4180 CSV field.

- A field containing a comma, a double quote, or a newline must be wrapped in
  double quotes.
- Inside a quoted field, every double quote in the value is written **twice**,
  so the three-character value  a"b  is rendered as the five-character field
  "a""b" — an opening quote, `a`, the inner quote written twice, `b`, and a
  closing quote.
- A field with none of those characters is returned unchanged, without quotes.
- The empty string is returned unchanged.
""",
    signatures={
        "python": "def csv_field(text: str) -> str:",
        "typescript": "function csvField(text: string): string {",
        "go": "func CsvField(text string) string {",
        "rust": "fn csv_field(text: &str) -> String {",
    },
    inputs=[
        "plain",
        "a,b",
        'say "hi"',
        '"',
        "",
        "line\nbreak",
        "tab\there",
        'x"y,z',
        "trailing,",
        'only"quote',
    ],
    reference=csv_field,
    extras={
        "symptom": (
            "Downstream parsers choke on our exports, but only on rows where a "
            "field contains a double quote — a product name like 24\" Monitor "
            "shifts every following column by one. Fields with commas or "
            "newlines round-trip fine."
        )
    },
    lang_extras={
        "python": {"buggy_code": dedent_code('''
            def csv_field(text: str) -> str:
                if "," in text or '"' in text or "\\n" in text:
                    return '"' + text + '"'
                return text
        ''')},
        "typescript": {"buggy_code": dedent_code('''
            function csvField(text: string): string {
                if (text.includes(",") || text.includes('"') || text.includes("\\n")) {
                    return '"' + text + '"';
                }
                return text;
            }
        ''')},
        "go": {"buggy_code": dedent_code('''
            import "strings"

            func CsvField(text string) string {
                if strings.ContainsAny(text, ",\\"\\n") {
                    return "\\"" + text + "\\""
                }
                return text
            }
        ''')},
        "rust": {"buggy_code": dedent_code('''
            fn csv_field(text: &str) -> String {
                if text.contains(',') || text.contains('"') || text.contains('\\n') {
                    return format!("\\"{}\\"", text);
                }
                text.to_string()
            }
        ''')},
    },
    solutions={
        "python": dedent_code('''
            def csv_field(text: str) -> str:
                if "," in text or '"' in text or "\\n" in text:
                    return '"' + text.replace('"', '""') + '"'
                return text
        '''),
        "typescript": dedent_code('''
            export function csvField(text: string): string {
                if (text.includes(",") || text.includes('"') || text.includes("\\n")) {
                    return '"' + text.split('"').join('""') + '"';
                }
                return text;
            }
        '''),
        "go": dedent_code('''
            package main

            import "strings"

            func CsvField(text string) string {
                if strings.ContainsAny(text, ",\\"\\n") {
                    return "\\"" + strings.ReplaceAll(text, "\\"", "\\"\\"") + "\\""
                }
                return text
            }
        '''),
        "rust": dedent_code('''
            fn csv_field(text: &str) -> String {
                if text.contains(',') || text.contains('"') || text.contains('\\n') {
                    return format!("\\"{}\\"", text.replace('"', "\\"\\""));
                }
                text.to_string()
            }
        '''),
    },
)


PARSE_SIZE = Family(
    name="parse_size",
    skill="units",
    difficulty="hard",
    io={"args": ["str"], "returns": "int"},
    spec="""
`parse_size` reads a Kubernetes-style resource quantity and returns the number
of bytes.

- The value is a run of digits followed by an optional suffix.
- Suffixes without an `i` are **decimal** powers of 1000: K = 1000,
  M = 1000000, G = 1000000000.
- Suffixes ending in `i` are **binary** powers of 1024: Ki = 1024,
  Mi = 1048576, Gi = 1073741824.
- No suffix means plain bytes.
- Return -1 for anything else: an empty string, a value with no leading digits,
  or an unrecognised suffix.
""",
    signatures={
        "python": "def parse_size(text: str) -> int:",
        "typescript": "function parseSize(text: string): number {",
        "go": "func ParseSize(text string) int {",
        "rust": "fn parse_size(text: &str) -> i64 {",
    },
    inputs=[
        "10",
        "5Ki",
        "5K",
        "2Mi",
        "2M",
        "1Gi",
        "7G",
        "",
        "3T",
        "abc",
        "512",
        "0K",
    ],
    reference=parse_size,
    extras={
        "symptom": (
            "Memory limits are provisioned slightly too high and the cluster "
            "autoscaler over-allocates. A limit written as 512Mi comes out "
            "exactly right, but the same limit written as 512M comes out about "
            "5% larger than the number of bytes it should mean."
        )
    },
    lang_extras={
        "python": {"buggy_code": dedent_code('''
            _UNITS = {
                "": 1,
                "K": 1024,
                "Ki": 1024,
                "M": 1048576,
                "Mi": 1048576,
                "G": 1073741824,
                "Gi": 1073741824,
            }


            def parse_size(text: str) -> int:
                end = 0
                while end < len(text) and "0" <= text[end] <= "9":
                    end += 1
                if end == 0:
                    return -1
                suffix = text[end:]
                if suffix not in _UNITS:
                    return -1
                return int(text[:end]) * _UNITS[suffix]
        ''')},
        "typescript": {"buggy_code": dedent_code('''
            const UNITS: Record<string, number> = {
                "": 1,
                K: 1024,
                Ki: 1024,
                M: 1048576,
                Mi: 1048576,
                G: 1073741824,
                Gi: 1073741824,
            };

            function parseSize(text: string): number {
                let end = 0;
                while (end < text.length && text[end] >= "0" && text[end] <= "9") end++;
                if (end === 0) return -1;
                const suffix = text.slice(end);
                if (!Object.prototype.hasOwnProperty.call(UNITS, suffix)) return -1;
                return parseInt(text.slice(0, end), 10) * UNITS[suffix];
            }
        ''')},
        "go": {"buggy_code": dedent_code('''
            import "strconv"

            func ParseSize(text string) int {
                units := map[string]int{
                    "":   1,
                    "K":  1024,
                    "Ki": 1024,
                    "M":  1048576,
                    "Mi": 1048576,
                    "G":  1073741824,
                    "Gi": 1073741824,
                }
                end := 0
                for end < len(text) && text[end] >= '0' && text[end] <= '9' {
                    end++
                }
                if end == 0 {
                    return -1
                }
                scale, ok := units[text[end:]]
                if !ok {
                    return -1
                }
                value, err := strconv.Atoi(text[:end])
                if err != nil {
                    return -1
                }
                return value * scale
            }
        ''')},
        "rust": {"buggy_code": dedent_code('''
            fn parse_size(text: &str) -> i64 {
                let bytes = text.as_bytes();
                let mut end = 0usize;
                while end < bytes.len() && bytes[end].is_ascii_digit() {
                    end += 1;
                }
                if end == 0 {
                    return -1;
                }
                let scale: i64 = match &text[end..] {
                    "" => 1,
                    "K" => 1024,
                    "Ki" => 1024,
                    "M" => 1048576,
                    "Mi" => 1048576,
                    "G" => 1073741824,
                    "Gi" => 1073741824,
                    _ => return -1,
                };
                match text[..end].parse::<i64>() {
                    Ok(value) => value * scale,
                    Err(_) => -1,
                }
            }
        ''')},
    },
    solutions={
        "python": dedent_code('''
            _UNITS = {
                "": 1,
                "K": 1000,
                "Ki": 1024,
                "M": 1000000,
                "Mi": 1048576,
                "G": 1000000000,
                "Gi": 1073741824,
            }


            def parse_size(text: str) -> int:
                end = 0
                while end < len(text) and "0" <= text[end] <= "9":
                    end += 1
                if end == 0:
                    return -1
                suffix = text[end:]
                if suffix not in _UNITS:
                    return -1
                return int(text[:end]) * _UNITS[suffix]
        '''),
        "typescript": dedent_code('''
            const UNITS: Record<string, number> = {
                "": 1,
                K: 1000,
                Ki: 1024,
                M: 1000000,
                Mi: 1048576,
                G: 1000000000,
                Gi: 1073741824,
            };

            export function parseSize(text: string): number {
                let end = 0;
                while (end < text.length && text[end] >= "0" && text[end] <= "9") end++;
                if (end === 0) return -1;
                const suffix = text.slice(end);
                if (!Object.prototype.hasOwnProperty.call(UNITS, suffix)) return -1;
                return parseInt(text.slice(0, end), 10) * UNITS[suffix];
            }
        '''),
        "go": dedent_code('''
            package main

            import "strconv"

            func ParseSize(text string) int {
                units := map[string]int{
                    "":   1,
                    "K":  1000,
                    "Ki": 1024,
                    "M":  1000000,
                    "Mi": 1048576,
                    "G":  1000000000,
                    "Gi": 1073741824,
                }
                end := 0
                for end < len(text) && text[end] >= '0' && text[end] <= '9' {
                    end++
                }
                if end == 0 {
                    return -1
                }
                scale, ok := units[text[end:]]
                if !ok {
                    return -1
                }
                value, err := strconv.Atoi(text[:end])
                if err != nil {
                    return -1
                }
                return value * scale
            }
        '''),
        "rust": dedent_code('''
            fn parse_size(text: &str) -> i64 {
                let bytes = text.as_bytes();
                let mut end = 0usize;
                while end < bytes.len() && bytes[end].is_ascii_digit() {
                    end += 1;
                }
                if end == 0 {
                    return -1;
                }
                let scale: i64 = match &text[end..] {
                    "" => 1,
                    "K" => 1000,
                    "Ki" => 1024,
                    "M" => 1000000,
                    "Mi" => 1048576,
                    "G" => 1000000000,
                    "Gi" => 1073741824,
                    _ => return -1,
                };
                match text[..end].parse::<i64>() {
                    Ok(value) => value * scale,
                    Err(_) => -1,
                }
            }
        '''),
    },
)


ADVANCED_FAMILIES = [
    LOWER_BOUND,
    PARSE_DURATION,
    COVERED_SECONDS,
    LUHN_VALID,
    IP_IN_CIDR,
    SLIDING_RATE_LIMIT,
    COUNTER_INCREASE,
    VERSION_BUMP,
    CSV_FIELD,
    PARSE_SIZE,
]
