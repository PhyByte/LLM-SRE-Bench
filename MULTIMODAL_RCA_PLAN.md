# Multi-modal RCA category — research findings & implementation plan

Working document. Everything under "Verified" was measured against the real
data, not inferred from a paper. Read this first in a fresh session.

**Status: research complete, data source decided, no project code written yet.**

---

## 0. Headline

The original plan was built on **AnoMod**. Direct measurement shows AnoMod's
data does not contain recoverable fault signal, so it has been **dropped**.
The category will be built on **Nezha** (FSE'23) instead, where 40 of 101
labelled faults pass a signal gate and — importantly — different fault types
are recoverable from *different* modalities, which is what makes a multi-modal
scoring design honest.

---

## 1. Why AnoMod was rejected (verified, negative result)

AnoMod ([GitHub](https://github.com/EvoTestOps/AnoMod), MSR 2026 Data Showcase)
looked ideal: logs + metrics + traces + API responses on SocialNetwork and
TrainTicket, with 4 anomaly levels. Access works fine — files are Git LFS
pointers, and `media.githubusercontent.com/media/...` serves real content and
honours HTTP Range (verified, returns `206`). Ground truth is excellent and
machine-readable: every TrainTicket chaos YAML carries `anomaly_level`,
`anomaly_type` and `target_service` labels, and the code-level faults are
recoverable from the `blade create k8s container-jvm` commands in
`run_experiment.sh`.

The data itself is the problem.

### Ground truth recovered (all 13 TrainTicket scenarios)

| Scenario | Level | Type | Target |
|---|---|---|---|
| `Lv_P_CPU_preserve` | performance | cpu_contention (2 workers, 80% load) | ts-preserve-service |
| `Lv_P_DISKIO_preserve` | performance | disk_io_stress (stress-ng iomix 1G) | ts-preserve-service |
| `Lv_P_NETLOSS_preserve` | performance | network_loss (90%) | ts-preserve-service |
| `Lv_S_KILLPOD_preserve` | service | pod-kill every 3s | ts-preserve-service |
| `Lv_S_HTTPABORT_preserve` | service | 70% of POSTs → 503 | ts-preserve-service |
| `Lv_S_DNSFAIL_preserve_no_order` | service | DNS error resolving ts-order-service | ts-preserve-service |
| `Lv_D_cachelimit` | database | memory stressor 85% | tsdb-mysql |
| `Lv_D_CONNECTION_POOL_exhaustion` | database | 8s network delay | tsdb-mysql |
| `Lv_D_TRANSACTION_timeout` | database | 15s network delay | tsdb-mysql |
| `Lv_C_security_check` | code | JVM return injection, `SecurityServiceImpl.check` | ts-security-service |
| `Lv_C_exception_injection` | code | JVM throw, `OrderServiceImpl.create` | ts-order-service |
| `Lv_C_travel_detail_failure` | code | JVM return injection, `TravelServiceImpl.getTripAllDetailInfo` | ts-travel-service |
| `Normal_case_em` | — | none | — |

### Verified: the signal is not there

Traces are correctly scoped (each file covers its own 3–25 min window; 0% shared
trace IDs between scenarios — an early "24h overlap" hypothesis was checked and
disproved). Despite that:

- **Trace latency cannot localize any scenario.** `ts-preserve-service` — the
  target of 6 of 12 scenarios — carries only **19–20 spans per window**, with
  median 4 ms and an occasional >1 s tail. Its p95 is therefore "was there one
  slow span", which is noise. A first-pass screen that ignored sample size
  produced a *false* KEEP for all 12 scenarios, with near-identical ×127–155
  ratios across totally unrelated fault types — the tell that it was measuring
  an artifact.
- **The DB faults left no trace at all.** A **15-second** injected MySQL delay
  produced **zero spans ≥10 s**; max span duration was 5 987 ms versus 6 356 ms
  in the baseline — *lower* than normal. Duration histograms are essentially
  identical to the fault-free run.
- **Metrics do not carry it either.** Under a 2-worker/80% CPU stressor,
  `ts-preserve-service` container CPU averaged **0.039 cores versus 0.092 in the
  baseline** — lower — with the same sawtooth in both (cadvisor sampling
  aliasing, not the fault). On peak CPU the injection target ranks *below*
  unrelated services.
- **Code-level faults are invisible.** For `Lv_C_exception_injection` the
  culprit ranks 16th by latency change (×1.2) while unrelated services move
  ×13.5. The target pod's log tail contains only unrelated `TokenException:
  Token expired` JWT noise.

**Root cause of the dataset's weakness:** the workload is EvoMaster, a fuzzer.
Most generated requests are invalid and get rejected at validation/auth before
reaching the DB or the deep business logic the faults were injected into — many
services sit at ~100% error rate even in `Normal_case_em`. The faults were
injected, but the traffic never exercised them. This is the same failure mode
the earlier session found in AnoMod's SocialNetwork half, where the API-response
modality is identical across all scenarios including the baseline, and 6 of 13
scenarios show no service outage at all.

Useful engineering that came out of it and is worth keeping: the 122 MB metric
CSVs are *grouped* (not sorted) by `metric_name`, so a coarse probe scan of ~200
small Range reads maps group boundaries and lets you pull one metric in ~10 MB
instead of 122 MB. Not needed for Nezha, but noted.

---

## 2. Nezha — the chosen source (verified)

| | |
|---|---|
| Paper | Nezha, FSE 2023 — *Interpretable Fine-Grained Root Causes Analysis for Microservices on Multi-Modal Observability Data* |
| Repo | https://github.com/IntelligentDDS/Nezha (Apache-2.0) |
| Size | 343 MB packed / 3.2 GB unpacked — plain git clone, no LFS |
| Systems | OnlineBoutique (10 services) · TrainTicket (~40 services) |
| Faults | **101 labelled injections** across 4 days |
| Fault types | `cpu_contention`, `cpu_consumed`, `network_delay`, `return`, `exception` |

Decisive advantage over AnoMod: the paper's own method reaches **92.9% top-1**
localization on OnlineBoutique, so the signal is known to be recoverable — and
our independent screen confirms it.

### Layout

```
rca_data/<date>/<date>-fault_list.json     # ground truth
rca_data/<date>/metric/<pod>_metric.csv    # per-pod, 1 sample/min
rca_data/<date>/log/HH_MM_log.csv          # per-minute, all pods
rca_data/<date>/trace/HH_MM_trace.csv      # per-minute, all pods
construct_data/<date>/...                  # fault-free baseline phase
construct_data/root_cause_{hipster,ts}.json # service → fault type → signal
```

Ground truth per fault: `inject_time`, `inject_timestamp`, `inject_pod`,
`inject_type`. Data files exist for exactly the 3 minutes around each injection.

### Schemas (verified by inspection)

- **metric** — `Time, TimeStamp, PodName, CpuUsage(m), CpuUsageRate(%),
  MemoryUsage(Mi), MemoryUsageRate(%), SyscallRead/Write,
  NetworkReceive/TransmitBytes, PodClient/ServerLatencyP90/95/99(s),
  PodWorkload(Ops), PodSuccessRate(%), Node*` — exactly the panel an SRE reads.
- **log** — `Timestamp, TimeUnixNano, Node, PodName, Container, TraceID, SpanID,
  Log`. Logs carry `TraceID`, so logs and traces genuinely correlate.
- **trace** — `TraceID, SpanID, ParentID, PodName, OperationName,
  StartTimeUnixNano, EndTimeUnixNano, Duration`. Clean span tree.

### ⚠ Data-quality bug to handle in the builder

`adservice-*_metric.csv` on 2022-08-22 has a corrupted `TimeStamp` column —
values start `186…` instead of `166…`, placing them in **2028**. All 9 other
pods are correct. The human-readable `Time` column is authoritative; the builder
must parse `Time`, not `TimeStamp`.

### Verified: the signal gate

Each fault was scored independently through a metric channel (per-pod
`CpuUsageRate(%)` over the window) and a log channel (per-pod error-log rate).
A fault is a candidate only if at least one channel ranks the injected pod #1.

| System | Fault type | Usable | Informative modality |
|---|---|---|---|
| OnlineBoutique | cpu_contention | 11 | metrics |
| OnlineBoutique | cpu_consumed | 6 | metrics (2 also logs) |
| OnlineBoutique | return | 4 | **logs** |
| OnlineBoutique | exception | 4 | **logs** |
| OnlineBoutique | network_delay | 3 | metrics |
| TrainTicket | cpu_contention | 7 | metrics |
| TrainTicket | return | 5 | **logs** |
| | **TOTAL** | **40 / 101** | |

This is the property the whole category depends on: **CPU faults are recoverable
from metrics and invisible in logs; `return`/`exception` faults are recoverable
from logs and invisible in metrics.** A model cannot win by always citing one
modality. A few faults (e.g. `frontend/cpu_contention` on 08-23,
`shippingservice/cpu_contention`) are top-1 in *both* channels — those make good
corroboration cases.

The 61 rejected faults are correctly rejected: `network_delay` is essentially
unlocalizable from pod metrics (mean rank ~13), and most TrainTicket
`exception` faults log nothing at the culprit.

---

## 3. Design

### Naming
`multimodal_rca` (category key) / "Multi-modal RCA" (display label). The
existing `root_cause` stays as the logs-only variant.

### New files

```
datasets/data/multimodal_rca.json     built cases (committed)
scripts/build_multimodal_rca.py       clone/screen/downsample/emit
core/schemas.py                       + MultiModalRCAResult
core/prompts.py                       + _multimodal_rca builder
evaluators/multimodal_rca.py          new scorer
core/config.py                        + weight, category registered
reports/generator.py                  + label + description
core/clients.py                       + MockClient branch (keeps the offline smoke test working)
```

### Case shape

```jsonc
{
  "id": "mm-ob-cpu-frontend",
  "source": "Nezha OnlineBoutique 2022-08-22 03:53:54 (cpu_contention on frontend)",
  "system": "onlineboutique",
  "services": ["frontend", "cartservice", ...],   // closed candidate set
  "incident_window": "03:52–03:57 UTC",
  "modalities": {
    "metrics": {...},   // per-service CPU/mem/latency/workload/success-rate
    "logs":    [...],   // sampled, error-biased but with normal noise retained
    "traces":  [...]    // per-service span counts, p50/p95, error counts
  },
  "ground_truth": {
    "culprit_service": "frontend",
    "fault_type": "cpu_contention",
    "informative_modalities": ["metrics"],   // measured by the screen
    "decoy_modalities": ["logs", "traces"],  // measured NOT to localize
    "evidence_keywords": ["CpuUsageRate", "72%", "frontend"]
  }
}
```

`informative_modalities` / `decoy_modalities` come from the builder's screening
pass, never hand-asserted — that is what makes modality scoring defensible.

### Answer schema

```python
class Evidence(BaseModel):
    modality: Literal["metrics", "logs", "traces"]
    observation: str

class MultiModalRCAResult(BaseModel):
    culprit_service: str
    fault_type: str          # closed vocabulary, shown in the prompt
    evidence: list[Evidence]
    summary: str
```

Fault-type vocabulary given to the model: `cpu_contention`, `cpu_consumed`,
`network_delay`, `code_return_value`, `code_exception`, `none`.

### Scoring (0–1, consistent with the existing evaluators)

```
0.40  culprit localization  exact match on the service (normalized), else 0
0.25  fault-type accuracy   exact match against the closed vocabulary
0.25  modality grounding    F1 of cited modalities vs informative_modalities.
                            Rewards citing what carries signal and penalizes
                            decoys, so "cite everything" does not win.
0.10  evidence quality      keyword recall of ground-truth evidence markers
```

Plus a **no-fault case** drawn from the fault-free `construct_data` phase, where
the correct answer is `culprit_service: "none"` — mirroring the suite's existing
anti-over-flagging cases (`ad-syn-clean`, `ts-*-clean`).

### Proposed case mix (~11 cases)

| Kind | n | Informative modality |
|---|---|---|
| CPU faults (contention/consumed), OnlineBoutique | 4 | metrics |
| `return` / `exception`, OnlineBoutique | 3 | logs |
| CPU + `return`, TrainTicket | 2 | metrics / logs |
| Corroboration (both channels agree) | 1 | metrics + logs |
| Fault-free baseline | 1 | — (answer is "none") |

### Weights — as approved earlier

| Category | Now | New |
|---|---|---|
| log_parsing | 20% | 15% |
| anomaly_detection | 30% | 25% |
| pattern_correlation | 20% | 15% |
| metrics_timeseries | 15% | 10% |
| root_cause | 10% | 10% |
| **multimodal_rca** | — | **20%** |
| efficiency | 5% | 5% |

### ⚠ Two integration consequences

1. **All published global scores shift.** `reports/generator.py::aggregate`
   recomputes from `CATEGORY_WEIGHTS`, so `benchmark.py aggregate` restates
   every stored model's global score under the new weights.
2. **Every existing model becomes "Incomplete coverage"** and drops out of the
   ranking until re-run, because `classify_summaries` defines `expected` as the
   union of categories any model has data for. Each of the 16 models needs
   `python benchmark.py run -m <model> -c multimodal_rca` — cheap, since the
   cache covers everything else.

### Cost

Multi-modal bundles are much larger than the current ~20-line log cases. Target
**2.5–3.5k tokens/case**; ~11 cases × 3 runs ≈ 85–115k input tokens per model,
roughly doubling the current per-model benchmark cost. Bundles must stay tight:
metrics downsampled to per-service summaries, logs sampled (stack-trace frames
collapsed), traces reduced to per-service aggregates.

---

## 4. Build order

1. `scripts/build_multimodal_rca.py` — clone Nezha into `datasets/raw/nezha/`
   (already covered by `.gitignore`), run the signal gate, downsample, emit
   `datasets/data/multimodal_rca.json`. Deterministic and seeded, following
   `scripts/build_datasets.py` conventions.
2. Schema → prompt → evaluator → config weight → generator labels → mock client.
3. Verify `python benchmark.py run --config models.mock.json -c multimodal_rca`
   passes end-to-end offline, and that the mock heuristic scores meaningfully
   below a frontier model.
4. README section + `list-categories` check.

## 5. Constraint check

Nothing above changes existing evaluators, schemas, prompts, or dataset files.
Caching, retries and the circuit breaker are untouched — the new category flows
through the same `RESULT_SCHEMAS` / `get_evaluator` dispatch as every other one.
