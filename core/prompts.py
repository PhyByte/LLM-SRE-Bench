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


FAULT_VOCABULARY = [
    "cpu_saturation",
    "network_delay",
    "code_return_value",
    "code_exception",
    "none",
    "unknown",
]


def _multimodal_rca(case: dict[str, Any]) -> str:
    modalities = case["modalities"]

    metric_lines = []
    for service, series in modalities.get("metrics", {}).items():
        metric_lines.append(f"{service}")
        metric_lines.extend(f"  {line}" for line in series)
    trace_lines = [f"{service}: {stats}" for service, stats in modalities.get("traces", {}).items()]

    # Empty modalities are omitted rather than shown as blank sections, so the
    # model is never invited to cite evidence that isn't in front of it.
    sections = []
    if metric_lines:
        sections.append(
            "<metrics>\nPer-service time series over the window, one sample per minute.\n"
            + "\n".join(metric_lines)
            + "\n</metrics>"
        )
    if modalities.get("logs"):
        sections.append("<logs>\n" + "\n".join(modalities["logs"]) + "\n</logs>")
    if trace_lines:
        sections.append(
            "<traces>\nPer-service span aggregates over the window.\n"
            + "\n".join(trace_lines)
            + "\n</traces>"
        )

    return f"""Task: multimodal_rca

You are on call for the "{case["system"]}" microservice system. An incident was
reported during {case["incident_window"]}. Below is the observability data
collected across three modalities for that window.

Not every modality is informative: some contain only normal background activity
for this incident. Cite evidence only from the modalities that actually support
your conclusion — citing a modality that shows nothing unusual counts against
you.

There are three possible verdicts, and choosing between them is the task:
  - a service name — the evidence identifies that service as the root cause
  - "none"    — the system is healthy; nothing here is a fault
  - "unknown" — something is wrong, but this evidence does not show which
                service is responsible

"none" and "unknown" are not interchangeable. Report "none" only when you
believe the system is behaving normally. Report "unknown" when there are signs
of a problem you cannot attribute to a specific service from what you were
given. Guessing a plausible-looking service when the evidence does not support
it scores worse than saying "unknown".

Candidate services (the culprit is one of these, or "none", or "unknown"):
{", ".join(case["services"])}

Fault types (choose exactly one):
{", ".join(FAULT_VOCABULARY)}

{chr(10).join(sections)}

Return JSON exactly in this shape:
{{
  "culprit_service": "<service name, or \\"none\\", or \\"unknown\\">",
  "fault_type": "<one of the fault types above>",
  "evidence": [{{"modality": "<metrics|logs|traces>", "observation": "<what you saw>"}}, ...],
  "summary": "<2-4 sentence incident summary>"
}}

If the system is healthy, return "none" for both culprit_service and fault_type
with an empty evidence list. If you cannot attribute the problem to a service,
return "unknown" for both, and use the summary to say what you observed and why
it is not enough to localize the fault."""


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
    "multimodal_rca": _multimodal_rca,
}
