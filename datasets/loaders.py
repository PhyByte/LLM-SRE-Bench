"""Dataset loading.

Each task category has a JSON file under datasets/data/ holding a list of test
cases. The bundled samples are small, Loghub-inspired sets (HDFS/BGL-style
logs) plus synthetic metrics series, so the benchmark runs out of the box.

To add cases, append objects to the JSON files (or point --data-dir at your
own directory with the same file names). Expected shapes:

  log_parsing.json         {"id", "logs": [...], "templates": [...]}
  anomaly_detection.json   {"id", "logs": [...], "anomalous_indices": [...]}
  pattern_correlation.json {"id", "logs": [...],
                            "expected_patterns": [{"name", "keywords": [...]}],
                            "expected_correlations": [{"cause", "effect"}]}
  metrics_timeseries.json  {"id", "metric", "values": [...], "anomalous_indices": [...]}
  root_cause.json          {"id", "logs": [...], "reference_root_cause",
                            "reference_summary", "keywords": [...]}
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).parent / "data"


def load_category(category: str, data_dir: str | Path | None = None) -> list[dict[str, Any]]:
    directory = Path(data_dir) if data_dir else DATA_DIR
    path = directory / f"{category}.json"
    if not path.exists():
        raise FileNotFoundError(f"no dataset file for category '{category}': {path}")
    with open(path, encoding="utf-8") as f:
        cases = json.load(f)
    if not isinstance(cases, list) or not cases:
        raise ValueError(f"{path} must contain a non-empty JSON list of test cases")
    return cases


def load_datasets(
    categories: list[str], data_dir: str | Path | None = None
) -> dict[str, list[dict[str, Any]]]:
    return {category: load_category(category, data_dir) for category in categories}


def generate_synthetic_timeseries(
    case_id: str,
    metric: str = "cpu_percent",
    length: int = 60,
    n_anomalies: int = 3,
    seed: int = 42,
) -> dict[str, Any]:
    """Generate a synthetic metric series with injected spike anomalies.

    Useful for expanding the metrics_timeseries dataset beyond the bundled
    samples: dump the returned dicts into metrics_timeseries.json.
    """
    rng = random.Random(seed)
    baseline = rng.uniform(30, 60)
    values = [round(baseline + rng.gauss(0, 2.0), 2) for _ in range(length)]
    anomaly_indices = sorted(rng.sample(range(5, length - 5), n_anomalies))
    for idx in anomaly_indices:
        spike = rng.choice([-1, 1]) * rng.uniform(25, 45)
        values[idx] = round(values[idx] + spike, 2)
    return {
        "id": case_id,
        "metric": metric,
        "values": values,
        "anomalous_indices": anomaly_indices,
    }
