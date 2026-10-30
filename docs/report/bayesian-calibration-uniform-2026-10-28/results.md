# Current-model calibration results (calibration_uniform_20261028)

Completed simulator jobs: 624; currently failed evaluations: 0; preserved failed/retried attempts: 0. Full schedule complete: True.

Primary comparison: iid uniform fixed opinions; three log activity ratios relative to neutral, with equal weights for left/right per-person rates. Primary events: originals+reshares; original-only is measurement sensitivity. Repost root Q uses the identical empirical/model detector.

Empirical collection filters are unavailable; an all-record count is provisionally matched to originals+reshares. This does not establish original-only empirical fit. No defaults have been adopted.

The fitted target is symmetric_neutral_profiles.png. Seven-bin activity_profiles.png is an asymmetry diagnostic. Ratios share a neutral denominator; standardized residuals are an engineering loss, not a likelihood. Opinion values remain fixed (mu=0); activity and network patterns can emerge.

| Candidate | Seeds | Activity loss | Original-only loss | Root Q (95% CI for mean) | Degree Gini | Activity/window drift |
|---|---:|---:|---:|---:|---:|---:|
| C1 | 20 | 4.018 | 5.117 | 0.430 ± 0.008 | 0.792 | 0.026 |
| C2 | 20 | 14.316 | 22.723 | 0.416 ± 0.012 | 0.969 | 0.176 |
| C3 | 20 | 33.863 | 36.130 | 0.420 ± 0.020 | 0.928 | 0.083 |
| C4 | 20 | 21.566 | 20.307 | 0.183 ± 0.084 | 0.962 | 0.163 |

Held-out empirical pre-event activity: CV=1.852, Gini=0.701 (762 unique people). Individual model activity is originals+reshares in the declared final window; windows/events differ, so this is a shape check, not another optimized target.

| Candidate | Seeds | Individual activity CV | Activity Gini | Zero-activity fraction |
|---|---:|---:|---:|---:|
| C1 | 20 | 0.292 | 0.160 | 0.000 |
| C2 | 20 | 1.308 | 0.515 | 0.000 |
| C3 | 20 | 3.036 | 0.870 | 0.203 |
| C4 | 20 | 1.114 | 0.345 | 0.000 |

Search evaluated 192 parameter points. Best mean search loss: 1.905. Search winner selection is noisy and is superseded by fresh-seed confirmation.

Source and measurement details: ../2026-10-27-calibration-run.md and ../2026-10-27-calibration-source-audit-and-search-design.md.

Generated plots: activity_profiles.png, degree_ccdf.png, objective_tradeoff.png. Per-seed and per-point CSVs preserve all available raw component scores.
