"""Prompt templates for each test category.

Every prompt demands a single JSON object so answers can be validated with
the schemas in core/schemas.py. Logs are numbered from 0 inside <logs> tags
and numeric series inside <series> tags, so evaluators (and the offline mock
provider) can reference items by index.
"""

from __future__ import annotations

from typing import Any

# Categories whose answer is code the harness compiles and runs.
CODE_WRITING_CATEGORIES = (
    "code_generation",
    "code_efficiency",
    "code_debugging",
    "code_refactoring",
)

SYSTEM_PROMPT = (
    "You are an expert SRE assistant specialized in log and metrics analysis. "
    "You always respond with a single valid JSON object and nothing else: "
    "no markdown fences, no explanations, no text before or after the JSON."
)

CODE_GENERATION_SYSTEM_PROMPT = (
    "You are an expert software engineer. "
    "You always respond with a single valid JSON object containing working code. "
    "No markdown fences, no explanations, no text before or after the JSON. "
    "The code must be correct, efficient, and handle all specified edge cases."
)

CODE_REVIEW_SYSTEM_PROMPT = (
    "You are a senior engineer reviewing a pull request. "
    "You always respond with a single valid JSON object and nothing else: "
    "no markdown fences, no explanations, no text before or after the JSON. "
    "You report real defects with their consequences, and you do not pad the "
    "review with style opinions or speculative findings."
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


def _code_generation(case: dict[str, Any]) -> str:
    language = case["language"]
    spec = case["spec"]
    signature = case.get("signature", "")
    
    return f"""Task: code_generation

Language: {language}

{spec}

{"Required function signature:" if signature else ""}
{signature}

Return JSON exactly in this shape:
{{"code": "<complete working implementation>"}}

The code must:
- Implement the specified functionality correctly
- Handle all edge cases mentioned in the spec
- Be syntactically correct and runnable
- Follow best practices for {language}"""


def _numbered_code(code: str) -> str:
    """Code lines numbered from 1, so findings can be pinned to a line."""
    return "\n".join(f"{i}: {line}" for i, line in enumerate(code.split("\n"), start=1))


def _code_efficiency(case: dict[str, Any]) -> str:
    language = case["language"]
    budget = case.get("time_budget_ms")
    return f"""Task: code_efficiency

Language: {language}

{case["spec"]}

Required function signature:
{case.get("signature", "")}

Your solution is run once against an input of {case["workload"]["arrays"][0]["n"]:,}
elements and must finish that call in under {budget} ms on the grading machine,
so the algorithm matters more than the micro-optimizations. It also has to be
correct on small inputs and edge cases.

Return JSON exactly in this shape:
{{"code": "<complete working implementation>"}}"""


def _code_debugging(case: dict[str, Any]) -> str:
    language = case["language"]
    return f"""Task: code_debugging

Language: {language}

This implementation is in production and is wrong. Find the defect and return a
corrected implementation.

Reported symptom:
{case["symptom"]}

What the function is supposed to do:
{case["spec"]}

Current implementation:
<code>
{case["buggy_code"]}
</code>

Keep the signature exactly as it is:
{case.get("signature", "")}

Return the complete fixed implementation — not a diff, not an explanation.

Return JSON exactly in this shape:
{{"code": "<complete fixed implementation>"}}"""


def _code_refactoring(case: dict[str, Any]) -> str:
    language = case["language"]
    return f"""Task: code_refactoring

Language: {language}

Refactor the code below. Its behavior is correct and must not change — it is
covered by tests you cannot see, and any behavior change fails the task.

Refactoring goal:
{case["goal"]}

What the function does (unchanged contract):
{case["spec"]}

Current implementation:
<code>
{case["original_code"]}
</code>

Keep the signature exactly as it is:
{case.get("signature", "")}

Return the complete refactored implementation — not a diff, not an explanation.

Return JSON exactly in this shape:
{{"code": "<complete refactored implementation>"}}"""


def _code_review(case: dict[str, Any]) -> str:
    language = case["language"]
    return f"""Task: code_review

Language: {language}

Review the code below as if it were a pull request you can block. Report the
defects that matter — correctness bugs, security holes, resource and
concurrency problems, and things that fall over at production scale. Say what
is wrong and why, not just which line looks suspicious. Do not report style,
naming, or formatting preferences, and do not pad the list: findings that do
not correspond to a real defect count against you.

Context:
{case["context"]}

Code (line numbers on the left are not part of the file):
<code>
{_numbered_code(case["code"])}
</code>

Return JSON exactly in this shape:
{{"findings": [{{"line": <int line number>, "severity": "<low|medium|high|critical>", "issue": "<what is wrong and why it matters>"}}, ...]}}

If the code has no defects worth blocking on, return {{"findings": []}}."""


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
    "code_generation": _code_generation,
    "code_efficiency": _code_efficiency,
    "code_debugging": _code_debugging,
    "code_refactoring": _code_refactoring,
    "code_review": _code_review,
}
