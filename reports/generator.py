"""Aggregation and report generation (markdown, CSV, JSON)."""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from core.config import CATEGORY_WEIGHTS
from core.runner import RunRecord
from evaluators.efficiency import evaluate as evaluate_efficiency


@dataclass
class ModelSummary:
    model: str
    category_scores: dict[str, float]  # 0-100 per category, incl. "efficiency"
    global_score: float  # 0-100, weighted
    efficiency_metrics: dict[str, float] = field(default_factory=dict)
    error_count: int = 0
    total_runs: int = 0


def aggregate(records: list[RunRecord]) -> list[ModelSummary]:
    """Roll run records up into per-model category scores and a global score.

    Weights are renormalized over the categories actually run (plus
    efficiency), so partial runs via --category still yield a 0-100 score.
    """
    by_model: dict[str, list[RunRecord]] = defaultdict(list)
    for record in records:
        by_model[record.model].append(record)

    summaries: list[ModelSummary] = []
    for model, model_records in by_model.items():
        # Per-case mean across runs, then per-category mean across cases.
        by_category_case: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
        for record in model_records:
            by_category_case[record.category][record.case_id].append(record.score)

        category_scores: dict[str, float] = {}
        for category, cases in by_category_case.items():
            case_means = [statistics.fmean(scores) for scores in cases.values()]
            category_scores[category] = 100 * statistics.fmean(case_means)

        efficiency = evaluate_efficiency(model_records)
        category_scores["efficiency"] = 100 * efficiency.score

        active_weights = {
            category: CATEGORY_WEIGHTS[category]
            for category in category_scores
            if category in CATEGORY_WEIGHTS
        }
        weight_total = sum(active_weights.values())
        global_score = sum(
            category_scores[category] * weight / weight_total
            for category, weight in active_weights.items()
        )

        summaries.append(
            ModelSummary(
                model=model,
                category_scores=category_scores,
                global_score=global_score,
                efficiency_metrics=efficiency.metrics,
                error_count=sum(1 for r in model_records if r.error is not None),
                total_runs=len(model_records),
            )
        )

    summaries.sort(key=lambda s: s.global_score, reverse=True)
    return summaries


_CATEGORY_LABELS = {
    "log_parsing": "Log Parsing",
    "anomaly_detection": "Anomaly Detection",
    "pattern_correlation": "Pattern & Correlation",
    "metrics_timeseries": "Metrics Time-Series",
    "root_cause": "Root Cause & Summary",
    "efficiency": "Efficiency & Consistency",
}


def _ordered_categories(summaries: list[ModelSummary]) -> list[str]:
    present = {c for s in summaries for c in s.category_scores}
    return [c for c in CATEGORY_WEIGHTS if c in present]


def write_reports(
    output_dir: str | Path,
    summaries: list[ModelSummary],
    records: list[RunRecord],
    run_info: dict[str, Any],
) -> Path:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    _write_comparison_table(output / "comparison_table.md", summaries, run_info)
    _write_detailed_csv(output / "detailed_results.csv", records)
    _write_summary_report(output / "summary_report.md", summaries, records, run_info)
    _write_results_json(output / "results.json", summaries, records, run_info)
    return output


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def _write_comparison_table(path: Path, summaries: list[ModelSummary], run_info: dict[str, Any]) -> None:
    categories = _ordered_categories(summaries)
    headers = ["Rank", "Model", "Global Score"] + [
        f"{_CATEGORY_LABELS[c]} ({CATEGORY_WEIGHTS[c]:.0%})" for c in categories
    ]
    rows = []
    for rank, summary in enumerate(summaries, start=1):
        medal = {1: " 🥇", 2: " 🥈", 3: " 🥉"}.get(rank, "")
        rows.append(
            [str(rank), f"**{summary.model}**{medal}", f"**{summary.global_score:.1f}**"]
            + [f"{summary.category_scores.get(c, 0):.1f}" for c in categories]
        )
    content = (
        f"# LLM Observability Benchmark — Comparison\n\n"
        f"Generated: {run_info['timestamp']}  \n"
        f"Runs per test: {run_info['runs_per_test']} · Models: {run_info['n_models']} · "
        f"Test cases: {run_info['n_cases']}\n\n"
        f"All scores are 0-100. The global score is the weighted average of the category scores.\n\n"
        + _md_table(headers, rows)
        + "\n"
    )
    path.write_text(content, encoding="utf-8")


def _write_detailed_csv(path: Path, records: list[RunRecord]) -> None:
    rows = [
        {
            "model": r.model,
            "category": r.category,
            "case_id": r.case_id,
            "run_index": r.run_index,
            "score": round(100 * r.score, 2),
            "latency_s": round(r.latency_s, 3),
            "input_tokens": r.input_tokens,
            "output_tokens": r.output_tokens,
            "cached": r.cached,
            "error": r.error or "",
            "metrics": json.dumps({k: round(v, 4) for k, v in r.metrics.items()}),
        }
        for r in records
    ]
    pd.DataFrame(rows).to_csv(path, index=False)


def _write_summary_report(
    path: Path,
    summaries: list[ModelSummary],
    records: list[RunRecord],
    run_info: dict[str, Any],
) -> None:
    categories = _ordered_categories(summaries)
    lines = [
        "# LLM Observability Benchmark — Summary Report",
        "",
        f"Generated: {run_info['timestamp']}",
        "",
        "## Overall Ranking",
        "",
    ]
    for rank, summary in enumerate(summaries, start=1):
        lines.append(
            f"{rank}. **{summary.model}** — global score {summary.global_score:.1f}/100 "
            f"({summary.error_count}/{summary.total_runs} failed runs)"
        )

    lines += ["", "## Category Leaders", ""]
    for category in categories:
        ranked = sorted(
            (s for s in summaries if category in s.category_scores),
            key=lambda s: s.category_scores[category],
            reverse=True,
        )
        if not ranked:
            continue
        leader = ranked[0]
        runner_up = (
            f" (next: {ranked[1].model} at {ranked[1].category_scores[category]:.1f})"
            if len(ranked) > 1
            else ""
        )
        lines.append(
            f"- **{_CATEGORY_LABELS[category]}**: {leader.model} "
            f"with {leader.category_scores[category]:.1f}{runner_up}"
        )

    lines += ["", "## Efficiency Details", ""]
    for summary in summaries:
        m = summary.efficiency_metrics
        if not m:
            continue
        tokens = f"{m['avg_total_tokens']:.0f}" if m.get("avg_total_tokens", -1) >= 0 else "n/a"
        lines.append(
            f"- **{summary.model}**: avg latency {m.get('avg_latency_s', 0):.2f}s, "
            f"avg tokens/call {tokens}, "
            f"score stddev across runs {m.get('score_stddev', 0):.1f} points"
        )

    error_records = [r for r in records if r.error is not None]
    lines += ["", "## Reliability", ""]
    if error_records:
        by_model_errors: dict[str, int] = defaultdict(int)
        for r in error_records:
            by_model_errors[r.model] += 1
        for model, count in sorted(by_model_errors.items(), key=lambda kv: -kv[1]):
            lines.append(f"- {model}: {count} failed run(s) (API errors or invalid JSON output)")
    else:
        lines.append("- All runs completed and produced parseable, schema-valid JSON.")

    lines += ["", "## Recommendations", ""]
    if summaries:
        best = summaries[0]
        lines.append(
            f"- **{best.model}** is the strongest overall pick for log/metrics analysis workloads "
            f"in this run (global score {best.global_score:.1f})."
        )
        for category in categories:
            ranked = sorted(summaries, key=lambda s: s.category_scores.get(category, 0), reverse=True)
            if ranked and ranked[0].model != best.model:
                lines.append(
                    f"- For **{_CATEGORY_LABELS[category].lower()}** specifically, consider "
                    f"**{ranked[0].model}** ({ranked[0].category_scores[category]:.1f} vs "
                    f"{best.category_scores.get(category, 0):.1f})."
                )
        flaky = [s for s in summaries if s.efficiency_metrics.get("score_stddev", 0) > 10]
        for s in flaky:
            lines.append(
                f"- **{s.model}** shows high run-to-run variance "
                f"(stddev {s.efficiency_metrics['score_stddev']:.1f} points); "
                f"pin temperature to 0 or increase runs_per_test before trusting its scores."
            )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_results_json(
    path: Path,
    summaries: list[ModelSummary],
    records: list[RunRecord],
    run_info: dict[str, Any],
) -> None:
    payload = {
        "run_info": run_info,
        "summaries": [
            {
                "model": s.model,
                "global_score": round(s.global_score, 2),
                "category_scores": {k: round(v, 2) for k, v in s.category_scores.items()},
                "efficiency_metrics": {k: round(v, 4) for k, v in s.efficiency_metrics.items()},
                "error_count": s.error_count,
                "total_runs": s.total_runs,
            }
            for s in summaries
        ],
        "records": [
            {
                "model": r.model,
                "category": r.category,
                "case_id": r.case_id,
                "run_index": r.run_index,
                "score": round(100 * r.score, 2),
                "metrics": r.metrics,
                "latency_s": round(r.latency_s, 3),
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                "cached": r.cached,
                "error": r.error,
            }
            for r in records
        ],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def make_run_info(config_runs: int, n_models: int, n_cases: int) -> dict[str, Any]:
    return {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "runs_per_test": config_runs,
        "n_models": n_models,
        "n_cases": n_cases,
    }
