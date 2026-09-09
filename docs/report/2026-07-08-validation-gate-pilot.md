# 2026-07-08 — Entering Step-2 (validation gate): finding + pilot design

**Context:** `docs/research-direction.md` §0 working method, Step 2 ("Validation gate (pilots)"),
under the 2026-07-08 redefinition (§1a): confirm the network reaches a structurally-separated
(Type-1) base state, and that a moderate hub produces measurable cross-cutting exposure
*attributable to it*, ideally checked across network types to test the scale-free-dependency
hypothesis. This was flagged as "not yet decided" (exact operationalization of hub-attributable
cross-cutting flow) — resolved below before running anything.

---

## Finding: the existing cross-cutting/assortativity metrics cannot see the hub

`Analysis.computeCrossCuttingFraction`, `computeOpinionAssortativity`,
`computeInteractionAssortativity`, and `computeInteractionCrossCuttingFraction` all skip any edge
where **either endpoint is a `target` agent** (`agentSet[i].getTarget()` / `[j].getTarget()`) —
`target` is set on exactly the intervened hubs (`InterventionSetup.pinHub` → `Agent.setTarget()`).
This was a reasonable original design (keep exogenously-pinned nodes from mechanically distorting
population-level polarization stats), but it means these four metrics — the entire current
structural-separation instrumentation — are **structurally blind to any edge touching the hub**,
i.e. blind to exactly the bridging edges the redefined Type-2 question is about. A with/without-hub
contrast on these metrics can only pick up an *indirect, one-hop-removed* effect (population members
who received hub-relayed content re-relaying it further to same-population followers); it cannot
directly confirm "the hub itself is the bridge." Running the validation pilot on these metrics alone
would risk a false null (mistaking "invisible to this metric" for "no effect").

**This is a construct-validity gap in the instrumentation, not a bug** — the metrics still do their
original job (population-level separation net of exogenous manipulation) — but they are the wrong
tool for the hub-attribution question and must not be the only readout for Step 2.

## Decision: hub-attributable bridging via post-hoc cascade analysis (no model-code change)

Rather than rewrite the frozen-adjacent `Analysis.java` metrics pre-freeze, compute the
hub-attributable quantity **post-hoc** from data already logged every run:
- `posts/repost_cascades.csv` (`step,rootPostId,parentPostId,postId,author,relayer,depth,
  conveyedOpinion`) — already on by default (`log_repost_cascade=true`). Under the default
  `rel_attrib=original`, `author` stays the original source for the whole chain, so hub
  involvement can only be read from the `relayer` field of each row (who performed *this specific*
  relay) — not from `author`.
- **New:** `degrees/agent_snapshot_{t0,final}.csv` (`agentId,intrinsicOpinion,opinion,
  followerCount,followeeCount,isTarget`) — added this session (`Writer.writeAgentSnapshot`,
  called at t=0 and at the end of `evolve()`). Needed because no existing export carries
  per-agent opinion/camp; the repost-cascade log alone can't tell us which camp a relayer
  belongs to. Cheap (O(N), once per run, no per-step cost).

**Operationalization (validation-gate level — simple contrast, not full mediation):**
1. From `run_config.csv`, identify the moderate-hub id (`role=="moderate"`) and extreme-hub ids
   (`role` in `{extreme+, extreme-}`) for the run.
2. Walk `repost_cascades.csv` ancestor chains (via `parentPostId`) to find, for each relay event,
   whether the moderate hub appears as `relayer` anywhere in its ancestry (including itself) —
   "hub-mediated" cascades.
3. For hub-mediated cascades rooted at an extreme hub, look up each downstream `relayer`'s camp
   (sign of `opinion` in `agent_snapshot_final.csv`) and compare to the root's camp (its fixed
   ±1). Fraction with opposite sign = **hub-mediated cross-camp reach**.
4. Compare this quantity (a) with the hub present (`n_mod=1`) vs. structurally-absent (`n_mod=0`,
   same seed ⇒ same network + dynamics RNG stream, so the pair is a clean counterfactual — with
   `n_mod=0` there is no moderate hub to mediate, so this is really "does a hub-mediated pathway
   exist and reach across camps at all"), and (b) across network types, to test the scale-free
   dependency hypothesis.
5. Report this alongside the existing population-level metrics (`crossCuttingFraction`,
   `interactionCrossCuttingFraction`, `opinionAssortativity`, `computeSignModularity`) as
   converging/diverging evidence, not a replacement.

This is deliberately the "simple with/without-hub contrast" named as one option in
`docs/report/2026-07-08-relay-ablation-diagnostic.md`'s open question, not the mediation-style
decomposition — appropriate for a pilot gate; revisit for the Step-3 frozen main batch if this
proves informative.

## Pilot design (Step 2 gate, per user go-ahead: small scale)

- **Scale:** `n=500`, `steps=15000` (production default is `n=1000, steps=40000`; this is a
  pilot, not the frozen main batch).
- **Factors:** `networkType ∈ {dcsbm, ws, random, lfr}` (dcsbm/lfr heavy-tailed-ish; ws/random are
  the non-scale-free controls) × `nModerate ∈ {0, 1}` (hub absent/present) — 8 cells.
- **Fixed:** `extreme=sym` (both extreme background hubs present in every cell, holding source
  extremity fixed per the Step-0 DAG), `channel=both`, all other knobs at current defaults
  (`relay_enabled=false`, `hostility_active=false`, per the 2026-07-08 redefinition — not
  reconsidered here).
- **Seeds:** 3 seeds per cell (`100,101,102`, chosen outside the production `0..29` range to avoid
  any folder collision), `net_seed` left at its default (== `seed`), so the `n_mod=0` vs `n_mod=1`
  runs at the same seed share an identical initial network and dynamics RNG stream — the only
  difference is the intervention itself. 8 cells × 3 seeds = **24 runs**.
- **Gate criteria (from research-direction.md §0 Step 2):**
  1. Structural-separation metrics (modularity / assortativity / crossCuttingFraction) plateau by
     `t_max=15000`, not still trending (else re-run at longer `steps`, per the
     2026-07-08-relay-ablation-diagnostic.md open check).
  2. DC-SBM (and LFR) actually sustain mid-scale hubs at equilibrium (t0 vs final follower counts
     for the pinned hubs / top-K pool).
  3. Hub-mediated cross-camp reach (new metric above) is non-zero and distinguishable between
     `n_mod=0`/`n_mod=1`, and — if the scale-free hypothesis holds — larger under
     `dcsbm`/`lfr` than under `ws`/`random`.

Next entry in this file (or a follow-up dated report) records the pilot results against these
criteria.

---

## Addendum: pre-pilot parameter-calibration discussion + `P_u` naming collision fixed

Before running the matrix above, went through the model's free parameters to sort them into (A)
behaviorally-meaningful knobs a reviewer will ask "why this value" about (candidates: `repost_prob`
functional form/range vs. cascade literature — Vosoughi/Roy/Aral 2018, Goel et al. 2012 — noting
their reshare rates are conditional on much larger feeds than `FEED_CAPACITY=10` so a number can't
be imported directly, only the "low but non-zero" qualitative range; `MU_PARAM`'s log-diminishing-
returns functional form vs. social-reward literature, Meshi/Tamir/Heekeren 2015; `INITIAL_STUBBORNNESS`
vs. Friedkin-Johnsen susceptibility estimates, e.g. Das/Gollapudi/Munagala 2014; bounded-confidence
scale vs. Deffuant 2000 / Hegselmann-Krause 2002; `sbm_gamma=2.3` vs. empirical SNS follower-count
exponents, e.g. Kwak et al. 2010) and (B) pure timescale/scale knobs with no "correct" external value
(`FEED_CAPACITY`, `FOLLOW_PROB`, `INITIAL_PP/MAX_PP/MIN_PP`, `COMFORT_PP_FACTOR`, platform-access
probability below) — decided by internal consistency (reaching a meaningful equilibrium within the
step budget), not citation. (A)-candidates not yet resolved; revisit before the Step-3 freeze if the
paper needs to defend specific values.

**Found + fixed while going through this list:** `Const.INITIAL_PU/MAX_PU/MIN_PU` ("Prob of Using
platform") and `ExperimentConfig.pU`/CLI `p_u` (the tie-dissolution/unfollow **phase-diagram knob**
central to the whole study) shared the "P_u" initials despite being unrelated mechanisms — initially
misread as dead code (a grep pattern miss), then confirmed live: `OpinionDynamics.java`'s per-agent
loop gates the **entire** action set (feed refresh, repost, follow, unfollow, post) behind
`nextDouble() > agent.getAccessProb()` each step. Confirmed as a pure category-(B) scale parameter
per the user's read: `MAX_PU == MIN_PU == INITIAL_PU == 0.1` identically (the clamp between them was
a no-op), homogeneous across all agents, no CLI key exists to sweep it, and its magnitude only
rescales how many step-ticks are "wasted" vs. active — not swept, kept at the current constant.

**Decision:** renamed the platform-access family to remove the collision (`ExperimentConfig.pU`/
`p_u` keeps its established name — it's the paper's own phase-knob terminology throughout
`research-direction.md`; renaming that would be far more disruptive):
- `Const.INITIAL_PU`/`MAX_PU`/`MIN_PU` → single constant `Const.ACCESS_PROB = 0.1` (MAX/MIN deleted
  outright — they were always identical to INITIAL, i.e. never actually bounded anything).
- `Agent.useProb`/`getuseProb()`/`setuseProb()` → `accessProb`/`getAccessProb()`/`setAccessProb()`.
- The now-pointless clamp (`Math.max(MIN_PU, Math.min(useProb, MAX_PU))` in `Agent.java`'s
  `updateMyself`) removed entirely — nothing mutates `accessProb` during dynamics, so there was
  nothing to clamp.
- Gephi export/import round-trip (`GraphVisualize`, `RepostVisualize`, `GephiReader`) node attribute
  renamed `useProb` → `accessProb` to match; old exported `.gexf` files with the `useProb` attribute
  name will no longer restore that field via `network=read` (falls back to the default constant —
  not fatal, this is experiment-run glue, not durable data).
- Verified: `grep -rn "INITIAL_PU\|MAX_PU\|MIN_PU\|useProb"` clean; full recompile clean; `ModelTests`
  28/28 pass.

---

## Pilot results (24 runs) against the Step-2 gate criteria

Ran the matrix above (`run_pilot_matrix.sh`); analyzed with
`scripts/validation_gate_pilot_analysis.py` (raw per-run output:
`docs/report/2026-07-08-validation-gate-pilot-results.csv`). One analysis bug found and fixed in
the process: gate 3's hub→camp attribution originally joined `rootPostId` against `repost_cascades
.csv`'s own `postId` column to recover the source camp — but that file logs only *relay events*, so
the original (root) post's id is never a row's `postId`, silently zeroing every match. Fixed by
reading the source camp directly off each row's own `author` field (correct under the default
`rel_attrib=original`, where `author` is preserved unchanged through the whole relay chain).

**Gate 1 (plateau) — NOT MET at this scale.** `opinionAssortativity` is high (0.70–0.99) and near-
flat (|Δ last-two-20%-windows| mostly <0.02), but `interactionCrossCuttingFraction` (the repost/
relay-based separation measure) is still declining meaningfully at `t=15000` in every cell (Δ ≈
−0.03 to −0.05, i.e. still losing ~3-5 percentage points of cross-cutting relay activity per
window). This is exactly the "caught mid-transition, not a real equilibrium" failure mode flagged
in this file's Addendum 1 / the original relay-ablation diagnostic. **Conclusion: `steps=15000` is
not enough; re-run at longer duration (production `steps=40000`, or a 2-3x pilot bump) before
treating any snapshot here as equilibrium.**

**Gate 2 (mid-scale hubs) — network generation confirmed; persistence is the open question.**
Initial (t0) hub follower counts cleanly separate by topology as expected: `dcsbm` ~115-119,
`lfr` ~40-50 (heavy-tailed, real hubs) vs. `random` ~12-14, `ws` ~4 (narrow degree distribution —
the "hub" is just an average node). This validates the network generators structurally. But by
`t=15000`, nearly every hub — extreme *and* moderate — has lost most of its initial followers
(often down to 0-6), consistent with the strong homophilous sorting gate 1 also shows. Two outlier
cells buck this: `dcsbm` seed 100's moderate hub only fell 114→92, and `random` seed 100's moderate
hub *grew* 12→129. Suggestive of differential treatment of the moderate vs. extreme hubs (matching
the "conduit immunity" mechanism in research-direction.md §2), but 3 seeds cannot distinguish signal
from noise here — flag for the larger run, not a conclusion yet.

**Gate 3 (hub-attributable cross-camp bridging) — real but rare at this scale.** Hub-mediated
cascades (extreme-hub-rooted repost chains passing through the moderate hub) occurred in 4 of 12
`n_mod=1` cells (`dcsbm` 2/3 seeds, `lfr` 1/3, `random` 1/3, `ws` 0/3). When they occurred, the
cross-camp fraction was substantial: 43%/43% (`dcsbm`), 27% (`lfr`), 80% (`random`) — i.e. the
mechanism, when active, reaches the opposite camp at a rate far above what pure chance among a
handful of relays would suggest. `ws` (non-scale-free control) produced zero hub-mediated cascades
in all 3 seeds — directionally consistent with the scale-free-dependency hypothesis, but `random`
(also non-scale-free, similarly small hub) produced one nonzero seed, so this is not yet a clean
separation. **Occurrence is bottlenecked by rare-event dynamics at `n=500/steps=15000/3 seeds`,
not by the mechanism being absent** — needs more seeds and/or the longer run from gate 1 before
concluding anything about the scale-free dependency either way.

**Overall gate verdict: not yet passed — re-run at longer `steps` (gate 1 is the blocking one) and
with more seeds once that's fixed, before any Step-3 freeze.** The pilot did its job: it caught an
under-baked run rather than letting a transient state pass for equilibrium.

---

## Pilot v2: steps doubled to 30000, seeds expanded to 5 (100-104), 40 runs

Same matrix, `n=500` kept, `steps=15000 → 30000`, seeds `{100,101,102} → {100,...,104}`. Raw output:
`docs/report/2026-07-08-validation-gate-pilot-results_st30000.csv` (the `st15000` file is
untouched, so the two are directly comparable per seed). All 40 runs clean (0 assertion errors).
(Operationally: the first launch of this batch was interrupted mid-run — 8 of 40 folders had been
created but none had finished a single "Elapsed time" line; deleted those stale partial folders,
per `run.sh`'s "abort if the folder exists" behavior, and relaunched the full 40-run matrix, which
then completed cleanly.)

**Gate 1 (plateau) — trend is decaying but still not zero; do not treat this as resolved.**
Paired seed-by-seed comparison of `interactionCrossCuttingFraction`'s windowed Δ (15000-step run vs.
30000-step run, same seed) gives a mean ratio (30k-Δ / 15k-Δ) of **≈0.43** — the decline rate roughly
halved when steps doubled, so it *is* relaxing, but it has not gone to ~0, and the ratio is highly
variable across cells (0.4–1.2 for most, with `ws` showing wild swings including a sign flip, since
its Δ magnitudes are near the noise floor to begin with). **Reading:** this looks like slow
(sub-exponential / power-law-ish) relaxation rather than an approach to a clean plateau within a
practically reachable step budget — doubling again would likely still show a nonzero, if smaller,
Δ. **Practical implication for Step 3:** rather than chasing an ever-elusive single-point
"equilibrium" value, report a **late-window time-average** (e.g. mean over the last 20-30% of
steps) instead of the final-step snapshot for this metric family, and state the residual-trend
caveat explicitly — this is the same concern model-structure-review.md item 4 already raised about
cumulative interaction metrics, now with pilot evidence behind it.

**Gate 2 (hub persistence) — same qualitative story as the 15000-step pass, no new resolution.**
Extreme hubs still collapse to near-zero followers by end of run in nearly every cell; the moderate
hub's fate is still mixed (mostly collapses, occasionally holds ~1/3 of its initial base, e.g.
`dcsbm` seed100 114→93). Doubling steps did not change this pattern, which is itself informative:
whatever is driving hub collapse has mostly *already happened* by step 15000 (consistent with gate
1's finding that the *rate* of further change is slowing).

**Gate 3 (hub-attributable bridging) — more seeds, same qualitative pattern, plus a real
construct-validity caveat found.** With 5 seeds: `dcsbm` 3/5 nonzero (mean cross-camp fraction
0.489), `lfr` 1/5 (0.273), `random` 1/5 (0.900), `ws` **0/5** — `ws` is now cleanly zero across all
10 seed-runs tested between the two passes (5 distinct seeds × 2 durations), the strongest evidence
yet for the scale-free-dependency hypothesis, though `random` (also non-scale-free) showing one
nonzero seed keeps this from being a clean binary result.

**Caveat found while comparing runs:** for the *same* seed, the identical historical cascade events
(deterministic prefix — `lfr` seed102's count/fraction reproduced exactly, 0.272727, at both
durations) can still get a **different** `hub_cross_camp_fraction` between the 15k and 30k runs
(e.g. `random` seed100: 0.800 → 0.900 with the same `n_hub_mediated_cascades=11`/`valid=10`). Cause:
the analysis labels each relaying agent's "camp" using that run's **final-snapshot opinion**, not
the agent's opinion *at the time of the historical relay event* — so if an agent's opinion sign
drifts between step 15000 and step 30000, an identical past event gets reclassified. **This is a
real proxy-noise source in the current operationalization**, not a bug in the fix applied earlier
this file — it means "camp" as measured here is a noisy stand-in for camp-at-exposure-time. Before
the Step-3 freeze, either accept this as bounded noise (opinions are band-limited per the FJ
analysis in model-structure-review.md, so drift should be modest) or log opinion at cascade-event
time directly (a small addition to `Writer.logRepostCascade`) to remove the proxy entirely.

**Updated overall verdict:** gate 1 is relaxing but not resolved even at 2x steps — the honest
conclusion is that this model may not have a clean single-point equilibrium reachable within any
practical step budget, and the Step-3 measurement plan should build in a late-window average and
state that explicitly, rather than treating a longer run as eventually "solving" gate 1. Gates 2/3
are unchanged in their qualitative story with more data; gate 3's scale-free signal (`ws` zero
across 10 runs) is the strongest single piece of evidence produced so far, but `random`'s one hit
keeps it short of definitive.

---

## Calibration discussion: literature-pinnable vs. pure-scale parameters, and `MU_PARAM` removed

Went through the model's free parameters to sort them into (A) ones a reviewer will ask "why this
value" about, arguably groundable in prior literature, and (B) pure timescale/scale knobs with no
"correct" external value. User is handling (B) directly (to be swept/robustness-checked later, not
decided now). (A) status as of this session:

- **Settled:** `sbm_gamma=2.3` — matches Kwak et al. 2010's fitted Twitter follower-distribution
  exponent (2.276) closely; verified via WebSearch. `MINIMUM_BC=0.2` — this model's opinion space is
  [-1,1] (width 2) vs. the classic Hegselmann-Krause/Deffuant [0,1] convention, so
  `MINIMUM_BC`/2 ≈ ε=0.1, which sits in HK 2002's classic multi-cluster-fragmentation range;
  theoretically derived, not independently looked up. The initial truncated-Gaussian opinion draw
  (R12, no atoms at ±1) is separately justified on **methodological** grounds (don't build the
  outcome-of-interest — bimodality/polarization — into the initial condition; same logic as this
  project's own "knob, not assumption" litmus test), not a numeric citation.
- **Reframed, not directly pinned:** `sbm_pin`/`sbm_pout` (DC-SBM homophily). Direct import of a
  literature number (e.g. Bakshy/Messing/Adamic 2015's Facebook cross-cutting-exposure figures) is
  a category error — those are emergent outcome measurements, while `pin`/`pout` are structural
  generation parameters. Better use: treat published cross-cutting-exposure figures as a
  **calibration target** for this model's own initial `crossCuttingFraction`, not a value to copy in.
  Not yet acted on.
- **Still open, pending user's own literature check:** `INITIAL_STUBBORNNESS=0.8` (candidate anchor:
  Das/Gollapudi/Munagala 2014's empirical opinion-dynamics fit — existence confirmed via WebSearch,
  specific fitted values NOT confirmed, PDF parsing blocked this session by missing `poppler-utils`);
  `repost_prob=0.25` (candidate anchor: Bakshy et al. 2011 — same verification gap); the *magnitude*
  of the bc-decline/recovery asymmetry (`bc_dec`/`bc_inc` — Baumeister et al. 2001 supports the
  *direction* bad≫good only, not a ratio).

**Decision: removed `MU_PARAM` (marginal-utility posting-probability feedback) entirely, not just
gated off.** This was one of two simultaneously-active, uncoordinated posting-probability feedbacks
flagged as an unresolved either/or in `research-direction.md` §3 item 6 and
`2026-07-07-model-structure-review.md` item 6 (the other being `COMFORT_PP_FACTOR`'s
spiral-of-silence rule) — not a mere double-counted scale parameter, since the two mechanisms cut in
*opposite* directions for the paper's central claim (repost-driven reinforcement would make a
reposted moderate hub *more* vocal; spiral-of-silence would tend to *silence* a moderate hub exposed
to disagreement from both camps, directly undermining "vocal moderate conduit"). Reasoning for
removing rather than keeping and gating: the mechanism's original purpose — explaining hub growth —
is better served by the velocity-primary For-You recommender (`research-direction.md` §3 item 6),
which is the more realistic growth channel for a hub's audience; `receivedRepostCount` had no other
reader, so removing `updatePostProb()` cleanly removed the whole counter with it, not a partial fix.

**Implementation:** removed `Const.MU_PARAM`, `Agent.receivedRepostCount` (field + constructor init),
`Agent.receiveRepost()` (the Agent-level counter increment — **not** `Post.receiveRepost()`, an
unrelated, still-active per-post velocity-tracking counter feeding the For-You feed's ranking, left
untouched), `Agent.updatePostProb()`, and both call sites in `OpinionDynamics.evolve()`. Posting
probability is now driven solely by `COMFORT_PP_FACTOR` (spiral-of-silence) and the For-You feed's
velocity ranking (repost-count-driven hub growth, via `Post`'s own counter) — the two mechanisms no
longer compound. Verified: `grep -rn "MU_PARAM|receivedRepostCount|updatePostProb"` clean (only the
unrelated `Post.receiveRepost()` remains); full recompile clean; `ModelTests` 28/28 pass; smoke run
(`n=200, steps=1000`) 0 assertion errors.

---

## `repost_prob` calibration: literature-anchored bounds instead of a single pinned value

Traced the citation chain for the current default (`repost_prob=0.25`, inherited from
`Sasahara et al. 2021`'s own model, which cites `Qiu et al. 2017` Nature Human Behaviour —
subsequently retracted, but only for its Fig. 4d/5 model-fitting figures, not for the raw
empirical statistics used here). Found two independent problems, one of magnitude and one of
mechanics:

- **Mechanics mismatch (the bigger issue):** Qiu et al.'s `μ≈0.75` is `n_t/(n_t+n_r)` — the
  fraction of a user's *own posting output* that is original vs. retweet — used in their own model
  as a **single per-turn action choice** (post new **or** reshare one item, mutually exclusive).
  This codebase's `Agent.repost()` instead rolls an independent Bernoulli(`repostProb`) check **for
  every post in the feed** (`FEED_CAPACITY=10` per step), so the same "0.25" produces roughly an
  order of magnitude more repost actions per step than the source model. Confirmed independently by
  comparing this model's own cascade-depth distribution against `Kwak et al. 2010`'s empirical
  Twitter retweet-tree data: Kwak finds 95.8% of retweet trees have depth 1 (max depth 11 in their
  whole dataset); a pilot-v2 run (`n=500, steps=30000`) shows only 20.5% at depth 1, with cascades
  extending to **depth 191** — a single cascade in one run recruited 491 of 500 agents. Traced one
  such deep cascade manually: not a 2-node ping-pong loop (a real bug would look like that) but a
  genuine broad branching tree, consistent with the mechanics mismatch above plus the apparent
  absence of any per-lineage "this is stale, stop relaying it" decay for the organic (non-algorithmic)
  feed path (`PostCash` does FIFO-evict on overflow, but whether that's tight enough to bound
  cascade depth over a 30000-step run was not confirmed).
- **Magnitude, independently corroborated:** `Meng et al. 2025` (PNAS) directly measures retweet
  probability as a hazard rate `ψ(x)` = (fraction of not-yet-retweeted users who retweet at their
  x-th exposure), fit from WeChat data: **scale is typically ~10⁻³**, and the shape is not
  monotonic — `ψ(x)` rises with exposure (social reinforcement) then peaks around `x*=2–3` (55% of
  messages) before saturating or dropping sharply. Neither this codebase nor Sasahara/Qiu's models
  track per-agent per-lineage exposure count at all, so this reinforcement-then-decay shape cannot
  currently be represented regardless of the flat probability chosen.
- **Firdaus, Ding, Sadeghian 2018** (retweet-prediction survey, *Online Social Networks and Media*)
  checked for a usable base-rate number: none found — it surveys *predictive features* (sentiment,
  follower count, hashtags) relative to retweet likelihood, not an absolute per-exposure rate.
  Qualitatively useful (negative-sentiment content retweets more, matching this model's
  reactance-adjacent design) but not a calibration anchor.

**Decision: do not import a single external number; record reference bounds for a sensitivity
sweep instead.**
- **Floor reference:** `Meng et al. 2025`'s ψ≈10⁻³ — but this is an *unconditional* population
  average across all message topics/salience levels on WeChat, whereas `repostProb` in this model
  only ever gates content that has **already passed the bounded-confidence tolerance check**
  (already topically relevant/agreeable) — a pre-filtered, higher-relevance subset. The true
  analogous rate is expected to sit above this floor, plausibly closer to `ψ(x*)` for
  higher-salience content, which the WeChat-population average does not resolve.
- **Ceiling reference:** current default `0.25`, inherited from Sasahara/Qiu — now understood to be
  inflated by the per-feed-item mechanics mismatch above, so treated as an *upper* bound, not a
  best estimate.
- **Planned sensitivity sweep:** `repost_prob ∈ {0.01, 0.10}` (already CLI-sweepable via the
  existing `repost_prob=` key — no code change needed) against the current default `0.25` as a
  reference point, checking whether the headline structural-separation / hub-bridging results
  (the Step-2 gate metrics) are qualitatively robust across this range before Step-3 freeze. Not
  yet run.
- **Deferred, larger fix (not undertaken now):** implementing per-agent per-lineage exposure
  counting so `repostProb` could follow Meng et al.'s rise-then-decay shape instead of a flat
  constant — would likely address the cascade-depth mismatch more directly than a flat-rate change
  alone, but is a real mechanism addition, out of scope for the current calibration pass.

---

## Metric fix: camp classification now uses opinion-at-event-time, not a final-snapshot proxy

Before sweeping any more parameters, addressed the measurement-stability issue found earlier in
this file (gate 3's `hub_cross_camp_fraction` changing for the *identical* historical event —
e.g. `random` seed100 0.800→0.900 — between a 15000-step and a 30000-step run of the same seed).
Root cause: the relaying agent's "camp" was looked up from `agent_snapshot_final.csv`, i.e. that
run's end-of-simulation opinion, not the agent's opinion *at the moment they performed that
historical relay*. Since opinions drift under FJ assimilation, a longer run can push the same
agent's opinion across zero between the two snapshots, silently reclassifying a past event.

**Fix:** `Writer.logRepostCascade` now takes the relaying agent's own opinion at call time and
writes it as a new `relayerOpinion` column in `posts/repost_cascades.csv` (header:
`step,rootPostId,parentPostId,postId,author,relayer,depth,conveyedOpinion,relayerOpinion`); the
call site in `OpinionDynamics.evolve()` passes `agent.getOpinion()` (the agent currently executing
the repost, at that exact point in the step). `scripts/validation_gate_pilot_analysis.py`'s
`gate3_hub_bridging` now classifies camp from `sign(relayerOpinion)` directly — no join, no
dependence on run duration — falling back to the old final-snapshot proxy only for pre-existing
cascade CSVs that lack the new column (flagged via a `camp_source` field in the analysis output).

**Verified:** recompile clean, `ModelTests` 28/28 pass, smoke run (`n=200, steps=500`) shows
`relayerOpinion` populated correctly in `repost_cascades.csv`. Not yet re-run against the existing
pilot-v1/v2 result folders (those predate this column, so gate 3 numbers reported earlier in this
file still used the final-snapshot proxy) — a fresh pilot pass after this fix will produce
directly comparable, duration-independent `hub_cross_camp_fraction` values.

---

## Tier-D knobs migrated off `Const` onto `SimParams`/CLI (2026-07-09)

Before the OAT robustness sweep below, found that `FEED_CAPACITY`, `FOLLOW_PROB`, `INITIAL_PP`,
`MAX_PP`, `MIN_PP`, `COMFORT_PP_FACTOR` were still plain `Const` literals with no CLI key at all —
an oversight from the R20 migration (`Const.java`'s own docstring says every runtime-tunable
parameter belongs on `SimParams`). Added `feed_capacity`, `follow_prob`, `initial_pp`, `max_pp`,
`min_pp`, `comfort_pp` as `ExperimentConfig`/`SimParams` fields + CLI keys (defaults unchanged,
still literally `Const.FEED_CAPACITY` etc., so this is additive, not default-changing) and
re-pointed the read sites (`AdminOptim.AdminFeedback`, `Agent`'s constructor/`updateMyself`/
`follow`/`makePost`) from `Const.X` to `p.x()`. Tagged in `tag()` only when non-default
(`_fc-`/`_folp-`/`_ipp-`/`_mxpp-`/`_mnpp-`/`_cpf-`). Verified: recompile clean, `ModelTests` 28/28
pass, smoke run with `feed_capacity=20 follow_prob=0.5 comfort_pp=1.3` shows the values took effect
(folder tag `..._fc-20_folp-0.500_cpf-1.300`, confirming the CLI keys actually reach the read
sites, not just the config object).

---

## OAT robustness/calibration sweep — design (Tier B/C/D)

Per the 3-tier triage discussed this session: Tier A (P_u, network type, scale-vs-position) is
Step-3 experiment scope, deliberately not touched now — "the model needs to stand on its own as
credible first." This sweep covers Tier B (light calibration check), Tier C (recommender vs. a real
degree-distribution target), Tier D (confirm-or-refute inertness of scale knobs).

**Scale (deliberately lighter than the validation-gate pilots above, since this is OAT screening,
not a precision run):** `n=300, steps=15000`, seeds `{200, 201, 202}`, network=dcsbm (baseline),
`n_mod=1, extreme=sym, channel=both` — same fixed background as the validation-gate pilots.

**Design: one-at-a-time (OAT).** Each cell changes exactly one parameter from the baseline
(current defaults); baseline itself is also run for reference. Not a full factorial — with ~18
candidate values across 3 tiers, factorial is infeasible; OAT answers "does this knob move the
Step-2 gate metrics at all," which is the actual question for Tier D and a first pass for Tier B/C.

| Tier | Parameter | Baseline | Alt. values tested | Literature anchor |
|---|---|---|---|---|
| B | `repost_prob` | 0.25 | 0.01, 0.10 | Meng et al. 2025 (floor, ψ≈10⁻³, population avg.); Sasahara/Qiu (ceiling, mechanically inflated — see above) |
| B | `bc_inc` | 0.0 | 0.001, 0.005 | Baumeister 2001 / Rozin & Royzman 2001 (direction only, no magnitude) |
| B | stubbornness (flat, via `stub_dist=uniform stub_min=X stub_max=X`) | 0.8 | 0.6, 0.95 | Das et al. 2014 (qualitative: stable per-user trait; no numeric anchor found) |
| B | `sbm_pout` (pin=0.08 held) | 0.002 | 0.005, 0.01 | Bakshy/Messing/Adamic 2015, Boutyline & Willer 2017 (as a *calibration target* for initial `crossCuttingFraction` ≈ 20-25%, not a direct value import) |
| C | `feedAlgoShare` (alpha) | 0.0 | 0.3, 0.6 | Kwak et al. 2010 (target: fitted final-network degree exponent should stay near γ≈2.3, the same anchor already used for `sbm_gamma`); also the direct test of whether hub growth actually occurs via the recommender now that `MU_PARAM` is removed |
| D | `feed_capacity` | 10 | 5, 20 | none (pure scale; confirming inertness) |
| D | `follow_prob` | 0.1 | 0.05, 0.2 | none |
| D | `comfort_pp` | 1.1 | 1.05, 1.2 | none (now the *sole* posting-probability feedback since `MU_PARAM` removal — worth checking even though "scale") |
| D | `max_pp` | 0.5 | 0.3, 0.8 | none |

18 non-baseline cells + baseline = 19 configurations × 3 seeds = 57 runs.

**Readout metrics:** the existing Step-2 gate battery (`opinionAssortativity`, `crossCuttingFraction`,
`interactionCrossCuttingFraction`, `signModularity`, `hub_cross_camp_fraction`/
`n_hub_mediated_cascades` — now using the event-time `relayerOpinion` fix) plus, for the Tier-C
`alpha` cells specifically, a power-law fit of the final degree distribution (`powerlaw` package,
already in `requirements.txt`) compared against the `sbm_gamma≈2.3` / Kwak et al. `γ≈2.276` target,
and the moderate hub's `followers_t0` vs `followers_final` (growth, not just persistence).

Results and conclusions recorded in the next entry after the runs complete.

---

## Two bugs caught before the sweep produced usable data (both fixed)

The first launch of the 57-run OAT sweep silently produced bad data; caught it before analyzing
anything by checking logs, not by trusting a clean exit code.

1. **`sbm_pin`/`sbm_pout`/`sbm_k`/`sbm_gamma`/`sbm_deg` were never added to `tag()`.** Two OAT cells
   differing only in `sbm_pout` (same seed, same everything else) produced the *identical* result
   folder name, so the second one hit `run.sh`'s own R26 "abort if the folder already exists" guard
   and silently wrote nothing (`logs/oat_sbmpout-001_seed200.log` confirmed the `[ABORT]` line).
   Fixed: `ExperimentConfig.tag()` now tags all five DC-SBM structural params when non-default
   (`_sbmk-`/`_sbmpin-`/`_sbmpout-`/`_sbmgamma-`/`_sbmdeg-`).
2. **macOS's stock `/bin/bash` is 3.2** (pre-GPLv3, no updates from Apple) and has two relevant gaps
   the sweep script hit: (a) `"${array[@]}"` on an **empty** array throws "unbound variable" under
   `set -u` — the `baseline` cell's empty `extra` token list crashed *that one iteration* silently
   (loop continued, so the other 18 cells looked fine, but 0 of 3 baseline runs ever executed);
   (b) `wait -n` (bash ≥4.3) doesn't exist in 3.2, though this one wasn't hit yet since the array bug
   surfaced first. Fixed: `run_oat_sweep.sh` now branches on `[ ${#extra[@]} -gt 0 ]` before ever
   expanding the array, and replaced `wait -n` with a plain `sleep 1` polling loop against
   `jobs -rp | wc -l`.

**Both caught by checking `logs/oat_*.log` for `ABORT`/missing files after a first launch, before
trusting the "ALL ... COMPLETE" final echo** — the script's own exit code was clean in both cases;
neither bug caused a nonzero exit. Cleaned up the 21 partial/ambiguous result folders from the first
(buggy) launch and relaunched from a clean state after both fixes; recompile clean, `ModelTests`
28/28 pass, and a targeted smoke test confirmed both fixes independently before the full relaunch.

**Third bug, caught after the (clean, 57/57) sweep completed:** `feedcap-20`'s aggregated metrics
were *bit-identical* to `baseline`'s to 6 decimal places across all 3 seeds — far too exact to be a
real "no effect" finding. Cause: `Agent`'s constructor set `postCash`'s real capacity via a
**second, independent hardcoded literal** (`setNumOfPosts(10)`), never touched by the Tier-D
migration above (which only fixed `AdminOptim.AdminFeedback`'s read site). Since `postCash` is the
pool `AdminFeedback` draws the visible feed from, requesting `feed_capacity=20` when the underlying
cache is hard-capped at 10 has no effect (the cache is the binding constraint); `feed_capacity=5` (below
10) *did* show a real effect already, which is exactly the asymmetric signature this kind of bug
produces. Fixed: `setNumOfPosts(10)` → `setNumOfPosts(p.feedCapacity())`. Recompiled, `ModelTests`
28/28 pass, re-ran only the 3 affected `feedcap-20` seeds — now clearly different from baseline.
See full results below; this is the corrected number.
