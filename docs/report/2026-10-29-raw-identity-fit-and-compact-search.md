# Raw identity fit and compact exploration — 2026-10-29

The user approved raw mean similarity as the main identity reward and requested that the current relative-fit runs stop. The old three-network sweep was stopped on October 29 at the time recorded in `results/calibration_multinetwork_20261028/STOPPED_BY_USER.json`. Four Python managers and 23 simulator JVMs were stopped; a subsequent process check found no remaining simulator for that study. Completed results: HK-shuffled 735, random 645, DC-SBM 646 (2,026 total), with zero finalized computational failures in the job records. Partial output remains preserved and must not be scored as complete or as a scientific failure. Resource attempts remain archived. The old study is stopped, not complete.

## Reward specification

Main identity fit is now the arithmetic mean over feed posts of `1 - abs(x_i - x_post)/2`. Empty feed fit remains zero. Identity contribution is `w_fit * raw_fit`; recognition and action costs are unchanged. No agent-specific random-feed expectation is subtracted. This removes the normalization that gave endpoint agents a larger possible improvement over their own random-feed baseline. Opinion-space boundary effects remain.

The simulator already implemented raw mode and its Java default was raw. The effective change is to the standing launcher and a separately identified calibration study (`uniform-raw-v4`). Historical studies explicitly retain `fit_mode=relative`. Raw standing runs use `baseline_raw_*` IDs and `standard_raw_*` stage names so old standing outputs cannot be silently reused. Raw calibration outputs are separate from the stopped study. Raw mode does not calculate/use the relative baseline; the launcher omits `fit_baseline`.

The raw specification changes reward levels and may change learning transients at the same `q_init`. This is part of the new specification; the old-to-new difference is not, by itself, proof that normalization caused a valley. Initial Q remains a search dimension. A short smoke test is an execution check, not scientific confirmation.

## Prepared compact budget (not launched)

| Item | Per network | Across three networks |
|---|---:|---:|
| Pilot: 8 controlled anchors + 40 Sobol settings, 5 seeds, 20k steps | 240 | 720 |
| Bayesian proposals: 16 settings, 5 seeds, 20k steps | 80 | 240 |
| Confirmation: 2 finalists, 10 fresh seeds, 20k steps | 20 | 60 |
| Horizon: best confirmed finalist, 5 paired seeds, 40k steps | 5 | 15 |
| Total planned evaluations | 345 | 1,035 |

All three initial network families remain independently fitted: HK-shuffled, directed random, and degree-corrected SBM. Initial opinions remain uniform, fixed (`mu=0`), and independent of SBM blocks. Preserve the broad existing 25-dimensional parameter priors. Eight anchors compare beta 0 versus 3 under four feed mixtures; the other 40 pilot settings span all parameter dimensions. No observations from the old relative-fit objective enter this new optimizer.

This reduces planned main simulated steps from 132.72 million to 21.0 million (84.2% fewer), before retries and analysis. Default total concurrency is 12 (4 per network), chosen conservatively rather than claimed optimal. Wall time still depends on the new activity and post-lifetime dynamics; the step-budget reduction is not a measured speedup. No new wall-clock deadline is asserted.

Search and fresh-seed confirmation use the same 20k horizon. The 40k check reuses five of the winning condition's confirmation seeds, allowing a paired horizon comparison. Inspect its stability and window drift before treating a result as persistent. A 48+16 setting search in 25 dimensions is screening, not a comprehensive sweep or reliable causal parameter-importance study. Do not narrow dimensions solely on correlations from relative-fit runs.

The expensive automatic transfer/feed/mechanism matrix is deferred. Network-null analysis and standard result export remain in the pipeline. Gaussian-versus-uniform comparison is deferred until the raw uniform specification has interpretable candidates; it is not queued or running.

## Targets and interpretation

Only identity reward and exploration execution change here. The empirical symmetric seven-bin W-shaped activity target and root-repost network Q objective remain unchanged. The user's earlier valley question was a diagnostic simplification, not an instruction to replace the empirical scoring target. Original+repost activity remains the provisional primary observation mapping, with original-only rates reported separately; the empirical event-definition limitation remains. Report extreme/neutral ratios as diagnostics and do not describe them as proof of monotone U shape.

## Execution

Prepared command (not executed):

```bash
venv/bin/python -u scripts/run_multinetwork_calibration.py --compact-raw
```

Defaults write to `results/calibration_raw_20261029/` and `logs/calibration_raw_20261029/`. Scientific inputs, targets and execution budgets are frozen per new family. The compact driver rejects search/confirmation horizons other than 20k and seed budgets other than 5/10. Historical study tokens and output directories remain separate.

## Verification

Java compilation and the model assertion harness passed, including a new regression showing that the same perfectly matching feed earns identity reward 1 at opinions -1, 0 and +1 even when deliberately different stored relative baselines are supplied. Historical relative-fit tests still pass. Python calibration checks cover study isolation, broad compact pilot coverage, fresh confirmation seeds, and paired horizon seeds. An isolated raw-mode HK smoke test ran two seeds for 1,000 steps each successfully; both recorded raw mode without a fit-baseline token. Verification logs and smoke artifacts are under `results/raw_fit_verification_20261029/`.
