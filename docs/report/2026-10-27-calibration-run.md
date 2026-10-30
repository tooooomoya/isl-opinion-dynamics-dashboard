# 2026-10-27 — Current-model Bayesian calibration run

User authorized proceeding with the broad source-audited design, including long runtime.
This run implements that design; it does not adopt calibrated defaults automatically.

## Frozen measurement and search specification

- Current attention-economy mechanism: bandit learner, fixed intrinsic ideology, rewiring on without similarity gate, stock credit; standing corrected Trend ranking and tie handling.
- Empirical initialization restored using the **762 unique-person** ideology counts. Within each of the seven ordinal bins, opinions are uniform; this is a declared mapping, not a measured psychological scale. Relative identity fit uses the realized population's expected similarity, not the uniform-population analytic expression.
- Vocal target: per-person daily activity before 2021-01-08, seven bins, mean-centered log-rate profile. Primary model observation is original+reshare activity by the acting agent; original-only fit is separately retained. Upstream collection filters remain unavailable, so the primary event mapping is provisional and cannot establish original-only realism.
- Activity loss: mean squared residual across the seven centered log rates, scaled by account-bootstrap SD (5000 replicates), each SD floored at 0.15. This stabilizes sampling weights; the seven residuals are correlated, so this is a declared calibration loss, not a likelihood/chi-square statistic. A half event per bin smooths entirely silent bins; raw rates are retained.
- Repost target: raw Conover release reprocessed with the **same** detector used for simulations. Weighted undirected projection, at most two communities from the leading-eigenvector method, six label-propagation runs initialized from it, select maximum directed weighted Q among the resulting two-label partitions. The release gives Q=0.4783239903 under this pipeline, versus 0.4778744664 using the published partition. The detector can return one label on unstructured graphs; those do not count as a two-camp match.
- Root attribution: original/source author -> resharer. Immediate-copy-author graph is logged and scored separately. All agents included in structural detection; no neutral-band exclusion. Largest weak component used. Primary network loss is squared Q error / 0.05². The 0.05 is a calibration tolerance, not an empirical standard error.
- Combined loss is the equal mean of activity loss and network loss. Every component remains in the output. Add a 50 penalty to runs without two structural communities, largest component covering at least half of agents, at least n reshares in that component, and at least n originals overall. These are declared degeneracy checks, not further empirical targets. Degree diagnostics are held out.
- Each simulation n=1000, search horizon=20000, primary measurement = last 10000 steps; exact activity and root/immediate graph logs in disjoint 5000-step windows. Consecutive-window drift retained. Display metrics sampled every 100 steps, with exact event logs independent of this sampling.
- Primary initial network = hkshuf; degree 5–50 varies, with hk_m coordinated to it; hk_a=4, hk_pt=.05. Other initial network families checked after confirmation. Conditional HK shape dimensions are not active in this initial 25-dimensional run.
- Feed mixture is searched using two coordinates transformed onto the three-feed simplex. The resulting mixture is a nuisance calibration condition; feed counterfactuals hold behavioral parameters fixed.

Search box is encoded in `scripts/bayesian_calibration.py` (`SPACE`) and the immutable run manifest. It matches the 25-dimensional table in the source-audit report. Reward weights sum to 10; costs independently span post [0,2], reshare [0,2], rewire [0,4].

## Budget and seeds

1. **128 points × 2 seeds = 256 simulations.** Twenty-eight anchors span four feed conditions and beta_h {0,1,1.5,2,2.5,3,6}; the remaining 100 points use a scrambled Sobol design transformed through the declared priors. Shared search seeds 271000–271001.
2. **64 Bayesian proposals × 3 seeds = 192 simulations.** Random-forest surrogate, expected improvement, eight sequential batches of eight. Seed 271002 added; same objective/source as pilot. The third seed improves precision during refinement, while initial points stay explicitly labeled as two-seed estimates.
3. **4 candidates × 20 fresh seeds = 80 simulations**, horizon 40000, seeds 272000–272019. Candidate set includes best combined fit, best vocal fit and best network fit; fourth by combined score. No claim of a stable winner from the search's small seed count alone.
4. Top two confirmed candidates: three other initial networks × five fresh seeds (30 runs), and three pure-feed counterfactuals × five fresh seeds (30 runs), all 40000 steps.
5. Best combined confirmed candidate: seven explicit mechanism variations × three fresh seeds (21 runs), all 40000 steps. Variations: gate on, rewiring off, state-based Q learner, notifications off, raw fit, post noise .2, delayed post credit. These are checks, not silent replacements for the fitted mechanism.

**Total planned: 609 simulations**, excluding smoke/regression checks. All complete seeds cache individually; optimizer proposal batches save before launch. Source snapshot compiled into an isolated directory. No old BO observations used. Default concurrency 16, JVM heap limit 2 GB; host has 32 logical CPUs/112 GiB RAM, with >60 GiB free at launch. Plenty of disk headroom. Each job timeout 1800 s is recorded as failure, not a successful/zero-loss run.

## Implementation and validation before full launch

- Added optional `calibration_log`, `metrics_every`, and short `run_id`. Defaults retain ordinary reporting; short IDs are paired with full launch configs and source hashes.
- New exact logger writes every agent, including zero-activity agents, and separate source/root graphs. It performs no random draws and fails loudly on write errors.
- Java `test.ModelTests`: **ALL PASS**, including empirical-init weights, copy-chain attribution and window reset/zero-activity tests.
- Python measurement tests: **4 passed**, covering feed-simplex/parameter mapping, scale invariance of activity profiles, structural detection distinct from ideology-sign partitions, and component coverage with isolates.
- Two-seed 1000-step smoke: complete, zero simulator assertion errors; exact activity and reshare graph totals match existing action logs.
- End-to-end equivalence (seed 279999, n=120, 1000 steps): with ordinary per-step reporting versus sampled metrics+calibration logging, final agent snapshots, follow edges, Q table, agent action counts and reaction graph are **byte-identical**. Logging/metric sampling did not change the simulated trajectory in this check.

Raw sources are cached persistently in ignored `results/empirical_source_audit/`. Extra analysis dependencies are pinned in `scripts/requirements-calibration.txt`.

## Run paths

- Driver: `scripts/bayesian_calibration.py`
- Metrics/target construction: `scripts/calibration_metrics.py`
- Output: `results/calibration_20261027/` (manifest, frozen sources, targets, per-seed JSONs, configurations, complete run outputs, pilot/BO/confirmation/validation summaries)
- Driver log: `logs/calibration/full.out`
- Pilot/source checks: `results/calibration_smoke_20261027/`, `results/calibration_equivalence_20261027/`, `logs/calibration_tests.log`

The full run will be considered complete only when all planned phases finish and results have been analyzed, including failures and limitations. Results and interpretation will be appended here.

## Additional source and null-model checks during the pilot

- The released activity notebook sets its ITS intervention date to 2021-01-09, whereas the paper describes 2021-01-08. The frozen target follows the **paper** (counts through January 7 inclusive). This one-day implementation discrepancy does not change the running objective.
- These are distinct observational populations: the activity panel counts supplied tweets among matched survey respondents, while Conover selects political-hashtag tweets before an earlier election. The model's ideology-bearing posts are treated as political for the latter comparison. The fit is to multiple stylized facts; it is not a single-population joint-data likelihood.
- Ten directed event-stub permutations of Conover's released graph preserve each node's in/out event strengths (parallel events/self loops allowed). Under the identical detector, observed Q=0.478324; null mean=0.124488, SD=0.010797; excess Q=0.353836. These are **our** null-model results, not a reproduction of the paper's z=11.02 (different null/construction). This held-out diagnostic does not alter the fitted raw-Q objective. Finalists will receive the same check.

## Early credit-attribution probe (additional 16 simulations)

At 100 completed pilot simulations, Q could be close while activity remained nearly flat. Before interpreting this as a mechanism limitation, launch a small independent probe of an existing mechanism option: stock versus delayed-post credit, crossed with beta_h {1,2,3,6}, standing 50/50 For You–Trend mixture, all other standing parameters fixed, two fresh seeds 276000–276001, 20000 steps. The main 25-dimensional search remains unchanged. Four additional JVM slots use the available CPU/RAM headroom (20 JVMs total on 32 logical CPUs; about 45 GiB unused RAM before adding these four).

This is a **single-baseline mechanism probe**, not optimization over the alternate specification and not a causal conclusion across the entire parameter space. Code `scripts/calibration_credit_probe.py`, log `logs/calibration/credit_probe.out`, aggregate `results/calibration_20261027/credit_probe.json`. Combined budget including this probe: 625 simulations, excluding smoke/regression checks. Per-job hashes/seeds are distinct from the primary run.

## Targeted beta contrast at an improving vocal-profile point (14 additional simulations)

By roughly half the initial pilot, one point gave originals+reshares relative to the middle bin approximately `[1.49,1.40,.90,1,1.19,1.50,1.44]` across two search seeds; originals alone also showed outer-bin elevation in both seeds. Q was about .35, and the empirical right-side inner-bin dip was absent. This is a promising **partial** pattern, not a successful seven-bin fit.

Preserve the global search unchanged and freeze this vocal candidate for a beta_h-only contrast at {1.5,2,base,3,4,6,9}, two fresh seeds 277000–277001, 20000 steps. The exact selected base/seed records are saved in `profile_beta_design.json` before launch. This tests whether the distance dial can improve structural fit while retaining the vocal pattern, without narrowing the broad search. Code `scripts/calibration_profile_beta_probe.py`. It waits for the credit probe to finish before using its four worker slots. Combined scheduled budget now **639 simulations**, excluding smoke/regression checks. If this supplemental check yields a clearly better candidate, it will require fresh-seed long-horizon confirmation before interpretation.

## Runtime correction after two computational timeouts

One Sobol point (both search seeds) reached the original 1800-second limit around steps 11k–13k: long lifetime 312, access ~.299, For You share ~.628. No assertion error/OOM was reported. These are computationally censored observations, **not measured bad fits**.

Increase the job limit to 7200 seconds and retry those two jobs with a 4 GB heap; ordinary jobs retain 2 GB. Preserve the old attempt JSON/logs and interrupted outputs. Update the driver so completed exact-hash outputs and still-running exact-hash JVMs can be adopted after a driver restart. Restart the manager only; existing simulations continue. Compiled simulator snapshot, target data, objective, parameters, and seeds are unchanged.

Also correct surrogate handling: a failed point remains explicitly recorded but is excluded from surrogate fitting. The original placeholder loss=1000 is bookkeeping for a missing evaluation and must not be interpreted as a scientific measurement. No BO round had started, so no proposals were informed by those placeholders.

Runtime worker limit becomes 20 plus at most four supplemental slots (24 total). Host still has substantial unused RAM and logical CPU capacity; normal heap caps sum to 48 GB, plus 4 GB extra for the two retries, below the 112 GiB host memory. The immutable original snapshot is retained; revised manager source is archived as `bayesian_calibration_runtime_v2.py`, with restart settings in `runtime_changes.jsonl`. A small later current-source tag fix makes optional measurement settings distinguishable in ordinary result folder names; calibration uses explicit run_id, so this does not alter any frozen simulation trajectory.

## Validation scheduling improvement (runtime v3)

Network/feed/mechanism checks are independent conditions. Submit their 81 jobs to one bounded worker pool rather than sequential tiny batches of only 3–5 jobs. Conditions, seeds, horizons, candidate selection and all scientific measurements are unchanged. Add a scheduler test verifying that independent conditions and seed groups remain separate under parallel execution (Python suite now five tests, all passing). Archive manager source as `bayesian_calibration_runtime_v3.py`; resume with exact-hash JVM/output adoption, without stopping ongoing simulations. Current-source Java test harness also passes after the optional measurement-tag fix.

## Pilot-tail overlap (runtime v4)

At 247/256 pilot jobs completed, the long-lifetime/high-access retry remains much slower than the ordinary points. Once 127/128 pilot points have complete outcomes, allow Bayesian refinement to start while the final point continues. Poll and incorporate its observed loss between proposal batches; do not substitute a fake loss. Require the pending outcome before selecting confirmation candidates. All 128 designed points and both seeds remain scheduled and retained. At most two extra pilot JVMs overlap the 20-slot refinement pool; this stays below the previously checked 24-JVM envelope.

This is an asynchronous scheduling change, not a changed simulator, event definition, parameter box, objective, or total point budget. Proposal history may depend on which genuine observations are available, as in asynchronous optimization generally. The scheduler test also checks that early-ready and pending pilot groups together contain every point. Archive as `bayesian_calibration_runtime_v4.py`, preserving earlier manager revisions and all in-flight JVMs.

At 125/128 points complete, three slow points remained. Runtime v5 supersedes the one-pending-point threshold with **at most four pending initial points** (at least 124/128 complete). Refinement concurrency is reduced by the pending seed slots to keep the global bound at 24 JVMs; every pending result is still required before confirmation. Frozen source, data, loss, and total budget are unchanged; tests pass. This avoids idle CPU while a small number of expensive points continue, and does not classify those points as poor fits.

## Point-level asynchronous refinement (runtime v6)

First refinement cohort showed the same long-tail runtime variation. Replace the eight-cohort barrier with point-level asynchronous updates: retain at most eight candidate points in flight, update the real forest only when all three genuine seed outcomes for a point are available, and fill a free point slot using EI. Constant-liar **copies** reserve pending initial/BO points while proposing; their temporary values never enter the real optimizer or the result dataset. Preserve the already-proposed first eight points and all running JVMs. Total refinement budget remains **64 points × 3 seeds**.

Persist the ordered proposal list in `bo_async_design.json`, observation/pending context in `bo_async_history.jsonl`, each completed point in `bo_point_*.json`, and legacy groups of eight for reporting. Failed points remain excluded from surrogate training. All initial and refinement outcomes are still required before selecting confirmation candidates. Worker budget remains bounded as above. This scheduling/proposal-policy change supersedes the fixed-cohort execution order only; it changes no model, measurement, objective, search box, or seed set.

Python suite now **six tests**, including exact async point/seed budget, real-versus-liar observation separation and pending-slot bounds. A separate dry run using the real skopt forest/EI implementation also passes. Manager source archived as `bayesian_calibration_runtime_v6.py`. At switch: 255/256 initial jobs and 19/24 first-cohort seed jobs had completed. One expensive initial seed still runs; no new computational failure is currently unresolved beyond that ongoing retry.

## Proposal-coordinate defect and correction (runtime v7)

After observing that every refinement proposal had dead_after=400, inspected the installed skopt 0.10.2 implementation. `Integer(..., prior='log-uniform')` transforms physical lifetime 100 to log-coordinate 2, but `Integer.transformed_bounds` returns physical bounds (10,400). `Optimizer._tell` clips a proposed log-coordinate against those bounds, so it is raised to at least 10; inverse transformation then saturates at physical 400. Direct prior sampling is broad, so a simple sampling test would not expose this acquisition-path defect.

Fix locally with a small `LogInteger` subclass returning log-coordinate bounds for identity/log mode, and (0,1) for normalized mode. Keep the discrete prior, physical range, all scientific parameters, and all actual simulation observations unchanged. Add a regression test checking transform/clip/inverse round trips and the **actual acquisition path** on a known one-dimensional optimum below 100; the old behavior would return 400. Python suite now **seven tests, all pass**.

The 16 pre-correction proposals are genuine physical evaluations at lifetime 400 and remain valid observations; their proposals were distorted and must not be described as a correctly functioning broad BO pass. Preserve them separately in the history and add a full **64 correctly proposed points**, rather than counting these 16 against the intended refinement budget. Saved budget is now 80 refinement points, recorded in `refinement_budget.json` and used automatically on resume. This adds 48 seed evaluations: **687 scheduled evaluations overall**, plus smoke/regression checks and the two preserved incomplete timeout attempts. Initial Sobol design and all 128x2 initial outcomes are unaffected.

Paused the proposal manager while diagnosing, leaving JVMs running, then resumed with archived source `bayesian_calibration_runtime_v7.py` and exact-hash output/JVM adoption. All scientific targets and the simulator remain frozen. No measured outcome is discarded or replaced with an optimizer prediction. The corrected acquisition bounds, rather than a changed objective or a widened parameter box, determine the remaining proposals.

## Cached-future capacity accounting (runtime v8)

On resume, already-completed initial results can briefly appear as pending futures while their cache files are read. Collect these before calculating refinement worker capacity; otherwise slots stay unnecessarily reserved for finished initial work. Test that such outcomes are incorporated before the optimizer's initial fit. Also allow up to twelve pending parameter points (three seeds each), while bounding actual JVM concurrency at 24, so partially finished seed groups do not leave CPU idle. Seven tests pass, including the new assertions and all 25 coordinate round trips.

With ~46 GiB unused RAM and ~46% logical CPU idle at the resource check, run at the already-declared 24-JVM upper bound (ordinary heap caps total 48 GB). All slow initial retries have now completed. Preserve in-flight simulations and the source/data/objective/budget. Archive scheduler source as `bayesian_calibration_runtime_v8.py`. This corrects resource accounting and queue occupancy, not a scientific mechanism.

## Decision (2026-10-27 ~23:10): symmetric (folded) activity loss, v2

- **Why:** the model is left/right symmetric, so the 7-bin empirical profile's L/R asymmetry (VL 1.86 vs VC 1.63; C 0.50 vs SL 0.65 mirror) cannot be fit by any parameter. Using it distorted ranking and the surrogate (e.g. the candidate with the best folded fit ranked outside the top by the v1 loss).
- **What:** mirror bins (1+7, 2+6, 3+5, 4) are pooled in both empirical target (person-level pooling, same bootstrap/0.15 floor recipe) and model (pooled counts / pooled population, +0.5 smoothing per folded bin). Q term, validity penalty, ranges, seeds unchanged. `loss_version=2`; v1 values kept as `*_v1_asym`.
- **Applied to:** all 512 stored ok jobs rescored from stored per-bin rates (no re-simulation; originals in `results/calibration_20261027/jobs_v1_backup_20261027`, old target in `targets_v1.json`). Driver restarted; BO budget raised 80 -> 128 so 48 new proposals are guided by the v2 surrogate. Confirmation/finalists/validation follow automatically under v2.
- **Supersedes:** the "frozen loss" condition in AGENT_RESUME. Earlier 7-bin L/R comparisons in this file are v1 diagnostics.
- Folded empirical relative profile (extreme, moderate, slight, middle): 1.73, 0.89, 0.51, 0.87. Min v2 activity loss over stored jobs: 0.22 (v1 min 3.59).

## Final interpretation (2026-10-28 ~03:50, v2 folded loss; run COMPLETE)

Schedule finished: 256 initial + 128 BO points (16 pre-correction + 64 corrected under v1 + 48 under v2), 4 finalists x 20 fresh seeds at 40000 steps, 19 validation settings. Figures/tables: `bayesian-calibration-2026-10-27/` (results.md, activity_profiles.png, degree_ccdf.png, objective_tradeoff.png, validation.csv). No defaults adopted.

**What the fresh-seed confirmation shows (activity loss is v2, 4 folded bins, sd floor 0.15):**
- No finalist fits both objectives. Activity loss 2.3-4.5 (a value of ~1 would mean ~0.15 log-units rms deviation per folded bin); Q 0.385-0.457 vs target 0.478 (tolerance 0.05, so Q is within ~1-2 tolerance units for three of four).
- Best search score (0.93, 2-3 seeds) did not survive 20 fresh seeds (winner's curse): the best confirmed total loss is 2.26.
- Shape (activity_profiles.png, 7-bin view is diagnostic only): the symmetric U (extremes above the middle, slight bins as the trough) is reproduced qualitatively by several finalists, e.g. C3 reaches ~1.5 at both extremes and ~0.6 at SL, and C4 matches the SC trough. The trough depth and the extreme/middle ratio are not matched jointly; the high-activity finalist C3 (extreme ~1.5x) has the weakest Q (0.385).
- The flat finalist C1 reaches the best Q (0.457) with individual-activity CV 0.03 (empirical 1.85): Q alone can be met by a model in which everyone acts at the same rate. C2/C3/C4 have CV 2.6/1.3/1.0 (Gini 0.79/0.51/0.42 vs empirical 0.70) - heterogeneity emerges without being targeted, but it is not paired with the right bin profile.
- C4 has the best activity loss (2.34) but 40% of its search-phase runs were flagged invalid (degeneracy penalty), so its total loss is 22; treat as a fit to the activity shape in the valid runs only.

**Degree (held out):** in-degree is strongly bimodal: P(followers=0) = 0.59-0.95 across finalists. Real follow networks do not have such a large zero-follower mass, so the degree distribution is not reproduced by any finalist. Per rewire's out-degree conservation this is mainly set by feed/rewiring dynamics, not by a tuned parameter.

**Robustness of the fit (validation.csv):** the first two confirmed candidates keep Q 0.4-0.47 under random initial network and some feed switches, but fit is fragile: HK initial network / For You-only feed / rewire gate on collapse Q (0.15-0.33 in the worst cases, network loss up to 43), and dcsbm gave invalid runs for one candidate. Calibrated behavior parameters are therefore not feed-/initial-network-invariant - relevant for the feed counterfactual study, which should be reported with this dependence rather than assuming a fixed behavioral calibration.

**Honest conclusion:** within this finite 25-dimension search, partial fits exist (symmetric U-shape in activity, or Q near 0.45), but not a joint fit of the folded activity profile, Q, and a plausible degree distribution. Likely structural gaps: activity heterogeneity and the zero-follower mass are not controlled by the searched behavioral parameters. Candidate next steps (not started): include individual-activity heterogeneity as an objective, and examine the zero-follower mass as a structural (rewire/feed) issue.
Caveats: all losses depend on the declared sd floor (0.15) and Q tolerance (0.05), which are not estimated standard errors; empirical activity (survey panel) and Q (hashtag retweets) are from different populations/periods.
