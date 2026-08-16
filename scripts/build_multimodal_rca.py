"""Build the multi-modal RCA dataset from the Nezha (FSE'23) observability data.

Nezha ships 101 fault injections across OnlineBoutique and TrainTicket, each with
per-pod metrics, per-minute logs and per-minute traces, plus a ground-truth list
naming the injected pod and fault type.

Only about 40 of those faults are actually solvable from the bundled evidence, so
this script screens every fault before using it: it ranks services by CPU through
the metric channel and by error-log rate through the log channel, and keeps a
fault only when at least one channel puts the injected pod first. The channels
that succeed become the case's `informative_modalities`, and the rest become
`decoy_modalities` — measured, never asserted, which is what lets the evaluator
score modality grounding honestly.

The screen is also what makes the category multi-modal in a meaningful way: CPU
faults are recoverable from metrics and invisible in logs, while return/exception
faults are the reverse, so no single modality answers every case.

Usage:
    python scripts/build_multimodal_rca.py              # clones Nezha on first run
    python scripts/build_multimodal_rca.py --seed 7     # different deterministic sample
    python scripts/build_multimodal_rca.py --report     # print the full screen, build nothing
"""

from __future__ import annotations

import argparse
import collections
import csv
import datetime
import json
import random
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable, Optional

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "datasets" / "raw" / "nezha"
DATA_DIR = ROOT / "datasets" / "data"

NEZHA_REPO = "https://github.com/IntelligentDDS/Nezha.git"

# Nezha collection days -> the system under test that day.
DAYS = {
    "2022-08-22": "onlineboutique",
    "2022-08-23": "onlineboutique",
    "2023-01-29": "trainticket",
    "2023-01-30": "trainticket",
}

# Nezha's inject_type -> the vocabulary we show the model.
#
# cpu_contention and cpu_consumed deliberately collapse to one label. Nezha
# injects them differently (a competing process stealing CPU vs the pod burning
# its own), but the two are indistinguishable in the observability data: measured
# across all 26 CPU faults, the same service under either fault shows the same
# pod CPU (~90-105%) and the same node CPU — e.g. frontend reads pod 104.5/node
# 5.1 under contention and pod 99.9/node 4.6 under consumption. Asking a model to
# call that distinction would score a coin flip, not a skill.
#
# "return" and "exception" stay distinct: both are code-level injections, but the
# evidence differs — a wrong return value versus a thrown exception in the logs.
FAULT_TYPES = {
    "cpu_contention": "cpu_saturation",
    "cpu_consumed": "cpu_saturation",
    "network_delay": "network_delay",
    "return": "code_return_value",
    "exception": "code_exception",
}
FAULT_VOCABULARY = sorted(set(FAULT_TYPES.values())) + ["none", "unknown"]

# How many "insufficient evidence" cases to include, and how deeply the culprit
# must be buried to qualify as one. Five against thirteen solvable cases keeps a
# blanket "always answer unknown" strategy well below the rule-based baseline,
# while still making confident misattribution expensive.
N_ABSTENTION = 5
ABSTENTION_MIN_RANK = 5

# Metrics carried into the bundle. Deliberately the panel an on-call engineer
# would actually open, not every column Nezha ships.
# PodSuccessRate(%) is deliberately absent: it is 0 for every pod in every window
# of the Nezha data, so it costs tokens and actively misleads — a flat "0% success"
# reads as catastrophic when the column is simply never populated.
METRIC_COLUMNS = [
    ("CpuUsageRate(%)", "cpu%", 1),
    ("MemoryUsageRate(%)", "mem%", 1),
    ("PodServerLatencyP90(s)", "p90ms", 0, 1000.0),  # seconds -> ms
    ("PodWorkload(Ops)", "ops", 1),
]

# TrainTicket has ~46 services against OnlineBoutique's 10, which would make its
# bundles twice the size of every other case. Rather than dropping services —
# which would shrink the candidate set and risk hinting at the answer — large
# systems keep every service but show the three columns that carry the fault.
METRIC_COLUMNS_COMPACT = [
    ("CpuUsageRate(%)", "cpu%", 1),
    ("PodServerLatencyP90(s)", "p90ms", 0, 1000.0),
    ("PodWorkload(Ops)", "ops", 1),
]
COMPACT_ABOVE_SERVICES = 20

ERROR_HINTS = ("error", "exception", "fail", "panic", "unavailable", "timeout", "refused")

# Window around the injection, in seconds, used for every modality.
WINDOW_BEFORE = 120
WINDOW_AFTER = 300

MAX_LOG_LINES = 30
MAX_ERROR_LOG_LINES = 18

csv.field_size_limit(sys.maxsize)


# --------------------------------------------------------------------------- raw data

def ensure_dataset() -> None:
    if (RAW_DIR / "rca_data").exists():
        return
    RAW_DIR.parent.mkdir(parents=True, exist_ok=True)
    print(f"cloning {NEZHA_REPO} into {RAW_DIR} (~343 MB, unpacks to ~3.2 GB)")
    subprocess.run(
        ["git", "clone", "--depth", "1", NEZHA_REPO, str(RAW_DIR)],
        check=True,
    )


def parse_metric_time(value: str) -> Optional[float]:
    """'2022-08-22 03:51:19.607... +0000 UTC m=+0.11' -> epoch seconds.

    The TimeStamp column cannot be trusted: adservice's file on 2022-08-22 is
    corrupted (values start 186... , placing them in 2028), while every other pod
    is correct. The human-readable Time column is authoritative everywhere.
    """
    head = value.split(".")[0].strip()
    try:
        parsed = datetime.datetime.strptime(head, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    return parsed.replace(tzinfo=datetime.timezone.utc).timestamp()


def short_service(pod: str) -> str:
    """'frontend-579b9bff58-t2dbm' -> 'frontend'.

    Deployment pods are named <service>-<replicaset-hash>-<pod-suffix>, so the
    service name is everything before the last two generated segments. Names that
    don't follow that shape are returned untouched.
    """
    parts = pod.split("-")
    if len(parts) >= 3 and parts[-1].isalnum() and parts[-2].isalnum():
        return "-".join(parts[:-2])
    return pod


def inject_epoch(fault: dict[str, Any]) -> int:
    """Injection time in epoch seconds, derived from `inject_time`.

    The companion `inject_timestamp` field cannot be trusted: on 2023-01-29 it is
    8 hours behind (it was computed in UTC+8 while every other day is UTC), which
    silently shifts the window off the data entirely. `inject_time` agrees with
    the metric/log timestamps on all four days, so it is the authority.
    """
    parsed = datetime.datetime.strptime(fault["inject_time"], "%Y-%m-%d %H:%M:%S")
    return int(parsed.replace(tzinfo=datetime.timezone.utc).timestamp())


def load_faults(day: str) -> list[dict[str, Any]]:
    path = RAW_DIR / "rca_data" / day / f"{day}-fault_list.json"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        hours = json.load(f)
    return [fault for hour in hours.values() for fault in hour]


def load_metrics(day: str) -> dict[str, list[tuple[float, dict[str, str]]]]:
    """pod -> [(epoch, row)] for every per-pod metric CSV of a day."""
    directory = RAW_DIR / "rca_data" / day / "metric"
    if not directory.exists():
        return {}
    out: dict[str, list[tuple[float, dict[str, str]]]] = {}
    for path in sorted(directory.glob("*_metric.csv")):
        pod = path.name.replace("_metric.csv", "")
        rows: list[tuple[float, dict[str, str]]] = []
        with open(path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                epoch = parse_metric_time(row.get("Time", ""))
                if epoch is not None:
                    rows.append((epoch, row))
        rows.sort(key=lambda item: item[0])
        out[pod] = rows
    return out


def minute_files(day: str, kind: str, inject_time: str, minutes: int = 3) -> list[Path]:
    """The per-minute CSVs (HH_MM_log.csv / HH_MM_trace.csv) covering a window."""
    directory = RAW_DIR / "rca_data" / day / kind
    hour, minute = inject_time.split(" ")[1].split(":")[:2]
    paths = []
    for delta in range(minutes):
        total = int(minute) + delta
        candidate = directory / f"{(int(hour) + total // 60) % 24:02d}_{total % 60:02d}_{kind}.csv"
        if candidate.exists():
            paths.append(candidate)
    return paths


def read_rows(paths: Iterable[Path]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in paths:
        with open(path, newline="", encoding="utf-8", errors="replace") as f:
            rows.extend(csv.DictReader(f))
    return rows


# ------------------------------------------------------------------------- log text

def log_message(raw: str) -> tuple[str, str]:
    """Unwrap a Nezha log cell into (severity, message).

    Both systems wrap the line as {"log": ..., "stream": ..., "time": ...}.
    OnlineBoutique's inner payload is JSON with message/severity fields;
    TrainTicket's is a plain Java log line.
    """
    text = raw
    try:
        outer = json.loads(raw)
        text = outer.get("log", raw)
    except (json.JSONDecodeError, TypeError):
        pass
    text = text.strip()
    try:
        inner = json.loads(text)
        if isinstance(inner, dict) and "message" in inner:
            return str(inner.get("severity", "info")), str(inner["message"]).strip()
    except (json.JSONDecodeError, TypeError):
        pass
    severity = "info"
    for level in ("ERROR", "WARN", "FATAL", "DEBUG", "INFO"):
        if level in text[:40]:
            severity = level.lower()
            break
    return severity, text


def is_error_text(severity: str, message: str) -> bool:
    if severity in ("error", "fatal"):
        return True
    lowered = message.lower()
    return any(hint in lowered for hint in ERROR_HINTS)


# ------------------------------------------------------------------------- screening

def metric_ranking(
    metrics: dict[str, list[tuple[float, dict[str, str]]]],
    inject_ts: int,
    column: str = "CpuUsageRate(%)",
) -> list[tuple[str, float]]:
    """Services ranked by mean value of `column` across the incident window."""
    scores: dict[str, float] = {}
    for pod, rows in metrics.items():
        values = []
        for epoch, row in rows:
            if inject_ts - WINDOW_BEFORE <= epoch <= inject_ts + WINDOW_AFTER:
                try:
                    values.append(float(row[column]))
                except (KeyError, TypeError, ValueError):
                    continue
        if len(values) >= 3:
            scores[pod] = statistics.fmean(values)
    return sorted(scores.items(), key=lambda item: -item[1])


def log_ranking(log_rows: list[dict[str, str]]) -> list[tuple[str, float]]:
    """Services ranked by share of their log lines that look like errors."""
    errors: collections.Counter = collections.Counter()
    totals: collections.Counter = collections.Counter()
    for row in log_rows:
        pod = row.get("PodName")
        if not pod:
            continue
        totals[pod] += 1
        severity, message = log_message(row.get("Log") or "")
        if is_error_text(severity, message):
            errors[pod] += 1
    rates = {pod: errors[pod] / totals[pod] for pod in totals if totals[pod] >= 50}
    return sorted(rates.items(), key=lambda item: -item[1])


def rank_of(ranking: list[tuple[str, float]], pod: str) -> Optional[int]:
    for index, (name, _) in enumerate(ranking, start=1):
        if name == pod:
            return index
    return None


def screen_fault(
    day: str,
    fault: dict[str, Any],
    metrics: dict[str, list[tuple[float, dict[str, str]]]],
) -> dict[str, Any]:
    """Decide whether a fault is solvable, and from which modalities."""
    inject_ts = inject_epoch(fault)
    pod = fault["inject_pod"]

    metric_rank = rank_of(metric_ranking(metrics, inject_ts), pod)
    log_rows = read_rows(minute_files(day, "log", fault["inject_time"]))
    log_rank = rank_of(log_ranking(log_rows), pod)

    informative = [
        name for name, rank in (("metrics", metric_rank), ("logs", log_rank)) if rank == 1
    ]
    return {
        "day": day,
        "system": DAYS[day],
        "inject_time": fault["inject_time"],
        "inject_timestamp": inject_ts,
        "pod": pod,
        "service": short_service(pod),
        "inject_type": fault["inject_type"],
        "fault_type": FAULT_TYPES.get(fault["inject_type"], fault["inject_type"]),
        "metric_rank": metric_rank,
        "log_rank": log_rank,
        "informative": informative,
        "usable": bool(informative),
    }


# ---------------------------------------------------------------- modality rendering

def build_metrics_block(
    metrics: dict[str, list[tuple[float, dict[str, str]]]], inject_ts: int
) -> dict[str, list[str]]:
    """Per-service downsampled series, one short line per metric.

    Services are emitted in alphabetical order so position never hints at the
    answer, and no derived "deviation from baseline" column is included — working
    that out is the model's job, not the builder's.
    """
    columns = (
        METRIC_COLUMNS_COMPACT if len(metrics) > COMPACT_ABOVE_SERVICES else METRIC_COLUMNS
    )
    block: dict[str, list[str]] = {}
    for pod in sorted(metrics):
        rows = [
            row
            for epoch, row in metrics[pod]
            if inject_ts - WINDOW_BEFORE <= epoch <= inject_ts + WINDOW_AFTER
        ]
        if not rows:
            continue
        lines = []
        for spec in columns:
            column, label, digits = spec[0], spec[1], spec[2]
            scale = spec[3] if len(spec) > 3 else 1.0
            series = []
            for row in rows:
                try:
                    series.append(round(float(row[column]) * scale, digits))
                except (KeyError, TypeError, ValueError):
                    continue
            if series:
                rendered = " ".join(
                    f"{value:.{digits}f}" if digits else f"{value:.0f}" for value in series
                )
                lines.append(f"{label}: {rendered}")
        if lines:
            block[short_service(pod)] = lines
    return block


def build_logs_block(log_rows: list[dict[str, str]], rng: random.Random) -> list[str]:
    """A sampled, error-biased but honest slice of the window's logs.

    The same rule is applied to every service: keep a capped sample of error-like
    lines and a capped sample of normal ones, drawn uniformly at random across all
    services. Nothing privileges the culprit — its errors dominate the sample only
    when it genuinely produced more of them, which is exactly the signal a model
    is supposed to find. For CPU faults, which log nothing unusual, this correctly
    yields an uninformative block.
    """
    errors, normal = [], []
    for row in log_rows:
        pod = row.get("PodName")
        if not pod:
            continue
        severity, message = log_message(row.get("Log") or "")
        if not message:
            continue
        message = message.replace("\n", " ").strip()
        if len(message) > 220:
            message = message[:217] + "..."
        entry = f"[{short_service(pod)}] {severity.upper()}: {message}"
        (errors if is_error_text(severity, message) else normal).append(entry)

    picked_errors = rng.sample(errors, min(len(errors), MAX_ERROR_LOG_LINES))
    room = MAX_LOG_LINES - len(picked_errors)
    picked_normal = rng.sample(normal, min(len(normal), max(room, 0)))
    sample = picked_errors + picked_normal
    rng.shuffle(sample)
    return sample


def build_traces_block(trace_rows: list[dict[str, str]]) -> dict[str, str]:
    """Per-service span aggregates: volume plus latency shape."""
    durations: dict[str, list[float]] = collections.defaultdict(list)
    for row in trace_rows:
        pod = row.get("PodName")
        if not pod:
            continue
        try:
            durations[short_service(pod)].append(float(row["Duration"]) / 1000.0)  # us -> ms
        except (KeyError, TypeError, ValueError):
            continue

    block: dict[str, str] = {}
    for service in sorted(durations):
        values = sorted(durations[service])
        if not values:
            continue
        p50 = values[len(values) // 2]
        p95 = values[min(len(values) - 1, int(0.95 * len(values)))]
        block[service] = (
            f"spans={len(values)} p50={p50:.1f}ms p95={p95:.1f}ms max={values[-1]:.1f}ms"
        )
    return block


def evidence_keywords(screened: dict[str, Any]) -> list[str]:
    """Markers a correct answer should mention. Kept few and factual."""
    keywords = [screened["service"]]
    if "metrics" in screened["informative"]:
        keywords.append("cpu")
    if "logs" in screened["informative"]:
        keywords.append("error")
    return keywords


# ------------------------------------------------------------------------ case build

def build_case(
    screened: dict[str, Any],
    metrics,
    rng: random.Random,
    case_id: str,
    abstain: bool = False,
) -> dict[str, Any]:
    """Build one case bundle.

    With `abstain=True` the same construction is used, but the expected answer
    becomes "unknown": a fault really was injected and the evidence does not
    reveal which service it hit. That is deliberately distinct from the
    fault-free case, whose answer is "none" — an on-call tool that reports "all
    clear" when it actually cannot tell is the dangerous failure, not a
    conservative one, so the two must not collapse into the same answer.
    """
    day, inject_ts = screened["day"], screened["inject_timestamp"]
    log_rows = read_rows(minute_files(day, "log", screened["inject_time"]))
    trace_rows = read_rows(minute_files(day, "trace", screened["inject_time"]))

    metrics_block = build_metrics_block(metrics, inject_ts)
    logs_block = build_logs_block(log_rows, rng)
    traces_block = build_traces_block(trace_rows)

    services = sorted(
        set(metrics_block) | set(traces_block) | {screened["service"]}
    )
    present = [
        name
        for name, block in (
            ("metrics", metrics_block), ("logs", logs_block), ("traces", traces_block)
        )
        if block
    ]
    informative = [m for m in screened["informative"] if m in present]
    decoys = [m for m in present if m not in informative]

    start = datetime.datetime.fromtimestamp(
        inject_ts - WINDOW_BEFORE, datetime.timezone.utc
    ).strftime("%H:%M")
    end = datetime.datetime.fromtimestamp(
        inject_ts + WINDOW_AFTER, datetime.timezone.utc
    ).strftime("%H:%M")

    if abstain:
        ground_truth = {
            "culprit_service": "unknown",
            "fault_type": "unknown",
            # Nothing localizes this fault, so any citation is a false positive.
            "informative_modalities": [],
            "decoy_modalities": present,
            "evidence_keywords": [],
            # Recorded so the evaluator can also accept a correct localization:
            # the screen is a crude ranking, and a model that genuinely finds the
            # culprit anyway must not be punished for out-reasoning it.
            "true_culprit": screened["service"],
            "true_fault_type": screened["fault_type"],
            "screen_ranks": {
                "metrics": screened["metric_rank"],
                "logs": screened["log_rank"],
            },
        }
    else:
        ground_truth = {
            "culprit_service": screened["service"],
            "fault_type": screened["fault_type"],
            "informative_modalities": informative,
            "decoy_modalities": decoys,
            "evidence_keywords": evidence_keywords(screened),
        }

    source = (
        f"Nezha {screened['system']} {screened['inject_time']} UTC "
        f"({screened['inject_type']} injected on {screened['service']})"
    )
    if abstain:
        source += " — culprit not recoverable from the bundled evidence"

    return {
        "id": case_id,
        "source": source,
        "system": screened["system"],
        "services": services,
        "incident_window": f"{start}-{end} UTC",
        "modalities": {
            "metrics": metrics_block,
            "logs": logs_block,
            "traces": traces_block,
        },
        "ground_truth": ground_truth,
    }


def build_clean_case(day: str, rng: random.Random, case_id: str) -> Optional[dict[str, Any]]:
    """A fault-free case built from Nezha's baseline phase.

    Mirrors the suite's existing anti-over-flagging cases: the correct answer is
    "none", and a model that invents a culprit scores zero on localization.
    """
    directory = RAW_DIR / "construct_data" / day
    if not (directory / "metric").exists():
        return None

    metrics: dict[str, list[tuple[float, dict[str, str]]]] = {}
    for path in sorted((directory / "metric").glob("*_metric.csv")):
        pod = path.name.replace("_metric.csv", "")
        rows = []
        with open(path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                epoch = parse_metric_time(row.get("Time", ""))
                if epoch is not None:
                    rows.append((epoch, row))
        rows.sort(key=lambda item: item[0])
        metrics[pod] = rows
    if not metrics:
        return None

    stamps = [epoch for rows in metrics.values() for epoch, _ in rows]
    midpoint = int(statistics.median(stamps))

    log_files = sorted((directory / "log").glob("*_log.csv"))[:2]
    trace_files = sorted((directory / "trace").glob("*_trace.csv"))[:2]
    metrics_block = build_metrics_block(metrics, midpoint)
    logs_block = build_logs_block(read_rows(log_files), rng)
    traces_block = build_traces_block(read_rows(trace_files))

    start = datetime.datetime.fromtimestamp(
        midpoint - WINDOW_BEFORE, datetime.timezone.utc
    ).strftime("%H:%M")
    end = datetime.datetime.fromtimestamp(
        midpoint + WINDOW_AFTER, datetime.timezone.utc
    ).strftime("%H:%M")

    return {
        "id": case_id,
        "source": f"Nezha {DAYS[day]} {day} fault-free baseline phase (no fault injected)",
        "system": DAYS[day],
        "services": sorted(set(metrics_block) | set(traces_block)),
        "incident_window": f"{start}-{end} UTC",
        "modalities": {
            "metrics": metrics_block,
            "logs": logs_block,
            "traces": traces_block,
        },
        "ground_truth": {
            "culprit_service": "none",
            "fault_type": "none",
            "informative_modalities": [],
            "decoy_modalities": ["metrics", "logs", "traces"],
            "evidence_keywords": [],
        },
    }


# ----------------------------------------------------------------------- selection

def select(screened: list[dict[str, Any]], rng: random.Random) -> list[dict[str, Any]]:
    """Pick a spread of usable faults across systems, fault types and modalities.

    Aims for a mix no single-modality strategy can win: metric-informative CPU
    faults, log-informative code faults, and a couple of cases where both agree.
    """
    usable = [s for s in screened if s["usable"]]
    quotas = [
        ("onlineboutique", "metrics", 4),
        ("onlineboutique", "logs", 3),
        ("trainticket", "metrics", 2),
        ("trainticket", "logs", 2),
    ]

    chosen: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()

    both = [s for s in usable if len(s["informative"]) == 2]
    rng.shuffle(both)
    for candidate in both[:1]:
        chosen.append(candidate)
        seen_keys.add((candidate["service"], candidate["fault_type"]))

    for system, modality, quota in quotas:
        pool = [
            s
            for s in usable
            if s["system"] == system
            and modality in s["informative"]
            and s not in chosen
        ]
        rng.shuffle(pool)
        taken = 0
        for candidate in pool:
            key = (candidate["service"], candidate["fault_type"])
            if key in seen_keys:
                continue
            chosen.append(candidate)
            seen_keys.add(key)
            taken += 1
            if taken >= quota:
                break

    chosen.sort(key=lambda s: (s["system"], s["fault_type"], s["service"]))
    return chosen


def select_abstention(
    screened: list[dict[str, Any]], rng: random.Random, quota: int = N_ABSTENTION
) -> list[dict[str, Any]]:
    """Pick faults whose culprit is deeply buried, for the "unknown" cases.

    The 61 faults the signal gate rejects are not waste — they are the only
    honest way to test whether a model knows when the evidence does not support
    a conclusion, which is the failure mode that makes RCA tooling dangerous.

    "Rejected" alone is too weak a bar, though: a fault whose culprit ranks 2nd
    is arguably still findable by better reasoning than the screen's crude
    ranking. Only faults buried past ABSTENTION_MIN_RANK in *both* channels
    qualify, so a model that abstains is agreeing with strong evidence of
    absence rather than being punished for a near miss.
    """
    def buried(rank: Optional[int]) -> bool:
        # A missing rank means the service never even surfaced in that channel.
        return rank is None or rank >= ABSTENTION_MIN_RANK

    pool = [
        s for s in screened
        if not s["usable"] and buried(s["metric_rank"]) and buried(s["log_rank"])
    ]

    # Spread across systems and fault types so "unknown" can't be pattern-matched
    # to one system or one kind of fault.
    rng.shuffle(pool)
    chosen: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for candidate in pool:
        key = (candidate["system"], candidate["fault_type"])
        if key in seen:
            continue
        chosen.append(candidate)
        seen.add(key)
        if len(chosen) >= quota:
            break
    # Top up from the rest of the pool if the variety pass ran short.
    for candidate in pool:
        if len(chosen) >= quota:
            break
        if candidate not in chosen:
            chosen.append(candidate)

    chosen.sort(key=lambda s: (s["system"], s["fault_type"], s["service"]))
    return chosen


def case_id_for(screened: dict[str, Any], index: int) -> str:
    system = "ob" if screened["system"] == "onlineboutique" else "tt"
    fault = screened["fault_type"].replace("code_", "").replace("_", "")[:8]
    service = screened["service"].replace("ts-", "").replace("service", "").strip("-")
    return f"mm-{system}-{fault}-{service or 'svc'}-{index:02d}"


def abstention_id_for(screened: dict[str, Any], index: int) -> str:
    system = "ob" if screened["system"] == "onlineboutique" else "tt"
    return f"mm-{system}-unknown-{index:02d}"


# ----------------------------------------------------------------------------- main

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=20260816, help="deterministic sampling seed")
    parser.add_argument("--report", action="store_true", help="print the screen and exit")
    args = parser.parse_args()

    ensure_dataset()
    rng = random.Random(args.seed)

    screened: list[dict[str, Any]] = []
    for day in DAYS:
        faults = load_faults(day)
        if not faults:
            continue
        metrics = load_metrics(day)
        print(f"screening {day} ({DAYS[day]}): {len(faults)} faults", file=sys.stderr)
        for fault in faults:
            screened.append(screen_fault(day, fault, metrics))

    usable = [s for s in screened if s["usable"]]
    print(f"\nsignal gate: {len(usable)}/{len(screened)} faults usable", file=sys.stderr)

    if args.report:
        print(f"{'day':11s} {'service':26s} {'type':16s} {'m.rank':>7s} {'l.rank':>7s}  informative")
        for s in screened:
            print(
                f"{s['day']:11s} {s['service'][:25]:26s} {s['fault_type']:16s} "
                f"{str(s['metric_rank'] or '-'):>7s} {str(s['log_rank'] or '-'):>7s}  "
                f"{','.join(s['informative']) or '-'}"
            )
        return

    selected = select(screened, rng)
    cases = []
    for index, item in enumerate(selected, start=1):
        metrics = load_metrics(item["day"])
        cases.append(build_case(item, metrics, rng, case_id_for(item, index)))

    # "Insufficient evidence" cases, drawn from the faults the gate rejected.
    abstentions = select_abstention(screened, rng)
    for index, item in enumerate(abstentions, start=1):
        metrics = load_metrics(item["day"])
        cases.append(
            build_case(item, metrics, rng, abstention_id_for(item, index), abstain=True)
        )
    print(
        f"abstention pool: {len(abstentions)} of "
        f"{sum(1 for s in screened if not s['usable'])} rejected faults",
        file=sys.stderr,
    )

    clean = build_clean_case("2022-08-22", rng, "mm-ob-clean-baseline")
    if clean:
        cases.append(clean)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / "multimodal_rca.json"
    path.write_text(json.dumps(cases, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"\nwrote {path} ({len(cases)} cases)")
    for case in cases:
        truth = case["ground_truth"]
        print(
            f"  {case['id']:34s} {truth['culprit_service']:24s} {truth['fault_type']:18s} "
            f"informative={','.join(truth['informative_modalities']) or 'none'}"
        )


if __name__ == "__main__":
    main()
