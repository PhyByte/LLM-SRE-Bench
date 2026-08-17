# LLM Observability Benchmark — Summary Report

Generated: 2026-08-17 22:54:23 UTC

## Overall Ranking

1. **grok-4.6-low** — global score 74.7/100 (0/100 failed runs) — completed in 13m 56s
2. **grok-4.5-low** — global score 72.9/100 (0/100 failed runs) — completed in 18m 53s
3. **opus-4.8** — global score 72.0/100 (25/192 failed runs) — completed in 10m 47s
4. **fable-5** — global score 71.7/100 (0/192 failed runs) — completed in 36m 32s
5. **gpt-5.6-terra** — global score 71.3/100 (0/192 failed runs) — completed in 11m 27s
6. **grok-4.6** — global score 70.4/100 (1/192 failed runs) — completed in 173m 42s
7. **gpt-5.6-luna** — global score 69.3/100 (1/192 failed runs) — completed in 12m 59s
8. **grok-4** — global score 69.0/100 (0/192 failed runs) — completed in 30m 55s
9. **sonnet-5** — global score 69.0/100 (5/192 failed runs) — completed in 36m 29s
10. **gpt-5.6-sol** — global score 68.6/100 (0/192 failed runs) — completed in 21m 21s
11. **fable-5-low** — global score 68.3/100 (32/192 failed runs) — completed in 15m 45s
12. **gpt-4o** — global score 62.1/100 (0/192 failed runs) — completed in 13m 11s
13. **haiku-4-5** — global score 61.5/100 (32/192 failed runs) — completed in 5m 57s
14. **gemma-3-12B** — global score 52.1/100 (0/192 failed runs) — completed in 232m 23s

## Category Leaders

- **Log Parsing**: grok-4.5-low with 92.4 (next: fable-5 at 92.1)
- **Anomaly Detection**: opus-4.8 with 68.8 (next: fable-5-low at 67.4)
- **Pattern & Correlation**: grok-4.5-low with 92.0 (next: opus-4.8 at 90.7)
- **Metrics Time-Series**: grok-4.6-low with 100.0 (next: opus-4.8 at 100.0)
- **Root Cause & Summary**: fable-5-low with 62.3 (next: fable-5 at 60.3)
- **Multi-modal RCA**: grok-4.6-low with 68.8 (next: grok-4.5-low at 65.9)
- **Efficiency & Consistency**: haiku-4-5 with 83.2 (next: opus-4.8 at 77.5)

## Efficiency Details

- **grok-4.6-low**: avg latency 8.36s, avg tokens/call 3644, score stddev across runs 3.7 points, full set: 13m 56s
- **grok-4.5-low**: avg latency 11.33s, avg tokens/call 3817, score stddev across runs 3.1 points, full set: 18m 53s
- **opus-4.8**: avg latency 3.88s, avg tokens/call 1826, score stddev across runs 0.9 points, full set: 10m 47s
- **fable-5**: avg latency 11.42s, avg tokens/call 2993, score stddev across runs 1.3 points, full set: 36m 32s
- **gpt-5.6-terra**: avg latency 3.58s, avg tokens/call 2199, score stddev across runs 3.7 points, full set: 11m 27s
- **grok-4.6**: avg latency 54.57s, avg tokens/call 2318, score stddev across runs 3.3 points, full set: 173m 42s
- **gpt-5.6-luna**: avg latency 3.89s, avg tokens/call 2326, score stddev across runs 1.7 points, full set: 12m 59s
- **grok-4**: avg latency 9.67s, avg tokens/call 2195, score stddev across runs 4.1 points, full set: 30m 55s
- **sonnet-5**: avg latency 11.04s, avg tokens/call 3160, score stddev across runs 2.6 points, full set: 36m 29s
- **gpt-5.6-sol**: avg latency 6.67s, avg tokens/call 2234, score stddev across runs 2.2 points, full set: 21m 21s
- **fable-5-low**: avg latency 5.91s, avg tokens/call 1462, score stddev across runs 1.0 points, full set: 15m 45s
- **gpt-4o**: avg latency 4.12s, avg tokens/call 2050, score stddev across runs 0.3 points, full set: 13m 11s
- **haiku-4-5**: avg latency 2.23s, avg tokens/call 1229, score stddev across runs 2.6 points, full set: 5m 57s
- **gemma-3-12B**: avg latency 72.62s, avg tokens/call 2470, score stddev across runs 1.0 points, full set: 232m 23s

## Reliability

- fable-5-low: 32 failed run(s) (API errors or invalid JSON output)
- haiku-4-5: 32 failed run(s) (API errors or invalid JSON output)
- opus-4.8: 25 failed run(s) (API errors or invalid JSON output)
- sonnet-5: 5 failed run(s) (API errors or invalid JSON output)
- gpt-5.6-luna: 1 failed run(s) (API errors or invalid JSON output)
- grok-4.6: 1 failed run(s) (API errors or invalid JSON output)

## Recommendations

- **grok-4.6-low** is the strongest overall pick for log/metrics analysis workloads in this run (global score 74.7).
- For **log parsing** specifically, consider **grok-4.5-low** (92.4 vs 91.4).
- For **anomaly detection** specifically, consider **opus-4.8** (68.8 vs 64.1).
- For **pattern & correlation** specifically, consider **grok-4.5-low** (92.0 vs 88.0).
- For **root cause & summary** specifically, consider **fable-5-low** (62.3 vs 53.9).
- For **efficiency & consistency** specifically, consider **haiku-4-5** (83.2 vs 51.5).
