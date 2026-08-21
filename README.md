# llm-sre-bench

**Benchmark frontier LLMs on real SRE work and developer coding tasks.**

This benchmark tests models on two tracks:

1. **SRE/Observability Track**: log parsing, anomaly detection, incident correlation, and root-cause analysis
2. **Developer Track**: real coding tasks across Python, TypeScript, Go, and Rust

Most LLM benchmarks test general reasoning. The SRE track tests whether a model can actually do
the job of an on-call engineer: parse raw production logs, spot the anomaly that isn't
shouting `ERROR`, trace a failure cascade across services, and name the root cause while
ignoring the red herrings.

The developer track tests practical coding ability with tasks that feel like real Cursor work,
not leetcode puzzles: string processing, data structures, config merging, rate limiting, and
log parsing — the kind of code developers actually write.

```
┏━━━━━━┳━━━━━━━━┳━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━┳━━━━━━━━┓
┃ Rank ┃ Model  ┃ Global ┃ parsing ┃ anomaly ┃ pattern ┃ metrics ┃ root   ┃ mm-rca  ┃ effic. ┃
┡━━━━━━╇━━━━━━━━╇━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━╇━━━━━━━━┩
│    1 │ grok-4 │   73.7 │    90.0 │    66.0 │    76.0 │    80.0 │   49.0 │     —   │   76.9 │
└──────┴────────┴────────┴─────────┴─────────┴─────────┴─────────┴────────┴─────────┴────────┘
```

*A frontier model scoring ~74 on the SRE track is by design — the suite is built to leave headroom, not to
hand out perfect scores.*

## Tracks

### SRE/Observability Track (default)

The original track focused on SRE and production operations:

## Why the SRE track is hard

- **Real data with real labels.** Log parsing uses genuine [Loghub](https://github.com/logpai/loghub)
  production logs (HDFS, BGL, OpenSSH, Zookeeper, Linux) with official ground-truth templates.
  Anomaly detection includes windows of BGL supercomputer logs with the dataset's real alert
  labels — where `"instruction cache parity error corrected"` is *normal* and keyword-grepping
  for "error" scores ~40.
- **Traps for cheap heuristics.** Clean cases punish over-flagging (models that "find" anomalies
  in healthy logs score 0 on them). Decoy warnings look scary but are routine. One case is
  silent data loss with no error keyword anywhere.
- **Seasonality-aware time series.** Metric series follow a daily cycle, so a global z-score
  misses off-peak spikes and level shifts. Harder cases add in-band peaks, weekend-vs-weekday
  dips, stuck/flatline sensors, counter wraps, and stale held samples — flagging the global
  max is not enough.
- **Red herrings in incidents.** Root-cause cases include unrelated deploys, failing crons, and
  network blips that happened during the window and must be ruled out — just like real postmortems.
- **Multi-modal incidents where the useful signal moves.** Real microservice faults are presented
  as metrics + logs + traces together. CPU faults show up only in the metrics; code-level faults
  only in the logs. A model that always reads the same modality scores 0 on half the cases.
- **Rule-based baseline included.** A keyword/z-score mock scores ~55 overall; the gap between
  that and a frontier model is the signal.

### Developer Track (code generation)

The developer track tests practical coding across four languages:

- **Real coding tasks, not puzzles.** Tasks feel like actual Cursor work: slugify a string, merge
  intervals, implement a rate limiter, overlay config dicts, build an LRU cache, parse structured logs.
  No artificial leetcode-style problems.
- **Four languages with the same task families.** The same 6 task families (slugify, interval merge,
  rate limiter, config overlay, LRU cache, log parser) run across Python, TypeScript, Go, and Rust,
  so you can compare model performance across languages.
- **Hidden test execution.** The prompt gives a spec and required signature, but not the test cases.
  Models must generate correct, working code that compiles and passes hidden unit tests.
- **Sandboxed execution.** Generated code runs in a tight sandbox with timeouts, no network, temp
  directory isolation, and resource limits. Compilation failures, runtime crashes, timeouts, or
  incorrect output all affect the score.
- **Scored on correctness + efficiency + code quality.** 60% correctness (tests passed), 20%
  compilation success, 10% runtime efficiency, 10% code quality (size penalty for verbose code).
- **Toolchain detection.** If Python/TypeScript/Go/Rust isn't installed, that language's cases are
  skipped (and recorded) instead of crashing the run. The mock provider works offline with no
  compilers needed for smoke testing.

The mock-heuristic baseline generates syntactically valid code that passes some simple tests but
fails on edge cases, giving frontier models room to demonstrate understanding.

## Test categories & scoring (SRE track)

|| Category | Weight | What's measured |
|---|---|---|
| Log Parsing | 15% | Template extraction accuracy + token F1 vs Loghub ground truth |
| Anomaly Detection | 25% | Precision / Recall / F1 on per-line labels |
| Pattern & Correlation | 15% | Pattern coverage + causal chain accuracy (A→B→C cascades) |
| Metrics Time-Series | 10% | Point-wise F1 (default ±1 tolerance) on injected anomalies |
| Root Cause & Summary | 10% | ROUGE-1/L + keyword recall vs reference (optional LLM-as-judge) |
| **Multi-modal RCA** | **20%** | Culprit localization across metrics + logs + traces on real microservice incidents |
| Efficiency & Consistency | 5% | Latency, token usage, run-to-run score variance |

**Global score** = weighted average, 0–100. Every case runs `runs_per_test` times (default 3);
scores are averaged per case, then per category. Answers must be strict JSON validated against
pydantic schemas — unparseable output scores 0 for that run.

## Developer track categories & scoring

| Category | Weight | What's measured |
|---|---|---|
| Code Generation | 95% | Correctness (60%), compilation (20%), runtime efficiency (10%), code quality (10%) across 24 cases covering 6 task families × 4 languages |
| Efficiency & Consistency | 5% | Latency, token usage, run-to-run score variance |

**Global score** = weighted average, 0–100. Cases are run `runs_per_test` times (default 3) and
averaged. For code generation, each case generates code that is compiled and executed against
hidden unit tests in a sandbox. Tests passed, compilation success, runtime speed, and code size
all factor into the score.

**Languages tested:** Python, TypeScript, Go, Rust

**Task families (same across all 4 languages):**
- Slugify (string processing)
- Interval merge (algorithm + edge cases)
- Rate limiter (sliding window, state management)
- Config overlay (recursive dict merge)
- LRU cache (data structure, O(1) requirement)
- Log parser (regex, error handling, SRE tie-in)

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
- **Five cases cannot be solved, and knowing that is the answer.** A fault really was injected,
  but it is buried in every channel. The calibrated verdict is `unknown`.

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

### Knowing when you can't tell

An RCA tool that confidently names the wrong service sends someone to the wrong place at 3am. So
three verdicts are possible, and telling them apart is most of the task:

| Verdict | Means |
|---|---|
| a service name | the evidence identifies that service |
| `none` | the system is healthy — nothing here is a fault |
| `unknown` | something is wrong, but this evidence doesn't show which service |

`none` and `unknown` are deliberately **not** interchangeable: a false all-clear is a different
failure from an honest "I can't attribute this", and only one of them is safe.

The five `unknown` cases are drawn from the faults the signal gate **rejected** — real injections
whose culprit ranks 6th or worse in *both* the metric and log channels. Scoring on an abstention
case:

| Answer | Score |
|---|---|
| `unknown` | 100 |
| the true culprit (found anyway) | 100 |
| `none` — false all-clear | 35 |
| a confident wrong service | 10 |

Naming the true culprit also scores full marks: the screen is a crude ranking, and a model that
genuinely out-reasons it hasn't made a mistake. What's punished is confident misattribution.
Nor can a model game this by always abstaining — that strategy scores ~30 overall, well below
the rule-based baseline. The baseline itself is confidently wrong on **all five**.

### Cases nobody can solve are dropped, and labels nobody can distinguish are merged

Only 40 of Nezha's 101 faults survive the signal gate for the solvable set — the rest are dropped
because the culprit is not recoverable, and a case nobody can solve measures nothing (five of
them are reused as the `unknown` cases above). The same principle applies to the labels: Nezha
separates `cpu_contention` from `cpu_consumed`, but the two are indistinguishable in the
observability data (the same service under either fault shows the same pod *and* node CPU), so
they collapse to one `cpu_saturation` label rather than scoring models on a coin flip.
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

# Smoke test — no API keys or compilers needed (offline rule-based mock models)
python benchmark.py run --config models.mock.json

# Run the SRE track only (default)
cp .env.example .env          # add the API keys you have
python benchmark.py run       # all configured models on SRE track

# Run the developer track
python benchmark.py run --suite developer

# Run both tracks
python benchmark.py run --suite all
```

**Developer track requirements:** To actually execute code and score results (not required for
mock/smoke tests), install the language toolchains:

- **Python:** `python3` (already required for the benchmark itself)
- **TypeScript:** `node` + `tsx` (install: `npm install -g tsx`)
- **Go:** `go` (install from golang.org)
- **Rust:** `rustc` (install from rust-lang.org)

Missing toolchains are detected at runtime; cases for unavailable languages are skipped and
recorded rather than crashing. You can run the developer track with only Python installed —
the other languages will be skipped.

Useful variations:

```bash
python benchmark.py run -m grok-4 -m opus-4.8           # subset of models
python benchmark.py run --suite sre                     # SRE track only (default)
python benchmark.py run --suite developer               # developer track only
python benchmark.py run --suite all                     # both tracks
python benchmark.py run -c anomaly_detection            # single category
python benchmark.py run -c code_generation              # just the developer category
python benchmark.py run --runs 1                        # quick pass (1/3 of the calls)
python benchmark.py list-models                         # check which keys are set
python benchmark.py list-categories                     # show all categories and suites
```

### Running models one at a time (recommended for local / expensive models)

You can run models sequentially. Each model’s raw results are saved in its own folder:

```bash
python benchmark.py run -m grok-4
python benchmark.py run -m opus-4.8
python benchmark.py run -m llama-3.3-70b --runs 1
```

After running any number of models, (re)build the combined comparison:

```bash
python benchmark.py aggregate
```

This command scans `results/<model>/records.json` for every model and regenerates
`comparison_table.md`, `summary_report.md`, `detailed_results.csv`, and `results.json`.

**Cost:** a full 3-run pass is ~200k input + ~25k output tokens per model on the SRE track —
roughly **$0.40–$4.00 per frontier model** at current list prices. (Multi-modal RCA is about 90k
of that input on its own: its bundles are far larger than the single-modality cases.)

The developer track adds another ~150k input + ~100k output tokens per model (24 cases × 3 runs,
generating complete functions/classes). Budget **$0.50–$5.00 per model** depending on pricing.

Responses are cached in `.cache/`, so interrupted or repeated runs never re-pay for the same call.

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
├── opus-4.8/
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
| `site_data.json` | Published payload for the showcase site (see below) |

Progress streams live in the terminal with per-call scores.

### Publishing to the showcase site

[llm-sre-website](https://github.com/PhyByte/llm-sre-website) reads one artifact from this
repository over HTTPS, so the two checkouts do not need to sit next to each other.

`run` and `aggregate` write `results/site_data.json` along with the other reports, so it never
falls behind `results.json` — a stale export shows a finished model as "partial" on the site with
nothing to explain why. All that is left is publishing it:

```bash
git add results/site_data.json && git commit && git push
python scripts/export_site_data.py   # re-export by hand, e.g. after editing prices
```

`site_data.json` is the published contract between the two repos: aggregate scores, list prices
and the per-category prose, derived from `results.json` and `models.json`. Only public
information goes in it — nothing from `.env` or the response cache. The site pulls it with
`npm run refresh-data` and compiles it into a typed module, so it only sees exports you have
actually pushed.

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
    { "name": "opus-4.8", "provider": "anthropic",
      "api_key": "${ANTHROPIC_API_KEY}", "model_id": "claude-opus-4-8" },
    { "name": "llama-3.3-70b", "provider": "openai",
      "base_url": "http://localhost:1234/v1", "model_id": "meta/llama-3.3-70b" }
  ]
}
```

| Provider | Works with | Notes |
|---|---|---|
| `openai`, `xai`, `google` | Any OpenAI-compatible endpoint | OpenAI, xAI, Gemini (`GEMINI_API_KEY`), Groq, Together, DeepSeek, Mistral, **LM Studio**, **vLLM**, llama.cpp — set `base_url`. Local `http://` servers need no API key. |
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

## The datasets (106 cases total: 82 SRE + 24 developer)

### SRE Track

| File | Cases | Source |
|---|---|---|
| `log_parsing.json` | 15 | Real Loghub 2k logs + official templates ([logpai/logparser](https://github.com/logpai/logparser)) |
| `anomaly_detection.json` | 11 | 6 real labeled BGL windows + 5 hard synthetics (decoys, silent failures, clean case) |
| `metrics_timeseries.json` | 18 | 10 seasonal series (96 pts) plus 8 traps: in-band peak, weekend dip, flatline, counter wrap, slow ramp, growing amplitude, extra clean, held samples |
| `pattern_correlation.json` | 10 | Curated multi-service cascades with distractors, 2-hop chains, common-cause, inverted cause, decoy deploys |
| `root_cause.json` | 10 | Curated incidents with red herrings (including false pages, flag defaults, noisy neighbors, AZ failure, decoy rollback) |
| `multimodal_rca.json` | 18 | Real [Nezha](https://github.com/IntelligentDDS/Nezha) microservice incidents (metrics + logs + traces): 12 signal-screened solvable, 5 unrecoverable (`unknown`), 1 healthy baseline |

### Developer Track

| File | Cases | Languages | Task Families |
|---|---|---|---|
| `code_generation.json` | 24 | Python, TypeScript, Go, Rust | 6 families (slugify, interval merge, rate limiter, config overlay, LRU cache, log parser) × 4 languages |

Regenerate or scale up the SRE generated portions deterministically:

```bash
python scripts/build_datasets.py [--seed N]          # re-downloads Loghub CSVs to datasets/raw/
python scripts/build_multimodal_rca.py [--seed N]    # clones Nezha to datasets/raw/nezha/
```

The Nezha clone is ~343 MB (≈3.2 GB unpacked) and lands in the gitignored `datasets/raw/`;
`multimodal_rca.json` itself is committed, so you only need the clone to rebuild.

`pattern_correlation.json`, `root_cause.json`, and `code_generation.json` are curated by hand —
edit them directly (or point `--data-dir` at your own directory with the same file names).

## Project layout

```
benchmark.py             CLI (typer + rich): run, aggregate, list-models, list-categories
models.json              model/provider configuration
core/                    config, provider clients, prompts, schemas, runner, cache
evaluators/              one scorer per category + efficiency
datasets/data/           bundled test cases (JSON)
scripts/build_datasets.py         deterministic dataset builder (Loghub + synthetic)
scripts/build_multimodal_rca.py   Nezha builder: signal screen + modality bundling
scripts/export_site_data.py       emits results/site_data.json for the showcase site
reports/                 aggregation + report generation
```

## Extending

- **Add a model:** append an entry to `models.json`. Any OpenAI-compatible API works out of
  the box; new native protocols need a small client in `core/clients.py`.
- **Add test cases:** append to the JSON files (shapes documented in `datasets/loaders.py`),
  or grow the generated sets via `scripts/build_datasets.py`.
- **Add a category:** dataset file + prompt template (`core/prompts.py`) + answer schema
  (`core/schemas.py`) + evaluator (`evaluators/`) + weight (`core/config.py`). See the
  `code_generation` category for a complete example of execution-based evaluation.
- **Add a language to the developer track:** add cases to `code_generation.json` and implement
  an executor in `evaluators/code_generation.py`.

## Toolchain Requirements (Developer Track)

The developer track requires language toolchains to compile and execute generated code:

- **Python 3.11+**: Already required for the benchmark itself
- **Node.js + tsx**: For TypeScript execution
  ```bash
  npm install -g tsx
  ```
- **Go 1.20+**: From [golang.org](https://golang.org/dl/)
- **Rust 1.70+**: From [rust-lang.org](https://www.rust-lang.org/tools/install)
  ```bash
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
  ```

**Detecting missing toolchains:** The evaluator checks for each compiler at runtime. If a
language's toolchain is unavailable, its cases are skipped (recorded with an error) rather
than failing the entire run. You can run the developer track with only Python and get partial
results — the other 3 languages will show "toolchain_unavailable" in their metrics.

**Offline mock mode:** The mock provider (`models.mock.json`) generates synthetic code without
executing it, so no compilers are needed for smoke testing the pipeline.

## Acknowledgements

Log data from [Loghub](https://github.com/logpai/loghub) / [logparser](https://github.com/logpai/logparser)
(LogPAI team) — please cite their work if you publish results based on these datasets.

Multi-modal RCA cases are derived from [Nezha](https://github.com/IntelligentDDS/Nezha)
(IntelligentDDS, FSE 2023) — *Nezha: Interpretable Fine-Grained Root Causes Analysis for
Microservices on Multi-Modal Observability Data*. Please cite their paper if you publish results
based on this category.
