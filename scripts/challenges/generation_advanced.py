"""Harder code_generation families.

Same contract as ``generation.py``: a spec, a required signature, and hidden
tests generated from a Python reference.

What makes these harder is that the difficulty lives in the specification, not
only in the algorithm. Each one states rules that a plausible implementation
gets wrong — a wildcard that must also match the empty string, `^0.2.3` ranging
differently from `^1.2.3`, integer division truncating toward zero rather than
down, a percent-escape whose decoded output must not be decoded again. The
hidden tests aim squarely at those clauses, so "wrote the well-known algorithm"
and "implemented what the spec actually says" come apart.
"""

from __future__ import annotations

from .common import Family, dedent_code

# ---------------------------------------------------------------------------
# Reference implementations
# ---------------------------------------------------------------------------


def glob_match(pattern: str, text: str) -> bool:
    p = 0
    t = 0
    star = -1
    mark = 0
    while t < len(text):
        if p < len(pattern) and (pattern[p] == "?" or pattern[p] == text[t]):
            p += 1
            t += 1
        elif p < len(pattern) and pattern[p] == "*":
            star = p
            mark = t
            p += 1
        elif star != -1:
            p = star + 1
            mark += 1
            t = mark
        else:
            return False
    while p < len(pattern) and pattern[p] == "*":
        p += 1
    return p == len(pattern)


def _all_digits(text: str) -> bool:
    if not text:
        return False
    for ch in text:
        if ch < "0" or ch > "9":
            return False
    return True


def cron_field_matches(field: str, value: int) -> bool:
    if not field:
        return False
    for part in field.split(","):
        if not part:
            return False
        body = part
        step = 1
        if "/" in part:
            body, _, step_text = part.partition("/")
            if not _all_digits(step_text):
                return False
            step = int(step_text)
            if step <= 0:
                return False
        if body == "*":
            if value % step == 0:
                return True
            continue
        if "-" in body:
            low_text, _, high_text = body.partition("-")
            if not _all_digits(low_text) or not _all_digits(high_text):
                return False
            low, high = int(low_text), int(high_text)
            if low > high:
                return False
        elif _all_digits(body):
            low = high = int(body)
        else:
            return False
        if low <= value <= high and (value - low) % step == 0:
            return True
    return False


def _signed_int(text: str) -> int | None:
    body = text[1:] if text.startswith("-") else text
    if not _all_digits(body):
        return None
    return -int(body) if text.startswith("-") else int(body)


def expand_ranges(text: str) -> list[int]:
    if text == "":
        return []
    out: list[int] = []
    for piece in text.split(","):
        if piece == "":
            return []
        cut = -1
        for i in range(1, len(piece)):
            if piece[i] == "-" and piece[i - 1] != "-":
                cut = i
                break
        if cut == -1:
            value = _signed_int(piece)
            if value is None:
                return []
            out.append(value)
            continue
        low = _signed_int(piece[:cut])
        high = _signed_int(piece[cut + 1:])
        if low is None or high is None or low > high:
            return []
        for value in range(low, high + 1):
            out.append(value)
    return out


def wrap_text(text: str, width: int) -> list[str]:
    if width <= 0:
        return []
    lines: list[str] = []
    current = ""
    for word in text.split(" "):
        if word == "":
            continue
        if current == "":
            current = word
        elif len(current) + 1 + len(word) <= width:
            current = current + " " + word
        else:
            lines.append(current)
            current = word
    if current != "":
        lines.append(current)
    return lines


def topological_order(nodes: list[str], before: list[str], after: list[str]) -> list[str]:
    known = set(nodes)
    indegree = {node: 0 for node in nodes}
    edges: dict[str, list[str]] = {node: [] for node in nodes}
    seen: set[tuple[str, str]] = set()
    for i in range(min(len(before), len(after))):
        source, target = before[i], after[i]
        if source not in known or target not in known or (source, target) in seen:
            continue
        seen.add((source, target))
        edges[source].append(target)
        indegree[target] += 1
    available = sorted(node for node in nodes if indegree[node] == 0)
    out: list[str] = []
    while available:
        node = available.pop(0)
        out.append(node)
        for target in edges[node]:
            indegree[target] -= 1
            if indegree[target] == 0:
                available.append(target)
        available.sort()
    return out if len(out) == len(nodes) else []


def _trunc_div(a: int, b: int) -> int:
    quotient = abs(a) // abs(b)
    return -quotient if (a < 0) != (b < 0) else quotient


def evaluate_expression(text: str) -> str:
    tokens: list[str] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == " ":
            i += 1
        elif "0" <= ch <= "9":
            j = i
            while j < len(text) and "0" <= text[j] <= "9":
                j += 1
            tokens.append(text[i:j])
            i = j
        elif ch in "+-*/()":
            tokens.append(ch)
            i += 1
        else:
            return ""

    pos = 0
    bad = False

    def peek() -> str:
        return tokens[pos] if pos < len(tokens) else ""

    def factor() -> int:
        nonlocal pos, bad
        token = peek()
        if token == "(":
            pos += 1
            value = expression()
            if bad or peek() != ")":
                bad = True
                return 0
            pos += 1
            return value
        if token != "" and "0" <= token[0] <= "9":
            pos += 1
            return int(token)
        bad = True
        return 0

    def term() -> int:
        nonlocal pos, bad
        value = factor()
        while not bad and peek() in ("*", "/"):
            operator = peek()
            pos += 1
            right = factor()
            if bad:
                return 0
            if operator == "*":
                value = value * right
            elif right == 0:
                bad = True
                return 0
            else:
                value = _trunc_div(value, right)
        return value

    def expression() -> int:
        nonlocal pos, bad
        value = term()
        while not bad and peek() in ("+", "-"):
            operator = peek()
            pos += 1
            right = term()
            if bad:
                return 0
            value = value + right if operator == "+" else value - right
        return value

    result = expression()
    if bad or pos != len(tokens) or not tokens:
        return ""
    return str(result)


def route_params(pattern: str, path: str) -> str:
    pattern_parts = pattern.split("/")
    path_parts = path.split("/")
    if len(pattern_parts) != len(path_parts):
        return "no-match"
    pairs: list[str] = []
    for index in range(len(pattern_parts)):
        expected = pattern_parts[index]
        actual = path_parts[index]
        if expected.startswith(":") and len(expected) > 1:
            if actual == "":
                return "no-match"
            pairs.append(expected[1:] + "=" + actual)
        elif expected != actual:
            return "no-match"
    return ";".join(pairs) if pairs else "no-params"


def _semver(text: str) -> tuple[int, int, int] | None:
    fields = text.split(".")
    if len(fields) != 3:
        return None
    for field in fields:
        if not _all_digits(field):
            return None
    return int(fields[0]), int(fields[1]), int(fields[2])


def semver_satisfies(version: str, constraint: str) -> bool:
    current = _semver(version)
    if current is None:
        return False
    if constraint == "*":
        return True
    for prefix in (">=", "<=", ">", "<"):
        if constraint.startswith(prefix):
            target = _semver(constraint[len(prefix):])
            if target is None:
                return False
            if prefix == ">=":
                return current >= target
            if prefix == "<=":
                return current <= target
            if prefix == ">":
                return current > target
            return current < target
    if constraint.startswith("^"):
        target = _semver(constraint[1:])
        if target is None:
            return False
        major, minor, _patch = target
        if major > 0:
            upper = (major + 1, 0, 0)
        elif minor > 0:
            upper = (0, minor + 1, 0)
        else:
            upper = (0, 0, target[2] + 1)
        return target <= current < upper
    if constraint.startswith("~"):
        target = _semver(constraint[1:])
        if target is None:
            return False
        upper = (target[0], target[1] + 1, 0)
        return target <= current < upper
    exact = _semver(constraint)
    return exact is not None and current == exact


def tokenize_command(text: str) -> list[str]:
    out: list[str] = []
    current = ""
    started = False
    quoted = False
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\\":
            if i + 1 >= len(text):
                return []
            current += text[i + 1]
            started = True
            i += 2
        elif ch == '"':
            quoted = not quoted
            started = True
            i += 1
        elif ch == " " and not quoted:
            if started:
                out.append(current)
                current = ""
                started = False
            i += 1
        else:
            current += ch
            started = True
            i += 1
    if quoted:
        return []
    if started:
        out.append(current)
    return out


def _is_hex(ch: str) -> bool:
    return ("0" <= ch <= "9") or ("a" <= ch <= "f") or ("A" <= ch <= "F")


def percent_decode(text: str) -> str:
    out = ""
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "+":
            out += " "
            i += 1
            continue
        if ch == "%" and i + 2 < len(text) and _is_hex(text[i + 1]) and _is_hex(text[i + 2]):
            code = int(text[i + 1:i + 3], 16)
            if 0x20 <= code <= 0x7E:
                out += chr(code)
                i += 3
                continue
        out += ch
        i += 1
    return out


# ---------------------------------------------------------------------------
# Families
# ---------------------------------------------------------------------------

GLOB_MATCH = Family(
    name="glob_match",
    skill="pattern_matching",
    difficulty="hard",
    io={"args": ["str", "str"], "returns": "bool"},
    spec="""
Decide whether a glob pattern matches a string, the way a log-file or path
filter does.

Rules:
- `*` matches any run of characters, **including an empty one**, so "a*c"
  matches "ac" as well as "abbbc".
- `?` matches exactly one character, and never zero, so "a?c" does not match
  "ac".
- Every other character matches only itself. There are no character classes and
  no escaping — a `*` in the pattern is always a wildcard.
- The pattern must match the *whole* string, not a prefix: "*.log" does not
  match "app.log.gz".
- An empty pattern matches only the empty string, and a pattern of only stars
  matches anything.
""",
    signatures={
        "python": "def glob_match(pattern: str, text: str) -> bool:",
        "typescript": "function globMatch(pattern: string, text: string): boolean {",
        "go": "func GlobMatch(pattern string, text string) bool {",
        "rust": "fn glob_match(pattern: &str, text: &str) -> bool {",
    },
    inputs=[
        ["", ""],
        ["", "a"],
        ["*", ""],
        ["?", ""],
        ["a*c", "abc"],
        ["a*c", "ac"],
        ["a*c", "abcd"],
        ["*.log", "app.log"],
        ["*.log", "app.log.gz"],
        ["a?c", "abc"],
        ["a?c", "ac"],
        ["**", "anything"],
        ["*x*", "axb"],
        ["*x*", "ab"],
        ["abc", "abc"],
        ["abc", "abd"],
        ["*a*b*c*", "xxaxxbxxcxx"],
        ["*a*b*c*", "xxaxxcxxbxx"],
    ],
    reference=glob_match,
    solutions={
        "python": dedent_code('''
            def glob_match(pattern: str, text: str) -> bool:
                p = 0
                t = 0
                star = -1
                mark = 0
                while t < len(text):
                    if p < len(pattern) and (pattern[p] == "?" or pattern[p] == text[t]):
                        p += 1
                        t += 1
                    elif p < len(pattern) and pattern[p] == "*":
                        star = p
                        mark = t
                        p += 1
                    elif star != -1:
                        p = star + 1
                        mark += 1
                        t = mark
                    else:
                        return False
                while p < len(pattern) and pattern[p] == "*":
                    p += 1
                return p == len(pattern)
        '''),
        "typescript": dedent_code('''
            export function globMatch(pattern: string, text: string): boolean {
                let p = 0;
                let t = 0;
                let star = -1;
                let mark = 0;
                while (t < text.length) {
                    if (p < pattern.length && (pattern[p] === "?" || pattern[p] === text[t])) {
                        p++;
                        t++;
                    } else if (p < pattern.length && pattern[p] === "*") {
                        star = p;
                        mark = t;
                        p++;
                    } else if (star !== -1) {
                        p = star + 1;
                        mark++;
                        t = mark;
                    } else {
                        return false;
                    }
                }
                while (p < pattern.length && pattern[p] === "*") p++;
                return p === pattern.length;
            }
        '''),
        "go": dedent_code('''
            package main

            func GlobMatch(pattern string, text string) bool {
                p, t, star, mark := 0, 0, -1, 0
                for t < len(text) {
                    if p < len(pattern) && (pattern[p] == '?' || pattern[p] == text[t]) {
                        p++
                        t++
                    } else if p < len(pattern) && pattern[p] == '*' {
                        star = p
                        mark = t
                        p++
                    } else if star != -1 {
                        p = star + 1
                        mark++
                        t = mark
                    } else {
                        return false
                    }
                }
                for p < len(pattern) && pattern[p] == '*' {
                    p++
                }
                return p == len(pattern)
            }
        '''),
        "rust": dedent_code('''
            fn glob_match(pattern: &str, text: &str) -> bool {
                let pattern: Vec<char> = pattern.chars().collect();
                let text: Vec<char> = text.chars().collect();
                let mut p = 0usize;
                let mut t = 0usize;
                let mut star: i64 = -1;
                let mut mark = 0usize;
                while t < text.len() {
                    if p < pattern.len() && (pattern[p] == '?' || pattern[p] == text[t]) {
                        p += 1;
                        t += 1;
                    } else if p < pattern.len() && pattern[p] == '*' {
                        star = p as i64;
                        mark = t;
                        p += 1;
                    } else if star != -1 {
                        p = (star + 1) as usize;
                        mark += 1;
                        t = mark;
                    } else {
                        return false;
                    }
                }
                while p < pattern.len() && pattern[p] == '*' {
                    p += 1;
                }
                p == pattern.len()
            }
        '''),
    },
)


CRON_FIELD_MATCHES = Family(
    name="cron_field_matches",
    skill="parsing",
    difficulty="hard",
    io={"args": ["str", "int"], "returns": "bool"},
    spec="""
Decide whether a single cron field matches a value — the check a scheduler runs
once per field to see whether a job is due.

A field is a comma-separated list of terms, and the field matches when **any**
term matches. Each term is one of:

- `*` — matches every value.
- `N` — matches exactly N.
- `A-B` — matches A through B inclusive.
- any of the above followed by `/S` — a step. `*/S` matches values that are
  multiples of S. `A-B/S` matches values in A..B that are S apart *counting
  from A*, so "0-30/10" matches 0, 10, 20 and 30 but not 25.

Rules:
- `value` is zero or greater.
- The whole field is rejected — return false — if any term is malformed: an
  empty term, a non-numeric bound or step, a step of zero, or a range whose low
  bound is above its high bound. An empty field is also false.
- Numbers are plain decimal digits; there are no names, no `L`, no `?`.
""",
    signatures={
        "python": "def cron_field_matches(field: str, value: int) -> bool:",
        "typescript": "function cronFieldMatches(field: string, value: number): boolean {",
        "go": "func CronFieldMatches(field string, value int) bool {",
        "rust": "fn cron_field_matches(field: &str, value: i64) -> bool {",
    },
    inputs=[
        ["*", 5],
        ["*/15", 30],
        ["*/15", 31],
        ["5", 5],
        ["5", 6],
        ["0-6", 3],
        ["0-6", 7],
        ["0-30/10", 20],
        ["0-30/10", 25],
        ["1,3,5", 3],
        ["1,3,5", 4],
        ["", 0],
        ["a", 1],
        ["5-1", 3],
        ["*/0", 4],
        ["10-20", 20],
        ["1-10/3", 7],
        ["1-10/3", 8],
        ["0,10-20/5", 15],
    ],
    reference=cron_field_matches,
    solutions={
        "python": dedent_code('''
            def _digits(text: str) -> bool:
                if not text:
                    return False
                for ch in text:
                    if ch < "0" or ch > "9":
                        return False
                return True


            def cron_field_matches(field: str, value: int) -> bool:
                if not field:
                    return False
                for part in field.split(","):
                    if not part:
                        return False
                    body = part
                    step = 1
                    if "/" in part:
                        body, _, step_text = part.partition("/")
                        if not _digits(step_text):
                            return False
                        step = int(step_text)
                        if step <= 0:
                            return False
                    if body == "*":
                        if value % step == 0:
                            return True
                        continue
                    if "-" in body:
                        low_text, _, high_text = body.partition("-")
                        if not _digits(low_text) or not _digits(high_text):
                            return False
                        low, high = int(low_text), int(high_text)
                        if low > high:
                            return False
                    elif _digits(body):
                        low = high = int(body)
                    else:
                        return False
                    if low <= value <= high and (value - low) % step == 0:
                        return True
                return False
        '''),
        "typescript": dedent_code('''
            function digits(text: string): boolean {
                return text.length > 0 && /^[0-9]+$/.test(text);
            }

            export function cronFieldMatches(field: string, value: number): boolean {
                if (field.length === 0) return false;
                for (const part of field.split(",")) {
                    if (part.length === 0) return false;
                    let body = part;
                    let step = 1;
                    const slash = part.indexOf("/");
                    if (slash >= 0) {
                        body = part.slice(0, slash);
                        const stepText = part.slice(slash + 1);
                        if (!digits(stepText)) return false;
                        step = parseInt(stepText, 10);
                        if (step <= 0) return false;
                    }
                    if (body === "*") {
                        if (value % step === 0) return true;
                        continue;
                    }
                    let low: number;
                    let high: number;
                    const dash = body.indexOf("-");
                    if (dash >= 0) {
                        const lowText = body.slice(0, dash);
                        const highText = body.slice(dash + 1);
                        if (!digits(lowText) || !digits(highText)) return false;
                        low = parseInt(lowText, 10);
                        high = parseInt(highText, 10);
                        if (low > high) return false;
                    } else if (digits(body)) {
                        low = parseInt(body, 10);
                        high = low;
                    } else {
                        return false;
                    }
                    if (value >= low && value <= high && (value - low) % step === 0) return true;
                }
                return false;
            }
        '''),
        "go": dedent_code('''
            package main

            import (
                "strconv"
                "strings"
            )

            func cronDigits(text string) bool {
                if len(text) == 0 {
                    return false
                }
                for _, ch := range text {
                    if ch < '0' || ch > '9' {
                        return false
                    }
                }
                return true
            }

            func CronFieldMatches(field string, value int) bool {
                if len(field) == 0 {
                    return false
                }
                for _, part := range strings.Split(field, ",") {
                    if len(part) == 0 {
                        return false
                    }
                    body := part
                    step := 1
                    if slash := strings.Index(part, "/"); slash >= 0 {
                        body = part[:slash]
                        stepText := part[slash+1:]
                        if !cronDigits(stepText) {
                            return false
                        }
                        step, _ = strconv.Atoi(stepText)
                        if step <= 0 {
                            return false
                        }
                    }
                    if body == "*" {
                        if value%step == 0 {
                            return true
                        }
                        continue
                    }
                    var low, high int
                    if dash := strings.Index(body, "-"); dash >= 0 {
                        lowText := body[:dash]
                        highText := body[dash+1:]
                        if !cronDigits(lowText) || !cronDigits(highText) {
                            return false
                        }
                        low, _ = strconv.Atoi(lowText)
                        high, _ = strconv.Atoi(highText)
                        if low > high {
                            return false
                        }
                    } else if cronDigits(body) {
                        low, _ = strconv.Atoi(body)
                        high = low
                    } else {
                        return false
                    }
                    if value >= low && value <= high && (value-low)%step == 0 {
                        return true
                    }
                }
                return false
            }
        '''),
        "rust": dedent_code('''
            fn cron_digits(text: &str) -> bool {
                !text.is_empty() && text.chars().all(|c| c.is_ascii_digit())
            }

            fn cron_field_matches(field: &str, value: i64) -> bool {
                if field.is_empty() {
                    return false;
                }
                for part in field.split(',') {
                    if part.is_empty() {
                        return false;
                    }
                    let mut body = part;
                    let mut step: i64 = 1;
                    if let Some((head, step_text)) = part.split_once('/') {
                        if !cron_digits(step_text) {
                            return false;
                        }
                        step = step_text.parse().unwrap_or(0);
                        if step <= 0 {
                            return false;
                        }
                        body = head;
                    }
                    if body == "*" {
                        if value % step == 0 {
                            return true;
                        }
                        continue;
                    }
                    let (low, high) = match body.split_once('-') {
                        Some((low_text, high_text)) => {
                            if !cron_digits(low_text) || !cron_digits(high_text) {
                                return false;
                            }
                            let low: i64 = low_text.parse().unwrap_or(0);
                            let high: i64 = high_text.parse().unwrap_or(0);
                            if low > high {
                                return false;
                            }
                            (low, high)
                        }
                        None => {
                            if !cron_digits(body) {
                                return false;
                            }
                            let single: i64 = body.parse().unwrap_or(0);
                            (single, single)
                        }
                    };
                    if value >= low && value <= high && (value - low) % step == 0 {
                        return true;
                    }
                }
                false
            }
        '''),
    },
)


EXPAND_RANGES = Family(
    name="expand_ranges",
    skill="parsing",
    difficulty="hard",
    io={"args": ["str"], "returns": "list<int>"},
    spec="""
Expand a compact range list such as "1-3,5,7-9" back into the integers it
stands for: [1, 2, 3, 5, 7, 8, 9].

Rules:
- Terms are separated by commas and expand in the order written; nothing is
  sorted and nothing is de-duplicated.
- A term is either a single integer or `low-high`, which expands to every
  integer from low to high inclusive. `5-5` is just [5].
- Integers may be negative, which makes the separator ambiguous: in "-3--1" the
  separating dash is the one that is neither the first character of the term nor
  directly preceded by another dash. That term expands to [-3, -2, -1].
- The whole input is rejected — return an empty list — if any term is malformed:
  an empty term, something that is not an optionally-signed run of digits, or a
  range whose low bound is above its high bound.
- The empty string expands to an empty list.
""",
    signatures={
        "python": "def expand_ranges(text: str) -> list[int]:",
        "typescript": "function expandRanges(text: string): number[] {",
        "go": "func ExpandRanges(text string) []int {",
        "rust": "fn expand_ranges(text: &str) -> Vec<i64> {",
    },
    inputs=[
        "1-3,5,7-9",
        "",
        "4",
        "1-2",
        "-3--1,4",
        "5-5",
        "3-1",
        "a",
        "1,,2",
        "1-",
        "0",
        "10-11,13-14",
        "-5",
        "2,2,2",
    ],
    reference=expand_ranges,
    solutions={
        "python": dedent_code('''
            def _signed(text: str):
                body = text[1:] if text.startswith("-") else text
                if not body:
                    return None
                for ch in body:
                    if ch < "0" or ch > "9":
                        return None
                return -int(body) if text.startswith("-") else int(body)


            def expand_ranges(text: str) -> list[int]:
                if text == "":
                    return []
                out = []
                for piece in text.split(","):
                    if piece == "":
                        return []
                    cut = -1
                    for i in range(1, len(piece)):
                        if piece[i] == "-" and piece[i - 1] != "-":
                            cut = i
                            break
                    if cut == -1:
                        value = _signed(piece)
                        if value is None:
                            return []
                        out.append(value)
                        continue
                    low = _signed(piece[:cut])
                    high = _signed(piece[cut + 1:])
                    if low is None or high is None or low > high:
                        return []
                    for value in range(low, high + 1):
                        out.append(value)
                return out
        '''),
        "typescript": dedent_code('''
            function signed(text: string): number | null {
                const negative = text.startsWith("-");
                const body = negative ? text.slice(1) : text;
                if (body.length === 0 || !/^[0-9]+$/.test(body)) return null;
                const value = parseInt(body, 10);
                return negative ? -value : value;
            }

            export function expandRanges(text: string): number[] {
                if (text === "") return [];
                const out: number[] = [];
                for (const piece of text.split(",")) {
                    if (piece === "") return [];
                    let cut = -1;
                    for (let i = 1; i < piece.length; i++) {
                        if (piece[i] === "-" && piece[i - 1] !== "-") {
                            cut = i;
                            break;
                        }
                    }
                    if (cut === -1) {
                        const value = signed(piece);
                        if (value === null) return [];
                        out.push(value);
                        continue;
                    }
                    const low = signed(piece.slice(0, cut));
                    const high = signed(piece.slice(cut + 1));
                    if (low === null || high === null || low > high) return [];
                    for (let value = low; value <= high; value++) out.push(value);
                }
                return out;
            }
        '''),
        "go": dedent_code('''
            package main

            import (
                "strconv"
                "strings"
            )

            func signedInt(text string) (int, bool) {
                body := text
                negative := strings.HasPrefix(text, "-")
                if negative {
                    body = text[1:]
                }
                if len(body) == 0 {
                    return 0, false
                }
                for _, ch := range body {
                    if ch < '0' || ch > '9' {
                        return 0, false
                    }
                }
                value, err := strconv.Atoi(body)
                if err != nil {
                    return 0, false
                }
                if negative {
                    return -value, true
                }
                return value, true
            }

            func ExpandRanges(text string) []int {
                out := []int{}
                if text == "" {
                    return out
                }
                for _, piece := range strings.Split(text, ",") {
                    if piece == "" {
                        return []int{}
                    }
                    cut := -1
                    for i := 1; i < len(piece); i++ {
                        if piece[i] == '-' && piece[i-1] != '-' {
                            cut = i
                            break
                        }
                    }
                    if cut == -1 {
                        value, ok := signedInt(piece)
                        if !ok {
                            return []int{}
                        }
                        out = append(out, value)
                        continue
                    }
                    low, okLow := signedInt(piece[:cut])
                    high, okHigh := signedInt(piece[cut+1:])
                    if !okLow || !okHigh || low > high {
                        return []int{}
                    }
                    for value := low; value <= high; value++ {
                        out = append(out, value)
                    }
                }
                return out
            }
        '''),
        "rust": dedent_code('''
            fn signed_int(text: &str) -> Option<i64> {
                let negative = text.starts_with('-');
                let body = if negative { &text[1..] } else { text };
                if body.is_empty() || !body.chars().all(|c| c.is_ascii_digit()) {
                    return None;
                }
                let value: i64 = body.parse().ok()?;
                Some(if negative { -value } else { value })
            }

            fn expand_ranges(text: &str) -> Vec<i64> {
                if text.is_empty() {
                    return Vec::new();
                }
                let mut out: Vec<i64> = Vec::new();
                for piece in text.split(',') {
                    if piece.is_empty() {
                        return Vec::new();
                    }
                    let bytes = piece.as_bytes();
                    let mut cut: i64 = -1;
                    for i in 1..bytes.len() {
                        if bytes[i] == b'-' && bytes[i - 1] != b'-' {
                            cut = i as i64;
                            break;
                        }
                    }
                    if cut == -1 {
                        match signed_int(piece) {
                            Some(value) => out.push(value),
                            None => return Vec::new(),
                        }
                        continue;
                    }
                    let cut = cut as usize;
                    let low = signed_int(&piece[..cut]);
                    let high = signed_int(&piece[cut + 1..]);
                    match (low, high) {
                        (Some(low), Some(high)) if low <= high => {
                            for value in low..=high {
                                out.push(value);
                            }
                        }
                        _ => return Vec::new(),
                    }
                }
                out
            }
        '''),
    },
)


WRAP_TEXT = Family(
    name="wrap_text",
    skill="text_layout",
    difficulty="hard",
    io={"args": ["str", "int"], "returns": "list<str>"},
    spec="""
Wrap a line of text into fixed-width lines, the way a terminal report does.

Rules:
- Words are the runs of non-space characters; runs of spaces separate them and
  are otherwise discarded, so leading, trailing and repeated spaces never reach
  the output.
- Fill greedily: keep adding the next word to the current line while the result,
  counting the single space that joins them, is at most `width`.
- A word longer than `width` is never broken. It goes on a line of its own,
  over-long, and wrapping continues after it.
- Words on a line are joined by exactly one space, and no line has leading or
  trailing spaces.
- Text with no words gives no lines, and a width of zero or less gives no lines.
""",
    signatures={
        "python": "def wrap_text(text: str, width: int) -> list[str]:",
        "typescript": "function wrapText(text: string, width: number): string[] {",
        "go": "func WrapText(text string, width int) []string {",
        "rust": "fn wrap_text(text: &str, width: i64) -> Vec<String> {",
    },
    inputs=[
        ["the quick brown fox", 10],
        ["", 10],
        ["   ", 10],
        ["supercalifragilistic", 5],
        ["a b c", 1],
        ["a b c", 3],
        ["hello world", 11],
        ["hello world", 10],
        ["one  two", 10],
        ["x", 0],
        ["alpha beta gamma delta", 12],
        ["  padded  words  here  ", 12],
        ["toolongword short", 6],
    ],
    reference=wrap_text,
    solutions={
        "python": dedent_code('''
            def wrap_text(text: str, width: int) -> list[str]:
                if width <= 0:
                    return []
                lines = []
                current = ""
                for word in text.split(" "):
                    if word == "":
                        continue
                    if current == "":
                        current = word
                    elif len(current) + 1 + len(word) <= width:
                        current = current + " " + word
                    else:
                        lines.append(current)
                        current = word
                if current != "":
                    lines.append(current)
                return lines
        '''),
        "typescript": dedent_code('''
            export function wrapText(text: string, width: number): string[] {
                if (width <= 0) return [];
                const lines: string[] = [];
                let current = "";
                for (const word of text.split(" ")) {
                    if (word === "") continue;
                    if (current === "") {
                        current = word;
                    } else if (current.length + 1 + word.length <= width) {
                        current = current + " " + word;
                    } else {
                        lines.push(current);
                        current = word;
                    }
                }
                if (current !== "") lines.push(current);
                return lines;
            }
        '''),
        "go": dedent_code('''
            package main

            import "strings"

            func WrapText(text string, width int) []string {
                lines := []string{}
                if width <= 0 {
                    return lines
                }
                current := ""
                for _, word := range strings.Split(text, " ") {
                    if word == "" {
                        continue
                    }
                    if current == "" {
                        current = word
                    } else if len(current)+1+len(word) <= width {
                        current = current + " " + word
                    } else {
                        lines = append(lines, current)
                        current = word
                    }
                }
                if current != "" {
                    lines = append(lines, current)
                }
                return lines
            }
        '''),
        "rust": dedent_code('''
            fn wrap_text(text: &str, width: i64) -> Vec<String> {
                let mut lines: Vec<String> = Vec::new();
                if width <= 0 {
                    return lines;
                }
                let width = width as usize;
                let mut current = String::new();
                for word in text.split(' ') {
                    if word.is_empty() {
                        continue;
                    }
                    if current.is_empty() {
                        current = word.to_string();
                    } else if current.len() + 1 + word.len() <= width {
                        current.push(' ');
                        current.push_str(word);
                    } else {
                        lines.push(current);
                        current = word.to_string();
                    }
                }
                if !current.is_empty() {
                    lines.push(current);
                }
                lines
            }
        '''),
    },
)


TOPOLOGICAL_ORDER = Family(
    name="topological_order",
    skill="graphs",
    difficulty="hard",
    io={"args": ["list<str>", "list<str>", "list<str>"], "returns": "list<str>"},
    spec="""
Order a set of tasks so every dependency runs before the task that needs it —
the order a deploy pipeline would execute its stages in.

- `nodes` holds the task names, which are distinct but in no particular order.
- `before` and `after` are parallel arrays describing edges: before[i] must come
  out ahead of after[i].
- Whenever more than one task is ready at the same time, take the
  **alphabetically smallest** one, so the answer is unique.
- An edge naming a task that is not in `nodes` is ignored. A repeated edge counts
  once.
- If the constraints cannot all be satisfied — any cycle, including a task that
  depends on itself — return an empty list.
- No tasks gives an empty list.
""",
    signatures={
        "python": (
            "def topological_order(nodes: list[str], before: list[str], "
            "after: list[str]) -> list[str]:"
        ),
        "typescript": (
            "function topologicalOrder(nodes: string[], before: string[], "
            "after: string[]): string[] {"
        ),
        "go": "func TopologicalOrder(nodes []string, before []string, after []string) []string {",
        "rust": (
            "fn topological_order(nodes: &[&str], before: &[&str], after: &[&str]) "
            "-> Vec<String> {"
        ),
    },
    inputs=[
        [["a", "b", "c"], ["a", "b"], ["b", "c"]],
        [["c", "b", "a"], [], []],
        [[], [], []],
        [["a", "b"], ["b"], ["a"]],
        [["a", "b"], ["a", "b"], ["b", "a"]],
        [["a"], ["a"], ["a"]],
        [["a", "b", "c"], ["c"], ["a"]],
        [["x", "y", "z"], ["x", "x"], ["y", "z"]],
        [["a", "b", "c", "d"], ["a", "a"], ["b", "c"]],
        [["a", "b"], ["z"], ["a"]],
        [["build", "test", "deploy"], ["build", "test"], ["test", "deploy"]],
        [["a", "b", "c"], ["a", "a"], ["b", "b"]],
    ],
    reference=topological_order,
    solutions={
        "python": dedent_code('''
            def topological_order(nodes: list[str], before: list[str], after: list[str]) -> list[str]:
                known = set(nodes)
                indegree = {node: 0 for node in nodes}
                edges = {node: [] for node in nodes}
                seen = set()
                for i in range(min(len(before), len(after))):
                    source, target = before[i], after[i]
                    if source not in known or target not in known:
                        continue
                    if (source, target) in seen:
                        continue
                    seen.add((source, target))
                    edges[source].append(target)
                    indegree[target] += 1
                available = sorted(node for node in nodes if indegree[node] == 0)
                out = []
                while available:
                    node = available.pop(0)
                    out.append(node)
                    for target in edges[node]:
                        indegree[target] -= 1
                        if indegree[target] == 0:
                            available.append(target)
                    available.sort()
                return out if len(out) == len(nodes) else []
        '''),
        "typescript": dedent_code('''
            export function topologicalOrder(
                nodes: string[],
                before: string[],
                after: string[],
            ): string[] {
                const known = new Set(nodes);
                const indegree = new Map<string, number>();
                const edges = new Map<string, string[]>();
                for (const node of nodes) {
                    indegree.set(node, 0);
                    edges.set(node, []);
                }
                const seen = new Set<string>();
                const count = Math.min(before.length, after.length);
                for (let i = 0; i < count; i++) {
                    const source = before[i];
                    const target = after[i];
                    if (!known.has(source) || !known.has(target)) continue;
                    const key = `${source}\\u0000${target}`;
                    if (seen.has(key)) continue;
                    seen.add(key);
                    (edges.get(source) as string[]).push(target);
                    indegree.set(target, (indegree.get(target) as number) + 1);
                }
                const available = nodes.filter((n) => indegree.get(n) === 0).sort();
                const out: string[] = [];
                while (available.length > 0) {
                    const node = available.shift() as string;
                    out.push(node);
                    for (const target of edges.get(node) as string[]) {
                        const left = (indegree.get(target) as number) - 1;
                        indegree.set(target, left);
                        if (left === 0) available.push(target);
                    }
                    available.sort();
                }
                return out.length === nodes.length ? out : [];
            }
        '''),
        "go": dedent_code('''
            package main

            import "sort"

            func TopologicalOrder(nodes []string, before []string, after []string) []string {
                known := map[string]bool{}
                indegree := map[string]int{}
                edges := map[string][]string{}
                for _, node := range nodes {
                    known[node] = true
                    indegree[node] = 0
                }
                seen := map[string]bool{}
                count := len(before)
                if len(after) < count {
                    count = len(after)
                }
                for i := 0; i < count; i++ {
                    source, target := before[i], after[i]
                    if !known[source] || !known[target] {
                        continue
                    }
                    key := source + "\\x00" + target
                    if seen[key] {
                        continue
                    }
                    seen[key] = true
                    edges[source] = append(edges[source], target)
                    indegree[target]++
                }
                available := []string{}
                for _, node := range nodes {
                    if indegree[node] == 0 {
                        available = append(available, node)
                    }
                }
                sort.Strings(available)
                out := []string{}
                for len(available) > 0 {
                    node := available[0]
                    available = available[1:]
                    out = append(out, node)
                    for _, target := range edges[node] {
                        indegree[target]--
                        if indegree[target] == 0 {
                            available = append(available, target)
                        }
                    }
                    sort.Strings(available)
                }
                if len(out) != len(nodes) {
                    return []string{}
                }
                return out
            }
        '''),
        "rust": dedent_code('''
            use std::collections::{HashMap, HashSet};

            fn topological_order(nodes: &[&str], before: &[&str], after: &[&str]) -> Vec<String> {
                let known: HashSet<&str> = nodes.iter().copied().collect();
                let mut indegree: HashMap<&str, i64> = nodes.iter().map(|&n| (n, 0)).collect();
                let mut edges: HashMap<&str, Vec<&str>> =
                    nodes.iter().map(|&n| (n, Vec::new())).collect();
                let mut seen: HashSet<(&str, &str)> = HashSet::new();
                let count = before.len().min(after.len());
                for i in 0..count {
                    let (source, target) = (before[i], after[i]);
                    if !known.contains(source) || !known.contains(target) {
                        continue;
                    }
                    if !seen.insert((source, target)) {
                        continue;
                    }
                    edges.get_mut(source).unwrap().push(target);
                    *indegree.get_mut(target).unwrap() += 1;
                }
                let mut available: Vec<&str> = nodes
                    .iter()
                    .copied()
                    .filter(|n| indegree[n] == 0)
                    .collect();
                available.sort_unstable();
                let mut out: Vec<String> = Vec::new();
                while !available.is_empty() {
                    let node = available.remove(0);
                    out.push(node.to_string());
                    let targets = edges.get(node).cloned().unwrap_or_default();
                    for target in targets {
                        let entry = indegree.get_mut(target).unwrap();
                        *entry -= 1;
                        if *entry == 0 {
                            available.push(target);
                        }
                    }
                    available.sort_unstable();
                }
                if out.len() != nodes.len() {
                    return Vec::new();
                }
                out
            }
        '''),
    },
)


EVALUATE_EXPRESSION = Family(
    name="evaluate_expression",
    skill="recursive_descent",
    difficulty="hard",
    io={"args": ["str"], "returns": "str"},
    spec="""
Evaluate a small arithmetic expression and return the result rendered as a
decimal string.

Grammar and rules:
- Operands are runs of decimal digits, so every literal is zero or positive.
  There is no unary minus; negative results only arise from subtraction.
- The operators are `+`, `-`, `*` and `/`. Multiplication and division bind
  tighter than addition and subtraction, and operators of equal precedence
  associate to the left, so "8-3-2" is 3 and "8/4*2" is 4.
- Parentheses group and may nest.
- Spaces may appear anywhere between tokens and are ignored.
- Division truncates **toward zero**, not downward, so "(0-7)/2" is -3 and not
  -4.
- Return the empty string for anything that is not a well-formed expression: an
  unexpected or unknown character, unbalanced parentheses, a missing operand,
  trailing tokens, division by zero, or empty input.
""",
    signatures={
        "python": "def evaluate_expression(text: str) -> str:",
        "typescript": "function evaluateExpression(text: string): string {",
        "go": "func EvaluateExpression(text string) string {",
        "rust": "fn evaluate_expression(text: &str) -> String {",
    },
    inputs=[
        "1+2",
        "2+3*4",
        "(2+3)*4",
        "8-3-2",
        "8/4*2",
        "(0-7)/2",
        "7/2",
        "10 / 3",
        "  1 +  2 ",
        "1/0",
        "",
        "(1+2",
        "1+",
        "1 2",
        "a+1",
        "((3))",
        "100*100",
        "2*(3+4)-5",
        "0-10",
    ],
    reference=evaluate_expression,
    solutions={
        "python": dedent_code('''
            def evaluate_expression(text: str) -> str:
                tokens = []
                i = 0
                while i < len(text):
                    ch = text[i]
                    if ch == " ":
                        i += 1
                    elif "0" <= ch <= "9":
                        j = i
                        while j < len(text) and "0" <= text[j] <= "9":
                            j += 1
                        tokens.append(text[i:j])
                        i = j
                    elif ch in "+-*/()":
                        tokens.append(ch)
                        i += 1
                    else:
                        return ""

                pos = 0
                bad = False

                def peek():
                    return tokens[pos] if pos < len(tokens) else ""

                def factor():
                    nonlocal pos, bad
                    token = peek()
                    if token == "(":
                        pos += 1
                        value = expression()
                        if bad or peek() != ")":
                            bad = True
                            return 0
                        pos += 1
                        return value
                    if token != "" and "0" <= token[0] <= "9":
                        pos += 1
                        return int(token)
                    bad = True
                    return 0

                def term():
                    nonlocal pos, bad
                    value = factor()
                    while not bad and peek() in ("*", "/"):
                        operator = peek()
                        pos += 1
                        right = factor()
                        if bad:
                            return 0
                        if operator == "*":
                            value = value * right
                        elif right == 0:
                            bad = True
                            return 0
                        else:
                            quotient = abs(value) // abs(right)
                            value = -quotient if (value < 0) != (right < 0) else quotient
                    return value

                def expression():
                    nonlocal pos, bad
                    value = term()
                    while not bad and peek() in ("+", "-"):
                        operator = peek()
                        pos += 1
                        right = term()
                        if bad:
                            return 0
                        value = value + right if operator == "+" else value - right
                    return value

                result = expression()
                if bad or pos != len(tokens) or not tokens:
                    return ""
                return str(result)
        '''),
        "typescript": dedent_code('''
            export function evaluateExpression(text: string): string {
                const tokens: string[] = [];
                let i = 0;
                while (i < text.length) {
                    const ch = text[i];
                    if (ch === " ") {
                        i++;
                    } else if (ch >= "0" && ch <= "9") {
                        let j = i;
                        while (j < text.length && text[j] >= "0" && text[j] <= "9") j++;
                        tokens.push(text.slice(i, j));
                        i = j;
                    } else if ("+-*/()".includes(ch)) {
                        tokens.push(ch);
                        i++;
                    } else {
                        return "";
                    }
                }

                let pos = 0;
                let bad = false;
                const peek = (): string => (pos < tokens.length ? tokens[pos] : "");

                const factor = (): number => {
                    const token = peek();
                    if (token === "(") {
                        pos++;
                        const value = expression();
                        if (bad || peek() !== ")") {
                            bad = true;
                            return 0;
                        }
                        pos++;
                        return value;
                    }
                    if (token !== "" && token[0] >= "0" && token[0] <= "9") {
                        pos++;
                        return parseInt(token, 10);
                    }
                    bad = true;
                    return 0;
                };

                const term = (): number => {
                    let value = factor();
                    while (!bad && (peek() === "*" || peek() === "/")) {
                        const operator = peek();
                        pos++;
                        const right = factor();
                        if (bad) return 0;
                        if (operator === "*") {
                            value = value * right;
                        } else if (right === 0) {
                            bad = true;
                            return 0;
                        } else {
                            value = Math.trunc(value / right);
                        }
                    }
                    return value;
                };

                const expression = (): number => {
                    let value = term();
                    while (!bad && (peek() === "+" || peek() === "-")) {
                        const operator = peek();
                        pos++;
                        const right = term();
                        if (bad) return 0;
                        value = operator === "+" ? value + right : value - right;
                    }
                    return value;
                };

                const result = expression();
                if (bad || pos !== tokens.length || tokens.length === 0) return "";
                return String(result);
            }
        '''),
        "go": dedent_code('''
            package main

            import (
                "strconv"
                "strings"
            )

            type exprParser struct {
                tokens []string
                pos    int
                bad    bool
            }

            func (p *exprParser) peek() string {
                if p.pos < len(p.tokens) {
                    return p.tokens[p.pos]
                }
                return ""
            }

            func (p *exprParser) factor() int {
                token := p.peek()
                if token == "(" {
                    p.pos++
                    value := p.expression()
                    if p.bad || p.peek() != ")" {
                        p.bad = true
                        return 0
                    }
                    p.pos++
                    return value
                }
                if token != "" && token[0] >= '0' && token[0] <= '9' {
                    p.pos++
                    value, _ := strconv.Atoi(token)
                    return value
                }
                p.bad = true
                return 0
            }

            func (p *exprParser) term() int {
                value := p.factor()
                for !p.bad && (p.peek() == "*" || p.peek() == "/") {
                    operator := p.peek()
                    p.pos++
                    right := p.factor()
                    if p.bad {
                        return 0
                    }
                    if operator == "*" {
                        value = value * right
                    } else if right == 0 {
                        p.bad = true
                        return 0
                    } else {
                        value = value / right
                    }
                }
                return value
            }

            func (p *exprParser) expression() int {
                value := p.term()
                for !p.bad && (p.peek() == "+" || p.peek() == "-") {
                    operator := p.peek()
                    p.pos++
                    right := p.term()
                    if p.bad {
                        return 0
                    }
                    if operator == "+" {
                        value = value + right
                    } else {
                        value = value - right
                    }
                }
                return value
            }

            func EvaluateExpression(text string) string {
                tokens := []string{}
                i := 0
                for i < len(text) {
                    ch := text[i]
                    if ch == ' ' {
                        i++
                    } else if ch >= '0' && ch <= '9' {
                        j := i
                        for j < len(text) && text[j] >= '0' && text[j] <= '9' {
                            j++
                        }
                        tokens = append(tokens, text[i:j])
                        i = j
                    } else if strings.ContainsRune("+-*/()", rune(ch)) {
                        tokens = append(tokens, string(ch))
                        i++
                    } else {
                        return ""
                    }
                }
                parser := &exprParser{tokens: tokens}
                result := parser.expression()
                if parser.bad || parser.pos != len(tokens) || len(tokens) == 0 {
                    return ""
                }
                return strconv.Itoa(result)
            }
        '''),
        "rust": dedent_code('''
            struct ExprParser {
                tokens: Vec<String>,
                pos: usize,
                bad: bool,
            }

            impl ExprParser {
                fn peek(&self) -> String {
                    if self.pos < self.tokens.len() {
                        self.tokens[self.pos].clone()
                    } else {
                        String::new()
                    }
                }

                fn factor(&mut self) -> i64 {
                    let token = self.peek();
                    if token == "(" {
                        self.pos += 1;
                        let value = self.expression();
                        if self.bad || self.peek() != ")" {
                            self.bad = true;
                            return 0;
                        }
                        self.pos += 1;
                        return value;
                    }
                    if !token.is_empty() && token.as_bytes()[0].is_ascii_digit() {
                        self.pos += 1;
                        return token.parse().unwrap_or(0);
                    }
                    self.bad = true;
                    0
                }

                fn term(&mut self) -> i64 {
                    let mut value = self.factor();
                    while !self.bad && (self.peek() == "*" || self.peek() == "/") {
                        let operator = self.peek();
                        self.pos += 1;
                        let right = self.factor();
                        if self.bad {
                            return 0;
                        }
                        if operator == "*" {
                            value *= right;
                        } else if right == 0 {
                            self.bad = true;
                            return 0;
                        } else {
                            value /= right;
                        }
                    }
                    value
                }

                fn expression(&mut self) -> i64 {
                    let mut value = self.term();
                    while !self.bad && (self.peek() == "+" || self.peek() == "-") {
                        let operator = self.peek();
                        self.pos += 1;
                        let right = self.term();
                        if self.bad {
                            return 0;
                        }
                        if operator == "+" {
                            value += right;
                        } else {
                            value -= right;
                        }
                    }
                    value
                }
            }

            fn evaluate_expression(text: &str) -> String {
                let chars: Vec<char> = text.chars().collect();
                let mut tokens: Vec<String> = Vec::new();
                let mut i = 0usize;
                while i < chars.len() {
                    let ch = chars[i];
                    if ch == ' ' {
                        i += 1;
                    } else if ch.is_ascii_digit() {
                        let start = i;
                        while i < chars.len() && chars[i].is_ascii_digit() {
                            i += 1;
                        }
                        tokens.push(chars[start..i].iter().collect());
                    } else if "+-*/()".contains(ch) {
                        tokens.push(ch.to_string());
                        i += 1;
                    } else {
                        return String::new();
                    }
                }
                let mut parser = ExprParser { tokens, pos: 0, bad: false };
                let result = parser.expression();
                if parser.bad || parser.pos != parser.tokens.len() || parser.tokens.is_empty() {
                    return String::new();
                }
                result.to_string()
            }
        '''),
    },
)


ROUTE_PARAMS = Family(
    name="route_params",
    skill="routing",
    difficulty="hard",
    io={"args": ["str", "str"], "returns": "str"},
    spec="""
Match a request path against a route pattern and report the captured
parameters, the way an HTTP router does.

- Both strings are split on "/" into segments, and the two must have the same
  number of segments — no wildcards spanning several segments. That makes
  leading and trailing slashes significant: "/a" is two segments, "" and "a".
- A pattern segment starting with ":" and at least one character long is a
  parameter; it captures whatever segment sits in that position. Any other
  pattern segment must equal the path segment exactly.
- A parameter never captures an empty segment: that is not a match.
- On a match, return the captures as "name=value" joined by ";" in the order the
  parameters appear in the pattern.
- Return exactly "no-params" for a pattern that matches but captures nothing,
  and exactly "no-match" when the path does not match.
""",
    signatures={
        "python": "def route_params(pattern: str, path: str) -> str:",
        "typescript": "function routeParams(pattern: string, path: string): string {",
        "go": "func RouteParams(pattern string, path string) string {",
        "rust": "fn route_params(pattern: &str, path: &str) -> String {",
    },
    inputs=[
        ["/users/:id", "/users/42"],
        ["/users/:id/posts/:postId", "/users/7/posts/9"],
        ["/users/:id", "/users/"],
        ["/users/:id", "/users/42/extra"],
        ["/health", "/health"],
        ["/health", "/healthz"],
        ["/users/:id", "/accounts/42"],
        ["", ""],
        ["/", "/"],
        ["/a/:b/c", "/a/x/c"],
        ["/a/:b/c", "/a/x/d"],
        [":only", "value"],
        ["/files/:name", "/files/report.pdf"],
    ],
    reference=route_params,
    solutions={
        "python": dedent_code('''
            def route_params(pattern: str, path: str) -> str:
                pattern_parts = pattern.split("/")
                path_parts = path.split("/")
                if len(pattern_parts) != len(path_parts):
                    return "no-match"
                pairs = []
                for index in range(len(pattern_parts)):
                    expected = pattern_parts[index]
                    actual = path_parts[index]
                    if expected.startswith(":") and len(expected) > 1:
                        if actual == "":
                            return "no-match"
                        pairs.append(expected[1:] + "=" + actual)
                    elif expected != actual:
                        return "no-match"
                return ";".join(pairs) if pairs else "no-params"
        '''),
        "typescript": dedent_code('''
            export function routeParams(pattern: string, path: string): string {
                const patternParts = pattern.split("/");
                const pathParts = path.split("/");
                if (patternParts.length !== pathParts.length) return "no-match";
                const pairs: string[] = [];
                for (let index = 0; index < patternParts.length; index++) {
                    const expected = patternParts[index];
                    const actual = pathParts[index];
                    if (expected.startsWith(":") && expected.length > 1) {
                        if (actual === "") return "no-match";
                        pairs.push(`${expected.slice(1)}=${actual}`);
                    } else if (expected !== actual) {
                        return "no-match";
                    }
                }
                return pairs.length > 0 ? pairs.join(";") : "no-params";
            }
        '''),
        "go": dedent_code('''
            package main

            import "strings"

            func RouteParams(pattern string, path string) string {
                patternParts := strings.Split(pattern, "/")
                pathParts := strings.Split(path, "/")
                if len(patternParts) != len(pathParts) {
                    return "no-match"
                }
                pairs := []string{}
                for index := range patternParts {
                    expected := patternParts[index]
                    actual := pathParts[index]
                    if strings.HasPrefix(expected, ":") && len(expected) > 1 {
                        if actual == "" {
                            return "no-match"
                        }
                        pairs = append(pairs, expected[1:]+"="+actual)
                    } else if expected != actual {
                        return "no-match"
                    }
                }
                if len(pairs) == 0 {
                    return "no-params"
                }
                return strings.Join(pairs, ";")
            }
        '''),
        "rust": dedent_code('''
            fn route_params(pattern: &str, path: &str) -> String {
                let pattern_parts: Vec<&str> = pattern.split('/').collect();
                let path_parts: Vec<&str> = path.split('/').collect();
                if pattern_parts.len() != path_parts.len() {
                    return "no-match".to_string();
                }
                let mut pairs: Vec<String> = Vec::new();
                for index in 0..pattern_parts.len() {
                    let expected = pattern_parts[index];
                    let actual = path_parts[index];
                    if expected.starts_with(':') && expected.len() > 1 {
                        if actual.is_empty() {
                            return "no-match".to_string();
                        }
                        pairs.push(format!("{}={}", &expected[1..], actual));
                    } else if expected != actual {
                        return "no-match".to_string();
                    }
                }
                if pairs.is_empty() {
                    return "no-params".to_string();
                }
                pairs.join(";")
            }
        '''),
    },
)


SEMVER_SATISFIES = Family(
    name="semver_satisfies",
    skill="versioning",
    difficulty="hard",
    io={"args": ["str", "str"], "returns": "bool"},
    spec="""
Decide whether a version satisfies a dependency constraint, using npm's rules.

A version is exactly three runs of digits separated by dots. Versions compare
component by component, major first. There are no prerelease suffixes here.

Constraints:
- `*` — anything.
- `1.2.3` — exactly that version.
- `>=`, `>`, `<=`, `<` followed by a version — the obvious comparison.
- `^V` — at least V, up to but excluding the next version that changes the
  leftmost **non-zero** component. So `^1.2.3` allows up to but not including
  2.0.0; `^0.2.3` allows up to but not including 0.3.0; and `^0.0.3` allows only
  0.0.3 itself, since the next 0.0.4 is excluded.
- `~V` — at least V, up to but excluding the next minor: `~1.2.3` allows up to
  but not including 1.3.0, and `~0.2.3` up to but not including 0.3.0.

Return false when the version or the constraint's version is not three
dot-separated runs of digits, and false for an unrecognised constraint.
""",
    signatures={
        "python": "def semver_satisfies(version: str, constraint: str) -> bool:",
        "typescript": "function semverSatisfies(version: string, constraint: string): boolean {",
        "go": "func SemverSatisfies(version string, constraint string) bool {",
        "rust": "fn semver_satisfies(version: &str, constraint: &str) -> bool {",
    },
    inputs=[
        ["1.2.3", "*"],
        ["1.2.3", "1.2.3"],
        ["1.2.4", "1.2.3"],
        ["1.2.3", ">=1.2.3"],
        ["1.2.2", ">=1.2.3"],
        ["1.2.3", ">1.2.3"],
        ["1.2.3", "<=1.2.3"],
        ["1.2.3", "<1.2.3"],
        ["1.9.0", "^1.2.3"],
        ["2.0.0", "^1.2.3"],
        ["1.2.2", "^1.2.3"],
        ["0.2.9", "^0.2.3"],
        ["0.3.0", "^0.2.3"],
        ["0.0.3", "^0.0.3"],
        ["0.0.4", "^0.0.3"],
        ["1.2.9", "~1.2.3"],
        ["1.3.0", "~1.2.3"],
        ["0.2.9", "~0.2.3"],
        ["1.2", "1.2.0"],
        ["1.2.3", "1.2"],
        ["1.2.3", "!1.2.3"],
        ["10.0.0", ">=9.0.0"],
    ],
    reference=semver_satisfies,
    solutions={
        "python": dedent_code('''
            def _parse(text: str):
                fields = text.split(".")
                if len(fields) != 3:
                    return None
                out = []
                for field in fields:
                    if not field:
                        return None
                    for ch in field:
                        if ch < "0" or ch > "9":
                            return None
                    out.append(int(field))
                return (out[0], out[1], out[2])


            def semver_satisfies(version: str, constraint: str) -> bool:
                current = _parse(version)
                if current is None:
                    return False
                if constraint == "*":
                    return True
                for prefix in (">=", "<=", ">", "<"):
                    if constraint.startswith(prefix):
                        target = _parse(constraint[len(prefix):])
                        if target is None:
                            return False
                        if prefix == ">=":
                            return current >= target
                        if prefix == "<=":
                            return current <= target
                        if prefix == ">":
                            return current > target
                        return current < target
                if constraint.startswith("^"):
                    target = _parse(constraint[1:])
                    if target is None:
                        return False
                    if target[0] > 0:
                        upper = (target[0] + 1, 0, 0)
                    elif target[1] > 0:
                        upper = (0, target[1] + 1, 0)
                    else:
                        upper = (0, 0, target[2] + 1)
                    return target <= current < upper
                if constraint.startswith("~"):
                    target = _parse(constraint[1:])
                    if target is None:
                        return False
                    return target <= current < (target[0], target[1] + 1, 0)
                exact = _parse(constraint)
                return exact is not None and current == exact
        '''),
        "typescript": dedent_code('''
            type Version = [number, number, number];

            function parseVersion(text: string): Version | null {
                const fields = text.split(".");
                if (fields.length !== 3) return null;
                const out: number[] = [];
                for (const field of fields) {
                    if (field.length === 0 || !/^[0-9]+$/.test(field)) return null;
                    out.push(parseInt(field, 10));
                }
                return [out[0], out[1], out[2]];
            }

            function compare(a: Version, b: Version): number {
                for (let i = 0; i < 3; i++) {
                    if (a[i] !== b[i]) return a[i] < b[i] ? -1 : 1;
                }
                return 0;
            }

            export function semverSatisfies(version: string, constraint: string): boolean {
                const current = parseVersion(version);
                if (current === null) return false;
                if (constraint === "*") return true;
                for (const prefix of [">=", "<=", ">", "<"]) {
                    if (constraint.startsWith(prefix)) {
                        const target = parseVersion(constraint.slice(prefix.length));
                        if (target === null) return false;
                        const c = compare(current, target);
                        if (prefix === ">=") return c >= 0;
                        if (prefix === "<=") return c <= 0;
                        if (prefix === ">") return c > 0;
                        return c < 0;
                    }
                }
                if (constraint.startsWith("^")) {
                    const target = parseVersion(constraint.slice(1));
                    if (target === null) return false;
                    let upper: Version;
                    if (target[0] > 0) upper = [target[0] + 1, 0, 0];
                    else if (target[1] > 0) upper = [0, target[1] + 1, 0];
                    else upper = [0, 0, target[2] + 1];
                    return compare(current, target) >= 0 && compare(current, upper) < 0;
                }
                if (constraint.startsWith("~")) {
                    const target = parseVersion(constraint.slice(1));
                    if (target === null) return false;
                    const upper: Version = [target[0], target[1] + 1, 0];
                    return compare(current, target) >= 0 && compare(current, upper) < 0;
                }
                const exact = parseVersion(constraint);
                return exact !== null && compare(current, exact) === 0;
            }
        '''),
        "go": dedent_code('''
            package main

            import (
                "strconv"
                "strings"
            )

            func parseVersion(text string) ([3]int, bool) {
                var out [3]int
                fields := strings.Split(text, ".")
                if len(fields) != 3 {
                    return out, false
                }
                for i, field := range fields {
                    if len(field) == 0 {
                        return out, false
                    }
                    for _, ch := range field {
                        if ch < '0' || ch > '9' {
                            return out, false
                        }
                    }
                    value, err := strconv.Atoi(field)
                    if err != nil {
                        return out, false
                    }
                    out[i] = value
                }
                return out, true
            }

            func compareVersions(a [3]int, b [3]int) int {
                for i := 0; i < 3; i++ {
                    if a[i] != b[i] {
                        if a[i] < b[i] {
                            return -1
                        }
                        return 1
                    }
                }
                return 0
            }

            func SemverSatisfies(version string, constraint string) bool {
                current, ok := parseVersion(version)
                if !ok {
                    return false
                }
                if constraint == "*" {
                    return true
                }
                for _, prefix := range []string{">=", "<=", ">", "<"} {
                    if strings.HasPrefix(constraint, prefix) {
                        target, valid := parseVersion(constraint[len(prefix):])
                        if !valid {
                            return false
                        }
                        c := compareVersions(current, target)
                        switch prefix {
                        case ">=":
                            return c >= 0
                        case "<=":
                            return c <= 0
                        case ">":
                            return c > 0
                        }
                        return c < 0
                    }
                }
                if strings.HasPrefix(constraint, "^") {
                    target, valid := parseVersion(constraint[1:])
                    if !valid {
                        return false
                    }
                    var upper [3]int
                    if target[0] > 0 {
                        upper = [3]int{target[0] + 1, 0, 0}
                    } else if target[1] > 0 {
                        upper = [3]int{0, target[1] + 1, 0}
                    } else {
                        upper = [3]int{0, 0, target[2] + 1}
                    }
                    return compareVersions(current, target) >= 0 && compareVersions(current, upper) < 0
                }
                if strings.HasPrefix(constraint, "~") {
                    target, valid := parseVersion(constraint[1:])
                    if !valid {
                        return false
                    }
                    upper := [3]int{target[0], target[1] + 1, 0}
                    return compareVersions(current, target) >= 0 && compareVersions(current, upper) < 0
                }
                exact, valid := parseVersion(constraint)
                return valid && compareVersions(current, exact) == 0
            }
        '''),
        "rust": dedent_code('''
            fn parse_version(text: &str) -> Option<(i64, i64, i64)> {
                let fields: Vec<&str> = text.split('.').collect();
                if fields.len() != 3 {
                    return None;
                }
                let mut out = [0i64; 3];
                for (i, field) in fields.iter().enumerate() {
                    if field.is_empty() || !field.chars().all(|c| c.is_ascii_digit()) {
                        return None;
                    }
                    out[i] = field.parse().ok()?;
                }
                Some((out[0], out[1], out[2]))
            }

            fn semver_satisfies(version: &str, constraint: &str) -> bool {
                let current = match parse_version(version) {
                    Some(value) => value,
                    None => return false,
                };
                if constraint == "*" {
                    return true;
                }
                for prefix in [">=", "<=", ">", "<"] {
                    if let Some(rest) = constraint.strip_prefix(prefix) {
                        let target = match parse_version(rest) {
                            Some(value) => value,
                            None => return false,
                        };
                        return match prefix {
                            ">=" => current >= target,
                            "<=" => current <= target,
                            ">" => current > target,
                            _ => current < target,
                        };
                    }
                }
                if let Some(rest) = constraint.strip_prefix('^') {
                    let target = match parse_version(rest) {
                        Some(value) => value,
                        None => return false,
                    };
                    let upper = if target.0 > 0 {
                        (target.0 + 1, 0, 0)
                    } else if target.1 > 0 {
                        (0, target.1 + 1, 0)
                    } else {
                        (0, 0, target.2 + 1)
                    };
                    return current >= target && current < upper;
                }
                if let Some(rest) = constraint.strip_prefix('~') {
                    let target = match parse_version(rest) {
                        Some(value) => value,
                        None => return false,
                    };
                    let upper = (target.0, target.1 + 1, 0);
                    return current >= target && current < upper;
                }
                match parse_version(constraint) {
                    Some(exact) => current == exact,
                    None => false,
                }
            }
        '''),
    },
)


TOKENIZE_COMMAND = Family(
    name="tokenize_command",
    skill="lexing",
    difficulty="hard",
    io={"args": ["str"], "returns": "list<str>"},
    spec="""
Split a command line into arguments the way a shell does, handling quotes and
escapes.

Rules:
- Runs of spaces separate arguments and are otherwise discarded.
- A double quote toggles quoting. Inside quotes, spaces are ordinary characters.
  The quote characters themselves never appear in the output, so `a"b"c` is the
  single argument `abc`.
- A backslash escapes the next character anywhere in the input, inside quotes or
  out, and the backslash itself is dropped: `a\\ b` is one argument `a b`, and
  `\\"` is a literal quote.
- An empty pair of quotes still produces an argument — the empty string — so `""`
  yields one empty argument, and `a""b` yields `ab`.
- Return an empty list for input that is only spaces or empty.
- Return an empty list for malformed input: a quote that is never closed, or a
  backslash at the very end with nothing to escape.
""",
    signatures={
        "python": "def tokenize_command(text: str) -> list[str]:",
        "typescript": "function tokenizeCommand(text: string): string[] {",
        "go": "func TokenizeCommand(text string) []string {",
        "rust": "fn tokenize_command(text: &str) -> Vec<String> {",
    },
    inputs=[
        "a b c",
        '"a b" c',
        "",
        "   ",
        "a\\ b",
        '"unterminated',
        "a\\",
        '""',
        'a"b"c',
        "  spaced   out  ",
        'say \\"hi\\"',
        'a""b',
        'echo "hello world" > out.txt',
    ],
    reference=tokenize_command,
    solutions={
        "python": dedent_code('''
            def tokenize_command(text: str) -> list[str]:
                out = []
                current = ""
                started = False
                quoted = False
                i = 0
                while i < len(text):
                    ch = text[i]
                    if ch == "\\\\":
                        if i + 1 >= len(text):
                            return []
                        current += text[i + 1]
                        started = True
                        i += 2
                    elif ch == '"':
                        quoted = not quoted
                        started = True
                        i += 1
                    elif ch == " " and not quoted:
                        if started:
                            out.append(current)
                            current = ""
                            started = False
                        i += 1
                    else:
                        current += ch
                        started = True
                        i += 1
                if quoted:
                    return []
                if started:
                    out.append(current)
                return out
        '''),
        "typescript": dedent_code('''
            export function tokenizeCommand(text: string): string[] {
                const out: string[] = [];
                let current = "";
                let started = false;
                let quoted = false;
                let i = 0;
                while (i < text.length) {
                    const ch = text[i];
                    if (ch === "\\\\") {
                        if (i + 1 >= text.length) return [];
                        current += text[i + 1];
                        started = true;
                        i += 2;
                    } else if (ch === '"') {
                        quoted = !quoted;
                        started = true;
                        i += 1;
                    } else if (ch === " " && !quoted) {
                        if (started) {
                            out.push(current);
                            current = "";
                            started = false;
                        }
                        i += 1;
                    } else {
                        current += ch;
                        started = true;
                        i += 1;
                    }
                }
                if (quoted) return [];
                if (started) out.push(current);
                return out;
            }
        '''),
        "go": dedent_code('''
            package main

            func TokenizeCommand(text string) []string {
                out := []string{}
                current := ""
                started := false
                quoted := false
                i := 0
                for i < len(text) {
                    ch := text[i]
                    if ch == '\\\\' {
                        if i+1 >= len(text) {
                            return []string{}
                        }
                        current += string(text[i+1])
                        started = true
                        i += 2
                    } else if ch == '"' {
                        quoted = !quoted
                        started = true
                        i++
                    } else if ch == ' ' && !quoted {
                        if started {
                            out = append(out, current)
                            current = ""
                            started = false
                        }
                        i++
                    } else {
                        current += string(ch)
                        started = true
                        i++
                    }
                }
                if quoted {
                    return []string{}
                }
                if started {
                    out = append(out, current)
                }
                return out
            }
        '''),
        "rust": dedent_code('''
            fn tokenize_command(text: &str) -> Vec<String> {
                let chars: Vec<char> = text.chars().collect();
                let mut out: Vec<String> = Vec::new();
                let mut current = String::new();
                let mut started = false;
                let mut quoted = false;
                let mut i = 0usize;
                while i < chars.len() {
                    let ch = chars[i];
                    if ch == '\\\\' {
                        if i + 1 >= chars.len() {
                            return Vec::new();
                        }
                        current.push(chars[i + 1]);
                        started = true;
                        i += 2;
                    } else if ch == '"' {
                        quoted = !quoted;
                        started = true;
                        i += 1;
                    } else if ch == ' ' && !quoted {
                        if started {
                            out.push(current.clone());
                            current.clear();
                            started = false;
                        }
                        i += 1;
                    } else {
                        current.push(ch);
                        started = true;
                        i += 1;
                    }
                }
                if quoted {
                    return Vec::new();
                }
                if started {
                    out.push(current);
                }
                out
            }
        '''),
    },
)


PERCENT_DECODE = Family(
    name="percent_decode",
    skill="encoding",
    difficulty="hard",
    io={"args": ["str"], "returns": "str"},
    spec="""
Decode a percent-encoded query-string value.

Rules:
- `+` becomes a space.
- `%` followed by two hexadecimal digits (either case) becomes the character
  with that code, but only when the code is a printable ASCII one, from 0x20
  (space) through 0x7E (`~`).
- A `%` that is not followed by two hex digits, or whose code is outside that
  printable range, is **left exactly as it is** and decoding continues from the
  next character. So "100%" stays "100%", "%zz" stays "%zz", and "%09" stays
  "%09".
- Decoding happens in one pass and the output is never decoded again: "%25" is
  a single "%" and is not treated as the start of another escape, and "a%2Bb"
  is "a+b" with a literal plus, not a space.
- Every other character is copied through unchanged. The empty string decodes to
  the empty string.
""",
    signatures={
        "python": "def percent_decode(text: str) -> str:",
        "typescript": "function percentDecode(text: string): string {",
        "go": "func PercentDecode(text string) string {",
        "rust": "fn percent_decode(text: &str) -> String {",
    },
    inputs=[
        "a%20b",
        "a+b",
        "",
        "100%",
        "%2",
        "%zz",
        "%41%42",
        "%7e",
        "%09",
        "a%2Bb",
        "no-escapes",
        "%25",
        "%2520",
        "a%",
        "%7F",
    ],
    reference=percent_decode,
    solutions={
        "python": dedent_code('''
            def _hex(ch: str) -> bool:
                return ("0" <= ch <= "9") or ("a" <= ch <= "f") or ("A" <= ch <= "F")


            def percent_decode(text: str) -> str:
                out = ""
                i = 0
                while i < len(text):
                    ch = text[i]
                    if ch == "+":
                        out += " "
                        i += 1
                        continue
                    if ch == "%" and i + 2 < len(text) and _hex(text[i + 1]) and _hex(text[i + 2]):
                        code = int(text[i + 1:i + 3], 16)
                        if 0x20 <= code <= 0x7E:
                            out += chr(code)
                            i += 3
                            continue
                    out += ch
                    i += 1
                return out
        '''),
        "typescript": dedent_code('''
            function isHex(ch: string): boolean {
                return /^[0-9a-fA-F]$/.test(ch);
            }

            export function percentDecode(text: string): string {
                let out = "";
                let i = 0;
                while (i < text.length) {
                    const ch = text[i];
                    if (ch === "+") {
                        out += " ";
                        i += 1;
                        continue;
                    }
                    if (ch === "%" && i + 2 < text.length && isHex(text[i + 1]) && isHex(text[i + 2])) {
                        const code = parseInt(text.slice(i + 1, i + 3), 16);
                        if (code >= 0x20 && code <= 0x7e) {
                            out += String.fromCharCode(code);
                            i += 3;
                            continue;
                        }
                    }
                    out += ch;
                    i += 1;
                }
                return out;
            }
        '''),
        "go": dedent_code('''
            package main

            import "strconv"

            func isHexDigit(ch byte) bool {
                return (ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f') || (ch >= 'A' && ch <= 'F')
            }

            func PercentDecode(text string) string {
                out := ""
                i := 0
                for i < len(text) {
                    ch := text[i]
                    if ch == '+' {
                        out += " "
                        i++
                        continue
                    }
                    if ch == '%' && i+2 < len(text) && isHexDigit(text[i+1]) && isHexDigit(text[i+2]) {
                        code, err := strconv.ParseInt(text[i+1:i+3], 16, 32)
                        if err == nil && code >= 0x20 && code <= 0x7E {
                            out += string(rune(code))
                            i += 3
                            continue
                        }
                    }
                    out += string(ch)
                    i++
                }
                return out
            }
        '''),
        "rust": dedent_code('''
            fn is_hex_digit(ch: char) -> bool {
                ch.is_ascii_hexdigit()
            }

            fn percent_decode(text: &str) -> String {
                let chars: Vec<char> = text.chars().collect();
                let mut out = String::new();
                let mut i = 0usize;
                while i < chars.len() {
                    let ch = chars[i];
                    if ch == '+' {
                        out.push(' ');
                        i += 1;
                        continue;
                    }
                    if ch == '%'
                        && i + 2 < chars.len()
                        && is_hex_digit(chars[i + 1])
                        && is_hex_digit(chars[i + 2])
                    {
                        let hex: String = chars[i + 1..i + 3].iter().collect();
                        if let Ok(code) = u32::from_str_radix(&hex, 16) {
                            if (0x20..=0x7E).contains(&code) {
                                out.push(char::from_u32(code).unwrap());
                                i += 3;
                                continue;
                            }
                        }
                    }
                    out.push(ch);
                    i += 1;
                }
                out
            }
        '''),
    },
)


ADVANCED_FAMILIES = [
    GLOB_MATCH,
    CRON_FIELD_MATCHES,
    EXPAND_RANGES,
    WRAP_TEXT,
    TOPOLOGICAL_ORDER,
    EVALUATE_EXPRESSION,
    ROUTE_PARAMS,
    SEMVER_SATISFIES,
    TOKENIZE_COMMAND,
    PERCENT_DECODE,
]
