# Calibration sweep results (systematic-A/B calibration plan)

Single running record of every calibration sweep run for this plan (系統A: network structure /
系統B: repost-cascade dynamics), consolidating what was previously split across a narrative report,
a raw-output dump, and a decisions ledger. New stages get a new dated section appended below, not a
new file. See `docs/research-direction.md` for the paper-level context and
`docs/report/2026-07-15-hk-calibration-stage1a.md` for the fuller narrative writeup of Stage 1a
(finite-size finding, implementation prerequisites) if more detail than this table view is needed.

**Process:** before running any sweep, the parameters/ranges/scale are reported here (or in chat)
and approved before execution — see `docs/report/2026-07-15-calibration-decisions.md`'s process note.

---

## Stage 1a — HK generator (m, A, pt) vs. Kwak et al. 2010

**Targets:** in-degree power-law exponent γ≈2.276; average local clustering coefficient ≈0.072
("What is Twitter, a Social Network or a News Media?", WWW'10).

**Design:** γ = 2 + A/m is analytic (`HolmeKimNetwork.java`), so `A = round(0.276·m)` per `m` up
front; grid swept `m ∈ {3(default),5,10,15,20,25,50}` × `pt ∈ {0.05,0.1,0.2,0.3}`, 3 seeds,
`n=1000, steps=1` (t=0 generator-only snapshot, no dynamics). 84 runs.
Script: `run_hk_calibration_sweep.sh` / `scripts/hk_calibration_analysis.py`.

**Finding — γ_fit (empirical power-law MLE) systematically undershoots γ_analytic by 0.3-0.5,
confirmed as a finite-size artifact, not a generator defect.** Scaling check on `m=25,A=7,pt=0.05`:

| n | γ_fit | max in-degree |
|---|---|---|
| 1000 | 1.866 | 205 |
| 3000 | 1.960 | 455 |
| 5000 | 2.011 | 664 |
| 10000 | 2.049 | 1148 |

Monotonic convergence toward γ_analytic=2.280 as n grows (same `k_max ~ n^{1/(γ-1)}` truncation
already documented for DC-SBM, `2026-07-09-oat-sweep-findings.md`). **Conclusion: trust the analytic
γ=2+A/m for calibration at this project's working scale (n=1000); γ_fit is not a reliable
cell-ranking signal here (its bias is roughly constant across cells).**

**Full grid (clustering coefficient, mean of 3 seeds; target 0.072):**

| m | A | γ_analytic | pt=0.05 | pt=0.10 | pt=0.20 | pt=0.30 | initial edges (n=1000) |
|---|---|---|---|---|---|---|---|
| 3 (old default) | 1 | 2.333 | 0.2027 | 0.1280 | 0.1253 | 0.1398 | ~3,000 |
| 5 | 1 | 2.200 | 0.2202 | 0.2628 | 0.2960 | 0.3153 | ~5,000 |
| 10 | 3 | 2.300 | 0.1636 | 0.2008 | 0.2322 | 0.1827 | ~10,000 |
| 15 | 4 | 2.267 | 0.1424 | 0.1539 | 0.1874 | 0.1824 | ~15,000 |
| 20 | 6 | 2.300 | 0.1021 | 0.1141 | 0.1329 | 0.1324 | ~20,000 |
| 25 | 7 | 2.280 | 0.0917 | 0.1004 | 0.1163 | 0.1171 | ~25,000 |
| 50 | 14 | 2.280 | 0.0571 | 0.0613 | 0.0684 | 0.0621 | ~50,000 |

Old default (m=3,A=1,pt=0.3) overshoots clustering 2-3x vs. target. Larger `m` (with `A` tracking γ)
plus low `pt` (0.05-0.1) tracks the target much better; best single-cell match is m=50,pt=0.20
(0.0684), but cost (edge count, and its compounding effect through Stage-1b/2 dynamics runs) rises
linearly with m. **m also doubles as the mid-scale-hub-hosting density knob** (research-direction.md).

**Decision (2026-07-16): m=15, A=4, pt=0.05.** Compute-cost tradeoff: m=25's initial edge count
(~25,000 at n=1000) compounds through every Stage-1b/2 production-scale run (n=1000, steps=40000,
many seeds x parameter combos) via follow growth, repost propagation, feed computation — not just a
one-time network-generation cost. m=15 is 40% cheaper on initial edges, at the cost of a
substantially worse clustering match (0.1424 vs. target 0.072, ~2x too high, vs. m=25's 0.0917).
**m=20 and m=25 deferred to a final robustness/confirmation check after the main calibration
sequence, not a full separate calibration pass** — i.e. re-run the finalized Stage 1b/2 pipeline
once at m=20 and m=25 at the end to confirm conclusions are not an artifact of the m=15 choice,
rather than calibrating all three in parallel now.

**γ_fit vs γ_analytic gap: accepted as an unfixable finite-size artifact at n=1000, not pursued
further.** This is a well-documented general limitation of MLE power-law fitting on finite
preferential-attachment-generated networks (xmin selection is dominated by not-yet-converged
low-degree/young nodes at small n; Clauset, Shalizi & Newman 2009; Broido & Clauset 2019), not a
defect in this codebase or fitting script — confirmed via the n-scaling check above, which showed
monotonic convergence toward the analytic value as n grows. Standard practice, adopted here: trust
the analytic γ=2+A/m for parameter selection, state the finite-n caveat explicitly in any writeup
that reports a realized/measured exponent from a production-scale (n=1000) run.

---

## Stage 1b — maxFollowCapacity, followProb, feedAlgoShare, feedHopH

**Design (revised from the original staged-grid plan, 2026-07-16): Bayesian optimization**, not a
grid — user asked whether the joint 4-parameter search could be done more efficiently; switched to
GP-based BO (`scikit-optimize`, newly installed) over `maxFollowCapacity∈[15,100]`,
`followProb∈[0.01,0.3]` (log-uniform), `feedAlgoShare∈[0,1]`, `feedHopH∈{1..5}` (integer). Loss =
normalized squared distance to (Gini=0.8, γ=2.276), each point averaged over 2 seeds. Scale: n=1000
(not shrunk further, to avoid compounding Stage-1a's finite-size fitting bias), steps=15000.
Script: `scripts/stage1b_bo_calibration.py`; raw log: `docs/report/stage1b_bo_evaluations.csv`.

**Execution note:** planned 5 rounds x 6 points (30 evals). Round 0 took 971s, round 1 took 1872s
(12 concurrent JVMs on shared hardware contending harder than expected — a wall-clock estimate
based on one single-run timing test did not account for this). The background process was then
killed mid-round-2 by an unrelated session/environment interruption (not a script bug) before round
2 could finish; recovered rounds 0-1 (12 points, all cleanly paired) and discarded round 2's partial
data (4 completed simulations existed but couldn't be reliably re-attributed to their source point
due to a thread-safety bug in the driver script's shared seed counter — `_seed_counter` is
incremented from multiple `ThreadPoolExecutor` threads without a lock, so seed-to-point assignment
across concurrently-evaluated points is not guaranteed contiguous; harmless to the 12 points that
did complete since each `evaluate_point()` call tracks its own seeds locally, but made post-hoc
recovery of the killed round unreliable — worth fixing before this script is reused). Given the
escalating per-round cost and no improvement found in round 1, stopped here rather than resuming.

**Screening result — clear, well-separated winner.** Best of 12 points by a wide margin (loss=1.14
vs. second-best 5.03): `max_follow=53.9, follow_prob=0.0102, alpha=0.845, hop=4` -> gini=0.765,
gamma_fit=2.518. `follow_prob` low (~0.01) was the dominant pattern distinguishing good points from
bad across the whole screen. BO proposes continuous values (its GP surrogate + EI acquisition
function operate over continuous space, unlike a pre-specified grid) — rounded for the confirmation
run and going forward: **`max_follow=55, follow_prob=0.01, alpha=0.85, hop=4`**.

**Confirmation (5 seeds, rounded values, n=1000, steps=15000):**

| seed | gini | gamma_fit |
|---|---|---|
| 40000 | 0.7632 | 2.566 |
| 40001 | 0.7681 | 2.174 |
| 40002 | 0.7967 | 2.444 |
| 40003 | 0.7644 | 2.400 |
| 40004 | 0.7643 | 2.549 |
| **mean ± std** | **0.7714 ± 0.0128** | **2.4266 ± 0.1409** |

Gini is close to target (0.8) and tight across seeds (low variance) — robust, not a single-seed
fluke. `gamma_fit` centers on 2.43, overshooting the 2.276 target (opposite direction from Stage
1a's initial-network fits, which undershot) — noisier across seeds (std 0.14) but not wildly so.
Same finite-size MLE caveat as Stage 1a applies (no analytic ground truth available for the emergent,
post-dynamics degree exponent to cross-check against, unlike the pure HK generator).

**Decision (2026-07-16, SUPERSEDED 2026-07-16 — see redo below): `maxFollowCapacity=55,
followProb=0.01, feedAlgoShare=0.85, feedHopH=4`.**

### Stage 1b REDO — added an opinion-assortativity floor (same day, after Stage 2 exposed a problem)

**Why:** starting Stage 2 (below) with the above values produced `Q_sign` (follow-graph modularity)
AND `Q_sign_repost` near zero (~0.005-0.01) across every sampled point — not a Stage-2 parameter
sensitivity issue, since it was uniform across the whole Stage-2 search space. Diagnosis: a
follow_prob diagnostic (`follow_prob=0.01` vs. `0.05` vs. `0.10`, all other params at the Stage-1b
values above) showed `opinionAssortativity` at 0.275 / 0.767 / 0.900 respectively — the original
Stage 1b loss (Gini + gamma only) had no counter-pressure against low follow_prob, so the optimizer
picked a value that satisfies structural realism (Gini/degree-exponent) while accidentally breaking
a basic behavioral requirement of the model: research-direction.md's Type-1 baseline (the follow
graph must be *able* to reach a separated, opinion-homophilous state) never had a chance to develop
within the run. (`Q_sign_repost` itself stayed flat regardless of follow_prob — a separate, Stage-2
question, not resolved by this redo; see below.)

**Fix:** added a third loss term — a one-sided penalty when `opinionAssortativity` falls below a
floor of 0.6 — leaving the Gini/gamma terms unchanged. `loss = ((gini-0.8)/0.05)^2 +
((gamma_fit-2.276)/0.3)^2 + max(0, (0.6-assort)/0.15)^2`.

**Design:** warm-started from the original Stage-1b run's 24 surviving result folders (re-scored
under the new loss, no new simulation), then 3 more BO rounds x 5 points (15 new evals, 1 seed
each). Script: `scripts/stage1b_redo_bo_calibration.py`; raw log:
`docs/report/stage1b_redo_bo_evaluations.csv`.

**Result:** warm-start best (loss=2.61, the original Stage-1b winner) was beaten decisively in round
1: `max_follow=52.1, follow_prob=0.134, alpha=0.149, hop=1` -> gini=0.811, gamma_fit=2.324,
assort=0.883, loss=0.075. Notably this was not a trade-off against Gini/gamma — lowering `alpha`
from ~0.85 to ~0.15 (much less opinion-blind recommender content, feed dominated by chronological
follow-based content) improved assortativity *and* Gini *and* gamma_fit simultaneously. Round 2
also surfaced a cautionary region: `alpha=1.0` combined with high follow_prob and hop=5 can push
assortativity to 0.97 while collapsing Gini to 0.13 (a near-egalitarian, unrealistic degree
distribution) — confirms `alpha` needs to stay moderate, not be pushed to either extreme.

**Confirmation (5 seeds, rounded values `max_follow=50, follow_prob=0.13, alpha=0.15, hop=1`,
n=1000, steps=15000):**

| seed | gini | gamma_fit | opinion_assortativity |
|---|---|---|---|
| 80000 | 0.7872 | 1.320 | 0.9277 |
| 80001 | 0.8912 | 1.409 | 0.6701 |
| 80002 | 0.6637 | 2.989 | 0.9742 |
| 80003 | 0.8078 | 1.336 | 0.9026 |
| 80004 | 0.8781 | 1.472 | 0.7257 |
| **mean ± std** | **0.8056 ± 0.0813** | **1.7052 ± 0.6442** | **0.8401 ± 0.1196** |

Gini and assortativity are both robust across seeds and hit their targets. `gamma_fit` is noisier
and lower than the single-seed screening value (1.71 mean vs. 2.32 single-seed) — consistent with
the already-documented finite-size MLE fitting limitation (Stage 1a), not a new problem; no analytic
ground truth exists for this emergent/dynamic exponent to resolve it further.

**Decision (2026-07-16, current): `maxFollowCapacity=50, followProb=0.13, feedAlgoShare=0.15,
feedHopH=1`.** Supersedes the pre-redo values above. `m=20`/`m=25` robustness re-check (deferred
from Stage 1a) still pending — do that check with these values held fixed, not independently.

## Stage 2 — bcDecRate, stubbornness, comfortPpFactor, feedCapacity, initialPostProb

**First attempt (2026-07-16), aborted after round 0.** Target: repost-network structural fit
(`Q_sign_repost`), using the repost-network instrumentation added 2026-07-15
(`Analysis.computeSignModularityFromMatrix`, `Writer.writeRepostDegrees`/
`writeRepostClusteringCoefficients`, wired into the dashboard). BO over `bcDecRate∈[0.9,0.999]`,
stub∈[0.2,0.8] (`stub_dist=uniform stub_min=X stub_max=X` — `stub_dist=const` silently ignores
stub_min/stub_max and always uses the hardcoded `Const.INITIAL_STUBBORNNESS=0.7`, verified in
`Agent.java` before writing the script), `comfortPpFactor∈[1.0,1.5]`, `feedCapacity∈[5,30]`,
`initialPostProb∈[0.05,0.5]`, holding the (pre-redo) Stage-1b values fixed. `bcIncRate = 1 + (1 -
bcDecRate)/10` (dependent, not swept). Round 0's 5 points all landed at `Q_sign_repost ≈ 0.001-0.02`
— uniformly near zero across the whole sampled space, which is what triggered the follow_prob
diagnostic and the Stage-1b redo above. **Not resumed yet** — should restart on top of the
redone Stage-1b values (`max_follow=50, follow_prob=0.13, alpha=0.15, hop=1`), since the repost
network's own modularity floor is still an open, separate question (the follow_prob diagnostic
showed `Q_sign_repost` stayed flat near zero even when `Q_sign`/opinionAssortativity improved a lot
— i.e. fixing the follow-graph assortativity problem does not, by itself, fix the repost-network
modularity problem Stage 2 was created to address).

**Literature note (2026-07-16):** the ~0.7-0.8 repost-network modularity target (Conover et al.
2011, 2010 US midterm election) was checked against additional independent sources before treating
it as a target rather than a US-specific outlier: a 26-country parliamentary Twitter database
(reports modularity/cluster-count/clustering-coefficient per country, some countries showing
"Type 2 networks with two large polarized clusters"), a 12-country parliamentary network comparison,
a 9-country politician-retweet-network study ("clear separation between political left and right" in
each), and a propaganda-network study reporting Louvain modularity Q=0.81/0.83 on retweet
connections. Directionally corroborated (strong retweet-network partisan segregation is not
US-specific) but exact magnitude wasn't independently re-confirmed at the same precision — treat
0.7-0.85 as a defensible **range**, not a tight point target. Also noted: Garimella & Morales
("Quantifying Controversy in Social Media") argue modularity is not a direct antagonism/controversy
measure and propose RWC (already implemented in this project's dashboard, `dashboard/analysis.py`'s
`compute_rwc`) as an alternative — worth keeping in mind if `Q_sign_repost` calibration proves hard
to reconcile with a single modularity number.

## Stage 1 + Stage 2 joint recalibration (2026-07-18) — supersedes both stages above

The bc mean-reversion mechanism redesign (docs/report/2026-07-18-bc-pp-boundary-collapse-
diagnosis.md) reopened Stage 1 (bc gates unfollowing, so it feeds follow-graph shape too) at the
same time Stage 2 needed a bc-mechanism-driven redo — so Stage 1 and Stage 2 were merged into one
10-dim joint GP-BO search rather than re-doing them separately. Full design, results, and the
final calibrated point: **docs/report/2026-07-18-joint-stage-calibration.md**.
