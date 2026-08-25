"""Shared helpers: robust JSON extraction from LLM output."""

from __future__ import annotations

import json
import re
from typing import Any

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)
# Trailing comma before a closing } or ] — a very common LLM serialization
# quirk that strict json.loads rejects. Stripping it measures SRE skill, not
# JSON pedantry. Only matches commas followed by optional whitespace + a close.
_TRAILING_COMMA = re.compile(r",(\s*[}\]])")

# JSON allows only these single-char escapes after a backslash (plus \uXXXX).
_JSON_SINGLE_ESCAPES = set('"\\/bfnrt')
_HEX = set("0123456789abcdefABCDEF")


def _sanitize_json_strings(text: str) -> str:
    """Fix common LLM mistakes inside JSON string literals.

    - Raw newlines / tabs / other controls → ``\\n`` / ``\\t`` / ``\\u00XX``
    - Invalid escapes like ``\\s`` (regex) or ``\\users`` → doubled backslash
      so the decoded string keeps a literal backslash

    Outside of strings the text is left untouched.
    """
    out: list[str] = []
    in_string = False
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if not in_string:
            if ch == '"':
                in_string = True
            out.append(ch)
            i += 1
            continue

        # --- inside a string ---
        if ch == '"':
            in_string = False
            out.append(ch)
            i += 1
            continue

        if ch == "\\":
            if i + 1 >= n:
                # Trailing lone backslash → escape it
                out.append("\\\\")
                i += 1
                continue
            nxt = text[i + 1]
            if nxt in _JSON_SINGLE_ESCAPES:
                out.append("\\")
                out.append(nxt)
                i += 2
                continue
            if (
                nxt == "u"
                and i + 5 < n
                and all(c in _HEX for c in text[i + 2 : i + 6])
            ):
                out.append(text[i : i + 6])
                i += 6
                continue
            # Invalid escape (e.g. \s, \d, \users) → literal backslash + char
            out.append("\\\\")
            out.append(nxt)
            i += 2
            continue

        if ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        elif ord(ch) < 0x20:
            out.append(f"\\u{ord(ch):04x}")
        else:
            out.append(ch)
        i += 1

    return "".join(out)


def _loads_lenient(text: str) -> Any:
    """json.loads with common LLM JSON fixes."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    try:
        return json.loads(_TRAILING_COMMA.sub(r"\1", text))
    except json.JSONDecodeError:
        pass

    fixed = _sanitize_json_strings(text)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        return json.loads(_TRAILING_COMMA.sub(r"\1", fixed))


def extract_json(text: str) -> dict[str, Any]:
    """Pull the first JSON object out of an LLM response.

    Handles markdown fences, leading/trailing prose around the object,
    trailing commas, unescaped control characters inside strings, and
    invalid backslash escapes (common when models dump regex/code into JSON).
    Raises ValueError if no parseable object is found.
    """
    candidate = text.strip()
    fenced = _FENCE.search(candidate)
    if fenced:
        candidate = fenced.group(1).strip()

    try:
        obj = _loads_lenient(candidate)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    start = candidate.find("{")
    if start == -1:
        raise ValueError("no JSON object found in response")

    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(candidate)):
        ch = candidate[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                obj = _loads_lenient(candidate[start : i + 1])
                if isinstance(obj, dict):
                    return obj
                raise ValueError("top-level JSON value is not an object")
    raise ValueError("unbalanced JSON object in response")
