# Reduced raw-fit calibration — 2026-10-29

The user approved reducing the exploration dimensions and launching the new study. This supersedes the unlaunched 25-parameter raw-fit plan. The historical relative-fit sweep remains stopped and preserved.

## Specification

Study identifier: `uniform-raw-reduced-v5`. Initial opinions: iid uniform on [-1,1], fixed (`mu=0`). Identity reward: `w_fit` times raw mean feed similarity, with no opinion-specific baseline. Rewiring, recognition, action costs and learning otherwise retain the established simulator mechanisms.

Thirteen parameters are explored, preserving their previous ranges and priors:

| Parameter | Range | Prior |
|---|---|---|
| beta_h | 0–12 | uniform |
| like_max_dist | 0.1–2 | uniform |
| q_tau | 0.02–2 | log uniform |
| q_eps | 0–0.3 | uniform |
| q_init | 0–20 | uniform |
| rec_fraction | 0.05–0.95 | uniform |
| cost_post | 0–2 | uniform |
| cost_reshare | 0–2 | uniform |
| cost_rewire | 0–4 | uniform |
| dead_after | 10–400 | integer, log uniform |
| access_prob | 0.02–0.3 | log uniform |
| fy_beta | 0–40 | uniform |
| start_deg | 5–50 | integer, uniform |

`w_rec=10*rec_fraction` and `w_fit=10*(1-rec_fraction)`.

Twelve inputs are fixed:

| Input | Value |
|---|---:|
| q_eta | 0.1 |
| rho_l | 0.3 |
| rho_r | 0.3 |
| l_ref | 1000 |
| recog_mix | 0.5 |
| recog_lambda | 2 |
| foryou_hop | 5 |
| trend_hop | 5 |
| foryou_hop_lambda | 0.5 |
| feed_capacity | 10 |
| feed_u | 4/9 |
| feed_v | 0.5 |

The last two inputs imply exactly one-third Chronological, one-third For You, and one-third Trend feeds in expectation. This is a controlled environment, not evidence that feed mixture is irrelevant. All fixed inputs are explicitly recorded in parent and per-family manifests and simulator tokens. Earlier marginal associations support prioritization, not proof of negligible causal influence; they were measured under relative identity fit and had weak activity prediction. Capacity, mixture, and distance decay are deliberate simplifications. Keep initial Q explored because raw rewards can change learning transients.

## Budget and networks

Independent searches for HK-shuffled, directed ER random, and degree-corrected SBM. Network density remains matched through the explored start degree; SBM block labels remain independent of opinions.

Per network: 48 pilot settings (8 controlled anchors + 40 scrambled Sobol draws), 16 Bayesian RF/EI proposals, five common search seeds per setting, 20,000 steps. The eight anchors span beta 0,1,2,3,6,12 at balanced reward weights and beta 3 at recognition fractions 0.2/0.8, with the same fixed feed mixture. Two finalists receive ten fresh seeds at the same 20k horizon. The best confirmed condition receives a 40k horizon check using its first five confirmation seeds, allowing a paired comparison. Total planned main simulations: 1,035; total planned simulated steps: 21 million. Twelve JVM workers total, four per family. Resource retries remain bounded and archived.

The budget has 84.2% fewer simulated steps than the stopped sweep. This is not a measured wall-time speedup or a reliable global sensitivity study. The automatic blanket feed/transfer/mechanism matrix is deferred. Standard report generation and degree/strength-controlled network nulls remain enabled. No old relative-fit observations are reused for training.

The empirical activity target remains symmetric W-shaped seven-bin activity, equal-side per-person rates relative to neutral, with original+repost as the provisional primary observation mapping and original-only as sensitivity. Repost Q remains the other fitted component. The earlier extreme/neutral contrast remains a diagnostic, not a replacement empirical target. Degree distribution and horizon/window drift remain validation outputs. Gaussian versus uniform and local perturbations of fixed inputs remain follow-ups, not running stages.

## Launch and artifacts

```bash
venv/bin/python -u scripts/run_multinetwork_calibration.py --reduced-raw
```

Results: `results/calibration_raw_reduced_20261029/`.
Logs and pipeline PID: `logs/calibration_raw_reduced_20261029/`.
Reports: `docs/report/bayesian-calibration-raw-reduced-20261029/`.

The parent pipeline freezes the workflow sources and design before launch; each family archives Java source/classes, target hashes, active priors, fixed inputs, and complete simulator configurations. Completion requires simulation, report generation, and network-null stages for all three families. Read `pipeline_status.json` for actual status; do not describe 20k finalists as horizon-stable until the paired 40k check is reviewed.

## Verification before launch

Eighteen Python tests pass, including historical-study isolation, 13-dimensional optimizer proposals, 12 fixed inputs, equal feed shares, reduced pilot coverage, and seed/horizon policies. A two-seed end-to-end 1,000-step smoke run under the reduced study succeeded; this checks execution and measurement, not fit quality. The preceding Java model tests passed, including common-baseline reward equality at neutral and both extreme opinions. Verification artifacts: `results/raw_reduced_verification_20261029/`.
