# 2026-07-31 — WSSIT2026-era vs current model: diff + reproduced-dynamics comparison

## Context / motivation

Direction shift (this date): re-anchor on the WSSIT2026 moderate-conduit finding before
extending the algorithm work further. First step: establish concretely how the current model
differs from the model that actually produced the WSSIT2026 submission, since ~5 weeks of
R1-R25 revisions + v11-v15 calibration happened in between (`docs/research-direction.md`,
commit `47feecf`, 2026-06-23) and it was not obvious how much of that is reparametrization vs.
mechanism change.

No `../Dev-wssit2026` directory or Feb-2026 branch exists on disk. The reference point used
instead: commit `870b318` ("config-driven intervention harness for moderate-influencer /
repost-hub study", 2026-06-19), the last commit before `47feecf` introduced
`research-direction.md` and the Type-1/Type-2 pivot. `870b318`'s `ExperimentConfig` is the
Exp-A/Exp-B channel-isolation harness for the moderate-influencer/repost-hub study — i.e. the
actual WSSIT2026 model.

## Static diff, `870b318` → current HEAD

- **Network topology**: Holme-Kim params `m` 3→15, `a` 1→4, `pt` 0.3→0.05. Current default
  network has ~5x the out-degree and a much lower triad-formation probability. Same generator
  family, very different graph.
- **Feed mechanism**: didn't exist in the WSSIT-era model (100% chronological follow-graph
  feed). Current default `feedAlgoShare (alpha) = 0.7` — a global velocity-ranked "For-You"
  recommender supplies 70% of the feed. `alpha=0` collapses this back to the legacy
  chronological feed (`AdminOptim.java:387`).
- **Follow rule itself is unchanged**: both eras gate follow candidates identically —
  `|postOpinion - opinion| < bc`. What moved is the parameters/mechanism feeding it:
  - `followProb` 0.1 → 0.01, `maxFollowCapacity` 10 → 43.86, `repostProb` 0.25 → 0.1.
  - bc dynamics: WSSIT-era used flat multiplicative decay (`BC_DEC_RATE=0.99`, init bc=1.0,
    floor 0.2). Current model replaced this with a graded ratchet (`bcInit=0.8`,
    `bcDecRate=0.5` — pinned at the hard ceiling, i.e. zero inertia — `bcRecoveryRate=0.0001`,
    floor/ceiling 0.2/1.0). This is a mechanism change, not a reparametrization.
- **New mechanisms with no WSSIT-era counterpart**: relay distortion (off by default,
  `relayEnabled=false`, so neutral here); empirical 7-bin initial-opinion option (default still
  `"gaussian"`, but `initOpinionClip` default flipped to truncated-resampling vs WSSIT's hard
  clip — minor).
- **Experiment framing**: WSSIT-era `ExperimentConfig` (Exp A channel isolation / Exp B
  number×size, fixed top-K moderate-hub pool) vs. current conduit/SF1 framework. Both still
  share the `extreme`/`nModerate` fields; current default is `extreme=NONE, nModerate=0` (no
  intervention) vs. WSSIT-era's own default `extreme=SYM, nModerate=1` (intervention active) —
  matters for reproduction below.

## Reproduction methodology

`git worktree add` at `870b318` (isolated checkout + build, no changes to the current working
tree). Both eras run at **their own native defaults** except `extreme=none n_mod=0` forced on
both (so the comparison isolates baseline network/opinion dynamics from the intervention
harness, which differs in shape between eras and isn't the object of this comparison). Both
default to `n=1000`, `steps=40000` already — no step-count patch needed, defaults happen to
match. 5 seeds per era (WSSIT-era: 0-4; current: 100-104, chosen only to avoid colliding with
an unrelated pre-existing `results/run_0..4` directory from earlier same-day work).

Metrics computed with formulas transcribed line-for-line from `Analysis.java`
(`computeOpinionAssortativity`, `computeInteractionAssortativity`, `computeCrossCuttingFraction`,
the sign-modularity `Q` formula, and the directed clustering-coefficient formula from
`computeClusteringCoefficients`) reimplemented in Python/networkx over the exported GEXF
snapshots at step 40000, so both eras are scored under one metric definition rather than two
independently-coded ones that could silently diverge. Script:
`scripts/wssit_era_vs_current_comparison.py`. The WSSIT-era run itself lives in a disposable
`git worktree` (not checked into this repo) at commit `870b318`; regenerate it with
`git worktree add <dir> 870b318` + compile + run with `extreme=none n_mod=0` before rerunning
this script.

## Results (mean ± std over 5 seeds, final step=40000 snapshot)

| metric | WSSIT-era (870b318) follow | current follow | WSSIT-era repost | current repost |
|---|---|---|---|---|
| edges | 5065 ± 925 | 23518 ± 1031 | 5232 ± 976 | 21415 ± 1561 |
| mean out-degree | 5.07 ± 0.92 | 23.52 ± 1.03 | 5.23 ± 0.98 | 21.41 ± 1.56 |
| clustering (Java formula) | 0.436 ± 0.049 | 0.297 ± 0.033 | 0.437 ± 0.048 | 0.317 ± 0.041 |
| opinion assortativity | 0.490 ± 0.185 | 0.484 ± 0.061 | **0.394 ± 0.249** | **0.735 ± 0.028** |
| cross-cutting fraction | 0.182 ± 0.098 | 0.248 ± 0.038 | 0.196 ± 0.104 | 0.208 ± 0.027 |
| sign modularity Q | 0.280 ± 0.114 | 0.240 ± 0.033 | 0.267 ± 0.117 | 0.277 ± 0.022 |

## Interpretation

1. **Follow-graph opinion assortativity did not move** (0.49 vs 0.48) — within noise. But the
   WSSIT-era estimate is barely usable at 5 seeds (std ≈ mean, sparser network gives a much
   noisier correlation estimate); would need more seeds to say anything sharper about the past
   model's follow-graph behavior specifically.
2. **Repost-network opinion assortativity roughly doubled (0.39 → 0.74) and got far more stable
   across seeds (std 0.25 → 0.03).** This is the one gap in this comparison that is clearly not
   noise. It isn't a new "hostile repost" channel diluting homophily — WSSIT-era repost was
   already 100% bc-gated, identical to now. The likely driver is the bc-dynamics mechanism swap:
   WSSIT-era's slow flat decay from bc=1.0 left agents broadly tolerant for much of a 40k-step
   run, while the current ratchet (zero-inertia `bcDecRate=0.5` from `bcInit=0.8`) narrows
   tolerance much harder and faster, which surfaces structurally as much tighter, more
   consistent in-camp relay behavior.
3. **Clustering coefficient is larger in the past on both networks** (0.44 vs ~0.30-0.32),
   confirming the suspicion going into this check. But neither era is close to the Kwak et al.
   2010 empirical target already referenced in the HK-generator comment (clustering ≈ 0.072) —
   both inflate 4-6x over the run via homophilous follow/unfollow dynamics, regardless of the
   generator's own `pt` knob. Current is *closer* to realistic (0.30 vs 0.44) despite `pt`
   itself moving further from its generator-level target (0.3 → 0.05), because the post-dynamics
   number is dominated by rewiring, not the initial graph structure.

## Candidate calibration-objective implications (for discussion, not yet decided)

- Repost-network opinion assortativity is a real, mechanism-driven divergence between eras and
  arguably deserves an explicit calibration target/band going forward, grounded in what's
  empirically plausible for relay/retweet homophily (cf. Conover et al. 2011-style
  retweet-network segregation numbers already used elsewhere in this codebase's assortativity
  comments) — not just left to fall out of whatever the bc ratchet parameters happen to produce.
- Clustering coefficient of the **evolved** (post-dynamics) network, not just the initial
  generator's `pt`, should probably become a tracked/calibrated quantity against the Kwak et al.
  2010 ≈0.072 target, since both eras miss it badly and the gap is large enough to matter for
  any "is this a realistic social network" claim in the paper.
- Follow-graph-level metrics need more seeds before drawing conclusions about the past model
  specifically — the sparse-network noise floor is high there.

## Additional metrics (second pass, same 5-seed runs, no new simulation)

Computed from the same GEXF snapshots already generated above, extending beyond the first
pass's structural/opinion-assortativity metrics. Formulas transcribed from
`Analysis.java` (`computeBimodalityCoefficient`, `computeOpinionKurtosis`,
`computeMeanTolerance`/`computeToleranceVar`, `computeBcExtremityCorrelation`) and from this
project's calibration scripts' `gini()` (e.g. `scripts/app_pol_baseline_bo_v13_graded_bc.py`),
so the in-degree Gini here is on the same footing as the project's usual calibration-loss
metric. Script: `scripts/wssit_era_vs_current_extra_metrics.py`. Note: bimodality, kurtosis,
mean tolerance, tolerance variance, and bc-extremity correlation are agent/node-level quantities
(opinion, bc), so they're identical whether read off the follow-network or repost-network GEXF
at the same step — not a bug, just means those five rows don't have separate follow/repost
values.

| metric | WSSIT-era follow | current follow | WSSIT-era repost | current repost |
|---|---|---|---|---|
| in-degree Gini | 0.962 ± 0.003 | 0.900 ± 0.005 | 0.962 ± 0.003 | 0.944 ± 0.002 |
| bimodality coeff (Sarle's b) | 0.450 ± 0.042 | 0.426 ± 0.033 | (same) | (same) |
| opinion excess kurtosis | -0.760 ± 0.200 | -0.631 ± 0.195 | (same) | (same) |
| mean tolerance (bc) | 0.778 ± 0.073 | 0.737 ± 0.018 | (same) | (same) |
| tolerance variance | 0.068 ± 0.009 | 0.034 ± 0.005 | (same) | (same) |
| bc-extremity correlation | **-0.469 ± 0.289** | **-0.826 ± 0.031** | (same) | (same) |
| reciprocity | 0.0018 ± 0.0005 | 0.0055 ± 0.0017 | 0.0017 ± 0.0005 | 0.0056 ± 0.0017 |
| largest weakly-connected-component fraction | **0.939 ± 0.012** | **0.999 ± 0.001** | 0.939 ± 0.012 | 0.998 ± 0.001 |
| structural (degree-degree) assortativity | 0.039 ± 0.008 | 0.066 ± 0.017 | 0.035 ± 0.008 | 0.044 ± 0.018 |

### Interpretation

- **Follow-network hub concentration is real and large: in-degree Gini 0.962 (past) vs 0.900
  (current)**, tight std on both sides. The past model concentrates followers into a starker
  winner-take-most hub structure (top node in-degree ~757/999 in a network with mean in-degree
  ~5, i.e. one node followed by ~76% of the population) than the current model (top ~10 nodes
  all clustered near 700-766 — a "plateau" of near-saturated hubs rather than one dominant
  winner). Repost-network Gini shows the same direction, smaller gap (0.962 vs 0.944).
- **bc-extremity correlation is the sharpest, most reliable gap found in this whole
  comparison**: -0.47 (past, std 0.29 — one seed even flipped sign to +0.09) vs -0.83 (current,
  std 0.03 — essentially pinned near ceiling). The asymmetric-tolerance-by-extremity mechanism
  (extremists hold tighter bc than moderates) is present but weak/unreliable in the WSSIT-era
  model and strong/highly consistent in the current model. This lines up with the bc-mechanism
  redesign already flagged above (flat 0.99/step decay from bc=1.0 vs. the current zero-inertia
  ratchet) — the newer mechanism doesn't just narrow tolerance faster on average, it makes the
  *extremity-dependence* of that narrowing far more deterministic.
- **Network connectivity is qualitatively different**: past model's follow-graph leaves ~6% of
  agents outside the giant weakly-connected component after 40k steps (0.939 mean); current
  model's is essentially fully connected (0.999). Isolated nodes can't be exposed to
  cross-cutting content at all, which matters for any claim about network-mediated exposure.
- Bimodality, kurtosis, reciprocity, and structural (degree-based, as opposed to opinion-based)
  assortativity show differences that are small relative to their seed-to-seed spread — treat
  as inconclusive at n=5, not as evidence of a mechanism-level gap, unless revisited with more
  seeds.

## Structural coefficients (third pass): path length, transitivity, weighted repost-Q, degree assortativity

Script: `scripts/wssit_era_vs_current_structural_coeffs.py`. Two corrections/additions over the
first two passes:

1. **The first pass's repost-network `modularity` was wrong** -- it used the unweighted
   sign-modularity formula, which matches `Analysis.java`'s `computeSignModularity` for the
   *follow* graph (correct, unweighted there) but not `computeSignModularityFromMatrix`, which
   the codebase uses for the *repost* graph specifically because it's weighted by repost count
   (see that function's 2026-07-15 comment: repost count, not mere presence, is the right
   weighting for a retweet-style network). Fixed here; the corrected value for current-model
   seed 100 (0.325) now matches that run's own instrumented `Q_sign_repost` column
   (`metrics/modularity.csv`) exactly, which is a useful independent check that the whole
   GEXF-parsing pipeline is reading the right network.
2. New: average shortest path length + diameter (undirected, largest connected component --
   undefined otherwise), global transitivity (triangle/connected-triple ratio -- a different
   definition of "clustering" than the per-node average reported in the first pass), and
   networkx's standard `degree_assortativity_coefficient` as a credibility check on the first
   extra-metrics pass's ad hoc `structural_assortativity` (which turns out not to have been a
   reliable measure -- see below).

| metric | WSSIT-era follow | current follow | WSSIT-era repost | current repost |
|---|---|---|---|---|
| weighted sign modularity Q | 0.280 ± 0.114 | 0.240 ± 0.033 | 0.260 ± 0.141 | 0.338 ± 0.044 |
| avg shortest path (giant component) | 2.329 ± 0.228 | 2.106 ± 0.016 | 2.318 ± 0.227 | 2.137 ± 0.019 |
| diameter (giant component) | 6.2 ± 0.4 | 4.2 ± 0.4 | 6.2 ± 0.4 | 4.8 ± 0.7 |
| global transitivity | **0.031 ± 0.001** | **0.099 ± 0.008** | 0.032 ± 0.001 | 0.079 ± 0.008 |
| degree assortativity (nx, standard) | **-0.281 ± 0.023** | **+0.066 ± 0.014** | -0.295 ± 0.018 | +0.108 ± 0.026 |

### Interpretation

- **Global transitivity contradicts the first pass's clustering-coefficient direction, and this
  matters.** First pass (this project's own directed-neighborhood formula, averaged per-node):
  past > current (0.44 vs 0.30). This pass (standard triangle/connected-triple ratio, a
  network-wide count, not a per-node average): **current > past** (0.08-0.10 vs 0.03). Both are
  computed correctly; they disagree because they weight nodes differently. The past model's
  extreme hub concentration (in-degree Gini 0.96, one node followed by ~76% of the population)
  means a handful of hub nodes contribute enormous numbers of *open* triples (pairs of the hub's
  many followers, most of whom don't follow each other) that drag the triangle-based ratio down,
  while the simple average-of-per-node-coefficients treats every peripheral low-degree node's
  (often trivially high) local coefficient as equally important. **Practical takeaway: "is
  clustering larger in the past" does not have a single answer -- it depends which of these two
  standard definitions is the one that matters for whatever empirical target this ends up being
  calibrated against (e.g. Kwak et al. 2010's ~0.072 figure needs to be checked against its own
  definition before picking a side).**
- **Degree assortativity flips sign, cleanly and with tight seeds-to-seed variance**: past model
  is disassortative (-0.28 to -0.30, the classic scale-free hub-and-spoke signature: a few giant
  hubs connect mostly to small nodes) while the current model is weakly *assortative* (+0.07 to
  +0.11: higher-degree nodes somewhat prefer each other). This is consistent with, and helps
  explain, the earlier Gini finding: the past model's degree distribution has one dominant
  winner (which structurally can't be assortative with anything, there's only one of it), while
  the current model's "plateau" of ~10 near-saturated hubs gives those hubs room to preferentially
  connect to one another. This also retroactively flags the first extra-metrics pass's ad hoc
  `structural_assortativity` (simple Pearson correlation of raw degree over edges, both near
  zero and same-signed for both eras) as **not a reliable measure** -- the standard nx
  formulation, which normalizes properly for directed degree correlation, is the one to trust
  going forward.
- **Path length / diameter differences are modest and largely a mechanical consequence of
  density** (current network has ~4-5x the edges), not a separately interesting structural
  claim on their own.
- **Repost weighted-Q is suggestive (0.26 vs 0.34) but not reliably distinguishable at n=5** --
  the past-era estimate's own seed-to-seed spread (std 0.141, one seed as low as 0.035) is larger
  than the gap between the two means.

## Follower-count distribution: CCDF + top-k concentration shares (fourth pass, 2026-08-01)

Script: `scripts/wssit_era_vs_current_followdist.py`. Quantifies the "single dominant hub vs.
plateau of ~10 near-saturated hubs" shape difference already visible in the raw
top-10-in-degree lists (§ static diff reproduction) directly, as a CCDF and as top-1%/5%/10%
and max-single-hub shares of total followers. Follow-network in-degree from
`degrees/degree_result_40000.csv` (both eras); repost-network in-degree from
`degrees/repost_degree_result_40000.csv` (current) / computed from the exported repost GEXF's
in-degree (WSSIT-era, no such CSV exists for that era).

![Follower-count CCDF, WSSIT-era vs current, follow network, pooled 5 seeds](2026-08-01-followdist-ccdf.png)

| metric (share of total followers) | WSSIT-era follow | current follow | WSSIT-era repost | current repost |
|---|---|---|---|---|
| top 1% of users | **72.8% ± 2.5%** | **31.4% ± 2.2%** | 72.4% ± 2.3% | 34.7% ± 3.3% |
| top 5% of users | 89.6% ± 1.3% | 79.9% ± 1.1% | 89.7% ± 1.3% | 89.9% ± 0.8% |
| top 10% of users | 94.7% ± 0.6% | 87.5% ± 0.9% | 94.7% ± 0.7% | 94.9% ± 0.4% |
| single largest hub | **14.2% ± 0.5%** | **3.3% ± 0.2%** | 13.9% ± 0.6% | 3.6% ± 0.4% |

### Interpretation

- **This is the cleanest, most interpretable number in the whole comparison.** In the WSSIT-era
  model, the single largest hub alone holds **14.2%** of every follow-edge in the network; the
  top 1% of users (10 of 1000 agents) hold **73%** of them. In the current model those numbers
  are 3.3% and 31% respectively — concentration is real in both, but the past model puts nearly
  a quarter of the entire population's attention-budget on ONE node, where the current model
  spreads a comparable total dominance across roughly ten nodes clustered near the same ceiling
  (visible as the "shelf" in the CCDF just before the tail, rather than WSSIT-era's single sharp
  drop). Std is tight (2-3pp) on every row, so this is not a seed-noise artifact.
- **Repost-network concentration is essentially the same shape as follow-network concentration
  in both eras** (top-1% and max-hub shares track within a couple points of the follow-network
  numbers) -- unsurprising since who gets relayed correlates strongly with who gets followed,
  but worth having confirmed rather than assumed.
- This sharpens (rather than just re-states) the earlier in-degree Gini finding (0.962 vs
  0.900): Gini alone doesn't distinguish "one giant winner" from "ten roughly-equal winners" --
  the top-k shares and the CCDF's shelf do.
- If a follower-count concentration target from empirical social-media data (e.g. an
  empirical top-1%-share or max-account-share figure) is ever adopted as a calibration
  objective, this is the number to calibrate against, not Gini alone -- Gini can look similar
  while the underlying shape (single-winner vs. multi-winner plateau) is qualitatively
  different, which matters for any claim about a specific "the/a moderate hub" being causally
  identifiable and singular versus one of several comparably-sized candidates.

## Activity-filtered repost-Q (fifth pass, 2026-08-01): testing the Conover filter-bias hypothesis

Follow-up on the discussion below (§ Synthesis): the user flagged that Conover et al. 2011's
~0.7-0.8 retweet-network modularity figure is inflated by their methodology excluding
low-activity/infrequent posters (who disproportionately bridge camps), making the earlier
"current repost Q=0.34 is too low vs. 0.7-0.8" framing potentially overstated. Tested directly.
Script: `scripts/wssit_era_vs_current_activity_filtered_q.py`. Current HEAD only -- WSSIT-era
has no per-agent post/repost authorship records (`posts/post_result_*.csv` there is aggregate
bin counts only, not per-agent), so this test isn't reproducible on that era's output.

Method: reconstructed the full-run cumulative repost network directly from
`posts/repost_cascades.csv`'s per-event log (every relay over all 40000 steps -- closer to
Conover's whole-observation-window scope than the 5000-step windowed snapshot used in the third
pass). "Activity" = total original posts (`posts/post_lifespan.csv` `author` column) + total
reposts made (`repost_cascades.csv` `relayer` column) per agent. Dropped the bottom X% of agents
by activity (standard node-filtering: induced subgraph on survivors), recomputed weighted
sign-modularity Q at illustrative cutoffs. Not a replication of Conover's exact threshold (not
available) -- a sensitivity check on the mechanism.

| drop bottom X% by activity | Q_sign (mean ± std, 5 seeds) | edge-weight retained |
|---|---|---|
| 0% (full population) | 0.318 ± 0.048 | 100% |
| 25% | 0.118 ± 0.105 | 27% |
| 50% | 0.105 ± 0.114 | 17% |
| 75% | 0.118 ± 0.128 | 8% |
| 90% | 0.145 ± 0.165 | 3% |

### Result: opposite of the hypothesis, and it points at a different, more fundamental gap

Q does not rise as inactive agents are dropped -- it collapses and gets noisy. Checking the
activity distribution directly explains why: per-agent posting+reposting activity over the full
run has **mean ≈ 5400-5800, std ≈ 700-1300, CV ≈ 0.12-0.24, minimum never below ~40-70**,
consistent across all 5 seeds. Every agent posts/reposts thousands of times over a 40k-step run
at broadly similar rates -- there is no low-activity tail for a Conover-style filter to remove.
"Dropping the least-active 25%" here removes agents that are still highly active in absolute
terms, essentially at random with respect to network structure; since an edge requires both
endpoints to survive, node removal shrinks the edge set faster than linearly (27% of edge
weight survives at a 25%-of-nodes cutoff), so the filtered numbers are mostly measuring Q on a
shrinking, noisier random subsample, not on a genuine "active core."

**This surfaces a previously-unflagged current-model gap: posting/reposting activity is not
realistically heavy-tailed.** Real platforms have extreme activity heterogeneity (most accounts
nearly silent, a small elite posting constantly); this model's CV of 0.12-0.24 is nowhere close.
This is a distinct axis from the follower/hub heterogeneity already found to be reasonably
heavy-tailed (Gini 0.90, top-1%-share 31%) -- structural (who's followed) and behavioral (who
posts) heterogeneity have decoupled here. The mechanism driving the narrow activity spread
(`postProb`/`postProbRelaxRate` comfort-ratchet dynamics, `initialPostProb=0.25537`,
`maxPostProb=1.0`) hasn't been traced in this pass; worth its own investigation if this becomes
a calibration priority.

**The original question is genuinely still open, not resolved either way**: whether Conover's
filtering methodology explains the 0.34-vs-0.7-0.8 gap can't be tested on this population, because
the population doesn't have the kind of activity tail the test assumes. Don't read this as
confirming the current model's repost-Q shortfall is "real" either -- it's an unresolved
question, not a settled one.

## Sixth pass (2026-08-01): individual-level empirical activity target, retrieved from source

Follow-up to the fifth pass's finding that current-model posting activity isn't heavy-tailed
(CV 0.12-0.24). `Const.java`'s `EMPIRICAL_POST_BIN_WEIGHTS` are per-bin *means* only, computed
from Buntain & Snegovaya 2025's underlying individual-level data but not exposing it. Retrieved
the actual source data directly: OSF 10.17605/OSF.IO/KQFM6 (via `doi.org/10.17605/OSF.IO/KQFM6`
-> OSF API file listing -> `03-its.models/_anon_data/`) -- `tw_handle_to_libcon.csv`
(handle -> self-reported ideology) and `twitter.2020to2021.matched.counts.parquet` (762 users x
736 daily post counts, 2020-01-01 to 2022-01-06). Cached at
`/private/tmp/.../scratchpad/osf_data/` this session -- not yet committed anywhere durable, see
open question below. Script: `scripts/activity_heterogeneity_empirical_target.py`.

**Validation**: summing each user's daily counts and grouping by ideology bin reproduces
`EMPIRICAL_POST_BIN_WEIGHTS` exactly (to rounding) and `EMPIRICAL_OPINION_BIN_COUNTS` exactly --
confirms this is the same source and the reconstruction is correct.

| bin | n | empirical mean | empirical CV | empirical median |
|---|---|---|---|---|
| 1 Very liberal | 160 | 4328.7 | 3.19 | 989 |
| 2 Liberal | 131 | 2682.9 | 2.81 | 527 |
| 3 Somewhat liberal | 85 | 1503.7 | 2.06 | 337 |
| 4 Middle of the road | 208 | 2135.8 | 1.72 | 502 |
| 5 Somewhat conservative | 46 | 691.1 | 1.45 | 388.5 |
| 6 Conservative | 71 | 1156.8 | 1.83 | 336 |
| 7 Very conservative | 64 | 3742.5 | 2.15 | 634 |
| **overall** | **765** | **2574.6** | **3.04** | **582** (min 5, max 141404) |

**Current model (pooled 5 seeds, n=5000)**: mean 5575.6, **CV 0.188**, median 5831, min 37, max
9585.

![Posting-activity heterogeneity CCDF: real Twitter vs current model, mean-normalized, log-log](2026-08-01-activity-heterogeneity-ccdf.png)

### This is now a hard, sourced number, not just a qualitative flag

Real per-user posting activity has **CV ≈ 1.4-3.2 depending on ideology bin, ≈3.0 overall** --
median (582) far below mean (2574.6), heavily right-skewed, spanning almost 5 orders of
magnitude (5 to 141,404 posts). The current model's CV (0.12-0.24) is over an order of
magnitude smaller. The mean-normalized CCDF makes the shape gap visually unambiguous: the real
distribution is a broad heavy tail reaching ~50x the population mean; the current model is
nearly a vertical step at 1x the mean -- i.e. almost every agent posts at close to the same
rate, which no real platform's user base does.

### Proposed calibration treatment

This resolves the earlier "no target exists" gap for individual posting-frequency
heterogeneity from the same already-adopted source as the bin7 target (no new empirical source
introduced, same paper/dataset, just used more fully). Proposed: add an activity-heterogeneity
term to the calibration loss, analogous to the existing `bin7_wasserstein` term -- either a
direct CV target (per-bin or overall) or a full quantile/Wasserstein match against this
distribution's shape. This also reopens the fifth pass's still-open Conover-filtering-bias
question: once the model can produce realistic activity heterogeneity, the activity-filtered
Q_sign test from that pass becomes meaningful to rerun (right now it couldn't discriminate,
because there was no real activity tail to filter on).

**Open question, not yet decided**: where should this OSF data live durably -- committed into
the repo (small: ~1MB total, already-public research data), or re-fetched on demand by
calibration scripts from the OSF URLs recorded here? Not resolved in this session.

**Update**: resolved -- a summarized (non-daily-granular) version is committed at
`data/empirical/buntain_snegovaya_2025_activity_by_handle.csv`, see its README for provenance.

### Cross-validation: is this a mechanism gap in `postProb`, or in `repostProb` specifically?

Decomposing the simulated "activity" measure into its two components (rather than treating it
as one combined number) resolves this cleanly, using data already on disk (no new simulation):

| component | simulated Gini | simulated CV |
|---|---|---|
| original posts only | **0.87-0.90** | 3.23-3.57 |
| reposts only | **0.04-0.10** | 0.11-0.25 |
| combined (the number used above) | 0.04-0.10 | 0.12-0.24 |

Original posting is *already* comparably or more concentrated than the real-world figures below
-- reposting is the near-total outlier, and dominates the combined number by volume (reposts
outnumber original posts ~40:1 in this model, so their near-uniformity swamps the signal).
Mechanistically: `postProb` updates every step via a per-agent comfort-ratchet (`Agent.java`),
genuinely differentiating agents; `repostProb` is set once at construction from a single global
config value (`this.repostProb = p.repostProb()`, `Agent.java:87`) and never updated again --
there is no per-agent differentiation mechanism for it at all.

**Two independent real-world cross-checks, obtained via web search** (not just the one OSF
source above):
- Zhu & Lerman 2016, "Attention Inequality in Social Media" (arXiv:1601.07200): Gini = **0.594**
  for "number of tweets posted" per user. Note their *retweets-received* Gini (0.9034) is a
  popularity/attention metric, not activity, and isn't new information for this project -- it's
  the same kind of receiving-side concentration already confirmed via this model's follower-count
  Gini (0.90-0.96, fourth pass above). Don't re-cite it as if it validated the activity side.
- Buntain & Snegovaya 2025 (same source as above): reconstructed total_posts Gini = **0.768**.

The two real sources don't agree with each other exactly (0.594 vs 0.768 -- different
samples/eras/methodology), but both sit far above the simulated combined 0.04-0.10, so the
qualitative gap is robust even though the precise target value isn't settled.

**Still an open caveat**: no literature source was found that isolates Gini/CV specifically for
retweets *made* per user (as opposed to received) -- the conclusion that `repostProb`
specifically needs a differentiation mechanism rests on the decomposition above (original-only
is fine, repost-only is the outlier, reposts dominate volume), not a direct empirical target for
repost-making behavior. Working hypothesis, not confirmed. See
[[project-activity-heterogeneity-gap]] memory for the persistent record of this finding.

## Synthesis: agreed problem list + proposed calibration objectives (2026-08-01)

Decision point after all five passes above, discussed and agreed with the user.

### Agreed: the WSSIT-era model is not a realism reference point

Several structural axes are further from plausible than the current model, not closer:
concentration is extreme in a way that reads as a small-N/low-`m` generator artifact rather
than a real follower distribution (single hub = 14.2% of all follow-edges; in-degree Gini
0.962); the network is thin (mean degree ~5) and meaningfully fragmented (~6% outside the
giant component); degree assortativity has the wrong *sign* for an online social network
(-0.28 to -0.30, disassortative, when real online social networks are one of the few real-world
network classes known to be assortative); and the asymmetric-tolerance-by-extremity mechanism
is weak and seed-unstable (-0.47, one seed sign-flipped) where the current model at least
produces it reliably. So: not a gold standard, a different and in some ways worse set of
problems.

### Scope correction (supersedes some framing above): 1-D opinion = topic/hashtag slice, not whole platform

Per the user (JCSS paper, opinion-value-definition section): the 1-D opinion axis represents a
single topic/hashtag slice of social media, not the whole platform. This demotes whole-platform
empirical figures (Kwak et al. 2010's gamma≈2.276, clustering≈0.072, platform-wide reciprocity)
from hard calibration targets to loose sanity priors only -- a topic slice isn't expected to
reproduce whole-platform aggregates. Topic/hashtag-level studies (Conover et al. 2011 and
similar) are the correct reference class instead, subject to the correction below.

### Conover et al. 2011's 0.7-0.8 repost-modularity figure: gap remains genuinely unresolved

The user's objection (their filtering excludes low-activity posters, who disproportionately
bridge camps, inflating measured modularity) was tested directly in the fifth pass above and
did **not** confirm the hypothesis -- but only because this model's population lacks the kind
of activity tail the test assumes (posting-activity CV 0.12-0.24, nowhere near Twitter's known
heavy-tailed shape). The comparison between our Q≈0.34 (unfiltered) and Conover's 0.7-0.8
(filtered) is still apples-to-oranges, just not resolvable in the direction either side
originally guessed. Treat as open, not settled.

### Confirmed NOT problems -- keep as-is, don't calibrate away from these

- Hub "plateau" (~10 comparably-dominant hubs rather than one dominant winner) -- plausible for
  topic-slice dynamics (hashtag-network studies routinely show a handful of dominant accounts).
- Full network connectivity (0.999-1.000) and the degree-assortativity sign flip to positive --
  both directional improvements over the WSSIT-era model.

### Explicitly demoted to observe-only, not active calibration targets (user decision, 2026-08-01)

- **Clustering** -- definition-dependent (per-node average vs. standard transitivity disagree in
  *direction* between eras, third pass), not decidable without first picking one definition and
  justifying it. Watch, don't calibrate against either number yet.
- **Reciprocity** -- scope-ambiguous under the topic-slice correction above (unclear whether
  Kwak et al. 2010's whole-platform ~20% figure transfers to a topic slice). Watch, don't
  calibrate against it yet.
- **Posting/reposting activity heterogeneity (parked, user decision, 2026-08-02)** -- combined
  activity Gini 0.04-0.10 (current) vs. two real-world combined-activity figures that disagree
  with each other (Zhu & Lerman 2016: 0.594; Buntain & Snegovaya 2025 reconstructed: 0.768), plus
  a mechanism hypothesis (`repostProb` needs per-agent differentiation, or `accessProb` should
  become a heterogeneous per-agent trait -- the latter proposed as the more parsimonious single
  mechanism, since it would also gate original posting and could avoid needing a second,
  redundant ratchet on `repostProb` specifically) that is plausible but **not empirically
  confirmed** -- no literature source isolates Gini/CV for retweets *made* per user specifically
  (only received/popularity, or combined post+repost totals). Decision: hold off on any
  mechanism change or calibration-loss term for this until repost-specific individual variation
  can be empirically demonstrated, rather than calibrate against an unconfirmed hypothesis.
  Proceed with calibration using the confirmed targets below in the meantime. Full mechanistic
  discussion retained in the sixth pass above and [[project-activity-heterogeneity-gap]] for
  whenever this gets revisited.

### RETRACTED (2026-08-02): "too-clean bc-extremity / repost-assortativity" was a misdiagnosis

The earlier claim (bc-extremity corr -0.826 std 0.031; repost assortativity 0.735 std 0.028,
"pinned near-deterministic") was based on *seed-to-seed* variance of the aggregate correlation.
At n=1000 agents (bc-extremity) or ~20000 edges (repost assortativity) per run, a stable
aggregate estimate across seeds is expected even when the underlying individual-level
relationship has substantial real scatter -- it does not by itself indicate the relationship is
too deterministic. Checked directly (seed 100, within-run): bc-extremity r²=0.63 (37% of bc
variance unexplained by |opinion| alone; per-opinion-decile bc std ranges 0.013-0.154, real
spread, not a tight line); repost assortativity r²=0.40 (60% unexplained; per-decile target-
opinion std 0.19-0.47). Both relationships have genuine individual/edge-level heterogeneity.
**No active calibration treatment needed here** -- retracted, not merely deprioritized. This
leaves **no confirmed new active calibration target** from this entire investigation, beyond
what was already deprioritized/parked above.

### Network density (still deprioritized, unchanged)

Mean degree 23.5, no topic-slice-scoped empirical figure available to hold this to (whole-
platform figures demoted per scope correction above). Deprioritize as a hard target; treat as
under-constrained rather than invent a number, unless a topic/hashtag-scoped density study
surfaces.

## Session wrap-up (2026-08-02)

Net result of this whole investigation, across six analysis passes plus the calibration-
objective discussion: **most suspected problems did not survive scrutiny.** Hub plateau, full
connectivity, and the degree-assortativity sign flip are confirmed improvements over the
WSSIT-era model, not issues. Clustering and reciprocity are genuinely ambiguous (definition- and
scope-dependent) and were explicitly parked rather than resolved. The activity-heterogeneity gap
is real in the data but its calibration relevance is unconfirmed (no source isolates repost-
specific individual variation) and was parked pending better evidence. The one item that
initially looked like a confirmed, actionable target -- "too-clean" bc-extremity/assortativity
relationships -- did not hold up under a closer look at within-run individual-level scatter and
is retracted outright.

**Practical upshot**: no calibration-loss change or mechanism fix is being made as a result of
this investigation. The `docs/data/empirical` addition (Buntain & Snegovaya individual-level
activity data) and the six comparison/analysis scripts under `scripts/wssit_era_vs_current_*`
and `scripts/activity_heterogeneity_empirical_target.py` remain as reusable infrastructure for
whenever any of the parked items (activity heterogeneity, clustering definition choice,
reciprocity scope) get revisited with stronger evidence. The WSSIT-era reference worktree used
throughout (`git worktree add <dir> 870b318`) was not committed anywhere and should be
regenerated from that commit if this comparison needs to be reproduced later.

## Caveats

- 5 seeds per arm; sufficient to see the repost-assortativity and clustering effects (well
  outside their observed seed-to-seed spread) but not enough for tight interval estimates,
  especially for the noisier WSSIT-era follow-graph numbers.
- `extreme=none n_mod=0` was forced on the WSSIT-era run to match current defaults; this is not
  the WSSIT-era model's own default (`extreme=SYM nModerate=1`) and does not by itself
  reproduce the WSSIT2026 paper's actual reported intervention results — this comparison is
  about baseline network/opinion dynamics only.
