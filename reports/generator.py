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
from collections import Counter, defaultdict
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
    refused_count: int = 0  # runs the model declined; scored 0, not failures
    total_runs: int = 0
    total_duration_s: float | None = None   # Wall-clock time to complete the full set for this model
    total_cost_usd: float | None = None     # Sum of per-call cost; None when the model has no pricing


# model name -> (input price, output price) in USD per 1,000,000 tokens.
Pricing = dict[str, tuple[float, float]]


def aggregate(records: list[RunRecord], pricing: Pricing | None = None) -> list[ModelSummary]:
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

        # Duration = sum of per-call model latencies. Cached records keep the
        # latency originally measured, so this stays correct across partial
        # re-runs and retries — unlike last-run wall-clock, which collapses to
        # seconds when a re-run mostly hits the cache.
        total_latency = sum(r.latency_s for r in model_records)

        # Total cost = sum over calls of (in_tokens * in_price + out_tokens *
        # out_price) / 1e6. Only computed when this model has pricing configured.
        total_cost: float | None = None
        if pricing and model in pricing:
            price_in, price_out = pricing[model]
            total_cost = sum(
                (r.input_tokens or 0) * price_in + (r.output_tokens or 0) * price_out
                for r in model_records
            ) / 1_000_000

        summaries.append(
            ModelSummary(
                model=model,
                category_scores=category_scores,
                global_score=global_score,
                efficiency_metrics=efficiency.metrics,
                error_count=sum(1 for r in model_records if r.error is not None),
                refused_count=sum(1 for r in model_records if r.refused),
                total_runs=len(model_records),
                total_duration_s=total_latency,
                total_cost_usd=total_cost,
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
    merge: bool = True,
) -> Path:
    """Persist results for a single model into its own folder.

    Creates: <base_dir>/<model>/records.json
    Also writes a small summary.json for convenience.

    By default (``merge=True``) the new records are merged into whatever is
    already stored for this model: new records replace existing ones for the
    same ``(category, case_id, run_index)``, while other runs are kept. Re-running
    one failed slot therefore does not wipe sibling successes on the same case.
    Pass ``merge=False`` to overwrite the folder with only ``records``.
    """
    base = Path(base_dir)
    model_dir = base / model
    model_dir.mkdir(parents=True, exist_ok=True)

    if merge:
        existing = load_model_records(base, model)
        refreshed = {(r.category, r.case_id, r.run_index) for r in records}
        records = [
            r for r in existing if (r.category, r.case_id, r.run_index) not in refreshed
        ] + list(records)

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
            summary_payload = {
                "model": s.model,
                "global_score": round(s.global_score, 2),
                "category_scores": {k: round(v, 2) for k, v in s.category_scores.items()},
                "efficiency_metrics": {k: round(v, 4) for k, v in s.efficiency_metrics.items()},
                "error_count": s.error_count,
                "refused_count": s.refused_count,
                "total_runs": s.total_runs,
                # Stable across cached re-runs (sum of per-call latencies).
                "total_duration_s": round(s.total_duration_s, 2) if s.total_duration_s is not None else None,
                # Wall-clock of the most recent run only — informational.
                "last_run_wall_clock_s": round(total_duration_s, 2) if total_duration_s is not None else None,
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
    pricing: Pricing | None = None,
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

    summaries = aggregate(all_records, pricing)

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
    "multimodal_rca": "Multi-modal RCA",
    "efficiency": "Efficiency & Consistency",
}

# One line per task category: what capability it probes and how it's scored.
_CATEGORY_DESCRIPTIONS = {
    "log_parsing": "Turning raw log lines into templates (variables masked). "
    "Score = 0.5 exact-template accuracy + 0.5 token-level F1 vs ground-truth templates.",
    "anomaly_detection": "Flagging which log lines are anomalous. "
    "Precision/recall/F1 over per-line labels vs the ground truth.",
    "pattern_correlation": "Identifying recurring event patterns and cause→effect "
    "links between them.",
    "metrics_timeseries": "Spotting anomalies in a numeric metric series. "
    "Point-wise precision/recall/F1 with a ±1-index tolerance.",
    "root_cause": "Explaining the incident. 0.4 ROUGE-L on the summary + 0.3 ROUGE-1 "
    "on the root cause + 0.3 keyword recall of the key entities.",
    "multimodal_rca": "Localizing the culprit service across metrics, logs and traces "
    "on real microservice incidents. 0.4 culprit + 0.25 fault type + 0.25 modality "
    "grounding (citing the modalities that actually carry signal) + 0.1 evidence recall.",
    "efficiency": "Derived from the runs above, not a dataset. 0.4 speed (vs a 20s "
    "budget) + 0.3 token thrift (vs 4000 tokens) + 0.3 run-to-run score stability.",
}


def _column_legend(categories: list[str], show_cost: bool) -> str:
    """Markdown section explaining every column in the comparison table."""
    lines = [
        "## What each column measures",
        "",
        "Scores are 0–100, higher is better. **Duration** and **Cost** are lower-is-better.",
        "",
        "- **Rank** — position among models that ran the full category set, best Global Score first "
        "(🥇🥈🥉 mark the top three). Partial or all-failed models are listed separately below and not ranked.",
        "- **Model** — the model's name as configured in `models.json`.",
        "- **Global Score** — the headline quality number: the weighted average of the category "
        "columns, using the weights shown in each header. Only categories the model actually ran count "
        "(weights renormalize), so a partial run still yields a 0–100 value — which is why partial runs "
        "aren't ranked against full ones.",
    ]
    for category in categories:
        label = _CATEGORY_LABELS.get(category, category)
        weight = CATEGORY_WEIGHTS.get(category)
        weight_str = f" ({weight:.0%} of Global Score)" if weight is not None else ""
        desc = _CATEGORY_DESCRIPTIONS.get(category, "")
        lines.append(f"- **{label}**{weight_str} — {desc}")
    lines.append(
        "- **Duration** — total model time to run this model's whole set: the sum of every call's "
        "measured latency across all cases and runs. It is *not* wall-clock — cached calls keep their "
        "originally measured latency, so it stays stable across re-runs."
    )
    if show_cost:
        lines.append(
            "- **Cost** — total USD to run this model's whole set at provider list price: "
            "Σ(input_tokens × input_price + output_tokens × output_price) ÷ 1,000,000. It counts every "
            "call (including cached ones) — it's the cost of *running the benchmark*, not your actual "
            "billed amount. Self-hosted/local models show `$0.00`; models with no price configured show `—`."
        )
    lines.append("")
    return "\n".join(lines)


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


def _fmt_cost(cost: Any) -> str:
    if cost is None:
        return "—"
    if cost == 0:
        return "$0.00"
    if cost < 0.01:
        return "<$0.01"
    return f"${cost:,.2f}"


def build_pricing(models: Any) -> Pricing:
    """Build a name -> (input, output) price map from configured models.

    Only models with both prices set are included; everything else is left out
    and will show "—" (uncosted) in the reports.
    """
    pricing: Pricing = {}
    for m in models:
        if m.price_input is not None and m.price_output is not None:
            pricing[m.name] = (m.price_input, m.price_output)
    return pricing


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


@dataclass
class CaseGap:
    case_id: str
    failed_indices: list[int]
    kinds: dict[str, int]
    total_runs: int

    def label(self) -> str:
        if len(self.failed_indices) >= self.total_runs:
            return self.case_id
        return f"{self.case_id}#{','.join(str(i) for i in self.failed_indices)}"


@dataclass
class CategoryGap:
    category: str
    failed_runs: int
    kinds: dict[str, int]
    cases: list[CaseGap]
    universe_size: int


@dataclass
class ModelGap:
    model: str
    total_runs: int
    failed_runs: int
    refused_runs: int
    missing_by_category: dict[str, list[str]]
    categories: list[CategoryGap]
    refused_categories: list[CategoryGap]


def _error_kind(error: str) -> str:
    lowered = error.lower()
    if error.startswith("skipped:"):
        return "skipped"
    if "refused" in lowered or "declined the prompt" in lowered:
        # Records stored before refusals became a scored outcome.
        return "refusal"
    if "empty response" in lowered:
        return "empty response"
    if any(token in lowered for token in ("unbalanced json", "jsondecode", "no json", "expecting value")):
        return "invalid JSON"
    for code in ("401", "403", "404", "429", "400", "500", "502", "503"):
        if f"http {code}" in lowered:
            return f"HTTP {code}"
    return error.split(":", 1)[0][:40]


def _category_gaps(
    recs: list[RunRecord],
    universe: dict[str, set[str]],
    runs_per_case: dict[tuple[str, str], int],
    kind_of: Any,
) -> list[CategoryGap]:
    by_category: dict[str, list[RunRecord]] = defaultdict(list)
    for record in recs:
        by_category[record.category].append(record)

    gaps: list[CategoryGap] = []
    for category, cat_recs in sorted(by_category.items()):
        by_case: dict[str, list[RunRecord]] = defaultdict(list)
        for record in cat_recs:
            by_case[record.case_id].append(record)
        cases = [
            CaseGap(
                case_id=case_id,
                failed_indices=sorted(r.run_index for r in case_recs),
                kinds=dict(Counter(kind_of(r) for r in case_recs)),
                total_runs=runs_per_case[(category, case_id)],
            )
            for case_id, case_recs in sorted(by_case.items())
        ]
        gaps.append(
            CategoryGap(
                category=category,
                failed_runs=len(cat_recs),
                kinds=dict(Counter(kind_of(r) for r in cat_recs)),
                cases=cases,
                universe_size=len(universe[category]),
            )
        )
    return gaps


def analyze_coverage(records: list[RunRecord]) -> list[ModelGap]:
    """Per-model failures, refusals, and cases this model never ran."""
    universe: dict[str, set[str]] = defaultdict(set)
    by_model: dict[str, list[RunRecord]] = defaultdict(list)
    for record in records:
        universe[record.category].add(record.case_id)
        by_model[record.model].append(record)

    gaps: list[ModelGap] = []
    for model, recs in by_model.items():
        present = {(r.category, r.case_id) for r in recs}
        missing: dict[str, list[str]] = {}
        for category, case_ids in universe.items():
            absent = sorted(cid for cid in case_ids if (category, cid) not in present)
            if absent:
                missing[category] = absent

        failed = [r for r in recs if r.error]
        refused = [r for r in recs if r.refused]
        if not failed and not refused and not missing:
            continue

        runs_per_case: dict[tuple[str, str], int] = Counter(
            (r.category, r.case_id) for r in recs
        )
        gaps.append(
            ModelGap(
                model=model,
                total_runs=len(recs),
                failed_runs=len(failed),
                refused_runs=len(refused),
                missing_by_category=missing,
                categories=_category_gaps(
                    failed, universe, runs_per_case, lambda r: _error_kind(r.error or "")
                ),
                refused_categories=_category_gaps(
                    refused, universe, runs_per_case, lambda r: f"{r.refused} refusal"
                ),
            )
        )

    gaps.sort(
        key=lambda g: (
            -g.failed_runs,
            -g.refused_runs,
            -sum(len(v) for v in g.missing_by_category.values()),
            g.model,
        )
    )
    return gaps


def _format_kinds(kinds: dict[str, int]) -> str:
    return ", ".join(f"{count} {kind}" for kind, count in kinds.items())


def _format_category_gap(gap: CategoryGap, prefix: str = "", max_cases: int = 8) -> str:
    kinds = _format_kinds(gap.kinds)
    whole_category = (
        len(gap.cases) == gap.universe_size
        and all(len(c.failed_indices) >= c.total_runs for c in gap.cases)
    )
    if whole_category and len(gap.kinds) == 1:
        kind = next(iter(gap.kinds))
        return f"{prefix}{gap.category} ({gap.failed_runs}): all {gap.universe_size} cases {kind}"
    labels = [c.label() for c in gap.cases]
    if len(labels) > max_cases:
        cases = f"{', '.join(labels[:max_cases])} +{len(labels) - max_cases} more"
    else:
        cases = ", ".join(labels)
    return f"{prefix}{gap.category} ({gap.failed_runs}): {kinds} — {cases}"


def format_coverage_lines(records: list[RunRecord]) -> list[str]:
    """Plain-text recap of failed / refused / missing runs, one model at a time."""
    gaps = analyze_coverage(records)
    if not gaps:
        return []
    failed = sum(1 for r in records if r.error is not None)
    refused = sum(1 for r in records if r.refused)
    headline = f"{failed}/{len(records)} runs failed"
    if refused:
        headline += f", {refused} declined by the model (scored 0)"
    lines = [f"Coverage gaps — {headline}:"]
    for gap in gaps:
        parts = [f"{gap.failed_runs}/{gap.total_runs} failed"]
        if gap.refused_runs:
            parts.append(f"{gap.refused_runs} declined")
        if gap.missing_by_category:
            never = ", ".join(
                f"{cat} ({len(ids)} cases)"
                for cat, ids in sorted(gap.missing_by_category.items())
            )
            parts.append(f"never ran {never}")
        lines.append(f"  {gap.model} — {'; '.join(parts)}")
        for category in gap.categories:
            lines.append(f"    {_format_category_gap(category)}")
        for category in gap.refused_categories:
            lines.append(f"    {_format_category_gap(category, prefix='declined ')}")
    return lines


def _write_comparison_table(path: Path, summaries: list[ModelSummary], run_info: dict[str, Any]) -> None:
    categories = _ordered_categories(summaries)
    ranked, partial, failed, expected = classify_summaries(summaries)

    show_cost = any(s.total_cost_usd is not None for s in ranked)
    headers = ["Rank", "Model", "Global Score"] + [
        f"{_CATEGORY_LABELS[c]} ({CATEGORY_WEIGHTS[c]:.0%})" for c in categories
    ] + ["Duration"] + (["Cost"] if show_cost else [])
    rows = []
    for rank, summary in enumerate(ranked, start=1):
        medal = {1: " 🥇", 2: " 🥈", 3: " 🥉"}.get(rank, "")
        rows.append(
            [str(rank), f"**{summary.model}**{medal}", f"**{summary.global_score:.1f}**"]
            + [f"{summary.category_scores.get(c, 0):.1f}" for c in categories]
            + [_fmt_duration(summary.total_duration_s)]
            + ([_fmt_cost(summary.total_cost_usd)] if show_cost else [])
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
    content += "\n" + _column_legend(categories, show_cost)
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
            "refused": r.refused or "",
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
        declined = (
            f", {summary.refused_count} declined" if summary.refused_count else ""
        )
        lines.append(
            f"{rank}. **{summary.model}** — global score {summary.global_score:.1f}/100 "
            f"({summary.error_count}/{summary.total_runs} failed runs{declined}){dur_str}"
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

    coverage_lines = format_coverage_lines(records)
    lines += ["", "## Reliability", ""]
    if coverage_lines:
        lines.extend(coverage_lines)
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
                "refused_count": s.refused_count,
                "total_runs": s.total_runs,
                "total_duration_s": round(s.total_duration_s, 2) if s.total_duration_s is not None else None,
                "total_cost_usd": round(s.total_cost_usd, 4) if s.total_cost_usd is not None else None,
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
                "refused": r.refused,
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
