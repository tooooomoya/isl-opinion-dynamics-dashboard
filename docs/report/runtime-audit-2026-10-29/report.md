# Runtime comparison, 2026-10-29

Previous uniform study: 624 simulations, 24 workers, started 2026-10-28 12:19:34, simulation schedule finished 2026-10-28 16:16:20 (approximately four hours).
New design: up to 3,288 unique evaluations across three independent fits. Total scheduled simulator steps increase from 16,400,000 to 132,720,000, a factor of 8.09. Search alone increases from 8.96 million to 115.2 million steps (12.86x). Resource-retry attempts add work beyond these counts.

Java source hashes are identical. Among 252 successful matched HK-shuffled parameter/seed pairs, excluding resource retries, median 40k/20k runtime ratio is 1.85, p90=2.21. This is broadly consistent with doubling the horizon, rather than a general throughput collapse. Completed-success conditioning omits the most expensive failed/retried tail; this is not a controlled concurrency benchmark.

Earlier ordinary baseline runs (results/rsearch/summary.jsonl) used 20k steps and fixed lifetime 50: medians about 40–45 seconds for Chrono and 76–173 seconds for For You depending on network. The ordinary standard script defaults to 12 workers; the previous uniform calibration explicitly used 24.

Host snapshot at 12:44 JST: 16 physical / 32 logical CPU cores; about 80% CPU use, 28 GB unused memory, zero swap use/pageouts/compression, and CPU speed/scheduler limits at 100% with no recorded thermal/performance warning. These observations do not establish the optimal worker count; they do not show global swapping or thermal throttling. Per-JVM heap pressure in expensive runs is independently documented in the main restart report.

Runtime-accounting caveat: metadata seconds can include time between actual simulator completion and manager adoption/collection. Use log/config timestamps as a wall-time proxy in this audit. In the current HK BO subset this makes the recorded mean substantially larger than the observed simulator-wall mean. No scientific outcomes or job metadata were changed by this audit.

| Run | Phase | Completed successes | Median simulator-wall seconds | P90 | Recorded mean / simulator-wall mean |
|---|---|---:|---:|---:|---:|
| previous_uniform | pilot | 256 | 208 | 882 | 347 / 345 |
| previous_uniform | bo | 192 | 248 | 533 | 329 / 327 |
| new_hkshuf | pilot | 636 | 383 | 1744 | 675 / 674 |
| new_hkshuf | bo | 38 | 870 | 3329 | 2573 / 1419 |
| new_random | pilot | 561 | 421 | 2475 | 950 / 940 |
| new_dcsbm | pilot | 560 | 428 | 2448 | 945 / 900 |
