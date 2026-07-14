"""Aggregation and report generation (markdown, CSV, JSON).

Supports two modes:
- Traditional: write everything into one flat directory.
- New recommended: per-model folders under the base results directory so you
  can run models one-by-one (or on different machines) and later regenerate
  the cross-model comparison reports.
"""

from __future__ import annotations

import itertools
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
    total_duration_s: float | None = None   # Wall-clock time to complete the full set for this model


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

        # Compute total observed LLM time as fallback when no wall-clock duration is stored
        total_latency = sum(r.latency_s for r in model_records)

        summaries.append(
            ModelSummary(
                model=model,
                category_scores=category_scores,
                global_score=global_score,
                efficiency_metrics=efficiency.metrics,
                error_count=sum(1 for r in model_records if r.error is not None),
                total_runs=len(model_records),
                total_duration_s=total_latency,  # will be overridden by stored wall time if available
            )
        )

    summaries.sort(key=lambda s: s.global_score, reverse=True)
    return summaries


# ---------------------------------------------------------------------------
# Per-model storage (enables running models independently and aggregating later)
# ---------------------------------------------------------------------------

MODEL_RESULTS_SUBDIR = "_"  # sentinel to avoid treating special dirs as models


def _is_model_dir(path: Path) -> bool:
    """A directory is considered a model result dir if it contains records.json."""
    return (path / "records.json").exists()


def save_model_results(
    base_dir: str | Path,
    model: str,
    records: list[RunRecord],
    run_info: dict[str, Any] | None = None,
    total_duration_s: float | None = None,
) -> Path:
    """Persist results for a single model into its own folder.

    Creates: <base_dir>/<model>/records.json
    Also writes a small summary.json for convenience.
    """
    base = Path(base_dir)
    model_dir = base / model
    model_dir.mkdir(parents=True, exist_ok=True)

    # Save raw records (source of truth)
    records_payload = [r.to_dict() for r in records]
    (model_dir / "records.json").write_text(
        json.dumps(records_payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Compute and save a per-model summary
    if records:
        model_summaries = aggregate(records)  # will only contain this model
        if model_summaries:
            s = model_summaries[0]
            # Prefer explicitly measured wall-clock duration over sum of latencies
            duration = total_duration_s if total_duration_s is not None else s.total_duration_s
            summary_payload = {
                "model": s.model,
                "global_score": round(s.global_score, 2),
                "category_scores": {k: round(v, 2) for k, v in s.category_scores.items()},
                "efficiency_metrics": {k: round(v, 4) for k, v in s.efficiency_metrics.items()},
                "error_count": s.error_count,
                "total_runs": s.total_runs,
                "total_duration_s": round(duration, 2) if duration is not None else None,
            }
            (model_dir / "summary.json").write_text(
                json.dumps(summary_payload, indent=2, ensure_ascii=False), encoding="utf-8"
            )

    if run_info:
        (model_dir / "run_info.json").write_text(
            json.dumps(run_info, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    return model_dir


def load_model_records(base_dir: str | Path, model: str) -> list[RunRecord]:
    """Load records for one specific model from its folder."""
    base = Path(base_dir)
    records_path = base / model / "records.json"
    if not records_path.exists():
        return []
    with open(records_path, encoding="utf-8") as f:
        raw = json.load(f)
    return [RunRecord.from_dict(item) for item in raw]


def load_model_duration(base_dir: str | Path, model: str) -> float | None:
    """Load the stored total wall-clock duration for a model, if available."""
    base = Path(base_dir)
    summary_path = base / model / "summary.json"
    if summary_path.exists():
        try:
            with open(summary_path, encoding="utf-8") as f:
                data = json.load(f)
            dur = data.get("total_duration_s")
            if dur is not None:
                return float(dur)
        except Exception:
            pass
    return None


def discover_model_dirs(base_dir: str | Path) -> list[str]:
    """Return model names that have stored results under base_dir."""
    base = Path(base_dir)
    if not base.exists():
        return []
    models = []
    for child in sorted(base.iterdir()):
        if child.is_dir() and child.name not in {"_", "aggregate"} and _is_model_dir(child):
            models.append(child.name)
    return models


def load_all_model_records(base_dir: str | Path) -> list[RunRecord]:
    """Load and combine records from all per-model folders under base_dir.

    Falls back to the legacy flat results.json if no per-model folders exist
    (for smooth transition from older runs).
    """
    records: list[RunRecord] = []
    models = discover_model_dirs(base_dir)
    for model in models:
        records.extend(load_model_records(base_dir, model))

    if not records:
        # Legacy fallback: try top-level results.json
        legacy = Path(base_dir) / "results.json"
        if legacy.exists():
            try:
                with open(legacy, encoding="utf-8") as f:
                    payload = json.load(f)
                raw_records = payload.get("records", [])
                for item in raw_records:
                    rec = RunRecord.from_dict(item)
                    # Legacy files stored display scores (0-100). Normalize to internal 0-1.
                    if rec.score > 1.5:   # heuristic: clearly on 0-100 scale
                        rec.score = rec.score / 100.0
                        # Also scale metrics that are percentages if they look like it
                        for k in list(rec.metrics.keys()):
                            if rec.metrics[k] > 1.5:
                                rec.metrics[k] = rec.metrics[k] / 100.0
                    records.append(rec)
            except Exception:
                pass
    return records


def write_aggregated_reports(
    base_dir: str | Path,
    extra_run_info: dict[str, Any] | None = None,
) -> Path:
    """Load records from all per-model folders, aggregate, and write the
    top-level comparison reports (comparison_table.md, etc.).

    This is the function you call to "rebuild the report" after running
    models individually.
    """
    base = Path(base_dir)
    base.mkdir(parents=True, exist_ok=True)

    all_records = load_all_model_records(base)

    if not all_records:
        # Nothing to do
        return base

    # If we loaded from legacy flat files, seed per-model folders for future use
    existing_models = set(discover_model_dirs(base))
    loaded_models = {r.model for r in all_records}
    for model in loaded_models:
        if model not in existing_models:
            model_recs = [r for r in all_records if r.model == model]
            save_model_results(base, model, model_recs)

    summaries = aggregate(all_records)

    # Override with stored wall-clock durations (more accurate than sum of per-call latencies)
    for s in summaries:
        stored = load_model_duration(base, s.model)
        if stored is not None:
            s.total_duration_s = stored

    # Build a reasonable run_info
    n_models = len({r.model for r in all_records})
    n_cases = len({(r.category, r.case_id) for r in all_records})
    # Try to infer runs_per_test from the data (most common value)
    sorted_for_runs = sorted(all_records, key=lambda r: (r.model, r.category, r.case_id))
    runs_counts = [len(list(g)) for _, g in itertools.groupby(
        sorted_for_runs, key=lambda r: (r.model, r.category, r.case_id)
    )]
    runs_per_test = max(runs_counts) if runs_counts else 3

    run_info = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "runs_per_test": runs_per_test,
        "n_models": n_models,
        "n_cases": n_cases,
    }
    if extra_run_info:
        run_info.update(extra_run_info)

    # Write the usual top-level artifacts
    _write_comparison_table(base / "comparison_table.md", summaries, run_info)
    _write_detailed_csv(base / "detailed_results.csv", all_records)
    _write_summary_report(base / "summary_report.md", summaries, all_records, run_info)
    _write_results_json(base / "results.json", summaries, all_records, run_info)

    return base


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
    """Legacy-friendly entry point.

    - Saves per-model records into results/<model>/ (so future aggregation works)
    - Then writes the usual top-level aggregated reports.
    """
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    # Always persist per-model data (this is the new canonical storage)
    by_model: dict[str, list[RunRecord]] = defaultdict(list)
    for r in records:
        by_model[r.model].append(r)

    for model, model_records in by_model.items():
        save_model_results(output, model, model_records, run_info)

    # Write the combined view at the root
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


def _fmt_duration(dur: Any) -> str:
    if dur is None:
        return "—"
    if dur >= 60:
        return f"{int(dur // 60)}m {int(dur % 60)}s"
    if dur > 0.05:
        return f"{dur:.1f}s"
    return "<0.1s"


def _task_categories(summary: ModelSummary) -> set[str]:
    return {
        c for c in summary.category_scores if c in CATEGORY_WEIGHTS and c != "efficiency"
    }


def classify_summaries(
    summaries: list[ModelSummary],
) -> tuple[list[ModelSummary], list[ModelSummary], list[ModelSummary], set[str]]:
    """Split models into (ranked, partial, failed, expected_categories).

    Only models that ran the full set of categories present in this benchmark
    are ranked against each other — a model that ran just one category would
    otherwise get a misleadingly high global score (its weights renormalize
    over the subset it ran). `expected` is the union of task categories any
    model produced data for.
    """
    expected: set[str] = set()
    for s in summaries:
        expected |= _task_categories(s)

    ranked, partial, failed = [], [], []
    for s in summaries:
        if s.error_count >= s.total_runs:
            failed.append(s)
        elif _task_categories(s) >= expected:
            ranked.append(s)
        else:
            partial.append(s)
    return ranked, partial, failed, expected


def _write_comparison_table(path: Path, summaries: list[ModelSummary], run_info: dict[str, Any]) -> None:
    categories = _ordered_categories(summaries)
    ranked, partial, failed, expected = classify_summaries(summaries)

    headers = ["Rank", "Model", "Global Score"] + [
        f"{_CATEGORY_LABELS[c]} ({CATEGORY_WEIGHTS[c]:.0%})" for c in categories
    ] + ["Duration"]
    rows = []
    for rank, summary in enumerate(ranked, start=1):
        medal = {1: " 🥇", 2: " 🥈", 3: " 🥉"}.get(rank, "")
        rows.append(
            [str(rank), f"**{summary.model}**{medal}", f"**{summary.global_score:.1f}**"]
            + [f"{summary.category_scores.get(c, 0):.1f}" for c in categories]
            + [_fmt_duration(summary.total_duration_s)]
        )
    content = (
        f"# LLM Observability Benchmark — Comparison\n\n"
        f"Generated: {run_info['timestamp']}  \n"
        f"Runs per test: {run_info['runs_per_test']} · Models: {run_info['n_models']} · "
        f"Test cases: {run_info['n_cases']}\n\n"
        f"All scores are 0-100. The global score is the weighted average of the category scores. "
        f"Only models that ran the full category set are ranked.\n\n"
        + _md_table(headers, rows)
        + "\n"
    )
    if partial:
        content += (
            "\n**Incomplete coverage** (ran only some categories — not ranked, because a "
            "partial run's global score isn't comparable). Re-run the full suite for these:\n\n"
        )
        for s in partial:
            covered = sorted(_task_categories(s))
            content += f"- {s.model} — ran only: {', '.join(covered) or 'none'}\n"
    if failed:
        content += "\n**Did not complete** (every call failed — bad key, no model access, or unreachable endpoint):\n\n"
        content += "\n".join(f"- {s.model} ({s.total_runs} calls failed)" for s in failed)
        content += "\n"
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
        dur = summary.total_duration_s
        dur_str = ""
        if dur is not None:
            if dur >= 60:
                dur_str = f" — completed in {int(dur // 60)}m {int(dur % 60)}s"
            elif dur > 0.05:
                dur_str = f" — completed in {dur:.1f}s"
            else:
                dur_str = " — completed in <0.1s"
        lines.append(
            f"{rank}. **{summary.model}** — global score {summary.global_score:.1f}/100 "
            f"({summary.error_count}/{summary.total_runs} failed runs){dur_str}"
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
        dur = summary.total_duration_s
        dur_part = ""
        if dur is not None:
            if dur >= 60:
                dur_part = f", full set: {int(dur // 60)}m {int(dur % 60)}s"
            elif dur > 0.05:
                dur_part = f", full set: {dur:.1f}s"
            else:
                dur_part = ", full set: <0.1s"

        if not m:
            if dur_part:
                lines.append(f"- **{summary.model}**:{dur_part}")
            continue
        tokens = f"{m['avg_total_tokens']:.0f}" if m.get("avg_total_tokens", -1) >= 0 else "n/a"
        lines.append(
            f"- **{summary.model}**: avg latency {m.get('avg_latency_s', 0):.2f}s, "
            f"avg tokens/call {tokens}, "
            f"score stddev across runs {m.get('score_stddev', 0):.1f} points{dur_part}"
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
                "total_duration_s": round(s.total_duration_s, 2) if s.total_duration_s is not None else None,
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
