# llm-sre-bench

**Benchmark frontier LLMs on real SRE work: log parsing, anomaly detection, incident correlation, and root-cause analysis.**

Most LLM benchmarks test general reasoning. This one tests whether a model can actually do
the job of an on-call engineer: parse raw production logs, spot the anomaly that isn't
shouting `ERROR`, trace a failure cascade across services, and name the root cause while
ignoring the red herrings. It runs the same standardized tests against any set of models
(Grok, Claude, GPT, local models via LM Studio/Ollama/vLLM, …) and produces a ranked,
weighted scorecard.

```
┏━━━━━━┳━━━━━━━━┳━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━┳━━━━━━━━┓
┃ Rank ┃ Model  ┃ Global ┃ parsing ┃ anomaly ┃ pattern ┃ metrics ┃ root   ┃ mm-rca  ┃ effic. ┃
┡━━━━━━╇━━━━━━━━╇━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━╇━━━━━━━━┩
│    1 │ grok-4 │   73.7 │    90.0 │    66.0 │    76.0 │    80.0 │   49.0 │     —   │   76.9 │
└──────┴────────┴────────┴─────────┴─────────┴─────────┴─────────┴────────┴─────────┴────────┘
```

*A frontier model scoring ~74 is by design — the suite is built to leave headroom, not to
hand out perfect scores.*

## Why this benchmark is hard

- **Real data with real labels.** Log parsing uses genuine [Loghub](https://github.com/logpai/loghub)
  production logs (HDFS, BGL, OpenSSH, Zookeeper, Linux) with official ground-truth templates.
  Anomaly detection includes windows of BGL supercomputer logs with the dataset's real alert
  labels — where `"instruction cache parity error corrected"` is *normal* and keyword-grepping
  for "error" scores ~40.
- **Traps for cheap heuristics.** Clean cases punish over-flagging (models that "find" anomalies
  in healthy logs score 0 on them). Decoy warnings look scary but are routine. One case is
  silent data loss with no error keyword anywhere.
- **Seasonality-aware time series.** Metric series follow a daily cycle, so a global z-score
  misses off-peak spikes and level shifts that a competent analysis catches.
- **Red herrings in incidents.** Root-cause cases include unrelated deploys, failing crons, and
  network blips that happened during the window and must be ruled out — just like real postmortems.
- **Multi-modal incidents where the useful signal moves.** Real microservice faults are presented
  as metrics + logs + traces together. CPU faults show up only in the metrics; code-level faults
  only in the logs. A model that always reads the same modality scores 0 on half the cases.
- **Rule-based baseline included.** A keyword/z-score mock scores ~55 overall; the gap between
  that and a frontier model is the signal.

## Test categories & scoring

| Category | Weight | What's measured |
|---|---|---|
| Log Parsing | 15% | Template extraction accuracy + token F1 vs Loghub ground truth |
| Anomaly Detection | 25% | Precision / Recall / F1 on per-line labels |
| Pattern & Correlation | 15% | Pattern coverage + causal chain accuracy (A→B→C cascades) |
| Metrics Time-Series | 10% | Point-wise F1 (±1 tolerance) on injected anomalies |
| Root Cause & Summary | 10% | ROUGE-1/L + keyword recall vs reference (optional LLM-as-judge) |
| **Multi-modal RCA** | **20%** | Culprit localization across metrics + logs + traces on real microservice incidents |
| Efficiency & Consistency | 5% | Latency, token usage, run-to-run score variance |

**Global score** = weighted average, 0–100. Every case runs `runs_per_test` times (default 3);
scores are averaged per case, then per category. Answers must be strict JSON validated against
pydantic schemas — unparseable output scores 0 for that run.

## Multi-modal RCA

The other categories hand the model one kind of data. This one hands it three — per-service
**metrics**, **logs**, and **trace** aggregates from a real microservice incident — and asks
which service caused it, from a closed candidate list.

Cases are built from [Nezha](https://github.com/IntelligentDDS/Nezha) (FSE'23), which ships 101
fault injections into OnlineBoutique and TrainTicket with ground truth naming the injected pod
and fault type.

**What makes it hard: the informative modality changes case to case.**

- CPU faults (`cpu_saturation`) are visible in the metric series and leave the logs completely
  ordinary.
- Code-level faults (`code_return_value`, `code_exception`) surface only in the logs and barely
  move CPU at all.
- One case has no fault at all — the correct answer is `none`, and inventing a culprit scores 0
  on localization.

So a model has to work out *which* signal to trust, not just read the one it was given. The
scoring makes that explicit:

```
0.40  culprit localization  exact service match, else 0
0.25  fault-type accuracy   exact match against a closed vocabulary
0.25  modality grounding    F1 of cited modalities vs the ones that carry signal
0.10  evidence quality      keyword recall over the ground-truth markers
```

**Modality grounding is not a formality.** Every case records which modalities actually localize
its fault — *measured* by the dataset builder, never hand-asserted: it ranks services by CPU
through the metric channel and by error-log rate through the log channel, and a modality only
counts as informative if it puts the injected pod first. Citing a modality that shows nothing
costs precision, so "cite all three" caps the component well below 1.0.

The bundled rule-based baseline demonstrates the point: a heuristic that always picks the
highest-CPU service scores **100 on every CPU case and 0 on every log-only case**, landing at
~59 overall. Single-modality strategies cannot win this category.

Only 40 of Nezha's 101 faults survive the signal gate — the rest are dropped because the culprit
is not recoverable from the bundled evidence, and a case nobody can solve measures nothing. The
same principle applies to the labels: Nezha separates `cpu_contention` from `cpu_consumed`, but
the two are indistinguishable in the observability data (the same service under either fault
shows the same pod *and* node CPU), so they collapse to one `cpu_saturation` label rather than
scoring models on a coin flip.
Rebuild or re-sample the set with:

```bash
python scripts/build_multimodal_rca.py --report   # print the signal screen, build nothing
python scripts/build_multimodal_rca.py            # rebuild (clones Nezha on first run)
```

## Quick start

Requires Python 3.11+.

```bash
git clone https://github.com/<you>/llm-sre-bench.git
cd llm-sre-bench
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Smoke test — no API keys needed (offline rule-based mock models)
python benchmark.py run --config models.mock.json

# Real benchmark
cp .env.example .env          # add the API keys you have
python benchmark.py run       # all configured models
```

Useful variations:

```bash
python benchmark.py run -m grok-4 -m claude-opus-4-8   # subset of models
python benchmark.py run -c anomaly_detection            # single category
python benchmark.py run --runs 1                        # quick pass (1/3 of the calls)
python benchmark.py list-models                         # check which keys are set
python benchmark.py list-categories
```

### Running models one at a time (recommended for local / expensive models)

You can run models sequentially. Each model’s raw results are saved in its own folder:

```bash
python benchmark.py run -m grok-4
python benchmark.py run -m claude-opus-4-8
python benchmark.py run -m llama-3.3-70b --runs 1
```

After running any number of models, (re)build the combined comparison:

```bash
python benchmark.py aggregate
```

This command scans `results/<model>/records.json` for every model and regenerates
`comparison_table.md`, `summary_report.md`, `detailed_results.csv`, and `results.json`.

**Cost:** a full 3-run pass is ~155k input + ~20k output tokens per model — roughly **$0.30–$3.00
per frontier model** at current list prices. (Multi-modal RCA is about 90k of that input on its
own: its bundles are far larger than the single-modality cases.) Responses are cached in
`.cache/`, so interrupted or repeated runs never re-pay for the same call.

You can selectively clear the cache for one model (useful when you want to re-run fresh):

```bash
python benchmark.py clear-cache -m grok-4
python benchmark.py run -m grok-4
```

- Use `--no-cache` on `run` to bypass the cache for a single execution without deleting anything.
- `python benchmark.py clear-cache --all` wipes the entire cache.

## Output

### Per-model folders (new canonical layout)

Results for each model are stored separately:

```
results/
├── grok-4/
│   ├── records.json       # All individual runs for this model (source of truth)
│   └── summary.json
├── claude-opus-4-8/
│   └── ...
├── comparison_table.md    # Regenerated by `python benchmark.py aggregate`
├── summary_report.md
├── detailed_results.csv
└── results.json
```

This design lets you run expensive or local models one-by-one (even across days) and later combine them.

### Aggregated reports

Run this anytime to rebuild the cross-model view from all per-model folders:

```bash
python benchmark.py aggregate
```

| File | Contents |
|---|---|
| `comparison_table.md` | Ranked comparison table with per-category scores |
| `summary_report.md` | Ranking, category leaders, efficiency details, recommendations |
| `detailed_results.csv` | Combined view across all models |
| `results.json` | Full machine-readable results |

Progress streams live in the terminal with per-call scores.

## Configuring models (`models.json`)

```json
{
  "runs_per_test": 3,
  "temperature": 0.0,
  "max_tokens": 4096,
  "request_timeout": 120,
  "judge_model": null,
  "models": [
    { "name": "grok-4", "provider": "xai", "base_url": "https://api.x.ai/v1",
      "api_key": "${XAI_API_KEY}", "model_id": "grok-4" },
    { "name": "claude-opus-4-8", "provider": "anthropic",
      "api_key": "${ANTHROPIC_API_KEY}", "model_id": "claude-opus-4-8" },
    { "name": "llama-3.3-70b", "provider": "openai",
      "base_url": "http://localhost:1234/v1", "model_id": "meta/llama-3.3-70b" }
  ]
}
```

| Provider | Works with | Notes |
|---|---|---|
| `openai`, `xai` | Any OpenAI-compatible endpoint | OpenAI, xAI, Groq, Together, DeepSeek, Mistral, **LM Studio**, **vLLM**, llama.cpp — set `base_url`. Local `http://` servers need no API key. |
| `anthropic` | Claude models | Official SDK; sampling params omitted (Opus 4.7+ rejects them) |
| `ollama` | Ollama's native API | Local models, no key |
| `mock` | — | Offline rule-based baseline for smoke tests |

API keys are referenced as `${ENV_VAR}` placeholders resolved from your environment / `.env` —
no secrets in the config file.

**Reliability:** models with missing keys are skipped with a warning, unreachable endpoints
fail fast, any per-call failure is recorded and the run continues, and a model failing 5 calls
in a row is circuit-broken instead of stalling the benchmark. One bad model never ruins a run.
Transient failures (intermittent 401s, timeouts, rate limits, malformed JSON) are automatically
re-attempted after the main pass — `--retries N` sets the number of extra passes (default 1;
`--retries 0` disables). Permanent failures (403 no-access, 404, connection refused) are not
retried. Because the cache only stores successes, retries and re-runs cost only the failed calls.

**LLM-as-judge (optional):** set `"judge_model"` to one of your configured model names and
root-cause answers get graded 0–10 by that model against the reference
(score = 0.7 × judge + 0.3 × reference metrics).

## The datasets (59 cases)

| File | Cases | Source |
|---|---|---|
| `log_parsing.json` | 15 | Real Loghub 2k logs + official templates ([logpai/logparser](https://github.com/logpai/logparser)) |
| `anomaly_detection.json` | 11 | 6 real labeled BGL windows + 5 hard synthetics (decoys, silent failures, clean case) |
| `metrics_timeseries.json` | 10 | Seasonal series (96 pts, daily cycle): off-peak spikes, level shifts, dips, 2 clean |
| `pattern_correlation.json` | 5 | Curated multi-service cascades with distractors and 2-hop causal chains |
| `root_cause.json` | 5 | Curated incidents with red herrings and reference answers |
| `multimodal_rca.json` | 13 | Real [Nezha](https://github.com/IntelligentDDS/Nezha) microservice incidents (metrics + logs + traces), signal-screened, + 1 healthy baseline |

Regenerate or scale up the generated portions deterministically:

```bash
python scripts/build_datasets.py [--seed N]          # re-downloads Loghub CSVs to datasets/raw/
python scripts/build_multimodal_rca.py [--seed N]    # clones Nezha to datasets/raw/nezha/
```

The Nezha clone is ~343 MB (≈3.2 GB unpacked) and lands in the gitignored `datasets/raw/`;
`multimodal_rca.json` itself is committed, so you only need the clone to rebuild.

`pattern_correlation.json` and `root_cause.json` are curated by hand — edit them directly.
You can also point `--data-dir` at your own directory with the same file names (great for
benchmarking on *your* production logs).

## Project layout

```
benchmark.py             CLI (typer + rich): run, aggregate, list-models, list-categories
models.json              model/provider configuration
core/                    config, provider clients, prompts, schemas, runner, cache
evaluators/              one scorer per category + efficiency
datasets/data/           bundled test cases (JSON)
scripts/build_datasets.py         deterministic dataset builder (Loghub + synthetic)
scripts/build_multimodal_rca.py   Nezha builder: signal screen + modality bundling
reports/                 aggregation + report generation
```

## Extending

- **Add a model:** append an entry to `models.json`. Any OpenAI-compatible API works out of
  the box; new native protocols need a small client in `core/clients.py`.
- **Add test cases:** append to the JSON files (shapes documented in `datasets/loaders.py`),
  or grow the generated sets via `scripts/build_datasets.py`.
- **Add a category:** dataset file + prompt template (`core/prompts.py`) + answer schema
  (`core/schemas.py`) + evaluator (`evaluators/`) + weight (`core/config.py`).

## Acknowledgements

Log data from [Loghub](https://github.com/logpai/loghub) / [logparser](https://github.com/logpai/logparser)
(LogPAI team) — please cite their work if you publish results based on these datasets.

Multi-modal RCA cases are derived from [Nezha](https://github.com/IntelligentDDS/Nezha)
(IntelligentDDS, FSE 2023) — *Nezha: Interpretable Fine-Grained Root Causes Analysis for
Microservices on Multi-Modal Observability Data*. Please cite their paper if you publish results
based on this category.
