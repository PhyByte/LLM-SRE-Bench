"""Export the public benchmark results as the payload the showcase site reads.

Emits `results/site_data.json` into this repository. That file is the published
contract: the site fetches it from GitHub and generates its own typed module from
it, so the two repositories no longer have to sit next to each other on disk.
Commit and push it like any other result artifact — an export that is never
pushed is invisible to the site.

The payload is split by track (SRE & Observability, Developer). Each track
carries its own categories, datasets, models and ranking, because the two are
separate leaderboards: a model that ran every SRE category and no developer one
is complete on the first and absent from the second, and a single blended score
across both would hide exactly that.

Scores are recomputed here from the stored records rather than read out of
results.json's `summaries`, which only ever holds whichever suite was active
when the reports were last written.

Only public information is exported: model names, providers, list prices, scores
and aggregate token/latency figures. Nothing from .env or the response cache.
"""

from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.config import (  # noqa: E402
    DEVELOPER_CATEGORY_WEIGHTS,
    SRE_CATEGORY_WEIGHTS,
    set_suite,
)
from reports.generator import (  # noqa: E402
    aggregate,
    classify_summaries,
    load_all_model_records,
)

# A blended $/1M-token price needs an input:output ratio. Measured across the
# ranked models the output share is ~4-11%, so 90/10 reflects this workload:
# SRE analysis reads a lot of evidence and answers with a short JSON verdict.
INPUT_SHARE, OUTPUT_SHARE = 0.90, 0.10

CATEGORIES = {
    "log_parsing": {
        "label": "Log Parsing",
        "blurb": "Turn raw log lines into templates, masking every variable part.",
        "measures": "Given production log lines, replace IDs, timestamps, paths and durations "
        "with <*> while keeping constant words exactly. This is the foundation of every log "
        "pipeline. It is how you group millions of lines into a handful of event types.",
        "scoring": "0.5 x exact-template accuracy + 0.5 x token-level F1 against ground truth.",
        "source": "Real Loghub 2k logs (HDFS, BGL, OpenSSH, Apache, Zookeeper, Linux) with the "
        "official ground-truth templates from logpai/logparser.",
        "hard": "Some templates are entirely constant. Models that over-wildcard everything "
        "lose points, so it rewards restraint as much as detection.",
    },
    "anomaly_detection": {
        "label": "Anomaly Detection",
        "blurb": "Flag which log lines are genuinely anomalous, and which only look scary.",
        "measures": "Given a window of logs, identify the anomalous lines by index. Routine "
        "warnings, retries and rolling-restart noise must be left alone.",
        "scoring": "Precision / recall / F1 over per-line labels.",
        "source": "Real labelled BGL supercomputer windows plus hard synthetic cases.",
        "hard": "BGL labels 'instruction cache parity error corrected' as NORMAL, so grepping "
        "for 'error' scores about 40. One case is a healthy service where the correct answer is "
        "zero anomalies: over-flagging scores 0. Another is silent data loss with no error "
        "keyword anywhere.",
    },
    "pattern_correlation": {
        "label": "Pattern & Correlation",
        "blurb": "Group related events and work out which failure caused which.",
        "measures": "Identify recurring problem patterns across services, then the causal links "
        "between them: the A causes B causes C cascade behind a multi-service incident.",
        "scoring": "0.6 x pattern coverage + 0.4 x correlation accuracy.",
        "source": "Curated multi-service cascades with distractors, 2-hop chains, common-cause "
        "and inverted-cause cases.",
        "hard": "Unrelated failures happen inside the same window and must not be wired into "
        "the causal chain. Some incidents share a common cause rather than A→B; some look like "
        "the retries are the root cause when the first timeout is upstream.",
    },
    "metrics_timeseries": {
        "label": "Metrics Time-Series",
        "blurb": "Spot anomalies in a seasonal metric series.",
        "measures": "Given a metric series (usually 96 points on a daily cycle; one case is 7 "
        "days hourly), find the indices that deviate from expected seasonal behaviour.",
        "scoring": "Point-wise precision / recall / F1. Default +/-1 index tolerance; some "
        "harder cases require an exact index.",
        "source": "Seasonal series with injected anomalies, clean series, and traps (in-band "
        "peaks, weekend-vs-weekday dips, flatlines, counter wraps, held samples).",
        "hard": "A global z-score misses off-peak spikes and level shifts. Harder cases go "
        "further: the global max is an in-season peak, a weekend dip is normal, a counter wrap "
        "is not an outage, and a stuck sensor looks like healthy flat numbers.",
    },
    "root_cause": {
        "label": "Root Cause & Summary",
        "blurb": "Explain the incident: what happened, the impact, and why.",
        "measures": "From an incident's logs, name the root cause in one sentence and write a "
        "short postmortem summary.",
        "scoring": "0.4 ROUGE-L on the summary + 0.3 ROUGE-1 on the root cause + 0.3 keyword "
        "recall. An optional LLM-as-judge can replace the blend.",
        "source": "Curated incidents with reference answers.",
        "hard": "Each incident contains red herrings (unrelated deploys, failing crons, network "
        "blips) that happened in the window and must be ruled out. Some pages are timezone "
        "false alarms; a successful rollback that does not help means the deploy was not the "
        "cause.",
    },
    "multimodal_rca": {
        "label": "Multi-modal RCA",
        "blurb": "Localize the culprit service across metrics, logs and traces at once.",
        "measures": "Given per-service metrics, logs and trace aggregates from a real "
        "microservice incident, name the culprit service from a closed candidate list, classify "
        "the fault, and cite the evidence that supports it. Three verdicts are possible and "
        "choosing between them is most of the task: a service, \"none\" (the system is healthy), "
        "or \"unknown\" (something is wrong but this evidence does not show what).",
        "scoring": "0.40 culprit localization + 0.25 fault type + 0.25 modality grounding "
        "+ 0.10 evidence recall.",
        "source": "Real incidents from the Nezha dataset (FSE 2023) on OnlineBoutique and "
        "TrainTicket, plus five faults whose culprit is unrecoverable from the evidence and one "
        "healthy baseline.",
        "hard": "The informative modality changes case to case. CPU faults show up in the "
        "metrics and leave the logs ordinary; code-level faults surface only in the logs. Citing "
        "a modality that shows nothing costs precision, so 'cite everything' cannot win. A "
        "metrics-only heuristic scores 100 on the CPU cases and 0 on the log-only ones. Five "
        "cases go further: a fault really was injected, but it is buried in every channel, and "
        "the calibrated answer is 'unknown'. Naming a plausible-looking service there scores 10 "
        "out of 100. The rule-based baseline does exactly that on all five.",
    },
    "code_generation": {
        "label": "Code Generation",
        "blurb": "Write a working utility from a spec and a required signature.",
        "measures": "Given a written spec and the exact signature to implement, produce code "
        "that compiles and passes unit tests the prompt never shows. Eight task families that "
        "read like real tickets rather than puzzles: slugify, interval merge, sliding-window "
        "rate limiter, recursive config overlay, LRU cache, log-line parser, semantic version "
        "comparison, latency quantiles.",
        "scoring": "0.6 x tests passed + 0.2 x compiles + 0.1 x runtime + 0.1 x code size.",
        "source": "Hand-written specs; every expected value is computed from a reference "
        "implementation and re-verified against all four compilers before it ships.",
        "hard": "The tests are hidden and the edge cases are where they live: empty inputs, "
        "duplicate keys, ties, boundaries. The signature is fixed, so a model that answers with "
        "its own preferred API fails to compile at all.",
    },
    "code_efficiency": {
        "label": "Code Efficiency",
        "blurb": "Correct is not enough. The answer has to be fast enough to ship.",
        "measures": "The same write-from-a-spec task, but each solution is run once against a "
        "200,000-element input and timed inside the process, against a budget set per language. "
        "Counting pairs that sum to a target, the largest k-sample burst in a metric series, the "
        "top talkers in a stream of ids.",
        "scoring": "0.45 x correctness + 0.15 x compiles + 0.35 x speed within budget (scaled by "
        "correctness) + 0.05 x code size.",
        "source": "Inputs are generated inside the test runner from a seeded generator, so all "
        "four languages see byte-identical data. Budgets are ~8x a reference implementation.",
        "hard": "The obvious nested-loop answer is correct. It passes every small test, compiles "
        "cleanly, and still cannot finish the real input — so it keeps the correctness half and "
        "loses the speed third. Reaching for a hash map or a prefix sum is the whole task.",
    },
    "code_debugging": {
        "label": "Bug Fixing",
        "blurb": "A plausible implementation that is quietly wrong, plus the symptom.",
        "measures": "Given working-looking code and the symptom a colleague reported, return a "
        "corrected implementation: a median that never sorts, a merge that drops one list's "
        "tail, a path normalizer that walks off the end of its own stack.",
        "scoring": "0.7 x correctness + 0.2 x compiles + 0.1 x code size, where correctness is "
        "half the whole test set and half the tests the shipped buggy version actually fails.",
        "source": "Each bug is seeded by hand and verified to be observable; which tests it "
        "breaks is measured per language when the dataset is built, not asserted.",
        "hard": "The hidden tests include the inputs the buggy version already handled, so a "
        "rewrite that breaks them is not a fix. Scoring the bug's own tests separately means "
        "handing the code back unchanged lands near 45, not near 85.",
    },
    "code_refactoring": {
        "label": "Refactoring",
        "blurb": "Change the shape of working code without changing what it does.",
        "measures": "Given correct but badly structured code and a stated goal, restructure it: "
        "collapse a nine-branch comparison chain into a lookup table, fold copy-pasted per-unit "
        "blocks into one loop, replace a quadratic membership scan with a set.",
        "scoring": "0.4 x tests still pass + 0.1 x compiles + 0.5 x structural rules, scaled by "
        "correctness.",
        "source": "Every 'before' is verified to pass the tests and to fail the structural rules "
        "its reference refactor satisfies, so the rules provably discriminate.",
        "hard": "Two ways to fail. Break the behaviour and the tests catch it; reformat without "
        "restructuring and the rules do. The rules accept any idiomatic answer - a Go switch and "
        "a Go map both pass - so what they actually test is whether the chain is gone.",
    },
    "code_review": {
        "label": "Code Review",
        "blurb": "Find the defects you would block a pull request on.",
        "measures": "Read a realistic service function and report what is wrong: SQL injection "
        "built by string concatenation, a query per row inside a loop, a cache that never "
        "evicts, a shared map with no lock, an auth token written to the logs, an HTTP call with "
        "no timeout.",
        "scoring": "0.65 x defect recall + 0.2 x precision + 0.15 x line localization.",
        "source": "Three components x four languages, three seeded defects each, matched by "
        "keyword so any reasonable wording counts.",
        "hard": "Padding the review costs precision and an empty review scores zero, so neither "
        "listing everything nor playing safe works. Where a defect does not translate - popping "
        "an empty array is silent in JavaScript and a panic in Rust - the case carries a "
        "language-appropriate defect instead of a fake one.",
    },
    "efficiency": {
        "label": "Efficiency & Consistency",
        "blurb": "Speed, token thrift and run-to-run stability.",
        "measures": "Derived from the runs above rather than its own dataset.",
        "scoring": "0.4 speed (against a 20s budget) + 0.3 token thrift (against 4000 tokens) "
        "+ 0.3 run-to-run score stability.",
        "source": "Computed from every other category's runs.",
        "hard": "A model that is accurate but slow and verbose pays for it here.",
    },
}

# Only the prose lives here. Case counts are read from datasets/data/ and the
# scored counts from the records, because a hand-maintained number drifts the
# moment a dataset grows — and a suite that claims cases nobody ran is worse
# than one that admits the gap.
DATASET_SOURCES = [
    ("log_parsing", "Loghub 2k + official templates"),
    ("anomaly_detection", "6 labelled BGL windows + 5 hard synthetics"),
    ("metrics_timeseries", "Seasonal series plus in-band / wrap / flatline traps"),
    ("pattern_correlation", "Curated multi-service cascades (common-cause, inverted, decoy deploy)"),
    ("root_cause", "Curated incidents with red herrings and decoy rollbacks"),
    ("multimodal_rca", "Nezha microservice incidents (metrics + logs + traces): "
     "12 solvable, 5 where the culprit is unrecoverable, 1 healthy baseline"),
    ("code_generation", "8 task families x 4 languages, reference-verified"),
    ("code_efficiency", "3 families x 4 languages, each with a timed 200k-element workload"),
    ("code_debugging", "3 seeded bugs x 4 languages, shipped with the reported symptom"),
    ("code_refactoring", "3 messy-but-correct functions x 4 languages, with structural rules"),
    ("code_review", "3 components x 4 languages, 3 seeded defects each"),
]

# The developer track runs every case in each of these, so the by-language view
# compares like with like. The toolchain line is what the sandbox actually
# invokes, which is the part a reader wants when a language scores oddly.
LANGUAGES = [
    {
        "key": "python",
        "label": "Python",
        "toolchain": "python3",
        "note": "Dynamically typed, so a wrong-shaped answer fails at the assertion "
        "rather than at compile time. The most forgiving of the four.",
    },
    {
        "key": "typescript",
        "label": "TypeScript",
        "toolchain": "node + tsx",
        "note": "Type-checked at run time by tsx. Object key order and floating-point "
        "formatting are the usual sources of a near-miss.",
    },
    {
        "key": "go",
        "label": "Go",
        "toolchain": "go run",
        "note": "Compiled and strict: an unused import or a signature that does not "
        "match the spec fails the whole file, so every test in that case is lost.",
    },
    {
        "key": "rust",
        "label": "Rust",
        "toolchain": "rustc (-O for timed cases)",
        "note": "Compiled, strict, and ownership-aware. Borrow-checker mistakes and "
        "String-vs-&str confusion are where most models lose points here.",
    },
]


def _language_of(case_id: str) -> str | None:
    for language in LANGUAGES:
        if case_id.endswith("_" + language["key"]):
            return language["key"]
    return None


# The two leaderboards. Each carries its own categories, datasets and ranking:
# they measure different work, most models have run only one of them, and a
# blended number across both would hide which.
TRACKS = [
    {
        "key": "sre",
        "label": "SRE & Observability",
        "tagline": "The on-call half: read the evidence, find the fault.",
        "blurb": "Log parsing, anomaly detection, failure correlation and root-cause analysis "
        "on real production data — including multi-modal incidents where the modality that "
        "carries the signal changes from case to case.",
        "weights": SRE_CATEGORY_WEIGHTS,
    },
    {
        "key": "developer",
        "label": "Developer",
        "tagline": "The keyboard half: write it, speed it up, fix it, review it.",
        "blurb": "Five kinds of coding work — writing a utility from a spec, making it fast "
        "enough on a large input, fixing a defect from a bug report, refactoring without "
        "breaking behaviour, and reviewing someone else's code — each in Python, TypeScript, "
        "Go and Rust, with every answer compiled and run in a sandbox.",
        "weights": DEVELOPER_CATEGORY_WEIGHTS,
    },
]


def track_of(category: str) -> str | None:
    """Which track a category belongs to. `efficiency` belongs to both."""
    for track in TRACKS:
        if category in track["weights"] and category != "efficiency":
            return track["key"]
    return None


def build_datasets(records: list, ranked: set[str], categories: list[str]) -> list[dict]:
    """Per-category case counts, split into what exists and what the ranking covers.

    A case counts as scored only when *every* ranked model has run it. One model
    running a new case is not coverage: it makes that model's category score
    incomparable with the rest, which is the opposite of what a leaderboard
    needs. Counting any single run instead would let five new cases look covered
    the moment one model touched them.
    """
    covered: dict[tuple[str, str], set[str]] = collections.defaultdict(set)
    for record in records:
        covered[(record.category, record.case_id)].add(record.model)

    rows = []
    for category, source in DATASET_SOURCES:
        if category not in categories:
            continue
        case_ids = [c["id"] for c in json.loads(
            (ROOT / "datasets" / "data" / f"{category}.json").read_text()
        )]
        # With nothing ranked yet, fall back to "anyone ran it" so the count is
        # still meaningful rather than uniformly zero.
        scored = sum(
            1 for cid in case_ids
            if (ranked <= covered[(category, cid)] if ranked else covered[(category, cid)])
        )
        rows.append(
            {
                "category": category,
                "cases": len(case_ids),
                "scored": scored,
                "source": source,
            }
        )
    return rows


def _model_entry(
    summary: dict,
    entry: dict,
    in_tok: int,
    out_tok: int,
    repeats: float,
    complete: bool,
    categories_scored: int,
    categories_total: int,
    per_language: dict[str, dict[str, float]],
) -> dict:
    """One row of a track's leaderboard."""
    price_in, price_out = entry.get("price_input"), entry.get("price_output")
    # A zero is not a price. It is either a placeholder nobody filled in or a
    # self-hosted model, whose real cost is hardware and operator time rather
    # than dollars per token — not comparable with list pricing either way.
    # Left as 0 it wins every "cheapest" comparison on the site and parks the
    # model on the origin of the score-against-price plot, so it is exported
    # as unknown and the site renders those cells as "not applicable".
    if not price_in or not price_out:
        price_in = price_out = None
    blended = (
        round(price_in * INPUT_SHARE + price_out * OUTPUT_SHARE, 3)
        if price_in is not None and price_out is not None
        else None
    )
    # Recomputed from the measured tokens and the current price table instead
    # of read off the run. The runner's own total is exactly this product, but
    # it was fixed at whatever price was configured that day, so a run made
    # before a price was filled in reports $0 — publishable as "free" long
    # after the rate is known.
    measured_cost = (
        round((in_tok * price_in + out_tok * price_out) / 1e6, 4)
        if blended is not None
        else None
    )
    return {
        "name": summary["model"],
        "provider": entry.get("provider"),
        "reasoning_effort": entry.get("reasoning_effort"),
        "global_score": round(summary["global_score"], 1),
        "scores": {k: round(v, 1) for k, v in summary["category_scores"].items()},
        "price_input": price_in,
        "price_output": price_out,
        "price_blended": blended,
        "measured_cost_usd": measured_cost,
        "total_runs": summary["total_runs"],
        "repeats_per_case": repeats,
        "errors": summary["error_count"],
        "refused": summary.get("refused_count", 0),
        "duration_s": summary["total_duration_s"],
        "avg_latency_s": round(summary["efficiency_metrics"].get("avg_latency_s", 0), 2),
        "avg_tokens": round(summary["efficiency_metrics"].get("avg_total_tokens", 0)),
        "score_stddev": round(summary["efficiency_metrics"].get("score_stddev", 0), 2),
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "complete": complete,
        # How much of the track this score actually covers. While a suite is
        # mid-migration these differ between models, and a global score computed
        # over five categories is not the same number as one computed over one.
        "categories_scored": categories_scored,
        "categories_total": categories_total,
        # {language: {category: score}}. Empty for tracks whose case ids carry
        # no language, which is every SRE case.
        "language_scores": per_language,
    }


def language_scores(records: list) -> dict[str, dict[str, dict[str, float]]]:
    """{model: {language: {category: score}}}, 0-100.

    Same rollup as everywhere else — mean across runs of a case, then mean
    across the cases — just partitioned by the language in the case id, so a
    model that is strong in Python and weak in Rust shows it instead of
    averaging out.
    """
    buckets: dict[tuple[str, str, str, str], list[float]] = collections.defaultdict(list)
    for record in records:
        language = _language_of(record.case_id)
        if language is None:
            continue
        buckets[(record.model, language, record.category, record.case_id)].append(record.score)

    per_case: dict[tuple[str, str, str], list[float]] = collections.defaultdict(list)
    for (model, language, category, _case), scores in buckets.items():
        per_case[(model, language, category)].append(sum(scores) / len(scores))

    out: dict[str, dict[str, dict[str, float]]] = collections.defaultdict(
        lambda: collections.defaultdict(dict)
    )
    for (model, language, category), means in per_case.items():
        out[model][language][category] = round(100 * sum(means) / len(means), 1)
    return {model: dict(langs) for model, langs in out.items()}


def build_languages(records: list, ranked: set[str], categories: list[str]) -> list[dict]:
    """Per-language case counts for this track, and how many are scored."""
    covered: dict[tuple[str, str], set[str]] = collections.defaultdict(set)
    for record in records:
        covered[(record.category, record.case_id)].add(record.model)

    rows = []
    for language in LANGUAGES:
        cases = scored = 0
        per_category: dict[str, int] = {}
        for category in categories:
            path = ROOT / "datasets" / "data" / f"{category}.json"
            if not path.exists():
                continue
            ids = [
                c["id"] for c in json.loads(path.read_text())
                if _language_of(c["id"]) == language["key"]
            ]
            if not ids:
                continue
            per_category[category] = len(ids)
            cases += len(ids)
            scored += sum(
                1 for cid in ids
                if (ranked <= covered[(category, cid)] if ranked else covered[(category, cid)])
            )
        if cases:
            rows.append({**language, "cases": cases, "scored": scored, "per_category": per_category})
    return rows


def build_track(track: dict, all_records: list, meta: dict) -> dict | None:
    """Scores, models and dataset coverage for one track.

    Returns None when nothing in this track has been run, so a repo that has
    only ever run one suite does not publish an empty second leaderboard.

    Scores are recomputed from the records with this track's weights active
    rather than taken from results.json's `summaries`, which holds only the
    suite that happened to be active when the reports were last written.
    """
    task_categories = [c for c in track["weights"] if c != "efficiency"]
    records = [r for r in all_records if r.category in task_categories]
    if not records:
        return None

    set_suite(track["key"])
    summaries = aggregate(records)
    ranked_summaries, _partial, _failed, _expected = classify_summaries(summaries)
    ranked = {s.model for s in ranked_summaries}

    tokens: dict[str, list[int]] = collections.defaultdict(lambda: [0, 0])
    cases: dict[str, dict[str, set]] = collections.defaultdict(
        lambda: collections.defaultdict(set)
    )
    runs: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for record in records:
        tokens[record.model][0] += record.input_tokens or 0
        tokens[record.model][1] += record.output_tokens or 0
        cases[record.model][record.category].add(record.case_id)
        runs[record.model][record.category] += 1

    by_language = language_scores(records)

    models = []
    for summary in summaries:
        name = summary.model
        covered = sorted(c for c in summary.category_scores if c in task_categories)
        # Every ranked model runs the same cases; some ran fewer repeats, which
        # the site discloses rather than silently normalising away.
        repeats = round(
            sum(runs[name][c] for c in covered)
            / max(sum(len(cases[name][c]) for c in covered), 1),
            1,
        )
        in_tok, out_tok = tokens[name]
        models.append(
            _model_entry(
                {
                    "model": name,
                    "global_score": summary.global_score,
                    # Per-language buckets (code_python, …) ride along for the
                    # developer track's by-language view; they are reported,
                    # never weighted.
                    "category_scores": summary.category_scores,
                    "total_runs": summary.total_runs,
                    "error_count": summary.error_count,
                    "refused_count": summary.refused_count,
                    "total_duration_s": summary.total_duration_s,
                    "efficiency_metrics": summary.efficiency_metrics,
                },
                meta.get(name, {}),
                in_tok,
                out_tok,
                repeats,
                name in ranked,
                len(covered),
                len(task_categories),
                by_language.get(name, {}),
            )
        )
    models.sort(key=lambda m: (-m["complete"], -m["global_score"]))

    datasets = build_datasets(records, ranked, task_categories)
    languages = build_languages(records, ranked, task_categories)
    categories = {
        key: {**CATEGORIES[key], "weight": weight, "track": track["key"]}
        for key, weight in track["weights"].items()
    }
    return {
        "key": track["key"],
        "label": track["label"],
        "tagline": track["tagline"],
        "blurb": track["blurb"],
        # n_cases is the comparable set — cases every ranked model ran — not a
        # count of everything touched, which rises as soon as a single model
        # reaches a new case. n_cases_total is the suite as built. The site
        # shows both rather than picking whichever is flattering.
        "n_cases": sum(d["scored"] for d in datasets),
        "n_cases_total": sum(d["cases"] for d in datasets),
        "categories": categories,
        "datasets": datasets,
        # Empty on a track whose cases are not per-language (the SRE suite).
        "languages": languages,
        "models": models,
    }


def export(results_dir: Path | None = None) -> tuple[Path, dict]:
    """Build the site payload from `results_dir` and write it beside the reports.

    Returns the path written and the payload, so callers can report on it without
    re-reading the file. `benchmark.py` calls this at the end of a run: the export
    is derived entirely from results.json, and leaving it as a separate manual
    step meant every finished run silently left the site a run behind.
    """
    results_dir = results_dir or ROOT / "results"
    # Records come from the per-model folders, the same source the reports read.
    # results.json is only consulted for the run header: its records carry
    # display-scaled scores (0-100), and re-aggregating those would multiply
    # every score by a hundred.
    results = json.loads((results_dir / "results.json").read_text())
    all_records = load_all_model_records(results_dir)
    config = json.loads((ROOT / "models.json").read_text())
    meta = {m["name"]: m for m in config["models"]}

    tracks = [t for t in (build_track(track, all_records, meta) for track in TRACKS) if t]
    if not tracks:
        raise ValueError("no records for any track — nothing to export")

    payload = {
        "generated": results["run_info"]["timestamp"],
        "runs_per_test": results["run_info"]["runs_per_test"],
        "n_cases": sum(t["n_cases"] for t in tracks),
        "n_cases_total": sum(t["n_cases_total"] for t in tracks),
        "price_blend": {"input": INPUT_SHARE, "output": OUTPUT_SHARE},
        "tracks": tracks,
    }

    out = results_dir / "site_data.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return out, payload


def pending_rows(payload: dict) -> list[dict]:
    """Dataset rows holding cases that not every ranked model has run."""
    return [
        {**row, "track": track["key"]}
        for track in payload["tracks"]
        for row in track["datasets"]
        if row["scored"] < row["cases"]
    ]


def main() -> None:
    out, payload = export()
    print(f"wrote {out.relative_to(ROOT)}")
    for row in pending_rows(payload):
        print(
            f"  ! {row['track']}/{row['category']}: {row['cases'] - row['scored']} of "
            f"{row['cases']} cases are not covered by every ranked model — the site will "
            "show them as pending"
        )
    for track in payload["tracks"]:
        models = track["models"]
        complete = [m for m in models if m["complete"]]
        print(
            f"\n  {track['label']}: {len(complete)} ranked, "
            f"{len(models) - len(complete)} partial, "
            f"{track['n_cases']}/{track['n_cases_total']} cases covered"
        )
        for m in complete[:5]:
            price = f"${m['price_blended']}/1M blended" if m["price_blended"] else "unpriced"
            print(f"    {m['name']:18s} {m['global_score']:5.1f}  {price}")
        if len(complete) > 5:
            print(f"    … and {len(complete) - 5} more")
    print("\ncommit and push results/site_data.json, then in the site repo: npm run refresh-data")


if __name__ == "__main__":
    main()
