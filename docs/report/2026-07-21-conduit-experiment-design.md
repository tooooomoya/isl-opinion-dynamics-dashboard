# 2026-07-21 — Reframing the hub-swap result; next experiment design

## Finding: the hub-swap series tested hub *identity*, not conduit *activity*

Traced `outOfBCRepostProb` end-to-end (`Agent.repost()`, [Agent.java:396-397](../../src/agent/Agent.java#L396-L397)):

```java
double pr = inBc ? this.repostProb : p.outOfBCRepostProb();
if (randomGenerator.dynamics().nextDouble() < pr) { ... }
```

`outOfBCRepostProb` is the probability an agent relays a post that falls **outside** their own
bounded-confidence window (cross-camp content). It has been held at `0.0` in the calibrated
defaults since Stage 2 (`ExperimentConfig.java:177`; independently driven there by BO across
Stage 2b/c/d — a genuine floor, not a boundary-pinning artifact). At `outOfBCRepostProb=0`, **no
agent — moderate or extreme — ever relays cross-camp content.** `research-direction.md`'s DAG
names the treatment as "moderate-conduit **activity** (repost/quote, mid-scale)" — this is exactly
the channel that is mechanically zeroed.

The hub-swap series (`docs/report/2026-07-18-joint-stage-calibration.md`, "Hub-swap causal
experiment" section: mega-hub → 3 individual mid-tier → 11-hub/15k → 10-hub/20k/n=30) manipulated
the target hub's **own opinion attribute**, not its relaying behavior. Since a hub's own posts are
governed by `postProb`/posting logic, not by `repost()`'s bc-gate, swapping opinion changes what
the hub *originates* directly to followers — it does not open the relay-of-cross-camp-content
channel, which was off throughout every one of those runs regardless of the swap.

## Decision (user, 2026-07-21): keep the swap series as-is; reframe, don't re-run

The completed hub-swap series stands as a well-powered (final arm: n=30, 20000 steps) answer to a
**narrower** question than originally framed: *does a mid-scale hub's own opinion identity affect
network-level cross-cutting exposure/polarization, holding topology fixed, in a regime where no
agent relays out-group content?* Answer: no detectable effect (see 2026-07-18 doc's Conclusion).

**Write-up consequence:** when reporting this result, state the `outOfBCRepostProb=0` scope
explicitly rather than presenting it as a direct test of the moderate-conduit-activity hypothesis.
The null is genuine for the question actually asked, but does not bear on the DAG's named
mechanism, since that mechanism was structurally inactive throughout.

**Not pursued now (deferred, not rejected):** re-running with `outOfBCRepostProb>0` as the primary
treatment (the more direct DAG test) — parked per user decision to move to a different next step
first. `relayEnabled=false` (reattribution bypass, the DAG's other currently-off mechanism) is in
the same deferred bucket.

## Open: what's the next experimental focus

Not yet decided. Candidates from `research-direction.md`'s remaining Step-3 agenda: `P_u × reactance`
phase diagram (Type-1/Type-2 transition), degree-matched rewiring counterfactual (bridge vs. raw
exposure — named in the DAG, never yet run, and shown below to have its own timing problem), network-
type/scale-free-dependency check, or the scale-vs-position factorial. To be picked up next session.

## Why the degree-matched rewiring counterfactual doesn't work either, as currently specified

User question: since a rewired counterfactual network has to be constructed at *some* point relative
to the dynamics, is it actually a valid counterfactual under this model's rules? Traced both timing
options in code:

- **`Agent.follow()`** ([Agent.java:457-461](../../src/agent/Agent.java#L457-L461)) only ever admits
  a candidate whose opinion is *inside* the follower's current `bc` — the model's own tie-formation
  rule cannot organically create a cross-camp edge. Any cross-cutting structure a rewiring wants to
  test has to be hand-inserted.
- **`Agent.unfollow()`** ([Agent.java:531-543](../../src/agent/Agent.java#L531-L543)) evaluates every
  followed tie identically regardless of provenance (`GephiReader`/`AdminOptim` don't distinguish
  organic vs. inserted edges) — reactively, whenever the followee's content lands in the follower's
  feed and falls outside `bc`.
- **Rewire the initial network, run to equilibrium:** gets washed out. The same bc-gated
  formation/dissolution that makes calibration reproducible from random initial conditions will pull
  *any* starting topology toward the same homophilous attractor. A null here reflects the model's
  ergodicity, not the hub's causal role — not informative for the hypothesis.
- **Rewire at/near equilibrium, short continuation** (mirroring the hub-swap design): avoids full
  re-convergence, but (a) still doesn't test repost-mediated conduiting (`outOfBCRepostProb=0`, same
  foreclosure as the identity-swap series), and (b) introduces a new confound the swap didn't have —
  `unfollow()` eligibility is content-driven, not time-driven, so a cross-camp edge anchored at a
  high-`postProb` hub gets tested for removal far more often than a diffuse edge to a low-activity
  node carrying the same nominal exposure volume, contaminating any concentrated-vs-diffuse contrast
  with a pure activity-rate artifact.

**Conclusion:** not well-posed under either timing without first resolving `outOfBCRepostProb`, or
protecting inserted edges from `unfollow()` (which would stop being "counterfactual within the
model's own rules"). Deprioritized until the repost-gate question is settled.

## Hub-tier characterization (2026-07-21): robust, multi-seed replacement for the deleted single-seed profile

The specific agent IDs/values from the 2026-07-18 hub-swap section's seed-920000 snapshot no longer
exist on disk (`results/` was purged before the v7 calibration run) and were only ever one stochastic
draw. Ran a fresh 20-seed characterization (`scripts/hub_tier_characterization.py`, n=1000,
steps=20000, current calibrated defaults, no swap/treatment — purely descriptive) to get a robust
picture of where moderate hubs sit in the degree distribution. `moderate` = |opinion| < 0.2 (same
threshold used to select the original mid-tier swap candidates).

**Rank-based tiers** (top=rank 1, semi_top=ranks 2-5, mid=ranks 6-20, low_mid=ranks 21-50), moderate
count out of tier size, mean ± sd across seeds: top 1.00±0.00/1, semi_top 1.75±0.70/4, mid
4.30±2.00/15, low_mid 13.30±2.08/30. Full per-rank profile:
`docs/report/hub_tier_characterization_summary.csv` / `_raw.csv`.

**Percentage-of-population tiers** (`scripts/hub_tier_pct_summary.py`, reprocessed from the same 20
runs' full agent snapshots, no re-simulation): mega (in-degree >500, i.e. >50% of n=1000) tier_size
7.2±0.9, frac_moderate **0.46±0.12**, mean|opinion|=0.212; mid (101-500, >10%-50%) tier_size
16.1±2.3, frac_moderate **0.32±0.15**, mean|opinion|=**0.353**; tail (≤100, ≤10%) tier_size
976.8±2.0, frac_moderate 0.37±0.02, mean|opinion|=0.323. Full data:
`docs/report/hub_tier_pct_summary.csv` / `_raw.csv`.

**Finding: moderation vs. reach is non-monotonic, not a clean gradient.** The mega tier (>50% reach,
~7 hubs/seed) is the *most* moderate band in the network; the mid tier (10-50% reach, ~16 hubs/seed)
is the *least* moderate band anywhere, including the 977-agent long tail. Confirms and generalizes
the old single-seed observation ("the most extreme opinions in the top 15 sit at the lowest
in-degrees there") as a real, seed-robust pattern (SD tight relative to the gap across 20 seeds), not
a one-snapshot artifact. **Consequence for hub selection in future experiments:** a "moderate,
mid-tier hub" is not a typical mid-tier hub — it's a roughly 1-in-3 minority within the band that is,
on average, the network's most extreme-leaning reach tier. Any future design sampling "the moderate
mid-tier hubs" is implicitly conditioning on an atypical subset of that population, which should be
stated explicitly rather than left implicit.

## Why node-level swaps can't isolate the hub-identity effect at all (2026-07-21, user insight)

User identified two compounding problems with every swap/rewiring design considered so far, on top
of the `outOfBCRepostProb=0` foreclosure already logged above:

1. **Substitution.** "Moderate hub" is an emergent *role* (density-near-center + `follow()`'s bc-gate
   means moderates are within reach of more of the population, not an identity tag on one agent.
   Swapping the current occupant's opinion doesn't remove the role, it vacates it — the reserve pool
   is enormous (this session's own 20-seed count: ~366 agents/1000 average |opinion|<0.2, vs. only
   ~8.4 currently occupying mega+mid hub tiers), so a substitute promptly fills the gap. None of the
   hub-swap series (2026-07-18/20 entries above) could have removed "a moderate hub" from the system
   even setting aside the repost-gate problem.
2. **Confound at scale.** Swapping enough agents to actually deplete that reserve pool stops being a
   hub-identity manipulation and becomes a population-opinion-composition manipulation (fewer
   moderates, more extremists in aggregate) — a different, legitimate but distinct experiment that
   should be labeled as such, not conflated with "the hub's causal role."

**Implication:** manipulating the rule level (`outOfBCRepostProb`, `relayEnabled`/`relAttrib`) is not
just preferable but likely the *only* lever in this model that can isolate the conduit-activity
question independent of population composition, since it changes what an (any) existing hub does
rather than who occupies the role.

## Circularity flagged in the SF1 calibration series (2026-07-21, user insight): don't fit the baseline to the outcome

The v1-v9 SF1 calibration effort (docs/report/2026-07-18-joint-stage-calibration.md above) tuned the
**no-manipulation baseline** to hit the empirical apparent-polarization range [1.19,1.26]. If the
paper's causal claim is "moderate-hub conduiting produces realistic apparent polarization," baking
that outcome into the uncalibrated/no-treatment model is circular: it manufactures the target via
loss-function tuning rather than letting it emerge from the hypothesized mechanism, making any
later "does manipulating the hub change SF1" test biased toward finding nothing (there's no room
left to move). General principle: never calibrate a model's null state to already match the value a
causal hypothesis is supposed to explain.

**Two complementary paths proposed (user, 2026-07-21):**
- **Correlational ("gaining implication"):** across many seeds of a given calibration point, check
  whether natural seed-to-seed variation in moderate-hub prevalence correlates with SF1 ratio. This
  directly answers an already-flagged, previously-shelved open question from the 2026-07-20 v9
  adoption entry above ("ratio's high per-seed variance... might be related to the proportion of
  moderate-hub-like agents in a given seed's realized draw... not yet tested").
- **Causal ("causal check"):** recalibrate *excluding* SF1 from the loss (i.e., a base model that
  does NOT already hit the apparent-polarization target — v3 or v7's already-documented points both
  qualify: Gini/Q/assort solid, SF1 short by ~12-40%), then manipulate hub conduiting/reach on top of
  that non-circular baseline and check whether SF1 moves toward the empirical range as a function of
  the manipulation.

**First-pass correlational check (2026-07-21):** reused the 20 already-completed hub-tier-
characterization runs (free, no new simulation) — computed SF1 ratio per seed from each run's
`results.csv` and correlated against two moderate-hub-prevalence indices from
`docs/report/hub_tier_pct_raw.csv`: count-based (moderate hubs in mega+mid tiers) and reach-weighted
(total followers commanded by moderate mega+mid hubs, and moderate share of hub-tier reach — the
more theoretically apt "conduit capacity" measure).

| index | Pearson r vs. SF1 ratio |
|---|---|
| total moderate hub count (mega+mid) | -0.169 |
| mega-tier moderate count only | +0.043 |
| mid-tier moderate count only | -0.196 |
| moderate-hub total reach | -0.017 |
| moderate share of hub-tier reach | -0.007 |
| (partial r, count vs. ratio, controlling total hub-tier size) | -0.143 |

**Read: uninformative null, not a disconfirmation.** n=20, critical `|r|≈0.44` for p=0.05 — every
value above is well inside the noise floor. Given SF1's own documented cross-seed SD (~0.15-0.23),
detecting a true r≈0.3 at reasonable power needs roughly n≈85 seeds; r≈0.2 needs closer to n≈190.
Twenty seeds cannot resolve this question in either direction yet. Consistent with this project's
own noise-tolerance lesson: do not read small correlation coefficients at low n as evidence of
"no effect" or "opposite effect."

**Open, not yet decided:** whether to scale Path 2 up to a properly-powered seed count, and/or begin
designing Path 1's treatment (repost-activity or reach-dose manipulation layered on a v3/v7-style
non-SF1-fit base point).

## Decision (user, 2026-07-21): start with Path 1

Rationale: Path 2 run on the *current* (SF1-fit) calibration point is unlikely to be informative
either way — realistic apparent polarization is close to guaranteed to show up on average regardless
of hub prevalence, since the baseline was tuned to sit near the target. Path 1 (non-circular base,
then manipulate) is the more decisive test and doesn't inherit that problem. Starting there.

### Snapshot: full current defaults, preserved before switching the Path-1 baseline

Before touching `ExperimentConfig.java` for a v3/v7-style non-SF1-fit base point, recording the
complete current default set (2026-07-20 "static bc" adoption, currently sitting as the literal
compiled defaults, git-uncommitted) verbatim from source, so it isn't lost:

**Network/growth:** `networkType="hk"`, `hkM=15`, `hkA=4` (gamma = 2+hkA/hkM = 2.267), `hkPt=0.05`.

**Follow dynamics:** `maxFollowCapacity=57` (`max_follow`), `followProb=0.009` (`follow_prob`),
`accessProb=0.1`, `pU=0.05` (P_u phase knob — legacy default, never part of the 10-dim joint search).

**Feed/recommender:** `feedAlgoShare=0.76` (`alpha`), `feedHopH=1` (`hop`), `velMode="windowed"`,
`feedCapacity=15` (`feed_capacity`).

**Bounded confidence (static-bc regime):** `bcRecoveryRate=0.0` (`bc_recovery`), `bcDecRate=1.0`
(`bc_dec` — provably freezes bc at `bcInit` forever, per the 2026-07-20 static-bc diagnostic above),
`bcFloor=0.2`, `bcCeiling=1.0`, `bcInit=0.56` (`bc_init`), `initOpinionClip=false`.

**Repost/relay:** `repostProb=0.1` (in-bc repost rate, never swept — base default throughout),
`relayEnabled=false`, `coupleRelayDistortion=true`, `relayDistortionStrength=0.5` (inert while
`relayEnabled=false`), `outOfBCRepostProb=0.0` (`out_of_bc_repost_prob` — the conduit-activity
foreclosure discussed above), `relAttrib="original"` (conduit immunity; inert while
`relayEnabled=false`).

**Posting/vocality:** `initialPostProb=0.21` (`initial_pp`), `maxPostProb=1.0` (`max_pp`),
`minPostProb=0.05`, `comfortPpFactor=0.5` (`comfort_pp`), `vocalComfortRadius=0.2`.

**Heterogeneity/capacity:** `stubDist="uniform"`, `stubMin=stubMax=0.69` (`stub_min`/`stub_max`),
`evictBeta=-1` (legacy argmax-disagreement eviction), `initPrune="trim"`.

**Hostility (inert, deprioritized 2026-07-08, not touched by any of this):** `hostilityActive=false`,
`lUp=0.005`, `lDown=0.005`, `lMis=0.05`, `thetaDist=0.4`.

**Scale/run:** `n=1000`, `steps=40000` (default — this project's runs consistently override to
`steps=20000` explicitly), `moderateBandHalfWidth=0.2` (matches this session's ad hoc `|opinion|<0.2`
moderate threshold — it's already a named config constant, not an arbitrary choice).

**Confirmed 5-seed profile at this exact point** (from the 2026-07-20 static-bc adoption entry
above): Gini=0.869±0.006, Q_sign_repost=0.454±0.034, assort=0.650±0.041, ratio(SF1)=1.334±0.230
(static-bc 20-seed) — the point this whole document's Path-1 discussion is proposing to move away
from as the *baseline*, in favor of a non-SF1-fit point (v3 or v7, both documented in
`2026-07-18-joint-stage-calibration.md`) for the causal test.

## Homophily/hostile repost-edge split (2026-07-21): design, rejected first draft, and implementation

**Starting proposal (user):** permit out-of-bc repost (`outOfBCRepostProb>0`, already built, held at the
Stage-2d floor) and, for out-of-bc relays specifically, convey the *reposter's* opinion instead of the
original poster's ("hostility-based reposting"), no perturbation — plus log homophily vs. hostile
repost edges separately in the gephi output.

**Why the opinion-swap half was rejected.** Traced the two places "cross-cutting" is actually computed:
structural metrics (`computeInteractionAssortativity`/`computeInteractionCrossCuttingFraction`/
`computeSignModularityFromMatrix`, [Analysis.java:279-419](../../src/analysis/Analysis.java#L279-L419))
key off the **agents'** own opinion attributes at the edge endpoints, never the post's conveyed
opinion; but the **receiver's** actual exposure/reactance (FJ assimilation, bc-decline, follow/unfollow
triggers) keys off `post.getPostOpinion()` — the **conveyed** value. Swapping conveyed opinion to the
reposter's own would make every relay (in- or out-of-bc) land, for the receiver, inside the reposter's
own bc by construction — the moderate's followers would never actually see the extreme content. Net
effect: the mechanism could inflate the *structural* cross-cutting number while being mathematically
incapable of ever moving the *affective/exposure* outcome — the "assumption masquerading as a
mechanism" failure mode from this file's own §3 litmus test (`docs/research-direction.md`), and a
direct hit on the DAG's M1 mediator and the paper's "moderate relays extreme content in their own
voice" key insight. **Decision (user, 2026-07-21): conveyed opinion stays verbatim for both in-bc and
out-of-bc relay** (no change to `relay()`'s conveyed-opinion formula at all) — the receiver's bc-decline
exposure channel needs the original content to survive relay, and the only real difference between an
in-bc and out-of-bc repost is which edge-type bucket it's logged under, not what the receiver perceives.

**Hostility mechanism deleted from the model (user, 2026-07-21).** Separately: the pre-existing
`hostilityActive`/`lUp`/`lDown`/`lMis`/`thetaDist` state-variable mechanism (ε-style hostility ratchet,
`receiveMisrepresentation()`, R2) was already inert (`hostilityActive=false` since the 2026-07-08
redefinition in `research-direction.md`) but still present in code. User's call: it was an AI-introduced
byproduct never specifically directed, and should be deleted outright rather than kept inert. Removed
from `Agent.java` (field, `getHostility()`, `receiveMisrepresentation()`, the contact-valence block in
`updateMyself()`, the misrepresentation-grievance block in `repost()`), `ExperimentConfig.java` (fields,
CLI cases, `tag()` line), `SimParams.java` (record components + constructor), `Analysis.java`
(`computeMeanHostility`/`computeHostilityVar`/`computeHostilityBins`), `OpinionDynamics.java` (the
`meanHostility`/`hostilityVar`/`hostility_i` CSV columns), `AssertionCheck.java` (the `[0,1]` bounds
check), and `ModelTests.java` (`testHostilityBounds`/`testHostilityGate` and all round-trip/tag
references). Verified: full `javac` compile clean, `ModelTests` shows the same 2 pre-existing `[tag]`
failures as `main` before this session's changes (`p_u tagged only when non-default`, `distinct configs
=> distinct tags` — confirmed pre-existing by running the test suite against the pre-session `git
stash`ed tree), nothing new broken. `computeMeanHostility` etc. and the R1 "behavioral hostility
proxies" (`outGroupBlockPropensity`, `crossRepostRate`, block/sanction counters) are a *different*,
untouched mechanism (block/sanction-rate proxies, not the deleted state variable) — left alone.

**"Hostile" repurposed as an edge-type label, not a state variable (user, 2026-07-21).** With the old
state-variable usage gone, no internal collision remains. Precedent check: the affective-polarization
literature (Iyengar & Westwood 2015; Iyengar, Lelkes, Levendusky, Malhotra & Westwood 2019) uses
"hostility" for a persistent attitudinal *state* (how the deleted mechanism used it); the signed-network/
structural-balance literature (Heider 1946; Cartwright & Harary 1956; Leskovec et al. 2010) uses
"hostile"/"negative" for a discrete *edge* label, which is the right shape for this use. Adopted, with
one caveat to carry into the paper: the label is a bc-threshold-crossing classification at relay time,
not a measured sentiment/toxicity/valence signal — say so explicitly wherever it's used, since the
signed-network precedent usually backs "hostile" with an independently coded valence this model doesn't
have.

**Measurement split (user, 2026-07-21): mechanism vs. outcome, kept separate.** Homophily/hostile
(bc-threshold-based) is a **mechanism**-level tag — which of the two probability gates
(`repostProb` vs. `outOfBCRepostProb`) fired for a given relay. The existing sign-based cross-cutting
partition (`computeInteractionCrossCuttingFraction`/`computeSignModularityFromMatrix`, moderate agents
with `|opinion|<moderateBandHalfWidth` excluded, matching Conover et al. 2011's undecidable-exclusion
convention) stays a measured **outcome**, computed exactly as before, over the combined repost graph —
not redefined or merged with the new edge type, since that's the convention "much of the former
experimental research" in this space already uses.

**Implementation.** `Post.java`: added `outOfBcRelay` (boolean, `isOutOfBcRelay()`), set at construction
alongside the existing lineage fields (`rootPostId`/`parentPostId`/`relayerId`/`depth`); false for
original (non-relay) posts. `Agent.java`: `repost()` passes its already-computed `inBc` flag into
`relay(post, !inBc)`, which threads it through to `Post.relayOf(...)` on both the `relayEnabled=false`
(verbatim) and `=true` branches — no change to the conveyed-opinion arithmetic itself.
`OpinionDynamics.java`: added `repostNetworkHomophily`/`repostNetworkHostile` (snapshot, reset every
5000 steps alongside `repostNetwork`, feeds the gephi export) and
`repostNetworkCumulativeHomophily`/`repostNetworkCumulativeHostile` (whole-run, mirrors
`repostNetworkCumulative`; not yet wired to any CSV metric — available for a future type-specific
structural read-out if wanted, not added speculatively). `repostNetworkWindow` intentionally **not**
split (not requested; can be added later). `RepostVisualize.java`: `updateGraph` now takes both
homophily and hostile dense matrices; kept a single directed edge per `(i,j)` pair (Gephi's graph model
here has no built-in parallel-edge support, and restructuring to a multigraph wasn't asked for) with
edge weight = combined total (unchanged downstream semantics) plus three new edge columns:
`homophilyReposts`/`hostileReposts` (Integer counts) and `dominantEdgeType` (String:
`homophily`/`hostile`/`mixed`, for quick categorical coloring/filtering in Gephi).

**Verified end-to-end:** `javac` clean; `ModelTests` unchanged (same 2 pre-existing failures); a smoke
run (`n=100 steps=5000 out_of_bc_repost_prob=0.05 log_gexf=true`) produced a populated
`repost_step_5000.gexf` with both `homophilyReposts>0` and `hostileReposts>0` edges present and
`dominantEdgeType` set correctly, confirming the split fires end-to-end once the gate is turned on.
`outOfBCRepostProb`'s default is **unchanged at 0.0** — enabling it for a specific experiment is a
calibration/run-design decision, not a default-config change, and stays out of scope for this entry.

## Experiment redesign (2026-07-21): secession test, not addition test

User redesigned the swap experiment: instead of Path-1's "start from a non-circular no-treatment
baseline, add the swap, see if SF1 emerges" (sufficiency test), the new design is "calibrate a
condition where apparent polarization already happens (moderate hubs present, organic/unswapped),
then secede the moderate hubs (same opinion-swap-to-extreme methodology as the 2026-07-18 hub-swap
series) and measure whether SF1 collapses" (necessity test). Assessed as legitimate and
non-circular **provided `out_of_bc_repost_prob` is fixed, not searched**, during the calibration
step — if it's free while fitting SF1, the search can simply dial in "however much cross-camp
repost volume is needed," reproducing the same hub-identity-vs-conduit-activity confound already
flagged for the original hub-swap series. Recommended design: free dims `hop, bc_dec,
bc_recovery, bc_init, comfort_pp` (v7's 5), fixed `out_of_bc_repost_prob` at the chosen treatment
dose, joint loss over Gini (0.8) + Q_sign_repost (0.48) + assort (0.6 floor) + SF1 ratio
([1.19,1.26]) with variance penalties (v7-style), evaluated on the organic (hub-present, unswapped)
network. Then secede the hubs on top of that fixed point and measure the pre/post delta in SF1
(and Gini/Q/assort as a sanity check).

User proposed fixing `out_of_bc_repost_prob = repost_prob` (0.1) "for simplicity." Flagged as a
literal reversion to the pre-2026-06-26 `coupleOutOfBCRepost=true` behavior that was explicitly
removed as a no-op (Agent.java comment), plus a construct-validity concern (in-group vs.
counter-attitudinal sharing are empirically distinct, well-documented as asymmetric in the
selective-exposure literature) and an empirical one (Stage 2b/c/d's BO, when `out_of_bc_repost_prob`
was still a free search dimension, independently converged it toward ~0). Recommended a cheap OAT
check instead of guessing.

### OAT scan: how much does out_of_bc_repost_prob move the structural facts?

Ran `scripts/oob_repost_prob_scan.py`: `out_of_bc_repost_prob ∈ {0, 0.01, 0.02, 0.05, 0.1}`, 3
seeds each, `n=1000, steps=20000`, all other params at the current v7/Path-1 defaults (no
recalibration yet — a cheap first pass, not a confirm-quality result). Raw:
`docs/report/oob_repost_prob_scan_raw.csv`, summary: `docs/report/oob_repost_prob_scan_summary.csv`.

| out_of_bc_repost_prob | Gini | Q_sign_repost | assort | ratio (SF1) |
|---|---|---|---|---|
| 0.00 | 0.800±0.014 | 0.470±0.010 | 0.727±0.037 | 1.00±0.25 |
| 0.01 | 0.795±0.016 | 0.476±0.015 | 0.734±0.033 | 1.08±0.08 |
| 0.02 | 0.789±0.013 | 0.470±0.009 | 0.736±0.018 | 1.42±0.25 |
| 0.05 | 0.784±0.004 | 0.465±0.011 | 0.746±0.044 | 0.99±0.06 |
| 0.10 | 0.804±0.009 | 0.449±0.027 | 0.749±0.038 | 1.28±0.23 |

**Result revises the concern above.** Gini and assort are essentially flat across the whole range —
no meaningful degradation even at `oob=0.1`, contrary to the BO-history-based prediction that equal
rates would badly miss the structural targets. Q_sign_repost shows the only directional signal (a
mild dip at `oob=0.1`, 0.449 vs. ~0.47 at lower levels) but it's within the n=3-seed noise band
(std=0.027 there), not a blowout. SF1's ratio is too noisy at n=3 to read at all (0.99–1.42, stds up
to 0.25 — consistent with this project's already-documented finding that SF1 needs ~85+ seeds to
resolve a real effect). **Conclusion: setting `out_of_bc_repost_prob = repost_prob = 0.1` does not
clearly wreck the structural calibration at this resolution** — the equal-rates objection raised
above is not strongly borne out empirically, at least in the tested range. `0.05` remains a
defensible lower-margin alternative (closer to the Q_sign_repost target, still a substantial,
non-arbitrary half-of-`repost_prob` dose) if a safety margin against the one soft signal is wanted.
Choice of `0.05` vs. `0.1` as the fixed treatment dose: **open, pending user decision.**

### Decision (user, 2026-07-21): `out_of_bc_repost_prob = 0.05`, on literature evidence of asymmetric sharing

User's decision rule: take `0.05` (asymmetric, out-group rarer) if research evidence supports out-group/
cross-cutting resharing happening less often than in-group resharing; otherwise `0.1` (equal, per the
"for simplicity" proposal). Checked via web search:

- **Conover et al. (2011), "Political Polarization on Twitter"** (AAAI ICWSM) — already cited elsewhere
  in this codebase's comments — found the retweet network highly segregated by ideology (minimal
  cross-camp connectivity), while the @-mention network shows much more ideologically-heterogeneous
  interaction. Retweeting specifically (the closest real-world analog to this model's repost mechanic)
  is the more homophilous of the two channels.
- **Wojcieszak, Casas, Yu, Nagler & Tucker (2022), "Most users do not follow political elites on
  Twitter; those who do show overwhelming preferences for ideological congruity"** (*Science Advances*)
  — quantitative: across 4 years of data (~1.5M users), in-group elite content is retweeted **13x more
  frequently** than out-group elite content. Also: when out-group content *is* shared, it disproportion-
  ately carries negative/critical commentary rather than plain endorsement — independent empirical
  support for the homophily/hostile edge-type framing adopted earlier in this document, not just for
  the probability asymmetry.

**Decision: `out_of_bc_repost_prob = 0.05` fixed for the secession experiment.** Noted honestly: the
literature's actual magnitude (13x) is far starker than the 2x implemented here (0.05 vs. repostProb=
0.1) — a more literature-faithful value would be closer to `0.1/13 ≈ 0.008` (near the `0.01` point
already in the OAT scan above, which also looked structurally safe on Gini/Q/assort). `0.05` is a
conservative, round-number compromise, not a precise fit to the 13x figure — flagged in case a reviewer
wants tighter grounding later.

Sources: [Conover et al. 2011](https://ojs.aaai.org/index.php/ICWSM/article/view/14126),
[Wojcieszak et al. 2022, Science Advances](https://www.science.org/doi/10.1126/sciadv.abn9418).

**Revised decision: `out_of_bc_repost_prob = 0.01`.** User pushed further on the 13x figure once
the "0.05 vs 0.1" framing was resolved: literal `repost_prob/13 ≈ 0.0077`, rounded to `0.01` (also
the closest point already covered in the OAT scan, safe on Gini/Q/assort there). Adopted as the
final fixed treatment dose for the secession experiment.

## First calibration attempt (2026-07-21): crash, warm-start recovery, and a lesson for CLAUDE.md

`scripts/app_pol_baseline_bo_calibration.py` (v7-style 5-dim search — `hop, bc_dec, bc_recovery,
bc_init, comfort_pp` — `out_of_bc_repost_prob` fixed at 0.01, loss = Gini+Q_sign_repost+assort+SF1,
CCDF written as a validation-only artifact, not a loss term per the user's decision to keep Gini
scalar) was launched as a plain background shell task and died mid-round-2 — no completion marker,
process gone, consistent with a harness/session teardown rather than a script bug. Recovered via
`scripts/app_pol_baseline_bo_resume.py`: warm-started the same `skopt.Optimizer` from the 12
already-evaluated points (`opt.tell()`), continued rounds 2-7 rather than restarting, this time
launched with `nohup ... & disown`. Completed successfully. Best point: `hop=1, bc_dec=0.999,
bc_recovery=0.0885, bc_init=0.4432, comfort_pp=0.5` — structural facts solid (Gini=0.8504±0.0063,
assort=0.8340±0.0148, Q_sign_repost=0.4978±0.0015) but SF1 unresolved at 5 confirm seeds
(ratio=0.9965±0.2318 vs. the search-time evaluation of the same point, 1.066±0.073 on different
seeds — same point, wildly different variance-dominated read, the already-documented "SF1 needs
~85+ seeds" problem recurring exactly as predicted). Two real methodology flags from this run, not
just the crash: `bc_dec` pinned at the search box's ceiling (0.999) in 27/48 evaluated points, and
`comfort_pp` pinned at its floor (0.5) at the winning point — both real boundary-pinning, not noise.
**Consequence: added a "Running experiments" section to `CLAUDE.md`** requiring `nohup`/`tmux` (never
a plain background call) plus resumable design for any long simulation run, so a session boundary
loses as little completed work as possible going forward.

## Retrospective check: did v1's gamma_fit loss term actually bias the six "never touched since" defaults?

User flagged that `stage_joint_bo_calibration.py` ("v1," 2026-07-18, the search whose output fixed
`max_follow=57, follow_prob=0.009, alpha=0.76, feed_capacity=15, initial_pp=0.21, stub=0.69` for
every version since) had `GAMMA_TARGET`/MLE power-law fit in its loss — the same methodology
already flagged as unreliable in this session's Gini/CCDF discussion. Traced the code history:
`v3`'s docstring (2026-07-18, same day) already independently reached this conclusion and dropped
`gamma_fit` from the loss (kept monitored-only) — *"the actual goal is heavy-tailedness, not a
specific exponent, and this is also the metric Stage 1a already documented as least trustworthy at
n=1000 (systematic MLE undershoot)... Gini stays in the loss and is a more robust proxy."* But that
fix only applied to *future* searches — the six inherited defaults are v1's raw, unmodified output,
never re-derived under the corrected loss. Recomputed v1's own 48 evaluated points' loss with
`gamma_fit` dropped entirely (Gini+assort-floor+Q_sign_repost only): **the winning point is
identical either way** (`max_follow=65.90, follow_prob=0.0100, alpha=0.823, feed_capacity=18,
initial_pp=0.500, stub=0.830`), and that point's own `gamma_fit_mean=1.972` was already a real miss
against the target (2.276) — gamma wasn't the deciding term even when present. Caveat stated
explicitly: this only checks points v1 actually evaluated, not whether gamma_fit's presence steered
the acquisition function's exploration path differently from a gamma-free search from scratch — an
unavoidable gap in any retrospective check. Given this evidence and the ~9-day deadline, decision was
to **not** rerun the 10-dim search from scratch, and instead fold a widened, partially-reopened
version of it into the app-pol baseline search below (a real reopening, not literally validated by
this check alone).

## Reopening the search space (2026-07-21): from 5 dims to 11, three tightened, two widened, one added

Given the boundary-pinning findings above and "we have enough time now," reopened the six v1-frozen
dims alongside the five already-searched ones, with targeted changes rather than a blanket
re-widen:
- **Tightened (user's proposal):** `max_follow` [15,100]→[15,50] (v1's winner sat at 65.9, no
  evidence for going past that); `alpha` [0,1]→[0.5,1.0] (excludes the pure-chronological regime,
  not this paper's operating assumption); `stub` [0.05,0.95]→[0.5,0.9] (excludes the very-low-
  stubbornness regime).
- **Widened (from this session's own boundary-pinning evidence, not the user's list):** `bc_dec`
  ceiling [0.5,0.999]→[0.5,**1.0**] (the just-finished 5-dim run's winner sat pinned on 0.999,
  27/48 points had bc_dec≥0.99); `comfort_pp` floor [0.5,3.0]→[**0.1**,3.0] (winner pinned at 0.5,
  never probed lower).
- **Added:** `bc_init` [0.2,1.0] — didn't exist as a free dim in v1 (added to the model 2026-07-14,
  after v1 ran); included now since every search since v7 has treated it as load-bearing.
- **Unchanged:** `follow_prob` [0.01,0.3] log-uniform, `hop` [1,5], `bc_recovery` [0.0,0.3],
  `feed_capacity` [5,40] — no evidence prompting a change.

## Empirical 7-bin fit (2026-07-21): initial-opinion distribution and posting-activity, from real data

User asked to ground both the initial opinion distribution and "the original posting dynamics" in
the same post-January-6 paper (Buntain & Snegovaya 2025) already used for the `out_of_bc_repost_prob`
asymmetry ratio, rather than assume a symmetric/synthetic shape. Located and downloaded the paper's
public OSF dataset (`10.17605/OSF.IO/KQFM6`, `_anon_data/` folder: `tw_handle_to_libcon.csv` +
`twitter.2020to2021.matched.counts.parquet`, n=765 real Twitter/X accounts with self-reported
ideological lean on a [-3,+3]/7-point scale and 2020-2022 daily post counts) — not just the paper's
qualitative text, actual per-account numbers.

**Findings:**
- Self-reported ideology counts by bin: -3:160, -2:131, -1:85, 0:208, +1:46, +2:71, +3:64 (sum=765).
  Genuinely asymmetric, ~2:1 liberal-leaning, consistent with Table 2 of the paper (full n=2019
  sample, same skew).
- Mean total posts per respondent by bin (full observation window): -3:4328.7, -2:2682.9,
  -1:1503.7, 0:2135.8, +1:691.1, +2:1156.8, +3:3742.5. Extremity(|lean|=3)/moderate ratio ≈1.95x,
  matching the paper's qualitative "twice as often." **Not monotonic in extremity** — grouped by
  `|lean|`: 0→2136, 1→1218, 2→2146, 3→4161 — the "somewhat" bins post *less* than moderates; only
  the most-extreme bin shows the real jump. This shape is invisible to a single variance-ratio
  metric (SF1) and would be erased by symmetrizing or fitting a smooth monotonic curve.

**Decision: accept the asymmetry, fit both quantities in opinion-space discretized into the same 7
bins as the survey** (not symmetrized) — user's proposal, assessed as better than symmetrizing
(avoids an arbitrary symmetrization choice) and better than the existing single-scalar SF1 ratio
(preserves the non-monotonic shape). Two different treatments, resolved by what's mechanically
possible, not by preference:
- **Initial opinion distribution: direct sampling, not a loss-function fit.** The existing generator
  (`Agent.java` constructor, truncated/clipped mean-0 Gaussian) has no skew parameter a BO search
  could move toward an asymmetric target — nothing to fit. Added a new `init_dist=empirical` option
  (`ExperimentConfig.initOpinionDist`, default `"gaussian"` unchanged) that draws each agent's
  intrinsic opinion directly from `Const.EMPIRICAL_OPINION_BIN_COUNTS`: pick one of 7 equal-width
  bins spanning [-1,1] proportional to the survey counts, then sample uniformly within that bin's
  continuous sub-interval (not 7 point masses — real respondents sharing a self-report label don't
  share one exact opinion value). Verified: n=1000 smoke run reproduced the target proportions
  within sampling noise (model 0.220/0.176/0.114/0.255/0.057/0.085/0.093 vs. target
  0.209/0.171/0.111/0.272/0.060/0.093/0.084).
- **Posting activity: a new loss term, scoring the existing mechanism, not replacing it** (user
  decision: "just scoring with the existing mechanism"). `comfort_pp`/`initial_pp` stay free/searched
  params; a new cumulative post-count-by-7-bin accumulator
  (`OpinionDynamics.postCountByBin7`, binned by *intrinsic* opinion — a fixed trait, matching how
  the empirical target itself was built from a fixed self-report, not the agent's *current* opinion,
  which drifts via FJ assimilation) runs alongside, never reset, parallel to the existing per-step
  `postOpinionVar`/`postShare` machinery (`Analysis.clearPostCash()` fires every step — confirmed by
  reading the code — so the existing SF1 ratio is a single-step snapshot at the final step, not
  cumulative; this new metric is deliberately cumulative-from-t=0 instead, matching how the
  empirical anchor itself pools posts over its *entire* ~2-year observation window rather than a
  late/steady-state slice). Written once at run's end to `metrics/post_bin7.csv`
  (`Writer.writePostBin7`). Loss term: sum of squared differences between model and empirical
  post-count proportions per bin, same `/0.05` scale convention as the other terms.

**Implementation:** `Const.java` (`EMPIRICAL_OPINION_BIN_COUNTS`, `EMPIRICAL_POST_BIN_WEIGHTS`,
`NUM_OF_BINS_EMPIRICAL_7=7` — a true constant, not exposed via CLI, per this file's own
migrate-or-delete invariant, since it's fixed survey data, not a tunable parameter). `Agent.java`
(`opinionToBin7()` static helper shared by both the sampler and the accumulator, so bin edges can't
drift out of sync; `sampleEmpiricalOpinion()`). `OpinionDynamics.java` (`postCountByBin7` field,
incremented alongside the existing `postOpinionVar`/`postShare` population filter). `Writer.java`
(`writePostBin7`). Verified: full `javac` clean, `ModelTests` unchanged (same 2 pre-existing
failures), smoke run confirmed both the sampler's proportions and the end-to-end
Java→CSV→Python loss pipeline (`scripts/app_pol_baseline_bo_v2_empirical7bin.py`).

## Calibration v2 launched (2026-07-21)

`scripts/app_pol_baseline_bo_v2_empirical7bin.py`: 11-dim space (above) × 12 rounds × 6 points × 5
seeds, `init_dist=empirical` and `out_of_bc_repost_prob=0.01` both fixed (not searched), loss =
Gini + Q_sign_repost + assort-floor + SF1 + 7-bin posting-fit, `n=1000, steps=20000`. Launched via
`nohup ... & disown` per the CLAUDE.md update above. Expected runtime ~2.5-3 hours. Results (best
point, confirmed structural facts, 7-bin posting-proportion comparison, CCDF) to be logged here on
completion.

## Calibration v2 completed (2026-07-22): winner's-curse gap and a boundary pin, not yet adoptable

All 12 rounds + 5-seed confirmation finished (`logs/app_pol_baseline_v2_stdout.log`, pid 16663,
total wall time ~4h02m). Search-time best (round 4): `point_loss=40.186` at `max_follow=15.0,
follow_prob=0.0799, alpha=0.9392, hop=2, bc_dec=0.5788, bc_recovery=0.2265, bc_init=0.7569,
stub=0.8236, comfort_pp=1.3737, feed_capacity=36, initial_pp=0.0638`. Rounds 5-11 never beat
round 4 (flat at 40.186 for 8 consecutive rounds).

**Problem 1: confirmation loss is substantially worse than the search-time estimate for the
identical point.** 5 fresh seeds gave `point_loss=51.278`, not 40.186 — barely better than round
0's search-time best (51.576). Per-term comparison (round-4 search estimate → confirm):
Gini 0.7422±0.0226 → 0.7377±0.0201 (flat), Q_sign_repost 0.4161±0.0420 → 0.4279±0.0209 (flat/
slightly better), **SF1 ratio 1.1381±0.1251 → 1.0874±0.1223 (worse, target [1.19,1.26])**,
**bin7 posting-fit loss 27.023 → 34.742 (worse)**. assort stayed non-binding (0.98 vs. 0.6 floor)
throughout. This is the same winner's-curse/noise pattern already documented in the first
calibration attempt's SF1 confirm gap (0.9965±0.2318 vs. 1.066±0.073, see entry above) — with only
`SEEDS_PER_POINT=5` across 72 evaluated points in a 12-round×6-point BO run, the acquisition
function's "best" point is partly selected for a favorable noise draw on the two highest-variance
terms (SF1, bin7), not purely for better parameters. Read: **round 4's apparent 22% loss
improvement over round 0 (51.576→40.186) is mostly noise, not signal** — the confirmed value
(51.278) is within noise of round 0's confirmed-quality estimate.

**Problem 2: `max_follow=15.0` is pinned at the tightened range's lower edge**, the same boundary-
pinning red flag this document already treats as diagnostic of a mis-specified range rather than a
genuine optimum (see the first-calibration-attempt entry's `bc_dec`/`comfort_pp` pins above). The
2026-07-21 tightening rationale for `max_follow` was "[15,100]→[15,50], v1's winner sat at 65.9, no
evidence for going past that" — that check only ruled out needing to go *above* 65.9, it never
tested whether 15 (the pre-existing lower bound, untouched by the tightening) was itself
unconstraining. It looks like it may not be.

**Problem 3: the 7-bin posting-shape term is the dominant, non-converging loss component
throughout.** It was the largest single term at round 4 (27.023 of 40.186, 67%) and got worse, not
better, by round 11/confirm (34.742). Posting proportions at the confirmed point vs. empirical
target: bin0 0.304 vs 0.267, bin1 0.124 vs 0.165, bin2 0.038 vs 0.093, bin3 0.328 vs 0.132, bin4
0.032 vs 0.043, bin5 0.063 vs 0.071, bin6 0.111 vs 0.230 — badly overshooting bin3 (moderate/
lean-right-ish) and undershooting bin6 (the most-extreme-in-that-direction bin), the opposite
direction from what "extremity drives posting" would predict. Twelve rounds of BO across 11
free dims never brought this down; open question, not yet resolved, whether `comfort_pp`/
`initial_pp` can reach the empirical non-monotonic shape at all under the existing posting
mechanism, or whether the mechanism's functional form structurally can't reproduce it regardless
of tuning.

**Status: this point is not adopted as the app-pol baseline.** Full log:
`docs/report/app_pol_baseline_v2_bo_evaluations.csv` (72 rows), confirm:
`app_pol_baseline_v2_bo_confirm.csv`, CCDF (validation-only): `app_pol_baseline_v2_indegree_ccdf.{csv,png}`.
Next-step options flagged to user, not yet decided: (a) re-open `max_follow`'s lower bound below 15
and re-run; (b) increase `SEEDS_PER_POINT`/`CONFIRM_SEEDS` to shrink the noise gap that's driving
the winner's-curse effect, at the cost of fewer rounds/points for the same wall-clock budget; (c)
investigate whether the posting mechanism can structurally reach the empirical 7-bin shape before
spending more compute on searching around it.

## Calibration v3 (2026-07-22): asymmetric loss weights, Wasserstein bin7, and an SF1 circularity investigation

User's framing (2026-07-22): given the whole calibration history, gini/Q_sign_repost have
consistently been "the easy part" of this model to fit, so app-pol (SF1) and the 7-bin posting fit
should matter more in the loss — asked whether asymmetric weighting made sense, and separately
whether including *both* SF1 and bin7 is a problem given they're "genuinely correlated."

**Empirical check of the weighting premise (72 already-evaluated v2 points).** Recomputed each
loss term's cross-point Pearson correlation. Gini: ~zero correlation with everything (r=-0.02 vs
SF1, r=-0.15 vs bin7) — genuinely orthogonal, and close to target (0.8) in nearly every calibration
this project has run (v7: 0.850; static-bc: 0.869; this run: 0.74). Q: moderately entangled
(r=0.45-0.56 with SF1/bin7) but still comparatively easy historically. **SF1 and bin7 correlate
strongly (r=-0.75, old sum-of-squares bin7 formula)** — confirms the user's premise: these two are
substantially redundant, not independent evidence.

**Wasserstein-1 for bin7 (user's proposal, adopted).** The old bin7 formula (sum of 7 squared
per-bin proportion differences, each divided by a flat 0.05 scale) treats the 7 ideology bins as
unordered categories — a mismatch between adjacent bins costs the same as one between opposite
extremes, which is wrong given the bins are ordered (−3…+3). Also structurally overweights bin7 by
~7x relative to any scalar term purely from summing 7 components, an artifact of dimensionality
rather than a deliberate weighting choice. Switched to Wasserstein-1 distance (`scipy.stats.
wasserstein_distance` over the 7 ordered bin centers, weighted by proportions) — respects bin
ordering, collapses to one scalar. Recomputed on the real per-seed `post_bin7.csv` files still on
disk from the v2 run (`scripts/retro_wasserstein_check.py`, 360 seed-evaluations): mean W1=0.666,
std=0.321. New-formula correlation with SF1 is if anything *stronger* (r=-0.81) than the old
formula's (r=-0.75), and the new W1 correlates r=0.94 with the old bin7 metric — same underlying
construct, better-shaped.

**SF1/bin7 arithmetic circularity — directly verified, not just suspected.** Computed the SF1
formula (`Var(opinion, post-count-weighted) / Var(opinion, population-weighted)`) directly on the
raw 7-bin survey numbers already in `Const.java` (`EMPIRICAL_OPINION_BIN_COUNTS`,
`EMPIRICAL_POST_BIN_WEIGHTS`), no simulation involved: **result = 1.1916**, matching the
literature's "1.19 full-period" target almost exactly. This is very unlikely to be coincidence —
the SF1 target and the bin7/init-distribution targets are most likely the same underlying dataset
computed three different ways, not three independent empirical facts. Real consequence for the
paper's write-up: cannot claim three independent validations from what's effectively one dataset.

**First instinct (dropping SF1 from the loss entirely) was tested and reversed.** Reasoning: if
SF1 is ~implied by bin7+init already, keep it out of the loss (validation-only, like CCDF) to avoid
triple-counting. Retro-scored all 72 v2 points under a trial loss with SF1 removed
(`scripts/retro_wasserstein_check.py`): the new top point (round 10, point 3) had an excellent
Wasserstein bin7 fit (0.529, well under the 0.666 mean) but SF1=0.702 — badly off target, wrong
direction. This demonstrates the static-data circularity argument does **not** reliably transfer to
the simulated dynamics: 20,000 steps of bc/network/posting dynamics sit between bin7 (cumulative,
intrinsic opinion) and SF1 (final-step, current/drifted opinion), and can decouple them. r=-0.81
leaves ~35% unexplained variance — real slack that active BO optimization (unlike passive
re-ranking) will hunt for and exploit if the loss gives it no reason not to.

**Noise-vs-signal check on round10/pt3 (2026-07-22, user: "cheap check first please").** Before
trusting that single 5-seed decoupled point as evidence, checked whether SF1=0.702 there was a real
feature of the point or a noise draw (SF1 already documented as needing ~85+ seeds to resolve
reliably). Re-evaluated the exact same parameters with 20 fresh seeds
(`scripts/round10pt3_noise_check.py`, seeds 1030000-1030019): individual values ranged wildly
(0.13 to 1.70, std=0.352, confirming the noise problem is real), fresh-20 mean=1.002. Pooled
25-seed estimate: **mean=0.942, std=0.347, SEM≈0.069, 95% CI ≈ [0.81, 1.08]** — still entirely
below the [1.19,1.26] target even accounting for the noise. **Conclusion: the decoupling is real,
not a sampling artifact** — the original 5-seed reading (0.70) was itself a somewhat unlucky low
draw (true value closer to ~0.94), but the better estimate still misses the target by a wide,
noise-robust margin. This vindicates keeping SF1 in the loss rather than dropping it: without it, a
BO search could and plausibly would drift toward exactly this kind of bin7-good/SF1-bad corner,
which would be useless for the planned baseline (needs realistic apparent polarization to already
be present before the hub-secession causal test can say anything about collapsing it).

**Final v3 design, `scripts/app_pol_baseline_bo_v3_wasserstein.py`:** loss = `0.5*gini_term +
0.7*Q_term + 0.7*SF1_term + assort_floor_term + 1.0*bin7_wasserstein_term` (weights chosen from the
correlation/ease evidence above: gini downweighted most since it's orthogonal and historically
easy, Q downweighted less since it's moderately entangled, SF1 downweighted modestly — kept, not
removed, per the noise-check finding — bin7 at full weight as the primary empirical-fit criterion).
Also folded in the still-open v2 postmortem item: `max_follow` lower bound widened 15→5 (v2's
winner pinned at 15, never tested for headroom below). Retro-scored against the 72 v2 points before
launch: round 4's original v2 winner remains top-ranked under the new weights (not a wild
reshuffle, just re-emphasis). `BASE_SEED` bumped to 1020000 to avoid collision with v2's used seed
range. Smoke-tested end-to-end (single point, single seed) before commit — clean run, no errors.

**Launched (2026-07-22):** `nohup python3 scripts/app_pol_baseline_bo_v3_wasserstein.py` +
`disown`, pid 27617, logging to `logs/app_pol_baseline_v3_stdout.log`. Same structure as v2 (12
rounds × 6 points × 5 seeds, `n=1000, steps=20000`, `init_dist=empirical` and
`out_of_bc_repost_prob=0.01` both fixed). Expected runtime ~2.5-4 hours given v2's observed
per-round variance. Results to be logged here on completion, including whether the winner's-curse
confirm-gap and boundary-pinning problems from v2 recur under the revised design.

## Calibration v4 (2026-07-22): v3 killed after ~15min — SF1 excluded from the round loss entirely, selected post-hoc instead

User's pushback on v3 (correct, and sharper than the reasoning that produced v3): the 25-seed
round10/pt3 noise-check confirmed the bin7-good/SF1-bad decoupling is *real*, not sampling noise —
but that doesn't mean SF1 is safe to include as a **round-level** loss term (v3's design, at
reduced weight 0.7). Computed the typical per-point SF1 measurement noise at the sampling budget
actually used during BO rounds (n=5/point), across all 72 v2-evaluated points: mean per-point std
= 0.190, giving a typical SEM of 0.085 and a **95% CI half-width of ~0.166 — more than double the
entire target window's width** (1.19 to 1.26 = 0.07 wide). At n=5, the SF1 mean-miss loss term
cannot resolve whether a point is inside the target window at all; it can barely distinguish
"clearly low" (~0.7) from "clearly high" (~1.3). Including it in the round loss, even at reduced
weight, doesn't steer the search toward the target — it injects measurement noise into the
acquisition function. This is very likely the actual mechanism behind the winner's-curse
confirm-gap already seen twice (v1's 5-dim run, v2's 11-dim run) — not a coincidence of unlucky
seeds, but a structural mismatch between the target window's width and what n=5 can measure.

**v3 killed** (pid 27617, ~15 min into round 0, no completed rounds, no `opt.tell()` calls made —
nothing to warm-start from; user confirmed starting the BO search from scratch was fine). No
orphaned JVMs left behind (verified via `pgrep`).

**v4 design** (`scripts/app_pol_baseline_bo_v4_topk_sf1select.py`):
1. Round-level loss = `0.5*gini + 0.7*Q_sign_repost + assort_floor + 1.0*bin7_wasserstein` only —
   SF1 fully excluded from `opt.tell()`. Still computed and logged every round for visibility.
2. After 12 rounds, take the **top 5** points by round loss (not just the single best) and
   re-evaluate each with **20 fresh seeds** (SEM≈0.043, 95% CI half-width≈0.083 — real resolving
   power against the 0.07-wide target window, unlike n=5). Select whichever of the 5 lands closest
   to the SF1 target midpoint (1.225). This uses SF1 exactly where it has statistical power (a
   20-seed comparison among a short, already-good-on-everything-else shortlist) and nowhere it
   doesn't (n=5 × 72 points is neither affordable nor informative for a 0.07-wide target). This
   selection stage doubles as the final confirmation report — no separate low-n confirm run after.
3. Everything else retained from v3 unchanged: Wasserstein-1 bin7 term, `max_follow` lower bound
   widened to 5, gini/Q asymmetric downweighting (independently justified by the correlation
   evidence, not affected by the SF1-noise finding).

Smoke-tested end-to-end (single point, single seed) before launch — clean run, SF1 correctly
computed/reported but excluded from `round_loss`. **Launched:** `nohup python3 scripts/
app_pol_baseline_bo_v4_topk_sf1select.py` + `disown`, pid 28135, logging to
`logs/app_pol_baseline_v4_stdout.log`. `BASE_SEED=1040000` (distinct from v1/v2/v3's ranges).
Expected runtime: ~2.5-4h for the 12-round search plus ~5 additional round-equivalent batches
(20 seeds × 5 candidates, run sequentially at 20 concurrent JVMs each) for the top-K SF1 selection
stage. Results — including whether any of the top-5 round-loss candidates actually lands near the
SF1 target, and if not, what that implies about whether this parameter space can jointly satisfy
gini/Q/bin7 and SF1 at all — to be logged here on completion.

## v4 result and a second real bug found in the bin7 metric (2026-07-22)

**v4 completed.** 12 rounds ran, top-5 candidates re-evaluated at n=20. Selected candidate:
`max_follow=5.0, follow_prob=0.054, alpha=0.803, hop=4, bc_dec=0.814, bc_recovery=0.0,
bc_init=0.503, stub=0.599, comfort_pp=2.893, feed_capacity=30, initial_pp=0.357`. Structural facts
reasonable (gini=0.883±0.005 vs 0.8, assort=0.996±0.0004 vs 0.6 floor, Q=0.432±0.022 vs 0.48) but
**two problems**: (1) `max_follow=5.0` pinned at the *new* lower bound — same red flag as v2,
just relocated, range widening didn't resolve it, only moved it; (2) **none of the top-5
candidates reached the SF1 target even at n=20** (well-powered) — SF1 = 1.072, 1.003, 0.968, 0.900,
0.885, all below [1.19,1.26]. Not a noise artifact this time (n=20 has real resolving power) — a
genuine sign of tension between the gini/Q/bin7 objectives and SF1 in this parameter space.

**User question that surfaced a second real bug:** "does the model activate pure moderates too
much?" Investigating this by pooling the winning candidate's 20 post_bin7.csv files revealed that
`post_bin7.csv` tracks **both** `popCount` and `postCount` per bin (`Writer.writePostBin7`), but
every version through v4 only ever read `postCount` (raw total) and compared it against
`EMPIRICAL_POST_BIN_PROPORTIONS` — which is actually a **per-capita rate** (mean posts per survey
respondent in that bin), not a population-weighted total-volume share. Since the model's realized
bin populations are wildly unequal under `init_dist=empirical` (moderates ~3-5x more numerous than
the extreme bins), comparing raw total volume to a per-capita target silently conflated "how much
each person posts" with "how many people are in that bin" — an apples-to-oranges bug present since
the empirical-7-bin feature was introduced (this session, 2026-07-21), affecting v2/v3/v4 alike.

**Corrected per-capita analysis of v4's winner** (postCount/popCount, pooled across its 20 seeds):
```
model per-capita rate (posts/agent) by bin: [1824, 1737, 1701, 1955, 1544, 1560, 1533]  -- nearly FLAT (~1.27x range)
empirical per-capita rate (real data):      691 to 4329 across bins                     -- 6.3x range
```
**Sharper, more correct diagnosis than "moderates over-post":** the model barely differentiates
posting intensity by opinion extremity *per person* at all. The raw-volume picture (moderates
dominating total posts) was mostly a population-size artifact — bin 3 has the most agents, so
naturally produces the most total posts, even though no individual moderate posts unusually often.
This directly explains the SF1 shortfall too: without real per-capita selective-amplification of
extreme voices, post-opinion variance can't rise much above population variance (SF1≈1).

## v5 (2026-07-22): bin7 metric fixed to per-capita rate; vocal_comfort_radius added as a 12th free dimension

**Fix:** `bin7_wasserstein(post_counts, pop_counts)` now normalizes `postCount` by the model's own
realized `popCount` per bin before comparing to the (already per-capita) empirical target, instead
of comparing raw totals. `read_metrics`/`evaluate_seed` now also return `pop_counts`.

**Quick 3-seed check (user request, before committing to a full relaunch)** against v4's winning
params: corrected bin7 W1 = 0.539±0.009 (n=3) — actually somewhat *better* than the old buggy
metric's 0.568, not worse, but the underlying per-capita proportions confirm the flat-rate finding
and sharpen it: model `[0.156, 0.148, 0.137, 0.169, 0.145, 0.130, 0.116]` vs. empirical target
`[0.267, 0.165, 0.093, 0.132, 0.043, 0.071, 0.230]` — real data spikes at **both** extreme bins
(0 and 6) with a dip in the middle; the model shows none of that U-shape, just a narrow band.

**New free dimension added:** `vocal_comfort_radius` (`Agent.java`'s `withinComfort` gate driving
the `comfort_pp` postProb boost/penalty — the vocal-minority mechanism). Fixed at its 0.2 default
in every calibration from v1 through v5 despite an explicit 2026-07-19 code comment noting it was
promoted to a sweepable CLI param specifically to test "whether the fixed absolute window is what's
suppressing SF1 apparent polarization" — never actually tested until now. Added as
`Real(0.02, 0.5, prior="log-uniform", name="vocal_comfort_radius")`, log-uniform to resolve narrow
(sharper gating) values well. 12-dim smoke test passed (`vcr-0.1000` correctly appears in the run's
output tag, confirming the CLI wiring); at that single arbitrary test point SF1 happened to land at
1.220 (within target) — not evidence on its own, but a reasonable sign the dimension is live.

**Launched:** `nohup python3 scripts/app_pol_baseline_bo_v5_percapita_bin7.py` + `disown`, pid
32223, logging to `logs/app_pol_baseline_v5_stdout.log`. Same structure as v4 otherwise (12 rounds
× 6 points × 5 seeds round-level loss with SF1 excluded, then top-5 × 20-seed SF1 selection stage).
`BASE_SEED=1050000`. Note: `results/` has grown to ~202GB from this session's accumulated runs
(v2 through v5) — not yet a problem (1.5TB free) but worth cleaning up old run directories once
this search's outputs are no longer needed for retro-checks, rather than left to grow unbounded.

## v5 completed and adopted into ExperimentConfig.java defaults (2026-07-22)

12 rounds + top-5×20-seed selection finished. Winner: `max_follow=5.0, follow_prob=0.0670,
alpha=0.8432, hop=5, bc_dec=0.8202, bc_recovery=0.0, bc_init=0.4141, stub=0.5857,
comfort_pp=1.6255, feed_capacity=36, initial_pp=0.0478, vocal_comfort_radius=0.1257`. Structural
facts solid (gini=0.848±0.011, assort=0.996±0.0003, Q=0.438±0.019); bin7 (per-capita) improved to
0.444±0.055 (vs. v4's corrected 0.539). **SF1 still missed target**: 1.027±0.078 (n=20, target
[1.19,1.26]) — and adding `vocal_comfort_radius` as a free dim didn't close the gap; all 5 top
candidates landed 0.927–1.027, arguably narrower than v4's spread. `max_follow=5.0` pinned at the
lower bound for the **third** calibration running (v2: 15, v4: 5, v5: 5) — still unresolved.

Adopted all 12 searched dimensions into `ExperimentConfig.java`'s defaults (user request: "reflect
the optimized param to exp config"), each field commented with old value + pointer to this report.
Deliberately left `outOfBCRepostProb`/`initOpinionDist` untouched at their pre-existing defaults —
those were fixed experiment-specific treatment choices for this calibration, not searched
parameters. (`outOfBCRepostProb` was subsequently changed to 0.01 by a separate, user-side edit —
noted here for the record, not something this session's calibration adoption did.) Compiled clean,
`ModelTests` unchanged (2 pre-existing failures only) at adoption time.

## The real mechanism, found by inspection, not search (2026-07-22)

User's diagnosis, from examining the adopted v5 point directly: **bc converges to a uniform 0.2
(the floor) for essentially all agents**, regardless of opinion. This is not a bug in a single run —
it's mathematically forced by `bcRecoveryRate=0.0` (the v5 winner's own value): with no recovery
term at all (`bc += 0 * (bcInit - bc)` is always zero) and decline firing on any out-of-bc contact,
bc is a pure one-way ratchet to the floor. Over 20000 steps it's essentially impossible for any
agent to never once encounter disagreement, so bc collapses to 0.2 for extremists and moderates
alike. **This explains the pattern spanning this entire session**: gini/Q/assort/bin7 have
consistently been "the easy part" while SF1 has never once reached target, across v1's original
defaults, v7, v9's static-bc, and every app-pol variant (v2-v5) — because a uniform bc-collapse
regime is what best satisfies the *structural* metrics, and that regime is exactly what forecloses
extremity-dependent echo-chamber formation, which SF1 depends on. Every search variant has been
correctly hill-climbing toward an optimum that structurally cannot produce the outcome needed.

User's proposed fix: asymmetric bc by extremity (narrow for extremists, wide for moderates),
achieved the same way as in their own prior JCSS paper — smooth, *emergent* asymmetry from tuning
the existing decline/recovery dynamics (not hard-coding opinion into the bc formula). Key insight:
`bcRecoveryRate` needs to be small-but-nonzero, not free to hit exactly 0.

### Literature grounding (2026-07-22)

- **wssit2026-TomoyaTakeda.tex's own "Confidence Decline" section** (this project's target paper)
  already cites Vallone, Ross & Lepper (1985, "hostile media effect") and Baumeister, Bratslavsky,
  Finkenauer & Vohs (2001, "Bad is Stronger than Good") for the asymmetric-negativity premise
  behind bc decline — but qualitative only (direction, not magnitude), and notably **the paper's
  own formal model has no recovery term at all**, just one-way decline. The codebase's
  `bcRecoveryRate` (content-independent passive drift) was added later (2026-07-18) as an
  engineering fix for boundary-collapse, never meant to represent "positive experience."
- **Deffuant-style fixed-uncertainty extremists** (JASSS 19/1/6, building on Deffuant, Amblard,
  Weisbuch & Faure 2002): extremists assigned uncertainty `u_e`, moderates `u`, ratio `u/u_e ≈ 100`
  kept fixed in their experiments. Directionally strong precedent, but a discrete two-group ratio
  in a stylized model, not a continuous correlation coefficient in a continuous one — not directly
  importable as our bc-extremity correlation's threshold.
- **Li, Luo & Porter (2023), "Bounded-Confidence Models of Opinion Dynamics with Adaptive
  Confidence Bounds" (arXiv:2303.07563)** — the load-bearing citation. Their eq. 2.3 gives exactly
  the functional form adopted below: `c(t+1) = c(t) + γ(1-c(t))` if receptive (in-bound contact),
  `c(t+1) = δ·c(t)` if not. Their `δ` (confidence-decrease) is exactly our existing `bcDecRate`;
  their `γ` (confidence-increase) is what `bcRecoveryRate` is redefined to mean below. Their tested
  ranges (`γ∈{0,0.0001,...,0.1}`, `δ∈{0.01,...,1}`, headline example `γ=0.001, δ=0.5`) anchor the
  new search range, rather than guessing one.

### Implementation (2026-07-22)

**`Agent.java`** (`updateMyself()`): decline unchanged (`bc *= bcDecRate` on out-of-bc contact,
`bcDist > this.bc`). Recovery redesigned from content-independent passive drift toward `bcInit` to
content-triggered growth toward `bcCeiling`, mirroring decline's shape and Li/Luo/Porter's eq. 2.3:
`bc = min(bc + bcRecoveryRate*(bcCeiling - bc), bcCeiling)`, firing only when `bcDist < this.bc`
(the same condition already gating FJ assimilation). `vocalComfortRadius`'s separate, fixed-window
comfort mechanism (postProb boost) is untouched — still deliberately decoupled from bc.

**`Analysis.java`**: new `computeBcExtremityCorrelation(Agent[])` — Pearson correlation of
`(|opinion|, bc)` across all non-target agents, same pattern as `computeOpinionAssortativity`.
Computed within-run at n=1000, far better powered than SF1's cross-seed comparison. Wired into
`OpinionDynamics.buildMetricsRow()` as a new `bcExtremityCorrelation` results.csv column.

**`ModelTests.java`**: updated the two hardcoded-default assertions that referenced stale values
(`bcDecRate==0.561`, `outOfBCRepostProb==0.0`) to the current adopted defaults (0.8202, 0.01).
Compiled clean; test suite back to the same 2 pre-existing failures (`p_u` tag, distinct-tag).

**Verified via a direct smoke run** (arbitrary point, `bc_recovery=0.01`): `meanTolerance=0.901`
(vs. the old floor-collapsed 0.2), `toleranceVar=0.0655` (real spread, not uniformly zero),
`bcExtremityCorrelation=-0.277` (negative, as hypothesized), SF1=1.583 (above target range, at an
unoptimized point) — strong confirmation the redesign produces genuine bc heterogeneity.

## Calibration v6 (2026-07-22): asymmetric-bc mechanism + bc-extremity correlation floor term

`scripts/app_pol_baseline_bo_v6_asymmetric_bc.py`. Changes from v5:
- `bc_recovery`'s range narrowed to `[0.0001, 0.05]` log-uniform (was `[0.0, 0.3]` linear),
  anchored on Li/Luo/Porter's own tested range rather than a box wide enough to let the search
  collapse back to ~0.
- New round-loss term: `bc_extremity_corr` must be ≤ **-0.1** (user's call — a direction-enforcing
  ceiling, not a literature-derived magnitude, since neither Vallone/Baumeister nor Li/Luo/Porter
  give a numeric target for this specific relationship, and Deffuant/JASSS's 100x ratio isn't in
  comparable units). Included in the round loss (unlike SF1) since it's computed within-run at
  n=1000 — well-powered, comparable reliability to gini/Q.
- Everything else unchanged from v5 (per-capita bin7 Wasserstein, SF1 excluded from round loss +
  top-K post-hoc selection at n=20, gini/Q asymmetric downweighting, `max_follow` lower bound at 5,
  `vocal_comfort_radius` free).

Smoke-tested end-to-end (12-dim space, new `bc_extremity_corr` term computed and logged correctly)
before launch. **Launched:** `nohup python3 scripts/app_pol_baseline_bo_v6_asymmetric_bc.py` +
`disown`, pid 46059, logging to `logs/app_pol_baseline_v6_stdout.log`, `BASE_SEED=1060000`. Same
12-round + top-5×20-seed structure as v4/v5.

**Housekeeping:** cleaned up `results/` (293GB → 49MB) before this launch — entirely gitignored,
untracked, and every prior run's conclusions were already captured in this report or the
`docs/report/*.csv` summaries, so the raw per-seed output was safe to discard. Added a
"Server/resource awareness" subsection to `CLAUDE.md`'s "Running experiments" section per user
request: monitor `results/` disk usage periodically during long calibration work (not just when
pressure is already suspected), be mindful of concurrent-JVM RAM headroom (`-Xmx2g` × concurrency),
and treat unexplained run-time slowdowns as a possible resource-pressure signal worth checking
before assuming it's just noise.

## v6 completed; v7 (2026-07-22): bc_init fixed high, dropped from search; progressive-fidelity round schedule

**v6 result.** 12 rounds + top-5×20-seed selection finished. Winner: `max_follow=14.18,
follow_prob=0.086, alpha=0.5, hop=2, bc_dec=0.770, bc_recovery=0.000223, bc_init=0.2, stub=0.704,
comfort_pp=1.102, feed_capacity=37, initial_pp=0.491, vocal_comfort_radius=0.191`. Structural facts
solid; `bc_extremity_corr=-0.164±0.110` — past the -0.1 ceiling, mechanism fires. **SF1=1.091±0.116
(n=20) — closest any version has gotten (gap=0.134 vs. v4/v5's ~0.198), but still short of
[1.19,1.26].** New boundary pins: `alpha=0.5` (lower edge) and `bc_init=0.2` (lower edge, = bcFloor).

**User diagnosis of *why* v6's mechanism "worked" for the wrong reason.** With `bc_init=0.2`
(already at the floor) and `bc_recovery` tiny, every agent starts maximally narrow — decline has
nowhere to go, since bc can't drop below where it already sits. The only thing that can move bc at
all is recovery (growth toward the ceiling on comfortable contact), and *who* gets early comfortable
contact, before any homophily-driven network sorting, is purely a function of local density in the
opinion distribution: moderates (bin 3 alone is ~27% of the population) are far more likely to have
a same-ish-opinion neighbor within a narrow window by chance than sparse extremists. So moderates
get lucky, trigger growth, drift toward the ceiling; extremists rarely do, stay at the floor. This
reproduces the target correlation sign, but via "who started with agreeable neighbors" — not "who
experiences more disagreement over time," which is the actual negativity-dominance mechanism this
whole design is grounded in (Vallone 1985; Baumeister 2001; wssit2026-TomoyaTakeda.tex's own
"Confidence Decline" section). User: "it is more like all the agents has wide bc at first" and only
extremists narrow it — the reverse of what v6 found.

**Why didn't BO find the bc_init≈1 region itself, if it's supposedly the "right" one?** Not
necessarily a search failure — `bc_extremity_corr` (like the rest of the loss) only measures the
*final* correlation, with no way to distinguish which causal pathway produced it. Both "narrow
start, moderates get lucky" and "wide start, extremists genuinely narrow" are observationally
equivalent to a loss function that only checks the outcome — a classic specification-gaming
pattern, not a bug in the optimizer. Separately, genuine BO limitations plausibly contributed too:
72 evaluated points across 11-12 dimensions is a sparse budget (a crude 3-level grid alone would
need ~500K points), each point's loss is itself noisy (n=5), and EI's exploration/exploitation
tradeoff can settle into deepening one basin rather than adequately probing a second, comparably-
good one if the landscape is multimodal — plausible here, and consistent with this session's
recurring boundary-pinning pattern (`max_follow` three times, now `alpha`/`bc_init` too).

**v7 changes** (`scripts/app_pol_baseline_bo_v7_wide_bc_init.py`):
1. `bc_init` dropped as a free dimension, fixed at `BC_INIT_FIXED=1.0` (=bcCeiling) for every
   agent. Forces decline to be the only thing that can move bc initially, so any resulting
   asymmetry has to come from extremists genuinely encountering more disagreement — the intended
   mechanism, not the v6 shortcut. Search space: 12 dims → 11.
2. **Progressive-fidelity round schedule** (user proposal, prompted by the BO-limitations
   discussion above): `ROUND_SCHEDULE = [(3 seeds, 10 points)]×6 + [(5 seeds, 6 points)]×6` —
   wide/cheap exploration first, narrow/precise refinement after, same spirit as Hyperband/
   multi-fidelity BO simplified to a 2-phase step change. Same total compute as the old flat
   12×6×5 schedule (360 JVM runs) but **96 distinct points instead of 72** — directly addresses
   the sparse-budget concern just diagnosed. Peak concurrency held at 30 JVMs throughout
   (unchanged). Seed allocation switched to a running counter (collision-safe under a variable
   seeds-per-point schedule, unlike the old fixed-arithmetic formula).

Smoke-tested both pieces (11-dim pipeline end-to-end; round-schedule seed-arithmetic dry-run,
confirmed 360 total JVM runs / 96 distinct points / zero seed collisions) before launch. At the
11-dim pipeline smoke test's single arbitrary point (`bc_init=1.0` fixed): `bc_extremity_corr=
-0.121` (past ceiling) and `SF1=1.180` (within a hair of the target range) — encouraging single-
point signal, not yet a result.

**Launched:** `nohup python3 scripts/app_pol_baseline_bo_v7_wide_bc_init.py` + `disown`, pid 49819,
logging to `logs/app_pol_baseline_v7_stdout.log`, `BASE_SEED=1070000`.

## Concrete secession-test design, locked while v7 runs (2026-07-23)

User revived the identity-swap design (parked as the "confound at scale"/substitution problem on
2026-07-21, lines 113-133 above) with a refinement — swap *all* occupants of a designated tier at
once, never a partial subset — and asked for a critical read before locking it in. Cross-checked
against `wssit2026-TomoyaTakeda.tex` directly (not from memory) as part of that review.

**Primary-source cross-check (2026-07-23).** §3.2 (lines 421-514) operationalizes the paper's
headline claim differently than this new design: 3 agents with **fixed** opinion (−1, 0, +1),
each independently toggled **Active/Inactive on posting+repost probability** (2³=8 combinations,
the `(A,I,A)`-style notation `research-direction.md` inherits). The causal lever there is
**activity**, with opinion/position held fixed by construction — the reverse of the lever designed
here (fix behavior rules, swap opinion/position). Both are legitimate tests of the same broad
hypothesis but are **not the same experiment**; state this explicitly in any writeup rather than
presenting the swap test as a direct reproduction of wssit2026's method.

**Decisions (user, 2026-07-23):**

1. **Swap timing: at t=0 (post network-generation, pre dynamics-loop), not an equilibrium branch.**
   User's rationale for reopening this after having "defeated the idea before": the `hk`
   network-generation step already produces real degree heterogeneity before the ABM dynamics
   loop starts (unlike a blank graph), and the dynamics phase's rich-get-richer/preferential-
   attachment-style growth makes a non-hub moderate *overtaking* a swapped former-hub's rank
   possible but not the near-guaranteed outcome an equilibrium-branch design would face. Mitigation
   for the substitution risk this doc already flagged (2026-07-21, lines 113-133): **check the
   degree-rank tier's opinion composition at the end of the treatment run, in both arms** — direct
   evidence on whether substitution happened, rather than assuming it away. Concretely: at the
   final step, report what fraction of the (still-defined) tier's occupants are the originally-
   swapped agents vs. new entrants, and each entrant's opinion class.
2. **Tier definition: betweenness / cross-camp hop-reach, not raw in-degree** (confirmed over
   reusing the existing in-degree-rank tiers as-is). Not yet implemented in `Analysis.java` — new
   instrumentation needed. Recommended (not yet confirmed by user): build **cross-camp
   hop-reachability** first (count of opposite-camp agents reachable within `feedHopH` hops of a
   candidate node) as the primary metric, since it directly operationalizes the model's own
   recommender mechanism — the channel the user's stated hypothesis (mid-tier moderates matter via
   hop-based distribution) actually names — with betweenness centrality as a secondary/robustness
   cross-check (a more generic graph concept, not tied to this model's specific `feedHopH`
   mechanic).
3. **Scope: identity-swap arm only for now.** A wssit2026-style activity-toggle arm (post/repost
   probability Active/Inactive, opinion held fixed — the original paper's actual lever, per the
   cross-check above) is explicitly parked as a separate follow-up experiment, not folded into this
   one — logged here so the position-vs-activity distinction isn't lost by the time that follow-up
   is designed.
4. **Swap value: `opinion := sign(original opinion) × 0.8`, fixed for the first run.** User flagged
   that pushing all the way to `±1` "gives another problem" (not yet root-caused — plausibly a
   boundary interaction with `bcCeiling=1.0`/opinion-clip edge behavior) and chose `0.8` as a
   pragmatic value to avoid it, with swap magnitude left as a candidate sweep dimension for later,
   not resolved now.
5. **Block-swap-by-tier retained**: every occupant of a designated tier is swapped together,
   all-or-nothing, never a partial subset — closes the "arbitrary partial swap" ambiguity cleanly,
   though per decision 1 it does **not** by itself close the substitution risk (that's why the
   end-of-run composition check exists).
6. **Control/treatment structure**: control = fitted/calibrated dynamics, unmanipulated. Treatment
   = identical run, same seed distribution, except the designated tier's occupants have their
   opinion swapped per decision 4 before the dynamics loop starts. Compare SF1 (apparent
   polarization ratio), `Q_sign_repost`, cross-cutting exposure fraction, and
   assort/Gini (structural sanity checks) between arms. **Reading convention**: treatment *worse*
   than control on these = the expected/uninteresting direction (more extremity in the network →
   naively more polarized); treatment *better* (lower apparent/structural polarization than
   control) = the counterintuitive result this design is built to detect, via a position/bridging
   channel distinct from wssit2026's original activity channel (see cross-check above).

**Open, not yet decided:** seed count per arm — given this project's established SF1 noise floor
(~85+ seeds needed to resolve a real effect on that metric specifically), the cheaper structural
metrics (Gini/Q/assort, resolvable at n≈20) should likely be the primary readout, SF1 secondary/
exploratory, unless seed budget is scaled up specifically for it.
**Not yet started:** implementation (hop-reach metric in `Analysis.java`, the swap-treatment
runner scripts) — parked pending v7 calibration (still running as of this entry) landing, since
the treatment run needs a settled baseline to swap on top of.

## Tier basis resolved: two independent tier schemes, run and reported separately (2026-07-23)

Follow-up question: should the swap tiers be defined by follower-% bands (user's simpler proposal
this session) or by hop-reach/betweenness (the previous entry's decision)? **Decision (user,
2026-07-23): do both, but as two independent experiments, not one combined design** — neither
computed as a covariate of the other, per user's explicit "do it separately."

**Scheme A — follower-% bands.** Tiers by in-degree as % of population: `>30%`, `30-20%`,
`20-10%`, `10-5%` (lower bands TBD — extend downward if warranted once Scheme A's initial tiers are
characterized). Finer-grained version of the existing mega/mid/tail split in
`hub_tier_pct_summary.csv`/`hub_tier_pct_raw.csv` (2026-07-21 entry above) — no new instrumentation
needed, can be scaffolded from the existing hub-tier-characterization scripts directly.

**Scheme B — hop-reach bands.** Tiers by cross-camp hop-reachability (definition above: count of
opposite-sign agents reachable within `feedHopH` hops). Requires the new `Analysis.java` metric,
not yet built (see "Not yet started" above) — betweenness centrality remains a secondary/robustness
cross-check within this scheme, not a third independent scheme of its own.

Each scheme gets its own full tier set, its own control/treatment swap runs, and its own reported
result (decisions 1, 3-6 above — timing, scope, swap value, control/treatment structure, reading
convention — apply identically to both schemes; only the tier-assignment criterion differs).
Kept separate deliberately: this also gives a natural, already-planned check on the user's original
hedge ("maybe follower count isn't what matters") — if Scheme A and Scheme B pick out
materially different agents and produce materially different treatment effects, that itself is a
finding about which notion of "hub" is doing the causal work, worth reporting either way.

**Practical sequencing**: Scheme A has no code dependency on new instrumentation, so its tier-
extraction/runner scaffolding can start in parallel with v7 calibration and with Scheme B's
`Analysis.java` work — not blocked the way Scheme B is.

## v7 stopped mid-search: comfort_pp<1 found to invert the postProb mechanism (2026-07-22)

**v7 progress at stop time**: 66 points evaluated (rounds 0-6 of the wide+narrow schedule), best
round-loss 2.248, unchanged since round 0. Three points landed genuinely inside the SF1 target
range [1.19,1.26] — round0/pt1 (1.250, bc_corr=+0.326, wrong direction), round1/pt3 (1.221,
bc_corr=-0.342, right direction), round2/pt5 (1.207, bc_corr=-0.121, right direction, marginal).

**Finding**: the two highest-SF1 points overall (round2/pt0: 1.468; round5/pt7: 1.530 — both
*above* target, not in it) both had `bc_extremity_corr` exactly `0.0` (degenerate: bc has zero
variance, either because `bc_dec=1.0` froze it outright, or because feed algorithm curation is
homophilous enough that out-of-bc contact essentially never happens to trigger decline at all) —
and both had `comfort_pp=0.1`, the search box's floor. Tracing the mechanism: `postProb *=
comfortPpFactor` on comfortable contact, `/= comfortPpFactor` on disagreement. This reads as
"comfort boosts vocality" only when `comfortPpFactor > 1`; below 1.0 it silently **inverts** into
"disagreement boosts vocality" — an unintended, undocumented mechanism. The 0.1 floor traces back
to 2026-07-21's boundary-pinning fix (widened from 0.5, correctly following the same heuristic
already used for `bc_dec`/`max_follow`) — but unlike those parameters, 1.0 is a **qualitative**
regime boundary for this formula, not just another point on a continuous scale, and that distinction
was missed at the time.

**round1/pt3 confirmation (properly powered, n=20)**: this was the best in-target, right-direction
point at n=5 (SF1=1.221, bc_corr=-0.342, comfort_pp=1.18 — already satisfying the soon-to-be-added
constraint). Confirmed with 20 fresh seeds: **SF1 regressed to 1.105±0.312 (now outside target) and
bc_corr regressed to -0.084±0.196 (now failing the ceiling)** — another instance of the winner's-
curse pattern already seen multiple times this session (v1's original SF1 gap, v2's confirm gap,
v6's round10/pt3 check). **Not adopted.**

**v7 stopped** (pid 49819, clean kill, no orphaned JVMs — CPU was already fully saturated at 30
concurrent JVMs, per the new server-awareness habit, so a parallel confirmation run needed the slot
freed rather than oversubscribing).

## Calibration v8 (2026-07-22): comfort_pp constrained to [1.0,3.0], warm-started from v7

`scripts/app_pol_baseline_bo_v8_comfort_pp_gte1.py`. Changes from v7:
1. `comfort_pp` range constrained to `[1.0, 3.0]` (was `[0.1, 3.0]`) — excludes the inverted-
   mechanism region entirely.
2. **Warm-started** (user proposal: "can we use the past information... comfort pp over 1.0"):
   `load_warm_start_points()` reads v7's evaluations CSV, keeps every point with `comfort_pp>=1.0`
   (42 of 66 v7 points qualify — round_loss itself is unchanged between v7/v8, so directly reusable
   without re-simulating), and `opt.tell()`s them into the fresh `Optimizer` before the round loop
   starts — same technique as the earlier v2 crash-recovery resume script. Also seeded into the
   in-memory `rows` list so they compete for the final top-K selection alongside new v8 points.
   Verified via dry run before launch: 42 points loaded with correct types, `opt.tell()` succeeds,
   `opt.ask()` afterward returns points correctly respecting the new comfort_pp>=1.0 bound.
3. `ROUND_SCHEDULE` trimmed from 6 wide + 6 narrow (12 rounds) to **4 wide + 6 narrow (10 rounds)**
   — the warm start substitutes for some wide-exploration value. Peak concurrency still 30 JVMs.

**Launched:** `nohup python3 scripts/app_pol_baseline_bo_v8_comfort_pp_gte1.py` + `disown`, pid
56916, logging to `logs/app_pol_baseline_v8_stdout.log`, `BASE_SEED=1080000`. Confirmed at launch:
"Warm-started from 42 already-evaluated v7 points ..., best warm-start loss = 2.248" printed
correctly before round 0 began.

## v8 stopped mid-search; postProb mechanism replaced with graded relaxation (2026-07-23)

**v8 progress at stop time**: round 7/10, best round-loss still 2.248 (the warm-start baseline)
across all 7 rounds — no newly-evaluated point ever beat the points already known before v8 even
started. Given the bang-bang finding below, this now reads as expected rather than surprising: no
value of `comfort_pp` could escape the mechanism's structural failure.

**Diagnosis (user-initiated dashboard inspection)**: user ran `run.sh` with round1/pt3's exact
params (`ExperimentConfig`-equivalent tokens) and `log_gexf=true` (the calibration/confirmation
runs all used `log_gexf=false`, so no prior run had ever produced an inspectable network for this
point) — seeds 9000000-9000002, 3 seeds, dashboard's new run-set picker (`dashboard/core.py`
`log_groups()`, grouping by `logs/*.log` filename prefix) used to view it. User's read of the
network snapshot (`size` mapped to postProb, then to bc): three-cluster echo-chamber structure
(both extremes + center) with a graded valley at the mild-partisan (|op|~0.3) bins — a good
qualitative match to the empirical 7-bin W-shape — but flagged the center cluster as "a bit too
activated," and separately noted the bc histogram showing most high-bc agents stuck at the ceiling
with no separation between extreme/moderate echo chambers.

**Root-cause trace (Agent.java `updateMyself()`, lines around the old comfort_pp branch)**:
`postProb *= comfortPpFactor` when `comfortPostRate > 0.5`, `postProb /= comfortPpFactor`
otherwise. This has no restoring force — being on either side of the 0.5 threshold is self-
reinforcing (crossing it doesn't change which branch fires next step) — so postProb has no stable
interior point and saturates to `minPostProb`/`maxPostProb` for literally every agent, regardless
of *how* comfortable their feed was, only *whether*. `comfort_pp`'s magnitude only changes time-to-
saturation, never the destination. This is why v8's comfort_pp search (any value in [1.0,3.0])
could not move the needle: the whole search space shares the same degenerate endpoint.

**Fix — graded comfort→vocality relaxation**: replaced the ratchet with
`targetPostProb = minPostProb + (maxPostProb-minPostProb)*comfortPostRate`,
`postProb += eta*(targetPostProb - postProb)`. Because the update now depends on `postProb` itself
(the `-postProb` term), `targetPostProb` is a genuine stable equilibrium at *every* comfort level,
not just the two boundaries — an agent with `comfortPostRate=0.6` settles at a stable intermediate
vocality instead of eventually saturating like one at 0.95. Mathematically: the old rule is a pure
integrator on a fixed-sign input (no interior fixed point, structurally identical failure whether
the increment is multiplicative or, as briefly considered and rejected, additive-without-feedback
`pp += eta*(comfortRate-0.5)` — that variant was proposed and rejected in this same conversation for
the same reason: no `-postProb` term means no restoring force, same bang-bang endpoint, just a
different pacing to get there). The adopted rule is a discrete leaky integrator / exponential
relaxation toward a moving target, the standard form for "settle toward a state-dependent set
point," used in preference to the same idea as a manually-triggered code review would recommend.

**Code changes**: `Agent.java` `updateMyself()` (mechanism above, replacing the old branch);
`SimParams.java`/`ExperimentConfig.java`: `comfortPpFactor` renamed to `postProbRelaxRate`
(field default `0.01`, untuned placeholder — time constant ~100 steps, matching
`comfortHistory`'s window size); CLI key `comfort_pp` retired, replaced by `pp_relax_eta` (clean
rename, not a backward-compat shim — old `comfort_pp` values are not meaningful under the new
mechanism, so there was nothing to preserve). `tag()` updated (`_cpf-` suffix → `_ppeta-`).

**Smoke test** (seed 9100000, round1/pt3's other params held fixed, `pp_relax_eta=0.01`,
`log_gexf=true`, n=1000/steps=20000): postProb histogram at step 20000 spans the full
`[0.052, 0.915]` range across all 10 deciles, no rail spikes — the bang-bang artifact is
confirmed gone. **However**: `corr(|opinion|, postProb) = +0.107` (weak), and the 7-signed-opinion-
bin breakdown shows the center bin (|op|<0.14, n=251) at mean postProb=0.45, comparable to the
extreme bins (0.52, 0.47) rather than roughly half per the empirical target (bin3/bin0 ratio
~0.49) — the "moderates over-activated" problem the user flagged from the dashboard is **not**
resolved by this fix alone. Likely cause (already flagged in Agent.java's own 2026-07-19 comment):
`vocalComfortRadius` is a fixed absolute opinion-distance window, which structurally favors
moderates (dense region of the opinion distribution) with more neighbors falling inside any fixed-
radius window than extremists (sparse tails), by pure geometry — independent of genuine homophily
quality. (Side finding, out of scope: `bc` is still sharply bimodal — 212/1000 agents pinned at the
0.2 floor, 502/1000 at the 1.0 ceiling — the separate `bcDecRate`/`bcRecoveryRate` ratchet has the
same class of problem, untouched by today's change.)

**Decision on the remaining gap (user, explicit)**: proceed to calibrate the fixed mechanism as-is
rather than also fixing `vocalComfortRadius`'s density bias first. Rationale given: the system has
several interacting factors (feed velocity ranking, follow-graph homophily quality, bc's own still-
bimodal dynamics) whose aggregate effect on the extremity/vocality relationship isn't reliably
predictable analytically in a complex-systems model — better to let BO search the corrected
mechanism's full space and see empirically how far it gets before deciding whether the density-bias
fix is actually load-bearing. If v9's calibration still can't close the center/extreme gap, that's
now much stronger evidence the density-bias fix is required (bang-bang is no longer a confound).

**v8 stopped** (pid 56916, clean kill, no orphaned JVMs — process was already down to 2 in-flight
JVMs at kill time, both allowed to finish naturally).

## Calibration v9 (2026-07-23): graded postProb mechanism, fresh search (no warm start)

`scripts/app_pol_baseline_bo_v9_graded_postprob.py`. Changes from v8:
1. `comfort_pp` dimension replaced by `pp_relax_eta` (`postProbRelaxRate`),
   `Real(0.0005, 0.1, log-uniform)` — spans slow (~2000-step time constant, barely reaches target
   over a 20000-step run) to fast (~10-step, tracks comfortPostRate almost immediately).
2. **No warm start**: v7/v8's evaluated `comfort_pp` values have no meaning under the new
   mechanism (different functional form, not a rescaled range) — nothing valid to `opt.tell()`
   from. Fresh `Optimizer`, `ROUND_SCHEDULE` restored to the original 6 wide + 6 narrow (12
   rounds, 96 points total) since the warm start is no longer substituting for exploration.
3. Round-loss definition, weights, and the top-K/20-seed SF1-selection stage are all unchanged —
   this calibration only changes what postProb *is* as a function of comfort, not how the loss
   scores the outcome.

**Launched:** `nohup python3 scripts/app_pol_baseline_bo_v9_graded_postprob.py` + `disown`, pid
89799, logging to `logs/app_pol_baseline_v9_stdout.log`, `BASE_SEED=1100000`. Confirmed at launch:
round 0 (10 points × 3 seeds, 30 concurrent JVMs, seeds 1100000-1100029) started cleanly.

## v9 top-K re-selection: still no point clears both targets (2026-07-23)

**Bug found in v9's own selection stage** (before re-selection): `compute_round_loss`'s
`bc_extremity_corr` term is a one-sided ceiling penalty (`max(0, (bc_corr-ceiling)/scale)^2`) —
zero once a point clears -0.1, with no further credit for going more negative. round4/pt5
(SF1=1.187, bc_corr=-0.472 at n=5 — the best combined point across the whole 96-point search)
scored round_loss=3.79 and never reached the original top-5, because its exceptional bc_corr
bought zero marginal credit past the ceiling while its gini/bin7 terms were merely average. The
original top-5's SF1-closest winner had bc_corr=-0.029±0.070 at n=20 — fails the ceiling with real
margin, confirming the ranking that fed the selection stage was itself broken, not just unlucky.

**Fix**: `scripts/app_pol_baseline_v9_reselect_topk.py` re-scores all 96 already-evaluated v9
points with an unbounded linear `bc_corr` credit (`(bc_corr-ceiling)/scale`, no clamp) in place of
the squared one-sided term — same normalization, but rewards "how far past the ceiling," not just
"past it." Re-ranked; only 1 of the original top-5 survived. Added a 6th bonus candidate (best raw
SF1 among points already clearing the ceiling at n~3-5) to also cover the direct question. Re-ran
the properly-powered n=20 confirmation on these 6 (no re-simulation of the 96 search points
needed — reused `launch`/`evaluate_seed`/`aggregate` from the v9 module).

**Result: no candidate clears both criteria simultaneously at n=20**, out of 6 candidates chosen
specifically to fix the selection bug:

| candidate | SF1 (n=20) | bc_corr (n=20) | note |
|---|---|---|---|
| round7/pt5 | 1.097±0.151 | −0.097±0.095 | best SF1 gap (0.13), fails ceiling by a hair |
| round4/pt3 | 1.061±0.260 | −0.306±0.123 | **assort=0.585, fails the 0.6 floor at n=20** despite ~0.98 at n=3 — another confirmation-stage instability |
| round11/pt1 (bonus) | 1.006±0.378 | −0.182±0.123 | was the best n~5 SF1 (1.217); regressed and high-variance at n=20 |
| round4/pt5 | 0.996±0.217 | −0.346±0.138 | |
| round10/pt2 | 0.887±0.153 | −0.185±0.157 | |
| round6/pt4 | 0.928±0.419 | **−0.469±0.070** | strongest, tightest bc_corr; SF1 std too large to read |

**Read**: 5 of 6 do achieve a genuine (non-degenerate, tight-CI) negative bc_corr — a real
improvement over v7/v8's degenerate/near-zero bc_corr false-positives — but none simultaneously
lands in the SF1 target window. The candidate closest on SF1 (round7/pt5, gap 0.13) is also the
one that misses bc_corr, and the strongest bc_corr signal (round6/pt4, tight ±0.07) carries SF1
uncertainty too wide to say anything. Across 96 systematically-searched points plus this targeted
6-candidate follow-up, the postProbRelaxRate-corrected mechanism, on its own, has not produced a
point meeting both structural targets under proper (n=20) confirmation.

**Bearing on the deferred vocalComfortRadius question**: this is the empirical test the user's
2026-07-23 "let BO handle it, complex systems" call asked for. The result is now a real data point
in favor of the density-bias hypothesis (fixed-radius comfort window structurally favoring
moderates) being load-bearing, not just a plausible-sounding mechanism concern — the bang-bang
postProb bug is fixed, bc_corr is achievable on its own, and it *still* doesn't co-occur with
in-target SF1 anywhere in an 11-dim, 102-point search. Not acted on without explicit direction;
flagged for the user to decide the next step.

## v10: pU (unfollow probability) freed as a 12th calibration dim (2026-07-24)

**Context**: user inspected round7/pt5 in the dashboard at both steps=20000 (v9's calibrated
horizon) and steps=40000 (2x, run manually via `run.sh ... init_dist=empirical`, without
`steps=20000`) and judged segregation excessive even at the calibrated 20000-step point, not just
at the extended horizon. Diagnosed (this session) two independent one-way ratchets compounding: bc
decline/recovery (`bcRecoveryRate` ~385x weaker than `bcDecRate` at round7/pt5) and, newly
identified, `pU`-gated unfollowing -- `Agent.java`'s `unfollow()` has no re-follow mechanism
(`block()` is permanent), so pruned ties never reform. Neither has a genuine stationary point;
longer runs just show further progress along the same monotone drift, not a new phenomenon.

**Why pU was never calibrated before**: reserved throughout v1-v9 as `research-direction.md`'s "P_u
phase-diagram knob" -- the paper's originally-planned primary manipulated variable (sweep
`P_u x reactance`, locate the Type-1/Type-2 transition). User pointed out the 2026-07-21 secession-
test redesign (this same report, "Experiment redesign: secession test, not addition test")
superseded that framing -- the actual planned experiment manipulates `out_of_bc_repost_prob` (fixed
at 0.01) plus hub secession, with free calibration dims `hop, bc_dec, bc_recovery, bc_init,
comfort_pp` -- `pU` is absent from that list too, i.e. already not the treatment variable in the
design actually being built toward. Verified via grep: `p_u` was never in any
`scripts/app_pol_baseline_bo_v*.py` SPACE, confirming it was always held at its legacy default
(0.01) purely by inertia, not active design intent post-2026-07-21. With no experiment left that
needs it clean, decision (user): free it for calibration.

**`scripts/app_pol_baseline_bo_v10_unfollow_prob.py`**: adds `p_u`, `Real(0.0005, 0.1,
log-uniform)` (centered in log-space on the legacy 0.01 default, ~20x weaker to ~10x stronger), as
a 12th free dim. Warm-started from v9's 96 evaluated points, each padded with `p_u=0.01` -- valid
reuse (not an approximation): `compute_round_loss` doesn't depend on `p_u`, and those 96 points
were genuinely run at that fixed value, so their real `point_loss` is exactly what re-evaluating
the same 11-dim point at `p_u=0.01` in the 12-dim space would produce. (v9's reselection-pass
candidates were NOT reused -- their scoring used a different, exploratory bc_corr credit formula,
not comparable to `compute_round_loss`.) `ROUND_SCHEDULE` trimmed to 4 wide + 6 narrow (10 rounds,
76 new points) mirroring v8's warm-start trim -- the other 11 dims' joint structure at `p_u=0.01`
is already densely covered; fresh exploration mainly needs to resolve the new `p_u` axis.

**Launched**: `nohup python3 scripts/app_pol_baseline_bo_v10_unfollow_prob.py` + `disown`, pid 7533,
logging to `logs/app_pol_baseline_v10_stdout.log`, `BASE_SEED=1200000`. Confirmed at launch:
"Warm-started from 96 already-evaluated v9 points (padded with p_u=0.01), best warm-start loss =
2.500" -- matches v9's own best round-loss exactly, confirming the padded reuse is computing
correctly before round 0 began.

## SF1 batch-to-batch reproducibility check (2026-07-24)

**Trigger**: v10's top-K confirmation stage re-evaluated the literal same parameter point as v9's
original candidate 0 (identical 11 dims, `p_u=0.01`) with a fresh set of 20 seeds. Result:
SF1=0.648±0.141, vs. v9's own confirmation of that same point at 1.032±0.157 -- a ~2.4-combined-SEM
swing between two "properly powered" n=20 reads of the *identical* configuration.

**Design** (user, 2026-07-24): rather than assume either read is representative, run
`scripts/app_pol_baseline_sf1_batch_noise_check.py` -- 10 independent n=20 batches (200 total
seed-evaluations) of that exact point, sequential (~20 concurrent JVMs/batch). Compares the
empirical std of the 10 batch-means against the theoretical prediction `pooled_std/sqrt(20)` (what
a single batch's own std implies the spread *should* be under simple iid sampling). If empirical
spread is substantially larger, that's direct evidence n=20's reported SEM understates the true
sampling variability for this metric/point -- not just "noisy," but a badly-calibrated error bar.

**Launched**: `nohup python3 scripts/app_pol_baseline_sf1_batch_noise_check.py` + `disown`, pid
12708, logging to `logs/sf1_batch_noise_check_stdout.log`, `BASE_SEED=1900000`, results also in
`docs/report/sf1_batch_noise_check.csv`. Launched slightly overlapping v10's own tail end (its
last top-K candidate) -- brief, bounded oversubscription (~40 JVMs vs. 32 logical cores for a few
minutes), RAM headroom checked and fine, judged acceptable given the short overlap window.

## ROOT CAUSE: v9-vs-v10 "same point, different result" was an uncontrolled pU default (2026-07-24)

**Symptom**: v10's top-K confirmation re-evaluated the literal same 11-dim parameter point as v9's
original candidate 0. Results differed far beyond sampling noise -- assort 0.978->0.806 (a metric
with std ~0.002!), Q_sign_repost 0.408->0.037, SF1 1.032->0.648, bin7 0.361->0.874. A 10-batch
(5 completed) reproducibility check of that point clustered tightly at SF1~0.63 (empirical
batch-mean std 0.023, TIGHTER than a single n=20's own std/sqrt(20) implies) -- ruling out both
sampling noise and bimodality. User correctly insisted it was mechanistic/environmental.

**Root cause (proven by controlled reproduction, not just inference)**: v9's `launch()` token list
never passes `p_u`, so v9 (and every calibration v1-v9) inherited the compiled `ExperimentConfig`
default for it. That default was **0.05** ("P_u phase-diagram knob" legacy value) and was changed to
**0.01** in the "launch v10" commit (1784cce, Tomoya, not an edit I made). v10 explicitly pins
`p_u=0.01` as its new 12th dim. So "the same point" ran at pU=0.05 in v9 and pU=0.01 in v10 -- a 5x
difference on the one axis v9 didn't control.

**Proof**: re-ran seed 1600000 (one of v9's actual confirmation seeds) with v9's exact other params
at both pU values. Same seed = deterministic, so any difference is pU alone:

| seed 1600000, only p_u differs | assort | Q_repost | SF1 | bc_corr | meanTolerance |
|---|---|---|---|---|---|
| p_u=0.05 (v9's default) | **0.9800** | 0.440 | 1.087 | -0.006 | 0.599 |
| p_u=0.01 (v10 explicit)  | 0.8031 | 0.018 | 0.402 | -0.386 | 0.259 |

The p_u=0.05 run reproduces v9's on-disk `assort=0.9800` to 4 decimals. Case closed.

**pU is a first-order structural lever** (bigger effect than most swept dims): raising it from 0.01
to 0.05 moves assort 0.80->0.98, Q_repost 0.02->0.44, SF1 0.40->1.09 (single-seed), and flips
bc_corr from -0.39 to -0.006. This makes sense mechanistically -- more unfollowing => stronger
homophilous sorting => higher assort/modularity, but also collapses the asymmetric-bc signal
(agents cut disagreeable ties instead of enduring them and narrowing bc). There is a real TENSION
here: pU=0.05 hits the structural targets better (Q=0.44 near the 0.48 target, assort well above the
0.6 floor) but has ~zero bc-extremity asymmetry; pU=0.01 has strong bc_corr (-0.39) but Q collapses
to 0.02, badly missing the modularity target. The "right" pU is a genuine open question, not a
nuisance to default away.

**Consequence 1 -- v10 is INVALID and must be discarded**: v10 warm-started by padding v9's 96
points with `p_u=0.01` and `opt.tell()`-ing them as if evaluated at pU=0.01. They were actually
evaluated at pU=0.05. So v10's GP was trained on 96 points mislabeled by 5x on the exact axis it was
meant to explore. Its "corr(p_u, loss)=-0.42" signal and its "no point beats warm-start / no
improvement" conclusion are both artifacts of corrupted training data, not real findings. The v10
run, its top-K selection, and the design-doc "v10" entry above are all superseded by this.

**Consequence 2 -- every calibration v1-v9 ran at pU=0.05**, but the ExperimentConfig now defaults
to pU=0.01 (external edit, "launch v10" commit). So the round7/pt5 baseline adopted into
ExperimentConfig, if re-run via run.sh after that edit, executes at pU=0.01 -- a DIFFERENT, much
less camp-structured regime (Q_repost ~0.02) than the pU=0.05 calibration that selected it. The
dashboard baseline and the calibration that chose it may be at different pU. To verify: check
whether the dashboard-confirmation folders (seeds 0-4) carry a `_pu-0.0500_` tag or not.

**Broader methodological lesson**: a calibration script that doesn't pass EVERY dynamics-relevant
parameter explicitly is silently coupled to the ExperimentConfig default, which can change between
runs (recompiles, external edits) and invalidate cross-run comparisons without any error. All
future calibration launch() token lists should pin every dynamics param, including ones "held at
default," so a run is fully specified by its own command line.

**Corrected path (proposed, not yet run -- pending user decision)**: redo the pU calibration
(call it v11) warm-started from v9's 96 points with the CORRECT label `p_u=0.05` (they are valid,
real evaluations -- just at 0.05, not 0.01), then let BO explore the pU axis honestly from there.
This recovers the warm-start value without the mislabeling. Alternatively, given pU's large effect
and the pU=0.05-vs-0.01 tension above, first decide whether the target regime is high-pU
(structure-matching, weak bc asymmetry) or low-pU (strong bc asymmetry, weak structure) before
spending another 10-round search.

## Calibration v11 (2026-07-24): corrected pU warm-start + min_pp=0.01

**User decisions**: (1) prioritize reaching the SF1 target over preserving bc_corr, given the
pU=0.05-vs-0.01 tension found above; (2) fix `min_pp=0.01` (was silently 0.05, unchanged since the
field's introduction) to test whether the postProb floor is propping up posting rates for
structurally low-comfort agents, contributing to the flat-instead-of-W-shaped bin7 fit.

**Verified before launching, not assumed**: hand-computed `compute_round_loss` for both pU regimes
using the seed-1600000 reproduction numbers -- Q_sign_repost's penalty alone is ~60 at p_u=0.01
(catastrophic miss of its 0.48 target) vs ~1.3 total round_loss at p_u=0.05. The existing,
unmodified loss function already strongly prefers the SF1-supporting regime once given correct
data -- no change to the bc_corr ceiling term or loss weights was needed to satisfy decision (1).

**`scripts/app_pol_baseline_bo_v11_pu_fix_minpp.py`**: copy of v10 with two fixes:
1. Warm-start relabeled: v9's 96 points padded with `p_u=0.05` (the value they were actually run
   at), not v10's wrong `0.01`.
2. `min_pp=0.01` added as a fixed launch() token (was implicit default 0.05 in every prior run).

Caveat noted in the script itself: v9's warm-start points were run at the OLD `min_pp=0.05`, so
reusing their `point_loss` under v11's new `min_pp=0.01` is not a perfectly literal match (unlike
p_u's fix, which is exact) -- accepted as a reasonable approximation since `min_pp`'s effect is
expected to be second-order and only enters `point_loss` via downstream structural metrics, not
directly.

**Launched**: `nohup python3 scripts/app_pol_baseline_bo_v11_pu_fix_minpp.py` + `disown`, pid 16008,
logging to `logs/app_pol_baseline_v11_stdout.log`, `BASE_SEED=1210000`. Confirmed at launch:
"Warm-started from 96 already-evaluated v9 points (padded with p_u=0.05, corrected from v10's wrong
0.01), best warm-start loss = 2.500" -- same warm-start loss value as v9/v10 (expected, since
point_loss values themselves are unchanged, only their p_u label was corrected) -- round 0 (30
JVMs, seeds 1210000-1210029) started cleanly.

## Calibration v12 (2026-07-24): bc_extremity_corr loss term fixed (ceiling -> target)

**v11 stopped** (round 4/10, clean kill pid 16008, no orphaned JVMs) -- not a bug, a loss-function
fix supersedes it; its 40 evaluated points are still valid data, reused in the warm start below.

**The fix**: `compute_round_loss`'s bc_corr term was `max(0, (bc_corr-CEILING)/SCALE)**2` with
CEILING=-0.1 -- floors at exactly 0 the instant bc_corr clears -0.1, giving zero further credit for
going more negative. Found while reviewing v11's early results: candidates with bc_corr=-0.32 and
-0.11 scored identically on this term, so the search had no incentive to find a stronger signal
than the bare minimum. User separately reassessed -0.1 itself against Cohen's (1988) correlation
effect-size convention (|r|~0.1 small, 0.3 medium, 0.5 large) -- -0.1 is only "small effect,"
barely clearing "not noise." -0.8 was proposed and rejected: across all 136 points evaluated so far
(v9's 96 + v11's 40), the single best bc_corr ever observed is -0.472 -- nothing has approached
-0.5, so -0.8 would not be a reachable target, just an arbitrary number. **Adopted: TARGET=-0.3**
(Cohen's "large effect" -- empirically a real stretch, only 12-16% of points across v9/v11 clear
it, but demonstrably reachable).

**New functional form**: `bc_corr_t = (bc_corr_mean - TARGET) / SCALE` -- linear, unbounded, no
square, no clamp (deliberately not the symmetric `term()` shape used for gini/Q/SF1, since there's
no reason "stronger than -0.3" should be penalized the way overshooting an empirical target would
be).

**Warm-start**: combined v9's 96 points (p_u=0.05 corrected, per v11's fix) + v11's 40 freshly-
evaluated points (real p_u, min_pp=0.01) = 136 points, all with `point_loss` RECOMPUTED via
`compute_round_loss` from their stored aggregate metrics under the new formula -- their on-disk
point_loss values were computed under the old ceiling-clamped term and would have silently
warm-started the search with the wrong objective otherwise. Sanity-checked before launch: v9's
strongest bc_corr point (-0.472) now gets a genuine bonus (-1.15 contribution, loss drops from a
recomputed 3.79-under-old-formula-equivalent to 2.64) instead of the flat 0 it got before.

**Launched**: `nohup python3 scripts/app_pol_baseline_bo_v12_bc_corr_target.py` + `disown`, pid
19727, logging to `logs/app_pol_baseline_v12_stdout.log`, `BASE_SEED=1220000`. Confirmed at launch:
"Warm-started from 136 points ..., best warm-start loss = 2.418" (already lower than v9/v11's 2.500
baseline purely from the bc_corr formula change re-scoring existing data) -- round 0 (30 JVMs,
seeds 1220000-1220029) started cleanly.

### v12 completed (2026-07-24): 10 rounds + top-K/n=20 confirmation -- SF1 and bc_corr still not
jointly achievable

Full 10-round schedule (`[(3,10)]*4 + [(5,6)]*6`, warm-started from 136 recomputed points) finished
cleanly; process exited normally (no longer in `ps`). Best round_loss stayed at the warm-start
value, 2.418, through all 10 rounds -- no fresh point beat the warm-started incumbent
(`max_follow=50, follow_prob=0.01, alpha=0.60, hop=2, bc_dec=0.943, bc_recovery=0.05, stub=0.9,
pp_relax_eta=0.1, feed_capacity=40, initial_pp=0.01, vocal_comfort_radius=0.0717, p_u=0.05`).

Top-5 by round_loss re-evaluated at n=20 for SF1 selection; **none clears both targets
simultaneously**:

| loss | bc_dec | vocal_comfort_radius | SF1 (target [1.19,1.26]) | bc_corr (target <= -0.3) |
|---|---|---|---|---|
| 2.418 | 0.943 (near-static) | 0.072 | 0.921 +/- 0.312 (short, gap 0.30) | -- |
| 2.644 | 0.758 | 0.057 | 1.000 +/- 0.163 (short, gap 0.23) | -- |
| 3.638 | 0.500 | 0.021 | 1.034 +/- 0.363 (short, gap 0.19) | -- |
| 3.697 | 0.670 | 0.021 | **1.044 +/- 0.343** (short, gap 0.18 -- closest) | -0.227 +/- 0.150 (short) |
| 3.715 | 0.547 | 0.021 | 0.825 +/- 0.228 (short, gap 0.40) | -- |

Selected candidate (round_loss=3.697, closest SF1 to target midpoint 1.225): gini=0.776+/-0.026
(near target 0.8), assort=0.924+/-0.024 (well clear of 0.6 floor), Q_sign_repost=0.422+/-0.031
(short of 0.48), SF1=1.044+/-0.343 (short of range, and SEM is ~5x the target window's half-width
-- SF1 remains poorly resolved even at n=20), bin7 W1=0.477 (bins 4-5 under-posted vs. empirical,
bin 6 over-posted), bc_corr=-0.227+/-0.150 (short of -0.3, CI straddles the target).

**Conclusion**: across v9 (96 pts) + v11 (40 pts) + v12 (10 rounds, ~60 pts, all rescored under the
corrected bc_corr formula), no point in the entire search has jointly cleared SF1-in-range AND
bc_corr<=-0.3. The two objectives pull in opposite directions along the same axes that matter most
(`bc_dec`, `vocal_comfort_radius`): low bc_dec (near-static bc) points score better on bc_corr's
loss contribution but land short on SF1's apparent-polarization ratio; higher bc_dec/lower
vocal_comfort_radius points get SF1 closer but bc_corr degrades. This is consistent with the
`vocalComfortRadius` density-bias diagnosis deferred earlier in this doc (fixed absolute-distance
window structurally favors moderates over extremists by geometry, independent of genuine
homophily) -- loss-function reweighting (v9's ceiling fix, v12's target fix) has not been able to
route around it. Revisiting that structural fix, rather than further BO search on the current
parameterization, is the likely next lever if joint SF1+bc_corr achievement is required.

### ExperimentConfig defaults reflected to round0/pt4 (2026-07-24, dashboard inspection only)

Per user request, adopted v12's round0/pt4 point as `ExperimentConfig`'s new defaults (same pattern
as v9 round7/pt5 on 2026-07-23) so it can be inspected in the dashboard: `maxFollowCapacity=39.1927,
followProb=0.01, feedAlgoShare=0.65620, feedHopH=1, feedCapacity=32, bcRecoveryRate=0.00156,
bcDecRate=0.95134 (near-static bc), vocalComfortRadius=0.15749 (wider again, back near v5's range),
stubMin=stubMax=0.71769, initialPostProb=0.22656, postProbRelaxRate=0.00652, p_u=0.04877,
minPostProb=0.01` (also fixed at 0.01 here, matching every v11/v12 `launch()` call -- was still the
untokenized 0.05 default from before v11's fix). `ModelTests`'s stale `bcDecRate==0.76711` sentinel
updated to `0.95134`; full suite re-run, all pass.

### bc mechanism redesigned to graded relaxation (2026-07-24)

Dashboard GEXF inspection of round0/pt4 (below) showed the bc distribution collapsed to a single
spike at bcCeiling (~85% of agents) plus a small floor pile -- no separation by opinion extremity --
despite bc_dec=0.951 being far from its 1.0 (fully-static) extreme, while the postProb distribution
looked properly graded (real interior spread, not bimodal). Diagnosis: the per-post asymmetric
ratchet (`bc *= bcDecRate` / `bc += bcRecoveryRate*(bcCeiling-bc)`, applied once PER POST in the
feed) has the exact same structural flaw diagnosed and fixed for postProb on 2026-07-23, one step
later -- with feed_capacity ~24-32 posts/step, whichever side (comfortable/uncomfortable) held even
a modest feed-majority compounded across ~20-30 sequential hits within a single step and steamrolled
bc to whichever rail that majority favored, regardless of the comfortable fraction's actual
magnitude. No graded interior equilibrium existed.

**Fix** (Agent.java updateMyself()): aggregate once per step into `inBcRate = assimNum/postNum`
(reusing the FJ-assimilation count already computed), then a single graded relaxation:
`targetBC = bcFloor + (bcCeiling-bcFloor)*inBcRate; bc += rate*(targetBC-bc)` -- exact structural
mirror of the postProb fix. `bcDecRate`/`bcRecoveryRate` are RETAINED as names but REINTERPRETED:
no longer a per-post multiplicative-shrink constant and a per-post additive-toward-ceiling constant
(two incommensurable functional forms), but two relaxation RATES toward the same shared target.
Negativity-dominance asymmetry (Vallone et al. 1985; Baumeister et al. 2001) is now the single,
comparable ratio bcDecRate/bcRecoveryRate (>1 = bc falls faster than it rises for an equally-sized
gap) -- a byproduct of this fix's rewrite, not a new capability, but now a single well-defined
number instead of smeared across two non-comparable mechanisms.

**Asymmetry ratio deliberately left free** (user decision, 2026-07-24): considered hardcoding a
fixed ratio (e.g. 10x, discussed as a simplification to cut BO from 12 to 11 effective dims) but
neither Vallone (1985) nor Baumeister (2001) give a precise multiplier -- both are qualitative
negativity-dominance arguments, not sources of a specific ratio. The closer quantitative analogue
(prospect-theory loss aversion, Tversky & Kahneman 1991) clusters around ~2-2.5x, notably weaker
than the 10x figure floated -- flagged as a reason not to hardcode an assumed value without a
citation backing it. Decision: keep both bcDecRate and bcRecoveryRate as free/swept BO dimensions,
same as before, so the asymmetry ratio is calibrated rather than assumed.

**Units changed, old values invalid**: bcDecRate/bcRecoveryRate's numeric meaning changed from
"per-post factor" to "per-step gap-closing fraction" -- v12's calibrated values (bcRecoveryRate=
0.00156, bcDecRate=0.95134 at round0/pt4) do NOT carry over; 0.95134 as a gap-closing fraction would
mean bc nearly instantly snaps to target every step, the opposite of "near-static" under the old
semantics. Reset to untuned placeholders (bcRecoveryRate=0.01, bcDecRate=0.02, order-of-magnitude
matched to postProbRelaxRate's default) pending fresh calibration -- also means the BO search-space
ranges for these two dims need re-deriving (old ranges were tuned as near-1.0 multiplicative
retention factors, not small gap-closing fractions) before the next calibration version launches.
`ModelTests`'s `bcDecRate` sentinel updated to 0.02; full suite re-run, all pass. Smoke test (single
seed, `run.sh --seeds 1300500 -- force=true steps=20000 log_gexf=false`) launched to confirm the bc
histogram is no longer bimodal-collapsed before relaunching calibration.

**Smoke test results**: at the untuned placeholders (bc_dec=0.02, bc_recovery=0.01), the histogram
collapsed HARDER than under the old mechanism -- 99.2% of agents pinned at bcCeiling (vs. round0/
pt4's ~85% under the old ratchet). A second point (bc_dec=0.1, bc_recovery=0.05) improved to 89.2%
at ceiling with a genuine secondary mode at [0.95,0.99) -- still not smoothly graded, but
bc_extremity_corr=-0.2875 at this single point already beat most of v9-v12's entire ~250-point
search (median ~-0.1 to -0.15).

Diagnosis for the persistent bimodality: bc's own "comfort" measurement (`bcDist < this.bc`) is
self-referential -- a wider bc mechanically admits more posts as "in-bc" regardless of actual
agreement, creating positive feedback once early homophily sorting begins. This differs from
postProb's fix, which worked cleanly because `comfortPostRate` is measured against a FIXED external
window (`vocalComfortRadius`), deliberately decoupled from postProb itself (R5/D4 design,
Agent.java:315-321). bc has no such external yardstick -- this self-referential structure is
standard for adaptive-BCM designs (same form as Li, Luo & Porter 2023 eq. 2.3, which this mechanism
follows), not a defect in the graded-relaxation redesign itself. Conclusion: don't expect the
histogram to look as cleanly graded as postProb's even at good bc_corr values; the floor cluster
(likely disproportionately true extremists) does the real work even when numerically small.

**Decision (user, 2026-07-25)**: proceed straight to a full calibration search (v13) rather than
more hand-picked smoke points, since the mechanism clearly can produce meaningfully negative
bc_corr and the remaining question ("which bc_dec/bc_recovery combination gives the best/most-graded
result") is a calibration question, not a further diagnosis question.

### Calibration v13 launched (2026-07-25): graded bc mechanism, fresh search

`scripts/app_pol_baseline_bo_v13_graded_bc.py` -- fresh 12-round/96-point schedule (`[(3,10)]*6 +
[(5,6)]*6`, same shape as v9's post-mechanism-redesign launch), **no warm start** (bc_dec/bc_recovery
units changed, v9-v12's values under those names are not comparable). `bc_dec`/`bc_recovery` ranges
widened to `Real(0.0005, 1.0, log-uniform)` each (from v9-v12's `[0.5,1.0]`/`[0.0001,0.05]`, tuned
for the old per-post-multiplicative semantics) -- both smoke-test points undershot badly, so the
space needs to reach much closer to 1.0 (near-instant per-step target-tracking) than the old range
implied. Both dims independently swept (not a hardcoded ratio) per the asymmetry discussion above.
All other 10 dims and `compute_round_loss` (bc_corr target=-0.3 etc.) unchanged from v12. Launched
`nohup python3 scripts/app_pol_baseline_bo_v13_graded_bc.py` + `disown`, pid 29339, logging to
`logs/app_pol_baseline_v13_stdout.log`, `BASE_SEED=1330000`. Round 0 (30 JVMs, seeds
1330000-1330029) started cleanly.

`results/` cleaned up before launch: removed all of v9-v12's completed/fully-analyzed run
directories (71G freed, `du -sh results/` 75G -> 3.8G) -- only the user's manually-launched
dashboard runs (`run_0`-`run_4`) were kept.

### Calibration v13 completed (2026-07-25): FIRST point clearing both SF1 and bc_corr jointly

Full 12-round schedule finished cleanly. Top-5 by round_loss re-evaluated at n=20; selected
candidate (closest SF1 to target midpoint): `max_follow=43.63, follow_prob=0.01, alpha=0.765,
hop=3, bc_dec=1.0, bc_recovery=0.0005, stub=0.9, pp_relax_eta=0.1, feed_capacity=40,
initial_pp=0.01, vocal_comfort_radius=0.452, p_u=0.1`. **SF1=1.238+/-0.145 (target [1.19,1.26],
gap 0.013) AND bc_corr=-0.541+/-0.100 (target <=-0.3, clears by ~2.4 SEM)** -- the first point
across the entire v9-v13 series (~350 points) to jointly clear both targets. gini=0.856+/-0.010,
assort=0.688+/-0.028 (floor 0.6, notably lower than v12's typical 0.8-0.9), Q_sign_repost=
0.408+/-0.019 (target 0.48, short), bin7 W1=0.442 (mediocre).

**Single-seed histogram check confirmed this is a real structural result, not a coincidental
aggregate correlation**: bc spread across [0.5,1.0] with mass in every bucket (only 10.4% at
ceiling, 0% at floor -- vs. 89-99% ceiling pile-up in the prior day's untuned smoke tests), and a
clean MONOTONIC decline in mean bc by opinion extremity: |opinion|<0.2 (moderates) mean bc=0.973;
[0.2,0.4) 0.835; [0.4,0.6) 0.799; [0.6,0.8) 0.785; [0.8,1.0) (extremists) mean bc=0.730 (single-seed
corr=-0.64). This is exactly the qualitative "moderate conduit" pattern the paper argues for.

**All 5 top-K candidates share bc_dec=1.0, bc_recovery=0.0005, vocal_comfort_radius~=0.5, p_u=0.1
IDENTICALLY** (other 8 dims vary widely: max_follow 19-44, follow_prob 0.01-0.15, hop 1-3, stub
0.69-0.9, feed_capacity 18-40, initial_pp 0.01-0.43 -- and still all land bc_corr in [-0.58,-0.45]
and SF1 in [0.96,1.24]). This is a completely consistent signal, not noise from one lucky point:
these 4 dims are doing essentially all the work on both targets, and every one sits at (or against)
its v13 search-box edge:
- `bc_dec=1.0` -- a legitimate hard ceiling (can't close >100% of a gap in one step). Fine to leave.
- `bc_recovery=0.0005` -- pinned at the box's LOWER edge. True optimum may want even slower recovery.
- `vocal_comfort_radius~=0.5` -- pinned at the box's UPPER edge (half the entire opinion range).
- `p_u=0.1` -- pinned at the box's UPPER edge.

Also consistent across all 5: **Q_sign_repost lands 0.41-0.45, every one short of the 0.48 target**
-- a real, unaddressed gap independent of the bc fix.

**Mechanistic critique of bc_dec=1.0** (user question, 2026-07-25): with bc_dec=1.0, the update
`bc += bc_dec*(targetBC-bc)` simplifies to `bc = targetBC` exactly -- NOT a fall to bcFloor, but an
instant snap to whatever that single step's comfortable-fraction (`inBcRate`) implies, wherever it
lands. There is no fixed "threshold" -- the decline branch fires whenever this step's inBcRate falls
below the SELF-REFERENTIAL level `(bc-0.2)/0.8` that keeps bc exactly where it already is (an
already-tolerant agent needs a higher comfortable-fraction just to avoid triggering decline than an
already-intolerant one). The substantive implication: bc_dec=1.0 means ZERO inertia on decline -- a
single net-uncomfortable step completely overwrites the agent's entire prior tolerance history, no
smoothing. Combined with near-zero bc_recovery, the qualitative story is "one bad step instantly and
(near-)permanently resets tolerance" -- closer to a single-event trauma/grudge dynamic than
"tolerance gradually erodes under repeated friction," which is the more natural reading of the
negativity-dominance citations (Vallone 1985; Baumeister 2001 -- both about differential WEIGHTING
in an accumulating impression, not literal single-event resets with no memory). The ~2000x asymmetry
ratio here (bc_dec/bc_recovery = 1.0/0.0005) is far past the closer quantitative analogue (prospect-
theory loss aversion, Tversky & Kahneman 1991, ~2-2.5x) discussed when the ratio was left free rather
than hardcoded. Also flagged: since decline has zero inertia, an individual agent's bc trajectory
over time is spiky (long slow recoveries punctuated by sudden full resets to whatever random value
that step's feed composition implies) even though the population cross-section at a fixed time looks
smoothly graded -- "graded across agents" is not the same claim as "graded within an agent's own
trajectory," and only the former has been checked so far.

**Decision (user, 2026-07-25)**: reflect candidate 4's exact parameters into `ExperimentConfig` for
dashboard inspection now, defer the box-widening/re-calibration question until after visual
inspection. `ModelTests`'s `bcDecRate` sentinel updated to 1.0; full suite re-run, all pass. NOT
treated as a scientifically finalized calibration -- see the boundary-pinning and bc_dec=1.0
critiques above before using these values in any reported result.

### bc vs. vocalComfortRadius: role clarification (user, 2026-07-25)

User question: does `bc_dec=1.0` mean bc falls to `bcFloor` whenever agents encounter enough
uncomfortable posts to cross some threshold? Clarified: no fixed threshold -- `targetBC = bcFloor +
(bcCeiling-bcFloor)*inBcRate` is continuous, and the decline/recovery branch choice is
self-referential (`targetBC < bc` vs `>=`, so an already-tolerant agent needs a higher in-bc
fraction just to avoid triggering decline than an already-intolerant one). `bc_dec=1.0` specifically
means the update collapses to `bc = targetBC` exactly -- a full-inertia-free jump to whatever that
one step's in-bc fraction implies, not a fall to the floor. Flagged as scientifically shaky: this is
a "single bad step completely resets tolerance, near-zero recovery" (grudge/trauma-style) dynamic,
a much stronger claim than the negativity-dominance citations (Vallone 1985; Baumeister 2001, both
about differential weighting, not literal single-event resets) support.

User then asked whether the whole "narrow bc -> vocal minority" premise is even right, proposing an
alternative: wide bc -> broader follow reach (via the bc-gated unfollow mechanism, `Agent.unfollow()`
retains disagreeing followees more readily when bc is wide) -> bigger connected camp -> more vocal,
rather than narrow tolerance directly causing vocality. Resolved via role clarification (user): bc
and vocalComfortRadius are two different KINDS of threshold, not two measurements of the same
thing -- bc is a rejection/defensive threshold (how much disagreement is tolerable before
disengaging: stops assimilation, triggers unfollow), vocalComfortRadius is an activation/expression
threshold (how much nearby agreement is needed to feel safe enough to speak). An agent can coherently
be narrow-bc (easily disengages) yet still have a generous comfort radius, or vice versa -- so they
should NOT be coupled (confirms R5/D4's original decoupling, for a clearer reason than the existing
code comment gave). Agent.java's R5/D4 comment (updateMyself()) expanded to capture this framing.

**Coherence constraint derived from the framing**: since comfortRadius = "agreement threshold" and
bc = "disagreement threshold," logically `comfortRadius <= bc` must hold -- a post that's
simultaneously "too disagreeable to tolerate" (outside bc) and "agreeable enough to embolden speech"
(inside comfortRadius) is a contradiction. Since bc is per-agent/dynamic (range `[bcFloor,
bcCeiling]` = `[0.2,1.0]`) and vocalComfortRadius is a single global constant, the clean way to
guarantee this WITHOUT reopening the self-referential-feedback problem (comparing against each
agent's live bc at runtime) is a static cap: `vocalComfortRadius < bcFloor = 0.2`, guaranteeing the
ordering for every agent at every step by construction, no runtime coupling needed.

**Smoke test at vcr=0.15 (below bcFloor), pp_relax_eta=0.03 (moderate, not pinned at max), other
dims = v13 candidate 4's values, n=3 seeds (1400000-1400002, GEXF logging)**: bc mean=0.813, spread
across [0.5,1.0] with only 3.6% at ceiling (vs. the dashboard-observed pileup at vcr=0.452);
postProb mean=0.374, genuinely graded (42% near floor, real spread through 0.1-1.0, only ~10% near
ceiling -- vs. the double-spike bimodal pattern the user flagged from the dashboard).
corr(|opinion|,bc)=-0.46, **corr(|opinion|,postProb)=+0.66** (strong positive -- extremists
genuinely more vocal, the right direction for bin7). Aggregate (n=3): SF1=1.225+/-0.276 (dead on
target midpoint), bc_corr=-0.399 (clears -0.3 target), gini=0.848, assort=0.734, Q=0.406 -- but
**bin7 W1=0.527, WORSE than v13 candidate 4's 0.442**. So the vcr<0.2 cap fixes the postProb
realism problem and the extremity-vocality correlation direction, but costs bin7 fit at this
particular (hand-picked, not searched) point.

**Is bin7's mediocre fit reweightable, or a structural ceiling?** User objection (correct): can't
assume upweighting bin7 in the loss helps just because other metrics are "easily achieved" --
reweighting only helps if a materially-better-fitting point actually exists in reach. Checked
empirically across all 96 of v13's evaluated points: bin7_w1 min=0.334, p10=0.454, median=0.546,
mean=0.641 -- real but modest headroom exists (best-ever 0.334, well below the ~0.44-0.53 range of
the SF1/bc_corr-optimized candidates), NOT a hard ceiling stuck at 0.4-0.5. But the best-bin7 points
split into two families: 3 of the top 5 (w1 0.33-0.40) achieve it by destroying gini (0.10-0.27 vs
target 0.8, unusable); only 2 of the top 5 (w1=0.398, 0.409) hold gini near-target while fitting
bin7 well -- and BOTH of those sit at vcr~0.45-0.5, exactly the range the coherence cap excludes.
So the vcr<0.2 cap's bin7 cost is real and specific, not incidental. Cross-metric correlations across
the same 96 points: `corr(bin7_w1, Q_sign_repost)=-0.55` (real relationship -- Q and bin7 likely
share a common driver, probably network-sorting-strength params: max_follow/follow_prob/hop/p_u,
both currently undershooting their targets in tandem), `corr(bin7_w1, bc_corr)=-0.003` (no
relationship -- improving bin7 doesn't cost bc_corr).

### Calibration v14 launched (2026-07-25): time-constrained scope cut -- SF1 + bin7 only

User: "no time left" -- fix params according to past results, target ONLY SF1 and bin7.
`scripts/app_pol_baseline_v14_sf1_bin7_only.py`. Fixed (not searched): `bc_dec=1.0,
bc_recovery=0.0005, p_u=0.1` -- v13's top-5 pinned identically at these values, well-established.
`compute_round_loss` reduced to bin7 fit ONLY (gini/Q/assort/bc_corr terms removed entirely, not
just downweighted) -- SF1 still excluded from round-level loss (n=5 noise exceeds the target
window, same reasoning as v9-v13), selected post-hoc via top-K n=20 same as before. 9 free dims
(down from 12): max_follow, follow_prob, alpha, hop, stub, pp_relax_eta, feed_capacity, initial_pp,
vocal_comfort_radius -- **vcr's box kept at v13's [0.02,0.5], the <0.2 coherence cap NOT applied**,
explicit trade-off given the time constraint: bc_corr is no longer an active target, so the
coherence argument (about keeping the vocal-minority mechanism sensible relative to bc) is
deprioritized, not resolved -- flagged for revisit later, not silently dropped. Reduced schedule (8
rounds vs v13's 12: `[(3,10)]*4 + [(5,6)]*4`, 64 points) for speed given fewer dims + simpler loss.
`results/` cleaned before launch (107G -> 6.3G, removed all of v13's completed dirs + today's smoke
tests). Launched `nohup python3 scripts/app_pol_baseline_v14_sf1_bin7_only.py` + `disown`, pid
35680, logging to `logs/app_pol_baseline_v14_stdout.log`, `BASE_SEED=1440000`. Round 0 (30 JVMs,
seeds 1440000-1440029) started cleanly.

### Cross-era variance review + v15 launched (2026-07-25): 2 more dims fixed

User request: review variance/mean of all free dims across past results before deciding what else
to fix. Pooled v9+v12+v13's top-5 "good" candidates (15 points spanning 3 different bc/postProb
mechanism eras -- only comparable dims pooled: max_follow, follow_prob, alpha, hop, stub,
pp_relax_eta, feed_capacity, initial_pp, vocal_comfort_radius; bc_dec/bc_recovery excluded from
pooling since their units changed at v13; p_u pooled from v12+v13 only, v9 predates it being free).
Coefficient of variation (std/mean) per dim:

| dim | mean | std | CV | note |
|---|---|---|---|---|
| stub | 0.822 | 0.076 | 0.09 | tightest -- fixed |
| alpha | 0.630 | 0.132 | 0.21 | 2nd tightest -- fixed |
| hop | 2.20 | 0.75 | 0.34 | low-cardinality int, left free |
| max_follow | 34.13 | 13.33 | 0.39 | left free |
| feed_capacity | 23.8 | 11.36 | 0.48 | left free |
| follow_prob | 0.098 | 0.086 | 0.88 | left free |
| pp_relax_eta | 0.048 | 0.040 | 0.83 | left free |
| vocal_comfort_radius | 0.218 | 0.208 | 0.96 | left free -- KNOWN to trade off against bin7 (see above), high CV here is not "safe to fix," it's "actively doing work" |
| initial_pp | 0.170 | 0.171 | 1.01 | left free |

p_u (v12+v13, n=10): mean=0.086, std=0.020 (already fixed at 0.1 in v14). bc_dec/bc_recovery
(v13 only, n=5): zero variance, all 5 candidates identical (already fixed in v14).

**Decision**: fix `stub=0.82`, `alpha=0.63` in addition to v14's three (bc_dec, bc_recovery, p_u) --
5 of 12 original dims now fixed, 7 remain free (max_follow, follow_prob, hop, pp_relax_eta,
feed_capacity, initial_pp, vocal_comfort_radius). v14 had not completed any round yet (0 rows in its
CSV) when this decision was made -- killed cleanly (pid 35680 + child JVMs), no data lost.

`scripts/app_pol_baseline_v15_more_fixed.py`: same bin7-only round loss / SF1-at-n=20 top-K
selection as v14, round schedule trimmed further for the smaller space (`[(3,10)]*3 + [(5,6)]*3`,
6 rounds/48 points vs v14's 8/64). `results/` re-checked before launch (9.3G, no cleanup needed).
Launched `nohup python3 scripts/app_pol_baseline_v15_more_fixed.py` + `disown`, pid 36089, logging
to `logs/app_pol_baseline_v15_stdout.log`, `BASE_SEED=1450000`. Round 0 (30 JVMs, seeds
1450000-1450029) started cleanly.

### Calibration v15 completed + reflected to ExperimentConfig (2026-07-25)

6 rounds (48 points) + top-K/n=20 finished cleanly. Selected candidate (closest SF1 to target
midpoint among top-5): `max_follow=43.864, follow_prob=0.0595, hop=4, pp_relax_eta=0.002215,
feed_capacity=31, initial_pp=0.255, vocal_comfort_radius=0.5` (pinned at the box's exact upper edge
again -- consistent with v13's finding that gini-preserving good-bin7 points cluster at vcr~0.45-0.5,
not a fluke), fixed dims unchanged (`bc_dec=1.0, bc_recovery=0.0005, p_u=0.1, stub=0.82, alpha=0.63`).

Result: SF1=1.148+/-0.130 (target [1.19,1.26], gap 0.077 -- short but closest of the top-5),
bc_corr=-0.570 (clears -0.3 well), gini=0.867, assort=0.896 -- but Q_sign_repost=0.417 (target 0.48)
and **bin7 W1=0.434 essentially unimproved from v13's 0.442**, despite the round-level loss now
targeting bin7 exclusively. Top-5 table shows why: candidates #2/#4 (round_loss 1.532/1.705) had
better bin7 fits (0.396/0.386) but worse SF1 (0.839/0.527) -- the SF1-closest selection criterion
doesn't reward the best-bin7 candidate, so a bin7-only round loss doesn't translate into a
bin7-improved FINAL pick under this two-stage (round-loss-then-SF1-select) selection design.

**Adopted into `ExperimentConfig` at the user's request given the project deadline** -- NOT a fully
closed calibration (Q and bin7 both remain short, same open gaps flagged since v9). Updated:
`maxFollowCapacity=43.8638, followProb=0.05955, feedAlgoShare=0.63 (now fixed), feedHopH=4,
feedCapacity=31, vocalComfortRadius=0.5, stubMin=stubMax=0.82 (now fixed), initialPostProb=0.25537,
postProbRelaxRate=0.002215`; `pU`, `bcDecRate`, `bcRecoveryRate` unchanged from v13 (already at
v15's fixed values). `ModelTests` unaffected (no change to the `bcDecRate` sentinel value); full
suite re-run, all pass.

### Periodic bin7 snapshots added (2026-07-25)

User asked how the 7-bin per-capita posting-rate fit looks at intermediate steps (5000/10000/
20000), not just the final cumulative fit -- `post_bin7.csv` was previously written only once, at
the very end of `evolve()`. Added a step-indexed variant: `Writer.writePostBin7(postCountByBin,
popCountByBin, folderPath, step)` writes `metrics/post_bin7_<step>.csv` inside the existing
`step % 5000 == 0` checkpoint block (same cadence as `degree_result_<step>.csv` etc.) --
`postCountByBin7` is cumulative-since-t=0 at every checkpoint (same semantics as the final file,
just read earlier), so these snapshots show how the shape evolves/stabilizes over the run, not a
windowed/instantaneous rate. `popCountByBin7` (population by bin, fixed at construction) hoisted
out of the end-of-run block to before the main loop, computed once, reused at every checkpoint and
the final write (was previously recomputed redundantly). Original `writePostBin7` (3-arg, writes
`post_bin7.csv`) unchanged -- every existing calibration script's `read_metrics()` still points at
that exact path. Compiles clean, full test suite re-run, all pass. Single-seed run launched
(`run.sh --seeds 1500000 -- force=true init_dist=empirical`, current `ExperimentConfig`/v15
defaults) to produce the snapshots.

**Result: the fit is non-stationary, not converging.** bin7 W1 (Wasserstein-1 vs. empirical) across
checkpoints: 5000=0.359, **10000=0.333 (best)**, 15000=0.355, 20000=0.371, 25000=0.389, 30000=0.406,
35000=0.418, 40000=0.427 -- a steady, almost-linear degradation from the step-10000 sweet spot to
the step-40000 dashboard default (~28% worse). bin4/5/6's cumulative share grows monotonically
while bin3 (moderate center) shrinks monotonically for the whole second half of the run -- a
genuine directional drift, not noise settling. Methodological implication: bin7 fit is not a stable/
converged property of this model, it's a moving target across simulation time, and it moves AWAY
from the empirical shape the longer the run continues. All calibration searches (v9-v15) evaluated
bin7 at `STEPS=20000` specifically (not the dashboard's 40000 default) -- this result shows that
choice has real consequences (a different optimum than fitting at 40000 would find), not just a
compute-budget tradeoff.

### accessProb cut to 1/4 -- time-constrained param freeze (2026-07-25)

User: "no time left," wants to freeze model params now (acknowledging possible small revision when
finalizing paper numbers) rather than re-run calibration. Idea: rather than re-searching parameters
against the non-stationary bin7 drift above, cut `accessProb` (this model's single global timescale
knob -- gates whether an agent acts AT ALL this step, before repost/follow/unfollow/post/
updateMyself()) by 4x (0.1 -> 0.025), on the reasoning that this should rescale the dynamics'
effective time axis by roughly the same factor -- moving the ~step-10000 sweet spot out to
~step-40000 (the dashboard's default run length), rather than needing to re-tune every other
parameter. `ExperimentConfig.accessProb` updated (0.1 -> 0.025), full test suite re-run, all pass.

**Not verified to be exactly linear** -- network-growth/follow dynamics have their own independent
probabilistic gating (`follow_prob`, `pU`), so a uniform 4x slowdown of "does this agent act at all"
doesn't necessarily rescale every sub-mechanism by the same factor. Verification run launched
(`run.sh --seeds 1600000 -- force=true init_dist=empirical log_gexf=true`, pid 44642, GEXF logging
on per user request so the shift can also be inspected directly in the dashboard's network
snapshots) to check whether the bin7 sweet spot actually lands near step 40000 under the new
accessProb, using the same periodic-snapshot infrastructure added above.

**Verification result**: the sweet spot did shift later, roughly as predicted (was degrading past
step 10000 under accessProb=0.1; now monotonically improves out to ~step 35000-40000 and plateaus
there, a ~3.5-4x shift matching the 4x accessProb cut) -- but the fit is worse in absolute terms
everywhere along the way (best W1=0.483 at step 35000-40000 vs. the old best-ever 0.333 at step
10000, ~45% worse), and the SHAPE itself changed, not just its timing (much flatter across all 7
bins -- bin0 stuck near 0.16-0.17 instead of reaching a sharper peak, bin3's dip shallower). So
accessProb is not a pure time-rescaling that preserves the asymptotic shape: it uniformly slows
every accessProb-gated sub-mechanism (post/repost/follow/unfollow/opinion-update), but the
network's INITIAL structure (built once at t=0 by the Holme-Kim generator, unaffected by
accessProb) doesn't get proportionally more time to interact with the now-slower content dynamics,
so the balance between structural sorting and content accumulation isn't preserved the way a pure
time-rescaling would need.

### Calibration closed for now (2026-07-25) -- frozen ExperimentConfig snapshot

User: "no time left," stopping the calibration effort here (project deadline -- Complex Networks
2026, see docs/research-direction.md). This is a working freeze, not a scientifically finalized
result -- values may be revisited when finalizing the paper's numbers. Full current defaults, for
reference (`src/experiment/ExperimentConfig.java`, as of this entry):

```
maxFollowCapacity = 43.8638      followProb = 0.05955
feedAlgoShare (alpha) = 0.63 (FIXED, not swept)     feedHopH (hop) = 4
feedCapacity = 31                accessProb = 0.025 (cut 4x from default 0.1, see above)
pU = 0.1 (FIXED, not swept)
bcDecRate = 1.0 (FIXED, pinned at hard ceiling -- zero inertia, see the mechanistic critique above)
bcRecoveryRate = 0.0005 (FIXED, pinned at search-box floor)
bcFloor = 0.2   bcCeiling = 1.0   bcInit = 1.0
vocalComfortRadius = 0.5 (pinned at search-box upper edge -- coherence cap `< bcFloor` discussed
    but NOT applied, explicit time-constrained trade-off, see "vcr<0.2" entries above)
stubMin = stubMax = 0.82 (FIXED, not swept)
initialPostProb = 0.25537        maxPostProb = 1.0        minPostProb = 0.01
postProbRelaxRate = 0.002215
n = 1000   steps = 40000
```

**Open items, not resolved by this freeze** (carried forward for future work, not silently
dropped):
- Q_sign_repost undershoots its 0.48 target across every version since v9 (typically 0.40-0.45).
- bin7 fit is mediocre (W1 ~0.43-0.48 depending on exact point/step) and, per the discovery above,
  genuinely non-stationary across simulation time -- not a converged property of the model.
- `bcDecRate=1.0`/`bcRecoveryRate=0.0005` (~2000x asymmetry) implies a zero-inertia "single bad
  step completely resets tolerance" dynamic, stronger than the negativity-dominance citations
  (Vallone 1985; Baumeister 2001) actually support -- flagged, not independently justified.
  `vocalComfortRadius=0.5` violates the derived discomfort/comfort-threshold coherence constraint
  (`vcr < bcFloor`) for the same time-constrained reason.
- `accessProb=0.025`'s effect on the model is NOT a clean time-rescaling (see verification result
  above) -- treat as an empirically-observed adjustment, not a theoretically-grounded one.
- 5 of 12 original BO dimensions are now hardcoded constants (`alpha`, `stub`, `bc_dec`,
  `bc_recovery`, `p_u`) based on a cross-era variance review, not re-verified under this exact
  final configuration.

`results/` cleaned (removed all completed verification/calibration run dirs, kept only the live
dashboard runs `run_0`-`run_4`) and `logs/` cleaned (2704 -> 23 files, mostly per-seed logs from
completed calibration runs whose data is already captured in the CSVs above; summary `*_stdout.log`
files and the current dashboard's `run_0.log`-`run_4.log` kept).

### ExperimentConfig defaults reflected to round0/pt4 (2026-07-24, dashboard inspection only, bc
mechanism since superseded by the graded-relaxation redesign above)

This point was NOT among v12's top-5 round_loss candidates (loss=5.32 vs. the winners' 2.4-3.7) --
its original n=3 read looked attractive on SF1 (1.222+/-0.074, in-range, unusually tight) and gini
(0.804, on target), with bc_corr (-0.151) and Q_sign_repost (0.399) merely mediocre, not standout.
Launched an n=10 re-check (`scripts/app_pol_baseline_v12_round0pt4_n10.py`, `nohup`+`disown`, pid
27761, seeds 1300000-1300009, log `logs/v12_round0pt4_n10_stdout.log` / `docs/report/
v12_round0pt4_n10.csv`) to see whether the tight n=3 SF1 read survives a larger sample before
treating it as informative.

**n=10 result: the n=3 read did not survive -- this was winner's-curse, not signal.**

| metric | n=3 (round0/pt4 original) | n=10 (this check) | target |
|---|---|---|---|
| gini | 0.804 | 0.796 +/- 0.007 | 0.8 |
| assort | 0.810 | 0.833 +/- 0.023 | >=0.6 floor |
| Q_sign_repost | 0.399 | 0.417 +/- 0.030 | 0.48 |
| SF1 ratio | **1.222 +/- 0.074 (in range)** | **1.058 +/- 0.151 (short, gap 0.13)** | [1.19,1.26] |
| bin7 W1 | 0.447 | 0.462 +/- 0.050 | 0 |
| bc_corr | -0.151 | **-0.056 +/- 0.181** | <=-0.3 |

SF1's mean dropped 0.16 and its std more than doubled going n=3->n=10 -- the tight, in-range n=3
read was exactly the kind of small-sample illusion flagged when this point was first surfaced (n=3
noise readily produces spuriously tight in-range reads; see the SF1 batch-noise-check investigation
earlier in this doc). bc_corr moved further from target too (-0.151 -> -0.056). Net: round0/pt4
does **not** outperform v12's actual top-5 winners on either axis once properly sampled -- it is
weaker than the selected candidate (round_loss=3.697, SF1=1.044+/-0.343, bc_corr=-0.227+/-0.150) on
bc_corr and comparable-or-worse on SF1. The `ExperimentConfig` defaults above remain reflected for
dashboard/GEXF inspection purposes only (matching the round7/pt5 precedent), not as a validated or
recommended calibration point.

## Restarting the swap experiment (2026-07-26): hub-tier check under the current (v15) calibration point

Resuming the hub-swap/secession design work parked above. First step: the tier picture from
`hub_tier_characterization.py`/`hub_tier_pct_summary.py` (2026-07-21, 20 seeds) is stale -- it ran
at the 2026-07-20 static-bc point, since superseded by the graded-bc redesign (v13) and the v14/v15
fixes (`accessProb` cut 4x, `stub`/`alpha` fixed, etc., see the "Calibration closed for now
(2026-07-25)" entry above). Re-ran the same mega/mid/tail (>500 / 100-500 / <=100 followers)
characterization at the current frozen defaults, with `init_dist=gaussian` (synthetic, not the
`init_dist=empirical` option) since the swap experiment's causal claim shouldn't be entangled with
the empirical-distribution grounding work. `scripts/hub_tier_check_v15_synth.py`: 3 seeds
(1726000-1726002), n=1000, steps=40000 (current default, not the steps=20000 shortcut most
calibration scripts used), every dynamics-relevant param pinned explicitly in `launch()` per the
pU-mislabeling lesson logged above. Raw: `docs/report/hub_tier_v15_synth_raw.csv`, summary:
`docs/report/hub_tier_v15_synth_summary.csv`.

**Per-tier aggregate (mean +/- sd across 3 seeds):**

| tier | followerCount | tier_size | n_moderate | frac_moderate | mean\|opinion\| | mean_followers |
|---|---|---|---|---|---|---|
| mega | >500 | 8.7+/-7.3 | 5.7+/-6.0 | 0.50+/-0.35 | 0.248 | 535.4 |
| mid | 100-500 | 126.3+/-9.2 | 21.7+/-5.6 | 0.17+/-0.05 | 0.506 | 234.5 |
| tail | <=100 | 865.0+/-3.6 | 308.0+/-24.5 | 0.36+/-0.03 | 0.360 | 9.4 |

**Mid-tier finding replicates cleanly**: mid is the *least* moderate band at all 3 seeds
individually (frac_moderate 0.18 / 0.11 / 0.24), same qualitative "moderation vs. reach is
non-monotonic" pattern as the 2026-07-21 characterization (there: mega most moderate at
0.46+/-0.12, mid least moderate at 0.32+/-0.15) -- confirms the pattern survives the bc-mechanism
redesign and the switch to synthetic init opinions, not an artifact of either the old calibration
point or the empirical distribution.

**Mega tier is far more seed-volatile than under the old calibration point, and this matters for
hub selection.** Per-seed breakdown: seed 1726000 mega n=4 (frac_moderate 0.75), seed 1726001 mega
n=3 (frac_moderate **0.00**), seed 1726002 mega n=19 (frac_moderate 0.74, with individual hubs
reaching 663/1000 followers -- a much larger dominant cluster than the other two seeds ever produce).
Contrast with the 2026-07-21 characterization's mega tier at the old point: 7.2+/-0.9 across 20
seeds -- tight, stable. At n=3 here the mega tier swings from a 3-hub, zero-moderate realization to
a 19-hub, mostly-moderate realization. Not yet enough seeds to say whether this reflects a genuinely
higher-variance regime under v15's parameters (larger `max_follow`=43.86 and `follow_prob`=0.05955
than the old point plausibly allow more run-away preferential-attachment outcomes in some seeds) or
whether 3 seeds is simply too few to resolve the mega tier specifically (it's the smallest-n tier by
construction, so seed noise hits it hardest). **Consequence: a fixed-followerCount tier boundary
(>500 for mega) is not yet demonstrated to give a stable-composition hub pool at this calibration
point** -- unlike the mid tier, which looks robust even at n=3. Open decision before finalizing tier
definitions for the swap experiment: run more seeds to see if mega-tier volatility settles, switch
to a rank-based tier definition (top-K by in-degree, as `hub_tier_characterization.py` did
originally) which is robust to network-size scale changes by construction, or both.

## Tier definitions and scaling to 20 seeds (2026-07-26, user decisions)

Three decisions, in response to the volatility finding above: (1) "20 seeds is enough" -- scale the
tier check from 3 to 20 seeds rather than switching to a rank-based definition. (2) "if mega dont
exist, just exclude them from results" -- an empty tier in a given seed is a missing observation for
that seed, not a zero; fixed `hub_tier_check_v15_synth.py`'s per-tier aggregate to compute
frac_moderate/mean|opinion| only over seeds where the tier is non-empty (previous version divided by
`max(size,1)`, silently scoring an empty tier as 0% moderate). (3) New three-band scheme, replacing
the open-ended mega/mid/tail split: **mega (>500), mid (100-500], small (50-100]** -- agents with
<=50 followers excluded entirely from the candidate pool (not "tail" catch-all).

20-seed result (seeds 1726000-1726019, same v15-frozen point + `init_dist=gaussian`): **mega now
present in all 20/20 seeds** (the n=3 pass's zero-mega seed, 1726001, was noise, not a real gap) --
tier_size=9.8+/-4.9, frac_moderate=0.61+/-0.26, mean\|opinion\|=0.182, mean_followers=551.7. mid:
tier_size=125.5+/-8.2, frac_moderate=**0.16+/-0.03** (the tight, low-variance tier), mean\|opinion\|=
0.502, mean_followers=229.2. small: tier_size=55.1+/-6.9, frac_moderate=0.26+/-0.06, mean\|opinion\|=
0.439, mean_followers=72.6. **Confirms, at proper power, the non-monotonic moderation-vs-reach
pattern**: mega most moderate (61%), mid least moderate (16%), small in between (26%) -- consistent
with the 2026-07-21 characterization at the old calibration point (46%/32%/tail-was-different-band),
now re-established under the current model. Raw: `docs/report/hub_tier_v15_synth_raw.csv`, summary:
`docs/report/hub_tier_v15_synth_summary.csv`. Every seed has a usable moderate-hub count in every
tier (mega 0-14, mid 14-27, small 5-22 per seed) -- no seed needs to be dropped from the next step.

## Secession experiment finally executed (2026-07-26)

User confirmed the treat/control framing ("we have to compare with treat and control, right?") and
authorized proceeding to treatment once the tier check was confirmed. Implemented
`scripts/hub_secession_experiment.py`, executing the design named-but-never-run in this doc's
"Experiment redesign: secession test, not addition test" section above, adapted to deplete a WHOLE
tier's realized moderate sub-population per seed rather than one hand-picked agent (per the
substitution critique also logged above -- a single swapped agent's role gets refilled from the
reserve pool; depleting an entire realized tier doesn't have that escape hatch).

**Design:** for each of the 20 already-equilibrated base networks (`hub_tier_check_v15_synth.py`'s
seeds 1726000-1726019, n=1000, steps=40000, current v15-frozen point, `init_dist=gaussian`) --
CONTROL continues the unmodified network; TREATMENT continues from a copy where every moderate hub
(\|opinion\|<0.2) within the target tier, as realized in that seed's own network, has its opinion
overwritten to +/-0.9 (sign preserved, same convention as the 2026-07-18/20 series). Both continue
`CONTINUE_STEPS=20000` further via `network=read`, every dynamics-relevant parameter pinned
explicitly (same FIXED dict as the tier-check script). Paired by base seed (20 pairs), distinct
seed ranges per (tier, arm) since `ExperimentConfig.tag()` doesn't encode `read_path` or which
agents were swapped -- collision risk if seed numbers were reused across arms/tiers.

**Caveat carried over explicitly, not silently assumed away:** `CONTINUE_STEPS=20000` is NOT
rescaled for the current `accessProb=0.025` (4x slower than the original swap series' implicit
0.1) -- matches the original series' final continuation length in raw step count, not in
"equivalent dynamics time." Flagged, not resolved, given the deadline.

Smoke-tested end-to-end before the full launch (single seed, `steps=5000`): swap correctly targets
only the intended agent IDs (verified by direct GEXF inspection), both arms produce valid, distinct
metrics (control sf1_ratio=1.158, treatment=0.937 at this one seed/short-horizon spot check --
illustrative only, not the result). Priority: **mid tier first** (research-direction.md's own
target band -- the original mega-hub test was already flagged as "the wrong tier," 72.5% reach
saturates the network regardless of opinion). Launched `nohup python3
scripts/hub_secession_experiment.py mid` + `disown`, log `logs/hub_secession_mid_stdout.log`,
per-seed logs `logs/secession_seed*.log`. Control seeds 2000000-2000019, treatment seeds
2010000-2010019. Results to be logged here on completion.

### Mid-tier secession result (2026-07-26): genuine null, consistent with the earlier series

Completed (both 20-run batches, ~55 min total wall time -- slower than the ~28 min estimate,
consistent with 19-20 concurrent JVMs on 32 cores contending for CPU rather than any problem).
Full log: `docs/report/hub_secession_mid.csv`. Paired (by base seed) treatment-vs-control, n=20 pairs:

| metric | control | treatment | paired diff | paired t |
|---|---|---|---|---|
| crossCuttingFraction | 0.0050+/-0.0026 | 0.0051+/-0.0021 | +0.0001+/-0.0013 | 0.32 |
| interactionCrossCuttingFraction | 0.1505+/-0.0294 | 0.1508+/-0.0313 | +0.0003+/-0.0121 | 0.10 |
| Q_sign_repost | 0.3563+/-0.0414 | 0.3548+/-0.0399 | -0.0016+/-0.0116 | -0.59 |
| opinionVar | 0.2079+/-0.0083 | 0.2073+/-0.0079 | -0.0005+/-0.0029 | -0.77 |
| sf1_ratio | 0.8684+/-0.2762 | 0.9114+/-0.3678 | +0.0429+/-0.4029 | 0.46 |
| bimodalityCoeff | 0.4338+/-0.0197 | 0.4318+/-0.0223 | -0.0020+/-0.0063 | -1.36 |
| opinionKurtosis | -0.6848+/-0.1187 | -0.6744+/-0.1253 | +0.0105+/-0.0353 | 1.29 |
| disagreement | 0.0418+/-0.0038 | 0.0413+/-0.0040 | -0.0005+/-0.0011 | **-2.10** |

**Read: genuine null, not a power problem alone.** 7 of 8 metrics land well under the df=19 critical
`|t|~2.09` (p=0.05, two-tailed, uncorrected). `disagreement` alone crosses it (-2.10), but the effect
is tiny relative to its own scale (~1.2% relative change) and does not survive a Bonferroni
correction for testing 8 metrics (needs `|t|>~3.2`) -- exactly the one-hit-in-eight rate chance alone
predicts, not a real signal. `sf1_ratio` -- the outcome the whole secession design was built to
move -- shows no directional consistency (control and treatment overlap heavily, treatment's own SD
0.37 dwarfs the +0.043 paired shift) and remains as unresolved-at-this-n as every prior SF1 read in
this project (needs ~85+ seeds per the 2026-07-21 batch-noise-check finding).

**This is the third independent design to find the same null**: single mega-hub (2026-07-18),
scaled multi-hub swap up to n=30 (2026-07-20), and now whole-mid-tier secession with the
conduit-activity channel actually open (`out_of_bc_repost_prob=0.01`, unlike the earlier all-zero
series) at n=20 (2026-07-26). Converging evidence across three different operationalizations of
"remove/alter the moderate hub population" is more informative than any one of them alone --
worth stating plainly as the swap experiment's headline result rather than as three separate
inconclusive attempts.

**Caveats to carry into any write-up, not swept under the null:** (1) `CONTINUE_STEPS=20000` is
still not accessProb-rescaled (flagged above, unresolved); (2) n=20 cannot resolve `sf1_ratio`
specifically at the precision this project's own noise-characterization work says is needed; (3)
`disagreement`'s marginal hit, while not surviving correction, is at least directionally consistent
with "removing moderates very slightly reduces measured disagreement" and could be revisited with
more seeds if time allows, not dismissed outright.

**Not yet run:** mega and small tiers (same design, different `TIER_SEED_OFFSETS` block already
reserved in `scripts/hub_secession_experiment.py`) -- open next step, pending user decision on
whether to spend remaining time on that or move to write-up.

### CRITICAL BUG FOUND (2026-07-26): the mid-tier "null" above is invalid -- swap didn't persist

User asked directly: "did you find the mid-tier moderate hubs emerge after you swap all the mid-tier
hubs toward extremes?" Checked the final-step snapshots (`agent_snapshot_final.csv`) for all 20
treatment runs against the original swap lists. **93% reversion**: of 391 agents swapped to extreme
across 20 seeds, 363 had drifted back to \|opinion\|<0.2 by step 20000. Total moderate-mid-tier-hub
count at the final step: treatment=486 (pooled), control=492 -- statistically indistinguishable.
The "secession" did not hold through the measurement window.

**Root cause: `write_swapped_gexf` only overwrote the `opinion` GEXF attribute, not
`intrinsicOpinion`.** `Agent.java:411`: `opinion = stubbornness*intrinsicOpinion +
(1-stubbornness)*assimilated`. With `stub=0.82` (current default), every step pulls opinion 82%
back toward the agent's own fixed `intrinsicOpinion` -- left at the original moderate value, this
mechanically erases the swap over ~20000 steps regardless of any network/social effect. Confirmed
`GephiReader.java:75-76` reads `intrinsicopinion` back in on `network=read`, so the fix is
load-bearing, not cosmetic.

**This exact failure mode was already diagnosed and fixed once before, in a different code path.**
`docs/report/2026-07-07-model-revision-requirements.md`, requirement R4 "Full hub pinning":
*"`InterventionSetup.apply` sets only `intrinsicOpinion`; ... hubs broadcast their stale
pre-intervention opinion and drift"* -- fixed there by setting `intrinsicOpinion`, `opinion`, AND
`stubbornness=1.0` together for the old `InterventionSetup` intervention pathway. That fix never
propagated to the GEXF-editing swap scripts (`swap_hub_opinion.py`, 2026-07-18 onward, and this
session's `hub_secession_experiment.py`) -- same bug, reintroduced in a different mechanism.

**Consequence: invalidates the "three independent nulls" framing reported earlier today.** The
original 2026-07-18 single-mega-hub swap and the 2026-07-20 multi-hub series used the same
opinion-only GEXF edit (`swap_hub_opinion.py`) -- their null results are subject to the identical
concern and should not be read as settled evidence of "no causal effect" without the same check.
Not re-verified here (out of scope for the immediate fix-and-rerun); flagged for anyone treating
those results as final.

**Fix applied (user decision, 2026-07-26): swap `opinion` AND `intrinsicOpinion` together;
`stubbornness` deliberately left untouched** (not R4's full `stubbornness=1.0` pin -- swapped
agents keep normal susceptibility to social influence afterward, only their opinion-valued
attributes are overwritten). `write_swapped_gexf` updated accordingly; verified by direct GEXF
inspection that both attributes land on the swapped agents post-fix. Also added resumability to
`run_arm`: an existing valid result at a given continuation seed is reused rather than
re-simulated (control is unaffected by this bug -- it never touched opinion/intrinsicOpinion --
so the 20 control runs were reused from disk; only the 20 treatment runs were re-simulated).
Relaunched `nohup python3 scripts/hub_secession_experiment.py mid` + `disown`. Corrected result to
be logged here on completion.

### Corrected mid-tier secession result (2026-07-26): large, highly significant effects on opinion-distribution metrics

With `intrinsicOpinion` fixed, the swap holds. Paired treatment-vs-control (n=20 base seeds),
opinion-distribution metrics:

| metric | control | treatment | paired diff | t |
|---|---|---|---|---|
| crossCuttingFraction | 0.0050+/-0.0026 | 0.0099+/-0.0091 | +0.0049+/-0.0074 | 2.88 |
| interactionCrossCuttingFraction | 0.1505+/-0.0294 | 0.1049+/-0.0359 | -0.0456+/-0.0171 | -11.65 |
| Q_sign_repost | 0.3563+/-0.0414 | 0.3996+/-0.0545 | +0.0433+/-0.0227 | 8.33 |
| opinionVar | 0.2079+/-0.0083 | 0.2295+/-0.0092 | +0.0216+/-0.0047 | 19.93 |
| sf1_ratio | 0.8684+/-0.2762 | 0.8430+/-0.2903 | -0.0254+/-0.3547 | -0.31 |
| bimodalityCoeff | 0.4338+/-0.0197 | 0.4710+/-0.0222 | +0.0373+/-0.0103 | 15.80 |
| opinionKurtosis | -0.6848+/-0.1187 | -0.8659+/-0.1155 | -0.1811+/-0.0518 | -15.23 |
| disagreement | 0.0418+/-0.0038 | 0.0557+/-0.0041 | +0.0139+/-0.0029 | 20.58 |

**User's critique (2026-07-26), correct and immediately load-bearing:** opinion-distribution metrics
(`opinionVar`, `bimodalityCoeff`, `opinionKurtosis`) are computed directly from the population's raw
opinion values, and the manipulation directly sets ~20 agents' opinion to +/-0.9 -- population-level
opinion spread increasing is arithmetic, not a discovered social-dynamics effect. `sf1_ratio` (a
ratio, `postOpinionVar/opinionVar`, which should absorb a pure composition-driven numerator/
denominator co-movement) showing no effect (t=-0.31) despite `opinionVar` moving by t=19.93 is
suggestive but too noisy at n=20 to lean on alone (SF1 needs ~85+ seeds per the 2026-07-21
batch-noise-check). Right question: does *posting/reposting behavior* (not raw opinion state)
change -- i.e. genuinely behavioral/surfacing metrics.

### Correction to the behavioral read: StepStats columns are per-step, not cumulative

First pass at behavioral metrics (`crossRepostRate`, `outGroupBlockPropensity`,
`outGroupSanctionRate`, `blockCount`, `unfollowCount`, `evictionCount`, `originalPostCount`,
`repostCount`) read only the FINAL row of `results.csv` -- same mistake as the intrinsicOpinion bug
in spirit (silently using an unintended slice of the data). `StepStats.java:7`: "Reset at the start
of each step... read into the metrics row at step end" -- every row is a single step's count, not a
run total, so reading the final row alone samples one step out of 20001. Caught when the user asked
"did unfollowCount actually emerge" and a check of the FULL time series showed 3.4-19% of steps have
nonzero `unfollowCount` even though the specific final step happened to read exactly 0 across all 40
runs (both arms) -- not a dead metric, just an unrepresentative single sample.

**Corrected whole-run aggregates** (sums for raw counts, mean-of-per-step-ratio for the three rate
columns, n=20 pairs) -- reverses several earlier "flat/borderline" reads into clearly significant
ones:

| metric | control | treatment | diff | t |
|---|---|---|---|---|
| blockCount (sum) | 31342+/-2101 | 37153+/-2460 | +18.5% | 14.38 |
| unfollowCount (sum) | 912+/-839 | 2993+/-1067 | +228% (3.3x) | 12.39 |
| evictionCount (sum) | 25766+/-1223 | 24319+/-1157 | -5.6% | -9.31 |
| originalPostCount (sum) | 325421+/-8200 | 318841+/-7249 | -2.0% | -11.68 |
| repostCount (sum) | 1238930+/-19297 | 1192839+/-26947 | -3.7% | -10.42 |
| outGroupSanctionRate (mean) | 0.022+/-0.002 | 0.019+/-0.002 | -13.6% | -10.17 |
| crossRepostRate (mean) | 0.319+/-0.036 | 0.250+/-0.041 | -21.6% | -13.87 |

Unfollowing and blocking both surge; cross-camp reposting, sanctioning, and total posting/reposting
volume all drop -- a coherent "accelerated homophilous sorting" signature, consistent with the
`P_u`-phase-knob story in `research-direction.md` (high `P_u` -> sorting -> Type 1).

### 5-bin posting-share result (2026-07-26): the actual behavioral finding

User's follow-up ask: show the posting-DISTRIBUTION difference (5-bin `postShare_i`, bin2=moderate
center, bins 0/4=extremes), the genuinely behavioral analogue of the opinion-variance numbers, since
"crossCuttingFraction decreasing is not a finding, it's confirmation" (bridge nodes were literally
deleted from the moderate pool) -- the open question is whether *posting behavior* redistributes.

| bin | control | treatment | diff | t |
|---|---|---|---|---|
| 0 (extreme-) | 0.088+/-0.016 | 0.105+/-0.018 | +19% | 12.80 |
| 1 | 0.238+/-0.045 | 0.251+/-0.054 | +5.6% | 3.82 |
| **2 (moderate)** | **0.334+/-0.036** | **0.276+/-0.044** | **-17.3%** | **-14.77** |
| 3 | 0.244+/-0.044 | 0.254+/-0.051 | +4.1% | 4.19 |
| 4 (extreme+) | 0.096+/-0.016 | 0.114+/-0.018 | +18% | 15.78 |

Clean, symmetric, highly significant U-shape: moderate-center posting share drops, both extremes
gain. **Robustness check against the same mechanical-artifact concern**: the 20 swapped agents'
own activity (pooled across 20 treatment seeds, from `repost_cascades.csv` author/relayer fields)
accounts for only 0.92% of total reposts (as relayer) and 2.11% (as author of reposted content) --
proportional to their 2.0% population share, not inflated. So the bin-share shift is overwhelmingly
coming from the other ~980 untouched agents' behavior, not mechanically from the swap's own
reclassification -- a real population-wide "silencing of the moderate middle" signature.

## Bridging-role isolation (2026-07-26): three treatments that never touch opinion

**User's design critique**: the swap-to-extreme manipulation bundles two different things into one
-- "remove the bridge" and "inject a new extremist" -- confounding bridging-role removal with
population-composition change. Also raised: seed-to-seed heterogeneity in swap count (14-27 hubs)
is uncontrolled treatment-intensity noise riding along with the causal contrast.

**Three alternatives proposed (user) and implemented, none touching opinion at all:**
1. **mute_access**: `accessProb=0` for the target hubs -- full deactivation (no posting, reposting,
   following, unfollowing, or opinion update). Broadest "hub simply isn't participating" test.
2. **mute_repost**: the hub keeps posting its own (moderate) content and stays normally followable,
   but stops relaying/reposting anything. User: "reposting is crucial because of their bridging
   role" -- isolates the specific bridging mechanism.
3. **algo_exclude**: the hub is excluded from the For-You velocity-ranked candidate pool only;
   organic/chrono reach (direct followers) is untouched. User's framing: this tests the hub's role
   in the hop-based recommender specifically; since literal node removal "is not a pure
   counterfactual" (removes the node from structural metrics too, and reopens the substitution/
   reserve-pool problem already flagged for the original hub-swap series), "implement ignorance
   just inside the recommendation algo" instead.

**Implementation** (`src/experiment/ExperimentConfig.java`, `src/experiment/SimParams.java`,
`src/dynamics/OpinionDynamics.java`, `src/admin/AdminOptim.java`, all 2026-07-26): three new CLI
tokens (`mute_access_ids`/`mute_repost_ids`/`algo_exclude_ids`, comma-separated agent IDs),
independent of the pre-existing `InterventionSetup` pool-selection machinery (that pathway picks
hubs by its own extreme/topk/sizeStrategy heuristics; these are driven directly by an externally-
supplied ID list, same pattern as the swap scripts' `moderate_hub_ids()`). `mute_access`/
`mute_repost` are applied directly to `agentSet` at the top of `evolve()` (`setAccessProb(0.0)` /
`setChannelMode(POST_ONLY)` -- the latter reusing the pre-existing but previously-unwired
`Agent.ChannelMode` machinery, built 2026-07-XX for "Exp A: repost-channel isolation" but never
connected to an externally-driven ID list before). `algo_exclude` threads a new `Set<Integer>`
field through `SimParams` (record, one new trailing field + `from()` update) and adds a single
filter line in `AdminOptim.AdminFeedback`'s For-You candidate loop
(`if (p.algoExcludeIds().contains(author)) continue;`), before the existing block/reach checks --
excluded authors' posts simply never enter the algorithmic pool, chrono delivery to direct
followers is untouched.

**Why this is more robust than the opinion-swap approach, not just cleaner in principle**: none of
the three requires editing a GEXF file at all -- CONTROL and TREATMENT read the *same* unmodified
base network, differing only in CLI tokens. This sidesteps the entire bug class discovered above
(forgetting to edit a second/third attribute in a hand-maintained GEXF writer).

**Verified before launch**: full `javac` recompile clean; `test.ModelTests` 44/44 PASS (no
regressions); `mute_access` spot-checked by direct GEXF inspection (`accessProb=0.0` present at
step 0 for target agents, confirming the mute is applied before the first export); `mute_repost`/
`algo_exclude` verified by code inspection only (both reuse simple, narrowly-scoped pre-existing
gates -- `Agent.repost()`'s `repostEnabled` check, already covered by the swap experiment's
continued use of the model; and a single added filter line) given time constraints.

**Design**: `scripts/hub_bridging_experiment.py`. CONTROL reused directly from disk (the mid-tier
secession experiment's control, seeds 2000000-2000019 -- identical unmodified-network continuation,
no reason to re-simulate). Each treatment continues from the same unmodified base GEXF via
`network=read` plus its one new CLI token populated with that seed's realized moderate mid-tier hub
IDs (same `moderate_hub_ids()` selection as the swap experiment). `CONTINUE_STEPS=20000` (same
caveat as before: not accessProb-rescaled). Distinct continuation-seed blocks per treatment
(mute_access 2100000-19, mute_repost 2110000-19, algo_exclude 2120000-19) to avoid folder collision.

**Launched** (2026-07-26): all three run sequentially inside one `nohup bash -c '...' & disown`
wrapper (not concurrently -- 3x20 concurrent JVMs at 2GB heap would want ~120GB, over this
machine's 112GB), logs `logs/hub_bridging_{mute_access,mute_repost,algo_exclude}_mid_stdout.log`.
Results to be logged here on completion.

**Parked for later (user, 2026-07-26)**: a fraction/dose-response design (sweep the fraction of
moderate hubs muted/removed rather than binary treat/control) -- explicitly deferred until "we get
a good result" from these three, to check magnitude/dose-dependence once a real effect is
established.

### Results: all three bridging-role treatments (2026-07-26)

Paired vs. control (n=20 base seeds), key metrics, alongside the swap result for comparison:

| metric (diff vs control, t) | swap (extreme) | mute_access (full deactivation) | mute_repost (repost only) | algo_exclude (For-You only) |
|---|---|---|---|---|
| Q_sign_repost | +0.043, t=8.3 | +0.020, t=5.0 | -0.001, t=-0.3 | +0.020, t=5.1 |
| crossRepostRate | -0.052, t=-13.9 | -0.038, t=-11.4 | -0.001, t=-0.8 | -0.033, t=-10.9 |
| bimodalityCoeff | +0.037, t=15.8 | +0.012, t=8.3 | -0.003, t=-1.6 | +0.013, t=6.7 |
| blockCount | +18.5%, t=14.4 | +2.7%, t=6.6 | -2.4%, t=-5.5 | +4.3%, t=7.6 |
| postShare bin2 (moderate) | -17.3%, t=-14.8 | -8.1%, t=-14.8 | +0.8%, t=3.0 | -4.7%, t=-7.9 |
| postShare bin0+bin4 (extremes) | +18-19%, t~13-16 | +7% each, t~9-13 | -1 to -0.6%, t~-4 to -5 | +5-6%, t~9-11 |
| postShare bin1 (lean-) | +5.6%, t=3.8 | +3.2%, t=4.7 | flat, t=-0.1 | +1.6%, t=2.1 |
| postShare bin3 (lean+) | +4.1%, t=4.2 | +2.7%, t=5.2 | flat, t=0.3 | flat, t=1.0 |
| sf1_ratio | 0.843 vs 0.868, t=-0.31 | 0.897 vs 0.868, t=0.32 | 0.712 vs 0.868, t=-1.75 | 0.834 vs 0.868, t=-0.43 |

**Clean pattern: `mute_repost` is null/mildly opposite-signed everywhere, while `mute_access` and
`algo_exclude` both reproduce the swap's qualitative signature at somewhat smaller magnitude, and
nearly match EACH OTHER** despite `algo_exclude` leaving the hub's own posting/reposting/organic-
follow reach completely untouched. Bin1/bin3 (lean, not extreme) move in the same direction as the
poles but smaller -- a genuine spread across the whole distribution, not just a two-point split.
`sf1_ratio` stays unresolved everywhere (all \|t\|<2, consistent with the project's established
~85-seed requirement), though directionally lowest for `mute_repost` and `algo_exclude` -- not
claimed as a finding, flagged for a future higher-n check.

**Read: the effect is carried by algorithmic amplification of the hub's content, not by the hub's
own active reposting/relaying.** Removing the hub from For-You surfacing alone gets you most of the
way to full deactivation's effect; removing only their reposting activity (while their own original
content and organic reach are untouched) does almost nothing. Directly engages
`research-direction.md`'s own flagged "conduit redundancy" risk (that at high algorithmic share the
follow-graph conduit could be washed out by the algorithm doing all the work) -- this result is
fairly direct evidence *for* that risk being real at the current operating point (`alpha=0.63`,
majority-algorithmic feed).

### algo_exclude corrected (2026-07-26): post-filter vs. graph-level BFS exclusion converge

User clarified the intended `algo_exclude` semantics were misimplemented: the first version only
filtered target-hub-authored posts out of each reader's own For-You candidate list (a post-
authorship filter). What was actually wanted: remove the target hubs from the **graph used for the
h-hop reachability BFS itself**, so they can neither surface their own content NOR serve as an
intermediate/bridge node connecting two OTHER agents' h-hop neighborhoods -- "excluded from the
network" for recommendation purposes, not just filtered at final candidate selection.

**Fix** (`AdminOptim.java` `computeReachable`/`ensureReachable`): `algoExcludeIds` threaded into the
BFS itself -- skipped whenever considered as a neighbor during frontier expansion (`if
(!excludeIds.contains(v) && visited.add(v)) frontier.add(v)`), so excluded agents never enter
anyone else's `reachableCache` and never get expanded through as a hop. An excluded agent's own
`reachableCache[self]` is still computed normally (their own feed as a reader is unaffected -- only
how others reach them/route through them changes). Kept the original post-authorship filter too, as
a safety net for the `h<=0` (global reach) edge case where the BFS cache isn't used at all.

Old (buggy) `algo_exclude` results (seeds 2120000-2120019) discarded and re-simulated under the
corrected semantics. `javac` clean, `test.ModelTests` 44/44 PASS.

**Result: the corrected version is statistically indistinguishable from the old (incorrect) one**
(Q_sign_repost +0.0203 vs +0.0213, crossRepostRate -0.0328 vs -0.0326, postShare bin2 -0.0157 vs
-0.0154, all within noise of each other). **This is informative, not a wasted fix**: it means the
target hubs' bridging/intermediary-ROUTING function through the h-hop BFS barely matters at
`hop=4` in this network's density -- too many alternative paths exist for removing ~20 nodes as
potential intermediate hops to meaningfully shrink anyone else's reachable set. The entire measured
effect comes from the simpler mechanism (the hub's own content no longer being algorithmically
surfaced), not from severing graph connectivity. Both implementations were, in practice, testing
the same thing at this operating point -- the distinction is real in principle (and could matter at
a different `hop`/network-density setting) but didn't bite here.

## SF1-prerequisite gap found, and full revalidation at accessProb=0.1 (2026-07-26/27)

**Gap found (user question: "why always the sf1 results be less than 1.0? has it confirmed by the
model calibration?").** Traced the history: the [1.19,1.26] SF1 target was only ever confirmed at
`accessProb=0.1`/`steps=20000` (the v9-v15 calibration convention). `accessProb` was cut to 0.025 on
2026-07-25 to fix bin7 non-stationarity at steps=40000 -- that fix's own verification run only
re-checked bin7, never SF1. Today's control arm under the un-validated cut read SF1=0.868+/-0.276
(n=20) -- 95% CI entirely below 1.0, not explainable as noise. Compounding it: metrics were being
read after a further 20000-step continuation on top of the already-un-validated 40000-step base
(effectively global step ~60000), even further from anything ever checked, and in the direction
(per the bin7 evidence) the fit is known to drift worse over time.

**User's fix (2026-07-26): revert `accessProb` to 0.1, shorten to `steps=20000`, check the
trajectory at step=10000 AND step=20000 instead of trusting one far-future point.** Full pipeline
rewrite, `scripts/bridging_revalidated.py`: rebuilds 20 fresh base equilibrium networks
(`access_prob=0.1`, `steps=20000`, seeds 1800000-1800019; realized mid-tier moderate-hub counts
3-16 per seed, mean ~8.5 -- fewer than the old accessProb=0.025 run's 14-27, expected given
different dynamics), then all 5 arms (control, swap, mute_access, mute_repost, algo_exclude) as
20000-step continuations, metrics read at both checkpoints via `read_metrics_at`. Distinct
continuation-seed blocks per arm (1810000/1820000/1830000/1840000/1850000 + i). Smoke-tested
end-to-end at reduced scale (steps=5000, 1 seed, all 5 arms) before the full launch -- clean.
Launched via `nohup ... & disown`; ran ~3h wall time across the equilibrium build + 5 sequential
20-seed arms (steps=20000 at access_prob=0.1 is heavier per-step than the old access_prob=0.025
runs, since more agents are active each step). Full log: `docs/report/bridging_revalidated.csv`.

**Framing set by the user, load-bearing for how these results should be read**: achieving SF1 > 1
under a properly validated config is a *prerequisite* for the paper's actual causal claim (moderate-
hub conduiting sustains realistic apparent polarization). This experiment series does not yet run on
top of such a validated config (see below -- control SF1 is closer but still short). User is running
a separate, deeper calibration sweep on another server to find/confirm a qualifying config. **Treat
everything below as mechanistic hint-gathering** (which channel the bridging effect runs through),
not paper-ready evidence, until that sweep produces a qualifying point.

**Control SF1 trajectory**: step 10000 = 0.900+/-0.155 (n=20), step 20000 = 0.960+/-0.119 (n=20) --
much closer to target than the un-validated accessProb=0.025 read (0.868+/-0.276), roughly half the
variance, and *converging toward* the target with more simulated time rather than drifting away
(the opposite of the accessProb=0.025/bin7 pattern). Still short of [1.19,1.26] at step 20000 (95%
CI [0.908,1.012]).

**Results at step 20000 (n=20 pairs, paired t vs. control), key metrics:**

| metric | swap | mute_access | mute_repost | algo_exclude |
|---|---|---|---|---|
| sf1_ratio | 1.032 vs 0.960, t=2.32 | 0.997 vs 0.960, t=0.95 | 0.966 vs 0.960, t=0.19 | 1.030 vs 0.960, t=2.20 |
| Q_sign_repost | +0.005, t=0.81 (ns) | -0.001, t=-0.29 (ns) | ~0, t=-0.01 (ns) | ~0, t=-0.02 (ns) |
| crossRepostRate | -0.032, t=-6.64 | -0.022, t=-6.13 | -0.004, t=-1.71 (ns) | -0.018, t=-4.69 |
| bimodalityCoeff | +0.020, t=8.08 | +0.010, t=6.28 | ~0, t=0.03 (ns) | +0.010, t=6.00 |
| postShare bin2 (moderate) | -0.030, t=-7.80 | -0.018, t=-7.05 | +0.001, t=0.68 (ns) | -0.013, t=-4.39 |
| postShare bin0+4 (extremes) | +0.012/+0.012 | +0.007/+0.005 | ~0/~0 (ns) | +0.007/+0.005 |

**Two things changed relative to the accessProb=0.025 series, neither swept under the rug:**
1. **`sf1_ratio` itself now moves with real signal for `swap` and `algo_exclude` specifically**
   (t~2.2-2.3) -- the first time the actual target metric (not just structural/behavioral proxies)
   has shown a resolvable treatment effect. `mute_access`/`mute_repost` don't reach significance on
   SF1.
2. **`Q_sign_repost` lost ALL significance across every treatment** (was one of the strongest
   signals under the old config, t up to 8.3; now every arm is \|t\|<1). This earlier "finding" does
   not survive the accessProb correction and should not be carried into any write-up.

**Everything else replicates robustly**: the behavioral U-shape (moderate-share collapse, both
extremes gain, cross-repost drops, `mute_repost`~null everywhere) holds under the corrected
baseline at essentially the same qualitative pattern as the (invalid) accessProb=0.025 run -- not
an artifact of that un-validated config.

**Status**: paused here pending (a) the user's parallel calibration sweep finding/confirming a
config that actually clears SF1>1.19, and (b) a decision on whether to extend these arms' step count
further (control SF1 was still rising at step 20000, not yet plateaued) once that lands.

## Asymmetric ideological homophily as a missing mechanism for the red/blue postShare gap (2026-07-27)

**Observation (user, via dashboard, manual param sweep on a git-uncommitted config -- see current
`ExperimentConfig.java`: `followProb=0.01`, `feedAlgoShare=0.7`, `feedHopH=2`, `feedCapacity=15`,
`accessProb=0.1`, `pU=0.05`, `bcRecoveryRate=0.0001`, `bcDecRate=0.5`, `bcInit=0.5`,
`vocalComfortRadius=0.2`, `postProbRelaxRate=0.1`, `initialPostProb=0.25537`,
`minPostProb=0.01`, `maxPostProb=1.0`; `initOpinionDist` -- default is `"gaussian"`
(`ExperimentConfig.java:252`), **not confirmed which value this specific dashboard run actually
used** -- open item, check before trusting the population-count explanation below as literal, not
just structural, for this run).** Two dashboard panels, 5-seed means: `cRateMean` (per-agent comfort
rate feeding the vocality mechanism) rises to comparable levels for both extreme camps (blue/negative
and red/positive) relative to the moderate/center camp -- but `postShare` (aggregate share of total
posts) stays dominated by the blue extreme; red's postShare tracks near or below moderate's despite
comparable `cRateMean`.

### Mechanism trace: why `cRateMean` and `postShare` can diverge

Vocality update, `Agent.java:333-336,376-402`: `comfortPostRate_i = |{feed posts within
vocalComfortRadius of opinion_i}| / |feed_i|`; `targetPostProb_i = minPostProb + (maxPostProb -
minPostProb)*comfortPostRate_i`; `postProb_i += postProbRelaxRate*(target - postProb_i)`. **No term
references `opinion_i` or `|opinion_i|` directly** -- extremity only enters through feed composition.
`postShare`, `computePostShareArray` (`Analysis.java:588-596`), is a **population-weighted aggregate**
(`postShareArray[classId] += 1.0` per post, normalized by total posts that step) -- mechanically
`bin_population x mean_postProb_in_bin`, unlike `cRateMean` which is a genuine per-agent average.
Bin membership (`setOpinionClass`, `Agent.java:234-238`) is reassigned from **live/current** opinion
after every update, not intrinsic opinion -- so a numerically small camp can also shrink over the run
via bc-driven assimilation, on top of any initial imbalance. If `initOpinionDist=empirical` is active,
`Const.EMPIRICAL_OPINION_BIN_COUNTS = {160,131,85,208,46,71,64}` (`Const.java:62`) gives the negative
extreme bin 2.5x the population of the positive extreme bin at t=0 -- a real, literature-sourced
(Buntain & Snegovaya's survey sample) asymmetry, not an artifact.

### Literature check: does the source paper explain the mechanism? No -- checked directly

Fetched Buntain & Snegovaya (2025, *PNAS Nexus* 4(11):pgaf333) directly. It reports the fact
(`"hyper-partisan accounts...are the most active, posting about twice as often as respondents in
other ideological bins"`) but is purely descriptive at the individual level -- no network-structure,
clustering, or homophily analysis anywhere in the paper. The "dense minority echo chamber" hypothesis
is **not** grounded in that paper; it required a separate literature search.

### Literature check: the broader asymmetric-homophily literature does support it

Searched and read in full: **Boutyline & Willer (2017, *Political Psychology*), "The Social Structure
of Political Echo Chambers"** (free author PDF, `ocf.berkeley.edu/~andrei/downloads/echo.pdf` --
Wiley's version is paywalled). N=238,943 Twitter ego networks of followers of 159 Congress members +
33 policy non-profits, 2009 pre-"Who to Follow" data (deliberately chosen to isolate organic, not
algorithmically-nudged, homophily). Homophily measure `o(f,H)` = % of a follower's other ties that
also follow the same hub H (a direct analog of this model's `follow()` bc-gated tie formation).
Ideology decomposed orthogonally: `score = extremity * (-1)^conservatism`, `extremity = |score|`
(continuous, σ=1), `conservatism = 1(score>0)` (binary direction).

**Regression results (Table 2, followers of Congress, N=238,943, cluster-adjusted SEs):**

| predictor | Model 1 (no controls) | Model 2 (full controls) |
|---|---|---|
| ideological conservatism | β=3.802, p<0.001 | β=3.251, p<0.001 |
| ideological extremity (1 SD) | β=4.533, p<0.001 | β=4.057, p<0.001 |

Mean observed homophily across the sample: 11.0-11.2%. Independent replication on policy non-profit
followers (N=103,864, further removed from party-organizational confounds): conservatism β=7.456→6.305
(controlled), extremity β=4.316→4.332 -- same sign, larger magnitude. Illustrative single-pair case
(not the regression, an anchor only): Cato Institute (conservative) vs. Amnesty International
(liberal), follower counts matched within 3% (10,298 vs 10,638) -- mean homophily 13.04% vs 6.75%.
**Robustness**, all reported in the paper: survives a reciprocity control (rules out "conservative
hubs' followers just get followed back more"), holds restricted to reciprocated/stronger ties only
(β=2.515-4.86, still p<0.001-0.05), replicates under randomization inference and propensity-score
matching (p<0.001, all 8 comparisons), and a reverse-causality check (homophily-x-account-age
interaction predicting extremity) found the main effect essentially unchanged, arguing against
"network structure caused the ideology" as an alternative explanation.

**Key algebraic point for this project's specific target.** For two agents at **equal extremity,
opposite sign** (i.e., exactly the red-extreme vs. blue-extreme comparison this project cares about),
the extremity term is identical for both and cancels. The entire homophily gap between them is
`β_conservatism` alone (3.25-3.80, controlled/uncontrolled) -- the extremity term (4.06-4.53, the
larger of the two coefficients) is *not* needed to explain this particular asymmetry, only the
already-separately-missing moderate-vs-extreme gap (which `cRateMean`'s current behavior suggests may
already be partially working via the indirect density channel).

### Decision (user, 2026-07-27): add a sign-conditional narrowing of `bcInit` for `opinion>0` agents, calibrated against this effect size

Rationale for the lever: `bc` gates `follow()`'s tie-admission directly -- the literal analog of
`o(f,H)`'s tie-formation mechanism, not a loose metaphor. The paper's own theoretical mechanism
("preference for certainty," Jost et al.'s motivated-cognition/rigidity literature) is a dispositional
trait argument, making a static initial-condition parameter (`bcInit`) a more construct-valid
translation than a stochastic follow-preference weight would be.

**Not yet decided / flagged before implementation, to inform the calibration run on the other server:**
1. **Unit mismatch -- do not plug 3.25 directly into `bcInit`.** β is in percentage points of
   `o(f,H)` (0-100% scale), not bc-width units on `[bcFloor,bcCeiling]`. Requires introducing a free
   `conservativeBcNarrowing` parameter, measuring this model's own homophily analog (assortativity, or
   a same-sign-tie-fraction built the same way as `o(f,H)`) as a function of it, and calibrating until
   the *relative* asymmetry matches (target ratio ≈ (11+3.25)/11 ≈ 1.30 using the controlled estimate,
   not an absolute offset).
2. **Which β to anchor on:** recommend the controlled congressional estimate (3.25, nets out
   constituency/prominence/Tea Party/margin confounds) as primary target; non-profit replication
   (6.31-7.46) as an upper-bound sensitivity check, not an average.
3. **Reopens calibration, not a bolt-on.** `bcInit` is currently one scalar the whole 11-dim BO history
   tuned assuming a symmetric population. Splitting it by sign adds a free dimension; the existing
   optimum is not guaranteed valid for either half post-split.
4. **Secondary effect beyond topology, to report explicitly, not hide.** `bc` also gates FJ
   assimilation/bc-decline (`Agent.java` `updateMyself()`), not just tie formation. Narrowing it for
   `opinion>0` agents means they'll also resist opinion change more -- which favorably double-fixes the
   live-reclassification/attrition confound already flagged in this document's `setOpinionClass`
   discussion above, but is importing a second implication of "preference for certainty" the homophily
   paper itself never measured. Legitimate given Jost et al.'s broader rigidity literature, but must be
   stated as an added assumption, not presented as a pure homophily replication.
5. **Regime-dependent.** Only equivalent to "persistently narrower bc" while the model stays in the
   current static-bc regime (`bcDecRate`/`bcRecoveryRate` ≈ frozen, per the 2026-07-20 static-bc
   finding earlier in this document). If bc dynamics get reopened (a "graded bc-relaxation mechanism"
   is already in progress per recent commits), an initial-only offset can decay away silently --
   revisit this dependency if/when that happens.
6. **Avoid a hard step at `opinion=0`.** Gate the narrowing the same way this codebase already
   excludes undecidable moderates elsewhere (`|opinion| > moderateBandHalfWidth`, or a continuous
   scaling) rather than a bare sign check, to avoid an artificial discontinuity at the origin.

**Status: mechanism and literature grounding written up here; calibration (OAT scan of
`conservativeBcNarrowing` against the model's own homophily metric, then joint recalibration of
`bcInit`+the new parameter) to be run by the user on a separate server.** No code changes made in this
session -- `Agent.java`/`ExperimentConfig.java` still have a single, sign-agnostic `bcInit`.

Sources: [Post-January 6 deplatforming shows long-term effects on ideological polarization among
Twitter users (Buntain & Snegovaya, PNAS Nexus 2025)](https://academic.oup.com/pnasnexus/article/4/11/pgaf333/8299825);
[The Social Structure of Political Echo Chambers (Boutyline & Willer, Political Psychology
2017)](https://onlinelibrary.wiley.com/doi/abs/10.1111/pops.12337) (free PDF:
[ocf.berkeley.edu/~andrei/downloads/echo.pdf](https://www.ocf.berkeley.edu/~andrei/downloads/echo.pdf)).

## Self-run 5-seed check at the "new calibration plan" config (2026-07-27): SF1 mean lands in target band for the first time, but n=5 is not a confirm

User hand-ran 5 seeds (seed 0-4, `results/run_0..4_ext-NONE_nmod-0_size-LARGEST_ch-BOTH`, no
intervention) directly against HEAD's `ExperimentConfig.java` -- the commit right after this
(`7df0011`, "new calibration plan") froze exactly this point: `followProb=0.01`, `feedAlgoShare=0.7`,
`feedHopH=3`, `feedCapacity=15`, `accessProb=0.1` (the validated value, per the 2026-07-26/27 gap-fix
above), `pU=0.05`, `bcRecoveryRate=0.0001`, `bcDecRate=0.5`, `bcInit=0.8`, `vocalComfortRadius=0.1`,
`postProbRelaxRate=0.1`. `n=1000`, `steps=40000`, `network=hk`. Computed SF1 (`postOpinionVar/
opinionVar`, same definition as `app_pol_baseline_bo_calibration.py`) and the other joint-calibration
metrics directly from `results.csv`/`modularity.csv`/degree files (no existing launcher script matched
this exact manual run, so metrics were recomputed ad hoc, same formulas as `read_metrics()` in that
script).

| step | SF1 ratio (mean+/-std, n=5) | assort | Q_sign_repost (target 0.48) | Gini (target 0.8) |
|---|---|---|---|---|
| 20000 | 1.2946 +/- 0.3476 | 0.7193 | 0.4015 | 0.8795 |
| 40000 | 1.2334 +/- 0.2241 | 0.7790 | 0.4194 | 0.8795 |

Per-seed SF1 at step 40000: `[0.976, 1.118, 1.435, 1.077, 1.560]` -- 4/5 above 1.0, 2/5 inside
`[1.19,1.26]`, one (seed 4) well past it.

**Read**: this is the first point where SF1's *mean* sits inside the target band under the validated
`accessProb=0.1` convention -- an improvement over the bridging-revalidation control arm two sections
above (stuck at `0.960+/-0.119`, n=20, at the old v15-ish point). Real signal, not nothing.

**Not a confirm, for reasons already established earlier in this document**: (1) n=5 is exactly the
sample size repeatedly flagged here as noise-dominated for SF1 (`"SF1 needs ~85+ seeds to resolve"`);
SE at step 40000 is ~0.10, so the 95% CI (~[1.03,1.43]) doesn't exclude "still short." (2) Gini
(0.880) and Q_sign_repost (0.419) both sit outside their calibration-scale tolerance (0.05) from
target (0.8 / 0.48) -- this is a hand-set point, not one that came out of a joint BO fit, so SF1
landing close doesn't mean the other stylized facts are simultaneously satisfied. (3) The ratio moved
1.295->1.233 between checkpoints (toward target, encouragingly, but a single 5-seed run can't
separate real convergence from noise, consistent with the still-not-cleanly-plateaued behavior noted
throughout this document).

**Next step, not yet run**: a 20-seed confirm at this exact point (same protocol as
`confirm_v9_best_20seed.py`/`confirm_v7_best_20seed.py`) would roughly halve the SE and give SF1 real
resolving power at step 40000 against `[1.19,1.26]`.

## Moderate-hub bridging experiment redone on the current-config point (2026-07-27): user's call, not for the paper's calibration claim, but re-run for the causal-mechanism section anyway

User's framing after the 20-seed confirm above landed: this config isn't going into the paper as the
calibrated point (it overshoots SF1 and misses Gini/Q/assort as shown above), but it's "the best one
ever" behaviorally, so the moderate-hub causal-manipulation section (the `control`/`swap`/
`mute_access`/`mute_repost`/`algo_exclude` design from the accessProb=0.1/0.025 series earlier in this
document) should be re-run on it anyway -- same status as those earlier series: mechanistic
hint-gathering, not paper-ready evidence.

**Implementation note (process, not science, but worth recording):** first attempt used seed base
`2000000` for the fresh equilibria, chosen without checking the existing `results/` inventory. That
range turned out to already be in use by the mid-tier secession/hub_bridging experiments documented
earlier in this file (`2000000-2000019` = secession control, `2010000-2010019` = secession treatment,
`2100000-2120019` = mute_access/mute_repost/algo_exclude). `is_done()` short-circuits before any
`launch()` call, so nothing was actually overwritten -- but the script would have silently built the
whole experiment on the *wrong* base equilibria (old v15-point secession-control networks, not fresh
current-config ones). Caught within seconds via the "reusing existing" log lines looking suspicious,
killed, incomplete garbage at the untouched `2020000-2020019` swap-arm range removed, re-launched on a
seed base (`3000000`+) verified against the full `results/` seed inventory beforehand
(`scripts/bridging_current_config.py`, updated to `FIXED` = current `ExperimentConfig.java` defaults).

**Realized moderate mid-tier hub counts are notably sparser than the old config**: `[5,3,4,7,6,6,7,8,
2,8,5,6,4,4,5,6,7,5,3,6]` across the 20 equilibria, mean **5.35** (min 2, max 8) -- vs. the old
v15-point's "3-16 per seed, mean ~8.5" reported in the accessProb=0.1 revalidation above. ~37% fewer
hubs per seed on average going into a causal-contrast design is exactly the kind of thing that inflates
cross-seed variance on any hub-driven effect; keep this in mind reading the results below.

**Results, n=20 pairs, paired t vs. control, step 20000 (full step-10000 checkpoint also in
`docs/report/bridging_current_config.csv`):**

| metric | swap | mute_access | mute_repost | algo_exclude |
|---|---|---|---|---|
| sf1_ratio | 1.298 vs 1.320, t=-0.30 | 1.277 vs 1.320, t=-0.72 | 1.332 vs 1.320, t=0.22 | **1.457 vs 1.320, t=1.97** |
| Q_sign_repost | -0.005, t=-0.88 (ns) | -0.001, t=-0.23 (ns) | +0.008, t=1.07 (ns) | +0.006, t=0.78 (ns) |
| crossRepostRate | -0.017, t=-1.85 (ns) | -0.008, t=-1.42 (ns) | -0.004, t=-0.59 (ns) | -0.008, t=-1.67 (ns) |
| bimodalityCoeff | +0.009, t=1.46 (ns) | +0.002, t=0.43 (ns) | ~0, t=0.01 (ns) | +0.003, t=0.74 (ns) |
| postShare bin2 (moderate) | -0.035, t=-1.34 (ns) | -0.009, t=-0.92 (ns) | +0.015, t=0.81 (ns) | -0.001, t=-0.16 (ns) |
| postShare bin0+4 (extremes) | +0.009/+0.004 (ns) | -0.005/+0.003 (ns) | +0.003/+0.005 (ns) | +0.007/+0.007 (ns) |
| disagreement | **+0.0129, t=6.58** | -0.003, t=-1.09 (ns) | +0.001, t=0.32 (ns) | +0.002, t=0.98 (ns) |
| unfollowCount | **+807, t=2.91** | +536, t=1.28 (ns) | -424, t=-1.51 (ns) | -302, t=-1.20 (ns) |

**Headline: almost everything that was statistically resolvable in the accessProb=0.1 revalidation
above (`swap`/`algo_exclude` on SF1; every arm's `crossRepostRate`/`bimodalityCoeff`/postShare U-shape)
loses significance at this point.** Point estimates mostly keep the *same qualitative direction*
(moderate-share collapse, extremes gain, cross-repost down, bimodality up) but the effect sizes shrink
and/or the noise grows enough that nothing but `algo_exclude`'s SF1 effect and `swap`'s
disagreement/unfollow effects clear conventional significance. Given the ~37%-sparser hub population
noted above, this reads as a power problem (fewer hub-carrying seeds -> noisier per-seed treatment
dose), not evidence the underlying mechanism disappeared -- but it must be reported as "not resolved
at this operating point," not glossed over.

**What *does* replicate, and is therefore the more trustworthy part of this result:**
- **`algo_exclude` increases SF1 relative to control, same direction as the accessProb=0.1
  revalidation, and if anything a larger point estimate** (+0.137 here vs. the earlier +0.070ish),
  though `t=1.97` (n=20) is just short of the conventional 0.05 threshold rather than clearly past it
  as before (`t=2.20`). Across two different, independently hand-set operating points, "excluding the
  moderate hub from the algorithmic BFS increases apparent polarization" is the one causal claim in
  this series that has now shown up twice in the same direction -- the closest thing to a robust
  finding in this whole experiment series so far.
- **`swap` still produces significant behavioral friction** (disagreement, unfollowCount, and at the
  earlier step-10000 checkpoint also `crossCuttingFraction` t=4.29, `bimodalityCoeff` t=2.84,
  `opinionKurtosis` t=-2.70, `outGroupBlockPropensity` t=3.96, `outGroupSanctionRate` t=3.64 -- all
  fading toward non-significance by step 20000) even though its SF1 effect itself doesn't replicate
  (previously significantly positive, t=2.32; here non-significant and sign-flipped, t=-0.30). Reading:
  swapping the moderate hub to an extreme reliably increases local friction/hostility signals early,
  but that doesn't cleanly translate into the *aggregate* apparent-polarization ratio at this sparser-
  hub operating point.
- **`mute_repost` remains null on essentially everything, both times** -- but see the 2026-07-27
  correction later in this document (Rollup section): the targeted hubs' repost volume is <1% of the
  network total, so this null is more likely an underpowered dose than a real absence of effect.

**Status: still hint-gathering, per the user's own framing, not paper-ready.** The two-for-two
replication of `algo_exclude`'s SF1-boosting direction is worth carrying forward as the most credible
lead if/when a properly calibrated point is eventually found; everything else in this run should be
read as "didn't resolve here," not "disproven."

## Same experiment, top-tier ("mega") hubs instead of mid-tier (2026-07-27): behavioral/structural effects resolve MORE clearly, SF1 itself resolves LESS -- an informative dissociation, not just noise

User asked to try the bridging series on top-tier hubs instead of mid-tier. Known prior caveat, from
this document's mid-tier-first decision: under the old v15-point config, the mega tier was flagged as
"the wrong tier" because reach already saturates the network (~72.5%) regardless of the hub's
opinion, so a treatment effect is hard to see there on principle. Re-checked anyway since this
config's realized hub composition differs throughout.

**Implementation**: `scripts/bridging_current_config_megatier.py`, `TIER_BOUNDS=(500, N)` (mega,
`followerCount>500`) instead of `(100,500)` (mid), reusing the SAME 20 already-built current-config
equilibria (`seeds 3000000-3000019` -- tier only affects downstream hub selection, not the
equilibrium build) with fresh arm seed ranges (`4010000-4050000`, verified unused beforehand -- no
repeat of the earlier seed-collision mistake).

**Realized mega-tier moderate hub counts are even sparser than mid-tier's**: `[1,8,7,3,0,0,1,7,1,1,2,
2,4,2,0,2,1,0,3,7]`, mean **2.6** (vs. mid-tier's 5.35), and **4 of 20 seeds have ZERO mega-tier
moderate hubs** -- those seeds' swap/mute arms are identical to control by construction, diluting the
contrast further on paper. Despite that, the results below are *not* uniformly washed out --
suggesting each mega-tier hub's larger individual reach compensates for there being fewer of them.

**Results, n=20 pairs, paired t vs. control, step 20000:**

| metric | swap | mute_access | mute_repost | algo_exclude |
|---|---|---|---|---|
| sf1_ratio | 1.395 vs 1.315, ns (t=0.90) | 1.290 vs 1.315, ns (t=-0.31) | 1.422 vs 1.315, ns (t=1.26) | 1.366 vs 1.315, ns (t=0.69) |
| crossRepostRate | **-0.022, t=-3.10** | -0.007, t=-1.12 (ns) | +0.007, t=1.02 (ns) | **-0.017, t=-2.45** |
| postShare bin2 (moderate) | **-0.045, t=-2.61** | **-0.044, t=-2.05** | +0.010, t=0.74 (ns) | **-0.072, t=-2.89** |
| postShare bin3 (extreme, gains) | **+0.034, t=2.32** | +0.028, t=1.41 (ns) | +0.001, t=0.06 (ns) | **+0.048, t=2.30** |
| unfollowCount | **+2156, t=2.85** | +684, t=1.90 (ns) | -248, t=-1.41 (ns) | +596, t=1.45 (ns) |
| outGroupBlockPropensity | **+0.0001, t=3.40** | +0.00004, t=1.28 (ns) | ~0, t=-1.97 (ns) | +0.00005, t=2.19 (ns) |
| outGroupSanctionRate | **+0.0005, t=3.31** | +0.0001, t=1.17 (ns) | -0.0001, t=-2.21 (ns) | +0.0001, t=1.62 (ns) |
| opinionVar | **+0.0041, t=3.16** | ~0, t=0.05 (ns) | -0.0007, t=-0.38 (ns) | +0.0013, t=0.61 (ns) |

**Headline dissociation, the opposite pattern from the mid-tier run above**: at mega tier, the
moderate-postShare-collapse/extreme-gain U-shape and `crossRepostRate` drop are now the
*best-resolved* effects (significant for `swap` and `algo_exclude`, both checkpoints -- step 10000
shows the same pattern, e.g. `postShare bin2` t=-2.78/-2.50/-3.03 for swap/mute_access/algo_exclude),
and `swap`'s friction/hostility metrics (`unfollowCount`, `outGroupBlockPropensity`,
`outGroupSanctionRate`, `opinionVar`) are cleaner and *more* significant than the mid-tier run's
equivalents. **But `sf1_ratio` itself doesn't resolve for any arm at mega tier** -- weaker than even
the marginal mid-tier `algo_exclude` result (t=0.69 here vs. t=1.97 at mid-tier for the same arm).

**Reading, stated carefully rather than over-claimed**: this is not simply "mega tier is noisier
because of the zero-hub seeds" -- if it were pure dilution, the *already-established* effects
(postShare U-shape, crossRepostRate, friction metrics) should have gotten weaker too, and instead they
got stronger/cleaner. What seems to be happening is a genuine **decoupling between the compositional/
structural channel (who posts what, how much gets reposted, local friction) and the aggregate SF1
ratio** -- consistent with this document's much earlier, independently-arrived-at point that SF1 is a
noisy, slow-resolving final-step aggregate while structural/behavioral metrics resolve with far fewer
seeds. Mega-tier hubs apparently move the *composition* channel more (larger individual reach, bigger
per-hub footprint on `postShare`/`crossRepostRate`) without moving *aggregate opinion-variance-ratio*
proportionally -- plausibly because a hub's front-and-center reach affects who's exposed to what more
than it affects the eventual variance of what gets posted. Also worth noting against the old
"mega saturates reach regardless of opinion" caveat: that finding doesn't obviously hold here either,
since these results are *not* flat nulls -- whether that's because this config's mega-tier reach is
less saturating than the old config's, or because the postShare/crossRepostRate channel isn't the one
saturation would suppress, is not resolved by this run and would need the actual reach-fraction
numbers (not computed here) to settle.

**Status: same as the mid-tier redo -- hint-gathering, not paper-ready, per the user's framing.** But
this specific dissociation (behavioral channel resolves at mega tier, SF1 aggregate resolves better at
mid tier, neither resolves both at once) is itself a real, reportable pattern worth keeping in mind
when this project eventually chooses which tier(s) to feature in the paper's causal section -- they
may be telling genuinely different parts of the same story rather than one being "the right answer."

## Rollup (2026-07-27): does WSSIT2026's headline claim currently happen in this model, across everything tested so far?

Prompted by a direct question after the two runs above. Two separate conditions are both required for
the paper's causal claim (moderate-hub conduiting sustains realistic apparent/affective polarization),
and across every rigorously-checked (n=20) point tested to date, **they have only ever held
separately, never simultaneously**:

**(1) Baseline SF1 in the empirical target `[1.19,1.26]`** -- never achieved with statistical
confidence at any tested point:
- Old v15-point (`accessProb=0.1` revalidated, this doc, "SF1-prerequisite gap found" section):
  control = **0.960+/-0.119** (n=20, step 20000) -- short.
- Current "new calibration plan" point (this doc, "20-seed confirm" section): control =
  **1.320+/-0.286 -> 1.548+/-0.335** (n=20, step 20000->40000, worsening with more steps) --
  overshoots.
- The model's baseline has passed *through* the target band as parameters moved between these two
  points, but no config tested has landed inside it with real resolving power.

**(2) The moderate-hub manipulation causally moving SF1 in the conduit direction** -- shown
significant exactly once, and only at the point that fails (1):
- Old point (control short of target): `swap` t=2.32, `algo_exclude` t=2.20 -- both significant
  SF1 increases (accessProb=0.1 revalidation section above).
- New point (control overshoots target): `algo_exclude` only marginal (t=1.97 mid-tier, t=0.69
  mega-tier); `swap` flipped sign and lost significance entirely (both sections above).

**No run to date has produced both at once** -- a baseline matching the empirical target AND a
significant causal hub effect on top of it. That is the actual state of the SF1 prerequisite this
project has been tracking since 2026-07-26.

**`mute_repost` (blocking the repost-only channel) has been null on every metric, in every config, at
every tier, every time it has been tested** (accessProb=0.1 revalidation, current-config mid-tier,
current-config mega-tier). **Correction (2026-07-27, prompted by a user question challenging whether
this null is trustworthy): checked directly against `repost_cascades.csv`'s `relayer` column rather
than trusting the code path alone.** The mute genuinely engages -- one spot-checked seed's 5 muted
mid-tier hubs produced exactly 0 reposts vs. ~2900 each unmuted in the paired control, and
`Agent.repostEnabled` is set once at t=0 and never reset -- so this is not a wiring bug. But **the
targeted hubs' repost volume is only ~0.2-0.8% of total network repost activity (mean 0.555% across
all 20 mid-tier seeds, computed directly)**. Removing well under 1% of aggregate repost volume and
finding no aggregate-metric movement is exactly what a dose/power problem looks like, not evidence
that the repost pathway is irrelevant to the paper's mechanism. **Retracting the earlier framing of
this as "a cleaner, more damaging result than the SF1 miss"** -- it is the opposite: a weaker result
than credited, because the treatment dose is tiny by construction (2-8 mid-tier moderate hubs out of
1000 agents). Testing the repost-channel claim properly would need either many more hubs muted
at once, or the dose-response design already flagged as "parked for later" earlier in this document
-- not this single-tier, few-hub manipulation.

**What partially survives across configs, and is therefore the most credible thread left**:
- `swap` reliably increases local friction/hostility (disagreement, unfollows, out-group sanctioning)
  at both tiers and both configs tested.
- `algo_exclude` increasing SF1 has now shown the same direction three times (old config,
  current-config mid-tier, current-config mega-tier), though clearly significant only the first time
  -- notably implicates *algorithmic surfacing*, not repost, as the more promising mechanism to
  pursue.

**Explicit caveat on scope**: this rollup covers what has been tested locally -- two operating points,
two tiers, n=20 each, not an exhaustive search. The user's parallel deeper calibration sweep on
another server (per project memory) has not landed yet, and could in principle produce a point that
clears both gates at once. As of everything checked so far, though, the headline claim has not
occurred in this model under any condition actually tested.

## Third tier completed (2026-07-27): small tier (50<followerCount<=100) -- weakest of the three, and it clarifies WHY mega beat mid/small on the behavioral channel

Completed the tier set on the current config (`scripts/bridging_current_config_smalltier.py`, same
design/equilibria, `TIER_BOUNDS=(50,100)`, arm seeds `5010000-5050000`).

**Hub density across all three tiers now characterized on this config** (contrast with the OLD
config's mega 61%/mid 16%/small 26% moderate-hub-fraction ordering, this doc ~line 1970 -- not
directly comparable since that was a fraction-of-tier-population measure, this is raw moderate-hub
count, but worth having both):

| tier | mean hubs/seed | range | zero-hub seeds |
|---|---|---|---|
| mega (>500) | 2.6 | 0-8 | 4/20 |
| mid (100-500] | 5.35 | 2-8 | 0/20 |
| small (50-100] | **6.4** | 2-14 | 0/20 |

Small tier has the *most* hubs of the three and no zero-hub seeds -- the best-powered tier on paper.

**Results, n=20, step 20000, small tier**: essentially a flat null across the board. `sf1_ratio`
diffs +0.041/+0.091/+0.003/+0.027 (swap/mute_access/mute_repost/algo_exclude), all `|t|<=1.0` --
weaker than mid-tier's already-marginal `algo_exclude` (t=1.97) and mega-tier's t=0.69. `crossRepostRate`
and `postShare bin2` (the moderate-collapse metric that was mega-tier's clearest signal, t=-2.6 to
-2.9) are **not significant for any arm at small tier** (all `|t|<1.5`). The only things that reach
significance here are `swap`'s `opinionVar` (t=3.94) and `opinionKurtosis` (t=-2.18) -- weaker/narrower
than the friction signature swap produced at the other two tiers.

**Dose check (same method as the mid-tier mute_repost correction above)**: small-tier hubs carry a
mean **0.677%** of total network repost volume (range 0.20%-1.43% across seeds) -- essentially the
same tiny dose as mid-tier's 0.555%, *despite having more hubs*. This resolves an apparent puzzle:
small-tier hubs are individually weaker (lower follower count = less reach = less repost activity per
hub), so more of them doesn't proportionally raise the aggregate dose. Consistent with the `mute_repost`
null being a dose artifact, not a real effect, at every tier tested so far.

**The three-tier pattern, put together, tells a coherent story**: mega tier -- fewest hubs (mean 2.6,
several seeds with none at all) but each individually large-reach -- produced the *clearest*
behavioral/structural signal (`crossRepostRate`, `postShare` U-shape, `swap`'s friction metrics all
significant). Small tier -- most hubs (mean 6.4) but each individually weak-reach -- produced almost
nothing. Mid tier sits in between on both hub count and effect strength, and is the only tier with even
a marginal SF1 signal (`algo_exclude`, t=1.97). **This suggests hub reach/individual size, not hub
count, is what drives the measurable causal footprint in this model** -- a sensible, mechanistically
interpretable finding, not just "more noise at more extreme tiers."

**Updated bottom line for the rollup above**: none of the three tiers, at this operating point,
produced a `sf1_ratio` effect anywhere close to significant. The mid-tier `algo_exclude` marginal
result remains the closest thing to a resolved SF1 causal effect at this config, and it is the
*weakest* tier on the structural/behavioral channel. No tier tested so far delivers both a validated
baseline and a significant causal effect simultaneously -- the conclusion of the rollup above stands
after completing the tier set, not just after two of three.

## New mechanism: true node removal, distinct from `algo_exclude` (2026-07-28)

**User's critique of `algo_exclude`, correct and load-bearing**: traced `AdminOptim.computeReachable`'s
own comment (2026-07-26) and confirmed it says so explicitly -- `algo_exclude` only changes what the
For-You BFS is willing to traverse; **"the follow graph itself (followees/followers) is untouched."**
An algo-excluded hub therefore still fully propagates through the ordinary chronological cascade
(followers -> followers-of-followers) via real, unmodified edges, and still counts as a real edge in
every structural metric (modularity, crossCuttingFraction, assortativity, degree distribution). None
of the four arms tested so far (swap/mute_access/mute_repost/algo_exclude) actually remove the hub as
a graph node -- `algo_exclude` is a narrow, feed-construction-only intervention, not a structural one.

**New mechanism implemented**: `ExperimentConfig.removeHubIds` / CLI `remove_hub_ids`
(`ExperimentConfig.java`, `OpinionDynamics.java`, 2026-07-28). At t=0, for each target hub: sever
every real edge in both directions via the same `AdminOptim.removeFollowEdge` used by ordinary
unfollow dynamics, and fully mute them (`ChannelMode.NONE` + `accessProb=0`). Self-sealing by
construction: `Agent.follow()`'s candidate list is built only from posts actually observed in an
agent's feed, and a muted, edge-severed hub can never author or be routed a new post again, so no
separate anti-reconnection guard is needed. Verified directly, not just by code-reading: a smoke test
(seed 9990000 vs. matched control 9991000, 5 mid-tier hubs) showed followerCount/followeeCount go
from real values (157-408 followers, 25-34 followees) to exactly 0 at t=0 **and stay 0 through the
whole run**, and repost events from these hubs go from 1491 (control, 2000 steps) to exactly 0
(treatment). `javac` clean; `test.ModelTests` has 3 pre-existing failures traced to stale hardcoded
defaults in the test file itself (`bcDecRate==1.0`, `p_u=0.05`-treated-as-non-default) left over from
the "new calibration plan" commit *before* this session -- confirmed unrelated by inspecting the
assertions directly; no new failures introduced.

**Design**: `scripts/bridging_current_config_removehub.py`. Reuses the mid-tier equilibria (seeds
3000000-3000019) and the mid-tier `control` runs already on disk (seeds 3010000-3010019, from the
earlier mid-tier bridging run) rather than re-simulating an identical unmanipulated continuation --
only the new `remove_hub` arm (seeds 6010000-6010019) was actually launched. Same mid-tier hub lists
as before (verified identical counts/IDs on rederivation), so this is a direct, same-hub comparison
against `algo_exclude`'s mid-tier result documented earlier in this file.

**Results, n=20, paired vs. the same control, step 20000 -- direct comparison to `algo_exclude` at
the identical mid-tier hubs**:

| metric | `algo_exclude` (mid-tier, earlier) | `remove_hub` (this run) |
|---|---|---|
| sf1_ratio | +0.1372, t=1.97 (marginal) | +0.0253, t=0.36 (ns; sign-flipped at step 10000, diff=-0.0461) |
| crossRepostRate | -0.0083, t=-1.67 (ns) | **-0.0140, t=-2.90 (significant)** |
| postShare bin2 (moderate collapse) | -0.0014, t=-0.16 (ns) | **-0.0289, t=-2.44 (significant)** |
| postShare bin0 (extreme gain) | +0.0069, t=1.80 (ns) | **+0.0090, t=2.31 (significant)** |
| disagreement | +0.0020, t=0.98 (ns) | **+0.0044, t=5.57 (highly significant)** |
| repostCount | ns | **-19183, t=-2.58 (significant)** |
| evictionCount | ns | **-249.25, t=-5.23 (highly significant)** |

**Reading: this confirms the user's critique directly.** Severing real edges (not just BFS-skipping)
unlocks exactly the effects `algo_exclude` could not see at mid tier -- the moderate-postShare-
collapse/extreme-gain U-shape and `crossRepostRate` drop, completely null under `algo_exclude` at this
tier, become clearly significant once the hub's actual structural position is removed. The effect
sizes/significance level here are comparable to what previously only showed up at **mega tier**
(t up to -2.6 to -2.9 there too), now achieved with ordinary **mid-tier** hubs -- i.e., the
chronological/structural-position channel `algo_exclude` was blind to does carry real, independently
resolvable weight, exactly as argued.

**But `sf1_ratio` itself still does not move, and is if anything weaker than `algo_exclude`'s already-
marginal result** (t=0.36 vs. t=1.97), with the sign flipping between checkpoints (step 10000:
diff=-0.046; step 20000: diff=+0.025) -- the classic signature of noise rather than a real effect.
This is not a power problem: the same run resolves `disagreement` at t=5.57 and `evictionCount` at
t=-5.23, both far past conventional significance, so this dataset clearly has resolving power when
there is something to resolve. **The pattern holds under the strongest intervention tested this
session: the compositional/behavioral channel (who posts what, how much gets reposted, local
friction) is real and scales with intervention strength, but the aggregate `sf1_ratio` is
mechanistically decoupled from it in this model/config** -- reinforcing, with much stronger evidence
than before, the dissociation flagged in the tier-comparison section above.

**Updated status for the standing rollup**: completing this stronger test does not change the
rollup's bottom line -- no manipulation tested so far (now including true node removal, the strongest
available) produces a significant `sf1_ratio` effect at this operating point. What has changed is the
confidence behind that conclusion: it is no longer "the tests so far haven't been powerful enough,"
since the compositional channel demonstrably resolves under the same data. The aggregate
apparent-polarization metric and the structural/behavioral mechanism this project has been probing
appear to be answering genuinely different questions in this model.

## `remove_hub` completed on mega and small tiers (2026-07-28) -- and a run-count policy change

**Policy change, user-directed (2026-07-28): going forward, 10 seeds per arm instead of 20.**
Rationale offered: this project's own calibration history has repeatedly found n=20 barely resolves
`sf1_ratio` anyway (SEM ~0.06-0.08 against a target window ~0.07 wide), so the marginal resolving
power lost dropping to n=10 is small relative to the compute saved, and the metrics that DO resolve
cleanly (postShare, crossRepostRate, disagreement) have tight enough SEMs that n=10 is often still
plenty. Applied starting with this entry's two runs; **the mid-tier `remove_hub` result immediately
above remains n=20** (already completed before the policy changed) -- comparisons below are
explicitly flagged as unequal-n where relevant, not silently treated as equivalent.

**Also, before running these**: reorganized `results/` (was 611 folders / 157GB in one flat
directory -- user's complaint: too heavy to browse/switch between experiments, including in the
dashboard) into per-experiment subfolders via a new `ExperimentConfig.resultsSubdir` CLI token
(`results_subdir=<name>`, `ExperimentConfig.java`/`OpinionDynamics.java`, empty by default = old flat
behavior unchanged) and widened `dashboard/core.py`'s `result_dir()` from a flat
`results/run_<seed>_*` glob to `results/**/run_<seed>_*` (verified `**` matches zero-depth too, so
this is backward compatible). Deleted 240 directories / 78.6GB of old, already-fully-documented
experiments (the accessProb=0.1/0.025 `bridging_revalidated` series, `hub_secession_experiment`,
`hub_bridging_experiment`, `hub_tier_check_v15_synth` -- all superseded by the "new calibration plan"
config and already written up with real numbers earlier in this document, so per this project's
standing disposability convention nothing was lost). Moved the remaining ~370 directories from
today's session into 7 named folders (`results/2026-07-27_sf1-check-5seed/`,
`..._sf1-confirm-20seed/`, `..._current-config-equilibria/`, `..._bridging-{mid,mega,small}-tier/`,
`results/2026-07-28_removehub-mid-tier/`); `results/` is now 78GB. Also split the previously-shared
`logs/bridgecur_seed*.log` prefix (all three tier scripts had copy-pasted the same log filename,
so the dashboard's run-set picker -- which groups by log prefix, not results folder -- was lumping
mid/mega/small tiers into one mixed group of 300+ seeds) into `bridgecur_{equil,mid,mega,small}_seed`
prefixes; verified via `dashboard.core.log_groups` that the picker now shows 5 clean, correctly-sized
groups. New experiments write directly into their own `results_subdir` from the start rather than
needing a post-hoc move.

**Results, n=10, step 20000, mega and small tiers, vs. the same tier-agnostic control reused
throughout (first 10 of the existing 20 control seeds)**:

| metric | mid (n=20, above) | mega (n=10) | small (n=10) |
|---|---|---|---|
| sf1_ratio | +0.0253, t=0.36 | **+0.1671, t=1.52** (largest point estimate seen all session, still ns) | +0.0259, t=0.20 |
| crossRepostRate | -0.0140, t=-2.90 (sig) | -0.0247, t=-1.42 (ns) | -0.0147, t=-0.99 (ns) |
| postShare bin2 (moderate) | -0.0289, t=-2.44 (sig) | -0.0521, t=-1.07 (ns) | -0.0489, t=-1.09 (ns) |
| disagreement | +0.0044, t=5.57 (sig) | -0.0064, t=-0.84 (ns, sign-flipped) | -0.0020, t=-0.78 (ns) |
| Q_sign_repost | -0.0041, t=-0.84 (ns) | -0.0089, t=-0.93 (ns) | **-0.0178, t=-2.46 (sig)** |
| interactionCrossCuttingFraction | +0.0027, t=0.53 (ns) | +0.0038, t=0.45 (ns) | **+0.0159, t=2.43 (sig)** |

Mega-tier hub counts from these 10 seeds: `[1,8,7,3,0,0,1,7,1,1]` (2/10 zero-hub, consistent with the
full-20-seed derivation reused earlier). Small-tier: `[6,6,2,7,5,6,6,3,5,14]` (no zero-hub seeds).

**Reading, calibrated to the n=10-vs-n=20 comparison explicitly**: point estimates at mega/small are
mostly comparable to or larger than mid-tier's (e.g. postShare bin2: -0.052/-0.049 vs. mid's -0.029),
but significance drops with the halved sample -- consistent with a real, roughly similar-or-larger
effect observed with less power, **not** evidence the effect is smaller at those tiers. This project's
own noise-tolerance lesson (do not read a weaker t-stat under a smaller n as a qualitatively different
result) applies directly here. Two things worth flagging without over-claiming: **mega-tier's
`sf1_ratio` point estimate (+0.167) is the largest across every arm/tier/mechanism tested this entire
session**, consistent with the earlier "hub reach matters more than hub count" reading, but still
short of resolved at t=1.52. **Small-tier turned up two new significant results**
(`Q_sign_repost`, `interactionCrossCuttingFraction`) not seen at mid-tier -- plausible, but with this
many metrics tested at n=10, some hits are expected by chance; treat as leads for a higher-n re-check,
not confirmed findings.

**Bottom line, now resting on four independent causal-manipulation designs (swap/mute_access/
mute_repost/algo_exclude/remove_hub) across three tiers and two configs**: no combination tested so
far produces a significant `sf1_ratio` effect at this operating point. This is not for lack of
trying, and the rollup's conclusion stands.

## 20-seed confirm of the same point (2026-07-27): the n=5 read was noise -- SF1 actually overshoots, and gets worse with more steps

Ran the follow-up (`scripts/confirm_current_config_20seed.py`, seeds 1900000-1900019, same HEAD
config as above, no CLI overrides, `n=1000`, `steps=40000`, metrics read at both checkpoints).
Launched via `nohup ... & disown`, ~35min wall time for all 20 concurrent seeds (`-Xmx2g` each, 20
workers on this machine's 32 cores/120GB RAM -- fine, but noticeably slower per-seed than the 5-seed
batch due to contention; worth remembering for future concurrency choices here). Full log:
`docs/report/current_config_20seed_confirm.csv`.

| step | SF1 ratio (mean+/-std, SEM, n=20) | assort (floor 0.6) | Q_sign_repost (target 0.48) | Gini (target 0.8) |
|---|---|---|---|---|
| 20000 | **1.3236 +/- 0.2860 (SEM 0.0639)** | 0.5954 +/- 0.0673 (SEM 0.0150) -- *below floor* | 0.3965 +/- 0.1024 (SEM 0.0229) | 0.8866 +/- 0.0031 (SEM 0.0007) |
| 40000 | **1.5482 +/- 0.3350 (SEM 0.0749)** | 0.6743 +/- 0.0589 (SEM 0.0132) | 0.4328 +/- 0.0502 (SEM 0.0112) | 0.8866 +/- 0.0031 (SEM 0.0007) |

**Conclusion: the n=5 read reported above was noise, and it pointed the wrong direction.** At n=5,
step 40000 read `1.2334+/-0.2241`, comfortably inside `[1.19,1.26]` and *decreasing* from the step
20000 read (1.2946). At n=20 (real resolving power -- SEM shrinks to ~0.06-0.07, a tight estimate),
the true mean is **1.32 at step 20000, rising to 1.55 at step 40000** -- not converging toward the
target, **diverging above it**, and at step 40000 the 95% CI (`~[1.40,1.69]`) doesn't come close to
touching `[1.19,1.26]`. This is exactly the failure mode this document has warned about repeatedly
(SF1 needs ~85+ seeds / n=5 is noise-dominated) -- this time the noise didn't just widen the
uncertainty, it flipped the qualitative read from "in range" to "clearly overshooting, and getting
worse over time."

**Other stylized facts, now tightly resolved (Gini SEM=0.0007) rather than ambiguous:**
- **Gini = 0.887, a real ~0.087 miss from the 0.8 target** -- not noise, the SEM is far too small for
  that gap to be sampling error.
- **`opinionAssortativity` fails its own 0.6 floor at step 20000** (0.595, SEM 0.015 -- genuinely
  under, not a rounding artifact) and only clears it by step 40000 (0.674) -- the network hasn't
  reached the structural-separation floor this project uses as a validity gate until quite late.
- **`Q_sign_repost` = 0.40 (step 20000) -> 0.43 (step 40000), still short of the 0.48 target** at both
  checkpoints, though moving the right direction with more steps (opposite of SF1's trend).

**Net read: this hand-set point (the "new calibration plan" HEAD config) does not clear the
SF1-prerequisite gate, and is not close on the other three stylized facts either once actually
resolved.** It should not be treated as a calibrated point -- it needs to go back through the same
kind of joint BO search the v1-v15 series used (this document's whole prior history), now specifically
penalizing SF1 for *overshooting* as well as undershooting (the loss functions defined in
`scripts/app_pol_baseline_bo_calibration.py` etc. already do this symmetrically via
`((ratio-RATIO_TARGET)/RATIO_SCALE)**2`, so no code change needed there -- just don't hand-pick a
point without running it back through that search). Also worth carrying forward: **SF1 is still not
plateaued at step 40000** (rising, not flattening) -- any future confirm at this config or a
similar one should keep checking multiple checkpoints rather than trusting a single final-step read,
per this document's standing caution.

## 2026-07-28 -- Design correction: manipulate-at-t0-and-evolve, not manipulate-on-equilibrium

**Everything in the mid/mega/small-tier bridging sections above and the `remove_hub` sections
answers a different causal question than the paper's actual hypothesis.** User's correction, quoted
directly: *"the hypothesis that moderate hubs act as conduit and affect polarization is about the
term of 'evolution' of the NW not the equilibrium state ... what I wanna do as the treatment is to
swap, or exclude the moderate hubs from the initial state and see how dynamics evolve."*

Confirmed by reading `docs/wssit2026-TomoyaTakeda.tex` (the actual WSSIT2026 paper) directly for the
first time this series -- section 4.4 (opinion-leader selection) and 5.2 (Active/Inactive 8-condition
design) pin 3 top-follower nodes' opinions to `{-1,0,+1}` **at t=0 of a freshly generated network**
and run the *entire* evolution (40000 steps) from there; the metric (`postOpinionVar`, final-window)
is read off that full trajectory, not a late-stage perturbation. Every script this week
(`bridging_current_config*.py`, `bridging_current_config_removehub*.py`) instead built a network to
equilibrium (20000 steps) and then applied swap/mute/algo_exclude/remove_hub as a *continuation*
treatment on the already-settled network -- a different, though not meaningless, question ("does
perturbing an already-polarized network change its further trajectory") than the paper's actual one
("does the presence of an active moderate hub from the start change how polarization develops").

**User's request for the extension (not a literal replication of the paper's Active/Inactive design):
keep the same 5 manipulation mechanisms already built this week (swap / mute_access / mute_repost /
algo_exclude / remove_hub), just anchor them at t=0 of a fresh network instead of at an equilibrium
snapshot, and observe the whole trajectory.**

**Mechanism (no Java changes needed):** every one of the 5 existing mechanisms is already a pure
`network=read` + CLI-id-set-token operation. Determinism check (seed 3000000, steps=2000): feeding a
seed's own `GEXF/lambda_0.0/step_0.gexf` back in via `network=read` reproduces that seed's native
`network=hk` run's `results.csv` **bit-for-bit**. Consequence: the already-completed
`2026-07-27_current-config-equilibria` runs (seeds 3000000-3000009, network=hk, steps=20000) are
themselves the correct "no manipulation, full evolution from t0" **control** for this design --
no need to relaunch a control arm at all. Only the 5 manipulation arms need fresh runs.

**Tier redefinition at t0 (important, non-obvious finding):** checked the t0
(`agent_snapshot_t0.csv`) followerCount distribution directly (10 seeds) before reusing the old
mega/mid/small tier boundaries (>500 / 100-500 / 50-100, which were defined against *equilibrium*
followerCount). Result: **the >500 "mega" band is completely empty at t0** -- max followerCount
across 10 fresh seeds is only 423-483. Follower counts above 500 are entirely a product of ~20000
steps of follow/unfollow dynamics (rich-get-richer via the For-You recommender's exposure feedback
loop), not something the raw HK generation produces on its own. So only two tiers are usable at t0,
not three -- matching the user's own suspicion that "third tier may not be explicit," though for the
opposite reason than guessed (it's the *top* band that vanishes at t0, not the bottom one):
  - **top-tier-initial**: followerCount(t0) > 100 (~7.4 moderate hubs/seed, range 5-10)
  - **mid-tier-initial**: followerCount(t0) in (50,100] (~7.0 moderate hubs/seed, range 5-12)

**Design launched (`scripts/initial_state_bridging.py`):** for each of the 2 tiers x 5 arms x 10
seeds (seeds 3000000-3000009 supplying the shared t0 network/hub-list source; new seeds
90[1-5]0000+i for top tier, 91[1-5]0000+i for mid tier), read back that seed's own `step_0.gexf`,
apply the arm's manipulation from t=0, run a full fresh 20000-step simulation, log metrics at every
2000 steps across the whole trajectory (not just an endpoint) into
`docs/report/initial_state_bridging_{top,mid}tier.csv`. Launched in the background
(`nohup ... & disown`, logs under `logs/initstate_seed*.log` and
`logs/initial_state_bridging_{top,mid}.driver.log`) per project convention. 100 total JVM runs;
verified 20 concurrent (`-Xmx2g` each) fit comfortably in available RAM (50GB free at launch) before
scaling up.

**Results (all 5 arms x 2 tiers x 10 seeds complete, SF1 = postOpinionVar/opinionVar, paired t vs.
control by base seed).** Note: `step=0` SF1 reads as a large negative number (~-4.4) for every
arm/tier including control -- an artifact of `postOpinionVar` being near-meaningless before any
posts exist, not a real signal; ignore step 0 throughout.

Headline: **every one of the 5 manipulations, in the top tier, produces a transient, moderately
significant positive bump in SF1 during the network's early formative window (roughly step
2000-6000, occasionally persisting to step 10000), which fades to statistical noise by step 20000.**
No arm shows a significant *final-state* SF1 effect in either tier:

| tier | arm | early-window peak (step, diff, t) | step 20000 (diff, t) |
|---|---|---|---|
| top | swap | step 2000: +0.41, t=+2.22 | -0.12, t=-1.22 |
| top | mute_access | step 2000: +0.50, t=+3.03 | -0.05, t=-0.28 |
| top | mute_repost | (no early bump; dose too small, consistent with 2026-07-27 finding) | -0.06, t=-0.59 |
| top | algo_exclude | step 4000: +0.38, t=+3.22 | +0.14, t=+0.91 |
| top | remove_hub | step 2000: +0.35, t=+2.62 | -0.08, t=-0.59 |
| mid | swap | step 4000: +0.19, t=+2.34 (weak) | +0.08, t=+1.10 |
| mid | mute_access | step 6000: +0.24, t=+1.83 (weak) | -0.04, t=-0.35 |
| mid | mute_repost | (no early bump) | +0.14, t=+0.86 |
| mid | algo_exclude | (no clear early bump) | +0.05, t=+0.27 |
| mid | remove_hub | step 4000/10000: +0.30/+0.26, t=+2.13/+2.00 | +0.10, t=+1.24 |

**Reading this (n=10, hold appropriately loosely):**
- The effect is **front-loaded, not sustained** -- manipulating the moderate hub at t=0 measurably
  accelerates the *early* divergence between what's posted and the underlying population opinion,
  but the unmanipulated control catches up by the time the network settles (~step 12000+). This is
  the opposite temporal shape from the paper's own finding (moderate-leader activity compounds with
  active extremes and *keeps* polarization elevated through 40000 steps) -- worth flagging as a real
  discrepancy between this current, more elaborate model (For-You recommender, graded bc-relaxation,
  repost lineage, etc.) and the original paper's simpler CNNR/Active-Inactive setup, not just noise.
- **`mute_repost` is the one arm with no early bump in either tier** -- consistent with the
  2026-07-21 dose finding (muted hubs carry <1% of total repost volume in this model), reinforcing
  that repost-channel suppression alone is too low-dose to matter; the effect (where it exists) is
  coming from the graph-position/reach channels (mute_access, algo_exclude, remove_hub) and from
  direct opinion reassignment (swap), not from throttling reposting specifically.
- **Top tier > mid tier**, same pattern as every prior tier comparison this week (mega/mid/small on
  the equilibrium design): fewer, larger-reach hubs produce cleaner, more detectable effects than
  many smaller ones, even though the *mechanism* is now anchored at t=0 rather than on an
  equilibrated network.
- **Given none of the 5 mechanisms sustain a significant SF1 effect to the final state**, if the
  paper's claim depends on a *persistent* moderate-hub effect, this current-config point does not yet
  demonstrate it under any of these 5 manipulations -- same standing caveat as the mega/mid/small
  equilibrium-design results above, now confirmed under the methodologically-corrected (t=0,
  full-trajectory) design too. Open question worth deciding with the user next: extend these runs
  past step 20000 (does the early bump ever re-emerge, or was 20000 steps enough to fully wash it
  out?), or treat "front-loaded-then-fades" as itself the finding and adjust the paper's claimed
  mechanism accordingly.

Full per-checkpoint data: `docs/report/initial_state_bridging_toptier.csv`,
`docs/report/initial_state_bridging_midtier.csv`. Dashboard: logs were split from one flat
`initstate_seed*.log` prefix (100 seeds, too heavy to browse) into 10 per-arm-per-tier prefixes
(`initstate_{top,mid}_{swap,mute_access,mute_repost,algo_exclude,remove_hub}_seed*.log`, 10 seeds
each) after the fact -- renaming log files mid-run is safe (open file descriptors track the inode,
not the path) and was verified not to disrupt the still-running `remove_hub` arm.

## 2026-07-28 -- CSS evaluation of the initial-state sweep: what it identifies, and what it doesn't

Re-analysis with trailing-1000-step windowed means (per-step `postShare`/`postOpinionVar` are shares
over a few hundred posts -- instantaneous reads are noise-dominated), SF1 as ratio-of-windowed-means,
paired t + Cohen's dz + minimum detectable effect (MDE, 80% power, alpha=.05, n=10), Holm correction
across the 10 tier x arm families, Pitman-Morgan paired variance tests, and per-seed dose-response.

### 1. The SF1 null is a *decomposition* result, not an absence of effect

Apparent polarization SF1 = postOpinionVar/opinionVar shows **nothing anywhere** -- all 5 arms, both
tiers, both checkpoints, none significant, none close after Holm. But the ratio's two components
**co-move almost exactly proportionally**. Top-tier `swap` at step 10000:

  - `opinionVar`      0.2069 -> 0.2212  (**+6.9%**, t=+2.44, p=.038)
  - `postOpinionVar`  0.2674 -> 0.2855  (**+6.8%**, ns on its own)
  - SF1               1.2801 -> 1.2739  (**-0.5%**, t=-0.05)

So the manipulation **raises the level of polarization (Type 1) and the level of expressed
polarization by the same proportion, leaving the expression *gap* untouched**. This is the single
most useful analytical result in the sweep: **SF1 is the wrong outcome variable for the conduit
hypothesis.** SF1 measures selective *expression* (the vocal-minority gap), which in this model is
governed by the expression machinery (`vocal_comfort_radius`, bc dynamics, `initial_pp`/`pp_relax_eta`)
-- not by where hubs sit in the graph. Reporting "no SF1 effect" as the headline would be reporting
that a thermometer didn't move when we were changing the pressure.

**Power caveat, stated properly:** MDE on SF1 is 0.17-0.44 SF1 units against a control of 1.28-1.48,
i.e. we can only rule out effects larger than **12-30% of the control level**. "Null" here means "no
effect bigger than roughly a quarter of the baseline," not "no effect." Per this document's standing
caution (SF1 needs ~85+ seeds), n=10 cannot resolve SF1 and was never going to.

### 2. The one robust finding is structural (Type 2), and it survived an artifact check

`crossCuttingFraction` is the only metric with Holm-surviving effects, and they **persist to step
20000** rather than fading like the raw-SF1 transient:

| tier/arm | step 10000 | step 20000 | dz |
|---|---|---|---|
| top / swap | -0.0756 (t=-4.13, p_holm=.023) | -0.0510 (t=-4.18, p_holm=.021) | -1.32 |
| top / mute_access | -0.0724 (t=-4.21, p_holm=.023) | -0.0567 (t=-4.78, p_holm=.010) | -1.51 |
| top / remove_hub | -0.0367 (t=-3.09, ns after Holm) | -0.0208 (t=-1.91, ns) | -0.60 |
| top / algo_exclude | -0.0376 (t=-2.59, ns after Holm) | -0.0172 (t=-1.47, ns) | -0.47 |
| top / mute_repost | +0.0212 (ns) | +0.0114 (ns) | +0.37 |

**Artifact check (essential -- nearly invalidated the result).** `Analysis.computeCrossCuttingFraction`
and `computeSignModularity` **exclude agents with |opinion| < 0.2** (the `isModerate` filter, 2026-07-18
Conover-style "undecidable" exclusion). That exclusion is *arm-dependent*: at step 20000, of the 74
treated top-tier hubs, the number sitting **inside** the metric's node set is **74/74 for `swap`**
(forced to |op|=0.9, and carrying 3.70% of all edges), **0/74 for `mute_access`** (frozen moderate,
0.00%), versus **11/74 for control** (1.20%). The two arms with the largest measured effect are
exactly the two whose metric membership deviates most from control -- i.e. the headline result was a
prime candidate for being a pure measurement artifact.

Recomputed at step 20000 from the step-20000 GEXF with the treated hub ids **excluded in every arm
including control** (common, treatment-independent node set):

| arm | as-measured | harmonized | vs harmonized control (0.1712) | t | p_holm |
|---|---|---|---|---|---|
| swap | 0.1259 | 0.1336 | **-0.0376** | -3.34 | **.035** |
| mute_access | 0.1220 | 0.1220 | **-0.0491** | -4.33 | **.0095** |
| remove_hub | 0.1525 | 0.1525 | -0.0187 | -1.93 | .257 |
| algo_exclude | 0.1592 | 0.1548 | -0.0163 | -1.34 | .425 |
| mute_repost | 0.1888 | 0.1848 | +0.0136 | +1.32 | .425 |

**The effect survives.** `swap`'s magnitude was inflated ~24% by the membership change (-0.0495 ->
-0.0376); `mute_access` was essentially unaffected. Both still survive Holm. **Any future write-up
of a sign-based camp metric (Q_sign, Q_sign_repost, crossCuttingFraction,
interactionCrossCuttingFraction) under a manipulation that changes hub opinions must harmonize the
node set first** -- `swap` in particular is structurally incapable of a clean read on these metrics
without it.

### 3. Direction: this *reverses* the paper's sign -- but the design omits the moderating factor

Neutralizing the moderate hub (`mute_access`) or converting it to an extreme (`swap`) makes the
network **more** structurally segregated (cross-cutting ties down 22-29% relative). The WSSIT2026
claim is the opposite: moderate-leader *activity* **worsens** polarization, so silencing it should
*reduce* segregation.

**This is not (yet) a refutation.** The paper's result is an **interaction**: comparing (A,A,A) vs
(A,I,A) -- both extremes Active -- the neutral leader's activity worsens polarization; but comparing
(I,I,I) vs (I,A,I) -- extremes Inactive -- it does not. **Every run in this sweep had `ext=NONE,
nmod=0`** (confirmed in every log: `[InterventionSetup] ... -> 0 hubs intervened.`) -- there are no
pinned extreme leaders at all, only an organically-evolving population. So this sweep sits in the
paper's *extremes-absent* cell, exactly the cell where the paper itself reports no significant
neutral-leader effect. **The design is an under-specified replication that omits the moderating
variable the hypothesis depends on.**

### 4. Causal status of each claim (what the design does and does not license)

**Strong.** Treatment assignment is perfectly matched on initial conditions: every arm reads the
same seed's `step_0.gexf`, and the round-trip was verified bit-for-bit exact. There is no
confounding by initial network or initial opinion distribution -- a genuinely clean matched design,
stronger than most observational CSS work on broker roles.

**Weakened by a fixable flaw -- no common random numbers.** `rand/randomGenerator.java` seeds the
dynamics stream from the *run* seed (`dynamicsRand = new Random(seed)`). Arms used seeds 90x/91x
while control used 3000000+i, so **control and treatment differ in their entire stochastic
trajectory, not only in the manipulation.** The paired estimator is still *unbiased* (streams are
exchangeable across seeds), but it carries full trajectory noise instead of isolating the treatment
-- which is precisely why MDE is 12-30% of baseline. The class doc for `network()` even flags the
intended pattern ("seeded by net_seed ... so the initial graph can be held fixed while dynamics noise
varies"). **Fix: run each arm at the *same* `seed` as its control, using `results_subdir` to avoid
the folder-name collision.** This is a variance-reduction change, not a validity fix, and should
sharply cut MDE at no extra compute.

**Not established -- dose-response.** Per-seed hub counts vary 5-10 (top) and 5-12 (mid), giving a
natural dose gradient. Correlations between per-seed hub count and per-seed effect are mostly
|r| < 0.63 (the n=10 significance threshold) and inconsistent in sign across metrics. **No
dose-response relationship is demonstrated**, which materially limits the causal claim -- a genuine
structural mechanism should scale with the number of bridges removed.

**Not established -- canalization.** Pitman-Morgan paired variance tests scatter around p<.05 at
roughly the rate expected by chance across ~140 tests. The apparent "treatments have smaller SEM"
pattern in the raw table does **not** survive testing. Do not claim it.

**Compositional-data caveat.** `postShare_0..4` sum to 1, so "extreme down / pre-extreme up" is
partly mechanical -- the mass must go somewhere, and the components are not independent. The
observed pattern (top-tier `swap`/`mute_access`/`remove_hub` shift mass from extreme into
pre-extreme bins) should be re-tested on additive-log-ratio-transformed coordinates before any claim
is made from it.

### 5. The mechanism the data *suggests* (hypothesis, not a result)

Ranking by harmonized effect: `mute_access` (-0.049) ~ `swap` (-0.038) >> `remove_hub` (-0.019) >
`algo_exclude` (-0.016) > `mute_repost` (+0.014). The two large effects are the two arms that
**leave a high-degree node occupying its bridging position while disabling its bridging function**
(`swap`: still posts, but extreme; `mute_access`: still posts, but never absorbs or relays).
`remove_hub` -- which *vacates* the position -- is markedly weaker.

That ordering suggests **it is not the hub's presence that matters but a bridging position held
without the bridging being performed**: a vacated position lets the network rewire around it and
partially restore cross-cutting contact, whereas an occupied-but-non-functional position forecloses
that substitution. This is the structural-holes / broker-failure intuition (Burt), and if it holds it
is a more interesting claim than the original conduit story -- but it is **generated post hoc from 5
arms at n=10 and is not tested.** Direct test: in the `remove_hub` arm, measure whether the orphaned
followers re-attach to *other* moderate agents (substitution) at a higher rate than in `mute_access`.
That analysis needs only the runs already on disk.

`mute_repost` is null or reversed on essentially every metric, consistent with the 2026-07-21 dose
finding (<1% of repost volume) -- it remains an under-dosed arm and should not be read as evidence
about the repost channel.

### 6. Recommended next experiment (do not run before agreeing the design)

1. **Add the extreme-leader factor** -- the missing moderating variable. `InterventionSetup` already
   supports it: `ext=SYM` (pin +-1 leaders by initial follower rank) x `nmod=1..k` x moderate-arm.
   Minimum viable factorial: {ext=NONE, ext=SYM} x {control, mute_access, swap, remove_hub}. This is
   the design that actually tests the paper's interaction claim, and it is the only way the
   direction conflict in section 3 can be resolved.
2. **Common random numbers** (same seed for control and arms, separated by `results_subdir`).
3. **Run to 40000 steps.** SF1 is still rising at 20000 (control 1.28 -> 1.48; the earlier 20-seed
   confirm reached 1.55 at 40000), so the system is *not* stationary and "the effect fades by 20000"
   is a statement about a non-equilibrium trajectory, not about the attractor.
4. **Primary outcome = harmonized `crossCuttingFraction` and `Q_sign_repost`, not SF1.** Per section 1,
   SF1 is structurally insensitive to this manipulation class; keep it as a reported secondary.
5. Raise n once (2) lands -- CRN should make n=10-20 adequate for the structural metrics; SF1 would
   still need ~85+ and is not worth chasing at this stage.

## 2026-07-28 -- Cross-seed dose-response: t=0 hub composition vs. realized polarization

Complementary analysis to the manipulation sweep: instead of intervening, exploit the **natural
variation across seeds** in how many/what kind of moderate hubs the initial network happens to
contain, and correlate that with realized polarization. Run on the **20** completed control-arm
equilibria (seeds 3000000-3000019, `network=hk`, unmanipulated), outcomes at step 20000 with
trailing-1000-step means, Spearman rank correlations.

**Why this is closer to a randomized dose experiment than to observational data:** opinions are drawn
i.i.d. Gaussian and the HK graph is generated independently, so the moderate-hub composition a seed
produces is **assigned by the RNG**, not selected by any process that also drives the outcome. The
"dose" is effectively randomly allocated. This is a genuinely stronger identification position than
the usual observational broker-role literature, and it is free -- the runs already exist.

### Headline: a clean dissociation between two independent channels

**Extreme reach at t=0 predicts *real* polarization (Type 1 and Type 2).** `reach_ext_top` (share of
total follower mass held by |op|>=0.6 hubs with >100 followers) hits raw p<.05 on **7 of 8** outcomes,
all in the coherent direction: `opinionVar` +0.55, `postOpinionVar` +0.51, `opinionAssortativity`
+0.61, `Q_sign_repost` +0.46, `bimodalityCoeff` +0.54, `postShare_extreme` +0.45, and
`crossCuttingFraction` **-0.48** (segregation up). `n_ext_top` -> `opinionAssortativity` is +0.68.

**Moderate reach at t=0 predicts *apparent* polarization -- and nothing else.**

| predictor | SF1 | postShare_extreme | opinionVar | crossCuttingFrac | Q_sign_repost |
|---|---|---|---|---|---|
| `reach_mod_all` (all moderates' follower-mass share) | **+0.53** | **+0.50** | +0.22 | +0.31 | +0.14 |
| `mod_pop_share` (moderate head-count share) | **+0.48** | +0.34 | +0.11 | +0.08 | +0.09 |
| `reach_mod_top` (top-tier moderate hubs only) | +0.44 | +0.42 | +0.19 | +0.37 | +0.11 |
| `n_mod_top` (**count**, not reach) | +0.24 | +0.23 | +0.15 | +0.17 | +0.13 |

So, answering the question directly: **apparent polarization gets *worse* with *more* moderate
reach** (rho=+0.53) -- the conduit-hypothesis direction. And again **reach predicts, raw count does
not** (+0.53 vs +0.24), the same reach-beats-count pattern found in every tier comparison this week.

**Two confounds checked and cleared:**
- *Compositional coupling* -- feared that "more moderates" mechanically means "fewer extremes."
  It does not: **rho(`reach_mod_all`, `reach_ext_top`) = -0.01** (p=.98). The two channels are
  statistically independent across seeds, so they are genuinely separable, and partial correlations
  controlling for extreme reach barely move (SF1 +0.53 -> +0.51; postShare_extreme +0.50 -> **+0.60**).
- *Denominator deflation* -- SF1 is a ratio, so a smaller `opinionVar` would inflate it artificially.
  Not the driver: `reach_mod_all` -> `opinionVar` is +0.22 (ns) while -> `postOpinionVar` is +0.43.
  **The numerator moves; the denominator does not.** More moderate reach means more extreme-skewed
  *content*, not a less polarized *population*.

### Statistical honesty: this does NOT survive strict multiple-comparison correction

Benjamini-Hochberg FDR across all 64 control-table tests leaves **exactly one** cell at q<0.10
(`n_ext_top` -> `opinionAssortativity`, rho=+0.68, raw p=.0011, q=.070). The moderate-reach -> SF1
result (raw p=.016) **does not survive** FDR-across-64.

Both framings are defensible and both should be stated:
- As **one of 64 exploratory cells**: not significant after correction. Do not report as a finding.
- As a **pre-specified primary hypothesis** -- which the conduit hypothesis licenses, since
  "moderate reach raises apparent polarization" is exactly the paper's a-priori claim -- it is a
  legitimate confirmatory test at rho=+0.53, **p=.016**, n=20.

The honest position: this is a **coherent, directionally-predicted, confound-checked pattern that is
suggestive but not yet established**. It is worth a pre-registered confirmatory test on fresh seeds
(the analysis is nearly free -- it only needs unmanipulated runs), and should not be written into
the paper as a result until that test is run.

The within-arm version of the same analysis (n=10 per treatment arm) shows **nothing** -- all
|rho| < 0.632. Underpowered as expected; do not report.

### This resolves the apparent conflict with the manipulation sweep

The correlational result (more moderate reach -> higher SF1) and the experimental result (removing
top-tier moderate hubs -> no SF1 change) look contradictory but are consistent:
1. The experiment only manipulated **top-tier moderate hubs** (`reach_mod_top` ~ 0.133 of follower
   mass); the correlational signal is carried by **all** moderate reach (`reach_mod_all` ~ 0.269),
   most of which the experiment never touched -- and note `reach_mod_top` alone gives the weaker
   +0.44.
2. The implied effect size is **~0.14 SF1 units per 1 sd of moderate reach**, which is *below* the
   experiment's MDE of 0.17-0.44. **The experiment was underpowered to detect the effect the
   correlation implies** -- the null was a power failure, not evidence of absence.

This yields a concrete power calculation for the next round: to detect ~0.14 SF1 units at the
sweep's observed sd_diff (~0.24) needs **n ~ 23** without common random numbers; with CRN (section 4
above) the paired noise should fall far enough that n=10-20 suffices.

### Converging evidence on the structural channel

Two methodologically independent analyses agree on sign:
- **Experimental:** neutralizing a top-tier moderate hub -> `crossCuttingFraction` **down**
  (-0.038 to -0.049, Holm-surviving after node-set harmonization).
- **Correlational:** more moderate reach -> `crossCuttingFraction` **up** (+0.31 to +0.42, ns).

Both say **moderate hubs are structurally integrative**. Combined with the correlational finding that
they simultaneously raise `postShare_extreme` (+0.50, partial +0.60), the emerging picture is that
**moderate hubs hold the network together across camps *and* are the channel through which extreme
content crosses between camps -- the bridge and the contagion are the same edge set.** That is a
sharper and more interesting formulation of the conduit hypothesis than "moderates worsen
polarization," it reconciles the sign conflict with WSSIT2026 in section 3 above, and it makes a
falsifiable prediction: **the cross-camp content that reaches a given agent should be
disproportionately routed through moderate-hub relays.** That is directly measurable from the repost
lineage already recorded in `Post` (`rootPostId`/`parentPostId`/`relayerId`/`depth`) on runs already
on disk -- and it is the single highest-value next analysis, because it tests the mechanism directly
rather than inferring it from aggregate correlations.

## 2026-07-28 -- Evolution/replacement check, and a three-tier intervention design (ID/Role/Adaptive)

User's concern: the model evolves for 20000 steps after any t0 manipulation, so even a fully successful
removal of a moderate-hub class could be undone if *other* agents grow into that structural role during
the run -- a t0-only intervention can't distinguish "the manipulation didn't matter" from "the manipulation
mattered but the network regenerated an equivalent replacement."

**Checked directly on already-completed top/mid-tier runs (no new compute).** Strict moderate-hub-class
reach (|op|<0.2, fc>100) at step 20000: control 13.47% (8.5 hubs, 2.7 new-since-t0 -- some background
churn even untreated) vs. **swap 2.67%** (2.2 hubs) and **remove_hub 1.83%** (1.4 hubs) -- collapsed, not
refilled in-kind. `mute_access` shows partial persistence instead (10.99%, milder manipulation, milder
effect). Mid-tier band (50-100 followers) shows heavy churn even in control (many mid-tier hubs simply
grow past fc=100 and "graduate" into top tier over 20000 steps) -- the band itself is transitional, not
a stable position, which is a separate and important caveat about using fixed absolute-follower-count
tier boundaries measured at a single point in time.

**But checking a *looser* band reveals the real story: role migration, not no-replacement.**
Near-moderate reach (0.2<=|op|<0.4, fc>100) at step 20000: control 21.62% (10.8 agents) vs.
**swap 25.49%** and **remove_hub 25.32%** -- both *higher* than control. So removing/converting the
strict moderates does not leave the bridging position empty -- it gets reoccupied by milder partisans
just outside the classification boundary. This is very plausibly part of why the crossCuttingFraction/
SF1 effects were modest rather than dramatic despite near-total elimination of the targeted class, and
it is direct, measured evidence for the user's concern, just in a more specific form (band-shift
substitution, not same-band regrowth).

### Proposed fix: a three-tier intervention design (user's proposal, not yet implemented)

Nested hierarchy of what's held fixed across the design, each removing one further assumption:

| design | what's fixed | causal question |
|---|---|---|
| **ID intervention** (this week's entire sweep) | specific agent ids, one-shot at t0 | "are *these agents* important?" |
| **Role intervention** | a band criterion (e.g. 10<=followers<50), re-evaluated and re-suppressed every rescan | "is *this role* important?" |
| **Adaptive intervention** | only an aggregate quantity (e.g. always remove enough reach to eliminate 13%), criterion not fixed at all | "is *this structural function* important?" |

Interpretive logic: ID-null with Role/Adaptive-positive -> the moderate *function* matters, not the
specific initial cohort (a purely ecological/niche claim). All three positive -> the initial cohort
carries some idiosyncratic importance beyond generically filling the niche (plausible path-dependence,
e.g. via who else they happened to be connected to at t0). This is a genuine capability an ABM has that
a real social experiment does not -- continuously intervening on a functional role, not just on named
individuals, is not something a field experiment could ever do.

**Key framing (user's own caveat, and correct):** Role/Adaptive suppress the substitution dynamic *by
construction*, so they cannot show *how* the network compensates -- only ID intervention can, and the
migration finding above is exactly that: ID intervention is simultaneously "the causal-effect-of-these-
agents" arm and "the natural-adaptation-dynamics" arm. Frame as complementary in the writeup: ID =
one-shot perturbation (reveals adaptation), Role/Adaptive = persistent suppression (reveals whether the
function is load-bearing) -- not competing designs answering the same question.

**Implementation, not yet built.** Role/Adaptive both need a re-scan-and-resuppress mechanism (identify
current qualifiers, suppress; release agents who no longer qualify) that does not exist yet. Two paths:
(1) Java-native, re-evaluated every N steps inside `evolve()` -- true continuous suppression, fine
granularity, requires new code. (2) Checkpoint-restart in Python -- run K steps, snapshot, re-identify
qualifiers, relaunch via `network=read` with an updated `mute_access_ids` list -- reuses everything
already built, no Java change, but only as fine-grained as the checkpoint interval K. Plan: start with
(2) at a moderate interval (~2000 steps) as an approximation; only build (1) if within-window churn (a
directly checkable property of `agent_snapshot` data already on disk) turns out too fast for that
approximation to hold. Open design question before building: for Adaptive, should the reach-ranked
selection pool stay restricted to moderate-opinion agents (re-evaluated each rescan, since opinion also
drifts) -- yes, otherwise Adaptive stops testing the moderate-reach hypothesis and starts testing
"does removing 13% of any agent's reach matter," a different question. **Not yet launched -- awaiting
confirmation on (a) checkpoint-restart vs. Java-native, and (b) rescan interval.**

## 2026-07-28 -- n=100 control-seed re-check: the SF1 correlation was noise; the structural one is real

Extended the control-equilibria pool from 20 to 100 seeds (3000020-3000099, same current-config point,
`2026-07-27_current-config-equilibria` subdir) specifically to re-test the n=20 dose-response findings
above at real power (|rho|>.197 at p<.05, vs. .444 at n=20).

**Retraction: the moderate-reach -> SF1 correlation does not replicate.** `reach_mod_all` -> `sf1_ratio`
was +0.53 (p=.016) at n=20; at n=100 it is **-0.02 (n.s.)**. Same for `postShare_extreme` (+0.50 -> +0.14
n.s.). This is exactly the outcome the FDR-non-survival at n=20 was warning about, now empirically
confirmed rather than just statistically flagged. **Do not carry the "moderate reach raises apparent
polarization" framing into the paper** -- it was a low-n false positive.

**Retraction: the "small follower-band (10-50) carries independent signal" finding does not replicate.**
Partial correlation of that band's reach vs. SF1 controlling for top-tier reach was +0.41 at n=20 (the
finding that motivated calling the mid/small tier boundaries into question); at n=100 it is **-0.007**.
Also noise.

**Retraction: "moderate reach and extreme reach are statistically independent across seeds" was wrong.**
Stated at n=20 as rho=-0.01 (p=.98); at n=100, **rho=-0.335 (p=.0007)** -- a real, moderate-strength
negative coupling (more moderate reach at t0 tends to co-occur with less extreme reach), which n=20 was
underpowered to detect. Any future partial-correlation analysis on this dataset must control for this.

**What DOES replicate and survives strict correction:** `reach_mod_all` -> `crossCuttingFraction`
(+0.511), -> `opinionAssortativity` (-0.324), -> `bimodalityCoeff` (-0.332) -- all survive BH-FDR across
the full 80-cell table (q<=0.006), and **all survive partial correlation controlling for the newly-found
extreme-reach coupling** (crossCuttingFraction partial rho=+0.462, p<.00001; assortativity -0.215,
p=.032; bimodality -0.277, p=.005). This is now a robust, independently-confirmed finding, and it
**converges with the experimental result** from the manipulation sweep (removing a moderate hub ->
crossCuttingFraction down, Holm-surviving after node-set harmonization, section "the one robust finding
is structural" above). Correlational and experimental evidence now agree specifically on this channel.

Separately, `reach_ext_top` robustly predicts both real polarization (opinionVar, opinionAssortativity,
Q_sign_repost, bimodalityCoeff -- all survive FDR) **and now also SF1 itself** (+0.320, survives FDR) --
at proper power, it is *extreme* reach, not *moderate* reach, that predicts apparent polarization.

**Consequence for the planned Java-native Role/Adaptive experiment:** the correlational motivation for
targeting SF1 has evaporated. What survives at full power and converges with the ID-intervention
experimental result is the crossCuttingFraction/structural-integration channel. **Recommend retargeting
the Role/Adaptive design's primary outcome to `crossCuttingFraction`/`opinionAssortativity`/
`bimodalityCoeff`, not SF1**, before locking in the requirement decision -- this is the mechanism with
both correlational and experimental support, and continuing to optimize a design around SF1 would be
chasing a correlation that a 5x larger sample already killed. Awaiting user confirmation on this
retargeting before proceeding to Java-native experiment requirements.

## 2026-07-28 -- Trajectory check: moderate-reach correlations are front-loaded and decay; extreme-reach's don't

Same n=100 control pool, same predictors, checked at steps 5000/10000/20000 (the only steps
`modularity.csv` logs) instead of only at 20000.

**`reach_mod_all` correlations are strongest early and decay monotonically:**

| metric | step 5000 | step 10000 | step 20000 |
|---|---|---|---|
| crossCuttingFraction | +0.720 | +0.647 | +0.511 |
| opinionAssortativity | -0.573 | -0.372 | -0.324 |
| bimodalityCoeff | -0.605 | -0.461 | -0.332 |
| Q_sign_repost | -0.428 | -0.328 | -0.101 (n.s.) |
| sf1_ratio | **-0.535** | -0.164 (n.s.) | -0.018 (n.s.) |

The SF1 null reported at step 20000 is the *endpoint of a decay*, not an absence of relationship: at
step 5000, moderate reach -> SF1 is -0.535 (p<.0001). Note the **sign is negative throughout** -- more
moderate reach means *less* apparent polarization early on, the opposite direction from the conduit
hypothesis, fading to zero rather than ever turning positive. Correct framing: "a transient dampening
effect that the network's own dynamics erase," not "no effect."

**`reach_ext_top` correlations are stable or strengthen over the same window** (crossCuttingFraction
-0.308->-0.390, opinionAssortativity ~stable ~+0.50, bimodalityCoeff +0.224->+0.312, Q_sign_repost
+0.302->+0.406, sf1_ratio +0.229->+0.320). Since both predictors are measured on the same seeds at the
same checkpoints, this rules out a generic "late-step correlations are noisier" artifact -- only the
moderate-reach column decays, so this is a real, specific asymmetry: **the network's endogenous
dynamics increasingly erase the initial-condition dependency on t0 moderate reach, while the t0
extreme-reach dependency persists or compounds instead.**

**Converges with everything else found today:** this is the same "front-loaded, fades" shape as the
ID-intervention manipulation sweep's SF1/ccf results, and is mechanistically consistent with the
band-migration finding (near-moderates structurally replacing suppressed strict-moderates over the
run) -- three independent lines of evidence (experimental sweep, this trajectory check, the migration
mechanism) now agree that moderate reach's influence is real but transient and gets structurally
eroded, not merely small or absent.

**Design implication:** the planned Java-native Role/Adaptive experiment should make **early-window
(~step 5000) crossCuttingFraction/Q_sign_repost/SF1 a co-primary outcome alongside step 20000**, not
an afterthought -- per this check, the effect being isolated causally is largest early and gets eroded
by the very dynamics the experiment studies, so a design that only reports the final state risks
measuring the tail end of an already-decayed signal.

## 2026-07-28 -- SF1's own ratio structure confounds it; postShare_extreme is share-diluted (checked, clean)

User's concern: both `postShare_extreme` and `sf1_ratio` could mechanically respond to *how many*
moderate/extreme agents exist, independent of any actual behavioral change in extremists -- i.e. "more
moderate agents post, more moderate posts exist, diluting everyone else's share/variance contribution
by pure arithmetic," not because extremists changed what they do.

**`postShare_extreme`: confirmed mechanism, but checked and clean.** `Analysis.java` line 596:
`postShareArray[i] /= total` where `total` = whole-population post count that step, not normalized by
bin population -- so the share-dilution mechanism the user describes is real in the code. Tested
directly: extreme agents' **per-capita** post rate (extreme-bin posts per step / count of |op|>=0.6
agents at t0) vs `reach_mod_all`, all three checkpoints: +0.056/+0.158/+0.181, **none significant**
(best case p=.071). Extremists' own posting behavior does not measurably change with moderate reach.
The raw `postShare_extreme` correlation was already null at n=100 (retracted two entries above), and
this confirms there is no per-capita behavioral signal hiding underneath a share-dilution artifact
either -- it is just null, cleanly.

**`sf1_ratio`: same concern, different and more structural mechanism.** SF1 = postOpinionVar/opinionVar
is a *ratio*, not a share, so the fix isn't a per-capita transform -- it's checking the numerator and
denominator separately. Both shrink as `reach_mod_all` increases, at every checkpoint, but at
**different and shifting relative rates**:

| step | reach -> opinionVar (denom) | reach -> postOpinionVar (numer) | net effect on the ratio |
|---|---|---|---|
| 5000 | -0.442 | **-0.544** | numerator shrinks faster -> SF1 net down (matches the -0.535 raw finding) |
| 10000 | -0.354 | -0.249 | rates converging -> SF1 flattening toward null |
| 20000 | -0.257 | -0.128 (n.s.) | denominator shrinks faster, numerator ~flat -> SF1 net ~0, mechanically |

The step-20000 "null" reported two entries above is a **near-cancellation between two unequal-magnitude
negative correlations**, not two opposing real effects -- `postOpinionVar`'s own correlation with reach
at step 20000 is not even significant alone (p=.203). Important to state precisely: this does **not**
mean there is a hidden/masked positive "conduit" effect waiting to be unmasked by adjustment (an earlier
partial-correlation check, controlling SF1 for opinionVar, produced a positive residual at step 20000 --
that is a mechanical consequence of the ratio's arithmetic when the denominator's shrinkage dominates a
statistically-flat numerator, not evidence of a distinct suppressed behavioral phenomenon; do not carry
that "unmasked positive effect" framing forward).

**Consequence -- extending the earlier retargeting recommendation:** report `opinionVar` and
`postOpinionVar` **separately** as outcomes for the Java-native experiment, not their ratio SF1. Both
individually show a clean, robust, monotonic-in-time relationship with moderate reach (both shrink,
consistent with the crossCuttingFraction/assortativity/bimodality integration finding already
established as the paper's most solid result). SF1 is compositionally entangled through both its terms
in a way that shifts unpredictably over the trajectory, making it a poor primary causal readout
regardless of whether an underlying effect is real -- this is a stronger and more specific reason to
drop it from the primary outcome set than "it doesn't correlate," and should be the final word on SF1
for this experimental line unless a future design specifically decomposes it into its two components
rather than reporting the ratio.

## 2026-07-28 -- The clean result: pre-extreme per-capita post rate, not extreme, carries the effect

User's sharper correction to the above: reporting `opinionVar`/`postOpinionVar` separately does not
fix the composition problem -- **both are still mechanically smaller whenever more moderate agents
exist**, for the same reason `postShare` was. The only way to actually isolate behavior from
composition is a genuine per-capita rate: `(posts originating from class X) / (count of agents in
class X)`, for both extreme and pre-extreme classes, not a population-level variance or share at all.

**Extreme (|op|>=0.6) per-capita post rate vs `reach_mod_all`: null throughout** (+0.056/+0.158/+0.181,
none significant, best p=.071) -- confirms the earlier per-capita extreme check. Strict extremists do
not change their individual posting behavior as a function of moderate reach, at any point in the
trajectory.

**Pre-extreme (0.2<=|op|<0.6) per-capita post rate vs `reach_mod_all`: strong, robust, and does NOT
decay** -- **-0.654 (step 5000), -0.621 (step 10000), -0.529 (step 20000)**, all p<.0001. This is the
single cleanest and strongest result in the entire investigation. Confirmed non-compositional: the
*count* of pre-extreme agents itself barely correlates with moderate reach (rho=-0.079, n.s., mean 465
agents), so this is a genuine per-capita behavioral signal, not a denominator artifact.

**Reframing:** the effect is not "moderates suppress extremists" -- extremists are unmoved. It is
**"moderate reach reduces the individual vocal activity of the mildly-partisan (pre-extreme)
population specifically."** This is plausibly connected to the model's bc/vocal-comfort mechanics
(pre-extreme agents are still within bc-tolerance range of moderate content in a way full extremists,
whose bc has decayed further, are not) rather than anything acting on extremists directly -- worth
checking against the actual post-probability/`vocalComfortRadius` code before asserting the mechanism,
but it is now a concrete, testable hypothesis rather than a guess.

**Consequence for outcome selection:** pre-extreme per-capita post rate should be a **primary** outcome
for the Java-native experiment, not a footnote -- it is the only outcome checked so far that is both
robust (survives to n=100), non-compositional (confirmed via the class-count check), and persistent
across the whole trajectory rather than decaying. Extreme per-capita post rate should still be reported
alongside it precisely because it is null -- the contrast (pre-extreme moves, extreme does not) is
itself the finding, and reporting only one class would lose that.

## 2026-07-30 -- Structural finding: `remove_hub`'s effect is NOT via "upstream" reach loss -- the network's largest hubs are mutually-redundant seed-clique members

User's question, following yesterday's directed-BFS verification (`docs/report/2026-07-29-feed-reach-
redesign.md`): does removing a large hub meaningfully cut its followers off from "upstream" content --
i.e., posts from accounts the hub itself follows, that a follower could only reach *through* the hub?
This is the literal mechanism the `remove_hub`/`algo_exclude` line of experiments above is meant to be
testing (the "conduit"/bridging framing), so it deserved a direct structural check rather than assumed.

**Method**: a standalone harness (`network.NetworkFactory` + `AdminOptim`, no dynamics loop --
followees-graph only) dumped the raw follow adjacency for the current default network (`network=hk,
hk_m=15, hk_a=4, hk_pt=0.05, n=1000`), then ran the exact `computeReachable` BFS (followees-only,
depth-capped) from every direct follower of the top-`followerCount` hub, with vs. without that hub
node (edges severed both directions, matching `remove_hub`'s actual mechanism exactly). Checked at
`hop` = 1 through 5.

**Result: every single direct follower loses exactly 1 reachable node -- the hub itself -- no more,
at every hop depth tested (1-5), with zero variance across 483 followers** (min=max=mean=1.00 lost).
Relative reach loss shrinks with hop (6.7% at hop=1 down to 1.45% at hop=5, since the reachable set
itself grows with hop while the fixed loss of "1" stays constant). Confirmed not an artifact of one
node or one network draw: identical result (mean_lost=1.000, min=max=1) for the 2nd-largest hub on the
same network, and for the top-2 hubs on an independently-generated network (different seed).

**Root cause, found by inspecting the hub's own followee list**: every top hub's `followeeCount=15`
(exactly `hk_m`), and its followees are literally the network generator's **m=15 seed clique**
(agent IDs 0-15, the Holme-Kim/Barabasi-Albert founder nodes that exist from step 0 of network growth)
-- a well-known founder-effect artifact of BA-family preferential-attachment generators, not specific
to this codebase. Each seed-clique member independently has ~350-470 followers itself (vs. the
population median of 2), i.e., the "upstream" content behind any single removed hub is itself a
*small set of near-universally-followed super-hubs*, redundantly reachable from virtually anywhere in
the graph within a couple of hops regardless of which single hub is removed.

**Consequence for interpreting `remove_hub`'s existing results (`crossRepostRate`/`postShare`/
`disagreement` moving significantly, `sf1_ratio` not, sections above)**: those effects cannot be
coming from an "upstream reach cutoff" channel, since that channel contributes essentially nothing
(loss = 1 node, always) -- they must be attributable entirely to the **first-order loss of the hub's
own authored/reposted content and behavior** (the hub no longer posts, reposts, or is visible itself),
not to any second-order bridging/gatekeeping effect on what its followers can still discover elsewhere.
This is a real, useful narrowing of what `remove_hub` is actually measuring, not a change to the
results themselves.

**Open flag for the paper's construct validity, not yet resolved**: if "moderate conduit"/"repost-hub"
is meant to model a realistic platform influencer, this founder-clique redundancy is a potential
mismatch -- real influencer removal (e.g., deplatforming) can genuinely cut off unique-audience access
in a way this network topology structurally cannot reproduce for its largest nodes, because the
Holme-Kim generator's seed clique is not a realistic stand-in for a single influencer (it's a small,
mutually-redundant hub *cluster*, and every top-`followerCount` node this project has been calling
"the hub" is a member of it, not a singular bridging node). Worth deciding whether hub-removal
experiments should instead target a node explicitly constructed to be a *non-redundant* bridge (e.g.,
a moderate agent connecting two otherwise-sparsely-connected opinion clusters, verified by an
articulation-point/low-alternate-path check like this one) rather than simply the highest-in-degree
node, if the paper's claim depends on a genuine single-point-of-failure conduit role. Not decided here
-- flagging for the next design discussion, since it bears on hub-selection strategy
(`sizeStrategy`/`InterventionSetup`) across this whole experimental line, not just `remove_hub`.

**Follow-up spot-check (2026-07-30, same day): founders vs. same-degree non-founders on betweenness/
PageRank/clustering.** One fresh full run (seed 8802001, n=1000, steps=20000, current provisional feed
point, `log_gexf=true` for the full adjacency), pooled agents with `50 < followerCount <= 500` (n=37:
17 founder-ID<30, 20 non-founder), regressed each `networkx` metric on `log(followerCount)` to control
for size, compared residuals. **Not statistically significant at this n** (Mann-Whitney p=0.21-0.53 --
a spot-check, not a powered test) but directionally coherent with the reachability finding above:
founders have *higher* PageRank than same-degree non-founders (raw means 0.0183 vs 0.0016 -- the clique
mutually reinforces its own rank) but *lower*, not higher, betweenness (0.000165 vs 0.000288) -- the
signature of a mutually-redundant high-visibility cluster, not a structural bridge/cut-vertex. Consistent
with, not independent confirmation of, the uniform-reachability-loss result; would need a properly
powered version (more seeds and/or all 5 tiers pooled) before citing as a standalone finding.

## 2026-07-30 -- Phase 1: `remove_hub` re-validated under the current mechanism, 5 tiers

`scripts/moderate_hub_5tier_removehub.py`. Two-phase design (fresh 20000-step equilibria under the
current, post-2026-07-29 feed mechanism -- provisional point hop=4/exp/lambda=0.11/alpha=0.7/tau=30,
NOT the final calibration -- then 20000-step continuations), n=10 seeds/arm, one shared `control` +
5 tier-specific `remove_hub` arms: mega (>500 followers), middle (100-500), small (50-100),
grassroot (10-50), peripheral (0-10), all `|opinion|<0.2`. Checkpoints 5000 and 20000 (continuation-
relative). Outcome tiering (user, 2026-07-30): primary = pre-extreme AND extreme per-capita post rate
(windowed, 1000-step trailing, per the 2026-07-29 v7 fix); secondary = sf1_ratio, opinionAssortativity;
tertiary = crossCuttingFraction, bimodalityCoeff (user's framing: these are the "easy to predict"
outcomes, deprioritized on purpose). Full log: `docs/report/moderate_hub_5tier_removehub.csv`.

**opinionAssortativity (secondary): the one clean, robust, and *persistent* signal.** Significant in
4/5 tiers, roughly U-shaped across tier size (mega t=2.01, middle t=3.58, small t=1.86 n.s., grassroot
t=5.42, peripheral t=7.12, all at step 20000) -- removing moderates, whether a handful of big hubs or
~170 tiny peripheral ones, reliably makes the network more segregated. **Unlike the earlier
correlational trajectory check** (which found moderate-reach correlations front-loaded and decaying by
step 20000), this causal effect is stable from step 5000 to 20000 in every tier (e.g. peripheral
t=7.89->7.12, grassroot t=6.60->5.42) -- a persistent structural effect, not a transient one.
Replicates the established "moderate presence integrates the network" finding cleanly post-fix.

**sf1_ratio (secondary): replicates its established unreliability, now directly visible as a
within-experiment trajectory, not just across separate checks.** Sign flips between the two
checkpoints in 4/5 tiers (e.g. middle +0.152->-0.055, small +0.117->-0.066). Peripheral is significant
at step 5000 (t=3.04) but decays to null by 20000 (t=1.34) -- the same front-loaded-decay shape found
elsewhere in this doc, now reproduced inside a single controlled experiment. Reinforces (does not just
repeat) the prior decision to keep sf1 out of the primary outcome set.

**percapita_preextreme (primary): significant at peripheral tier, but in the OPPOSITE direction from
the established correlational prediction -- and this is stable, not a late-run artifact.** The
correlational finding (2026-07-28 entries above) was moderate reach -> *less* pre-extreme per-capita
posting (negative correlation), which predicts REMOVING moderates should *increase* pre-extreme
per-capita posting. Instead, every tier shows a *decrease* (peripheral: -0.0320 at step 5000, t=-3.53;
-0.0306 at step 20000, t=-3.95 -- strengthening, not decaying; other tiers same sign, not significant
at n=10). **Open, unresolved discrepancy**, not explained by this run: either (a) the original
correlation was not causal in the assumed direction (confounded or reverse-causal), or (b) `remove_hub`
suppresses overall network engagement/activity broadly (a "vitality" effect touching all classes) rather
than specifically releasing pre-extreme agents from a targeted suppression. Needs a follow-up before
either framing is trusted. `percapita_extreme` stays null everywhere at both checkpoints, consistent
with "extremists' own behavior unmoved."

**Mega-tier caveat**: 3 of 10 equilibrium seeds had **zero** moderate mega-tier hubs to remove at all
(`n_hubs` per seed: 13,1,1,0,11,0,0,0,8,6) -- those "treated" continuations are just control runs with
different RNG, diluting/noising the mega comparison. Mega's numbers here should be treated as
underpowered relative to the other four tiers until re-run with seeds pre-screened to guarantee >=1
hub, or more seeds.

**Tertiary outcomes (crossCuttingFraction, bimodalityCoeff) mostly small/null as expected** -- consistent
with the user's own call to deprioritize them as "easy to predict," though note the predictions weren't
strongly confirmed either (bimodalityCoeff in particular stayed nearly flat almost everywhere except a
marginal mega-tier signal) -- these outcomes just don't carry much information either way at this n.

## 2026-07-30 -- Phase 1b: re-tiered into 4 bands (user reframing), same day

User reframed the 5 tiers into 4: mega >300, middle 30-300, small 3-30, peripheral 0-3 (`scripts/
moderate_hub_5tier_removehub.py`, reused unchanged; motivation: mega's old >500 threshold left 3/10
seeds with zero hubs). Efficient re-run: the 10 equilibria and 10 `control` continuations are
tier-agnostic, so both were reused as-is from Phase 1 -- only the 40 new `remove_hub` continuations
(4 tiers x 10 seeds) were launched. Full log: `docs/report/moderate_hub_4tier_removehub.csv`.

**Mega's zero-hub problem is fixed**: n_hubs per seed now 1-15 (was 0-13 with 3 zeros). Mega
numbers should now be treated as trustworthy on the same footing as the other tiers.

**opinionAssortativity (secondary) replicates robustly under the new boundaries too** -- significant
in all 4 tiers at step 20000 (mega t=2.12, middle t=3.77, small t=7.22, peripheral t=5.56). Confirms
this finding is not an artifact of the specific tier cutpoints chosen.

**percapita_preextreme (primary): the sign discrepancy from Phase 1 is not uniform -- it is
tier-dependent, which refines (does not resolve) the open question.** At step 20000: mega (1-15 hubs
removed, few big ones) is *positive* (+0.021, t=1.16, n.s.) -- the SAME direction the original
correlational finding (moderate reach -> less pre-extreme posting) would predict for hub removal.
Middle is negative but n.s. (-0.019, t=-1.65). Small and peripheral (83-127 agents removed at once)
are negative AND significant (t=-3.22, t=-3.30) -- the opposite-direction effect found in Phase 1.
**Reading**: the discrepancy concentrates specifically in the mass-removal tiers (many tiny hubs
removed simultaneously), not the few-big-hub tier -- this is a point in favor of a "removing 100+
agents at once broadly suppresses network activity/vitality" explanation over "the original
correlation was reverse-causal/confounded," since a genuine reverse-causality story has no obvious
reason to depend on how many agents are removed at once. Still not conclusive; user to follow up.

**sf1_ratio (secondary) again shows the front-loaded-decay instability** -- e.g. small tier
significant at step 5000 (t=2.48) decaying to n.s. by 20000 (t=1.18); same pattern in peripheral
(t=2.09->1.65) and middle (t=1.50->0.48). Consistent, further replication of its unreliability as a
primary readout.

## 2026-07-30 -- Echo-chamber-deformation hypothesis check (pre-extreme-filtered triad + diffusion
reach), post-hoc on existing data, no new sim runs

User's hypothesis for the tier-dependent pre-extreme sign discrepancy above: removal of small/
peripheral moderate agents deforms the echo chamber specifically for pre-extreme agents.
`scripts/preextreme_echo_chamber_analysis.py`, entirely post-hoc on Phase 1b's already-completed
output (control 9200000-9, remove_hub small 9430000-9, remove_hub peripheral 9440000-9) -- no new
simulation.

**Part A -- pre-extreme-filtered triad, both directions** (IN = rows where `relayer` is
final-classified pre-extreme, i.e. pre-extreme's own repost behavior; OUT = rows where `author`
[stable original source, `rel_attrib=original`] is pre-extreme, i.e. how OTHERS relay pre-extreme's
content; crossCutting/assortativity computed directly from the already-logged `conveyedOpinion`/
`relayerOpinion` columns -- same sign-based crossCutting definition as the codebase's own
`Q_sign_repost`/`crossRepostRate`; bimodality = bimodality coefficient of pre-extreme's own final
opinion values; window = steps (15000,20000] of each continuation). Full log:
`docs/report/preextreme_echo_chamber_analysis.csv`.

**One clean, significant, narrow signature: `cross_out` drops significantly for both tiers**
(small: -0.034, t=-3.33; peripheral: -0.041, t=-4.96) -- pre-extreme agents' OWN authored content
gets relayed by opposite-camp agents less often once these hubs are removed. Everything about
pre-extreme's own INCOMING side (cross_in t=1.15/1.35 n.s., assort_in t=-0.90/-1.19 n.s.) and their
internal opinion spread (bimodal t=0.21/0.69 n.s., completely flat) shows no effect. **Reading**: a
real but narrow echo-chamber effect -- not "pre-extreme sees less cross-cutting content" and not
"pre-extreme splits into two poles," specifically "pre-extreme's own voice reaches the other camp
less." Caveat: does not obviously map onto the model's own `postProb` mechanism (driven by comfort
of an agent's INCOMING feed, not how far their own posts travel) -- real and useful, but not
established as the causal pathway to the percapita_preextreme posting-rate drop found in Phase 1/1b.

**Part B -- diffusion strength + are these specific agents conduits to pre-extreme?** For each
control seed, derived the same moderate-small/peripheral agent-id lists the removal arms actually
sever (from the corresponding equilibrium snapshot), then measured (source window (10000,19900]):
`reach_rate` = fraction of a group's relay events whose result is itself reposted >=1 more time;
`preext_given_reach` = of those, fraction whose next-hop relayer is pre-extreme. Full log:
`docs/report/preextreme_conduit_reach.csv`.

| group | reach_rate | P(next hop pre-extreme \| propagated) |
|---|---|---|
| population baseline | 7.54%+/-0.35% | 64.98%+/-3.03% |
| moderate-small | 8.01%+/-1.25% (comparable) | **51.61%+/-4.59%** |
| moderate-peripheral | **1.39%+/-0.17% (~5x weaker)** | **51.29%+/-6.83%** |

Small-tier agents diffuse at an ordinary rate; peripheral-tier agents' reposts almost never
propagate further (consistent with 0-3 followers). **Neither group over-indexes on reaching
pre-extreme -- both sit BELOW the 65% population baseline** (itself high mainly because pre-extreme
is ~49% of the population). If anything these agents are slightly worse-than-average conduits to
pre-extreme specifically, not better.

**Combined reading, genuinely unresolved**: the agents being removed are not themselves unusually
effective conduits into pre-extreme, yet removing them measurably reduces cross-camp relay of
pre-extreme content (Part A). This points toward an indirect, network-level effect (removing this
population shifts the broader repost ecosystem enough to reduce cross-camp relay generally) rather
than "these specific agents were personally bridging to pre-extremes" -- worth further work before
treating either framing as settled.

## 2026-07-30 -- Counterfactual Conduit test (user's definition) + broader-deactivation check

Two more post-hoc tests, same underlying control-arm data (no new sim runs). User's own
operationalization, `scripts/counterfactual_conduit_analysis.py`.

**Counterfactual Conduit**: for each cascade C (grouped by rootPostId in `repost_cascades.csv`),
I(C)=1 if it ever reaches the opposite camp from the root's sign (`relay_enabled=false` means
`conveyedOpinion` is verbatim the root's opinion throughout, so this is a plain sign check against
`relayerOpinion`). I_{-R}(C) = same check after pruning every node relayed by an agent in target
set R, and everything downstream of it (a structural necessity test on the ALREADY-OBSERVED
cascade tree, not a re-simulation -- a node's children only exist because it created the post they
relayed, so removing it removes its subtree). Delta(C)=I(C)-I_{-R}(C) in {0,1}; Counterfactual
Conduit = mean(Delta(C)), reported both unconditional (all cascades) and conditional (only
cascades that actually crossed camps). Cascade window: depth-1 event step in (10000,19000].
Full log: `docs/report/counterfactual_conduit.csv`.

| tier | cc_unconditional | cc_conditional |
|---|---|---|
| small | 3.45%+/-1.43% | **7.54%+/-2.47%** |
| peripheral | 4.54%+/-1.65% | **9.94%+/-3.08%** |

**Genuine, non-trivial, consistent across all 10 seeds: ~7.5-10% of cascades that actually crossed
camps would NOT have without these agents' participation.** Peripheral agents, despite being much
weaker diffusers on average (Part B `reach_rate` 1.4% vs small's 8%), are MORE necessary per-crossing-
cascade than small tier -- consistent with less redundant backup structure around lone peripheral
bridges (fewer alternate routes to substitute). Reconciles Parts A/B: not exceptionally good conduits
on average, but genuinely irreplaceable for a meaningful minority of cascades -- the mechanistic
source of Part A's `cross_out` reduction.

**Broader-deactivation check (user's second hypothesis, 2026-07-30: "peripheral agents activate some
local activity; removal deactivates it")** -- tested via total network activity
(originalPostCount+repostCount per step), control vs remove_hub, window (15000,20000]:

- Activity drops significantly when these agents are removed: **-9.7% (t=-19.34) small, -10.8%
  (t=-16.43) peripheral** -- both essentially undeniable at this sample size.
- **But decomposed and mostly refuted as an ADDITIONAL mechanism**: the removed agents themselves
  personally perform **10.58%+/-1.14% (small) / 11.52%+/-1.39% (peripheral) of all repost activity**
  in the control run -- matching, if anything slightly EXCEEDING, the measured drop. The activity
  effect is essentially the mechanical consequence of removing agents who directly accounted for
  that much volume, not evidence that the remaining ~900 agents become less active. If anything, the
  measured drop being marginally smaller than the removed agents' own share hints at mild
  compensation, not amplified deactivation. **Hypothesis not supported as a distinct mechanism** --
  useful to have ruled out cleanly rather than left open.

**Where this leaves the pre-extreme puzzle**: the differential effect (pre-extreme per-capita drops,
extreme per-capita does not, Phase 1/1b) is not explained by broad deactivation (which would hit
both classes proportionally and has now been ruled out as a distinct effect) -- more likely tied to
the genuine, if modest, conduit-necessity effect found here feeding into Part A's `cross_out`
reduction. The exact causal chain from "less unique bridging capacity" to "pre-extreme specifically
posts less" is still not fully closed; the mechanically cleanest pieces of this investigation
(counterfactual necessity, activity decomposition) are now resolved, the remaining open piece is
narrower than where this line of inquiry started.

## 2026-07-30 -- Closing piece: pre-extreme is significantly over-represented among necessary-cascade originators

User's follow-up: among cascades whose cross-camp reach depended on R (Delta(C)=1 above), what
fraction of their ORIGINATORS (root `author`, stable per cascade since `rel_attrib=original`) are
pre-extreme? First pass (weighting by cascade COUNT) was badly confounded: a handful of hyper-
prolific founder-clique hub authors (each 6-8% of all root events alone, all center/bin-2 opinion)
dominate cascade counts, so a count-weighted fraction mostly reflects which class those few
dominant hubs happen to land in per seed (swung 3%-79% across seeds -- noise, not signal). Redone
weighting by UNIQUE ORIGINATING AUTHOR instead (each distinct author counted once regardless of how
many cascades they started) -- much more stable, n=10 seeds:

| originator population | pre-extreme fraction |
|---|---|
| population baseline | 48.6% |
| all cascade-originating authors | 48.47%+/-7.35% (flat -- no bias in who ever gets reposted at all) |
| crossed-camp originating authors | 54.81%+/-9.37% |
| **necessary-cascade originating authors (small)** | **57.62%+/-14.84%** |
| **necessary-cascade originating authors (peripheral)** | **59.31%+/-16.57%** |

**Significant over-representation relative to population baseline**: small tier diff=+9.14pp vs.
all-originators, t=2.89, p=0.018; peripheral diff=+10.85pp, t=3.33, p=0.0088 (both paired, n=10).
The further narrowing from "crossed" (54.8%) to "necessarily so" is NOT itself significant
(t=1.21, p=0.257) -- most of the enrichment already happens at "crosses camp at all," not
specifically at the necessity step.

**This closes the loop**: pre-extreme agents are not disproportionately REACHED by these conduits
when the conduits act (Part B: slightly below baseline), but pre-extreme's OWN content is
disproportionately DEPENDENT on these specific low-tier conduits to cross camps at all. The real
asymmetry is that pre-extreme's cross-camp content is more fragile/bottlenecked in general
(over-represented among cascades that cross camps at all, and further among those that need R
specifically), not that these agents preferentially target pre-extreme as an audience. Consistent
with, and now gives a concrete mechanism for, Part A's `cross_out` reduction and the original
Phase 1/1b finding that removing these tiers specifically (not extreme per-capita) reduces
pre-extreme per-capita posting.

## 2026-07-30 -- Participation vs. necessity: cascade path participation rate, all 4 tiers

User's question: of all cross-camp cascades in control, what fraction pass THROUGH a moderate hub
of each tier at all (mere participation -- relayer set intersects R -- not necessity)? Same window/
method as the Counterfactual Conduit test above, all 4 tiers this time. Full log:
`docs/report/moderate_hub_cascade_participation.csv`.

| tier | n_agents | participation rate |
|---|---|---|
| mega | 15 | 19.40%+/-9.62% |
| middle | 13 | 38.05%+/-2.60% |
| small | 109 | 67.80%+/-4.27% |
| peripheral | 127 | 71.07%+/-4.42% |

Roughly tracks tier POPULATION SIZE (more agents -> more chances one shows up in a large cascade),
not individual reach -- mega has the fewest agents and the lowest participation rate despite vastly
higher per-agent reach.

**The informative contrast is against necessity (Counterfactual Conduit, small=7.54%,
peripheral=9.94%, logged above)**: small/peripheral PARTICIPATE in 68-71% of crossing cascades but
are only NECESSARY in ~7.5-10% -- roughly an 8-9x gap between "somewhere in the path" and "actually
load-bearing." Strong quantitative confirmation of the redundancy picture already established:
these agents show up constantly in cross-camp cascades, but there is almost always an alternate
route around any single one of them.

## 2026-07-30 -- In-BC vs. out-of-BC ("hostile") composition of direct cross-camp crossings

User's question, following the depth-1/no-moderate finding above: of the >90% of crossings that
happen via direct extreme-to-extreme contact (no moderate involved), how many are in-BC (ordinary
sharing) vs. out-of-BC ("hostile"/out-of-tolerance relay, `outOfBCRepostProb`-gated)? This flag
(`Post.isOutOfBcRelay()`) existed in code but was never written to `repost_cascades.csv` -- only
used transiently for GEXF edge coloring (reset every 5000 steps, not queryable after the fact, and
not reconstructable post-hoc since it depends on each agent's `bc` value at the moment of relay,
which isn't logged per-event). **Added `outOfBcRelay` as a new column to `repost_cascades.csv`**
(`Writer.java`, `logRepostCascade`/`REPOST_CASCADE_HEADER`) -- a permanent, generically useful
instrumentation addition, not experiment-specific. Recompiled clean; reran all 10 control seeds
(9200000-9200009, same equilibria, `network=read`, unchanged otherwise) to populate it.

**Result (pooled/count-weighted across all 10 seeds, robust to one small-sample outlier seed --
9200000 had only 249 crossing cascades vs. 3000-9000+ for the others, so its fraction alone was
noisy at 36-44%; excluding it gives 2.62%+/-1.38%, consistent with the pooled figure)**:

| basis | out-of-BC ("hostile") fraction |
|---|---|
| all crossing relay events | 0.28% (n=760,285) |
| first/shallowest crossing node per cascade | 2.49% (n=54,429) |
| depth-1 direct crossings only | **2.57% (n=49,295)** |

**~97.4% of direct extreme-to-extreme cross-camp crossings are in-BC -- ordinary, non-hostile
reposting, not the deliberate "hostile"/dunking mechanism.** Makes sense given
`out_of_bc_repost_prob=0.01` is 10x below `repost_prob=0.1`, but the substantive read is mechanistic:
cross-camp cascading is mostly driven by agents whose `bc` is still wide enough (many haven't decayed
far from `bc_init=0.8`) that opposite-camp content simply reads as comfortable enough to share at the
ordinary rate, not by deliberate outrage-driven relay. Combined with the depth-1/no-moderate-needed
finding: cross-camp cascading in this model is mostly (a) direct, (b) ordinary/non-hostile, and (c)
not dependent on any moderate conduit -- three separate findings all pointing the same direction.
Full per-seed log: `docs/report/crossing_inbc_vs_outbc.csv`.

## 2026-07-30 -- For-You (algorithmic) vs. chronological composition of direct cross-camp crossings

User's question, extending the in-BC/out-of-BC check above: of the direct (depth-1) crossings, how
much routes via the algorithmic For-You feed vs. plain chronological-from-follows? Channel
provenance was NOT retained anywhere in the code before this (explicitly noted in `AdminOptim.java`:
"channel provenance isn't retained on Post/Agent.feed once delivered, so this is the only point it's
knowable") -- added properly this time, not a post-hoc approximation:

**Implementation** (`Post.java`, `Agent.java`, `AdminOptim.java`, `Writer.java`): `Post` gained a
`viaAlgo` field (parallel to the existing `outOfBcRelay` pattern). `Agent` gained a per-step
`forYouRootIds` set, populated by `AdminOptim.AdminFeedback` right after building the `forYou` list
(before it's merged+shuffled into `feed`, the only point this is knowable) -- chrono and For-You are
mutually exclusive by `rootPostId` already (For-You's build loop skips anything in chrono's
`seenRoots`), so membership is unambiguous. `Agent.repost()` checks this set per relay and passes
`viaAlgo` through `relay()`/`Post.relayOf()` to the logged post, and `Writer` gained a new
`viaAlgo` column in `repost_cascades.csv`. Recompiled clean (`ModelTests`: same 3 pre-existing
failures, unrelated -- confirmed before this addition too, no new failures). Reran all 10 control
seeds to populate it.

**Result (pooled/count-weighted, n=10 seeds)**:

| basis | via For-You (algo) | via chronological |
|---|---|---|
| all crossing relay events | 68.75% | 31.25% |
| first/shallowest crossing node per cascade | 45.60% | 54.40% |
| depth-1 direct crossings only | **50.35%** | **49.65%** |

**Roughly even 50/50 split for the depth-1 direct crossings that dominate cross-camp cascading**,
despite chrono only occupying 30% of feed capacity (`alpha=0.7` => 70% algo slots) -- chronological/
follow-based exposure punches above its feed-share weight for causing direct crossings specifically.
Consistent with `opinionAssortativity` sitting well below 1.0 throughout every measurement in this
doc (~0.4-0.5) -- a meaningful fraction of ordinary follow edges already cross camp lines, so plain
chronological reach regularly delivers opposite-camp content without the algorithm's help.

**This corrects an earlier speculation in this doc** (the depth-1/no-moderate entry above guessed
the algorithm was "very plausibly" the dominant channel) -- the data doesn't support that as
strongly as implied; it's a roughly even split, not algorithm-dominated. Revised full picture:
cross-camp cascading in this model is mostly direct (90%+ at depth-1), mostly non-hostile (97%+
in-BC), and roughly evenly split between algorithmic and organic/follow-based discovery -- not
routed through moderate conduits, and not primarily an algorithmic-exposure artifact either.
Full per-seed log: `docs/report/crossing_algo_vs_chrono.csv`.

## 2026-07-31 -- Replicating the original (pre-For-You) moderate-conduit test at alpha=0

User's framing: the moderate-conduit hypothesis was first stated in WSSIT2026, in an environment
that had no For-You algorithmic feed at all. Everything logged in this doc since 2026-07-21 has
been measured with the algorithm on (`alpha=0.7`). Before trusting any of those findings as
commentary on the *original* hypothesis, check whether the conduit effect the hypothesis actually
claims (mid-tier moderate hub bridges cross-camp content) shows up at all with the algorithm fully
off -- i.e. run the bridging test in the regime the hypothesis was stated for.

**Design** (`scripts/alpha0_conduit_replication.py`): `alpha=0` for both equilibrium-building and
continuation (not just continuation) -- feed content can trigger block/unfollow, so network
topology itself is potentially alpha-dependent; reusing an `alpha=0.7` equilibrium under a
"no-algorithm" continuation would leave stale structural traces of the algorithmic regime. 20 fresh
seeds (6000000-6000019), mid-tier moderate hubs (100 < followers <= 500, `|opinion|<0.2`, same
convention as `bridging_current_config.py`), current-config FIXED params otherwise unchanged.

Arms: `control`, `mute_repost` (hub loses repost/relay capability -- the direct test of "does the
hub function as a conduit"), `algo_exclude` (hub excluded from the For-You candidate pool). Included
`algo_exclude` deliberately as a **negative control, not a live treatment**: at `alpha=0`,
`feedAlgoShare=0` => `algoSlots = floor(0*capacity) = 0` (`AdminOptim.java:396`) => the For-You
stream is structurally always empty regardless of `algo_exclude_ids`. If the harness is behaving
correctly, `algo_exclude` vs `control` should show nothing but seed noise.

**Result: `algo_exclude` behaved exactly as the null-control prediction.** Every core metric
(`Q_sign_repost`, `sf1_ratio`, `crossCuttingFraction`, `bimodalityCoeff`, `disagreement`) has
`|t|<2.4` at both checkpoints, no consistent sign across checkpoints. Confirms the harness/CLI
wiring is correct at `alpha=0` (no accidental leakage of the excluded set into some other pathway).

**Result: `mute_repost` (the actual conduit test) does NOT show a robust, checkpoint-consistent
signal on the metrics that discriminate Type 1 vs Type 2 polarization:**

| metric | step 10000 diff (t) | step 20000 diff (t) |
|---|---|---|
| sf1_ratio | -0.109 (t=-2.55) | +0.057 (t=1.63) |
| crossCuttingFraction | +0.0045 (t=2.64) | +0.0021 (t=1.37) |
| bimodalityCoeff | -0.0000 (t=-0.07) | +0.0012 (t=2.00) |
| Q_sign_repost | +0.0033 (t=1.30) | +0.0019 (t=0.61) |
| opinionKurtosis | -0.0013 (t=-0.50) | -0.0058 (t=-2.19) |

`sf1_ratio` flips sign between checkpoints (significantly negative at 10000, non-significantly
positive at 20000) -- the opposite of a clean, monotone conduit effect. `crossCuttingFraction`'s
step-10000 bump (t=2.64) fades to non-significant by step 20000 and moves in parallel with a
transient `blockCount` drop (t=-2.12 at 10000, fading by 20000) -- more plausibly "muting the hub's
repost also mutes a source of block-triggering exposure, temporarily leaving more cross-cutting
edges intact" than "the hub was carrying cross-cutting content that disappears when muted." Neither
reading survives to the second checkpoint.

**What IS robust across both checkpoints:** `originalPostCount` (population-wide, not just the
muted hub) rises with `mute_repost` at both checkpoints (t=3.60, t=3.45) and `postShare_3`
(upper-middle opinion bin) falls at both (t=-3.04, t=-2.40). These are activity/composition effects,
not the Type-1/Type-2 discriminating metrics the hypothesis is actually about.

**Read against the algo_exclude null-control floor**, `mute_repost`'s core-metric t-stats
(sf1_ratio, crossCuttingFraction, bimodalityCoeff, Q_sign_repost: all |t|<2.65, inconsistent sign
across checkpoints) are not clearly distinguishable from the noise floor a true no-op shows
(algo_exclude's own postShare_0/1 hit t=1.98-2.65 with zero possible causal mechanism). n=20 seeds
is likely underpowered to resolve an effect this size either way -- this is an **inconclusive, not
a null, result**: it does not confirm the original moderate-conduit hypothesis replicates cleanly
in the pre-algorithm (alpha=0) regime, but it also doesn't rule it out. Consistent with (from the
other direction) the conduit-redundancy risk already flagged in `docs/research-direction.md`
("at high alpha... the conduit can be washed out") -- here at the opposite extreme (alpha=0) the
conduit's OWN signal is what's weak/noisy, suggesting the mid-tier repost-mute manipulation alone,
at this n, may just be a low-power lever for these particular outcome metrics regardless of alpha.

Full per-seed/per-checkpoint log: `docs/report/alpha0_conduit_replication.csv`.

**Open follow-up (not yet run):** increase n beyond 20 seeds to check whether the sf1_ratio/
crossCuttingFraction signals sharpen or continue to bounce sign; or try a larger/more extreme hub
tier (this used the same 100-500 follower mid-tier as the alpha=0.7 series) in case mid-tier hubs
specifically are too weak a lever to move population-level Type1/Type2 metrics regardless of the
algorithm being on or off.

## 2026-07-31 -- Moderate-tier participation ratio across EVERY cascade (not just cross-cutting)

User's question: broaden the earlier participation-rate check (line ~3866, restricted to
cross-camp cascades) to ALL cascades in the control arm -- of every repost cascade, what fraction
has at least one relayer belonging to each moderate tier? Categories are not mutually exclusive (a
cascade's relay chain can touch multiple tiers); `none` = relayed exclusively by non-moderate
(`|opinion|>=0.2`) agents. Same data/window/tier convention as the rest of this doc: control arm,
seeds 9200000-9200009, cascades selected by depth==1 event step in (10000,19000], relayer set taken
across the full cascade tree regardless of step. Script: `scripts/cascade_moderate_tier_composition.py`.

| tier | n_agents | share of ALL cascades touched | share of CROSS-CAMP cascades touched (from above) |
|---|---|---|---|
| mega | 15 | 10.04%+/-4.55% | 19.40%+/-9.62% |
| middle | 13 | 17.72%+/-3.15% | 38.05%+/-2.60% |
| small | 109 | 35.44%+/-5.23% | 67.80%+/-4.27% |
| peripheral | 127 | 39.83%+/-5.10% | 71.07%+/-4.42% |
| **none** (no moderate relayer at all) | -- | **51.99%+/-6.34%** | (n/a -- by definition every cross-camp cascade in this comparison excludes the "no crossing" case, not "no moderate") |

**Every tier participates roughly 2x more often in cross-camp cascades than in cascades generally**
(mega 10.0%->19.4%, middle 17.7%->38.1%, small 35.4%->67.8%, peripheral 39.8%->71.1%) -- moderates
are disproportionately likely to show up on a path that happens to cross camps, consistent with
sitting nearer the middle of the opinion/network space. But **just over half of ALL cascades
(52.0%) involve no moderate-tier agent whatsoever** -- the bulk of repost activity in this model is
extreme-to-extreme, moderates are a minority participant even before asking whether they're
necessary (necessity was already shown to be far lower still: small 7.54%, peripheral 9.94%, see
above). Three layers, each smaller than the last: ~48% of cascades touch a moderate at all -> ~68-71%
of the smaller cross-camp subset touch small/peripheral specifically -> ~7.5-10% actually require
them. Full per-seed log: `docs/report/cascade_moderate_tier_composition.csv`.

## 2026-07-31 -- Necessity (Counterfactual Conduit), extended to all 4 tiers, unconditional over EVERY cascade

User's follow-up to the "every cascade" participation table above: not participation, necessity.
Extended `scripts/counterfactual_conduit_analysis.py` (previously small/peripheral only) to mega
and middle, using the same `remove_hub` continuation data already on disk (9410000-9,
9420000-9) for the activity-decomposition supplement. Same definition/window as before: Delta(C) =
1 iff removing every relay by an agent in tier R (and everything downstream) kills that cascade's
cross-camp reach; `cc_unconditional` = mean(Delta(C)) over ALL cascades (the direct answer to "of
every cascade, what fraction needs tier R"); `cc_conditional` = same but restricted to cascades that
crossed camps at all (already reported for small/peripheral above -- values reproduce exactly,
0.0754/0.0994, confirming consistency).

| tier | n_agents | cc_unconditional (every cascade) | cc_conditional (crossed-camp cascades only) |
|---|---|---|---|
| mega | 1-15 | 0.07%+/-0.08% | 0.18%+/-0.21% |
| middle | 11-21 | 0.29%+/-0.23% | 0.64%+/-0.47% |
| small | 83-114 | 3.45%+/-1.43% | **7.54%+/-2.47%** |
| peripheral | 89-127 | 4.54%+/-1.65% | **9.94%+/-3.08%** |

**Necessity is monotone in the OPPOSITE direction from raw agent count/participation**: mega has the
fewest agents (1-15) and the lowest necessity (0.07-0.18%); peripheral has the most agents (89-127)
and the highest (4.5-9.9%) -- exactly the opposite of what "more of them -> more load-bearing" would
predict, and the opposite of the participation numbers' own driver (participation tracked population
size). Combined with the participation-rate table two entries above (mega participates in only 19.4%
of crossing cascades yet is needed in just 0.18% of those it touches -- essentially fully redundant
even when present; peripheral participates in 71.1% and is needed in 9.94% of those -- still mostly
redundant, but an order of magnitude less so). Mega/middle hubs are almost never individually
load-bearing for cross-camp reach at all (near-zero even conditional on crossing) -- consistent with
the founder-clique redundancy finding (2026-07-30): the largest hubs have so much overlapping
reach that no single one is ever necessary. Small/peripheral's higher necessity despite lower
individual reach fits the "less redundant backup structure around a lone peripheral bridge"
reading already given for small vs. peripheral above, now shown to hold relative to mega/middle too,
by roughly two orders of magnitude.

**Activity-decomposition supplement extended to mega/middle**: `remove_hub_mega` -1.0% (t=-2.33),
`remove_hub_middle` -1.7% (t=-6.37) -- both far smaller than small/peripheral's ~10% drop, matching
their much smaller share of total repost volume (few agents). No sign of mega/middle being
disproportionately load-bearing for overall network activity either.

Full per-seed log: `docs/report/counterfactual_conduit.csv`.
