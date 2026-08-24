# LLM Observability Benchmark — Summary Report

Generated: 2026-08-24 20:13:56 UTC

## Overall Ranking

1. **opus-4.8** — global score 73.3/100 (0/246 failed runs) — completed in 17m 38s
2. **grok-4.6-low** — global score 72.6/100 (0/246 failed runs) — completed in 32m 31s
3. **gpt-5.6-terra** — global score 70.6/100 (0/246 failed runs) — completed in 16m 5s
4. **grok-4.5-low** — global score 70.4/100 (0/246 failed runs) — completed in 42m 18s
5. **grok-4.5** — global score 70.0/100 (0/246 failed runs) — completed in 108m 25s
6. **grok-4.6** — global score 69.2/100 (0/246 failed runs) — completed in 248m 2s
7. **sonnet-5** — global score 68.3/100 (0/246 failed runs) — completed in 31m 19s
8. **grok-4** — global score 67.9/100 (0/246 failed runs) — completed in 33m 10s
9. **gpt-5.6-sol** — global score 67.3/100 (0/246 failed runs) — completed in 26m 46s
10. **gpt-5.6-luna** — global score 67.2/100 (0/246 failed runs) — completed in 20m 9s
11. **qwen3.8-27b** — global score 66.9/100 (0/246 failed runs) — completed in 91m 1s
12. **fable-5-low** — global score 66.6/100 (0/246 failed runs, 22 declined) — completed in 24m 16s
13. **gemini-3.1-pro** — global score 66.4/100 (0/246 failed runs) — completed in 68m 59s
14. **gemma-4-26B-a4b** — global score 66.2/100 (1/246 failed runs) — completed in 65m 37s
15. **gemini-3.6-flash** — global score 66.0/100 (0/246 failed runs) — completed in 67m 52s
16. **qwen3.6-27b** — global score 64.2/100 (0/246 failed runs) — completed in 175m 1s
17. **fable-5** — global score 64.1/100 (0/246 failed runs, 25 declined) — completed in 41m 9s
18. **gemma-4-31b** — global score 64.1/100 (0/246 failed runs) — completed in 150m 3s
19. **haiku-4-5** — global score 63.8/100 (0/246 failed runs) — completed in 10m 34s
20. **gpt-4o** — global score 61.0/100 (0/246 failed runs) — completed in 15m 21s
21. **qwen3-coder-30b** — global score 55.8/100 (0/246 failed runs) — completed in 7m 38s
22. **qwen3-32b** — global score 52.1/100 (0/246 failed runs) — completed in 70m 36s
23. **gemma-3-12B** — global score 50.6/100 (0/246 failed runs) — completed in 237m 39s

## Category Leaders

- **Log Parsing**: fable-5 with 92.1 (next: gpt-5.6-terra at 91.9)
- **Anomaly Detection**: gemma-4-26B-a4b with 70.9 (next: qwen3.8-27b at 69.3)
- **Pattern & Correlation**: gpt-5.6-terra with 86.0 (next: opus-4.8 at 86.0)
- **Metrics Time-Series**: opus-4.8 with 81.8 (next: grok-4.6 at 79.6)
- **Root Cause & Summary**: grok-4.5-low with 56.2 (next: grok-4.6 at 55.9)
- **Multi-modal RCA**: grok-4.6-low with 68.8 (next: grok-4.5 at 68.3)
- **Efficiency & Consistency**: qwen3-coder-30b with 77.8 (next: gpt-4o at 77.3)

## Efficiency Details

- **opus-4.8**: avg latency 4.30s, avg tokens/call 2383, score stddev across runs 1.4 points, full set: 17m 38s
- **grok-4.6-low**: avg latency 7.93s, avg tokens/call 1984, score stddev across runs 2.0 points, full set: 32m 31s
- **gpt-5.6-terra**: avg latency 3.92s, avg tokens/call 1917, score stddev across runs 3.1 points, full set: 16m 5s
- **grok-4.5-low**: avg latency 10.32s, avg tokens/call 2234, score stddev across runs 4.0 points, full set: 42m 18s
- **grok-4.5**: avg latency 26.45s, avg tokens/call 2287, score stddev across runs 2.8 points, full set: 108m 25s
- **grok-4.6**: avg latency 60.50s, avg tokens/call 2050, score stddev across runs 3.0 points, full set: 248m 2s
- **sonnet-5**: avg latency 7.64s, avg tokens/call 2797, score stddev across runs 4.0 points, full set: 31m 19s
- **grok-4**: avg latency 8.09s, avg tokens/call 1903, score stddev across runs 5.5 points, full set: 33m 10s
- **gpt-5.6-sol**: avg latency 6.53s, avg tokens/call 1957, score stddev across runs 2.8 points, full set: 26m 46s
- **gpt-5.6-luna**: avg latency 4.91s, avg tokens/call 2092, score stddev across runs 3.1 points, full set: 20m 9s
- **qwen3.8-27b**: avg latency 22.20s, avg tokens/call 3880, score stddev across runs 0.5 points, full set: 91m 1s
- **fable-5-low**: avg latency 6.50s, avg tokens/call 2487, score stddev across runs 1.9 points, full set: 24m 16s
- **gemini-3.1-pro**: avg latency 16.83s, avg tokens/call 2103, score stddev across runs 0.4 points, full set: 68m 59s
- **gemma-4-26B-a4b**: avg latency 16.07s, avg tokens/call 4429, score stddev across runs 2.4 points, full set: 65m 37s
- **gemini-3.6-flash**: avg latency 16.56s, avg tokens/call 2086, score stddev across runs 2.5 points, full set: 67m 52s
- **qwen3.6-27b**: avg latency 42.69s, avg tokens/call 5066, score stddev across runs 0.0 points, full set: 175m 1s
- **fable-5**: avg latency 11.17s, avg tokens/call 2758, score stddev across runs 1.3 points, full set: 41m 9s
- **gemma-4-31b**: avg latency 36.60s, avg tokens/call 3642, score stddev across runs 1.7 points, full set: 150m 3s
- **haiku-4-5**: avg latency 2.58s, avg tokens/call 1994, score stddev across runs 2.8 points, full set: 10m 34s
- **gpt-4o**: avg latency 3.74s, avg tokens/call 1756, score stddev across runs 1.7 points, full set: 15m 21s
- **qwen3-coder-30b**: avg latency 1.86s, avg tokens/call 2338, score stddev across runs 0.8 points, full set: 7m 38s
- **qwen3-32b**: avg latency 17.22s, avg tokens/call 3015, score stddev across runs 4.0 points, full set: 70m 36s
- **gemma-3-12B**: avg latency 57.97s, avg tokens/call 2162, score stddev across runs 1.1 points, full set: 237m 39s

## Reliability

Coverage gaps — 1/5658 runs failed, 47 declined by the model (scored 0):
  gemma-4-26B-a4b — 1/246 failed
    metrics_timeseries (1): 1 empty response — ts-temp-clean#0
  fable-5 — 0/246 failed; 25 declined
    declined metrics_timeseries (9): 9 cyber refusal — ts-bytes-counter-wrap, ts-cpu-flatline, ts-latency-inband-peak
    declined pattern_correlation (7): 7 cyber refusal — pc-006-vacuum-common-cause, pc-008-decoy-deploy#2, pc-009-thundering-herd
    declined root_cause (9): 9 cyber refusal — rc-006-dashboard-timezone, rc-007-flag-default-on-restart, rc-010-rollback-did-not-help
  fable-5-low — 0/246 failed; 22 declined
    declined metrics_timeseries (6): 6 cyber refusal — ts-bytes-counter-wrap, ts-latency-inband-peak
    declined pattern_correlation (7): 7 cyber refusal — pc-006-vacuum-common-cause#1, pc-008-decoy-deploy#0,1, pc-009-thundering-herd, pc-010-missing-middle-stampede#1
    declined root_cause (9): 9 cyber refusal — rc-006-dashboard-timezone, rc-007-flag-default-on-restart, rc-010-rollback-did-not-help

## Recommendations

- **opus-4.8** is the strongest overall pick for log/metrics analysis workloads in this run (global score 73.3).
- For **log parsing** specifically, consider **fable-5** (92.1 vs 91.9).
- For **anomaly detection** specifically, consider **gemma-4-26B-a4b** (70.9 vs 68.8).
- For **pattern & correlation** specifically, consider **gpt-5.6-terra** (86.0 vs 86.0).
- For **root cause & summary** specifically, consider **grok-4.5-low** (56.2 vs 55.2).
- For **multi-modal rca** specifically, consider **grok-4.6-low** (68.8 vs 60.6).
- For **efficiency & consistency** specifically, consider **qwen3-coder-30b** (77.8 vs 71.8).
