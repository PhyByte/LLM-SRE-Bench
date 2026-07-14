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


def _loads_lenient(text: str) -> Any:
    """json.loads, retried once with trailing commas removed."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return json.loads(_TRAILING_COMMA.sub(r"\1", text))


def extract_json(text: str) -> dict[str, Any]:
    """Pull the first JSON object out of an LLM response.

    Handles markdown fences, leading/trailing prose around the object, and
    trailing commas. Raises ValueError if no parseable object is found.
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
