# LLM Observability Benchmark — Comparison

Generated: 2026-07-13 21:25:50 UTC  
Runs per test: 3 · Models: 13 · Test cases: 46

All scores are 0-100. The global score is the weighted average of the category scores. Only models that ran the full category set are ranked.

| Rank | Model | Global Score | Log Parsing (20%) | Anomaly Detection (30%) | Pattern & Correlation (20%) | Metrics Time-Series (15%) | Root Cause & Summary (10%) | Efficiency & Consistency (5%) | Duration |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **claude-opus-4-8** 🥇 | **82.2** | 91.9 | 68.8 | 90.7 | 100.0 | 57.8 | 86.1 | 7m 9s |
| 2 | **gpt-5.6-terra** 🥈 | **76.2** | 91.9 | 62.1 | 82.7 | 86.3 | 54.2 | 84.9 | 3.3s |
| 3 | **gpt-5.6-luna** 🥉 | **75.6** | 91.3 | 63.1 | 85.3 | 79.6 | 51.9 | 83.9 | 0.8s |
| 4 | **gpt-5.6-sol** | **73.5** | 91.7 | 61.1 | 74.7 | 83.3 | 54.3 | 79.4 | 7.1s |
| 5 | **grok-4** | **72.0** | 89.5 | 62.8 | 73.3 | 80.0 | 51.8 | 69.0 | 24m 59s |
| 6 | **gemma-4-31b** | **68.5** | 90.3 | 61.4 | 58.7 | 86.7 | 50.8 | 44.1 | 0.8s |
| 7 | **gpt-4o** | **65.6** | 90.6 | 62.4 | 60.0 | 53.3 | 42.3 | 91.4 | 3m 41s |
| 8 | **gemma** | **58.5** | 74.8 | 51.8 | 81.3 | 24.3 | 40.5 | 80.1 | 14m 13s |

**Incomplete coverage** (ran only some categories — not ranked, because a partial run's global score isn't comparable). Re-run the full suite for these:

- gemma-3-12b — ran only: log_parsing
- mock-heuristic — ran only: metrics_timeseries
- mock-naive — ran only: metrics_timeseries

**Did not complete** (every call failed — bad key, no model access, or unreachable endpoint):

- grok-4.5 (138 calls failed)
- llama-3.3-70b (138 calls failed)
