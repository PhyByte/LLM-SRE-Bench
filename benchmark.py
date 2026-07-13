"""LLM Observability Benchmark Suite — CLI entry point.

Usage:
    python benchmark.py run                          # full benchmark, models.json
    python benchmark.py run --category anomaly_detection
    python benchmark.py run --model grok-4 --model claude-opus-4-8
    python benchmark.py run --config models.mock.json   # offline smoke test
    python benchmark.py list-categories
    python benchmark.py list-models
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
from reports.generator import aggregate, make_run_info, write_reports

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

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Benchmarking...", total=total)

        def on_record(record: RunRecord) -> None:
            status = "[red]ERR[/red]" if record.error else f"{100 * record.score:5.1f}"
            cached = " [dim](cached)[/dim]" if record.cached else ""
            progress.update(
                task,
                advance=1,
                description=(
                    f"{record.model} · {record.category} · {record.case_id} "
                    f"#{record.run_index} → {status}{cached}"
                ),
            )

        records = runner.run(datasets, model_names, on_record=on_record)

    summaries = aggregate(records)
    run_info = make_run_info(config.runs_per_test, len(model_names), n_cases)
    output = write_reports(output_dir, summaries, records, run_info)

    _print_summary_table(summaries)

    failed = sum(1 for r in records if r.error is not None)
    if failed:
        console.print(f"[yellow]{failed}/{len(records)} runs failed — see detailed_results.csv[/yellow]")
    console.print(f"\nReports written to [bold]{output}/[/bold]:")
    for name in ("comparison_table.md", "detailed_results.csv", "summary_report.md", "results.json"):
        console.print(f"  - {output / name}")


def _print_summary_table(summaries) -> None:
    if not summaries:
        console.print("[red]No results.[/red]")
        return
    categories = [c for c in CATEGORY_WEIGHTS if any(c in s.category_scores for s in summaries)]
    table = Table(title="Benchmark Results (0-100)", show_lines=False)
    table.add_column("Rank", justify="right")
    table.add_column("Model", style="bold")
    table.add_column("Global", justify="right", style="bold cyan")
    for category in categories:
        table.add_column(f"{category}\n({CATEGORY_WEIGHTS[category]:.0%})", justify="right")
    for rank, summary in enumerate(summaries, start=1):
        table.add_row(
            str(rank),
            summary.model,
            f"{summary.global_score:.1f}",
            *[f"{summary.category_scores.get(c, 0):.1f}" for c in categories],
        )
    console.print(table)


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


if __name__ == "__main__":
    app()
