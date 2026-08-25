# LLM Observability Benchmark — Summary Report

Generated: 2026-08-25 16:42:01 UTC

## Overall Ranking

1. **qwen3-coder-30b** — global score 92.0/100 (0/72 failed runs) — completed in 1m 10s
2. **gpt-4o** — global score 89.6/100 (0/72 failed runs) — completed in 3m 38s
3. **gemma-3-12B** — global score 88.0/100 (0/72 failed runs) — completed in 3m 10s
4. **fable-5-low** — global score 81.4/100 (0/72 failed runs, 5 declined) — completed in 6m 48s
5. **opus-4.8** — global score 80.6/100 (0/72 failed runs) — completed in 6m 22s
6. **gpt-5.6-terra** — global score 79.0/100 (0/72 failed runs) — completed in 5m 56s
7. **grok-4.5-low** — global score 76.5/100 (0/72 failed runs) — completed in 7m 54s
8. **grok-4** — global score 72.4/100 (0/72 failed runs) — completed in 11m 20s
9. **sonnet-5** — global score 71.1/100 (0/72 failed runs) — completed in 9m 11s
10. **gemini-3.6-flash** — global score 68.5/100 (0/72 failed runs) — completed in 14m 51s
11. **grok-4.6-low** — global score 67.6/100 (0/72 failed runs) — completed in 10m 3s
12. **gpt-5.6-luna** — global score 66.2/100 (0/72 failed runs) — completed in 10m 21s
13. **haiku-4-5** — global score 65.2/100 (0/72 failed runs) — completed in 5m 22s
14. **fable-5** — global score 62.0/100 (0/72 failed runs) — completed in 13m 21s
15. **gpt-5.6-sol** — global score 60.4/100 (0/72 failed runs) — completed in 13m 51s
16. **grok-4.5** — global score 53.8/100 (0/72 failed runs) — completed in 22m 52s
17. **grok-4.6** — global score 48.9/100 (0/72 failed runs) — completed in 46m 56s
18. **gemma-4-31b** — global score 41.7/100 (0/72 failed runs) — completed in 41m 4s
19. **gemma-4-26B-a4b** — global score 30.2/100 (0/72 failed runs) — completed in 20m 46s
20. **qwen3.6-27b** — global score 30.0/100 (0/72 failed runs) — completed in 94m 51s
21. **qwen3.8-27b** — global score 25.0/100 (0/72 failed runs) — completed in 104m 0s
22. **qwen3-32b** — global score 21.6/100 (0/72 failed runs) — completed in 96m 22s

## Category Leaders

- **Efficiency & Consistency**: qwen3-coder-30b with 92.0 (next: gpt-4o at 89.6)

## Efficiency Details

- **qwen3-coder-30b**: avg latency 0.97s, avg tokens/call 551, score stddev across runs 1.6 points, full set: 1m 10s
- **gpt-4o**: avg latency 3.03s, avg tokens/call 522, score stddev across runs 0.3 points, full set: 3m 38s
- **gemma-3-12B**: avg latency 2.64s, avg tokens/call 642, score stddev across runs 1.6 points, full set: 3m 10s
- **fable-5-low**: avg latency 6.10s, avg tokens/call 844, score stddev across runs 0.0 points, full set: 6m 48s
- **opus-4.8**: avg latency 5.31s, avg tokens/call 899, score stddev across runs 1.7 points, full set: 6m 22s
- **gpt-5.6-terra**: avg latency 4.95s, avg tokens/call 731, score stddev across runs 4.6 points, full set: 5m 56s
- **grok-4.5-low**: avg latency 6.59s, avg tokens/call 1086, score stddev across runs 1.8 points, full set: 7m 54s
- **grok-4**: avg latency 9.45s, avg tokens/call 666, score stddev across runs 3.1 points, full set: 11m 20s
- **sonnet-5**: avg latency 7.66s, avg tokens/call 1326, score stddev across runs 3.1 points, full set: 9m 11s
- **gemini-3.6-flash**: avg latency 12.38s, avg tokens/call 634, score stddev across runs 1.6 points, full set: 14m 51s
- **grok-4.6-low**: avg latency 8.38s, avg tokens/call 1207, score stddev across runs 5.5 points, full set: 10m 3s
- **gpt-5.6-luna**: avg latency 8.63s, avg tokens/call 1127, score stddev across runs 6.8 points, full set: 10m 21s
- **haiku-4-5**: avg latency 4.48s, avg tokens/call 924, score stddev across runs 15.8 points, full set: 5m 22s
- **fable-5**: avg latency 11.13s, avg tokens/call 1413, score stddev across runs 4.3 points, full set: 13m 21s
- **gpt-5.6-sol**: avg latency 11.55s, avg tokens/call 970, score stddev across runs 7.7 points, full set: 13m 51s
- **grok-4.5**: avg latency 19.06s, avg tokens/call 1066, score stddev across runs 0.1 points, full set: 22m 52s
- **grok-4.6**: avg latency 39.11s, avg tokens/call 1207, score stddev across runs 1.7 points, full set: 46m 56s
- **gemma-4-31b**: avg latency 34.23s, avg tokens/call 2429, score stddev across runs 0.0 points, full set: 41m 4s
- **gemma-4-26B-a4b**: avg latency 17.32s, avg tokens/call 3896, score stddev across runs 5.0 points, full set: 20m 46s
- **qwen3.6-27b**: avg latency 79.05s, avg tokens/call 5562, score stddev across runs 0.0 points, full set: 94m 51s
- **qwen3.8-27b**: avg latency 86.67s, avg tokens/call 7456, score stddev across runs 4.2 points, full set: 104m 0s
- **qwen3-32b**: avg latency 80.31s, avg tokens/call 5386, score stddev across runs 7.0 points, full set: 96m 22s

## Reliability

Coverage gaps — 52/2866 runs failed, 5 declined by the model (scored 0):
  mock-heuristic — 26/26 failed; never ran code_generation (24 cases), metrics_timeseries (18 cases), multimodal_rca (18 cases), pattern_correlation (10 cases), root_cause (10 cases)
    anomaly_detection (11): all 11 cases skipped
    log_parsing (15): 5 SyntaxError, 10 skipped — lp-bgl-01, lp-bgl-02, lp-bgl-03, lp-hdfs-01, lp-hdfs-02, lp-hdfs-03, lp-linux-01, lp-linux-02 +7 more
  mock-naive — 26/26 failed; never ran code_generation (24 cases), metrics_timeseries (18 cases), multimodal_rca (18 cases), pattern_correlation (10 cases), root_cause (10 cases)
    anomaly_detection (11): all 11 cases skipped
    log_parsing (15): 5 SyntaxError, 10 skipped — lp-bgl-01, lp-bgl-02, lp-bgl-03, lp-hdfs-01, lp-hdfs-02, lp-hdfs-03, lp-linux-01, lp-linux-02 +7 more
  fable-5-low — 0/72 failed; 5 declined; never ran anomaly_detection (11 cases), log_parsing (15 cases), metrics_timeseries (18 cases), multimodal_rca (18 cases), pattern_correlation (10 cases), root_cause (10 cases)
    declined code_generation (5): 5 cyber refusal — log_parser_go, log_parser_rust#1,2
  fable-5 — 0/72 failed; never ran anomaly_detection (11 cases), log_parsing (15 cases), metrics_timeseries (18 cases), multimodal_rca (18 cases), pattern_correlation (10 cases), root_cause (10 cases)
  gemini-3.6-flash — 0/72 failed; never ran anomaly_detection (11 cases), log_parsing (15 cases), metrics_timeseries (18 cases), multimodal_rca (18 cases), pattern_correlation (10 cases), root_cause (10 cases)
  gemma-3-12B — 0/72 failed; never ran anomaly_detection (11 cases), log_parsing (15 cases), metrics_timeseries (18 cases), multimodal_rca (18 cases), pattern_correlation (10 cases), root_cause (10 cases)
  gemma-4-26B-a4b — 0/72 failed; never ran anomaly_detection (11 cases), log_parsing (15 cases), metrics_timeseries (18 cases), multimodal_rca (18 cases), pattern_correlation (10 cases), root_cause (10 cases)
  gpt-4o — 0/72 failed; never ran anomaly_detection (11 cases), log_parsing (15 cases), metrics_timeseries (18 cases), multimodal_rca (18 cases), pattern_correlation (10 cases), root_cause (10 cases)
  gpt-5.6-luna — 0/72 failed; never ran anomaly_detection (11 cases), log_parsing (15 cases), metrics_timeseries (18 cases), multimodal_rca (18 cases), pattern_correlation (10 cases), root_cause (10 cases)
  gpt-5.6-sol — 0/72 failed; never ran anomaly_detection (11 cases), log_parsing (15 cases), metrics_timeseries (18 cases), multimodal_rca (18 cases), pattern_correlation (10 cases), root_cause (10 cases)
  gpt-5.6-terra — 0/72 failed; never ran anomaly_detection (11 cases), log_parsing (15 cases), metrics_timeseries (18 cases), multimodal_rca (18 cases), pattern_correlation (10 cases), root_cause (10 cases)
  grok-4 — 0/72 failed; never ran anomaly_detection (11 cases), log_parsing (15 cases), metrics_timeseries (18 cases), multimodal_rca (18 cases), pattern_correlation (10 cases), root_cause (10 cases)
  grok-4.5 — 0/72 failed; never ran anomaly_detection (11 cases), log_parsing (15 cases), metrics_timeseries (18 cases), multimodal_rca (18 cases), pattern_correlation (10 cases), root_cause (10 cases)
  grok-4.5-low — 0/72 failed; never ran anomaly_detection (11 cases), log_parsing (15 cases), metrics_timeseries (18 cases), multimodal_rca (18 cases), pattern_correlation (10 cases), root_cause (10 cases)
  grok-4.6 — 0/72 failed; never ran anomaly_detection (11 cases), log_parsing (15 cases), metrics_timeseries (18 cases), multimodal_rca (18 cases), pattern_correlation (10 cases), root_cause (10 cases)
  grok-4.6-low — 0/72 failed; never ran anomaly_detection (11 cases), log_parsing (15 cases), metrics_timeseries (18 cases), multimodal_rca (18 cases), pattern_correlation (10 cases), root_cause (10 cases)
  haiku-4-5 — 0/72 failed; never ran anomaly_detection (11 cases), log_parsing (15 cases), metrics_timeseries (18 cases), multimodal_rca (18 cases), pattern_correlation (10 cases), root_cause (10 cases)
  opus-4.8 — 0/72 failed; never ran anomaly_detection (11 cases), log_parsing (15 cases), metrics_timeseries (18 cases), multimodal_rca (18 cases), pattern_correlation (10 cases), root_cause (10 cases)
  qwen3-coder-30b — 0/72 failed; never ran anomaly_detection (11 cases), log_parsing (15 cases), metrics_timeseries (18 cases), multimodal_rca (18 cases), pattern_correlation (10 cases), root_cause (10 cases)
  sonnet-5 — 0/72 failed; never ran anomaly_detection (11 cases), log_parsing (15 cases), metrics_timeseries (18 cases), multimodal_rca (18 cases), pattern_correlation (10 cases), root_cause (10 cases)
  gemini-3.1-pro — 0/246 failed; never ran code_generation (24 cases)

## Recommendations

- **qwen3-coder-30b** is the strongest overall pick for log/metrics analysis workloads in this run (global score 92.0).
- **haiku-4-5** shows high run-to-run variance (stddev 15.8 points); pin temperature to 0 or increase runs_per_test before trusting its scores.
