# Current-model calibration results (random)

Completed simulator jobs: 345; currently failed evaluations: 0; preserved failed/retried attempts: 0. Full schedule complete: True.

Primary comparison: iid uniform fixed opinions; three log activity ratios relative to neutral, with equal weights for left/right per-person rates. Primary events: originals+reshares; original-only is measurement sensitivity. Repost root Q uses the identical empirical/model detector.

Empirical collection filters are unavailable; an all-record count is provisionally matched to originals+reshares. This does not establish original-only empirical fit. No defaults have been adopted.

Study: uniform-raw-reduced-v5; 13 explored parameters. Fixed inputs: q_eta=0.1, rho_l=0.3, rho_r=0.3, l_ref=1000, recog_mix=0.5, recog_lambda=2, foryou_hop=5, trend_hop=5, foryou_hop_lambda=0.5, feed_capacity=10, feed_u=0.444444, feed_v=0.5.

The fitted target is symmetric_neutral_profiles.png. Seven-bin activity_profiles.png is an asymmetry diagnostic. Ratios share a neutral denominator; standardized residuals are an engineering loss, not a likelihood. Opinion values remain fixed (mu=0); activity and network patterns can emerge.

Fitting and confirmation network: random. Network-transfer validation conditions are reported separately.

| Candidate | Seeds | Activity loss | Original-only loss | Root Q (95% CI for mean) | Degree Gini | Activity/window drift |
|---|---:|---:|---:|---:|---:|---:|
| C1 | 10 | 1.808 | 3.902 | 0.468 ± 0.009 | 0.515 | 0.045 |
| C2 | 10 | 3.599 | 3.266 | 0.472 ± 0.008 | 0.599 | 0.029 |

Held-out empirical pre-event activity: CV=1.852, Gini=0.701 (762 unique people). Individual model activity is originals+reshares in the declared final window; windows/events differ, so this is a shape check, not another optimized target.

| Candidate | Seeds | Individual activity CV | Activity Gini | Zero-activity fraction |
|---|---:|---:|---:|---:|
| C1 | 10 | 0.573 | 0.215 | 0.000 |
| C2 | 10 | 0.143 | 0.078 | 0.000 |

Search evaluated 64 parameter points. Best mean search loss: 0.954. Search winner selection is noisy and is superseded by fresh-seed confirmation.

Source and measurement details: ../2026-10-27-calibration-run.md and ../2026-10-27-calibration-source-audit-and-search-design.md.

Generated plots: activity_profiles.png, degree_ccdf.png, objective_tradeoff.png. Per-seed and per-point CSVs preserve all available raw component scores.
