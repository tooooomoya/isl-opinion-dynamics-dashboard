# 2026-07-18 — Joint Stage 1 + bc-mechanism + Stage 2 calibration

## Why this superseded the staged Stage 1 / Stage 2 split

The bc mean-reversion redesign (docs/report/2026-07-18-bc-pp-boundary-collapse-diagnosis.md)
changed `bc`'s dynamics fundamentally. A quick recheck of Stage 1c/1d's calibrated follow-graph
point under the new mechanism (2 seeds, n=1000/steps=15000, all else default) found `gamma_fit`
collapsed from 2.357 to ~1.39 — well outside the existing noise band. Root cause: `bc` gates
unfollowing (`Agent.java` ~530), so it feeds follow-graph shape directly, unlike the repost-bc-
gating change, which had no such path back into Stage 1's metrics. Decision (user, 2026-07-18):
fold Stage 1 (follow-graph) and Stage 2 (repost-network) into **one joint search** rather than
re-doing Stage 1 standalone and re-discovering the same coupling in Stage 2 again.

## Design

**10 dims** (down from 4+6 — `out_of_bc_repost_prob` dropped per user decision, held fixed at 0.0):
`max_follow, follow_prob, alpha, hop, bc_dec, bc_recovery, stub, comfort_pp, feed_capacity,
initial_pp`. `bcInit` held fixed at 0.6 (floor/ceiling midpoint — see the bc-redesign report for
why it can't default to `bcCeiling` anymore) rather than swept, to keep dimensionality bounded.

**Combined loss** — straight sum of the two previously-separate losses, same terms/scales already
validated in isolation:
```
loss = ((gini-0.8)/0.05)^2 + ((gamma_fit-2.276)/0.3)^2
     + max(0, (0.6-assort)/0.15)^2 + ((q_sign_repost-0.48)/0.05)^2
```
No warm start: neither Stage 1b/1c/1d's nor Stage 2b/c/d's evaluation points are valid
observations of this loss surface (different bc mechanism entirely, plus `bc_recovery` is a new,
previously-unswept dimension).

Script: `scripts/stage_joint_bo_calibration.py`. n=1000, steps=15000 (unchanged scale). 8 rounds x
6 points x 3 seeds = 144 sim runs, then automatic 5-seed confirmation of the winner. Log:
`docs/report/stage_joint_bo_evaluations.csv`.

## Main run result — 4 of 10 dims pinned at box edges

Best point (`max_follow=65.9, follow_prob=0.01, alpha=0.82, hop=1, bc_dec=0.7, bc_recovery=0.144,
stub=0.83, comfort_pp=2.0, feed_capacity=18, initial_pp=0.5`), 5-seed confirm:

| metric | result | target |
|---|---|---|
| Gini | 0.792 ± 0.012 | 0.8 |
| gamma_fit | 1.982 ± 0.033 | 2.276 |
| opinionAssortativity | 0.842 ± 0.011 | >= 0.6 |
| Q_sign_repost | 0.488 ± 0.007 | 0.48 |

Three of four landed close to target with low variance; `gamma_fit` off by ~0.3 but consistent
across seeds — plausibly the same finite-size MLE undershoot Stage 1a documented at n=1000 (no
analytic ground truth exists for this emergent/post-dynamics exponent to confirm against).

**Flagged before accepting:** `follow_prob` (0.01), `bc_dec` (0.7), and `comfort_pp` (2.0) all sat
exactly at their search-box edges — and not just for this one point; the 2nd/3rd-best points
repeated the same `bc_dec`/`follow_prob` pins. Same red flag as Stage 1c's boundary-pinned point.
`hop=1` was also at its edge but that's a hard floor (can't go below 1), not a box artifact.

## Follow-up: widen the 3 pinned dims, warm-start from the main run

`follow_prob: [0.01,0.3] -> [0.003,0.3]` (same lower bound Stage 1d used), `bc_dec: [0.7,0.999] ->
[0.5,0.999]`, `comfort_pp: [1.0,2.0] -> [1.0,3.0]`. Same dynamics as the main run (box only
changed), so warm-started from all 48 of the main run's evaluated points (best warm-start loss
1.164) — same justification Stage 1c -> 1d used. Script: `scripts/stage_joint_bo_followup.py`. 5
rounds x 6 points x 3 seeds, log: `docs/report/stage_joint_followup_bo_evaluations.csv`.

**Result: boundary-pinning resolved.** New best point (`max_follow=57.28, follow_prob=0.0089,
alpha=0.765, hop=1, bc_dec=0.632, bc_recovery=0.082, stub=0.687, comfort_pp=2.068,
feed_capacity=15, initial_pp=0.212`, loss=0.912) sits comfortably interior on all three widened
dims — none pinned at either the old or new edge. A competing cluster (e.g. rank-3:
`bc_dec=0.5, comfort_pp=3.0, follow_prob=0.003`, all three pinned simultaneously at the *new*
edges) still exists, but its loss (1.173) is clearly worse, reading as a genuine local optimum
rather than evidence the true optimum is still being truncated.

5-seed confirm of the new best point: Gini=0.787±0.012, gamma_fit=2.016±0.035,
assort=0.883±0.009, Q_sign_repost=0.494±0.002 — a wash against the pre-widen point on all four
metrics (no decisive improvement), but with the edge-pinning concern resolved.

## Top 5 combined (main + follow-up), by loss

| rank | loss | max_follow | follow_prob | alpha | hop | bc_dec | bc_recovery | stub | comfort_pp | feed_capacity | initial_pp |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 0.912 | 57.28 | 0.0089 | 0.765 | 1 | 0.632 | 0.082 | 0.687 | 2.068 | 15 | 0.212 |
| 2 | 1.164 | 65.90 | 0.0100 | 0.823 | 1 | 0.700 | 0.144 | 0.830 | 2.000 | 18 | 0.500 |
| 3 | 1.173 | 100.0 | 0.0030 | 0.824 | 1 | 0.500 | 0.111 | 0.815 | 3.000 | 5 | 0.010 |
| 4 | 1.201 | 15.0 | 0.0046 | 0.797 | 1 | 0.500 | 0.194 | 0.691 | 1.650 | 17 | 0.010 |
| 5 | 1.330 | 15.0 | 0.0073 | 0.909 | 1 | 0.509 | 0.137 | 0.950 | 2.367 | 5 | 0.500 |

**Note on `hop=1`:** all 5 of the top points independently landed on `hop=1` — a repeated signal,
not a fluke of one point. Combined with `alpha≈0.76-0.91` (high), this is *not* equivalent to the
legacy chronological-only model: velocity ranking still re-sorts the same 1-hop pool by engagement
rather than recency, so it reads as "For-You surfaces buzz within your own network" (a followee's
post suddenly taking off, or a followee's repost of a friend-of-friend's post going viral), not as
global algorithmic injection. Interpretable, and a real finding worth keeping in the writeup, not
an artifact to explain away.

## Decision (DECIDED 2026-07-18): adopt the follow-up's winning point, rounded

Re-confirmed at the rounded values with 5 fresh seeds before baking into defaults — held up within
noise of the raw-value confirm:

| metric | rounded-point confirm | raw-point confirm |
|---|---|---|
| Gini | 0.787 ± 0.010 | 0.787 ± 0.012 |
| gamma_fit | 1.994 ± 0.022 | 2.016 ± 0.035 |
| opinionAssortativity | 0.885 ± 0.014 | 0.883 ± 0.009 |
| Q_sign_repost | 0.489 ± 0.008 | 0.494 ± 0.002 |

**Final calibrated defaults** (`ExperimentConfig.java`): `max_follow=57, follow_prob=0.009,
alpha=0.76, hop=1, bc_dec=0.63, bc_recovery=0.08, stub=0.69, comfort_pp=2.07, feed_capacity=15,
initial_pp=0.21, out_of_bc_repost_prob=0.0 (held fixed, not itself calibrated — open item if a
nonzero rate is wanted later)`.

**Deferred, not dropped:** the m=20/m=25 HK-generator robustness check (Stage 1a) and a possible
separate calibration pass for `out_of_bc_repost_prob` both remain open follow-ups.

## v2 (2026-07-18): added SF1 "apparent polarization" as a 5th loss term — supersedes the point above

**Why:** dashboard review raised whether moderates post "too much" (silent-majority intuition).
Checked the literature first (Pew Research: 6% of prolific political tweeters produce 73% of
political tweets and are the most partisan; multiple studies replicate that the most active
posters hold more extreme opinions than the general population, distorting perceived public
opinion) — confirms the qualitative pattern is real. But checking our own data first: raw
`postShare_2` (moderate bin) being the largest slice is mostly a population-size artifact (the
moderate bin is also the largest population bin, ~29%); normalizing by population share gives a
vocality ratio of ~0.97 for moderates (roughly proportional, not over-vocal) — the actual anomaly
in the current model is an asymmetry between the extreme tails, not a clean moderate-vs-extreme
split, and only based on 5 seeds.

**Better anchor found:** `docs/reference/JCSS-TomoyaTakeda2026.pdf` Section 4.2 (stylized-fact
validation for the sibling Structural Backfire Effect paper, same underlying model) operationalizes
this exact phenomenon as SF1: `sigma^2_post / sigma^2_opinion` (post-weighted opinion variance over
user-weighted opinion variance), anchored to an empirical range of **[1.19, 1.26]** recomputed
directly from Buntain & Snegovaya 2025 (PNAS Nexus)'s primary account-level Twitter/X data (n=762
users, ~1.96M posts) — hyperpartisan accounts post 2-3x as often as moderates. Their sibling model
achieved median 1.248 (IQR [1.175,1.299]) against this range, under a *different* configuration
(monotone-only bc decay, no recovery term, HK pt=0.3) than our current mean-reversion mechanism —
so the target range transfers (empirical, model-independent) but their achieved value does not
guarantee ours will land in range without a genuine search.

This ratio is already logged in every run as `postOpinionVar / opinionVar` (both already in
`results.csv`) — no new instrumentation needed. Checked the previous (v1) calibrated point's 5-seed
confirm: mean ratio 0.952 +/- 0.162, below 1.0 on average, well short of [1.19,1.26] — confirms a
real gap, not just a dashboard impression.

**Loss term added:** `((ratio - 1.225) / 0.035)^2` (midpoint/half-width of the empirical range,
same squared-distance style as the other four terms). Same 10 dims, same (already-widened) box as
the v1 follow-up. No warm start (v1's CSVs didn't log `postOpinionVar`/`opinionVar`, and the
underlying result folders are gone). Script: `scripts/stage_joint_bo_v2_apparent_polarization.py`,
8 rounds x 6 points x 3 seeds, log: `docs/report/stage_joint_v2_bo_evaluations.csv`.

**v2 result: rejected.** Best point pinned 7/10 dims at box edges, including `bc_dec=0.999` +
`bc_recovery=0.0` together — the optimizer found it easier to freeze `bc` entirely (no decline, no
recovery, stuck at `bcInit`) than to satisfy all 5 targets with it active. Collateral damage:
`gamma_fit` collapsed to 1.43 (vs. 2.28 target, worse than v1's 1.99), and the ratio still fell
short (1.08 vs. 1.19-1.26) with huge cross-seed variance. Diagnosed with a per-agent GEXF snapshot
(`log_gexf=true`, v1's calibrated point, n=1000/steps=15000): `corr(|opinion|, bc) = -0.09`
(near zero), `corr(bc, postProb) = +0.41` (wrong sign), `corr(|opinion|, postProb) = -0.008`
(~zero) — the causal chain "extremity -> tighter bc -> bc-gated echo chamber (`Agent.follow()`
already gates new-tie candidates on `|diff|<bc` and evicts the most opinion-distant followee, so
this part of the mechanism is structurally correct) -> narrow-radius comfort match -> higher
`postProb`" is not happening. Root cause: `bc_recovery` (0.08) pulls every agent back toward
`bcInit=0.6` regardless of position, and `follow_prob=0.009` gives each agent only ~13 follow
opportunities across the whole 15000-step run — not enough for the correct mechanism to produce
heterogeneity. v2's boundary-pinning was the optimizer correctly discovering this tension (wanting
higher `follow_prob` and neutralized `bc`) and trading it off against Gini/gamma_fit, which were
calibrated assuming the slow regime.

## v3 (2026-07-18): re-weighted objective, current — supersedes v2

**Changes (user decision):**
- `steps`: 15000 -> 20000, to give the `follow_prob`-gated echo-chamber mechanism more absolute
  opportunities to fire at the same `access_prob=0.1`.
- `opinionAssortativity` dropped from the loss (monitored only, still logged): if SF1 requires
  bc-gated echo-chamber formation, assortativity is a near-necessary byproduct of the same
  mechanism, not an independent target. Not fully trusted blind, though — this is the same metric
  that silently collapsed once before (original Stage 1b `follow_prob` diagnostic).
- `gamma_fit` dropped from the loss entirely (monitored only): the actual goal is heavy-tailedness,
  not a specific exponent, and this metric is also the one already documented (Stage 1a) as least
  trustworthy at n=1000 (systematic MLE undershoot, no analytic ground truth for the emergent
  post-dynamics exponent). Gini stays in the loss as a more robust concentration proxy (no
  finite-size xmin-selection bias, indifferent to power-law vs. log-normal).
- `bc_recovery` box tightened `[0.0,0.3] -> [0.0,0.05]` so extremity-driven decline isn't drowned
  out by an overly strong content-independent recovery pull.

**Net:** loss = Gini + Q_sign_repost + SF1 ratio (3 terms, down from 5) — SF1 gets more relative
pull without touching its own scale. Fresh run, no warm start (the step-horizon change alone
invalidates every prior evaluation, on top of the loss-formula change). Script:
`scripts/stage_joint_bo_v3_silent_majority.py`, 8 rounds x 6 points x 3 seeds, log:
`docs/report/stage_joint_v3_bo_evaluations.csv`.

**v3 result: healthy optimization, no boundary pinning, but SF1 still short.** Best point
(`max_follow=55.6, follow_prob=0.031, alpha=0.234, hop=2, bc_dec=0.591, bc_recovery=0.0083,
stub=0.91, comfort_pp=2.28, feed_capacity=36, initial_pp=0.14`) sits interior on every dim. 5-seed
confirm: Gini=0.7998+/-0.012 (near-exact), Q_sign_repost=0.4978+/-0.001 (near-exact),
assort(monitored)=0.958+/-0.004 (high without being a target -- the "comes along for free" bet
paid off), but apparent-polarization ratio=0.964+/-0.044, still short of [1.19,1.26] and actually
*lower* than v2's degenerate 1.079.

Re-ran the per-agent GEXF diagnostic on this point (n=1000, steps=20000): `corr(|opinion|,bc) =
-0.068` (still ~zero), `corr(bc,postProb) = +0.117` (still wrong sign, weaker), `corr(|opinion|,
postProb) = -0.268` (extremity predicts LESS vocal). `postProb` by bin: `[0.444, 0.500, 0.500,
0.500, 0.485]` -- the three centrist bins are pegged exactly at the ceiling (`maxPostProb=0.5`),
both extreme bins sit below it. **The model currently produces the opposite of silent-majority/
vocal-minority: moderates are maximally vocal, extremes are the quieter ones.**

Tested (per user request) whether this is a `VOCAL_COMFORT_RADIUS` artifact: promoted the constant
to a CLI-tunable `vocalComfortRadius` (`ExperimentConfig.java`/`SimParams.java`/`Agent.java`,
default kept at the old 0.2) and swept it directly at the v3 point (0.10/0.20/0.35/0.50/0.70,
single seed each). `corr(|opinion|,postProb)` stayed negative at every value tested (-0.126 to
-0.337, no sign flip, no clean trend with radius) -- rules out "window too narrow/wide" as the
explanation. Consistent with the underlying cause: `comfortPostRate` measures absolute proximity
to a population-dense region, which structurally favors moderates (who live in the dense center of
a unimodal opinion distribution) over extremes, regardless of the window's width. Kept the
promoted parameter (harmless, now a documented negative result) but did not pursue a relative-
conformity mechanism redesign (discussed, deferred) -- next move is a reweighted sweep instead.

## v4 (2026-07-19): explicit weight multipliers re-prioritizing SF1 -- current

**Why:** user's hypothesis on v3's diagnostic -- bin0 (extreme-) had the *tightest* bc (0.300) of
any bin yet was still less vocal than looser-bc bins 1-3, suggesting `bc_dec`'s decline effect is
now strong enough to diffuse bc-gated echo-chamber formation across the whole population rather
than concentrating it on the extremity-driven tails. Gini/Q_sign_repost get satisfied "for free"
by this broad-based sorting, which doesn't specifically privilege the tails the way SF1 needs --
i.e. the objective's easiest path to satisfying Gini/Q happens to work against SF1.

**Fix:** explicit weight multipliers on the loss terms (`WEIGHT_GINI=1.0, WEIGHT_Q=1.0,
WEIGHT_RATIO=3.0`), keeping each term's target/scale (how much noise to tolerate) separate from
its weight (how much it matters) -- cleaner than folding the reweight into `RATIO_SCALE` directly.
Same 10 dims/box and steps=20000 as v3. Fresh run, no warm start (loss-formula change invalidates
v3's evaluated points). Script: `scripts/stage_joint_bo_v4_reweighted.py`, 8 rounds x 6 points x 3
seeds, log: `docs/report/stage_joint_v4_bo_evaluations.csv`, running 2026-07-19.

**Caveat flagged before running, not yet resolved:** extreme bins are a small population (~120
agents each vs. ~290 for moderates, out of 1000) -- even under identical homophily-seeking
pressure, extremists may structurally lack enough same-camp candidates to fill ~55 followee slots.
If so, that's a capacity ceiling reweighting can't fix. Worth checking if v4 still falls short.

**v4 result: worse than v3, not better -- rejected.** Best point (`max_follow=15, follow_prob=0.3,
alpha=0.354, hop=5, bc_dec=0.999, bc_recovery=0.0, stub=0.95, comfort_pp=1.0, feed_capacity=27,
initial_pp=0.345`) re-discovered v2's exact degenerate trick (`bc_dec≈1` + `bc_recovery=0`, bc
frozen at `bcInit`), this time with 6/10 dims pinned at box edges (vs. v2's 7/10, but a different
6, and `comfort_pp` pinned at the *opposite* extreme, 1.0 vs. v2's 3.0). 5-seed confirm:
Gini=0.832+/-0.004, Q_sign_repost=0.498+/-0.002 (both still hit), assort(monitored)=0.994+/-0.0004
(near-total segregation), but **ratio=0.871+/-0.151** -- worse than v3's 0.964 despite 3x the
loss weight on exactly this term, and far less stable (loss std 283 vs. v3's 17.8). Tripling the
weight didn't push the optimizer toward a better relative-conformity regime; it just found a
cheaper way to satisfy Gini/Q via brute-force segregation while the ratio itself got worse and
noisier. Read as evidence *for* the capacity-ceiling hypothesis (more weight can't fix a target
that isn't reachable by reweighting the same dims) rather than a search-budget problem. **v3's
point remains the best "sane" (non-pinned, stable) calibrated point at this stage.**

## Manual point (2026-07-20, user): breaks the ceiling hypothesis, but unstable

User hand-edited `ExperimentConfig.java` directly (not via BO) rather than continuing to reweight
the existing 10-dim search:

| param | v1 default | manual |
|---|---|---|
| `feedHopH` | 1 | 2 |
| `bcRecoveryRate` | 0.08 | 0.001 (near-frozen) |
| `bcDecRate` | 0.63 | 0.98 (near-frozen: `bc *= 0.98` per hit) |
| `bcInit` | 0.6 | 1.0 (back to ceiling) |
| `maxPostProb` | 0.5 | 1.0 |
| `comfortPpFactor` | 2.07 | 1.05 |

Compiled and ran the standard 5-seed confirm harness (`scripts/confirm_manual_expconfig.py`,
n=1000/steps=20000, no CLI overrides -- pure compiled defaults):

| seed | gini | gamma_fit | assort | Q_sign_repost | ratio |
|---|---|---|---|---|---|
| 810000 | 0.861 | 1.39 | 0.840 | 0.448 | 1.053 |
| 810001 | 0.852 | 1.85 | 0.772 | 0.476 | 1.525 |
| 810002 | 0.858 | 1.66 | 0.743 | 0.474 | 1.436 |
| 810003 | 0.844 | 1.45 | 0.812 | 0.463 | 1.094 |
| 810004 | 0.860 | 1.70 | 0.789 | 0.478 | 1.351 |
| mean | 0.855+/-0.006 | 1.61+/-0.17 | 0.791+/-0.033 | 0.468+/-0.011 | **1.292+/-0.187** |

Mean ratio (1.292) clears [1.19,1.26] for the first time across five attempts (v1=0.95,
v2=1.08 degenerate, v3=0.96, v4=0.87 degenerate) -- **falsifies the strict capacity-ceiling
reading**: the model can produce ratio > 1.2, just not via any point BO's 10-dim search (always
paired "bc frozen" with the old, stronger comfort/postProb settings) had found.

**Caveat: the mean is misleading.** No individual seed lands in [1.19,1.26] -- outcomes are
bimodal, splitting between ~1.05-1.09 (2/5 seeds) and ~1.35-1.52 (3/5 seeds), not five runs
clustered near 1.2. std (0.187) is ~4x v3's (0.044). Same instability signature as the rejected
v2/v4 degenerate points (bc nearly frozen -> outcome hinges on which agents get unlucky early
contact sequences, not a robust attractor). Gini also overshoots (0.855 vs. 0.80) and
Q_sign_repost undershoots slightly (0.468 vs. 0.48, within noise).

**Read:** real progress (the target is reachable on average), not yet a stable calibration point.

## v5 (2026-07-20): local BO search focused on the manual point's region -- current

**Design:** rather than re-running the full 10-dim box, fix the dims the manual point didn't touch
at their v1-calibrated values (`max_follow=57, follow_prob=0.009, alpha=0.76, feed_capacity=15,
initial_pp=0.21, stub=0.69, out_of_bc_repost_prob=0.0`) and search only the 5 dims implicated by
the manual result, boxed tightly around it:

```
hop:          Integer(1, 3)
bc_dec:       Real(0.9, 0.999)
bc_recovery:  Real(0.0, 0.02)
bc_init:      Real(0.8, 1.0)      # newly swept -- fixed at 0.6 in all prior stages
comfort_pp:   Real(0.5, 1.5)
max_post_prob: fixed at 1.0 (not searched)
```

Same loss as v3 (equal-weight Gini + Q_sign_repost + ratio, no v4-style multipliers -- v4 showed
reweighting backfires). n=1000, steps=20000. 6 rounds x 6 points x 3 seeds = 108 sim runs, then
5-seed confirm of the winner. Script: `scripts/stage_joint_bo_v5_local.py`, log:
`docs/report/stage_joint_v5_bo_evaluations.csv`.

Goal: find a point in this newly-opened region that hits the SF1 target *and* is stable
(low cross-seed variance), not just correct on average.

**v5 result: boundary-pinned again, and trades away Q_sign_repost/assortativity for SF1 --
not an acceptable point.** Best point (`hop=2, bc_dec=0.969, bc_recovery=0.02, bc_init=0.888,
comfort_pp=0.725`) pins `bc_recovery` exactly at the box's *upper* edge -- the opposite direction
from every prior pin (v2/v4 wanted `bc_recovery` at 0, this wants more than 0.02 allows). 5-seed
confirm:

| metric | v5 best | v3 (reference) | manual (reference) | target |
|---|---|---|---|---|
| Gini | 0.890+/-0.004 | 0.800+/-0.012 | 0.855+/-0.006 | 0.8 |
| gamma_fit (monitored) | 1.645+/-0.032 | -- | 1.61+/-0.17 | -- |
| assort (monitored) | **0.400+/-0.061** | 0.958+/-0.004 | 0.791+/-0.033 | -- |
| Q_sign_repost | **0.299+/-0.049** | 0.498+/-0.001 | 0.468+/-0.011 | 0.48 |
| ratio | 1.306+/-0.145 | 0.964+/-0.044 | 1.292+/-0.187 | [1.19,1.26] |

Ratio's mean and variance both improved slightly over the manual point, but `Q_sign_repost`
collapsed to ~62% of target and assortativity dropped to less than half of every other point in
this whole calibration series. Same equal-weight loss as v3 (which hit Gini/Q almost exactly)
now lets the optimizer buy SF1 gains by giving up network structure entirely -- inside this
tightened box, the three targets appear to be in genuine tension, not merely under-searched.
Rejected as a calibration candidate. Open question for the user: widen `bc_recovery` past 0.02
(the pinned edge) and re-run, or treat this as evidence that SF1 and Q_sign_repost/assortativity
trade off against each other in the near-frozen-bc regime and step back to a different lever.

**Diagnosis (user, 2026-07-20): the loss was never actually equal-weight.** `RATIO_SCALE=0.035`
(set in v2 to match the empirical target's half-width) is tighter than `GINI_SCALE=Q_SCALE=0.05`,
so a fixed absolute error costs `(0.05/0.035)^2 ~= 2.04x` more loss on ratio than the same-sized
error on Gini/Q -- present in every "equal-weight, no multiplier" run since v2, including v3 and
v5, not just v4's explicit `WEIGHT_RATIO=3`. Compounding this: ratio's own cross-seed noise
(0.044-0.187, measured across v3/manual/v5) is frequently *larger* than its 0.035 scale, while
Gini's noise (0.004-0.012) sits comfortably inside its 0.05 scale -- the objective was asking the
optimizer to hit ratio more precisely than the simulation reproducibly delivers, rewarding
noise-chasing/boundary points over stable ones.

## v6 (2026-07-20): true equal-weight loss + widened bc_recovery -- current

**Fix:** `RATIO_SCALE` raised to `0.05` (matches `GINI_SCALE`/`Q_SCALE` exactly -- genuine equal
weighting, no hidden asymmetry). `bc_recovery` box widened `[0.0,0.02] -> [0.0,0.2]` since v5
pinned at the old upper edge -- still safely within the damped-convergence regime (the
mean-reversion update only overshoots/oscillates once the rate exceeds 1.0). Same other 4 dims
(`hop, bc_dec, bc_init, comfort_pp`) and fixed dims as v5. Fresh run, no warm start. Script:
`scripts/stage_joint_bo_v6_equal_weight.py`, 6 rounds x 6 points x 3 seeds, log:
`docs/report/stage_joint_v6_bo_evaluations.csv`, running 2026-07-20.

**v6 result: no boundary pins, ratio's mean clears the target for the first time, but
Gini/Q/assort don't improve on v5's collapse.** Best point (`hop=1, bc_dec=0.961,
bc_recovery=0.019, bc_init=0.860, comfort_pp=0.890`) -- `bc_recovery` now lands well interior
(0.019, nowhere near the widened 0.2 edge). 5-seed confirm:

| metric | v6 | v5 (old scale) | v3 (ref) | target |
|---|---|---|---|---|
| Gini | 0.854+/-0.009 | 0.890+/-0.004 | 0.800+/-0.012 | 0.8 |
| assort (monitored, global) | 0.424+/-0.043 | 0.400+/-0.061 | 0.958+/-0.004 | -- |
| Q_sign_repost | 0.303+/-0.065 | 0.299+/-0.049 | 0.498+/-0.001 | 0.48 |
| ratio | **1.198+/-0.165** | 1.306+/-0.145 | 0.964+/-0.044 | [1.19,1.26] |

Equalizing the loss weight resolved the boundary-pinning artifact but did **not** fix the Gini/Q/
assort collapse -- essentially identical to v5's despite removing the scale asymmetry. Reads as a
genuine mechanism trade-off (wide/near-frozen `bc` disables the `follow()` homophily gate; see
discussion below), not a loss-tuning artifact.

## Is `Q_sign_repost=0.3` actually bad? Two clarifications (2026-07-20, user-prompted)

**(1) The 0.48 target's provenance is looser than it looks.** Per
`docs/report/2026-07-17-stage2-target-correction.md`, 0.48 comes from Conover et al. 2011's
retweet-network modularity via **data-driven label-propagation community detection**, whereas
`Q_sign_repost` is a **strict, known sign-based two-community partition** -- a different metric
computed in the same spirit, not the same statistic. The correction doc itself concludes 0.48 is
order-of-magnitude guidance, and if anything the true sign-partition value is more likely lower
than 0.48 (label noise inflates data-driven modularity relative to a forced binary split). Treating
Q as directional/monitored rather than a hard `(q-0.48)^2` target is defensible on its own terms.
By the generic Newman-Girvan convention, Q > ~0.3 is the usual threshold cited for "non-random
community structure" -- 0.3 is not a collapse to the ~0.001-0.02 failure mode this project already
documented once (original Stage-2 round-0), it's a weaker-but-real structure.

**(2) `opinionAssortativity` is a single pooled Pearson correlation over every follow edge in the
network** (`Analysis.java` `computeOpinionAssortativity`, Newman scalar assortativity) -- no
per-opinion-class breakdown exists in the pipeline. Computed one from a single-seed GEXF snapshot
at the v6 point (final-step follow graph, 5 equal-width opinion bins,
`Const.NUM_OF_BINS_OF_OPINION=5`):

| bin | n agents | follow edges | mean\|delta-opinion\| | local corr(src,tgt) | frac same-sign |
|---|---|---|---|---|---|
| 0 (extreme-) | 62 | 698 | 0.366 | 0.176 | **0.904** |
| 1 | 255 | 4289 | 0.290 | 0.162 | 0.713 |
| 2 (moderate) | 372 | 8125 | 0.328 | 0.097 | **0.522** |
| 3 | 237 | 3841 | 0.300 | 0.230 | 0.697 |
| 4 (extreme+) | 74 | 769 | 0.342 | 0.188 | **0.909** |
| global (sanity check) | -- | 17722 | -- | 0.446 | -- |

(Global corr 0.446 matches the reported seed-averaged 0.424+/-0.043 within noise -- consistent
methodology.) **The aggregate collapse is not uniform.** It's driven almost entirely by the
moderate bin sitting at a same-sign coin flip (0.522, no camp loyalty), while both extreme bins are
at ~0.90 same-sign -- strongly camp-loyal. This is the asymmetric structure the paper's Type-2 story
actually needs (extremes segregate, moderates bridge), invisible in the pooled scalar because a
highly-segregated small tail population gets averaged against a much larger, weakly-segregated
center. Caveat: local Pearson correlations themselves are modest everywhere (0.10-0.23) even in the
extreme bins, so if "assortativity" means magnitude-covariation it's weak across the board --
`frac_same_sign` (matching `Q_sign_repost`'s own sign-based logic) is the more theoretically
appropriate reading here.

**Open gap, not yet checked:** this diagnostic was run on the **follow graph**
(`GEXF/lambda_0.0/step_20000.gexf`); `Q_sign_repost` is computed on the separate **repost
network**. The follow-graph tail-vs-center asymmetry does not automatically imply the same holds on
the repost network -- that needs its own per-bin same-sign check before concluding `Q_sign_repost`
0.30 is similarly "healthy-but-masked" rather than a genuine repost-mechanism weakness.

**Correction (2026-07-20):** checked `crossRepostRate` (0.40) against the properly moderate-
excluded repost metric `interactionCrossCuttingFraction` (0.185, from the same v6 confirm runs) --
these do NOT agree. `crossRepostRate` has no moderate-band exclusion
([Agent.java:405](../../src/agent/Agent.java#L405), raw `opinion*postOpinion<0` sign test on every
repost), so it picks up sign noise from the ~372/1000 agents sitting near opinion~=0. Properly
matched (both moderate-excluded), `crossCuttingFraction` (follow, 0.202+/-0.055) and
`interactionCrossCuttingFraction` (repost, 0.185+/-0.078) are statistically indistinguishable -- the
repost layer is NOT more diluted than the follow layer. **Retracts the "wide bc dilutes repost
segregation" explanation above.** `Q_sign_repost=0.30` vs. an 82% same-camp tie fraction remains
unexplained (modularity is not a linear function of same-camp fraction; needs its own investigation,
not assumed away).

## Foundation-credibility audit (2026-07-20): does ANY point jointly satisfy all 4 structural facts?

Before any moderate-hub-specific experiment, the base model needs to reproduce well-established
structural facts on its own terms: Gini/heavy-tailed degree (~0.8, real-Twitter-like), Q_sign_repost
(~0.48, Conover et al. 2011), opinion-assortativity/homophily (reasonably high), SF1 apparent-
polarization (in [1.19,1.26]). Mined all 168 points logged across v3-v6 (not just each version's
chosen "best") for any point jointly satisfying all four (generous bands: gini in 0.8+/-0.06, q in
0.48+/-0.08, assort>=0.6, ratio in [1.10,1.35]).

**Result: exactly one nominal hit, and it's not real.** The only point clearing all four bands is
v4's already-rejected `bc_dec=0.999, bc_recovery=0.0` degenerate point, read from its 3-seed
*search-round* aggregate (`gini=0.827, q=0.500, assort=0.994, ratio=1.159`). But this exact point's
actual 5-seed *confirm* (already on record) gave `ratio=0.871+/-0.151` -- a miss, wildly different
from the 3-seed reading. Same parameters, different seed draws, incompatible answers: the apparent
4-way success was a small-sample fluke, not a stable property of the point. **Zero robust points
found across 168 candidates and 4 different search strategies.** The two known families
(tight-bc/v3-like: Gini/Q/assort hit, SF1 short; wide-frozen-bc/v4-v6-like: SF1 mean can reach
target, Gini/Q/assort collapse) trade off against each other; neither is a credible "this is our
simulated social network" foundation on its own.

## v7 (2026-07-20): variance-penalized loss, widened box -- current

**Fix, two parts (user decision):**
1. `SEEDS_PER_POINT` raised 3 -> 5 (matches `CONFIRM_SEEDS`) -- closes exactly the gap that let
   v4's fluke through the search in the first place.
2. Explicit variance-penalty terms added to the loss for each hard-target metric (gini, q, ratio),
   same `0.05` scale as the mean-miss terms (genuine equal treatment, no arbitrary weight):
   `loss = sum_m [ ((mean_m-target_m)/scale_m)^2 + (std_m/scale_m)^2 ] + assort floor term`.
   `assort` keeps its original v1 one-sided floor term (0.6 floor) rather than a hard target --
   restored to the loss (dropped in v3-v6) since we're now checking joint feasibility, not just SF1.

Also widened the 5 contested dims (`hop, bc_dec, bc_recovery, bc_init, comfort_pp`) back to their
ORIGINAL full ranges (v3/v4's box for hop/bc_dec/bc_recovery, full `[bcFloor,bcCeiling]=[0.2,1.0]`
for bc_init, union of v3/v4 and v5/v6's ranges for comfort_pp) rather than v5/v6's narrow box
centered on the manual point, so the search isn't pre-biased toward the wide/frozen-bc family
before the variance penalty gets a chance to rule it out on its own merits. Other 6 dims fixed at
v1's stable, never-implicated values. n=1000, steps=20000, 8 rounds x 6 points x 5 seeds = 240 sim
runs, then 5-seed confirm. Script: `scripts/stage_joint_bo_v7_robust.py`, log:
`docs/report/stage_joint_v7_bo_evaluations.csv`, running 2026-07-20.

Deleted all prior `results/` run folders (80GB, 530 completed folders) before launching -- all
metrics needed from them are already recorded in this doc; no live processes were using them.

**v7's best point, 20-seed targeted confirm (resolving the 5-seed discrepancy):** the two
independent 5-seed reads for `hop=1, bc_dec=0.561, bc_recovery=0.105, bc_init=0.838,
comfort_pp=1.018` disagreed on ratio (search-round 1.152+/-0.109 vs. confirm 0.907+/-0.096). Ran
20 fresh seeds on just this point (`scripts/confirm_v7_best_20seed.py`, no search): `gini=0.794+/-
0.016` (SEM 0.0035), `Q_sign_repost=0.471+/-0.016` (SEM 0.0035), `assort=0.736+/-0.034` (SEM
0.0077, comfortably above the 0.6 floor), `ratio=1.066+/-0.152` (SEM 0.034). True ratio mean is
~1.07 -- both 5-seed reads were noisy draws from a real distribution, not evidence of chaotic
bistability. Per-seed ratio values (sorted): `[0.705, 0.852, 0.909, 0.944, 0.962, 0.983, 0.985,
0.995, 1.019, 1.06, 1.102, 1.104, 1.131, 1.131, 1.162, 1.189, 1.199, 1.218, 1.321, 1.339]` --
smooth and unimodal, not the bimodal split the frozen-bc family showed. **Best foundation
candidate this project has produced:** mechanism-alive (bc genuinely declines and recovers, not
frozen), 3 of 4 structural facts solid and stable (Gini, Q, assort), SF1 short by a real but modest
~12-15%, not chaotic.

## v8 (2026-07-20): warm-started continuation of v7 in the same box -- current

v7's own 48-point log (not just its chosen "best") surfaced a second promising, non-degenerate
point -- `round7/idx4`: `hop=1, bc_dec=0.783, bc_recovery=0.085, bc_init=0.758, comfort_pp=1.179`,
`ratio=1.124+/-0.081` (tighter than the chosen best's 1.152+/-0.109), `gini=0.833, q=0.464,
assort=0.721` -- plus a third, structurally different family (`bc_dec~0.999, bc_recovery~0.2-0.3,
bc_init~0.2, comfort_pp~1.2-3.0`) with excellent `Q_sign_repost~0.49`/`assort~0.95-0.98` but ratio
short at ~0.97-1.01. 48 points is thin coverage for a 5-dim continuous+integer space and neither
region looks converged. Rather than narrowing the box around one candidate (premature -- the good
points already span most of it) or re-searching blind, warm-started a fresh `Optimizer` with all
48 of v7's (point, point_loss) observations (re-derived under this script's identical loss/box --
valid warm-start, nothing changed) before asking for 8 more rounds. Same 5-dim box, same
variance-penalized 5-seed loss. Script: `scripts/stage_joint_bo_v8_warmstart.py`, log:
`docs/report/stage_joint_v8_bo_evaluations.csv`. **Killed after round 0** (user redirected, see v9)
-- round 0 (warm-started from v7's 48 points) hadn't beaten v7's best (loss still 6.967).

## v9 (2026-07-20): SF1 ratio only, other 3 facts ignored -- current

**User decision:** stop balancing all 4 facts; find the best achievable, *stable* fit to the SF1
ratio alone, ignoring Gini/Q_sign_repost/assort entirely, as a ceiling-finding exercise (not a
calibration candidate by itself -- what the other 3 metrics look like at the winning point is
still worth reporting, just not optimized for). Loss reduced to
`((ratio_mean-1.225)/0.05)^2 + (ratio_std/0.05)^2` only -- kept the variance-penalty half rather
than mean-only, since a mean-only ratio objective is exactly what produced v4's fluke. Same 5-dim
box as v7/v8 (not narrowed), same 6 fixed dims, 5 seeds/point (unchanged -- still need enough seeds
per point to trust a "hit", per the v7 lesson). v8 killed cleanly (round 0 only, no result lost
that mattered) to free the machine for this run. Script:
`scripts/stage_joint_bo_v9_ratio_only.py`, log: `docs/report/stage_joint_v9_bo_evaluations.csv`,
running 2026-07-20. Whatever wins still needs a 20-seed confirm before trusting its true mean.

**v9 result: best point genuinely hits SF1 on the mean, first time in the project.** Best point
`hop=1, bc_dec=0.999, bc_recovery=0.234, bc_init=0.559, comfort_pp=0.5` (both `bc_dec` and
`comfort_pp` sit at the search box's edges -- flagged, not dismissed, since the confirm shows
healthy non-collapsed structure, unlike v2/v4's degenerate edge-pins). Two independent 5-seed
batches disagreed on ratio again (search-round 1.094+/-0.155; confirm 1.355+/-0.208 -- a ~0.26
swing, same magnitude as v7's point's swing), so ran a 20-seed targeted confirm
(`scripts/confirm_v9_best_20seed.py`):

| metric | v9 20-seed | v7 20-seed (prior best) | target |
|---|---|---|---|
| Gini | 0.872+/-0.004 | 0.794+/-0.016 | 0.8 |
| Q_sign_repost | 0.454+/-0.049 | 0.471+/-0.016 | 0.48 |
| assort | 0.650+/-0.050 | 0.736+/-0.034 | >=0.6 floor |
| ratio | **1.236+/-0.225** | 1.066+/-0.152 | [1.19,1.26] |

True ratio mean 1.236 sits essentially on the target center (1.225) -- the first confirmed point
in this whole project whose mean actually lands inside the band. Per-seed spread is still wide
(0.854-1.580 across the 20 seeds) but smooth/unimodal (not the old bimodal split) -- only 3/20
individual seeds land strictly inside [1.19,1.26], the rest scatter on both sides of a real,
correctly-centered mean. Trade-off vs. v7's point: Gini overshoots more (0.872 vs 0.8), assort is
weaker (0.650, near its floor rather than comfortably above it) -- worse but not collapsed on
either.

## Decision (DECIDED 2026-07-20): adopt v9's point as the new calibrated defaults

Baked into `ExperimentConfig.java`: `feedHopH=1` (unchanged), `bcRecoveryRate=0.234`,
`bcDecRate=0.999`, `bcInit=0.559`, `comfortPpFactor=0.5` (`maxPostProb=1.0` unchanged, already
fixed at this value across v7-v9). Recompiled clean; `test.ModelTests` passes except 2
pre-existing, unrelated failures (`testTag`'s `p_u` case -- stale test assumption that
`pU`'s default isn't `0.05`, when it already is at HEAD before this session's changes; verified via
`git show HEAD` on `ExperimentConfig.java`, not something this adoption introduced). 3-seed spot
check on the freshly compiled defaults (seeds 900500-900502, no CLI overrides) reproduced the
expected profile: ratio 0.97/1.53/1.76 (wide spread, consistent with the confirmed std),
assort 0.64/0.67/0.71, Q_sign_repost 0.45/0.48/0.49 -- consistent with the 20-seed confirm.

**Open item raised by user:** ratio's high per-seed variance (std 0.225) might be related to the
*proportion* of moderate-hub-like agents in a given seed's realized network/opinion draw, not pure
sampling noise in a fixed-structure sense -- i.e. variance could be compositional (how many
vocal-moderate conduits a given seed happens to produce) rather than dynamical. Not yet tested;
candidate explanation for the next investigation.

## Static-bc confirmation (2026-07-20): the dynamic mechanism is vestigial at this point

**User's observation:** v9's adopted `bc_dec=0.999` means decline shaves off ~0.1% of bc per
uncomfortable contact, while `bc_recovery=0.234` pulls 23% of the gap back toward `bcInit` on
every step -- recovery so thoroughly dominates decline that bc should barely ever leave `bcInit`
in practice. If true, the whole asymmetric-tolerance mechanism built in the 2026-07-18 bc redesign
isn't doing any work at this specific operating point.

**Tested directly, not just inferred.** `bc_dec=1.0` *exactly* isn't an approximation of "very
weak decline" -- `this.bc *= 1.0` never changes bc at all, and since bc starts at `bcInit`
([Agent.java](../../src/agent/Agent.java) constructor), the recovery term
`bcRecoveryRate*(bcInit-bc)` is then multiplying zero forever too. `bc_dec=1.0` makes bc
*provably* static at `bcInit` for every agent, permanently, regardless of `bc_recovery`'s value.
Ran 20 seeds at `hop=1, bc_dec=1.0, bc_recovery=0.0, bc_init=0.56, comfort_pp=0.5` (rounded from
v9's raw point) and compared against v9's dynamic-bc 20-seed confirm:

| metric | static (`bc_dec=1.0`) | dynamic (v9, `bc_dec=0.999`) |
|---|---|---|
| Gini | 0.869+/-0.006 | 0.872+/-0.004 |
| Q_sign_repost | 0.454+/-0.034 | 0.454+/-0.049 |
| assort | 0.650+/-0.041 | 0.650+/-0.050 |
| ratio | 1.334+/-0.230 | 1.236+/-0.225 |
| crossCuttingFraction | 0.043+/-0.022 | 0.044+/-0.016 |
| interactionCrossCuttingFraction | 0.047+/-0.026 | 0.035+/-0.021 |

Gini/Q/assort match to 2-3 decimal places; ratio's mean shifts somewhat but both sit well within
the same noisy, overlapping range; the independent segregation metrics (never touched by any
loss) match too. **Confirmed: the dynamic bc mechanism is vestigial here** -- a static, uniform
`bc=0.56` reproduces the same emergent behavior as the calibrated dynamic version. Bounded
confidence itself (the fixed-width homophily filter in `Agent.follow()`) still clearly matters --
that's presumably what drives the segregation -- but the asymmetric decline/recovery *dynamics*
built in the 2026-07-18 redesign aren't adding anything at this operating point.

## Decision (DECIDED 2026-07-20): adopt static bc as the new calibrated defaults, supersedes v9

Baked into `ExperimentConfig.java`: `bcDecRate=1.0` (static bc, was 0.999), `bcRecoveryRate=0.0`
(no effect once decline is off, set to 0 rather than left implying unused dynamics, was 0.234),
`bcInit=0.56` (rounded from 0.559, confirmed at the rounded value directly, not just the raw
float), `comfortPpFactor=0.5` (unchanged, already clean), `feedHopH=1` (unchanged). The old
`bcRecoveryRate`/mean-reversion machinery (`Agent.java`) is left in place, not deleted -- still
available if a future experiment needs dynamic bc again, just inert at `bcDecRate=1.0`.
`test.ModelTests`'s `testSimParamsSentinels` hardcoded the old `bc_dec==0.999` default; updated to
`1.0`. Recompiled clean; only the 2 pre-existing, unrelated `p_u`-tag failures remain (present at
`HEAD` before this session, not introduced by this adoption). 3-seed spot check on the freshly
compiled rounded defaults reproduced the expected profile (ratio 1.48/1.50/1.47, assort
0.60/0.66/0.67, Q_sign_repost 0.44/0.45/0.48).

**Net effect on the model going forward:** the calibrated foundation is now *simpler* than what
the 2026-07-18 bc redesign produced -- static, uniform bounded confidence, no decline/recovery
dynamics needed to reproduce Gini/Q_sign_repost/assortativity/SF1 at this operating point. This is
worth stating plainly in any writeup rather than presenting unused machinery as load-bearing.

## Hub-swap causal experiment (2026-07-20): does moderation of the hub specifically matter?

**Design.** Sharpest version of research-direction.md's own named counterfactual ("degree-matched
rewiring without a moderate conduit -- is it the bridge, or just the exposure?"), done more
surgically than a rewiring: same hub, same network, only its opinion changes. Ran one seed
(920000) to equilibrium (n=1000, steps=20000, newly-adopted static-bc defaults) with
`log_gexf=true`, found the natural hub ranking by in-degree -- **the top 3 hubs are all
moderate already** (`agent 3: inDegree=725, opinion=0.123`; `agent 9: 722, 0.175`; `agent 2: 717,
-0.131`), and the most extreme opinions in the top 15 sit at the lowest in-degrees there
(`agent 8: opinion=-0.696, inDegree=272`) -- the moderate-hub pattern emerges naturally, unforced.

Took agent 3 (rank-1 hub, 725/1000 followers) as the swap target. `scripts/swap_hub_opinion.py`
writes a byte-identical copy of the equilibrium GEXF with only agent 3's `opinion` attvalue changed
(`0.1225 -> 0.9`, same sign, more extreme) -- diffed the two files to confirm exactly one line
differs. `network=read` (confirmed via `ReadNetwork.java`/`GephiReader.java` to reconstruct both
topology and every agent's opinion/bc/postProb/accessProb from the GEXF) loads either file as an
identical starting point for both arms.

**Protocol:** `scripts/run_hub_swap_experiment.py` -- CONTROL (hub stays natural/moderate) vs.
TREATMENT (hub swapped to extreme), 10 seeds each, `steps=5000` continuation from the common
snapshot. Measures: global `crossCuttingFraction`/`interactionCrossCuttingFraction`/
`Q_sign_repost`, plus a hub-specific metric computed from each run's own final GEXF -- among agent
3's followers, what fraction are opposite-sign to agent 3 (the direct test of whether the hub's
own moderation vs. extremity changes who it's bridging to). Log:
`docs/report/hub_swap_experiment.csv`.

**Result (agent 3, the mega-hub, 725/1000 followers = 72.5% of the population):** no significant
effect on anything (all t~1.3-1.5). Directionally, extreme was *higher* cross-cutting/*lower*
modularity than moderate -- opposite the naive hypothesis. The sharpest test (hub's own follower
cross-fraction) showed literally no difference (0.4022 vs 0.4007); follower *count* dropped ~10%
(726->654) when swapped to extreme -- the hub loses reach, but its remaining followers' camp mix
doesn't change. Checked whether the hub's own `postProb` explained the direction: it was pinned at
the 1.0 ceiling in both conditions, ruling that mechanism out. **Flagged agent 3 as the wrong tier
to test** -- 72.5% reach means the hub already saturates the network regardless of opinion; not a
"mid-scale conduit" the way research-direction.md's own framing means it.

**Mid-tier follow-up:** found 11 moderate candidates with inDegree in [50,300] from the same
equilibrium snapshot (agents 22/16/40/37/43/69/46/47/67/98/30, opinions all |op|<0.2). Tested
3 individually (agent 22: 153 followers, opinion=-0.014; agent 16: 140, -0.188; agent 40: 96,
-0.0002), 10 seeds each, `steps=5000`, reusing one shared control. Notable baseline finding
(no swap needed): agents 22 and 40 (near-*exact* centrists) already have ~50/50 cross-camp
follower bases (0.507, 0.501); agent 16 (moderate but off-center) has a skewed 0.242 -- suggests
exact centrism, not just falling inside the moderate band, predicts natural bridging position.
Swap-to-extreme (-0.9) result: `crossCuttingFraction` decreased consistently across all 3 hubs
(0.0388->0.0341/0.0357/0.0377) -- opposite direction from the mega-hub, though none individually
significant (t~-0.3 to -1.15). Full polarization panel (`opinionVar`, `bimodalityCoeff`,
`opinionKurtosis`) showed no movement at all; SF1 ratio was mixed (agent22 down, agent16 flat,
agent40 up, none significant).

**Scaled up: 11 hubs simultaneously, 15000 steps, n=10/arm** (`scripts/run_hub_swap_multi11_15k.py`,
log `docs/report/hub_swap_multi11_15k.csv`) -- swapped all 11 candidates at once (each to +/-0.9
preserving natural sign) to raise the "dose." Result: the consistent `crossCuttingFraction` effect
from the individual mid-tier tests *vanished* (0.0286 vs 0.0297, flat); SF1 showed the largest
movement (1.183 vs 1.078, t~-1.4, still n.s.) -- direction consistent with "moderate hubs sustain
higher SF1 via cross-cutting-driven provocation of extremes." **Confound flagged:** hub count
and window length both changed vs. the individual tests, so the vanished ccf effect can't be
attributed to either factor alone.

**Final, properly-powered test: 10 hubs (dropped agent 30, weakest), 20000 steps, n=30/arm**
(`scripts/run_hub_swap_multi10_20k.py`, log `docs/report/hub_swap_multi10_20k.csv`, sequential
execution -- 30 seeds/arm concurrently would be 60 JVMs at once, exceeding both the tested-safe
~30-concurrent range and available RAM). **Result: genuine null.** The SF1 signal that looked
promising at n=10 (diff=-0.105, t~-1.4) *shrank to less than half* at n=30 (diff=-0.043, t~-0.96)
-- the signature of a small-sample fluctuation evaporating under real power, not a real effect
firming up. Every other metric (`crossCuttingFraction`, `interactionCrossCuttingFraction`,
`Q_sign_repost`, `disagreement`, `opinionVar`, `bimodalityCoeff`, `opinionKurtosis`) was already
flat and stayed flat.

**Conclusion (2026-07-20):** across the full sequence (mega-hub; 3 individual mid-tier hubs;
11 hubs/15000 steps; 10 hubs/20000 steps at real power), swapping a moderate hub's opinion to
extreme -- topology held fixed, only opinion changed -- produced no statistically supported causal
effect on cross-cutting exposure or any polarization measure. Caveat before treating this as fully
settled: topology was never allowed to *rewire* in response to the new opinion in any of these
tests (only `network=read`'s starting state changed); unfollow/refollow-driven network
reorganization might need longer than 20000 steps to manifest from a frozen start. As tested, the
honest reporting is a negative result for this specific operationalization of the moderate-conduit
hypothesis, not evidence the hypothesis is confirmed.
