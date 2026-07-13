"""Build the benchmark datasets from real Loghub data + hard synthetic generators.

Produces (deterministically, seeded):
  datasets/data/log_parsing.json        — real Loghub 2k lines with ground-truth templates
  datasets/data/anomaly_detection.json  — real labeled BGL windows + hard synthetic cases
  datasets/data/metrics_timeseries.json — seasonal series with subtle injected anomalies

pattern_correlation.json and root_cause.json are curated by hand and not
touched by this script.

Usage:
    python scripts/build_datasets.py            # downloads Loghub CSVs on first run
    python scripts/build_datasets.py --seed 7   # different deterministic sample
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "datasets" / "raw"
DATA_DIR = ROOT / "datasets" / "data"

LOGHUB_BASE = "https://raw.githubusercontent.com/logpai/logparser/main/data/loghub_2k"
PARSING_SYSTEMS = ["HDFS", "BGL", "OpenSSH", "Apache", "Zookeeper", "Linux"]


# --------------------------------------------------------------------------- raw data

def download_raw() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for system in PARSING_SYSTEMS:
        target = RAW_DIR / f"{system}_2k.log_structured.csv"
        if target.exists():
            continue
        url = f"{LOGHUB_BASE}/{system}/{system}_2k.log_structured.csv"
        print(f"downloading {url}")
        response = httpx.get(url, follow_redirects=True, timeout=60)
        response.raise_for_status()
        target.write_bytes(response.content)


def read_structured(system: str) -> list[dict[str, str]]:
    with open(RAW_DIR / f"{system}_2k.log_structured.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ------------------------------------------------------------------- log parsing cases

def build_log_parsing(rng: random.Random, cases_per_system: int = 3, lines_per_case: int = 8) -> list[dict]:
    cases = []
    for system in PARSING_SYSTEMS:
        rows = read_structured(system)
        by_template: dict[str, list[dict]] = {}
        for row in rows:
            template = row["EventTemplate"].strip()
            if len(template) >= 4:
                by_template.setdefault(template, []).append(row)
        templates = sorted(by_template)
        if len(templates) < lines_per_case:
            print(f"  {system}: only {len(templates)} templates, skipping", file=sys.stderr)
            continue
        # Constant templates (no <*>) punish over-wildcarding: keep some in the pool.
        constants = [t for t in templates if "<*>" not in t]
        variables = [t for t in templates if "<*>" in t]
        for case_index in range(cases_per_system):
            n_const = min(len(constants), 2)
            chosen = rng.sample(constants, n_const) + rng.sample(
                variables, min(len(variables), lines_per_case - n_const)
            )
            rng.shuffle(chosen)
            logs, truths = [], []
            for template in chosen:
                row = rng.choice(by_template[template])
                logs.append(row["Content"].strip())
                truths.append(template)
            cases.append(
                {
                    "id": f"lp-{system.lower()}-{case_index + 1:02d}",
                    "source": f"Loghub {system} 2k (logpai/logparser)",
                    "logs": logs,
                    "templates": truths,
                }
            )
    return cases


# -------------------------------------------------------------- anomaly detection cases

def build_bgl_anomaly_windows(rng: random.Random, n_windows: int = 6, window: int = 25) -> list[dict]:
    """Real labeled anomalies: BGL rows with Label != '-' are alerts.

    BGL is discriminative because normal lines include scary-sounding text
    ('instruction cache parity error corrected' is labeled NORMAL) while some
    alerts look mundane — keyword grep fails here.
    """
    rows = read_structured("BGL")
    candidates = []
    for start in range(0, len(rows) - window, window // 2):
        slice_ = rows[start : start + window]
        anomalies = [i for i, row in enumerate(slice_) if row["Label"].strip() != "-"]
        candidates.append((start, slice_, anomalies))

    mixed = [c for c in candidates if 2 <= len(c[2]) <= window // 2]
    clean = [c for c in candidates if len(c[2]) == 0]
    rng.shuffle(mixed)
    rng.shuffle(clean)
    selected = mixed[: n_windows - 1] + clean[:1]

    cases = []
    for idx, (start, slice_, anomalies) in enumerate(selected, start=1):
        cases.append(
            {
                "id": f"ad-bgl-{idx:02d}",
                "source": f"Loghub BGL 2k rows {start}-{start + window} (real alert labels)",
                "logs": [row["Content"].strip() for row in slice_],
                "anomalous_indices": anomalies,
            }
        )
    return cases


def _interleave(rng: random.Random, normal: list[str], anomalous: list[str]) -> tuple[list[str], list[int]]:
    """Insert anomalous lines (order preserved) at random positions among normal ones."""
    logs = list(normal)
    positions = sorted(rng.sample(range(1, len(logs)), len(anomalous)))
    for offset, (pos, line) in enumerate(zip(positions, anomalous)):
        logs.insert(pos + offset, line)
    indices = [logs.index(line) for line in anomalous]
    return logs, sorted(indices)


def build_synthetic_anomalies(rng: random.Random) -> list[dict]:
    cases = []

    # 1. JVM service: numeric outliers hidden in routine GC/request noise.
    normal = []
    for i in range(24):
        kind = i % 4
        if kind == 0:
            normal.append(f"GC pause {rng.randint(35, 95)}ms, heap {rng.randint(52, 68)}% used")
        elif kind == 1:
            normal.append(f"GET /api/v2/items 200 in {rng.randint(20, 140)}ms")
        elif kind == 2:
            normal.append(f"WARN slow query took {rng.randint(600, 950)}ms: SELECT * FROM items WHERE tenant_id=?")
        else:
            normal.append(f"connection pool: {rng.randint(6, 12)}/40 in use")
    anomalous = [
        "GC pause 14280ms, heap 97% used",
        "GET /api/v2/items 200 in 21903ms",
        "java.lang.OutOfMemoryError: GC overhead limit exceeded in thread pool-3-worker-11",
    ]
    logs, indices = _interleave(rng, normal, anomalous)
    cases.append({
        "id": "ad-syn-jvm",
        "source": "synthetic: numeric outliers among routine warnings (slow queries are normal here)",
        "logs": logs,
        "anomalous_indices": indices,
    })

    # 2. Auth service: isolated failed logins are routine; a coordinated
    #    brute-force burst followed by a success is the anomaly.
    users = ["alice", "bob", "carol", "dave", "erin", "frank"]
    normal = []
    for i in range(20):
        user = rng.choice(users)
        ip = f"10.0.{rng.randint(0, 4)}.{rng.randint(10, 250)}"
        if i % 6 == 3:
            normal.append(f"login failed for {user} from {ip}: invalid password (attempt 1)")
        elif i % 6 == 5:
            normal.append(f"password reset requested by {user}")
        else:
            normal.append(f"login success for {user} from {ip}")
    anomalous = [
        "login failed for svc-backup from 185.220.101.34: invalid password (attempt 1)",
        "login failed for svc-backup from 185.220.101.34: invalid password (attempt 2)",
        "login failed for svc-backup from 185.220.101.34: invalid password (attempt 3)",
        "login failed for svc-backup from 185.220.101.34: invalid password (attempt 4)",
        "login success for svc-backup from 185.220.101.34",
        "api token created by svc-backup with scope admin:*",
    ]
    logs, indices = _interleave(rng, normal, anomalous)
    cases.append({
        "id": "ad-syn-auth",
        "source": "synthetic: brute-force burst + takeover; isolated login failures are normal noise",
        "logs": logs,
        "anomalous_indices": indices,
    })

    # 3. Rolling deploy: scary-looking but *normal* pod restarts (decoys);
    #    the anomaly is one pod OOM crash-looping.
    normal = []
    for replica in range(1, 7):
        normal.append(f"Killing container web in pod web-{replica:02d} for rolling update to v2.9.0")
        normal.append(f"Pulled image registry.local/web:v2.9.0 in {rng.randint(1, 4)}.{rng.randint(0, 9)}s")
        normal.append(f"Started container web in pod web-{replica:02d}")
        normal.append(f"Readiness probe succeeded for pod web-{replica:02d}")
    anomalous = [
        "Container web in pod web-04 terminated: OOMKilled (exit code 137)",
        "Back-off restarting failed container web in pod web-04 (restart count 4)",
        "Container web in pod web-04 terminated: OOMKilled (exit code 137)",
    ]
    logs, indices = _interleave(rng, normal, anomalous)
    cases.append({
        "id": "ad-syn-deploy",
        "source": "synthetic: rolling-update kills are normal; the OOM crash loop is not",
        "logs": logs,
        "anomalous_indices": indices,
    })

    # 4. Clean case: a busy, healthy service full of routine WARNs. Punishes
    #    models that flag anything containing 'warn'/'retry'/'failed over'.
    logs = []
    for i in range(22):
        kind = i % 5
        if kind == 0:
            logs.append(f"processed batch {4000 + i} ({rng.randint(800, 1200)} events) in {rng.randint(90, 240)}ms")
        elif kind == 1:
            logs.append(f"WARN cache miss ratio {rng.randint(12, 24)}% over last minute, within budget")
        elif kind == 2:
            logs.append(f"retrying fetch of shard {rng.randint(1, 8)} metadata, attempt 1 of 5 — succeeded")
        elif kind == 3:
            logs.append("health check passed: all 12 downstream dependencies reachable")
        else:
            logs.append(f"rotated log file app.{rng.randint(10, 30)}.log, freed {rng.randint(40, 90)}MB")
    cases.append({
        "id": "ad-syn-clean",
        "source": "synthetic: healthy service, zero anomalies (over-flagging scores 0)",
        "logs": logs,
        "anomalous_indices": [],
    })

    # 5. Data pipeline: silent correctness anomaly — record counts collapse
    #    without any ERROR keyword at all.
    normal = [f"ingest tick {i:02d}: wrote {rng.randint(9200, 10800)} records to warehouse" for i in range(18)]
    anomalous = [
        "ingest tick 18: wrote 312 records to warehouse",
        "ingest tick 19: wrote 0 records to warehouse",
        "ingest tick 20: wrote 0 records to warehouse",
    ]
    logs, indices = _interleave(rng, normal, anomalous)
    cases.append({
        "id": "ad-syn-silent",
        "source": "synthetic: silent data loss, no error keywords at all",
        "logs": logs,
        "anomalous_indices": indices,
    })

    return cases


# ------------------------------------------------------------------ time series cases

def _seasonal_series(rng: random.Random, length: int, base: float, amplitude: float, noise: float) -> list[float]:
    return [
        base + amplitude * math.sin(2 * math.pi * i / 24) + rng.gauss(0, noise)
        for i in range(length)
    ]


def build_timeseries(rng: random.Random) -> list[dict]:
    """Seasonal series where global z-scores fail: anomalies are deviations
    from the *expected seasonal value*, sometimes smaller than the seasonal
    swing itself. Includes level shifts, off-peak spikes, and clean series.
    """
    cases = []
    specs = [
        # (id, metric, base, amplitude, noise, anomaly spec)
        ("ts-cpu-offpeak-spike", "cpu_percent", 45, 18, 1.5, ("spikes", 3, 14)),
        ("ts-latency-shift", "p99_latency_ms", 220, 60, 8, ("shift", 10, 90)),
        ("ts-rps-dip", "requests_per_second", 900, 350, 20, ("dips", 2, 0.15)),
        ("ts-mem-creep", "memory_percent", 55, 8, 1.0, ("shift", 14, 18)),
        ("ts-err-rate-burst", "error_rate_percent", 1.2, 0.5, 0.12, ("spikes", 4, 4.5)),
        ("ts-disk-io-clean", "disk_iops", 400, 120, 15, None),
        ("ts-queue-spike", "queue_depth", 80, 30, 5, ("spikes", 2, 160)),
        ("ts-conn-drop", "active_connections", 1500, 400, 40, ("dips", 3, 0.08)),
        ("ts-temp-clean", "gpu_temp_celsius", 62, 6, 0.8, None),
        ("ts-p50-slow-shift", "p50_latency_ms", 45, 10, 2.0, ("shift", 12, 22)),
    ]
    for case_id, metric, base, amplitude, noise, anomaly in specs:
        length = 96  # 24h at 15-minute resolution, two seasonal cycles per day
        values = _seasonal_series(rng, length, base, amplitude, noise)
        indices: list[int] = []
        if anomaly is not None:
            kind, count_or_len, magnitude = anomaly
            if kind == "spikes":
                indices = sorted(rng.sample(range(8, length - 8), count_or_len))
                for i in indices:
                    values[i] += magnitude
            elif kind == "dips":
                indices = sorted(rng.sample(range(8, length - 8), count_or_len))
                for i in indices:
                    values[i] *= magnitude
            elif kind == "shift":
                start = rng.randint(20, length - count_or_len - 10)
                indices = list(range(start, start + count_or_len))
                for i in indices:
                    values[i] += magnitude
        cases.append(
            {
                "id": case_id,
                "metric": metric,
                "values": [round(v, 2) for v in values],
                "anomalous_indices": indices,
            }
        )
    return cases


# ----------------------------------------------------------------------------- main

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=20260713, help="deterministic sampling seed")
    args = parser.parse_args()

    download_raw()
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    rng = random.Random(args.seed)
    outputs = {
        "log_parsing.json": build_log_parsing(rng),
        "anomaly_detection.json": build_bgl_anomaly_windows(rng) + build_synthetic_anomalies(rng),
        "metrics_timeseries.json": build_timeseries(rng),
    }
    for filename, cases in outputs.items():
        path = DATA_DIR / filename
        path.write_text(json.dumps(cases, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {path} ({len(cases)} cases)")

    print("\npattern_correlation.json and root_cause.json are curated by hand — not regenerated.")


if __name__ == "__main__":
    main()
