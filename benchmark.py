"""LLM Observability Benchmark Suite — CLI entry point.

Usage (recommended workflow for running models one at a time):

    # Run models independently (results go to results/<model>/)
    python benchmark.py run -m grok-4
    python benchmark.py run -m claude-opus-4-8
    python benchmark.py run -m llama-3.3-70b --runs 1

    # Rebuild the combined comparison table + reports from all model folders
    python benchmark.py aggregate

Other examples:
    python benchmark.py run --category anomaly_detection
    python benchmark.py run --config models.mock.json   # offline smoke test
    python benchmark.py list-categories
    python benchmark.py list-models
    python benchmark.py clear-cache -m grok-4
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from core.config import CATEGORY_WEIGHTS, TASK_CATEGORIES, BenchmarkConfig
from core.runner import BenchmarkRunner, RunRecord
from datasets.loaders import load_datasets
from reports.generator import (
    aggregate,
    classify_summaries,
    load_all_model_records,
    load_model_duration,
    make_run_info,
    save_model_results,
    write_aggregated_reports,
    write_reports,
    _task_categories,
)

from core.cache import ResponseCache

app = typer.Typer(help="Benchmark LLMs on log analysis, anomaly detection, and SRE tasks.")
console = Console()


@app.command()
def run(
    config_path: Path = typer.Option("models.json", "--config", help="Config file (models.json)."),
    categories: Optional[list[str]] = typer.Option(
        None, "--category", "-c", help="Run only these categories (repeatable)."
    ),
    models: Optional[list[str]] = typer.Option(
        None, "--model", "-m", help="Run only these models by name (repeatable)."
    ),
    runs: Optional[int] = typer.Option(None, "--runs", help="Override runs_per_test."),
    retries: int = typer.Option(
        1,
        "--retries",
        help="Extra passes to re-attempt transiently-failed runs (401/timeout/5xx/bad JSON). 0 disables.",
        min=0,
    ),
    no_cache: bool = typer.Option(False, "--no-cache", help="Bypass the response cache."),
    output_dir: Path = typer.Option("results", "--output-dir", "-o", help="Report directory."),
    data_dir: Optional[Path] = typer.Option(
        None, "--data-dir", help="Alternative dataset directory (same file names)."
    ),
) -> None:
    """Run the benchmark and write reports to the results directory."""
    config = BenchmarkConfig.load(config_path)
    if runs is not None:
        config.runs_per_test = runs

    selected_categories = categories or TASK_CATEGORIES
    invalid = [c for c in selected_categories if c not in TASK_CATEGORIES]
    if invalid:
        console.print(f"[red]Unknown categories: {invalid}. Valid: {TASK_CATEGORIES}[/red]")
        raise typer.Exit(code=1)

    if models:
        known = {m.name for m in config.models}
        missing = [m for m in models if m not in known]
        if missing:
            console.print(f"[red]Unknown models: {missing}. Configured: {sorted(known)}[/red]")
            raise typer.Exit(code=1)

    datasets = load_datasets(selected_categories, data_dir)
    n_cases = sum(len(cases) for cases in datasets.values())

    # Skip models whose provider requires an API key that isn't configured,
    # so a missing key never aborts (or pollutes) the whole run. Local
    # OpenAI-compatible servers (LM Studio, vLLM, llama.cpp — plain http)
    # don't need a key, so only https endpoints are gated.
    model_names = []
    skipped = []
    for name in models or [m.name for m in config.models]:
        model_config = config.get_model(name)
        needs_key = (
            model_config.provider in ("openai", "xai", "anthropic")
            and not (model_config.base_url or "https://").startswith("http://")
        )
        if needs_key and not model_config.api_key:
            skipped.append(name)
        else:
            model_names.append(name)
    if skipped:
        console.print(
            f"[yellow]Skipping (no API key configured): {', '.join(skipped)} — "
            f"set the key in .env or remove the model from {config_path}[/yellow]"
        )
    if not model_names:
        console.print("[red]No runnable models: every selected model is missing its API key.[/red]")
        raise typer.Exit(code=1)

    total = BenchmarkRunner.total_tasks(config, datasets, model_names)

    console.print(
        f"\n[bold]LLM Observability Benchmark[/bold] — "
        f"{len(model_names)} model(s) x {n_cases} case(s) x {config.runs_per_test} run(s) "
        f"= {total} calls\n"
    )

    runner = BenchmarkRunner(config, use_cache=not no_cache)
    records: list[RunRecord] = []
    model_durations: dict[str, float] = {}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Benchmarking...", total=total)
        seen_keys: set[tuple] = set()

        def on_record(record: RunRecord) -> None:
            status = "[red]ERR[/red]" if record.error else f"{100 * record.score:5.1f}"
            cached = " [dim](cached)[/dim]" if record.cached else ""
            key = (record.model, record.category, record.case_id, record.run_index)
            # First sighting advances the bar; a repeat is a retry pass — relabel
            # without advancing, so the counter stays within the planned total.
            is_retry = key in seen_keys
            seen_keys.add(key)
            tag = " [yellow](retry)[/yellow]" if is_retry else ""
            progress.update(
                task,
                advance=0 if is_retry else 1,
                description=(
                    f"{record.model} · {record.category} · {record.case_id} "
                    f"#{record.run_index} → {status}{cached}{tag}"
                ),
            )

        records, model_durations = runner.run(
            datasets, model_names, on_record=on_record, retry_failed=retries
        )

    # 1. Persist the models we just ran into their own folders
    #    (this enables running one model at a time across multiple sessions)
    for model_name in sorted({r.model for r in records}):
        model_recs = [r for r in records if r.model == model_name]
        duration = model_durations.get(model_name)
        save_model_results(output_dir, model_name, model_recs, total_duration_s=duration)

    # 2. Rebuild the cross-model comparison from *all* available per-model folders
    #    (merges newly run models with any previously saved ones)
    all_records = load_all_model_records(output_dir) or records
    summaries = aggregate(all_records)

    # Enrich with stored wall-clock durations (more accurate than sum of per-call latencies)
    for s in summaries:
        stored = load_model_duration(output_dir, s.model)
        if stored is not None:
            s.total_duration_s = stored

    # Use the actual number of distinct models we have data for
    actual_models = len({r.model for r in all_records})
    actual_cases = len({(r.category, r.case_id) for r in all_records})
    run_info = make_run_info(config.runs_per_test, actual_models, actual_cases)

    output = write_aggregated_reports(output_dir)

    _print_summary_table(summaries)

    failed = sum(1 for r in all_records if r.error is not None)
    if failed:
        console.print(f"[yellow]{failed}/{len(all_records)} runs failed across all models[/yellow]")
    console.print(f"\nPer-model results saved under [bold]{output}/<model>/[/bold]")
    console.print(f"Aggregated reports written to [bold]{output}/[/bold]:")
    for name in ("comparison_table.md", "detailed_results.csv", "summary_report.md", "results.json"):
        console.print(f"  - {output / name}")


@app.command("aggregate")
def aggregate_cmd(
    output_dir: Path = typer.Option("results", "--output-dir", "-o", help="Results directory containing per-model folders."),
) -> None:
    """Rebuild comparison_table.md, summary_report.md, etc. from all per-model result folders.

    Use this after running models individually, e.g.:
        python benchmark.py run -m grok-4
        python benchmark.py run -m claude-opus-4-8
        python benchmark.py aggregate
    """
    all_records = load_all_model_records(output_dir)
    if not all_records:
        console.print(f"[red]No per-model results found under {output_dir}/<model>/records.json[/red]")
        raise typer.Exit(code=1)

    summaries = aggregate(all_records)

    # Enrich with any stored wall-clock durations
    for s in summaries:
        stored = load_model_duration(output_dir, s.model)
        if stored is not None:
            s.total_duration_s = stored

    n_models = len({r.model for r in all_records})
    n_cases = len({(r.category, r.case_id) for r in all_records})

    run_info = make_run_info(3, n_models, n_cases)
    output = write_aggregated_reports(output_dir)

    _print_summary_table(summaries)

    console.print(f"\nRebuilt aggregated reports from {n_models} model(s) in [bold]{output}/[/bold]")
    for name in ("comparison_table.md", "detailed_results.csv", "summary_report.md", "results.json"):
        console.print(f"  - {output / name}")


def _fmt_duration(dur) -> str:
    if dur is None:
        return "—"
    if dur >= 60:
        return f"{int(dur // 60)}m {int(dur % 60)}s"
    if dur > 0.05:
        return f"{dur:.1f}s"
    return "<0.1s"


def _print_summary_table(summaries) -> None:
    if not summaries:
        console.print("[red]No results.[/red]")
        return
    # Only rank models that ran the full category set. Models with partial
    # coverage (e.g. one interrupted category) get an inflated global score
    # because the weights renormalize over the subset they ran — split them out.
    ranked, partial, failed, _expected = classify_summaries(summaries)

    categories = [c for c in CATEGORY_WEIGHTS if any(c in s.category_scores for s in summaries)]
    table = Table(title="Benchmark Results (0-100)", show_lines=False)
    table.add_column("Rank", justify="right")
    table.add_column("Model", style="bold")
    table.add_column("Global", justify="right", style="bold cyan")
    for category in categories:
        table.add_column(f"{category}\n({CATEGORY_WEIGHTS[category]:.0%})", justify="right")
    table.add_column("Duration", justify="right")  # full set wall-clock time

    for rank, summary in enumerate(ranked, start=1):
        table.add_row(
            str(rank),
            summary.model,
            f"{summary.global_score:.1f}",
            *[f"{summary.category_scores.get(c, 0):.1f}" for c in categories],
            _fmt_duration(summary.total_duration_s),
        )
    console.print(table)

    if partial:
        console.print(
            "[yellow]Incomplete coverage (ran only some categories — not ranked; "
            "re-run the full suite):[/yellow]"
        )
        for summary in partial:
            covered = ", ".join(sorted(_task_categories(summary))) or "none"
            console.print(f"  [dim]- {summary.model} — ran only: {covered}[/dim]")
    if failed:
        console.print(
            "[yellow]Did not complete (every call failed — bad key, no access, "
            "or unreachable endpoint):[/yellow]"
        )
        for summary in failed:
            console.print(f"  [dim]- {summary.model} ({summary.total_runs} calls failed)[/dim]")


@app.command("list-categories")
def list_categories() -> None:
    """Show test categories and their weights in the global score."""
    table = Table(title="Test Categories")
    table.add_column("Category")
    table.add_column("Weight", justify="right")
    table.add_column("Kind")
    for category, weight in CATEGORY_WEIGHTS.items():
        kind = "derived from other runs" if category == "efficiency" else "dataset-backed"
        table.add_row(category, f"{weight:.0%}", kind)
    console.print(table)


@app.command("list-models")
def list_models(
    config_path: Path = typer.Option("models.json", "--config", help="Config file."),
) -> None:
    """Show the models configured in the config file."""
    config = BenchmarkConfig.load(config_path)
    table = Table(title=f"Models in {config_path}")
    table.add_column("Name", style="bold")
    table.add_column("Provider")
    table.add_column("Model ID")
    table.add_column("API key set?", justify="center")
    for model in config.models:
        needs_key = model.provider in ("openai", "xai", "anthropic")
        key_state = "✅" if model.api_key else ("❌" if needs_key else "n/a")
        table.add_row(model.name, model.provider, model.model_id, key_state)
    console.print(table)


@app.command("clear-cache")
def clear_cache(
    model: Optional[str] = typer.Option(
        None, "--model", "-m", help="Clear cache only for this model name."
    ),
    all: bool = typer.Option(
        False, "--all", help="Clear the entire cache (dangerous)."
    ),
    cache_dir: Path = typer.Option(".cache", "--cache-dir", help="Cache directory."),
) -> None:
    """Clear cached LLM responses.

    Examples:
        python benchmark.py clear-cache -m grok-4          # only grok-4
        python benchmark.py clear-cache --all              # everything
    """
    cache = ResponseCache(cache_dir)

    if all:
        count = cache.clear_all()
        console.print(f"[yellow]Cleared entire cache: removed {count} entries from {cache_dir}/[/yellow]")
        return

    if not model:
        console.print("[red]Please specify --model <name> or use --all to clear everything.[/red]")
        console.print("Example: python benchmark.py clear-cache -m grok-4")
        raise typer.Exit(code=1)

    count = cache.clear_model(model)
    if count > 0:
        console.print(f"[green]Cleared {count} cached responses for model '{model}'.[/green]")
    else:
        console.print(f"[yellow]No (new-style) cached responses found for model '{model}'.[/yellow]")
        console.print("[dim]Note: older cache entries (before selective clear) may need --all.[/dim]")


if __name__ == "__main__":
    app()
