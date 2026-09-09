# 2026-07-07 — Model-Revision Requirements Specification

**Status:** approved requirements, ready for implementation.
**Source:** cold code-grounded review of the model core (2026-07-07, reviewer session), conducted
without reference to prior design memos. This document translates that review into implementable
requirements for a separate implementation agent.
**Scope:** model/code changes only (Tier 1 + 2 + 3 of the review). The simulation plan
(factor levels, run counts) is out of scope. Empirical-anchoring *analysis* is out of scope, but
the *logging* it requires is in scope (R19).
**Second pass (same day):** legacy-simplification / instantiability requirements R20–R26 added
after a usability & performance audit of `Writer`, `Network`, `AssertionCheck`, `run.sh`, and
`lib/` (user request: reduce friction for other users of the codebase). R20/R21 change the
parameter- and metric-plumbing patterns and **must land before** the new dials and metrics of
Phases 2–4; the phase plan in §7 is updated accordingly.

---

## 0. Locked decisions (user-approved 2026-07-07)

| # | Decision | Choice |
|---|----------|--------|
| D1 | Scope | Tier 1 + 2 + 3, all requirements below |
| D2 | Affective-axis operationalization | **Both** behavioral proxies (R1) and an explicit affect state variable (R2) |
| D3 | Intervened-hub opinion | **Full pin**: `stubbornness = 1.0` and `opinion = intrinsicOpinion` set immediately at t=0 |
| D4 | Comfort-gate radius | **Fixed `Const.MINIMUM_BC`** (perceptual radius by design); fix the contradictory comment, not the code |

---

## 1. Global conventions (apply to every requirement)

**G1 — Backward compatibility by default.** Every new mechanism ships behind a config parameter
whose default reproduces current behavior, *except* where the current behavior is classified as a
defect (R4 hub pinning, R5 comment fix, R12 init-opinion truncation, R16a disagreement-metric
exclusion — these change the default and are flagged `[default-changing]`).

**G2 — Config plumbing.** After R20 lands, every new parameter is defined **once** in the
instance-scoped params object (field + default + CLI key + tag rule co-located); it must be
(a) parseable as a `key=value` CLI token, (b) appended to `tag()` **only when it differs from the
fixed literal default** (do NOT compare against runtime-mutated values — see the documented
2026-06-26 folder-collision bug in `ExperimentConfig.java:66-71`), and (c) written into
`run_config.csv`. If a requirement is implemented before R20, follow the legacy pattern
(`Const` static + `ExperimentConfig` field) and migrate it during R20.

**G3 — RNG discipline.** After R15, all new stochastic mechanisms must draw from the *dynamics*
stream. Note in the implementation report every change that alters RNG consumption order (these
break bitwise reproducibility with old runs; that is accepted — see V1).

**G4 — Metrics.** After R21 lands, every new per-step metric is a single named `put` into the
metrics row (no `RESULT_LIST` entry, no `Writer` field/setter/switch-case). All population
metrics exclude `target` hubs unless stated. **R21 must therefore precede R1, R2, R6, R10, R16**
— do not add ~15 new columns through the legacy 5-edit pipeline.

**G5 — Documentation.** Each requirement, when implemented, gets a dated entry in the active
`docs/report/` file recording what changed, the config key(s), and the default.

---

## 2. Phase 1 — Foundations & defect fixes (do first)

### R15 — Separate RNG streams `[foundation — implement before everything else]`
**Problem.** One global `Random` serves network generation, intervention, and dynamics
(`rand/randomGenerator.java`); the network cannot be held fixed while varying dynamics noise, and
any parameter change that alters network-generation draws silently reseeds the dynamics.
**Requirement.**
- Refactor `randomGenerator` to expose three named streams: `network()`, `intervention()`,
  `dynamics()`. Seeding: `net_seed` (new CLI key, default = `seed`), intervention and dynamics
  derived from `seed` with fixed distinct offsets (e.g. `seed`, `seed + 0x9E3779B9`), or via
  `SplittableRandom.split()` — implementer's choice, but deterministic and documented.
- Migrate call sites: all `network/*` generators → `network()`; `InterventionSetup` → `intervention()`;
  everything else (agent behavior, shuffles, feeds) → `dynamics()`.
**Acceptance.** Same `net_seed` + two different `seed` values ⇒ identical initial network
(assert equal degree-sequence hash); different `net_seed` + same `seed` ⇒ different networks.

### R4 — Full hub pinning `[default-changing]`
**Problem.** `InterventionSetup.apply` sets only `intrinsicOpinion`; with μ=0.8 an "extreme hub at
±1" actually broadcasts ≈±0.8 and drifts, and hubs broadcast their stale pre-intervention opinion
until their first non-empty-feed update. Docs claim "exogenously fixed" — mismatch.
**Requirement.**
- In `InterventionSetup.apply`, for every intervened hub (extreme and moderate):
  `setIntrinsicOpinion(op)`, `setOpinion(op)`, `setStubbornness(1.0)`.
- Update the C3 comment in `OpinionDynamics` and the class Javadoc of `InterventionSetup`: the
  claim "exogenously fixed" is now literally true.
- **Interaction warning (must be documented in code comment):** with relay strength coupled to
  stubbornness (see R3), a pinned hub (μ=1) relays fully flattened content (conveyed = hub
  opinion). For a moderate hub this means relays are pure-neutral. This is the intended
  "maximal conduit reframing" default; the global `s_relay` override (R3) is the dial to weaken it.
**Acceptance.** At step 1, every hub's emitted post opinion equals its assigned opinion exactly;
hub opinion trajectory is constant over the whole run.

### R3 — Restore the conduit dials: `P_r^out` and `s_relay`
**Problem.** The out-of-BC relay probability was collapsed into `repostProb` and relay-distortion
strength into `stubbornness` (2026-06-26 parsimony decision). Out-of-BC relaying *is* the paper's
central mechanism; collapsing its rate removes the dose–response dial.
**Requirement.**
- `Agent.repost()`: per feed post, repost probability = `repostProb` when
  `|Δopinion| < bc`, else `P_ROUT` (new: `Const.P_R_OUT`, CLI `p_r_out=`, default **coupled**:
  sentinel `-1` ⇒ use `repostProb`).
- `Agent.relay()`: distortion strength = `S_RELAY` (new: `Const.S_RELAY`, CLI `s_relay=`,
  default **coupled**: sentinel `-1` ⇒ use the agent's own `stubbornness`). When set (≥0) it
  applies to **all** agents, including pinned hubs.
- `tag()` additions: `_prout-…` and `_srel-…` only when non-default (G2).
**Acceptance.** Defaults reproduce current coupled behavior (identical decision logic, allowing
RNG-order differences per G3). `p_r_out=0` disables out-of-BC relaying entirely;
`s_relay=0` yields verbatim relays (conveyed == original).

### R5 — Comfort-gate comment fix `[default-changing: comment only]`
**Requirement.** In `Agent.updateMyself` (currently lines 261-262): keep
`Const.MINIMUM_BC` as the comfort radius (per D4); replace the contradictory comment with one
stating: *fixed perceptual comfort radius by design — keeps the vocality mechanism
(comfort ⇒ postProb boost) active even when dynamic bc has collapsed, so intolerant extremists
remain vocal (vocal-minority mechanism); deliberately NOT the dynamic bc.*
**Acceptance.** Code and comment agree; no behavioral change.

### R12 — Truncated (resampled) initial opinions `[default-changing]`
**Problem.** `Math.max(-1, Math.min(1, gaussian*0.6))` puts ~4.8% point masses at exactly ±1 —
manufactured boundary extremists.
**Requirement.** Rejection-sample `N(0, INITIAL_OPINION_STD)` until `|x| ≤ 1`
(draws from the *dynamics* stream — or a dedicated `init` use of it — per G3). Config
`init_opinion={truncate|clip}`, CLI `init_op=`, default `truncate`.
**Acceptance.** With `truncate`, no agent initializes at exactly ±1 across 10 seeds
(excluding intervened hubs).

---

## 3. Phase 2 — Affective axis & event instrumentation (Tier 1 core)

### R0 — Sanction/exposure event instrumentation `[prerequisite for R1, R2, R10]`
**Requirement.** Introduce a lightweight per-step event collector (e.g. an `EventLog` object
passed into agent methods or returned from them — implementer's choice, but no O(N²) allocations
per step). It must capture, per step, with actor/target ids:
- unfollow events, block events (currently created inside `Agent.unfollow()` and the
  capacity-eviction branch of `Agent.follow()` — eviction counts as an unfollow event, tagged
  `eviction`);
- repost events (reposter, original author, original opinion, conveyed opinion, triggering feed
  post's relay-flag — see R19 for Post fields);
- per-agent per-step out-group exposure counts: number of feed posts read whose opinion sign
  differs from the reader's (and, separately, whose |Δopinion| > bc), needed as the denominator
  for propensity metrics.
"Out-group" is defined by `sign(opinion)` of reader vs. post content, consistent with
`computeCrossCuttingFraction`.

### R1 — Behavioral hostility metrics (model-invariant proxies)
**Requirement.** New per-step metrics (all exclude target hubs, per G4):
1. `outGroupBlockPropensity` = (block + unfollow events this step whose target's *post content*
   was opposite-sign) / (total out-group posts read this step). This is
   P(sanction | out-group exposure) — a propensity, not a raw count, so it separates behavioral
   hostility from exposure composition.
2. `outGroupSanctionRate` = same numerator / (number of active agents this step) — raw-rate companion.
3. `crossRepostRate` = reposts whose original author is opposite-sign / total reposts this step
   (based on **original** post opinion, before relay distortion).
4. `blockCount`, `unfollowCount`, `evictionCount` — raw per-step counts (replaces/extends the
   existing follow/unfollow counters; keep existing columns for continuity).
**Acceptance.** Metrics present in output CSV; sanity check on a short run: propensity ∈ [0,1];
with `p_u=0` and eviction impossible, propensity = 0.

### R2 — Explicit affect state variable (hostility thermometer)
**Requirement.** New per-agent variable `hostility h ∈ [0,1]`, init `0.0`. **Read-out only in
v1: h must not feed back into any behavior** (no gating, no probabilities) — this is what breaks
the mechanism/outcome circularity. Two update channels, both applied in `updateMyself` /
the relay path:
1. **Contact valence:** for each post read, if `|postOpinion − opinion| > Const.MINIMUM_BC`
   (fixed radius, per D4 — deliberately NOT the dynamic bc, so h is not isomorphic to bc):
   `h += LAMBDA_UP * (1 − h)`; else `h *= (1 − LAMBDA_DOWN)`.
2. **Misrepresentation grievance:** when one of the agent's own posts is relayed with
   `|conveyed − original| > THETA_DIST`, the *author's* `h += LAMBDA_MIS * (1 − h)` (event
   available from R0/R19 instrumentation; apply at most once per relay event).
Constants (all `Const`, CLI keys, swept-able): `LAMBDA_UP` (`l_up=`, default 0.005),
`LAMBDA_DOWN` (`l_down=`, default 0.005), `LAMBDA_MIS` (`l_mis=`, default 0.05),
`THETA_DIST` (`theta_dist=`, default 0.4). Defaults are provisional; they only scale the
readout, not the dynamics, because h has no feedback.
**Metrics:** `meanHostility`, `hostilityVar`, plus per-opinion-bin means
(`hostility_0..4`, same binning as `cRateMean_*`).
**Documentation note (put in code comment):** channel 1 mirrors bc's exposure-valence logic by
construction (contact theory); the anti-tautology defenses are (a) no behavioral feedback,
(b) the misrepresentation channel, (c) fixed radius. The primary anti-tautology axis remains R1.
**Acceptance.** h ∈ [0,1] always; with `l_up=l_mis=0`, h stays 0; hostility columns in CSV.

### R10 — Misattribution as a named, measured mechanism
**Problem.** Relays keep the original author's ID while carrying (by default) ~μ-reframed content;
agents sanction the original author for the reposter's distortion. Currently an unremarked side
effect; it is plausibly the Type-2 engine and must be measured, and switchable off.
**Requirement.**
1. `Post` gains fields: `rootPostId`, `parentPostId`, `relayerId` (−1 for originals), `depth`
   (0 for originals), and `isRelay()`. `Agent.relay()` populates them (see also R19).
2. New metrics: `relayDistortionMean` = mean `|conveyed − original|` over this step's relays;
   `misattributedSanctionCount` = sanction events (R0) whose triggering feed post `isRelay()`
   and whose original author is the sanction target.
3. New config `relay_attrib={original|reposter}` (CLI `rel_attrib=`, default `original` = legacy).
   With `reposter`, the relayed copy's `postUserId` is set to the relayer: sanctions/follows then
   target the relayer; conduit hubs lose their sanction immunity. This is the neutralization arm.
**Acceptance.** Default output unchanged in behavior (fields are additive); with
`rel_attrib=reposter`, blocks triggered by relays target relayers (verifiable in a unit test).

---

## 4. Phase 3 — Mechanism dials & robustness arms (Tier 2)

### R6 — Repost-volume calibration support
**Requirement.** `REPOST_PROB` becomes config (`repost_prob=`, default 0.25 = legacy). Add
per-step metrics `originalPostCount` and `repostCount` (from R0), so the repost:post ratio is
observable per run (empirical target band ≈ 1–3:1; calibration itself is experiment-side).
Congruence-biased sharing is covered by R3 (`p_r_out < repost_prob` is the congruence-bias arm).

### R7 — Sweepable tolerance decay
**Requirement.** `BC_DEC_RATE` non-final, CLI `bc_dec=`, default 0.99 = legacy, `tag()` per G2.
Implementation report must state the derived saturation timescale formula
(active-steps to floor ≈ ln(MINIMUM_BC/BOUNDED_CONFIDENCE) / (feedSize·ln(BC_DEC_RATE)) as an
upper bound) so experimenters can reason in exposure units.

### R8 — Block forgetting
**Problem.** Blocks are permanent and unbounded ⇒ monotone shrinkage of every agent's reachable
content space ⇒ a hub-independent drift toward separation confounding the x-axis.
**Requirement.** Geometric forgetting: each step an agent is active, every entry in its
`unfollowList` is lifted independently w.p. `P_FORGET` (CLI `p_forget=`, default `0.0` = legacy
permanent). Draw from dynamics stream. Note: lifting a block does not restore a follow edge.
Implementation may iterate a per-agent set of blocked ids (not the full boolean array) for
efficiency.
**Acceptance.** `p_forget=0` reproduces legacy; with `p_forget=0.01`, expected block lifetime
≈ 100 active steps (unit-testable in expectation).

### R9 — Probabilistic capacity eviction + initial-condition consistency
**Requirement.**
1. In `Agent.follow()`'s over-capacity branch, replace deterministic evict-max-disagreement with
   softmax: `P(evict k) ∝ exp(EVICT_BETA · |o_k − o_i|)` over current followees. CLI
   `evict_beta=`, sentinel `-1` = legacy deterministic argmax (default). `evict_beta=0` = uniform
   random eviction.
2. New config `init_prune={none|trim}` (CLI `init_prune=`, default `none` = legacy). With `trim`,
   after network generation each agent with out-degree > `MAX_FOLLOW_CAPACITY` randomly removes
   followees (network stream) down to the cap, so the t=0 condition satisfies the model's own
   constraint. Document that `none` leaves most agents permanently over-cap (eviction fires on
   nearly every follow).
**Acceptance.** Sentinel reproduces legacy choice on a fixed fixture; `trim` yields max
out-degree ≤ cap at t=0.

### R11 — Windowed velocity + hop-knob honesty
**Requirement.**
1. Config `velocity_mode={cumulative|windowed}` (CLI `vel_mode=`, default `cumulative` = legacy).
   `windowed`: score = (likes gained since the previous ranking pass) / (steps elapsed since it),
   normalized by `(followers+1)` as now. Implement by storing per-post `likesAtLastRank` /
   `stepAtLastRank` (updated inside `rankByVelocity`).
2. Add a code comment at `Const.FEED_HOP_H` and in `AdminOptim.ensureReachable`: at current
   density (undirected degree ≈ 35, N=1000), h ≥ 2–3 is effectively global; the knob only binds
   at h=1 or on much sparser graphs.
**Acceptance.** `cumulative` output logic unchanged; `windowed` demotes a stalled early-burst
post below a currently-rising one in a constructed unit test.

### R13 — Heterogeneous stubbornness (robustness arm)
**Requirement.** Config `stub_dist={const|uniform}` with `stub_min=`, `stub_max=`
(defaults: `const` at 0.8 = legacy; for `uniform`, suggest 0.4–0.9). Draw at agent construction
from dynamics stream. Note interactions in code comments: stubbornness is also the coupled relay
strength (R3) and is overridden to 1.0 for pinned hubs (R4) *after* sampling.

---

## 5. Phase 4 — Craft, metrics, scaling, logging (Tier 3)

### R14 — Dead-mechanism removal
**Requirement.** Remove (do not quarantine): `Agent.like()` (never called — "likes" are reposts
throughout), `AdminOptim.recommendPostQueue` + `addRecommendPost` + `MAX_RECOMMENDATION_POST_LENGTH`,
`AdminOptim.getManipulationTarget` (contains `System.exit(0)`), `Const.TARGET_DIRECTION`,
`Const.FOLLOWER_THRESHOLD`, `Const.INCREMENT_PU/DECREMENT_PU/INCREMENT_PP/DECREMENT_PP`,
`admin/ExpIntervention.java` (entire class — superseded by `InterventionSetup`, zero references),
`Analysis.computeFeedVariance`/`setFeedList`/`clearFeedList` if unreferenced. Rename
`recievedLike*` → `receivedRepost*` (Post) and `recievedLikeCount` → `receivedRepostCount`
(Agent) to make the semantics honest; update `updatePostProb` comment ("reposts", not "likes").
`POST_COST` stays (real knob, documented default 0).
**Acceptance.** Project compiles; no unreachable mechanism code in `agent/`, `admin/`,
`dynamics/`; grep for `recieved` returns nothing.

### R16 — Metric hygiene
1. `computeDisagreement`: skip edges touching target hubs (align with every other metric)
   `[default-changing]`.
2. Add Sarle's bimodality coefficient `b = (g1² + 1) / (g2 + 3(n−1)²/((n−2)(n−3)))` on non-target
   opinions (`bimodalityCoeff` column); keep kurtosis.
3. Windowed interaction graph: every `INTERACTION_WINDOW` steps (config, default 5000) snapshot
   `repostNetworkCumulative`; windowed metrics = assortativity / cross-cutting on
   (current − previous snapshot). New columns `interactionAssortativityW`,
   `interactionCrossCuttingFractionW`.
4. Evolved-graph sign-partition modularity: Newman directed modularity of the
   `sign(opinion)` partition on the current follow graph, computed every 5000 steps alongside the
   gexf export (O(m) via adjacency lists; do NOT densify). Written to a side CSV
   (`metrics/modularity.csv`: step, Q_sign).
5. Feed-order honesty: rename the "chronological" stream (comments + variable names) to
   `randomRecent`; add config `feed_order={random|recent}` (CLI `feed_order=`, default `random` =
   legacy shuffle-then-take; `recent` = take the most recently arrived posts from cash).

### R17 — Configurable scale & duration
**Requirement.** `NUM_OF_USER` and `MAX_SIMULATION_STEP` become non-final, CLI `n=` and `steps=`
(defaults 1000 / 40000). Audit for hidden N-dependencies (e.g. `Agent.NUM_OF_AGENTS`,
array sizing in `OpinionDynamics`, `AdminOptim`, `AssertionCheck`, gephi exporters) — all must
size from the runtime value.
**Memory note (must be checked, not necessarily refactored):** `repostNetwork` +
`repostNetworkCumulative` are dense `int[N][N]` (≈ 200 MB at N=5000) and `Network` holds a dense
`double[N][N]`. Requirement: N=2000 must run in default JVM heap; if N=5000 is infeasible,
document the bound in the implementation report and (optionally) switch repost matrices to
sparse maps behind the same accessor.
**Acceptance.** `n=500` and `n=2000` runs complete and produce consistent output schema.

### R18 — Block–opinion correlated initialization
**Requirement.** Config `rho_block=` ∈ [0,1] (default 0 = legacy independence). With K communities
from `DCSBMNetwork.getCommunityAssignments()`, assign community means `m_c` equally spaced on
`[−rho_block, +rho_block]` (K=4 ⇒ {−ρ, −ρ/3, +ρ/3, +ρ}); agent i's intrinsic opinion ~
truncated `N(m_{c(i)}, INITIAL_OPINION_STD)` (truncation per R12). Wire community assignments from
the network object into agent initialization in `OpinionDynamics.setAgents` (only defined for
DC-SBM; other generators require `rho_block=0`, enforce with a clear error).
**Acceptance.** `rho_block=0` reproduces legacy distribution; `rho_block=0.8` yields initial
cross-cutting fraction well below 0.5 (sanity test).

### R19 — Cascade logging (empirical-anchor enabler)
**Requirement.** Using the R10 Post fields, buffer-write every relay event to
`posts/cascades.csv`: `step, rootPostId, parentPostId, postId(new relay copy), rootAuthor,
relayer, depth, originalOpinion, conveyedOpinion`. Config `log_cascades={true|false}`
(default true; flag exists to cap disk usage on huge sweeps). This enables offline cascade-size /
structural-virality analysis (Goel 2016, Vosoughi 2018 comparison) without further code changes.
**Acceptance.** Depths chain correctly for a relay-of-a-relay in a unit test; file written and
parseable.

---

## 5b. Phase 1.5 — Legacy simplification & instantiability (R20–R26)

Added after a second-pass audit (user request): reduce the friction that makes the codebase
awkward for anyone besides its author, and remove per-step performance sinks. R20/R21 are
load-bearing for the rest of this spec (they change how parameters and metrics are added);
R22/R23 are correctness-preserving refactors covered by V1; R24–R26 are usability hygiene.

### R20 — Instance-scoped parameters (kill the mutable `Const` statics) `[foundation]`
**Problem.** `Const` is a global bag of `public static` fields, several non-final; `main()`
mutates them from `ExperimentConfig` before constructing the simulator
(`OpinionDynamics.java:292-297`). Consequences: (a) one JVM can only ever run one configuration —
parallelism is forced to the `run.sh` "10 JVMs × 2 GB heap" pattern and in-process sweeps/tests
are impossible; (b) parameter definitions are split arbitrarily between `Const` and
`ExperimentConfig`, so adding one parameter takes edits in up to five places (Const field,
ExperimentConfig field, `fromArgs` case, `tag()`, `main()` assignment); (c) test isolation is
impossible (state leaks between runs).
**Requirement.**
- Introduce an immutable instance class (suggested name `SimParams`) that carries **every**
  runtime parameter (everything now in `ExperimentConfig` plus every mutable `Const` field, plus
  the genuinely-tunable finals such as `REPOST_PROB`, `BC_DEC_RATE`, `MAX_SIMULATION_STEP`,
  `NUM_OF_USER`, feed constants). Built by the CLI parser (absorb `ExperimentConfig.fromArgs`
  and `tag()` into it or keep `ExperimentConfig` as the builder — implementer's choice).
- `OpinionDynamics`, `Agent`, `AdminOptim`, `Analysis`, `Writer`, network generators, and
  `InterventionSetup` receive the params object (constructor injection; `Agent` may hold a
  reference — one per-agent pointer, no copying). No class reads a mutable static for a runtime
  parameter afterward.
- `Const` shrinks to true physical constants (bin counts, result-folder layout strings) —
  everything left in it must be `final`.
- Together with R15 (instance-scoped RNG streams passed alongside the params object), this makes
  `new OpinionDynamics(params).evolve()` self-contained.
**Acceptance.** `grep -rn "public static [^f]" src/constants/Const.java` returns nothing
(no non-final statics); two `OpinionDynamics` instances with different params constructed in one
JVM produce independent, correct runs (smoke test: sequential is sufficient, thread-safety is
NOT required).

### R21 — Metrics pipeline replacement (retire `RESULT_LIST`) `[foundation — before R1/R2/R6/R10/R16]`
**Problem.** Adding one metric currently requires five coordinated edits (`Const.RESULT_LIST`
string, `Writer` field, `Writer` setter, `appendSingleMetric` switch case, `exportStepMetrics`
call), the binned columns are resolved by parsing the trailing `_N` off the key string at write
time (`Writer.java:203-226`), and a typo in any key produces a **silently empty column** instead
of an error. This spec adds ~15 columns; the legacy pipeline would roughly double that work and
its failure mode is invisible.
**Requirement.**
- Replace with an ordered map-based row: a `MetricsRow` (thin wrapper over `LinkedHashMap
  <String, Number>`) that `Analysis`/`OpinionDynamics` fill via `row.put("opinionVar", v)` —
  including binned metrics (`put("cRateMean_" + i, v)` in a loop). `Writer` becomes generic:
  writes the header from the first row's key set, then values in insertion order; a row whose
  key set differs from the header is a hard error (fail fast, not empty cell).
- Delete `Const.RESULT_LIST`, all per-metric `Writer` fields/setters, and `appendSingleMetric`
  (~250 lines net).
- Column names and order stay identical to the current output for legacy metrics (downstream
  notebooks keep working).
- **Output layout `[default-changing]`:** write one append-mode `metrics/results.csv` per run
  (likewise `posts/`, `opinion/`) instead of per-1000-step file shards
  (`result_0_1000.csv`, …) — downstream currently has to glob-and-concat. Keep the in-memory
  batching (buffer, flush every `BATCH_SIZE` steps) for I/O efficiency; only the file layout
  changes. Note the change prominently in the implementation report since analysis notebooks
  must drop their concat step.
**Acceptance.** Legacy columns byte-identical in name/order/format on a short run; a deliberately
mismatched row throws; single CSV per stream per run.

### R22 — Single source of truth for the follow graph
**Problem.** The follow relation is stored twice — `Agent.followList` (dense `boolean[N]` per
agent) and `AdminOptim.followees/followers` sets — synchronized by hand through the
`int[]{followedId, evictedId}` return protocol of `Agent.follow()` (magic value −1) plus
`admin.updateAdjacencyMatrix`. `AssertionCheck`'s first check exists solely to detect desyncs of
this dual bookkeeping. This is the standing maintenance trap of the codebase.
**Requirement.**
- Make `AdminOptim` the sole owner of the follow graph. `Agent.follow()/unfollow()` query it
  (pass the admin or a narrow read interface into the methods, which already receive
  `agentSet`); remove `Agent.followList` and the boolean-array plumbing
  (`setFollowList`, `getFollowList`).
- Replace the `int[]{added, evicted}` / `unfollowedId` return protocol with the R0 event
  objects: `follow()/unfollow()` emit events; `OpinionDynamics` applies them to the admin and
  the `EventLog` in one place. (Do R22 together with R0 — they touch the same seams.)
- `Agent.unfollowList` (blocks) **stays agent-owned** — it is genuinely private state, not a
  duplicate.
- `AssertionCheck`'s follow-consistency check becomes obsolete; keep only the opinion-range and
  new invariant checks (V4).
- Maintain a per-agent running followee count (replaces the O(N) scan in
  `Agent.follow():408-411`).
**Acceptance.** V1 regression passes; no dense per-agent follow arrays remain; follow/unfollow
behavior unchanged on a fixed-seed short run (decision-level trace comparison on ~50 steps).

### R23 — Per-step O(N²) hotspot removal
**Problem.** Three per-step costs scale as N² regardless of activity:
1. `AssertionCheck.assertionChecker` calls `admin.getAdjacencyMatrix()` **every step**
   (`OpinionDynamics.java:230`), materializing a fresh N×N `double[][]` — ≈8 MB × 40,000 steps
   ≈ 320 GB of allocation churn at N=1000, and it hard-blocks R17's N=5000.
2. `computeInteractionAssortativity` / `computeInteractionCrossCuttingFraction` scan the full
   dense N×N `repostNetworkCumulative` every step (`Analysis.java:215-251`).
3. `Network.getAdjacencyMatrix()` deep-copies N² on every call — acceptable at 5000-step export
   cadence, unacceptable per step.
**Requirement.**
- AssertionCheck iterates `admin.getFollowees(i)` directly (no matrix materialization) and runs
  every `assert_interval` steps (new config, CLI `assert_int=`, default 1000; `1` = legacy
  cadence). After R22 this check shrinks per that requirement.
- Store `repostNetwork`/`repostNetworkCumulative` sparsely (e.g. `Map<Long,Integer>` keyed
  `i*N+j`, or per-agent `HashMap<Integer,Integer>`); repost edges are sparse relative to N².
  Interaction metrics iterate entries, not the N×N grid. Gephi export and R16.3 snapshots adapt
  to the sparse form.
- Audit that no per-step code path calls `Network.getAdjacencyMatrix()` or
  `admin.getAdjacencyMatrix()`; dense materialization is allowed only at the 5000-step
  export/snapshot cadence.
**Acceptance.** A 2000-step N=1000 run shows a measurable wall-clock improvement (report the
before/after timing); metric values unchanged vs. dense implementation on a fixed seed
(unit-test the sparse metric against the dense formula on a small random matrix).

### R24 — Config-driven network selection
**Problem.** Choosing the initial network means editing comment blocks in
`OpinionDynamics.setNetwork()` and recompiling — the first wall any external user hits. The
generator zoo (9 classes) is otherwise fine.
**Requirement.**
- New config `network={dcsbm|ba|hk|ws|dms|cnn|lfr|random|read}` (CLI `network=`, default
  `dcsbm`) resolved by a small factory. Generator-specific parameters get CLI keys only for the
  ones the study actually varies (DC-SBM: `sbm_k=`, `sbm_pin=`, `sbm_pout=`, `sbm_gamma=`,
  `sbm_deg=` with current values as defaults); other generators may keep hardcoded defaults,
  documented in the factory.
- Fix the dishonest base-class API while there: `Network.setEdge(i,j,weight)` ignores `weight`
  and writes 1.0 (`Network.java:37-41`) — either honor the weight or change the signature to
  `setEdge(i,j)`; remove `reduceEdge`/`increaseEdge` if unreferenced.
- `setCustomized()`/`ReadNetwork`/`GephiReader` become the `network=read` path (with
  `read_path=` key) instead of commented-out code.
**Acceptance.** Switching generators requires no source edit; `network=dcsbm` with default keys
reproduces the current construction (same net_seed ⇒ same degree-sequence hash as before the
change).

### R25 — Dead dependencies and export toggles
**Requirement.**
- Delete `lib/gurobi` and `lib/ApacheCommonsMath` from the tree/classpath docs — zero references
  in `src/` (verified 2026-07-07). The gephi toolkit stays (used by the two visualizer classes).
- New config `log_gexf={true|false}` (CLI `log_gexf=`, default `true`): when false, skip all
  gephi graph construction/export (both visualizers) — large sweeps don't pay the 5000-step
  export cost or need the artifacts.
- README gets a short "build & run" section documenting the classpath (see R26).
**Acceptance.** Compile and a full smoke run succeed with the two jar directories removed;
`log_gexf=false` run produces no GEXF files and no gephi-related allocations.

### R26 — `run.sh` safety and parameterization
**Problem.** `run.sh` (a) hardcodes the seed list and passes no config tokens — every experiment
edits the script; (b) executes `rm -rf results/run_*` and `rm -f logs/*.log` unconditionally at
startup, silently destroying previous results; (c) relies on the zsh/globstar-dependent
`src/**/*.java` expansion; (d) ~60 lines are a commented-out older variant.
**Requirement.**
- Accept seeds and passthrough config tokens as arguments
  (`./run.sh --seeds "0 1 2" --parallel 10 -- key=value key=value …`); keep current values as
  defaults.
- **Never auto-delete results.** Remove both `rm` lines; if a target run folder exists, abort
  with a message (the `tag()` naming already makes collisions meaningful).
- Replace the glob with `find src -name '*.java'` into `javac @argfile` (shell-portable); delete
  the commented-out legacy block.
**Acceptance.** Running twice in a row does not destroy the first run's output; a config-token
run (`-- p_u=0.05`) lands in the correctly tagged folder; script runs under bash and zsh.

---

## 6. Verification & regression requirements

**V1 — Legacy regression (statistical, not bitwise).** RNG refactoring (R15) and instrumentation
make bitwise reproduction of old runs impossible; that is accepted. Required instead: with all
configs at legacy values (`init_op=clip`, sentinel dials, `p_forget=0`, `vel_mode=cumulative`,
`feed_order=random`, `rho_block=0`, and — for this test only — hub pinning toggled to the old
anchor behavior via a temporary flag or branch comparison), run 5 seeds before/after and confirm
the trajectories of `opinionVar`, `meanTolerance`, `opinionAssortativity`,
`crossCuttingFraction` are statistically indistinguishable (overlapping mean ± 2 s.e. bands over
the last 5000 steps). Provide the comparison script (Python or shell + existing CSV outputs)
under `scripts/` or scratch, and report the result. The script must read both output layouts
(legacy per-1000-step shards and R21's single CSV).

**V2 — Unit tests** (JUnit if available, else a `main`-based assertion harness under `src/test`
or `AssertionCheck` extensions): relay distortion formula incl. `s_relay` sentinel/override and
clipping; `p_r_out` gating; hub pinning invariance (R4 acceptance); truncated init has no ±1
atoms; block forgetting expected lifetime; softmax eviction with `evict_beta` sentinel = legacy
argmax; hostility bounds and zero-update case; misattribution switch (R10); cascade depth
chaining (R19); `fromArgs` round-trip for every new key; `tag()` emits each new token only when
non-default and produces distinct folder names for distinct configs.

**V3 — Config-matrix smoke test.** One short run (e.g. `steps=500`, `n=300`) for: legacy
defaults; each new dial individually at a non-default value; and one "everything on" combination.
All must complete without exceptions and emit schema-complete CSVs (all `RESULT_LIST` columns).

**V4 — AssertionCheck consistency.** Extend `AssertionCheck` to also verify: follow-list/admin
adjacency consistency still holds under eviction+forgetting; hub opinions constant when pinned;
`h ∈ [0,1]`.

---

## 7. Implementation order & dependency graph

```
Phase 1:   R15, R20, R21 → (R4, R3, R5, R12)   foundations: RNG streams, instance params,
                                               metrics pipeline — all three before anything
                                               that adds parameters or columns
Phase 1.5: R23, R24                            hotspot removal + network factory (independent,
                                               can interleave with Phase 2)
Phase 2:   (R0 + R22) → (R1, R2, R10)          event instrumentation and follow-graph
                                               single-ownership touch the same seams — do
                                               together; then metrics; R10 needs Post fields
                                               (shared with R19)
Phase 3:   R6, R7, R8, R9, R11, R13            independent dials, any order
Phase 4:   R14, R16, R17, R18, R19, R25, R26   R19 reuses R10's Post fields; R18 depends on
                                               R12+R15; R17 (N scaling) depends on R23's
                                               sparse matrices
Then: V1–V4
```

Known cross-requirement interactions the implementer must keep in mind:
- R4 × R3: pinned hubs (μ=1) relay fully flattened content under the coupled default; `s_relay`
  is the global override.
- R13 × R3 × R4: stubbornness sampling happens at construction; hub pinning overrides afterward;
  coupled relay strength follows the final value.
- R12 × R15: init sampling must come from the designated stream so `net_seed` alone fixes the
  network but not the opinions.
- R8 × R10: with `rel_attrib=reposter`, forgetting applies to relayer-targeted blocks like any
  other.

## 8. Out of scope (separate tracks)

- Experiment design: which dials to sweep, factor levels, run counts (research-direction /
  simulation-plan track).
- Empirical-anchoring analysis itself (cascade-distribution comparison, attention Gini,
  segregation-gap replication) — enabled by R19 logging but performed offline.
- Mean-field/analytic treatment of the tolerance–rewiring feedback (theory track).
- BC-gated assimilation variant: **deliberately not a code requirement in this round** — reviewer
  finding #2 is addressed by documentation (state loudly that bc gates relations, not
  assimilation) and can be added later as a single config if referees demand the robustness arm.
  If the implementer finds it cheap (one branch in `updateMyself`), adding
  `bc_gate_assim={false|true}` (default false) is welcome but optional.
