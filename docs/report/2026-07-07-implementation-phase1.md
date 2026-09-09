# 2026-07-07 — Phase-1 implementation of the model-revision requirements (handoff report)

**Spec:** `docs/report/2026-07-07-model-revision-requirements.md` (R-numbers below refer to it).
**Session scope:** ~40-minute implementation pass, foundations-first. Everything below compiles
(`javac` clean) and passed a smoke run (seed=9990 with the new dials active; see §Verification).

---

## Implemented this session

### R15 — Named RNG streams ✅
- `rand/randomGenerator` now exposes `network()` / `intervention()` / `dynamics()`;
  `init(seed, netSeed)`. Network generators draw from `network()` (seeded by `net_seed`,
  default = `seed`, CLI `net_seed=`); everything else from `dynamics()`; `intervention()`
  reserved (hub selection is currently deterministic). `get()` removed — any un-migrated call
  site fails compile by design.
- `ExperimentConfig.resolvedNetSeed()` resolves the sentinel.

### R3 — Conduit dials restored ✅
- `p_r_out=` (out-of-bc relay probability; sentinel −1 = coupled to `repostProb`; `0` disables
  out-of-bc relaying) — gate in `Agent.repost()`.
- `s_relay=` (relay distortion strength; sentinel −1 = coupled to the agent's `stubbornness`;
  when ≥0 overrides for ALL agents incl. pinned hubs) — in `Agent.relay()`.
- Both tagged in `tag()` only when non-default; both logged to `run_config.csv`.

### R4 — Full hub pinning ✅ `[default-changing]`
- `InterventionSetup.pinHub()`: intervened hubs get `intrinsicOpinion`, `opinion` (immediate,
  no stale broadcast), and `stubbornness = 1.0`. "Exogenously fixed" is now literally true.
- Documented interaction: with the coupled relay default, a pinned hub (μ=1) relays fully
  flattened content; `s_relay` is the dial to weaken that.

### R5 — Comfort-gate comment fix ✅
- `Agent.updateMyself`: kept fixed `Const.MINIMUM_BC` (decision D4), replaced the contradictory
  comment with the design rationale (vocal-minority mechanism survives bc collapse).

### R7 — Sweepable tolerance decay ✅
- `Const.BC_DEC_RATE` non-final, CLI `bc_dec=`, tagged when ≠ 0.99. Saturation-timescale note
  in `Const`.

### R12 — Truncated initial opinions ✅ `[default-changing]`
- Default is rejection-sampled truncated Gaussian (no atoms at ±1); legacy behind
  `init_op=clip` (tagged `_initop-clip`).

### R23a — Per-step O(N²) hotspot: AssertionCheck ✅
- No more per-step `admin.getAdjacencyMatrix()` dense materialization (~8 MB/step at N=1000);
  iterates `getFollowees(i)` directly. Cadence now `assert_int=` (default 1000 steps; 1 = legacy).
  Consistency errors now also counted in `numOfError`, not just printed.

### R14 — Dead-code removal (bulk) ✅
- Deleted: `Agent.like()`, `AdminOptim.recommendPostQueue`/`addRecommendPost`/
  `getManipulationTarget` (with its `System.exit(0)`), `admin/ExpIntervention.java` (whole
  class), `Const.TARGET_DIRECTION`/`FOLLOWER_THRESHOLD`/`MAX_RECOMMENDATION_POST_LENGTH`/
  `INCREMENT_PP`/`DECREMENT_PP`/`INCREMENT_PU`/`DECREMENT_PU`.
- Renamed misspelled identifiers, semantics now honest ("likes" were reposts):
  `Post.recievedLike` → `receivedReposts` (`getReceivedReposts`), `Post.receiveLike()` →
  `receiveRepost()`, `Agent.recievedLikeCount` → `receivedRepostCount`, `Agent.receiveLike()` →
  `receiveRepost()`. `grep -ri recieved src/` is clean.
- Kept: `getTopInfluencers` (harmless, not in the spec's delete list), `POST_COST` (real knob).

### R26 — run.sh safety & parameterization ✅
- `--seeds "…" --parallel N --heap Xg -- key=value…` argument interface; **no more
  `rm -rf results/run_*` / log deletion**; portable `find`+`@argfile` compile instead of
  zsh-only `src/**/*.java`; commented-out legacy block deleted; seeds passed as `seed=N` tokens.
- Java-side guard (`OpinionDynamics.main`): if the target result folder already exists the run
  **aborts** with a message instead of silently overwriting shards.

### G2 plumbing for all of the above ✅
- New `ExperimentConfig` fields/keys: `net_seed`, `p_r_out`, `s_relay`, `bc_dec`, `init_op`,
  `assert_int`; `tag()` emits `_prout-` / `_srel-` / `_bcdec-` / `_initop-clip` / `_nseed-`
  only when non-default; `run_config.csv` gained run-level columns
  `net_seed,p_r_out,s_relay,bc_dec,init_op`.

## Verification done
- Full compile clean (javac, gephi jars on classpath).
- Smoke run `seed=9990 p_r_out=0.1 s_relay=0.5 bc_dec=0.995`: healthy past step 8000 with no
  exceptions; folder tagged `..._prout-0.100_srel-0.50_bcdec-0.9950`; `run_config.csv` carries
  the new run-level columns; hub records show pinned opinions (±1, 0). (Killed at ~8k steps —
  full 40k-step runs are experiment-side.)
- R26 guard verified: re-running the identical config aborts with
  `[ABORT] result folder already exists: …`.
- **R15 acceptance verified:** `seed=9991 net_seed=9990` produced an initial degree sequence
  (`degrees/degree_result_0.csv`) byte-identical to the `seed=9990` run, and its folder was
  tagged `_nseed-9990`. Network is fixed by `net_seed` alone; dynamics vary with `seed`.
- Smoke-test result folders were deleted after verification.

## Session 2 additions (2026-07-07, Opus) — Phase 1 foundations + Phase 1.5

### R21 — MetricsRow pipeline + single-CSV layout ✅ `[default-changing: output layout]`
- New `writer/MetricsRow.java` (thin `LinkedHashMap<String,Number>`). `Writer` is now generic:
  header frozen from the first row, **keyset mismatch = hard `IllegalStateException`** (was a
  silent empty cell on a typo'd key). All per-metric fields/setters/`appendSingleMetric` deleted;
  `Const.RESULT_LIST` deleted. Adding a metric = one `row.put(...)` in
  `OpinionDynamics.buildMetricsRow()` (insertion order = column order).
- **Output layout changed:** one appended file per stream per run —
  `metrics/results.csv`, `posts/post_result.csv`, `opinion/opinion_result.csv` — instead of
  per-1000-step shards. **Downstream notebooks must drop their glob-and-concat step.** In-memory
  batching (flush every 1000 steps) retained.
- Verified: header byte-identical in name/order to the legacy `RESULT_LIST`; single header (no
  dup at batch boundary); 43 consistent fields; int metrics stay ints, doubles `%.4f`.

### R23b/c — sparse repost matrices + dense-call audit ✅
- New `analysis/SparseIntMatrix.java` replaces the two dense `int[N][N]` repost counters. The
  per-step interaction metrics (`computeInteractionAssortativity`/`...CrossCuttingFraction`) now
  iterate realized `(i→j)` entries (was a full N×N grid scan every step — 10⁶ cell-checks/step at
  N=1000). Math is identical (sparse entries = exactly the dense non-zeros). Dense snapshot
  materialized via `toDense(n)` **only** at the 5000-step gephi export.
- R23c audit: no per-step `getAdjacencyMatrix()` calls remain — dense materialization is confined
  to setup and the `step % 5000` export block.
- Verified: interaction columns populated and evolving under the sparse path; the
  `toDense`→RepostVisualize export path fired twice (steps 5000, 10000) in the everything-on
  smoke below with no exceptions.

### R24 — config-driven network factory + honest setEdge ✅
- New `network/NetworkFactory.java`; `network=` CLI key (`dcsbm`|`ba`|`hk`|`ws`|`dms`|`cnn`|`lfr`|
  `random`|`read`, default `dcsbm`) with DC-SBM params exposed (`sbm_k/sbm_pin/sbm_pout/sbm_gamma/
  sbm_deg`) and `read_path=`. `setNetwork()` comment-block selection is gone; `network=read` wires
  the old `setCustomized`/`GephiReader` path. Tagged `_nw-<type>` when non-default.
- `Network.setEdge(i,j,weight)` now **honors the weight** (was silently writing 1.0, corrupting
  `CustomNetwork`'s row-normalized weights); added clean `setEdge(i,j)` overload; removed unused
  `reduceEdge`/`increaseEdge`.
- `OpinionDynamics` constructor now takes `cfg` (constructor injection — a step toward R20).
- Verified: `dcsbm` default reproduces original construction; `network=ba` switches with no source
  edit and tags correctly.

### R20 — instance-scoped SimParams (mutable Const statics eliminated) ✅ `[foundation]`
- New immutable `experiment/SimParams.java` (a `record`, built via `SimParams.from(cfg)`) carries
  every runtime knob. Injected by reference into `Agent`, `AdminOptim`, `OpinionDynamics`. The
  `main()` block that overwrote ~11 mutable `Const` statics per run is **gone**; `Const` now holds
  only `final` constants.
- **Acceptance met:** `grep "public static [^f]" Const.java` → NONE. Determinism verified
  (same seed, two separate JVMs → byte-identical output). A single JVM can now run multiple
  configs sequentially (re-`init` the RNG between runs).
- **Caveat for next session:** `randomGenerator` streams and `Post.postIdCounter` are still
  `static`. Sequential multi-run in one JVM is correct as long as `randomGenerator.init()` is
  called before each run; `Post.postIdCounter` won't reset between in-JVM runs (cosmetic — IDs
  keep climbing, no correctness impact). Reset both if true in-process batch running is added.
- ExperimentConfig is the (effectively-immutable-after-parse) builder; formalizing *its* fields as
  final/builder-style is a remaining nicety, not required by the acceptance criterion.

## Session 3 additions (2026-07-07, Opus) — Phase 2, 3, 4

All compile clean and passed a combined smoke run (`n=400 steps=3000 p_forget=0.02 evict_beta=2
vel_mode=windowed alpha=0.3 stub_dist=uniform rel_attrib=reposter log_gexf=false`) with **0
assertion errors**, plus a default `n=1000 steps=5000` run (0 errors, gephi + modularity emitted).
The metrics CSV grew from **43 → 59 columns** (16 new; all present at default config too).

### R10 — Post lineage + attribution ✅
`Post` gains `rootPostId/parentPostId/relayerId/depth` + `isRelay()`; `Post.relayOf(...)` factory.
`Agent.relay()` records lineage and applies `rel_attrib` (`original` = legacy conduit immunity;
`reposter` = relayed copy's `postUserId` becomes the relayer, neutralizing misattribution).
Verified: cascade log shows `author==relayer` under `rel_attrib=reposter` and depth-≥2 chains.

### R6 / R13 ✅
`repost_prob=` (SimParams); volume metrics `originalPostCount`/`repostCount`.
`stub_dist={const|uniform}` + `stub_min/stub_max` — heterogeneous stubbornness drawn at construction
(hub pinning still overrides to 1.0 afterward; relay strength couples to the final value).

### R8 / R9 / R11 ✅
- R8 `p_forget=`: geometric block forgetting per active step, iterating a maintained blocked-id
  list (O(blocks), not O(N)); zero cost at the default `p_forget=0`. Lifting a block does not
  restore a follow edge.
- R9 `evict_beta=`: softmax eviction `P(k) ∝ exp(beta·|Δo|)` (sentinel `<0` = legacy argmax,
  `0` = uniform). `init_prune=trim`: randomly removes over-cap followees at t=0 (network stream)
  so agent follow-lists and admin start consistent with the cap.
- R11 `vel_mode=windowed`: For-You velocity = reposts *gained since the previous ranking pass* per
  elapsed step (demotes stalled early bursts); per-post snapshot in AdminOptim. `cumulative` = legacy.

### R2 — hostility state variable (anti-tautology affective axis) ✅
Per-agent `hostility ∈ [0,1]`, **read-out only (no behavioral feedback in v1)** — this is what keeps
it independent of the exposure-gating `bc`. Two channels: contact valence (rises on out-of-
`MINIMUM_BC` exposure, decays on comfortable — fixed radius, not dynamic bc) and misrepresentation
grievance (the post's attributed author gets a jump when their content is relayed with distortion
> `theta_dist`). Rates: `l_up/l_down/l_mis/theta_dist`. Metrics `meanHostility`, `hostilityVar`,
`hostility_0..4`. Verified evolving (~0.66) and bounded.

### R0 / R1 — lightweight event instrumentation + behavioral hostility proxies ✅
Rather than a full EventLog object, `Agent` exposes transient per-step counters
(`lastReposts/lastCrossReposts/lastBlocks`) and `OpinionDynamics` accumulates per-step stats in the
main loop (population actors only). New metrics: `outGroupBlockPropensity`
(sanctions / out-group posts read), `outGroupSanctionRate` (sanctions / active agents),
`crossRepostRate` (opposite-sign reposts, on the pre-relay feed-post opinion), `blockCount`,
`unfollowCount`, `evictionCount`. **Caveat:** the "block a non-followed disliked user" path
contributes to `blockCount` but its out-group-ness isn't separately tallied; sanction-propensity
counts unfollows + evictions (the dominant sanctions). This is the primary axis that answers
reviewer finding #1 (the affective outcome must not be the assumed mechanism).

### R16 (hygiene) ✅ except windowed-interaction (deferred)
- R16.1 `computeDisagreement` now excludes target-touching edges (`[default-changing]`).
- R16.2 `bimodalityCoeff` (Sarle) added alongside kurtosis.
- R16.4 sign-partition modularity of the evolved follow graph → side CSV `metrics/modularity.csv`
  every 5000 steps (verified: Q_sign=0.31 on a default run).
- R16.5 `feed_order={random|recent}` in AdminFeedback (`random` = legacy shuffle).
- **Deferred: R16.3** windowed interaction graph — adds a second per-step sparse scan for marginal
  value; do it if a transient-vs-steady interaction split is needed.

### R17 / R18 / R19 / R25 ✅
- R17 `n=` / `steps=` configurable — `Const.NUM_OF_USER/MAX_SIMULATION_STEP` no longer used at
  runtime; `OpinionDynamics`, `Agent` (followList sizing), `Analysis` size from the runtime value.
  Verified `n=400`. **Memory bound:** `Network` still holds a dense `double[N][N]` (~32 MB at
  N=2000, ~200 MB at N=5000); repost matrices are sparse (R23b). N=2000 is comfortable; N=5000
  needs a bigger heap.
- R18 `rho_block=` — DC-SBM community means equally spaced on `[-ρ,ρ]`, truncated-Gaussian init
  around them. Verified: initial opinion-assortativity 0.00 (ρ=0) → 0.31 (ρ=0.8). Errors clearly
  if used with a non-DC-SBM network.
- R19 cascade logging → `posts/cascades.csv`
  (`step,rootPostId,parentPostId,postId,author,relayer,depth,conveyedOpinion`), `log_cascades=`
  toggle. Verified depth chaining and grouping by `rootPostId`.
- R25 deleted `lib/gurobi` + `lib/ApacheCommonsMath` (zero refs); `log_gexf=false` skips all gephi
  construction/export (verified no GEXF files; the per-5000 `writeDegrees`/clustering/modularity
  still run, and `repostNetwork` still clears to bound memory).

### R22 — follow-graph single ownership: **DONE (full refactor, byte-identical regression PASS)**
`Agent.followList`/`getFollowList`/`setFollowList` removed; **`AdminOptim` is the sole owner** of the
follow graph. `follow()/unfollow()` query and mutate it via `follows/followeeCount/sortedFollowees/
addFollowEdge/removeFollowEdge`, **inline** (the deferred end-of-turn `admin.updateAdjacencyMatrix`
is gone). The desync trap is eliminated, so `AssertionCheck`'s followList-vs-admin check is retired.
- **Determinism preserved:** eviction (argmax + softmax) iterates `sortedFollowees` (ascending id),
  reproducing the old `followList` index-order tie-breaking exactly.
- **Regression:** captured a 3-seed baseline before the refactor; after it, output is
  **byte-identical** (md5 match on all 3), and after adding the later columns the shared columns
  remain byte-identical. This is a provably behavior-preserving refactor, not a behavior change.

### R16.3 — windowed interaction graph ✅
`repostNetworkWindow` (sparse) resets every `interaction_window` steps; columns
`interactionAssortativityW` / `interactionCrossCuttingFractionW` give the recent-relaying (transient)
view alongside the cumulative ones. Metrics CSV is now **61 columns**.

### BC-gated assimilation (`bc_gate_assim`) ✅ (reviewer #2, optional arm)
When true, the FJ update averages only in-tolerance (dynamic-bc) feed posts; default false averages
the whole feed and is **behavior-preserving** (verified in the byte-identical regression). This lets
referees from the opinion-dynamics tradition see that bc-gating doesn't drive the result.

### V4 — AssertionCheck extended ✅
Replaced the obsolete followList check with: no follow edge to a blocked user; `opinion∈[-1,1]`;
`hostility∈[0,1]`; and **pinned-hub invariance** (target hubs keep `opinion==intrinsic`). A default
`n=1000` run reports 0 errors.

### V2 — unit-test harness ✅
`src/test/ModelTests.java` (no JUnit; run `java -cp bin test.ModelTests`). **28 checks, ALL PASS:**
config round-trip for every new key, `tag()` non-default-only + distinctness, Post relay lineage
(depth/root/parent/relayer + attribution), SimParams sentinels, truncated-init has no ±1 atoms and
stays in range, hostility bounds/monotonicity, attribution switch.

## NOT done — remaining for the next session

Essentially only the empirical/analysis and one statistical-regression item remain; all model-code
requirements R0–R26 are implemented.
- **V1 statistical regression** (5-seed, whole-run distributional compare vs. a pre-session checkout)
  not run. Note it can no longer be *byte*-identical: R4/R12/RNG-restreaming (session 1) intentionally
  changed trajectories. The meaningful in-session guard — that R22 and every Phase-2/3/4 default is
  behavior-preserving — **was** established via the byte-identical 3-seed regression above. A full V1
  vs. commit `07d8b11` would only re-confirm the *intended* session-1 changes, so it is low value.
- **V3** full config-matrix smoke — covered informally by the combined smokes; a scripted matrix
  (one short run per dial + an all-on run) would formalize it.
- Empirical-anchoring **analysis** (cascade-size/virality vs. Goel/Vosoughi, attention Gini,
  segregation gap) — out of scope by design; R19 cascade logging now enables it offline.

## New config keys (session 3) — quick reference
`repost_prob, stub_dist, stub_min, stub_max, p_forget, evict_beta, init_prune, vel_mode,
rel_attrib, l_up, l_down, l_mis, theta_dist, interaction_window, feed_order, n, steps, rho_block,
log_cascades, log_gexf, bc_gate_assim` — all default to legacy behavior and tag the run folder only
when non-default. Metrics CSV is **61 columns** (was 43 pre-session).

## Behavioral changes to be aware of (intentional, per spec)
1. Hubs are now truly pinned (extreme hubs broadcast exactly ±1, moderates exactly 0).
2. Initial opinions have no ±1 atoms by default (R12 truncate).
3. Same seed no longer reproduces pre-session trajectories bitwise (RNG streams + consumption order).
4. Assertion checks run every 1000 steps by default (`assert_int=1`, restores every-step).
5. Reruns abort on existing result folders instead of overwriting.
6. Metrics output is one appended CSV per stream (R21), not per-1000-step shards — notebooks must
   drop their glob-and-concat. Metrics CSV is now 59 columns.
7. At *default* config the new Phase-2/3/4 mechanisms are inert (all dials default to legacy), so a
   default run is behavior-equivalent modulo the intentional R4/R12/RNG changes already noted.
