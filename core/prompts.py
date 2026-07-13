"""Prompt templates for each test category.

Every prompt demands a single JSON object so answers can be validated with
the schemas in core/schemas.py. Logs are numbered from 0 inside <logs> tags
and numeric series inside <series> tags, so evaluators (and the offline mock
provider) can reference items by index.
"""

from __future__ import annotations

from typing import Any

SYSTEM_PROMPT = (
    "You are an expert SRE assistant specialized in log and metrics analysis. "
    "You always respond with a single valid JSON object and nothing else: "
    "no markdown fences, no explanations, no text before or after the JSON."
)

JUDGE_SYSTEM_PROMPT = (
    "You are a strict grader for incident root-cause analyses. "
    "You always respond with a single valid JSON object and nothing else."
)


def _numbered(lines: list[str]) -> str:
    return "\n".join(f"{i}: {line}" for i, line in enumerate(lines))


def build_prompt(category: str, case: dict[str, Any]) -> str:
    builder = _BUILDERS[category]
    return builder(case)


def _log_parsing(case: dict[str, Any]) -> str:
    return f"""Task: log_parsing

Extract the log template of each log line below. Replace every variable part
(IDs, numbers, IP addresses, paths, durations, hostnames) with the placeholder <*>.
Keep constant words exactly as they appear. Return one template per input line,
in the same order.

<logs>
{_numbered(case["logs"])}
</logs>

Return JSON exactly in this shape:
{{"templates": ["<template for line 0>", "<template for line 1>", ...]}}"""


def _anomaly_detection(case: dict[str, Any]) -> str:
    return f"""Task: anomaly_detection

Analyze the log lines below and identify which lines are anomalous
(errors, failures, security issues, or abnormal behavior — not routine
warnings or informational noise). Use the 0-based line numbers.

<logs>
{_numbered(case["logs"])}
</logs>

Return JSON exactly in this shape:
{{"anomalous_indices": [<int>, ...]}}

If no line is anomalous, return {{"anomalous_indices": []}}."""


def _pattern_correlation(case: dict[str, Any]) -> str:
    return f"""Task: pattern_correlation

Analyze the log lines below. First identify the recurring problem patterns
(groups of related events). Then identify causal correlations between the
patterns (which pattern causes or triggers which other pattern).

<logs>
{_numbered(case["logs"])}
</logs>

Return JSON exactly in this shape:
{{
  "patterns": [{{"name": "<short_snake_case_name>", "description": "<what the pattern is>"}}, ...],
  "correlations": [{{"cause": "<pattern name>", "effect": "<pattern name>"}}, ...]
}}"""


def _metrics_timeseries(case: dict[str, Any]) -> str:
    values = ", ".join(str(v) for v in case["values"])
    return f"""Task: metrics_timeseries

Below is a time series of the metric "{case["metric"]}" sampled at a fixed
interval. Identify the indices (0-based) of anomalous points — values that
deviate abnormally from the series' normal behavior (spikes, drops, level
shifts).

<series>
{values}
</series>

Return JSON exactly in this shape:
{{"anomalous_indices": [<int>, ...]}}"""


def _root_cause(case: dict[str, Any]) -> str:
    return f"""Task: root_cause

Below are the logs collected during a production incident. Determine the most
likely root cause and write a concise incident summary (2-4 sentences) covering
what happened, the impact, and the root cause.

<logs>
{_numbered(case["logs"])}
</logs>

Return JSON exactly in this shape:
{{"root_cause": "<one sentence root cause>", "summary": "<2-4 sentence incident summary>"}}"""


def build_judge_prompt(case: dict[str, Any], candidate_root_cause: str, candidate_summary: str) -> str:
    return f"""Grade a candidate root-cause analysis against the reference answer.

Reference root cause: {case["reference_root_cause"]}
Reference summary: {case["reference_summary"]}

Candidate root cause: {candidate_root_cause}
Candidate summary: {candidate_summary}

Score the candidate from 0 to 10:
- 0-3: wrong or missing root cause
- 4-6: partially correct (right area, wrong mechanism, or major omissions)
- 7-8: correct root cause with a mostly complete summary
- 9-10: correct root cause and an accurate, complete summary

Return JSON exactly in this shape:
{{"score": <number 0-10>, "reasoning": "<one sentence>"}}"""


_BUILDERS = {
    "log_parsing": _log_parsing,
    "anomaly_detection": _anomaly_detection,
    "pattern_correlation": _pattern_correlation,
    "metrics_timeseries": _metrics_timeseries,
    "root_cause": _root_cause,
}
