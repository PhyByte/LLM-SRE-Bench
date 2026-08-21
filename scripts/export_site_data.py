"""Export the public benchmark results as the payload the showcase site reads.

Emits `results/site_data.json` into this repository. That file is the published
contract: the site fetches it from GitHub and generates its own typed module from
it, so the two repositories no longer have to sit next to each other on disk.
Commit and push it like any other result artifact — an export that is never
pushed is invisible to the site.

Only public information is exported: model names, providers, list prices, scores
and aggregate token/latency figures. Nothing from .env or the response cache.
"""

from __future__ import annotations

import collections
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

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
]


def build_datasets(results: dict, ranked: set[str]) -> list[dict]:
    """Per-category case counts, split into what exists and what the ranking covers.

    A case counts as scored only when *every* ranked model has run it. One model
    running a new case is not coverage: it makes that model's category score
    incomparable with the rest, which is the opposite of what a leaderboard
    needs. Counting any single run instead would let five new cases look covered
    the moment one model touched them.
    """
    covered: dict[tuple[str, str], set[str]] = collections.defaultdict(set)
    for record in results["records"]:
        covered[(record["category"], record["case_id"])].add(record["model"])

    rows = []
    for category, source in DATASET_SOURCES:
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


def export(results_dir: Path | None = None) -> tuple[Path, dict]:
    """Build the site payload from `results_dir` and write it beside the reports.

    Returns the path written and the payload, so callers can report on it without
    re-reading the file. `benchmark.py` calls this at the end of a run: the export
    is derived entirely from results.json, and leaving it as a separate manual
    step meant every finished run silently left the site a run behind.
    """
    results_dir = results_dir or ROOT / "results"
    results = json.loads((results_dir / "results.json").read_text())
    config = json.loads((ROOT / "models.json").read_text())

    meta = {m["name"]: m for m in config["models"]}

    tokens: dict[str, list[int]] = collections.defaultdict(lambda: [0, 0])
    cases: dict[str, dict[str, set]] = collections.defaultdict(lambda: collections.defaultdict(set))
    runs: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for record in results["records"]:
        tokens[record["model"]][0] += record["input_tokens"] or 0
        tokens[record["model"]][1] += record["output_tokens"] or 0
        cases[record["model"]][record["category"]].add(record["case_id"])
        runs[record["model"]][record["category"]] += 1

    models = []
    for summary in results["summaries"]:
        name = summary["model"]
        entry = meta.get(name, {})
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
        in_tok, out_tok = tokens[name]
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
        covered = sorted(c for c in summary["category_scores"] if c != "efficiency")
        # Every ranked model runs the same cases; some ran fewer repeats, which
        # the site discloses rather than silently normalising away.
        repeats = round(
            sum(runs[name][c] for c in covered) / max(sum(len(cases[name][c]) for c in covered), 1),
            1,
        )
        models.append(
            {
                "name": name,
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
                "duration_s": summary["total_duration_s"],
                "avg_latency_s": round(summary["efficiency_metrics"].get("avg_latency_s", 0), 2),
                "avg_tokens": round(summary["efficiency_metrics"].get("avg_total_tokens", 0)),
                "score_stddev": round(summary["efficiency_metrics"].get("score_stddev", 0), 2),
                "input_tokens": in_tok,
                "output_tokens": out_tok,
                "complete": "multimodal_rca" in summary["category_scores"],
            }
        )

    models.sort(key=lambda m: (-m["complete"], -m["global_score"]))

    weights = {
        "log_parsing": 0.15,
        "anomaly_detection": 0.25,
        "pattern_correlation": 0.15,
        "metrics_timeseries": 0.10,
        "root_cause": 0.10,
        "multimodal_rca": 0.20,
        "efficiency": 0.05,
    }

    datasets = build_datasets(results, {m["name"] for m in models if m["complete"]})

    payload = {
        "generated": results["run_info"]["timestamp"],
        "runs_per_test": results["run_info"]["runs_per_test"],
        # n_cases is the comparable set — cases every ranked model ran — not
        # run_info's count, which rises as soon as a single model touches a new
        # case. n_cases_total is the suite as built. The site shows both rather
        # than picking whichever is flattering.
        "n_cases": sum(d["scored"] for d in datasets),
        "n_cases_total": sum(d["cases"] for d in datasets),
        "price_blend": {"input": INPUT_SHARE, "output": OUTPUT_SHARE},
        "categories": {
            key: {**value, "weight": weights[key]} for key, value in CATEGORIES.items()
        },
        "datasets": datasets,
        "models": models,
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
    return [d for d in payload["datasets"] if d["scored"] < d["cases"]]


def main() -> None:
    out, payload = export()
    models = payload["models"]
    complete = [m for m in models if m["complete"]]

    print(f"wrote {out.relative_to(ROOT)}")
    for row in pending_rows(payload):
        print(
            f"  ! {row['category']}: {row['cases'] - row['scored']} of {row['cases']} cases "
            "are not covered by every ranked model — the site will show them as pending"
        )
    print(f"  {len(complete)} fully-covered models, {len(models) - len(complete)} partial")
    for m in complete:
        price = f"${m['price_blended']}/1M blended" if m["price_blended"] else "unpriced"
        print(f"    {m['name']:18s} {m['global_score']:5.1f}  {price}")
    print("\ncommit and push results/site_data.json, then in the site repo: npm run refresh-data")


if __name__ == "__main__":
    main()
