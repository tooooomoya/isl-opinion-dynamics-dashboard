# Uniform-opinion emergence calibration (2026-10-28)

Status: launched after measurement tests, Java tests, and a two-seed end-to-end smoke run passed. Live status is in `results/calibration_uniform_20261028/pipeline_status.json`; this document is the prospective specification, not a claim that calibration has finished.

## Scientific question

Can learning and interaction generate an opinion-conditioned posting-activity valley and a segregated repost network from an initially uniform opinion population? Opinions are fixed (`mu=0`). The experiment concerns activity/network emergence, not the emergence of an opinion distribution. The previous empirical-initialization experiment and its outputs remain separate.

## Frozen prospective measurement

- Initialization: 1,000 iid uniform opinions on [-1,1]. Finite seeds can have unequal bin counts and spontaneous left/right differences; symmetry concerns the ensemble, not exact equality in each realization.
- Activity: compute each of seven bins' per-person event rate, including agents who posted zero times. For each mirror pair, take the arithmetic mean of the two rates, with equal weights for sides. Divide each result by the neutral bin's per-person rate.
- Primary target, in order extreme / partisan / slight / neutral: **[1.7394583, 1.0486309, 0.7019427, 1]**. These are pre-2021-01-08 account means from the deduplicated 762-person panel. They differ from the old population-weighted folded target.
- Primary activity loss: mean of three squared standardized log-ratio residuals; neutral/neutral is identically one and adds no fourth residual. Bootstrap accounts within each original bin (5,000 draws); use bootstrap log-ratio SD with a 0.15 floor. Store shared-denominator covariance, but do not call this loss a likelihood or assume independent evidence from the three ratios.
- A half-event per original bin stabilizes logarithms in nearly silent bins for scoring. Preserve unsmoothed rates and ratios for interpretation.
- Tweet-type correspondence remains unresolved: public data count supplied tweet records, with private upstream original/repost filtering unavailable. Primary model event count is provisionally original+repost, matching the previous declared mapping; original-only ratios/loss are stored separately. Neither mapping is chosen by optimization.
- Network: root-author-to-reposter directed weighted events; same two-community detection pipeline on empirical and simulated largest weak components. Target Q=0.4783239903, tolerance=0.05. Cross-community share, Q by opinion sign, and community/sign agreement remain diagnostics.
- Combined objective: equal mean of activity and Q losses. Preserve the existing +50 invalid-structure/activity penalty; no two communities, giant fraction<0.5, fewer than n repost events in giant, or fewer than n original posts in the measurement window is invalid. Computational failures are recorded separately and excluded from surrogate fitting.
- No absolute activity/time-unit match. The seven-bin profile and signed left/right gaps remain visible as diagnostics; no sign-specific asymmetry is a fitted target.
- Degree distribution, individual activity inequality, and time-window drift are held-out checks. A model with good Q but poor ideological alignment or implausible activity/degree structure is not declared empirically realistic.

The runtime token `fit_baseline=empirical` means the mean similarity to the **realized simulated population** in the existing Java code. It does not import the survey composition. `init_dist=uniform` controls initialization. Retain this relative-reward mechanism without changing it during calibration.

## Search and validation budget

Same 25-dimensional physical parameter box as the previous study, including beta_h in [0,12], recognition/fit weights, independent action costs, learning settings, feed mixture/reach, rewiring, post lifetime, and initial degree. Use the corrected logarithmic-integer acquisition bounds from the start. No previous empirical-initialization scores are used to train the new surrogate.

1. 128 initial parameter settings × 2 seeds, 20,000 steps.
2. 64 RF/EI Bayesian-optimization settings × 3 seeds, 20,000 steps.
3. Four selected candidates × 20 fresh seeds, 40,000 steps.
4. Up to two viable confirmed candidates: alternate initial networks and pure feeds, 60 jobs in total; seven mechanism settings for the best candidate, 21 jobs.
5. Up to two viable candidates × 5 new seeds at 80,000 steps; best candidate with beta_h=0 × 5 seeds. Longer runs assess transient fits; they do not imply convergence by construction.

Maximum main schedule: **624 simulator evaluations**, with 24 JVMs at a time and a 7,200-second per-job timeout. All measurements use the final 10,000 steps (or all steps for the separate smoke test). If fewer viable candidates exist, the validation count can be smaller. No candidate is automatically made the default.

After simulation, the pipeline exports tables, seven-bin diagnostics, the primary `symmetric_neutral_profiles.png`, degree/activity CCDFs, surrogate checks, and directed-strength-preserving network-null diagnostics (10 permutations, first three sorted successful confirmation seeds per candidate). `PIPELINE_COMPLETE.json` requires all stages; `COMPLETE.json` covers the simulator schedule only.

## Verification and provenance

- Python measurement/scheduler tests: 9 passed, including equal-side weighting under unequal populations, clock-scale and reflection invariance, and refusing to mix studies in one output directory.
- Java `test.ModelTests`: ALL PASS using smoke-run frozen classes.
- Two seeds × 1,000 steps: status ok, loss_version=3, init_dist=uniform, mu=0; observed bin counts sum to 1,000 and populate all bins. Those short runs are implementation checks, not evidence of fit.
- A separate analysis smoke export checks plot/report generation.
- Each main run snapshots Java sources/classes and Python driver/measurement files; manifest records source hashes, measurement hash, target hash, and base tokens. Resume refuses changed study, measurement, target, or baseline specification. Configurations and outcomes are saved per seed. Historical outputs are not rescored.

## Locations and resumption

- Run: `results/calibration_uniform_20261028/`
- Logs/PID: `logs/calibration_uniform_20261028/{pipeline.pid,pipeline.out,full.out,analysis.out,network_null.out}`
- Results: `docs/report/bayesian-calibration-uniform-2026-10-28/`
- Launch/resume the whole pipeline: `venv/bin/python -u scripts/run_uniform_calibration.py --workers 24` (check the saved PID before resuming).
- Export an interim report: `venv/bin/python scripts/analyze_bayesian_calibration.py --run results/calibration_uniform_20261028 --output docs/report/bayesian-calibration-uniform-2026-10-28`

Design rationale and checked sources: [initial-distribution review](2026-10-28-initial-distribution-design-review.md); detailed empirical event/selection caveats: [source audit](2026-10-27-calibration-source-audit-and-search-design.md).

## Confirmation update (2026-10-28, approximately 16:00 JST)

All four candidates have completed the prespecified 20 fresh seeds at 40,000 steps; the remaining validation bundle is still running at this update. The earlier two-seed valley candidate does not retain its quantitative fit: original extreme/neutral changes from 1.584 in search to 3.316 in confirmation, and slight/neutral from 0.792 to 1.425. Both horizon and seed sample change, so this contrast alone does not isolate the cause. The best confirmed candidate by both primary activity loss and combined loss instead has nearly flat original activity (extreme/neutral 0.996, slight/neutral 0.949), primary activity loss 4.018, and Q=0.430. These are not a successful empirical valley fit.

Generated separate confirmed-fit and earlier-valley search/confirmation PNGs, including seven-bin diagnostics. Full parameter comparison against the actual `standard_run.py` standing hkshuf/For You configuration, incorporating inherited overrides and Java defaults: [comparison report](bayesian-calibration-uniform-2026-10-28/best_fit_comparison.md). This comparison does not imply isolated causal effects of changed parameters. Current-run confirmation remains 20 seeds; user preference for **future** confirmations is 10 seeds.

## Prospective seed/horizon policy update (2026-10-28, approximately 16:16 JST)

The user requested at least about five seeds during search after seeing large search/confirmation differences. Future driver defaults are now five seeds per initial setting, five per BO setting, and ten fresh confirmation seeds. Both search and confirmation default to 40,000 steps to remove the previous horizon change. Shared search seed numbers are used across settings; they vary initial opinion draws, initial network realization, and stochastic dynamics. Network-family variation remains a separate validation dimension.

Persist `execution_design.json` per run and reject conflicting resume requests. Existing manifests without that file recover their historical 2/3/20 seed counts and 20k/40k horizons. The active run's historical specification has been saved explicitly; its process was not restarted or modified. The archived original driver/simulator remain intact. Ten Python tests pass, including new default budgets, preservation of old runs, rejection of changed frozen schedules, and actual five-seed submission to the BO scheduler. No additional full search was launched in this policy update.
