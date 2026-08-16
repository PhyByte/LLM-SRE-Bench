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
        "pipeline — it is how you group millions of lines into a handful of event types.",
        "scoring": "0.5 x exact-template accuracy + 0.5 x token-level F1 against ground truth.",
        "source": "Real Loghub 2k logs (HDFS, BGL, OpenSSH, Apache, Zookeeper, Linux) with the "
        "official ground-truth templates from logpai/logparser.",
        "hard": "Some templates are entirely constant. Models that over-wildcard everything "
        "lose points, so it rewards restraint as much as detection.",
    },
    "anomaly_detection": {
        "label": "Anomaly Detection",
        "blurb": "Flag which log lines are genuinely anomalous — and which only look scary.",
        "measures": "Given a window of logs, identify the anomalous lines by index. Routine "
        "warnings, retries and rolling-restart noise must be left alone.",
        "scoring": "Precision / recall / F1 over per-line labels.",
        "source": "Real labelled BGL supercomputer windows plus hard synthetic cases.",
        "hard": "BGL labels 'instruction cache parity error corrected' as NORMAL, so grepping "
        "for 'error' scores about 40. One case is a healthy service where the correct answer is "
        "zero anomalies — over-flagging scores 0. Another is silent data loss with no error "
        "keyword anywhere.",
    },
    "pattern_correlation": {
        "label": "Pattern & Correlation",
        "blurb": "Group related events and work out which failure caused which.",
        "measures": "Identify recurring problem patterns across services, then the causal links "
        "between them — the A causes B causes C cascade behind a multi-service incident.",
        "scoring": "0.6 x pattern coverage + 0.4 x correlation accuracy.",
        "source": "Curated multi-service cascades with distractors and 2-hop causal chains.",
        "hard": "Unrelated failures happen inside the same window and must not be wired into "
        "the causal chain.",
    },
    "metrics_timeseries": {
        "label": "Metrics Time-Series",
        "blurb": "Spot anomalies in a seasonal metric series.",
        "measures": "Given 96 points of a metric on a daily cycle, find the indices that deviate "
        "from expected seasonal behaviour — spikes, dips and level shifts.",
        "scoring": "Point-wise precision / recall / F1 with a +/-1 index tolerance.",
        "source": "Seasonal series with injected anomalies, including two clean series.",
        "hard": "The series follow a daily cycle, so a global z-score misses off-peak spikes and "
        "level shifts. Some anomalies are smaller than the seasonal swing itself.",
    },
    "root_cause": {
        "label": "Root Cause & Summary",
        "blurb": "Explain the incident: what happened, the impact, and why.",
        "measures": "From an incident's logs, name the root cause in one sentence and write a "
        "short postmortem summary.",
        "scoring": "0.4 ROUGE-L on the summary + 0.3 ROUGE-1 on the root cause + 0.3 keyword "
        "recall. An optional LLM-as-judge can replace the blend.",
        "source": "Curated incidents with reference answers.",
        "hard": "Each incident contains red herrings — unrelated deploys, failing crons, network "
        "blips — that happened in the window and must be ruled out.",
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
        "out of 100 — the rule-based baseline does exactly that on all five.",
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
    ("metrics_timeseries", "Seasonal series, 96 points each"),
    ("pattern_correlation", "Curated multi-service cascades"),
    ("root_cause", "Curated incidents with red herrings"),
    ("multimodal_rca", "Nezha microservice incidents (metrics + logs + traces): "
     "12 solvable, 5 where the culprit is unrecoverable, 1 healthy baseline"),
]


def build_datasets(results: dict) -> list[dict]:
    """Per-category case counts, split into what exists and what has been run.

    A case only counts as scored once it appears in the records. New cases are
    therefore visible on the site as pending from the moment they are built,
    rather than silently inflating a total that the published scores do not
    cover.
    """
    scored_pairs = {(r["category"], r["case_id"]) for r in results["records"]}
    rows = []
    for category, source in DATASET_SOURCES:
        case_ids = [c["id"] for c in json.loads(
            (ROOT / "datasets" / "data" / f"{category}.json").read_text()
        )]
        rows.append(
            {
                "category": category,
                "cases": len(case_ids),
                "scored": sum(1 for cid in case_ids if (category, cid) in scored_pairs),
                "source": source,
            }
        )
    return rows


def main() -> None:
    results = json.loads((ROOT / "results" / "results.json").read_text())
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
        blended = (
            round(price_in * INPUT_SHARE + price_out * OUTPUT_SHARE, 3)
            if price_in is not None and price_out is not None
            else None
        )
        in_tok, out_tok = tokens[name]
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
                "measured_cost_usd": summary["total_cost_usd"],
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

    datasets = build_datasets(results)

    payload = {
        "generated": results["run_info"]["timestamp"],
        "runs_per_test": results["run_info"]["runs_per_test"],
        # n_cases is what the published scores actually cover; n_cases_total is
        # the suite as built. They differ whenever cases exist that no model has
        # run yet, and the site says so rather than picking whichever is nicer.
        "n_cases": results["run_info"]["n_cases"],
        "n_cases_total": sum(d["cases"] for d in datasets),
        "price_blend": {"input": INPUT_SHARE, "output": OUTPUT_SHARE},
        "categories": {
            key: {**value, "weight": weights[key]} for key, value in CATEGORIES.items()
        },
        "datasets": datasets,
        "models": models,
    }

    out = ROOT / "results" / "site_data.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    complete = [m for m in models if m["complete"]]
    print(f"wrote {out.relative_to(ROOT)}")
    pending = [d for d in datasets if d["scored"] < d["cases"]]
    for row in pending:
        print(
            f"  ! {row['category']}: {row['cases'] - row['scored']} of {row['cases']} cases "
            "have no runs yet — the site will show them as pending"
        )
    print(f"  {len(complete)} fully-covered models, {len(models) - len(complete)} partial")
    for m in complete:
        print(f"    {m['name']:18s} {m['global_score']:5.1f}  ${m['price_blended']}/1M blended")
    print("\ncommit and push results/site_data.json, then in the site repo: npm run refresh-data")


if __name__ == "__main__":
    main()
