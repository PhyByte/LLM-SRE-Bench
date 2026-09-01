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
  metrics_timeseries.json  {"id", "metric", "values": [...], "anomalous_indices": [...],
                            optional "tolerance"}
  root_cause.json          {"id", "logs": [...], "reference_root_cause",
                            "reference_summary", "keywords": [...]}
  multimodal_rca.json      {"id", "system", "services": [...], "incident_window",
                            "modalities": {"metrics": {svc: [lines]},
                                           "logs": [...],
                                           "traces": {svc: summary}},
                            "ground_truth": {"culprit_service", "fault_type",
                                             "informative_modalities": [...],
                                             "decoy_modalities": [...],
                                             "evidence_keywords": [...]}}

The developer track's five files share a base shape — {"id", "language",
"task_family", "skill", "difficulty", "spec", "signature", "io", "test_cases"}
— and add what their category needs. ("io" is absent on the six original
code_generation families, which predate it and are driven by per-family
harnesses in evaluators/code_exec.py instead.) Do not hand-edit them: they are generated
by scripts/build_code_challenges.py, which computes every expected value from a
reference implementation and can re-verify the whole set against the real
compilers (``--check``).

  code_generation.json     base shape only
  code_efficiency.json     + "workload" (in-language generated input and its
                             answer) and "time_budget_ms" (per language)
  code_debugging.json      + "buggy_code", "symptom", and "regression_indices"
                             (which tests the buggy version fails, measured
                             per language when the dataset is built)
  code_refactoring.json    + "original_code", "goal" and "structure" (the
                             regex rules the refactor must satisfy)
  code_review.json         {"id", "language", "component", "context", "code",
                            "defects": [{"id", "line", "severity",
                                         "keywords_any": [...]}]} — no
                            execution, so no io/test_cases

``io`` declares the argument and return types the harness renders literals
from: int, float, str, bool, list<T>, pair<T,T>, map<str,T>.
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
