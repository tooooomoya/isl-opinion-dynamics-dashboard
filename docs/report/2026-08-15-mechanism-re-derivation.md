# 2026-08-15 — Mechanism re-derivation: the moderate hub is a tolerance-narrowing insulator, not a conduit

> **Status: this entry supersedes the mechanism account assumed in
> `docs/report/2026-08-07-cna2026-paper-writing-handoff.md` §9 and in the comfort-volume regression
> (`scripts/lmp_feedmech_comfortvol_test2.py`).** Two premises those relied on are refuted by direct
> measurement below. The paper's *empirical* findings (facilitator/mediator effect sizes, the backbone
> effects) are unaffected — what changes is the causal story told about them, and that story is now
> quantitatively supported where it previously was not.

## 0. What prompted this

§9c's direct structural-mediation regression returned R²=0.064–0.168 (density + betweenness variants
predicting the M_silent-minus-control extreme-camp posting-rate difference) — far weaker than the
comfort-volume regression's 0.560, and reproducing none of the p_u-driven vcr crossing shift. Rather
than accept that as "structure doesn't matter," the question was re-opened: **is E↔NE follow density
even the quantity this model's mechanics read?**

The answer is no, and tracing why exposed two false premises.

## 1. Refuted premise #1: the algorithmic-feed pathway is dead in this configuration

`BASE_TOKENS` sets `alpha=0` → `feedAlgoShare=0`. Consequently
`OpinionDynamics.java:295` sets `velocityRanked = null` and `AdminOptim.java:396` gives
`algoSlots = 0`; the entire For-You branch (`AdminOptim.java:419-446`) never executes.

This matters because the algorithmic channel is the *only* place graph topology enters exposure as a
first-class input: `computeReachable()` (`AdminOptim.java:338-361`) runs a true BFS over the follow
graph and `acceptProbability()` (`AdminOptim.java:370-381`) converts hop distance into an acceptance
probability. With `alpha=0`, **none of that runs**. Betweenness centrality — which is only
mechanistically meaningful as a proxy for shortest-path-mediated reach — has no channel through which
to act. Testing it as a mediator was mis-specified from the start.

The surviving delivery path is exclusively: author posts/reposts → delivered to
`admin.getFollowers(author)` → reader's `postCash` FIFO → uniform sample of ≤`chronoSlots` becomes the
feed (`AdminOptim.java:399-417`).

## 2. Refuted premise #2: feeds are starved, so nothing is "displaced"

Measured (`scripts/lmp_feedmech_feedfill_check.py`), extreme-camp readers' trailing-window feed size:

| | vcr=0.1 | vcr=0.15 | vcr=0.2 |
|---|---|---|---|
| control | 2.03 | 2.20 | 2.39 |
| M_silent | 2.27 | 2.46 | 2.65 |

**Against `feed_capacity=15.** Feeds run at 14–20% of capacity; 12+ slots sit empty every step.

This directly refutes the premise stated in `lmp_feedmech_comfortvol_test2.py`'s docstring — "when
feed_capacity is fixed, more near-extreme content filling freed-up slots can mechanically compete with
(displace) own-camp content reaching the same reader." **There is no slot competition.** Content adds
and subtracts freely. Whatever the R²=0.560 regression was capturing, the displacement rationale
offered for it is not supported.

Relatedly, follow capacity is also nowhere near binding: extreme-camp readers carry mean out-degree
2.85 (control) / 6.5–6.8 (M_silent) against `max_follow=43.8638`.

## 3. Refuted premise #3: the moderate hub barely reaches the extreme camp at all

Moderate-authored content in extreme-camp readers' feeds (`feedModCountMean`, trailing window):

| | vcr=0.1 | vcr=0.15 | vcr=0.2 |
|---|---|---|---|
| control | 0.011 | 0.025 | 0.015 |
| M_silent | 0.000 | 0.000 | 0.000 |

That is **0.5%–2.3% of a ~2.0–2.4-item feed**. The direct "moderate content dilutes the extreme camp's
comfort" story cannot account for a comfort-rate gap of −0.005 to +0.027 (§5) — removing 0.01–0.06
items cannot move a ratio that much. **The moderate hub's causal role is not delivery of its own
content.**

Corroborating this, the follow-graph shows extreme readers have already purged the moderate hubs under
control (`scripts/lmp_feedmech_followee_composition.py`):

| E-camp readers' mean # of moderate hubs followed | vcr=0.1 | vcr=0.15 | vcr=0.2 |
|---|---|---|---|
| control | 0.017 / 0.077 | 0.048 / 0.074 | 0.012 / 0.102 |
| M_silent | 3.251 / 3.267 | 3.257 / 3.262 | 3.261 / 3.259 |

(cells shown as p_u=0.05 / p_u=0.15). Under control the moderate hubs are gone; under M_silent they
are retained but silent — inert ties that deliver nothing and, since capacity does not bind, crowd out
nothing.

## 4. The mechanism that IS supported: tolerance-narrowing, not conduction

Moderate-hub content (pinned opinion 0.0) is out-of-`bc` for essentially every extreme-camp agent. Two
consequences follow from the agent code:

- `unfollow()` (`Agent.java:619-643`) fires block+unfollow at probability `p_u` on any out-of-bc
  followee post — this purges the moderate hubs themselves (§3's table).
- `bc` relaxes toward a target set by the step's in-tolerance feed fraction, narrowing faster than it
  widens. Persistent out-of-bc moderate content therefore **holds `bc` narrow**.

Because `follow()` (`Agent.java:547-596`) recruits new ties *only* from in-bc feed content while
`unfollow()` blocks on out-of-bc content, `bc`'s level governs whether near-extreme (NE) authors become
follow candidates or block triggers. Measured `bc` among extreme-camp non-hub agents
(`scripts/lmp_feedmech_bc_gate_check.py`), M_silent minus control:

| bc_mean diff | vcr=0.1 | vcr=0.15 | vcr=0.2 |
|---|---|---|---|
| p_u=0.05 | +0.0137 | +0.0118 | +0.0135 |
| p_u=0.15 | +0.0369 | +0.0316 | +0.0310 |

Silencing the moderate hub widens `bc`, and **the gap is ~2.6× larger at p_u=0.15** — matching the
~3× ratio in the downstream NE-influx gap (§5).

> **Correction to an intermediate framing.** A "bc > 0.6 gate" was floated while forming this
> hypothesis (0.6 = distance from an extreme agent at ±1.0 to a near-extreme hub at ±0.4) and is
> **wrong**; it is retained here only so the reasoning is auditable. Measured bc_mean is 0.27–0.35
> (`bc_floor=0.2`), and only 0.1–1.2% (control) / 1.1–5.6% (M_silent) of extreme agents exceed 0.6.
> The error was treating camp membership as a point value: class 4 spans opinion [0.6, 1.0] and class 3
> spans [0.2, 0.6], so extreme-to-NE distance ranges from ~0 (both near the shared boundary) to 1.4.
> `bc` acts as a **graded window over that distance distribution**, not a sharp threshold. The
> directional predictions survive; the threshold framing does not.

## 5. The sign flip and the p_u × vcr crossing shift, explained

Extra NE-authored content reaching extreme readers (M_silent − control), and the share of it that
registers as within-`vcr` "comfortable" (`scripts/lmp_feedmech_mechanism_test.py`):

| | vcr=0.1 | vcr=0.15 | vcr=0.2 |
|---|---|---|---|
| p_u=0.05 — NE influx | +0.134 | +0.139 | +0.156 |
| p_u=0.05 — comfortable share | 1.2% | 20.6% | 38.2% |
| p_u=0.15 — NE influx | +0.434 | +0.375 | +0.436 |
| p_u=0.15 — comfortable share | 1.2% | 9.7% | 27.0% |

Comfort rate is `comfortPostNum / postNum` per agent (`Agent.java:421`), feeding `targetPostProb`
(`Agent.java:445`). Extra NE content **always** enters the denominator but enters the numerator only
once `vcr` is wide enough to make it comfortable. Hence:

- **low `vcr`** → 98.8% of the influx is uncomfortable → comfort rate falls → extreme camp posts less
  (the *facilitator* regime: the active moderate hub is associated with **more** extreme posting)
- **high `vcr`** → a third of the influx is comfortable → comfort rate rises → extreme camp posts more
  (the *mediator* regime)

`p_u` shifts the crossing point because it sets **how much** extra NE content arrives (~3× more at
p_u=0.15) **and** how uncomfortable it is. The latter has a structural explanation: of the extra NE
ties, the share going to *pinned hubs* (fixed at exactly ±0.4, the far edge of the NE band, hence
rarely within `vcr`) is 47% at p_u=0.05 but **68%** at p_u=0.15 — computed from
`lmp_feedmech_followee_composition.py`'s hub_NE vs pop_class1/pop_class3 diffs. A bigger and
systematically more-distant influx needs a wider `vcr` to be outweighed → crossing moves right.

## 6. Quantitative confirmation

Per-seed regressions, n=90 (15 seeds × 2 `p_u` × 3 `vcr`), predictor and response both
M_silent-minus-control:

| model | R² |
|---|---|
| **outcome ~ d_cRate** (per-agent comfort rate) | **0.852** |
| outcome ~ d_own_comfort + d_ne_comfort | 0.375 |
| outcome ~ d_ne_comfort + d_ne_total | 0.306 |
| outcome ~ d_density + d_bc_undir (§9c structural) | 0.143 |
| outcome ~ d_cRate + d_density + d_bc_undir | 0.857 |

**Comfort rate alone explains 85% of the outcome variance, and adding the structural metrics on top
contributes +0.005.** Structure's influence is fully mediated through comfort rate; there is no
residual direct structural effect. This retro-explains §9c's null result: it was not a bad choice of
structural index, it was a test for an arrow the model does not contain.

Crossing-point reproduction (the test the volume regression failed):

| | p_u=0.05 | p_u=0.15 | shift |
|---|---|---|---|
| outcome | vcr=0.141 | vcr=0.199 | 0.058 |
| d_cRate | vcr=0.115 | vcr=0.178 | **0.063** |
| comfort-volume regression (prior) | ~0.18 | ~0.18 | **0.00** |

Absolute positions are offset by ~0.025, but the **p_u-driven shift is reproduced almost exactly**.

### Methodological note carried forward

Comfort rate must be aggregated as a **mean of per-agent ratios**, not a ratio of summed feed counts.
An intermediate pass used the latter and obtained a uniformly negative gap (−0.05 to −0.14) at every
cell, i.e. **no sign flip at all** — because it implicitly weights agents by feed size.
`Analysis.java:563-565` aggregates correctly (`cRateMean_i`), and that is what reproduces the crossing.
This is the same ratio-of-means hazard the handoff already flagged for §9b's `p_u` contrast; it has now
bitten twice in this project.

## 7. Consequences for the paper

1. **The "conduit"/"mediate" framing is not what the model does.** The moderate hub does not carry
   content between camps — it reaches the extreme camp with 0.5–2.3% of their feed and is purged
   within the run. Its causal role is to **keep the extreme camp's tolerance narrow**, which keeps
   their feeds own-camp-pure and therefore comfortable. Framing to consider: *moderate hubs as
   tolerance-narrowing insulators*, whose removal exposes the extreme camp to near-extreme content.
2. **The facilitator effect gains a mechanism.** "Active moderate hub → more extreme-camp posting" is
   now explicable: narrow tolerance → NE content excluded → high comfort → high posting. This is a
   stronger position than the current draft's, which asserts a mechanism without quantitative backing
   (§9's item 2).
3. **§9's planned Discussion sentence citing the 12–15%/16–36% density numbers should not be written
   as a causal claim.** Those density contrasts are real (re-derived on the final grid — see §9b
   output in `logs/lmp_feedmech_structural_9b_stdout.log`), but §6 shows density carries no
   independent explanatory weight once comfort rate is in the model. Cite it, if at all, as a
   *correlate* of the tie-formation shift, not as the operative channel.
4. **`vcr`'s interpretive load increases.** The sign of the whole effect is set by whether influxed NE
   content falls inside `vcr`. Since `vcr` has no empirical calibration anchor in this project
   (handoff §2), this should be stated plainly as the paper's principal parameter sensitivity.

## 8. What is measured vs. what is inferred

**Measured directly:** feed starvation (§2); moderate-content share and hub purging (§3); bc gap and
its p_u scaling (§4); NE influx, comfortable share, and hub-vs-population composition of new NE ties
(§5); all regressions and crossing points (§6).

**Inferred, not directly proven:** the specific causal link *narrower bc → fewer NE authors qualify as
follow candidates → fewer NE ties*. The endpoints are measured (bc differs; NE ties differ, in the
predicted direction, with matching p_u scaling), but the intervening step — that the tie-formation
rate responds to bc in the manner described — has not been instrumented. A targeted check would log
`follow()` candidate-set composition per step by author class. Worth doing before this story is
committed to the paper's Discussion as a claim rather than an interpretation.

## 9. Scripts

All under `scripts/`, all read the already-completed
`results/2026-08-14_lmp_feedmech_structural_9b/` grid (no new simulation runs needed):

- `lmp_feedmech_structural_9b.py` — the §9b grid launcher + density/betweenness report. Now caches
  per-seed structural metrics to `structural_metrics_9b.json` inside each run dir (betweenness is
  ~10 s/seed; the cache makes repeat analysis passes instant).
- `lmp_feedmech_structural_9c.py` — §9c structural-mediation regression (the null result).
- `lmp_feedmech_followee_composition.py` — followee-set composition of extreme-camp readers.
- `lmp_feedmech_feedfill_check.py` — feed fill level and composition. **Its "COMFORT RATIO" block uses
  the incorrect ratio-of-sums aggregation** (see §6's note); read `lmp_feedmech_mechanism_test.py` for
  the correct per-agent figures.
- `lmp_feedmech_bc_gate_check.py` — bc distribution among extreme-camp agents. **Its docstring's
  "0.6 gate" framing is refuted** (see §4's correction box); the measurements themselves stand.
- `lmp_feedmech_mechanism_test.py` — the decisive test (§5, §6).

Logs: `logs/{followee_composition,feedfill_check,bc_gate_check,mechanism_test}.log`.

---

# ADDENDUM (same day) — trajectory analysis corrects §4 and §6 above

Two user critiques, both correct, forced a revision. **Read this addendum as authoritative over §4–§6.**

## A1. Retracted: the R²=0.852 comfort-rate result is tautological, not a finding

§6 presented `outcome ~ d_cRate` (R²=0.852) as decisive evidence for a mechanism. It is not.
`Agent.java:445` computes `targetPostProb = minPostProb + (maxPostProb - minPostProb) * comfortPostRate`
— comfort rate is the **only** free variable in the sole equation governing posting probability. A high
R² between it and a posting-rate outcome is guaranteed by construction and carries no mechanistic
information. What the number legitimately supports is narrow and technical: that per-agent aggregation
(`cRateMean_i`) is the correct estimator and feed-size-weighted ratio-of-sums is not (§6's
methodological note stands). The comparison against the structural regression's R²=0.143 is likewise
uninformative, since the structural metrics were never in the update equation to begin with.

## A2. Retracted: "moderate content holds bc narrow" is not a sustained mechanism

The critique: extreme-camp readers follow only 0.017–0.102 moderate hubs at step 40000 — already
purged — so moderate posts cannot keep suppressing `bc` thereafter. The trajectory
(`scripts/lmp_feedmech_trajectory.py`, `logs/trajectory.log`, vcr=0.1, 8 seeds) confirms this:

| moderate hubs followed by E readers | step 0 | 5000 | 10000 | 20000 | 40000 |
|---|---|---|---|---|---|
| control, p_u=0.05 | 3.020 | 0.064 | 0.016 | 0.002 | 0.008 |
| control, p_u=0.15 | 3.020 | 0.074 | 0.065 | 0.069 | 0.057 |
| M_silent (either) | 3.020 | ~3.02 | ~3.02 | ~3.02 | ~3.02 |

**The purge completes before the first checkpoint.** Moderate-authored content in extreme readers'
feeds decays accordingly at p_u=0.05 (1.588 → 0.668 → 0.234 → 0.037 → 0.005, monotone), so the
"sustained suppression" framing is dead there.

One qualification, which is a genuine observation and not a rescue of the old story: at **p_u=0.15 the
moderate content does not decay to zero but plateaus** (0.932 → 0.136 → 0.082 → 0.059 → 0.055 → 0.056,
flat from bin 10000 onward), tracking a persistent 0.057–0.080 moderate hubs still followed. Why a
*higher* unfollow probability leaves *more* moderate ties intact is **unexplained** — candidate
explanations (lower encounter rate in a more aggressively pruned feed; agents carrying moderate ties
with them as their own opinion drifts into the extreme class) are untested speculation and are flagged
as such.

## A3. The corrected mechanism: an early perturbation that selects between self-reinforcing basins

`bc` collapses from 0.800 to ~0.21 in **every** condition by step 5000, then slowly recovers
(`bc_recovery=0.0001`/step). Blocking is concentrated in the same early window — population blockCount
per step falls from 2.42–5.25 in the first bin to ~0.02 by the end — and **blocks are permanent**. So
the follow network's fate is largely settled during the first few thousand steps, and what happens
afterwards is slow relaxation within the structure that window left behind.

| bc (mean over E readers) | 5000 | 10000 | 20000 | 40000 |
|---|---|---|---|---|
| control p_u=0.05 | 0.204 | 0.209 | 0.229 | 0.276 |
| M_silent p_u=0.05 | 0.212 | 0.219 | 0.240 | 0.286 |
| **DIFF** | +0.008 | +0.010 | +0.010 | **+0.010 (flat)** |
| control p_u=0.15 | 0.213 | 0.222 | 0.246 | 0.294 |
| M_silent p_u=0.15 | 0.239 | 0.252 | 0.280 | 0.335 |
| **DIFF** | +0.026 | +0.030 | +0.034 | **+0.041 (growing)** |

The arm gap opens by step 5000 in both rows. What differs is what happens next:

- **p_u=0.05 — transient, then locked in.** The gap is set early and stays flat (+0.010) for 35,000
  steps. Near-extreme ties keep eroding in both arms (control 1.887→0.374, M_silent 1.519→0.581).
- **p_u=0.15 — transient, then amplified.** The gap grows monotonically (+0.026→+0.041), and
  **M_silent@p_u=0.15 is the only condition where near-extreme ties stop eroding** (1.056→0.972,
  roughly flat) while every other condition decays by 4–5×.

The amplification is a positive feedback: wider `bc` → more near-extreme content is in-tolerance →
not blocked, and eligible as a `follow()` candidate → near-extreme ties survive → the in-tolerance
share of the feed stays high → `bc`'s relaxation target stays high → wider `bc`. `p_u` sets the loop
gain, because it governs how fast out-of-tolerance sources are *permanently* removed, which is exactly
what determines the in-tolerance share.

**So the moderate hub is not maintaining anything.** Its content perturbs the system during the
formative window — adding out-of-tolerance encounters that both consume blocking draws and depress the
`bc` relaxation target — and that perturbation selects which basin the run settles into. Everything
after ~step 5000 is the consequence, not the cause. This is path dependence, not ongoing suppression.

This also supplies the structural account of `p_u` the user anticipated: `p_u` is not simply
"more separation." Higher `p_u` purges out-of-tolerance sources faster, which *raises* the in-tolerance
share and hence *widens* `bc` (control 0.276→0.294, M_silent 0.286→0.335 going from p_u=0.05 to 0.15) —
self-purification. Its effect on the extreme camp's exposure to near-extreme content is therefore
**arm-dependent**, which is why the near-extreme influx moves in opposite directions with `p_u` in the
two arms (control 0.079→0.060, M_silent 0.213→0.494 at vcr=0.1).

## A4. The sign flip is visible in time, not just across vcr

The M_silent-minus-control gap in comfort rate (and postProb) starts **positive** and crosses to
negative during the run:

| cRateMean DIFF (bin) | 0 | 2000 | 6000 | 10000 | 20000 | 38000 |
|---|---|---|---|---|---|---|
| p_u=0.05 | +0.043 | +0.069 | +0.030 | +0.009 | −0.000 | −0.003 |
| p_u=0.15 | +0.030 | +0.018 | +0.003 | −0.006 | −0.014 | −0.019 |

Crossing occurs around step 15,000–20,000 at p_u=0.05 but 6,000–10,000 at p_u=0.15. The trailing-window
outcome the paper reports is therefore a **late-time reading of a non-monotone trajectory**, and the
same run would report the opposite sign if measured at step 5,000. This is consistent with — and
sharpens — the handoff's §9 item 6 note about divergence at steps 5000–15000 that "loses significance
by conventional thresholds later even as the raw gap keeps growing."

## A5. What the paper can and cannot say now

- **Keep:** "the moderate hub's activity governs whether near-extreme content flows into the extreme
  camp's feeds." That is the user's existing claim and it is well supported (near-extreme influx
  differs by +0.12 at p_u=0.05 and +0.55 at p_u=0.15, established early and sustained).
- **Fix wording:** it is an **influx**, not a replacement/displacement. Feeds run at 2.0–3.0 of 15
  slots, so nothing is displaced (§2).
- **Do not write:** that moderate content continuously suppresses the extreme camp's tolerance. It
  acts in the first few thousand steps and is gone (A2).
- **Do not write:** the R²=0.852 comfort-rate figure as evidence of mechanism (A1).
- **Newly available, if the framing is wanted:** the effect is path-dependent — an early, transient
  perturbation selecting between self-reinforcing structural basins, with `p_u` as the loop gain. This
  is a stronger and more distinctive claim than the conduit story, but it rests on a single vcr level
  (0.1) and 8 seeds so far; it needs the same trajectory run across the full grid before it goes in.

## A6. Still not closed

The link *narrower bc → fewer near-extreme authors qualify as `follow()` candidates → fewer ties*
remains inferred, not instrumented (as flagged in §8). The trajectory strengthens the circumstantial
case — bc and tie counts move together, with matching p_u scaling and the right time ordering — but
logging `follow()`'s candidate set by author class is still the direct test.

Script: `scripts/lmp_feedmech_trajectory.py`. Log: `logs/trajectory.log`.

---

# ADDENDUM 2 — "is the near-extreme camp inside the extreme camp's echo chamber?"

User framing (2026-08-15): the self-purification result (higher `p_u` → wider `bc`) is echo-chamber
formation seen from another angle; `vcr` and `p_u` both gate *how far out still counts as homophilic*;
so when NE falls inside E's gate, NE→E influx should rise. Measured across the full grid at 5
checkpoints. Scripts: `lmp_feedmech_chamber_gate.py`, `lmp_feedmech_chamber_gate_wt.py`.
Logs: `logs/chamber_gate.log`, `logs/chamber_gate_wt.log`, `logs/gate_influx_test.log`.

## B1. The circularity constraint, and why three of five measures failed it

With `alpha=0`, influx arrives only through follow edges, so any chamber measure defined on E→NE ties
makes "chamber → influx" true by construction. Measures were built to avoid that. Three still failed,
for two distinct reasons.

**Failure mode 1 — the treatment intervenes directly on tie survival.** Unfollow fires only on an
out-of-tolerance *encounter*, so a hub that posts nothing is never encountered and never purged.
Extreme readers therefore retain ~3.26 moderate hubs under M_silent vs ~0.01–0.10 under control. Those
ties are inert (moderate-hub `postProb`: 0.966 control, **0.010** M_silent) but unweighted network
measures count them at full strength. The damage is large and direction-dependent:

| `src_overlap_third`, M_silent − control | unweighted | activity-weighted | artifact share |
|---|---|---|---|
| p_u=0.05 | +0.458 | **+0.008** | **98%** |
| p_u=0.15 | +0.450 | **+0.073** | **84%** |

**This is a general hazard for this experimental design, not a quirk of one metric:** silencing
changes tie *survival*, not just content, so the treatment mechanically moves any structural index.
**§9a's plan to define the structural layer as E↔NE follow density inherits exactly this problem.**
Activity weighting (by `postProb`) is required for any structural measure used in the paper.

**Failure mode 2 — partition degeneracy.** `louvain_comembership` came out *higher* under control
(+0.21 vs +0.10), the opposite sign to every other measure, and activity weighting did not fix it.
Modularity explains why: Q = 0.30–0.40 (control) vs 0.57–0.60 (M_silent). Control's network is too
sparse to resolve, so Louvain lumps the camps into one weak community; the high co-membership reflects
an unresolved partition, not a shared chamber. It also has **R²=0.000** against influx. Disqualified.

`src_overlap_pop` (hubs excluded structurally) is clean but measures a channel carrying only 10–20% of
feed content (hub-authored content is 1.80–2.35 of a 2.0–2.9-item feed), and disagrees with the others
(sign flips with `p_u`). Not usable either.

**Surviving measures: `bc_inclusion` (Layer 1, graph-independent) and `src_overlap_third_wt`.**

## B2. The two gates are not one quantity

| M_silent − control, vcr=0.1, step 40000 | p_u=0.05 | p_u=0.15 | ratio |
|---|---|---|---|
| `bc_inclusion` (structural gate) | +0.015 | +0.078 | 5.2× |
| `src_overlap_third_wt` (corrected) | +0.008 | +0.073 | 9× |
| NE influx (the explanandum) | +0.12 | +0.55 | 4.5× |

Three independently-defined quantities move in the same order with comparable ratios. But the two
gates behave completely differently in absolute terms:

- **structural gate (`bc_inclusion`)**: collapses 1.000 → 0.13 by step 5000, then recovers to
  0.20–0.36; strongly treatment- and `p_u`-dependent.
- **perceptual gate (`vcr_inclusion`)**: 0.035 → 0.026–0.028 and **flat thereafter; arm difference
  ±0.002**. It is effectively a constant fixed by `vcr` and the opinion distribution.

So `vcr` does **not** move "how far out counts as homophilic" over the run. It is a fixed post-hoc
filter on whether influxed content registers as comfortable. This is why the comfortable share of NE
influx was 1.2% in *both* `p_u` rows at vcr=0.1 — a structural necessity, not a coincidence.
**Division of labour: `p_u` sets how much near-extreme content arrives; `vcr` sets the sign of its
effect.**

## B3. Gate width predicts influx — but is not sufficient

Levels, 180 runs, both arms pooled, step 40000 (non-circular: `bc_inclusion` never touches the graph):

| model | R² |
|---|---|
| **ne_influx ~ bc_inclusion** | **0.527** |
| ne_influx ~ bc_inclusion + src_overlap_third_wt | 0.649 |
| ne_influx ~ src_overlap_third_wt | 0.262 |
| ne_influx ~ vcr_inclusion | 0.109 |
| ne_influx ~ louvain_comembership_wt | 0.000 |

The limit is visible in the cell means (vcr=0.1):

| | bc_inclusion | NE influx |
|---|---|---|
| p_u=0.05 **M_silent** | 0.2160 | **0.2130** |
| p_u=0.15 **control** | **0.2306** | **0.0603** |

**A wider gate with 3.5× less influx.** The residual 47% is systematic and arm-linked, not noise:
blocks are permanent, so an open gate cannot readmit an already-blocked source. The operative
statement is therefore

> influx ≈ f(gate width **×** how much of the near-extreme camp is still unblocked),

and the second factor is set by the early transient (Addendum 1, A3), not by the current gate.

## B4. Opinion geometry is static

`ene_dist_p10` (10th percentile of same-sign |o_E − o_NE|, the distance bc must exceed) moves only
0.169 → 0.182–0.189, arm difference ±0.006. The camps neither converge nor separate. Whether they
share a chamber is governed by **tolerance and history**, not by opinion movement — which is worth
stating explicitly in the paper, since "polarization" is usually read as camps moving apart.

## B5. Usable for the paper

- **§9a's operational definition should be revised**: structural layer = `bc_inclusion` (share of the
  same-sign near-extreme camp inside an extreme agent's bc window), perceptual layer =
  `vcr_inclusion`. Both are opinion-space quantities, immune to the tie-survival artifact that
  disqualifies follow-density and community-based indices under this treatment design.
- **Reportable**: `bc_inclusion` explains 53% of near-extreme influx (65% with the corrected overlap),
  non-circularly; `vcr_inclusion` is flat and treatment-invariant; Louvain co-membership is
  uninformative here (R²=0.000, Q-confounded).
- **Must be stated**: gate width is necessary, not sufficient — same gate, 3.5× influx difference.
- **Caveat**: all of B2–B4 is step-40000 cross-section plus 5 checkpoints on the existing 15-seed
  grid. No new runs; nothing here needs any.

## B6. The `vcr` sweep IS a direct manipulation of the perceptual gate (interpretation for the heatmap)

Because `vcr_inclusion` is flat in time after ~step 5000 and nearly treatment-invariant (B2), sweeping
`vcr` sets the perceptual gate directly rather than perturbing something that then equilibrates. The
swept range maps to:

| `vcr` | perceptual gate = share of same-sign NE camp inside `vcr` | drift from t=0 |
|---|---|---|
| 0.1 | **2.6%** | 3.53% → 2.6% |
| 0.15 | **6.5%** | 7.91% → 6.5% |
| 0.2 | **12.0%** | 14.00% → 12.0% |

A 4.6× span, monotone and roughly doubling per step. Drift settles by step 5000 (the extreme camp
polarises slightly toward ±1.0, lengthening E–NE distances) and is flat thereafter; the arm difference
never exceeds 0.011 (<10% relative), against `bc_inclusion`'s 5–38% relative treatment effect.

**Design consequence:** the two heatmap axes are asymmetric in kind — `vcr` is a *directly set*
perceptual gate, `p_u` an *indirect, emergent* structural gate operating through bc with feedback and
path dependence (A3, B3). Worth stating explicitly rather than presenting them as two comparable
"parameters."

**Refinement (do not overstate the mapping).** `vcr_inclusion` is computed against a *uniform* sample
of the near-extreme camp. Realised influx is not uniform, because `follow()` recruits only from in-bc
content and therefore selects systematically closer near-extreme sources:

| `vcr` | uniform gate | realised comfortable share of influx, p_u=0.05 | p_u=0.15 |
|---|---|---|---|
| 0.1 | 2.6% | 1.2% | 1.2% |
| 0.15 | 6.5% | **20.6%** | 9.7% |
| 0.2 | 12.0% | **38.2%** | 27.0% |

At p_u=0.05 the realised share runs ~3× above the uniform gate; the selection is weaker at p_u=0.15,
where 68% (vs 47%) of the extra near-extreme ties go to hubs pinned at exactly ±0.4, i.e. the far edge
of the band. So: **`vcr` fixes the gate width; the composition being filtered is set by which sources
cleared the structural gate.**

**Useful for the write-up:** this partly answers handoff §2's concern that `vcr` has no empirical
calibration anchor. It cannot be calibrated to data here, but it *can* be reported in interpretable
terms — "at vcr=0.1 only ~2.6% of the adjacent camp is expressively comfortable" — which is far more
legible to a reader than a bare radius in opinion units.

---

# ADDENDUM 3 — decomposing M-active's suppression effect: origin vs. amplification

**User critique (correct):** Addendum 1's claim "moderate content holds bc narrow" risked being circular —
stating the M_silent-vs-control bc gap as "the mechanism" is just the same fact restated unless the gap
itself can be traced to something measurable and independent of the tie-count/influx outcome it's meant
to explain. The user's preferred, more defensible framing: M-active's effect is that it suppresses
NE→E influx relative to the M-silent counterfactual, full stop — no need to route through an
unverified "bc gap" claim. Asked: can the bc-gap story be checked against real numbers, and if so, does
it decompose into distinguishable contributions?

## C1. The exact formula, and why it is checkable non-circularly

`Agent.java:410-417`: `targetBC = bcFloor + (bcCeiling-bcFloor) * inBcRate`, where
`inBcRate = assimNum/postNum` (`Agent.java:339-350`) — `assimNum` counts feed posts within `bc`,
`postNum` counts all feed posts, evaluated fresh each step. Because moderate-hub content (pinned at
0.0) is always out-of-bc for an extreme reader (bcDist ≈ 0.6–1.0, versus measured `bc` never exceeding
~0.4), it contributes to `postNum` but **never** to `assimNum` — a certain, not estimated, fact. This
makes a purely algebraic counterfactual checkable without needing to know `assimNum`'s absolute value:
removing M's count `M` from the denominator changes `inBcRate` by a factor of `P/(P-M)`, i.e. a
relative rise of `M/(P-M)` — computable directly from already-logged `feedChronoCountMean_i` (≈`P`)
and `feedModCountMean_i` (≈`M`), independent of the tie-count outcome being explained.

## C2. M's early feed share is large enough to matter

`scripts` one-off (`logs/early_dilution_check.log`), control arm, vcr=0.1, 1000-step bins:

| bin | p_u=0.05: M share | mechanical Δ(inBcRate) | p_u=0.15: M share | mechanical Δ(inBcRate) |
|---|---|---|---|---|
| 0–1000 | 43.0% | **+75.5%** | 41.2% | **+70.1%** |
| 1000–2000 | 41.3% | +70.2% | 22.1% | +28.4% |
| 2000–3000 | 32.8% | +48.9% | 11.2% | +12.6% |
| 3000–4000 | 22.1% | +28.4% | 7.0% | +7.5% |
| 5000–6000 | 7.0% | +7.5% | 4.4% | +4.6% |

Moderate-hub content is **40%+ of the extreme camp's feed in the first 1000 steps** (before any
purge has happened — hubs start highly-followed by construction). The implied mechanical depression of
`inBcRate` (70–76% relative, in the arm where M is active but not yet purged) comfortably exceeds the
eventual observed `bc` gap at step 5000 (+3.9% relative at p_u=0.05, +12.2% at p_u=0.15, from Addendum
1 §A3's trajectory table) — there is ample "raw material" for the dilution channel to plausibly account
for the gap's *origin* on its own.

## C3. But dilution alone does not explain why the gap is BIGGER at higher p_u

The decay rate itself is diagnostic: at p_u=0.15, M's feed share collapses far faster (41%→22%→11% by
bin 2000) than at p_u=0.05 (43%→41%→33% — still in the 20s by bin 3000), because higher `p_u` purges M
faster. **If dilution size/duration alone governed the resulting `bc` gap, p_u=0.15 — with a shorter
dilution window — should produce a *smaller* gap, not the observed larger one** (+12.2% vs +3.9%
relative at step 5000). This is the opposite of what dilution-only would predict.

**Resolution:** two distinct channels, not one, and not circular restatements of each other:

1. **Origin (dilution, `p_u`-independent in kind, verified above):** M's own out-of-bc content is
   ~40%+ of the earliest feed, purely mechanically depressing `inBcRate`'s target for however long M
   remains present — large enough on its own to open a `bc` gap between arms.
2. **Scaling with `p_u` (amplification, established in Addendum 1 §A3, not re-derived here but now
   correctly attributed): once *any* initial gap exists, the self-reinforcing loop — wider `bc` → more
   near-extreme content in-tolerance → not blocked, eligible as a `follow()` candidate → surviving ties
   keep the in-tolerance share elevated → `bc`'s target stays elevated — has a gain set by `p_u` (how
   fast out-of-tolerance sources are permanently pruned, which sets how quickly the surviving
   population's in-tolerance share rises). This loop, not the dilution episode's own size, is what
   the p_u=0.05-vs-0.15 gap difference should be attributed to.

## C4. Not yet quantified

`unfollow()` (`Agent.java:619-643`) draws once per agent per step (gated by a single `p_u` coin flip)
and, on success, blocks only the *first* followed out-of-bc post it encounters in that step's
(already-shuffled) feed, then returns — at most one block per agent per step. Moderate-hub content
therefore also competes with any other out-of-tolerance followee for that step's single blocking slot,
a mechanism distinct from `inBcRate` dilution (it affects tie survival directly, not via bc's target).
Not quantified here; not needed to explain the observed gap given C2's dilution channel already
supplies sufficient magnitude, but a candidate secondary contributor if the numbers are revisited.

## C5. Recommended framing for the paper

Prefer the user's simpler, fully-verified headline claim — "moderate-hub activity suppresses
near-extreme-camp influx relative to the moderate-silent counterfactual, keeping the extreme camp's
feed comparatively pure" — as the primary statement, since it rests only on directly measured
quantities. If the `bc` mechanism is explained at all, state it as two distinct, non-circular pieces:
(a) moderate-hub content's large early feed share mechanically depresses the in-tolerance ratio that
sets `bc`'s target (verified algebraically, C2), and (b) the resulting gap is then amplified by a
`p_u`-gained feedback loop (Addendum 1 §A3) — do not conflate the two into a single "bc gap" claim, and
do not present (a) as explaining the *size* of `p_u`'s effect, which C3 shows it does not.

Script: the one-off computation in this addendum is not yet saved as a standalone script (ad hoc,
`python3 -c` invocation logged to `logs/early_dilution_check.log`); promote to a script if reused.

---

# ADDENDUM 4 — which mechanism explains the OUTCOME HEATMAP's effect sizes: dilution or amplification?

**User question:** of Addendum 3's two mechanisms (C2 dilution/origin, C3 amplification/feedback-loop),
which one explains the *magnitude* of the facilitator/mediator effect in the final outcome heatmap
(not just the `bc` gap it was derived from)? Answered directly from already-established numbers, no
new computation.

## D1. Lining up the three quantities along the `p_u` axis (vcr=0.1)

| quantity | p_u=0.05 | p_u=0.15 | ratio (0.15/0.05) |
|---|---|---|---|
| dilution magnitude (M's feed share, bin 0, Addendum 3 §C2) | 43.0% | 41.2% | **0.96×** (flat/slightly down) |
| amplification proxy (`bc_inclusion` gap, step 40000, Addendum 2 §B2) | +0.015 | +0.078 | **5.2×** |
| NE-influx gap (`NE_total`, mechanism_test.log P3) | +0.134 | +0.434 | **3.2×** |
| **outcome effect size** (facilitator strength, mechanism_test.log P1) | −0.014 | −0.030 | **2.1×** |
| crossing point (vcr) | 0.141 | 0.199 | shift = 0.058 |

## D2. Verdict

**Dilution's own magnitude is p_u-invariant** (43.0% vs 41.2% at the earliest checkpoint — the two
`p_u` rows start from essentially the same initial feed-share depression; what differs between them is
only how *fast* it decays, which if anything predicts a smaller downstream effect at high `p_u`, given
the shorter exposure window established in Addendum 3 §C3). If dilution alone governed effect size,
the two `p_u` rows should produce comparable facilitator magnitudes. They do not (2.1× apart).

**Amplification scales with `p_u` in the same direction and comparable order of magnitude as the
outcome effect itself** (5.2× on `bc_inclusion`, 3.2× on realized NE influx, 2.1× on the final posting-
rate outcome — a sensible attenuating cascade as the signal passes through the downstream comfort
gate). **The amplification mechanism (the self-reinforcing, `p_u`-gained feedback loop of Addendum 1
§A3 / Addendum 3 §C3) is what governs how strongly the facilitator/mediator effect scales across the
heatmap's `p_u` axis. Dilution explains only why an effect exists at all (Addendum 3 §C2), not why it
is stronger at higher `p_u`.**

## D3. The `vcr` axis is governed by neither

Neither dilution nor amplification is a `vcr`-axis mechanism — both operate on the structural
(`bc`-mediated) gate, which (Addendum 2 §B2) is nearly `vcr`-invariant in the sense that matters here.
The regime-shift (sign flip) along `vcr` is governed by the separate, third mechanism already
established: the comfort gate (`vcr_inclusion`), essentially flat with respect to `p_u` and the arm.

## D4. Summary table for the paper

| heatmap axis | what it controls | governing mechanism |
|---|---|---|
| `p_u` (effect strength) | how much the facilitator/mediator magnitude grows | **amplification** — self-reinforcing tolerance-preservation loop, gain set by `p_u` |
| `vcr` (regime sign) | whether the effect is facilitator or mediator | **comfort gate** (`vcr_inclusion`) — independent of both bc mechanisms |
| (background) | that any effect exists at all | dilution — moderate-hub content's large early feed share, but explains only the origin, not the scaling |

---

# ADDENDUM 5 — reframing the paper's mediator/facilitator paragraph, and a plain-language glossary
# for the two mechanisms in Addenda 3–4

**Status note (2026-08-15, end of session): the user has explicitly said their own interpretation has
not caught up with the pace of today's findings.** This addendum is saved as a working memo to resume
from, not a finished conclusion — cross-check every claim below against `results/` before it goes into
the paper.

## E1. The draft's current mediator/facilitator sentence is imprecise, and should be replaced

**Current draft language:** "moderate hubs act as a mediator when the extreme camp can be considered
homophilic to the near-extreme camp, and act as a facilitator when considered heterophilic to the
near-extreme camp."

**Why this doesn't hold up against today's numbers.** If a single homophily/heterophily *state*
between the two camps governed the regime, some measure of that state should predict the outcome
heatmap's regime (facilitator vs. mediator) well. The best-available, non-circular candidate,
`bc_inclusion` (Addendum 2's structural gate), predicts the *volume* of near-extreme content reaching
the extreme camp well (R²=0.527, established two turns before Addendum 5 in-session) but predicts the
*outcome itself* poorly (R²=0.033–0.054, same turn). A single-state homophily variable cannot be doing
the explanatory work the sentence claims.

**The corrected two-gate picture (already in Addenda 2–4, restated here as the replacement frame):**

1. Silencing the moderate hub always increases near-extreme content flowing to the extreme camp,
   in every grid cell measured (§4 of the "M-silentの効果" turn, and Addendum 2 §B1's confirmed
   direction) — not a state-dependent, conditional fact, but the design's constant.
2. **The *openness gate*** — how much of that flow gets through at all — is set by `p_u`, via the
   `bc`-mediated self-reinforcing loop (glossary, §E3 below), not by any fixed camp-level homophily.
   It is graded and dynamically emergent, not a binary state.
3. **The *comfort gate*** — whether the flow that gets through registers as expressively comfortable —
   is set by `vcr`, nearly invariant to `p_u`, `arm`, and time (Addendum 2 §B2).
4. The facilitator/mediator regime shift is which side of the comfort gate's threshold the openness
   gate's (p_u-scaled) flow lands on — a product of two independently-varying gates, not a single
   homophily axis.

**Proposed replacement paragraph** (from the "M active framing is hard" turn, reproduced verbatim as
drafted, not yet re-verified against a fresh read of the numbers):

> The regime shift is not organized by a single homophily/heterophily state between the extreme and
> near-extreme camps. Rather, two largely independent gates operate in sequence: an *openness gate*,
> set by `p_u` through a self-reinforcing, path-dependent tolerance-narrowing loop, which governs how
> much near-extreme content reaches the extreme camp; and a *comfort gate*, set by `vcr` and nearly
> invariant to `p_u` or the moderate hub's own state, which governs whether that content, once
> arrived, registers as expressively comfortable. The moderate hub's active state exerts its effect
> entirely through a small, early (pre-step-5000) perturbation to the openness gate — not through any
> sustained content it delivers — whose consequences are amplified by `p_u`'s loop gain. Moderate
> hubs act as a facilitator (active hub associated with more extreme-camp posting) when the openness
> gate is either narrow enough, or wide enough but delivering content the comfort gate rejects; they
> act as a mediator only once the comfort gate's admitted share outweighs the rejected remainder.

**Open flag on this paragraph, raised by the user in the very next turn and not yet resolved:** the
phrase "M's active state... push[es] the system into a narrower `bc` trajectory than the M-silent
counterfactual" risks being circular — restating "M active has less near-extreme influx than M-silent"
via an intermediate variable (`bc`) without showing `bc` does independent explanatory work. Addendum 3
resolves this (the `M/(P-M)` algebraic dilution test, using only logged feed-composition columns, is
non-circular), but the replacement paragraph above was drafted *before* that resolution and should be
revised to fold in Addendum 3–4's origin/amplification split explicitly, e.g. replacing "a small,
early... perturbation... amplified by `p_u`'s loop gain" with the more precise two-step account:
moderate content is ~40%+ of the extreme camp's feed in the first ~1000 steps (Addendum 3 §C2, not
state-dependent on `p_u`), and it is `p_u`'s effect on the *subsequent* feedback loop (Addendum 3 §C3,
Addendum 4) — not the size of that initial dilution — that governs how strongly the resulting gap, and
therefore the outcome heatmap's effect size, scales with `p_u`.

## E2. The complementary M-active / M-silent framing (still valid, keep)

From the "M-silentの効果とすると理解しやすいんだけど" turn: because the paper's subject is the ACTIVE
hub's effect, but the cleanest causal story is naturally stated from the silencing side, use the
following as a standing bridge, true in every grid cell measured:

- Active moderate hub ⇔ near-extreme content suppressed (relative to the silent counterfactual).
- Silent moderate hub ⇔ near-extreme content admitted (relative to the active counterfactual).

State this pairing once, explicitly, as the common baseline before layering the `p_u`/`vcr`-dependent
regime on top — it resolves the awkwardness of arguing "the active hub's effect" through a mechanism
that is easiest to describe via its absence.

## E3. Glossary — what "feedback loop" means here (for anyone re-reading this file cold)

Two per-agent states co-determine each other over time, closing into a loop rather than a one-way
chain:

- **State 1: `bc` (this agent's current tolerance threshold).**
- **State 2: which near-extreme sources this agent currently follows.**

**Rule A** (`Agent.java:410–412`): this step's `targetBC` is set by `inBcRate` = the fraction of this
step's feed that falls within the agent's *current* `bc`; `bc` relaxes toward `targetBC` over time.
So: today's feed content (which depends on State 2, who is followed) sets tomorrow's `bc` (State 1).

**Rule B** (`follow()`/`unfollow()`, `Agent.java:547–643`): new ties form only from content within the
agent's *current* `bc`; existing ties are broken (probability `p_u`) if the followee's content falls
outside the agent's *current* `bc`. So: today's `bc` (State 1) sets tomorrow's follow set (State 2).

Chaining A and B closes the loop: wide `bc` → near-extreme content is in-tolerance → not blocked, and
eligible as a new follow candidate → near-extreme ties survive/grow → that (in-tolerance-by-admission)
content dominates future feed composition → `inBcRate` stays high → `targetBC` stays high → `bc` stays
wide. The loop is **self-reinforcing**: a wide `bc` manufactures the conditions that keep it wide;
symmetrically, a narrow `bc` (near-extreme content judged out-of-tolerance, blocked, never admitted)
manufactures the conditions that keep it narrow, relative to the counterfactual. `p_u` sets the loop's
**gain** — how fast out-of-tolerance sources are permanently pruned each cycle, which is what determines
how quickly each pass around the loop moves the surviving population's in-tolerance share (and hence
`bc`'s target). Higher `p_u` = faster pruning = more gain per cycle = a bigger eventual arm gap, all
else equal — this is what Addendum 3 §C3 and Addendum 4 attribute the `p_u`-axis scaling of the outcome
heatmap to, as distinct from the one-shot, non-looping dilution effect (Addendum 3 §C2) that only
explains why any gap opens in the first place.

## E4. What is still unresolved (carried forward, unchanged)

Same two items as Addendum 1 §A6 / Addendum 3 §C4:
1. `follow()`'s candidate-set composition by author class has not been directly instrumented — the
   bc→tie-formation link is inferred from matching timing/scaling, not logged step-by-step.
2. The `unfollow()` "one block per agent per step" rule (Addendum 3 §C4) may add a second,
   un-quantified channel (moderate content competing with other out-of-tolerance sources for a given
   step's single blocking draw) on top of the `inBcRate`-dilution channel already quantified.

---

# ADDENDUM 6 — grid resolution upgrade, 2x3 to 4x4, confirms the story at finer resolution

**Decision (user, 2026-08-15):** expand the grid from `p_u in {0.05, 0.15} x vcr in {0.1, 0.15, 0.2}`
(6 cells) to `p_u in {0.05, 0.08, 0.11, 0.15} x vcr in {0.10, 0.13, 0.17, 0.20}` (16 cells), to check
whether the two-endpoint patterns established in Addenda 1-5 hold at finer resolution or were an
artifact of sparse sampling. Reuses the 4 corner cells already computed under 9b's grid
(`p_u in {0.05,0.15} x vcr in {0.10,0.20}`, 120 of 480 total runs); 360 new runs launched via
`scripts/lmp_feedmech_grid4x4.py`, same `SUBDIR`, same 15-seed block, GEXF export kept (betweenness
centrality deliberately skipped -- established useless, `alpha=0` kills its only channel, and
Addendum 4 showed it added negligible R² on top of `bc_inclusion`). Disk: 94GB total under
`results/2026-08-14_lmp_feedmech_structural_9b/` (1.7TB free on disk, no pressure).

## F1. Outcome heatmap: the crossing point shifts smoothly with `p_u`

| `p_u` | vcr=0.10 | vcr=0.13 | vcr=0.17 | vcr=0.20 | crossing (interpolated) |
|---|---|---|---|---|---|
| 0.05 | −0.0141 | −0.0059 | +0.0152 | +0.0216 | **0.141** |
| 0.08 | −0.0144 | −0.0102 | +0.0034 | +0.0216 | **0.160** |
| 0.11 | −0.0176 | −0.0257 | +0.0018 | +0.0073 | **0.167** |
| 0.15 | −0.0296 | −0.0142 | −0.0050 | +0.0004 | **0.198** |

The two endpoints (0.141, 0.198) match the 2-level grid's earlier numbers (0.141, 0.199) almost
exactly -- a clean internal consistency check. The two new intermediate points fall in between, in
order (0.160, 0.167), confirming the shift is a real, roughly monotonic trend across `p_u`, not a
two-point artifact. **One irregularity:** at p_u=0.11, the outcome dips *further negative* between
vcr=0.10 and vcr=0.13 (−0.0176 → −0.0257) before turning around -- non-monotonic in `vcr`, unlike the
other three `p_u` rows. Flagged, not yet explained; plausibly seed noise (n=15) but not confirmed
either way.

## F2. `bc_inclusion` (structural gate): monotonic in `p_u` at all 4 vcr levels, in both arms

Control: 0.2013 → 0.2178 → 0.2311 → 0.2306 (vcr=0.1; a −0.0005 dip from p_u=0.11 to 0.15, within noise)
-- monotonic increasing at every other vcr column (0.13, 0.17, 0.20). M_silent: strictly monotonic
increasing at all 4 vcr columns (e.g. vcr=0.1: 0.2160 → 0.2509 → 0.2769 → 0.3090). 15 of 16 (arm, vcr)
column-sequences are exactly monotonic in `p_u`; the one exception is a noise-scale reversal.
**Confirms Addendum 4/6's "higher `p_u` -> wider structural gate" as a smooth, not merely two-point,
trend**, and further sharpens the amplification story: M_silent's rise across `p_u` (+0.093 from
p_u=0.05 to 0.15 at vcr=0.1) is roughly 3x steeper than control's (+0.029) -- consistent with control's
early dilution (Addendum 3 §C2) capping how much headroom the feedback loop (Addendum 3 §C3) has to
amplify from.

## F3. `vcr_inclusion` (comfort gate): still flat across all 4 `p_u` levels

Control, vcr=0.1: 0.0277, 0.0264, 0.0270, 0.0258 across p_u=0.05→0.15 -- no systematic trend, all
within a tight band. Same pattern holds at vcr=0.13/0.17/0.20 and in the M_silent arm. The two-gate
division of labour (Addendum 2 §B2: `p_u` sets volume via the structural gate, `vcr` sets comfort via
an essentially `p_u`-invariant gate) survives the resolution upgrade unchanged.

## F4. Where this leaves the paper

The finer grid does not change any qualitative conclusion from Addenda 1-5; it upgrades their
evidentiary weight from "true at two `p_u` points" to "a smooth trend across four." Useful for the
paper's figures (a 4x4 heatmap is a materially better visual than 2x3) and for stating "the crossing
point shifts monotonically with `p_u`" without the two-point-artifact caveat. The p_u=0.11 non-monotone
cell (F1) should be checked (e.g. more seeds at that one cell) before being either explained or
dismissed as noise.
