"""LLM Observability Benchmark Suite — CLI entry point.

Usage (recommended workflow for running models one at a time):

    # Run models independently (results go to results/<model>/)
    python benchmark.py run -m grok-4
    python benchmark.py run -m opus-4.8
    python benchmark.py run -m llama-3.3-70b --runs 1

    # Rebuild the combined comparison table + reports from all model folders
    python benchmark.py aggregate

Other examples:
    python benchmark.py run --category anomaly_detection
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

from core.config import (
    ALL_CATEGORIES,
    CATEGORY_WEIGHTS,
    DEVELOPER_CATEGORIES,
    SRE_CATEGORIES,
    TASK_CATEGORIES,
    BenchmarkConfig,
    set_suite,
)
from core.runner import BenchmarkRunner, RunRecord
from datasets.loaders import load_datasets
from reports.generator import (
    aggregate,
    build_pricing,
    classify_summaries,
    format_coverage_lines,
    load_all_model_records,
    make_run_info,
    save_model_results,
    write_aggregated_reports,
    write_reports,
    _task_categories,
)

from core.cache import ResponseCache
from scripts.export_site_data import export as export_site_data, pending_rows

app = typer.Typer(help="Benchmark LLMs on log analysis, anomaly detection, and SRE tasks.")
console = Console()


def _write_site_data(output_dir: Path) -> None:
    """Refresh the showcase site's payload alongside the other reports.

    Kept in step with results.json automatically: as a separate manual step it
    was forgotten after most runs, and a stale export shows a finished model as
    "partial" on the site with nothing to explain why.
    """
    try:
        out, payload = export_site_data(output_dir)
    except Exception as error:  # noqa: BLE001 - a reporting extra must never fail a run
        console.print(f"[yellow]Could not write site_data.json: {error}[/yellow]")
        return
    console.print(f"  - {out}")
    for row in pending_rows(payload):
        console.print(
            f"[yellow]  ! {row['track']}/{row['category']}: {row['cases'] - row['scored']} of "
            f"{row['cases']} cases are not covered by every ranked model, so the site "
            "will show them as pending[/yellow]"
        )


@app.command()
def run(
    config_path: Path = typer.Option("models.json", "--config", help="Config file (models.json)."),
    suite: str = typer.Option(
        "sre",
        "--suite",
        help="Test suite to run: 'sre' (observability), 'developer' (code generation), or 'all'.",
    ),
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
        help="Extra attempts per slot after a transient failure (timeout/5xx/bad JSON/"
        "empty response). Retries run immediately on that slot before moving on. "
        "0 disables.",
        min=0,
    ),
    no_cache: bool = typer.Option(False, "--no-cache", help="Bypass the response cache."),
    replace: bool = typer.Option(
        False,
        "--replace",
        help="Re-run every selected slot and overwrite its stored result. By default a "
        "run skips slots already scored in results/<model>/ and only calls "
        "failures or never-run cases. Only the selected slots are replaced — "
        "results for categories this run did not touch are left alone.",
    ),
    declined: bool = typer.Option(
        False,
        "--declined",
        help="Also re-run slots the model previously declined (safety-classifier "
        "refusals). Skipped by default because a refusal is deterministic for a "
        "given prompt — use this to re-check after a provider policy change.",
    ),
    output_dir: Path = typer.Option("results", "--output-dir", "-o", help="Report directory."),
    data_dir: Optional[Path] = typer.Option(
        None, "--data-dir", help="Alternative dataset directory (same file names)."
    ),
) -> None:
    """Run the benchmark and write reports to the results directory."""
    config = BenchmarkConfig.load(config_path)
    if runs is not None:
        config.runs_per_test = runs

    # Set the active suite (affects CATEGORY_WEIGHTS and TASK_CATEGORIES)
    try:
        suite_categories = set_suite(suite)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=1)

    # Allow categories flag to override/filter the suite's categories
    selected_categories = categories or suite_categories
    invalid = [c for c in selected_categories if c not in ALL_CATEGORIES]
    if invalid:
        console.print(
            f"[red]Unknown categories: {invalid}. Valid: {ALL_CATEGORIES}[/red]"
        )
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
            model_config.provider in ("openai", "xai", "anthropic", "google")
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

    # Already-scored slots are not called again: a stored success stands, and a
    # stored refusal is a settled 0 (the same prompt is declined again). Only
    # failures and never-run cases cost API calls.
    skip_keys: set[tuple[str, str, str, int]] = set()
    skipped_declined = 0
    if not replace:
        selected_cases = {
            (category, case["id"])
            for category, cases in datasets.items()
            for case in cases
        }
        for record in load_all_model_records(output_dir):
            if (
                record.model not in model_names
                or record.error is not None
                or (record.category, record.case_id) not in selected_cases
                or not 0 <= record.run_index < config.runs_per_test
            ):
                continue
            if record.refused:
                if declined:
                    continue
                skipped_declined += 1
            skip_keys.add(
                (record.model, record.category, record.case_id, record.run_index)
            )

    planned = BenchmarkRunner.total_tasks(config, datasets, model_names)
    total = BenchmarkRunner.total_tasks(config, datasets, model_names, skip_keys=skip_keys)

    console.print(
        f"\n[bold]LLM Observability Benchmark[/bold] — "
        f"{len(model_names)} model(s) x {n_cases} case(s) x {config.runs_per_test} run(s) "
        f"= {planned} slots"
    )
    if skip_keys:
        scored = f"{len(skip_keys)} already scored"
        if skipped_declined:
            scored += f" ({skipped_declined} declined)"
        console.print(f"  [dim]{scored}, {total} remaining[/dim]")
        console.print(
            "  [dim]--declined re-checks declined slots · "
            "--replace re-runs everything[/dim]\n"
        )
    else:
        console.print()

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

        def on_record(record: RunRecord) -> None:
            # Called once per slot with the final outcome (retries already done
            # inline), so the counter always advances. Print a lasting line so
            # past OK/ERR results stay visible instead of being overwritten.
            if record.error:
                status = "[red]ERR[/red]"
            elif record.refused:
                status = "[magenta]DECLINED[/magenta]"
            else:
                status = f"[green]{100 * record.score:5.1f}[/green]"
            cached = " [dim](cached)[/dim]" if record.cached else ""
            detail = ""
            if record.error:
                # Keep the line short: first meaningful clause of the error.
                brief = record.error.split(" — ", 1)[0]
                if len(brief) > 72:
                    brief = brief[:69] + "..."
                detail = f"  [dim]{brief}[/dim]"
            elif record.refused:
                detail = f"  [dim]{record.refused}[/dim]"
            progress.print(
                f"{record.model} · {record.category} · {record.case_id} "
                f"#{record.run_index} → {status}{cached}{detail}"
            )
            # Advance the counter; leave the live description alone — the runner
            # sets it to the next in-flight slot via on_status.
            progress.update(task, advance=1)

        # Checkpoint each model the moment it finishes. A full sweep takes hours,
        # and a Ctrl-C partway through must not throw away the models that are
        # already done. Also enables running one model at a time across sessions.
        def on_model_complete(
            model_name: str, model_recs: list[RunRecord], duration: float
        ) -> None:
            # Always merge. --replace means "re-run the slots I selected and
            # overwrite those results", and the merge already does exactly that:
            # a new record replaces the stored one for the same (category,
            # case_id, run_index). Writing the folder from scratch instead threw
            # away every category the current run did not touch, so a
            # `--suite developer --replace` pass silently deleted all the stored
            # SRE results for each model it ran.
            save_model_results(
                output_dir,
                model_name,
                model_recs,
                total_duration_s=duration,
                merge=True,
            )

        def on_status(message: str) -> None:
            # Loading / in-flight retries: update the live bar only (no new line).
            progress.update(task, description=f"[cyan]{message}[/cyan]")

        records, model_durations = runner.run(
            datasets,
            model_names,
            on_record=on_record,
            retry_failed=retries,
            skip_keys=skip_keys,
            on_model_complete=on_model_complete,
            on_status=on_status,
        )

    # Rebuild the cross-model comparison from *all* available per-model folders
    # (merges newly run models with any previously saved ones)
    all_records = load_all_model_records(output_dir) or records
    pricing = build_pricing(config.models)

    # Use the actual number of distinct models we have data for
    actual_models = len({r.model for r in all_records})
    actual_cases = len({(r.category, r.case_id) for r in all_records})
    run_info = make_run_info(config.runs_per_test, actual_models, actual_cases)

    output = write_aggregated_reports(output_dir, pricing=pricing)

    # Console summary uses the active suite from the run; for dual-track data the
    # SRE table stays the primary printed ranking.
    sre_recs = [r for r in all_records if r.category in SRE_CATEGORIES]
    if sre_recs:
        set_suite("sre")
        summaries = aggregate(sre_recs, pricing)
    else:
        summaries = aggregate(all_records, pricing)

    _print_summary_table(summaries)
    _print_coverage_resume(all_records)
    console.print(f"\nPer-model results saved under [bold]{output}/<model>/[/bold]")
    console.print(f"Aggregated reports written to [bold]{output}/[/bold]:")
    report_names = [
        "comparison_table.md",
        "comparison_table_developer.md",
        "detailed_results.csv",
        "summary_report.md",
        "results.json",
    ]
    for name in report_names:
        path = output / name
        if path.exists():
            console.print(f"  - {path}")
    _write_site_data(output)


@app.command("aggregate")
def aggregate_cmd(
    config_path: Path = typer.Option("models.json", "--config", help="Config file (for model pricing)."),
    output_dir: Path = typer.Option("results", "--output-dir", "-o", help="Results directory containing per-model folders."),
) -> None:
    """Rebuild comparison tables and reports from all per-model result folders.

    Writes ``comparison_table.md`` (SRE) and, when code-generation results exist,
    ``comparison_table_developer.md``.

    Use this after running models individually, e.g.:
        python benchmark.py run -m grok-4
        python benchmark.py run -m opus-4.8
        python benchmark.py aggregate
    """
    all_records = load_all_model_records(output_dir)
    if not all_records:
        console.print(f"[red]No per-model results found under {output_dir}/<model>/records.json[/red]")
        raise typer.Exit(code=1)

    pricing = {}
    if config_path.exists():
        pricing = build_pricing(BenchmarkConfig.load(config_path).models)

    output = write_aggregated_reports(output_dir, pricing=pricing)

    sre_recs = [r for r in all_records if r.category in SRE_CATEGORIES]
    if sre_recs:
        set_suite("sre")
        summaries = aggregate(sre_recs, pricing)
    else:
        summaries = aggregate(all_records, pricing)

    n_models = len({r.model for r in all_records})
    _print_summary_table(summaries)
    _print_coverage_resume(all_records)

    console.print(f"\nRebuilt aggregated reports from {n_models} model(s) in [bold]{output}/[/bold]")
    for name in (
        "comparison_table.md",
        "comparison_table_developer.md",
        "detailed_results.csv",
        "summary_report.md",
        "results.json",
    ):
        path = output / name
        if path.exists():
            console.print(f"  - {path}")
    _write_site_data(output)


def _fmt_duration(dur) -> str:
    if dur is None:
        return "—"
    if dur >= 60:
        return f"{int(dur // 60)}m {int(dur % 60)}s"
    if dur > 0.05:
        return f"{dur:.1f}s"
    return "<0.1s"


def _fmt_cost(cost) -> str:
    if cost is None:
        return "—"
    if cost == 0:
        return "$0.00"
    if cost < 0.01:
        return "<$0.01"
    return f"${cost:,.2f}"


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
    table.add_column("Duration", justify="right")  # total model time = sum of per-call latencies
    show_cost = any(s.total_cost_usd is not None for s in ranked)
    if show_cost:
        table.add_column("Cost", justify="right")

    for rank, summary in enumerate(ranked, start=1):
        table.add_row(
            str(rank),
            summary.model,
            f"{summary.global_score:.1f}",
            *[f"{summary.category_scores.get(c, 0):.1f}" for c in categories],
            _fmt_duration(summary.total_duration_s),
            *([_fmt_cost(summary.total_cost_usd)] if show_cost else []),
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


def _print_coverage_resume(records: list[RunRecord]) -> None:
    """After the ranking table: which models missed runs, and where."""
    lines = format_coverage_lines(records)
    if not lines:
        return
    console.print(f"\n[yellow]{lines[0]}[/yellow]")
    for line in lines[1:]:
        if line.startswith("    "):
            console.print(f"[dim]{line}[/dim]")
        else:
            console.print(line)


@app.command("list-categories")
def list_categories() -> None:
    """Show test categories and their weights in the global score."""
    # Show all available categories with their suite association
    table = Table(title="Test Categories")
    table.add_column("Category")
    table.add_column("Suite", justify="center")
    table.add_column("SRE Weight", justify="right")
    table.add_column("Developer Weight", justify="right")
    table.add_column("Kind")

    from core.config import DEVELOPER_CATEGORY_WEIGHTS, SRE_CATEGORY_WEIGHTS

    all_cats = set(SRE_CATEGORIES + DEVELOPER_CATEGORIES + ["efficiency"])
    for category in sorted(all_cats):
        if category in SRE_CATEGORIES:
            suite = "SRE"
        elif category in DEVELOPER_CATEGORIES:
            suite = "Developer"
        else:
            suite = "Both"

        sre_weight = SRE_CATEGORY_WEIGHTS.get(category, 0)
        dev_weight = DEVELOPER_CATEGORY_WEIGHTS.get(category, 0)
        kind = "derived from other runs" if category == "efficiency" else "dataset-backed"

        table.add_row(
            category,
            suite,
            f"{sre_weight:.0%}" if sre_weight > 0 else "—",
            f"{dev_weight:.0%}" if dev_weight > 0 else "—",
            kind,
        )

    console.print(table)
    console.print(
        "\n[dim]Use --suite sre|developer|all to select which categories to run.[/dim]"
    )


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
