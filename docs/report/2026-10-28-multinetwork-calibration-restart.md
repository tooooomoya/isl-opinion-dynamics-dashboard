# Multi-network uniform-opinion calibration restart (2026-10-28)

The user requested fitting on random and SBM networks in addition to HK-shuffled and restarting with the updated seed budget. The preceding single-network run had already completed all simulation, report, and null stages at 16:17 JST; no processes remained to stop. Its results and scientific specification are preserved.

## Independent fitting conditions

Run three separate calibrations on `hkshuf`, `random`, and `dcsbm`. Each family has its own RF/EI surrogate, candidates, fresh-seed confirmation, and results. This estimates network-specific parameter sets; it does not assume that a single parameter vector fits all three families. Cross-network transfer remains a separate validation exercise.

- **HK-shuffled:** existing directed Holme–Kim generation, A=4, triangle probability=0.05, m coordinated with searched density; directed degree-preserving swaps before optional exact density enforcement.
- **Random:** directed Erdős–Rényi graph, p=start_deg/(n−1), then enforce exactly n×start_deg edges. This keeps the searched density comparable across families.
- **SBM:** existing degree-corrected SBM (the standing script's `sbm` condition maps to `dcsbm`): four balanced, randomly assigned blocks; p_in=0.08, p_out=0.002, degree exponent=2.3; sbm_deg=start_deg, followed by the same exact density enforcement. Block membership is independent of opinions; these runs begin with structural clustering. A high repost Q alone therefore does not establish emergence of political segregation. Report community/opinion alignment, sign Q, and randomized-network diagnostics.

All conditions use 1,000 iid uniform intrinsic opinions, mu=0, and evolving rewiring. Network/dynamics seed streams are separate but derived from each shared seed number. Same initial parameter design and seed numbers across the three families; independently adaptive BO proposals after that. The original 25-parameter ranges are retained, including density 5–50. SBM block parameters are fixed structural assumptions in this search, not extra searched degrees of freedom.

## Seed, horizon, and budget specification

For **each network family**:

1. 128 initial settings × **5 seeds** × 40,000 steps = 640 simulations.
2. 64 RF/EI settings × **5 seeds** × 40,000 steps = 320 simulations.
3. Four finalists × **10 fresh seeds** × 40,000 steps = 40 simulations.
4. Up to 96 validation simulations: transfer to the three other network types (including unshuffled HK), pure-feed contrasts, mechanism contrasts, 80k-step horizon checks, and beta_h=0.

Maximum: **1,096 per network / 3,288 total main simulations**, plus the completed six short smoke simulations. Smaller counts are possible if fewer viable confirmed candidates exist. Individual job timeout remains 7,200 seconds. Pilot/BO computational failures remain separate from objective outcomes and do not train the surrogate. No old search/confirmation outcomes initialize the new surrogates. No fitted defaults are adopted automatically.

Three drivers receive eight workers each, **24 total**. A run-wide semaphore also bounds concurrency across overlapping pilot and refinement pools; otherwise small worker pools could briefly exceed the advertised limit during tail overlap. Network and measurement identity are frozen per manifest; seed/horizon design is persisted per family. A family cannot resume with a different fitting network. The multi-network pipeline holds an exclusive process lock to prevent duplicate parent launches.

Activity and network measurement remain exactly as in the [uniform study's prospective specification](2026-10-28-uniform-calibration-run.md): equal-side per-person rate ratios relative to neutral, three standardized log-ratio residuals, provisional original+repost event mapping with separate original-only sensitivity, and the matched detected two-community root-repost Q. The empirical symmetric target is [1.73946,1.04863,0.70194,1]. No absolute activity matching or left/right asymmetry target is introduced.

## Verification and operation

- Python tests: **12 passed**, covering new defaults, historical resume preservation, actual five-seed BO submission, network identity and density tokens, concurrency across overlapping pools, and existing metrics/acquisition tests.
- End-to-end smoke: two seeds per family at 1,000 steps, all six status=ok, loss_version=3, uniform initialization, expected network tokens, no simulator invariant failures.
- No Java scientific-model changes were required. Each new family snapshots and compiles its own identical Java source and saves the driver/measurement source and hashes. Parent workflow code and hashes are also archived.

Launched as a detached pipeline after the tests and smoke checks:

```bash
venv/bin/python -u scripts/run_multinetwork_calibration.py --workers 24
```

- Parent run: `results/calibration_multinetwork_20261028/`
- Family runs: `hkshuf/`, `random/`, `dcsbm/` below the parent.
- Parent process: `logs/calibration_multinetwork_20261028/pipeline.pid`.
- Logs: `logs/calibration_multinetwork_20261028/{hkshuf,random,dcsbm}/{full,analysis,network_null}.out`.
- Results: `docs/report/bayesian-calibration-multinetwork-2026-10-28/{hkshuf,random,dcsbm}/`.
- Parent status and per-family status JSONs are in the parent run directory. A parent `PIPELINE_COMPLETE.json` requires every family's simulation, analysis, and null stages to finish successfully. `COMPLETE.json` inside a family covers its simulation schedule only.

The previous run's 2/3-seed screening and changed confirmation horizon made initial ranking unreliable. This restart compares five-seed search outcomes at the same 40k horizon used for ten-seed confirmation. Five seeds reduce screening noise; they do not guarantee precise ranking or a successful fit. Interpret fresh-seed performance, variation, time drift, and structural plausibility together.

## Runtime correction (2026-10-29, approximately 09:13 JST)

At the morning check, HK-shuffled had 633/640 initial evaluations recorded; random and DC-SBM each had 495/640. Seventeen computational failures were recorded (15 two-hour timeouts and two HK-shuffled JVM heap exhaustions near step 39k). Failed points are excluded from surrogate fitting; these are not scientific fit measurements. Confirmation has not yet started in any family.

Found a static BO worker-reservation defect: at pilot-tail overlap, `workers=max(1,8−5×pending_points)` could create a one-worker BO executor that remained at one worker after the pilot tail finished. The shared run-wide semaphore already controls actual concurrency across both pools, so use the full eight-worker BO executor throughout. Keep the shared semaphore to retain the 24-JVM total cap. Extend the scheduler regression test to check that pending pilot points cannot permanently reduce executor capacity; all 12 tests pass.

Reloaded only the parent/driver managers after archiving the corrected manager as `runtime_driver_20261029.py` in each family. All 21 then-running simulator JVMs stayed alive for exact-configuration adoption. Preserve original source/classes, measurements, physical parameters, targets, seed/horizon budgets, outcomes, and proposal history. Runtime/proposal timing can change in this asynchronous optimizer; no surrogate receives invented outcomes. Old/new manager PIDs and preserved JVM PIDs are recorded in `runtime_changes.jsonl` in the parent run directory.

## Resource-failure recovery (2026-10-29, approximately 10:42 JST)

At 10:33, failed current evaluations numbered 11 HK-shuffled, 2 random, and 9 DC-SBM. The original two-hour timeout and 2 GB per-JVM heap are the relevant caps; at least one timeout log also contains a heap-exhaustion message. A jstat check at approximately 10:37 showed two slow JVMs with 100% old-generation occupancy and approximately 3,880–3,984 seconds of cumulative garbage collection over approximately two hours. This supports per-JVM heap pressure as an important contributor to the slow tail. It does not diagnose every allocation's source. Host-level memory was available. A subsequent snapshot is saved as `gc_resource_audit_20261029.json`.

Enable one bounded engineering retry of verified timeouts/heap exhaustion, with **4 GB heap and 10,800 seconds**. Keep normal attempts at 2 GB / 7,200 seconds, the same seeds/tokens/frozen simulator, and at most 24 live simulator JVMs. Archive the failed JSON/logs/raw partial output before retry. Persist retry resources per key so manager reloads adopt a retry with its correct limits. A second resource failure remains computationally censored; model/invariant failures are not automatically retried as resource failures.

Before launching, count inherited simulator JVMs as well as this manager's semaphore slots. This avoids oversubscription when retries of old failed keys enter the queue before the manager has adopted all later-running keys. Serialize the check-and-launch operation per family. Reloaded only the managers; all 24 then-running JVMs stayed alive. Corrected manager source is archived as `runtime_driver_resource_retry_20261029.py`; policy and manager changes are recorded in the parent run directory. Fifteen tests pass, including bounded retry classification, preserving simulator CLI tokens on a 2-to-4 GB retry, archiving failures, retaining a successful retry cache, and waiting for inherited-JVM capacity. Recovery is enabled, not yet verified to have resolved every failed seed.

Five-seed screening at 10:33–10:35: the best original-post profile so far in HK-shuffled has extreme/neutral=1.656, partisan/neutral=1.280, slight/neutral=1.038, Q=0.394; all five extreme ratios lie between 1.578 and 1.723. This is stable extreme elevation, but not the target inner-bin trough (0.702). Corresponding best original-profile settings in random and DC-SBM have extreme/slight ratios 1.135/0.941 (Q=0.447) and 1.189/0.975 (Q=0.437). These are preliminary screened settings, not fresh-seed confirmations or successful full-valley reproductions. Original-only remains a measurement sensitivity, while primary fitting still uses original+repost counts under the declared provisional mapping.

## Comparison with previous runtime (2026-10-29, approximately 12:49 JST)

[Runtime audit](runtime-audit-2026-10-29/report.md) and [matched-pair plot](runtime-audit-2026-10-29/matched_runtime_comparison.png): the previous single-network uniform calibration also used 24 workers and completed its simulation schedule in approximately four hours. New planned total simulation steps are 132.72 million versus 16.4 million (8.09x), before resource retries. Among 252 successful matched HK-shuffled parameter/seed pairs with identical Java source hashes, excluding resource retries, doubling 20k to 40k steps gives median runtime ratio 1.85 and p90 2.21. This does not support a general runtime collapse from the current total concurrency, although it is not a controlled comparison of worker counts and omits the censored expensive tail.

At 12:44 JST, the host had 28 GB unused RAM, zero swap/compression/pageouts, approximately 80% CPU use, and no reported thermal/performance throttling. The ordinary standard runner defaults to 12 workers, whereas both compared calibrations use 24 total. The audit separates simulator-wall time (log/config timestamps) from manager-recorded elapsed time: some adopted BO jobs had already finished long before the manager collected their result, inflating metadata `seconds`. Future progress estimates should use the simulator-wall proxy, budget, remaining phases, and resource-retry state rather than that inflated duration alone. No running model, scientific outcomes, or concurrency limits were changed by this audit.

## Network and strategy diagnostics (2026-10-29)

Generated a [mechanism report](fit-mechanisms-2026-10-29/report.md), network PNG/GraphML snapshots, final-Q and realized-action proportions, exact parameter/baseline comparison, and exploratory parameter importance. Select the current strongest complete valid five-seed original-post profile in HK-shuffled (a diagnostic, not a changed optimization target); select the lowest seed 271000 for visualization without choosing a visually attractive realization. Initial opinion-sign Q≈−0.003 changes to final-follow Q≈0.425 and root-repost Q≈0.400 in that seed. Initial and final follow networks each have 46,000 directed ties; final-10k root repost network has 74,054 ties and 92,390 events. Initial layout is based on initial topology; final follow/repost share a final-topology layout; opinions determine color only.

Five-seed final greedy preferences from the actual bandit state0: Post1.40%, Like98.50%, Repost0.04%, Rewire0.06%. Final10k action-choice shares: Post5.04%, Like87.94%, Repost3.51%, Rewire3.51%. Dominant observed actions are stable across the final two5k windows, but this is not proof of Q-value/network convergence. Ongoing epsilon=0.1385 exploration gives about3.46% per action when all four are available, close to observed repost/rewire shares. Use state0 Q tables: the generic agent snapshot averages unvisited states and is inappropriate for this preference calculation.

Exploratory importance uses only complete valid initial Sobol settings (98 HK,92 random,92 DC-SBM), excluding manual anchors and adaptive BO points. Four-fold held-out forests predict log1p five-seed component losses. Network-loss predictive skill vs constant is0.52–0.62 and beta_h dominates held-out permutation importance across all three families. Original-post-loss predictive skill is−0.05 to0.07: its importance ranking is not reliable evidence for how to produce the missing inner trough. Marginal beta_h/q_tau associations recur, with family-dependent signals in reward balance, access, density and FY sharpness. These are exploratory associations, not causal effects; no local ablations were run. Event/action totals and graph counts were cross-checked against calibration logs; no live simulator or scientific scoring was changed.
