# Current-model calibration results (2026-10-27 run)

Completed simulator jobs: 818; currently failed evaluations: 13; preserved failed/retried attempts: 2. Full schedule complete: True.

Primary comparison: deduplicated pre-2021-01-08 seven-bin activity; model originals+reshares; root-attributed repost network, identical two-community detector on empirical/simulated graphs.

Empirical collection filters are unavailable; an all-record count is provisionally matched to originals+reshares. This does not establish original-only empirical fit. No defaults have been adopted.

Proposal audit: 16 pre-correction lifetime-400 proposals are retained as valid physical evaluations, followed by a separate budget of 64 proposals with corrected integer-log acquisition bounds. See proposal_history.csv; these policies must not be conflated in an optimizer benchmark.

| Candidate | Seeds | Activity loss | Original-only loss | Root Q (95% CI for mean) | Degree Gini | Activity/window drift |
|---|---:|---:|---:|---:|---:|---:|
| C1 | 20 | 4.163 | 4.158 | 0.457 ± 0.010 | 0.913 | 0.006 |
| C2 | 20 | 3.878 | 4.776 | 0.447 ± 0.021 | 0.864 | 0.420 |
| C3 | 20 | 4.510 | 5.696 | 0.385 ± 0.020 | 0.970 | 0.176 |
| C4 | 20 | 2.340 | 2.493 | 0.437 ± 0.027 | 0.842 | 0.017 |

Held-out empirical pre-event activity: CV=1.852, Gini=0.701 (762 unique people). Individual model activity is originals+reshares in the declared final window; windows/events differ, so this is a shape check, not another optimized target.

| Candidate | Seeds | Individual activity CV | Activity Gini | Zero-activity fraction |
|---|---:|---:|---:|---:|
| C1 | 20 | 0.033 | 0.019 | 0.000 |
| C2 | 20 | 2.617 | 0.786 | 0.000 |
| C3 | 20 | 1.342 | 0.510 | 0.000 |
| C4 | 20 | 0.983 | 0.415 | 0.000 |

Search evaluated 256 parameter points. Best mean search loss: 0.933. Search winner selection is noisy and is superseded by fresh-seed confirmation.

Credit attribution at the standing mixed-feed baseline: see credit_probe.csv and credit_probe.png. These are local contrasts; the global search specification is unchanged.

beta_h at the improving vocal-profile candidate: see profile_beta_probe.csv and profile_beta_probe.png. These are local contrasts; the global search specification is unchanged.

Source and measurement details: ../2026-10-27-calibration-run.md and ../2026-10-27-calibration-source-audit-and-search-design.md.

Generated plots: activity_profiles.png, degree_ccdf.png, objective_tradeoff.png. Per-seed and per-point CSVs preserve all available raw component scores.
