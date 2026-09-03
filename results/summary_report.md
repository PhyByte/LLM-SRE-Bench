# LLM Observability Benchmark — Summary Report

Generated: 2026-09-03 22:57:45 UTC

## Overall Ranking

1. **fable-5.1-low** — global score 73.8/100 (0/246 failed runs) — completed in 30m 1s
2. **opus-4.8** — global score 73.3/100 (0/246 failed runs) — completed in 17m 38s
3. **grok-4.6-low** — global score 72.6/100 (0/246 failed runs) — completed in 32m 31s
4. **fable-5.1** — global score 72.5/100 (0/246 failed runs) — completed in 42m 52s
5. **gpt-5.6-terra** — global score 70.6/100 (0/246 failed runs) — completed in 16m 5s
6. **grok-4.5-low** — global score 70.4/100 (0/246 failed runs) — completed in 42m 18s
7. **grok-4.5** — global score 70.0/100 (0/246 failed runs) — completed in 108m 25s
8. **grok-4.6** — global score 69.2/100 (0/246 failed runs) — completed in 248m 2s
9. **sonnet-5** — global score 68.3/100 (0/246 failed runs) — completed in 31m 19s
10. **grok-4** — global score 67.9/100 (0/246 failed runs) — completed in 33m 10s
11. **gpt-5.6-sol** — global score 67.3/100 (0/246 failed runs) — completed in 26m 46s
12. **gpt-5.6-luna** — global score 67.2/100 (0/246 failed runs) — completed in 20m 9s
13. **qwen3.8-27b** — global score 66.9/100 (0/246 failed runs) — completed in 91m 1s
14. **gemma-4-26B-a4b** — global score 66.2/100 (1/246 failed runs) — completed in 65m 25s
15. **gemini-3.6-flash** — global score 66.0/100 (2/246 failed runs) — completed in 66m 50s
16. **fable-5-low** — global score 65.3/100 (0/246 failed runs, 25 declined) — completed in 23m 50s
17. **qwen3.6-27b** — global score 64.2/100 (0/246 failed runs) — completed in 175m 1s
18. **gemma-4-31b** — global score 64.1/100 (0/246 failed runs) — completed in 150m 3s
19. **haiku-4-5** — global score 63.8/100 (0/246 failed runs) — completed in 10m 34s
20. **fable-5** — global score 63.6/100 (0/246 failed runs, 26 declined) — completed in 40m 58s
21. **gpt-4o** — global score 61.0/100 (0/246 failed runs) — completed in 15m 21s
22. **qwen3-coder-30b** — global score 55.8/100 (0/246 failed runs) — completed in 7m 38s
23. **qwen3-32b** — global score 52.1/100 (0/246 failed runs) — completed in 70m 36s
24. **gemma-3-12B** — global score 50.6/100 (0/246 failed runs) — completed in 237m 39s

## Category Leaders

- **Log Parsing**: fable-5 with 92.1 (next: gpt-5.6-terra at 91.9)
- **Anomaly Detection**: gemma-4-26B-a4b with 70.9 (next: qwen3.8-27b at 69.3)
- **Pattern & Correlation**: fable-5.1-low with 92.0 (next: fable-5.1 at 90.7)
- **Metrics Time-Series**: opus-4.8 with 81.8 (next: fable-5.1-low at 80.6)
- **Root Cause & Summary**: grok-4.5-low with 56.2 (next: grok-4.6 at 55.9)
- **Multi-modal RCA**: grok-4.6-low with 68.8 (next: grok-4.5 at 68.3)
- **Efficiency & Consistency**: qwen3-coder-30b with 77.8 (next: gpt-4o at 77.3)

## Efficiency Details

- **fable-5.1-low**: avg latency 7.32s, avg tokens/call 2450, score stddev across runs 1.9 points, full set: 30m 1s
- **opus-4.8**: avg latency 4.30s, avg tokens/call 2383, score stddev across runs 1.4 points, full set: 17m 38s
- **grok-4.6-low**: avg latency 7.93s, avg tokens/call 1984, score stddev across runs 2.0 points, full set: 32m 31s
- **fable-5.1**: avg latency 10.46s, avg tokens/call 2696, score stddev across runs 2.1 points, full set: 42m 52s
- **gpt-5.6-terra**: avg latency 3.92s, avg tokens/call 1917, score stddev across runs 3.1 points, full set: 16m 5s
- **grok-4.5-low**: avg latency 10.32s, avg tokens/call 2234, score stddev across runs 4.0 points, full set: 42m 18s
- **grok-4.5**: avg latency 26.45s, avg tokens/call 2287, score stddev across runs 2.8 points, full set: 108m 25s
- **grok-4.6**: avg latency 60.50s, avg tokens/call 2050, score stddev across runs 3.0 points, full set: 248m 2s
- **sonnet-5**: avg latency 7.64s, avg tokens/call 2797, score stddev across runs 4.0 points, full set: 31m 19s
- **grok-4**: avg latency 8.09s, avg tokens/call 1903, score stddev across runs 5.5 points, full set: 33m 10s
- **gpt-5.6-sol**: avg latency 6.53s, avg tokens/call 1957, score stddev across runs 2.8 points, full set: 26m 46s
- **gpt-5.6-luna**: avg latency 4.91s, avg tokens/call 2092, score stddev across runs 3.1 points, full set: 20m 9s
- **qwen3.8-27b**: avg latency 22.20s, avg tokens/call 3880, score stddev across runs 0.5 points, full set: 91m 1s
- **gemma-4-26B-a4b**: avg latency 16.02s, avg tokens/call 4429, score stddev across runs 2.4 points, full set: 65m 25s
- **gemini-3.6-flash**: avg latency 16.44s, avg tokens/call 2021, score stddev across runs 2.6 points, full set: 66m 50s
- **fable-5-low**: avg latency 6.47s, avg tokens/call 2504, score stddev across runs 1.9 points, full set: 23m 50s
- **qwen3.6-27b**: avg latency 42.69s, avg tokens/call 5066, score stddev across runs 0.0 points, full set: 175m 1s
- **gemma-4-31b**: avg latency 36.60s, avg tokens/call 3642, score stddev across runs 1.7 points, full set: 150m 3s
- **haiku-4-5**: avg latency 2.58s, avg tokens/call 1994, score stddev across runs 2.8 points, full set: 10m 34s
- **fable-5**: avg latency 11.18s, avg tokens/call 2763, score stddev across runs 1.3 points, full set: 40m 58s
- **gpt-4o**: avg latency 3.74s, avg tokens/call 1756, score stddev across runs 1.7 points, full set: 15m 21s
- **qwen3-coder-30b**: avg latency 1.86s, avg tokens/call 2338, score stddev across runs 0.8 points, full set: 7m 38s
- **qwen3-32b**: avg latency 17.22s, avg tokens/call 3015, score stddev across runs 4.0 points, full set: 70m 36s
- **gemma-3-12B**: avg latency 57.97s, avg tokens/call 2162, score stddev across runs 1.1 points, full set: 237m 39s

## Reliability

Coverage gaps — 34/26064 runs failed, 1220 declined by the model (scored 0):
  gemma-4-26B-a4b — 5/1086 failed
    code_generation (1): 1 empty response — tokenize_command_typescript#0
    code_refactoring (3): 3 invalid JSON — compact_ranges_rust
    metrics_timeseries (1): 1 empty response — ts-temp-clean#0
  gemma-3-12B — 4/1086 failed
    code_generation (4): 4 invalid JSON — route_params_go#1,2, semver_compare_go#0,1
  qwen3-32b — 4/1086 failed
    code_debugging (2): 2 invalid JSON — csv_field_python#1,2
    code_generation (2): 2 invalid JSON — evaluate_expression_rust#1,2
  fable-5.1-low — 3/1086 failed; 3 declined
    code_refactoring (3): 3 invalid JSON — format_table_row_rust
    declined code_debugging (3): 3 cyber refusal — normalize_path_python
  gpt-4o — 3/1086 failed
    code_refactoring (3): 3 invalid JSON — format_table_row_rust
  qwen3-coder-30b — 3/1086 failed
    code_debugging (3): 3 invalid JSON — csv_field_rust
  qwen3.6-27b — 3/1086 failed
    code_review (3): 3 invalid JSON — sync_pager_python
  qwen3.8-27b — 3/1086 failed
    code_review (3): 3 ValidationError — fetch_with_retry_rust
  gemini-3.6-flash — 2/1086 failed
    multimodal_rca (2): 2 HTTP 429 — mm-tt-unknown-05#0,1
  gemma-4-31b — 2/1086 failed
    code_refactoring (2): 2 invalid JSON — compact_ranges_rust#1,2
  gpt-5.6-sol — 1/1086 failed
    code_generation (1): 1 empty response — evaluate_expression_rust#2
  grok-4.5 — 1/1086 failed
    code_refactoring (1): 1 invalid JSON — format_table_row_rust#1
  fable-5-low — 0/1086 failed; 610 declined
    declined code_debugging (150): 150 cyber refusal — counter_increase_go, counter_increase_python, counter_increase_rust, counter_increase_typescript, covered_seconds_go, covered_seconds_python, covered_seconds_rust, covered_seconds_typescript +42 more
    declined code_efficiency (83): 83 cyber refusal — distinct_window_total_go, distinct_window_total_python, distinct_window_total_rust, distinct_window_total_typescript, largest_rectangle_python, largest_rectangle_rust, largest_rectangle_typescript, longest_increasing_run_go +22 more
    declined code_generation (46): 46 cyber refusal — evaluate_expression_python#1,2, evaluate_expression_typescript#1,2, histogram_quantile_go, histogram_quantile_python, histogram_quantile_rust, histogram_quantile_typescript, log_parser_go#0,2, log_parser_rust#1,2 +10 more
    declined code_refactoring (150): 150 cyber refusal — bill_summary_go, bill_summary_python, bill_summary_rust, bill_summary_typescript, check_limits_go, check_limits_python, check_limits_rust, check_limits_typescript +42 more
    declined code_review (156): all 52 cases cyber refusal
    declined metrics_timeseries (6): 6 unspecified refusal — ts-bytes-counter-wrap, ts-latency-inband-peak
    declined pattern_correlation (10): 8 unspecified refusal, 2 cyber refusal — pc-006-vacuum-common-cause, pc-008-decoy-deploy, pc-009-thundering-herd, pc-010-missing-middle-stampede#1
    declined root_cause (9): 9 cyber refusal — rc-006-dashboard-timezone, rc-007-flag-default-on-restart, rc-010-rollback-did-not-help
  fable-5 — 0/1086 failed; 604 declined
    declined code_debugging (152): 152 cyber refusal — counter_increase_go, counter_increase_python, counter_increase_rust, counter_increase_typescript, covered_seconds_go, covered_seconds_python, covered_seconds_rust, covered_seconds_typescript +43 more
    declined code_efficiency (81): 81 cyber refusal — distinct_window_total_go#0,1, distinct_window_total_python, distinct_window_total_rust#1, distinct_window_total_typescript#0, largest_rectangle_go, largest_rectangle_python, largest_rectangle_rust, largest_rectangle_typescript +25 more
    declined code_generation (34): 34 cyber refusal — histogram_quantile_go, histogram_quantile_python, histogram_quantile_rust, histogram_quantile_typescript, percent_decode_go, percent_decode_python, percent_decode_rust, percent_decode_typescript +4 more
    declined code_refactoring (155): 155 cyber refusal — bill_summary_go, bill_summary_python, bill_summary_rust, bill_summary_typescript, check_limits_go, check_limits_python, check_limits_rust, check_limits_typescript +44 more
    declined code_review (156): all 52 cases cyber refusal
    declined metrics_timeseries (9): 9 cyber refusal — ts-bytes-counter-wrap, ts-cpu-flatline, ts-latency-inband-peak
    declined pattern_correlation (8): 8 cyber refusal — pc-006-vacuum-common-cause, pc-008-decoy-deploy#1,2, pc-009-thundering-herd
    declined root_cause (9): 9 cyber refusal — rc-006-dashboard-timezone, rc-007-flag-default-on-restart, rc-010-rollback-did-not-help
  fable-5.1 — 0/1086 failed; 3 declined
    declined code_debugging (3): 3 cyber refusal — normalize_path_python

## Recommendations

- **fable-5.1-low** is the strongest overall pick for log/metrics analysis workloads in this run (global score 73.8).
- For **log parsing** specifically, consider **fable-5** (92.1 vs 91.6).
- For **anomaly detection** specifically, consider **gemma-4-26B-a4b** (70.9 vs 64.8).
- For **metrics time-series** specifically, consider **opus-4.8** (81.8 vs 80.6).
- For **root cause & summary** specifically, consider **grok-4.5-low** (56.2 vs 55.8).
- For **multi-modal rca** specifically, consider **grok-4.6-low** (68.8 vs 65.8).
- For **efficiency & consistency** specifically, consider **qwen3-coder-30b** (77.8 vs 64.7).
