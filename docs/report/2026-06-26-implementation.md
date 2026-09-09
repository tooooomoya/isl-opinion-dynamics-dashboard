# Implementation — Moderate Conduit / Type-1 vs Type-2

Base paper: `docs/wssit2026-TomoyaTakeda.tex`. Canonical objective: `docs/research-direction.md`.
Start of the Step-1 build (research-direction.md §4 build order). Model changes begin here.
Last updated: 2026-06-26

---

## Build order being followed (research-direction.md §4)
1. **(1c) Outcome instrumentation — 2-D plane** ← *this entry* (low-risk, gates the validation gate).
2. (1b) Feed + network (velocity-primary For-You, hop `h`, opinion-blind, block-on-For-You).
3. (1a) Agent mechanisms (asymmetric ε with slow recovery; quote-repost λ-blend / relay distortion; reattribution bypass).
4. Step-2 validation gate → freeze.

## Decision log

- **2026-06-26 — (1c) 2-D outcome plane instrumented.** Implemented the measurement instrument that
  distinguishes Type 1 from Type 2 (opinion variance alone cannot). Five per-step metrics added,
  all excluding exogenous (target) hubs, consistent with `opinionVar`:
  - **y-axis (affective hostility via ε/tolerance, per §4 — NOT opinion variance):**
    `meanTolerance` (mean of agents' `bc`; low ⇒ hostile), `toleranceVar`.
  - **x-axis (structural separation):** `opinionAssortativity` (Newman scalar assortativity =
    Pearson corr of opinion across directed follow edges; →1 = homophilous sorting / Type-1 structure),
    `crossCuttingFraction` (fraction of follow edges crossing the O=0 divide; high = connected across
    camps / Type-2 substrate).
  - **affective/bimodality companion:** `opinionKurtosis` (excess kurtosis over all `O_i`; negative ⇒
    bimodal two-camp distribution).
  - **Type map:** Type 1 = upper-right (high separation, high hostility); **Type 2 = upper-left**
    (low separation, high hostility) = target.
  - **Files:** `Analysis.java` (5 compute methods), `Const.RESULT_LIST`, `Writer.java`
    (fields/setters/`appendSingleMetric`), `OpinionDynamics.exportStepMetrics`.
  - **Caveat (documented follow-up):** structural axis is computed on the **follow graph**. The
    2026-06-23 literature audit (Conover 2011) flags that the cross-cutting layer empirically lives in
    the **interaction/quote graph**, and follow-graph modularity can hide a live Type-2 state. An
    interaction-graph variant of the x-axis is deferred (needs a persistent quote/repost edge log;
    `repostNetwork` currently resets every 5000 steps and is author-level only).
  - **Refactor:** the per-step metric export in `OpinionDynamics.evolve()` (long wall of
    `analyzer.compute…` / `writer.set…` calls) extracted into a private `exportStepMetrics(...)` helper
    to keep the agent-loop body readable. Behavior-preserving.
  - **Pilot diagnostic (free, from the smoke test):** a naive run `extreme=sym, channel=both, seed=0`
    at t=40000 lands at **assortativity ≈ 0.59, crossCutting ≈ 0.31, kurtosis ≈ −1.02,
    meanTolerance ≈ 0.69**. High assortativity + bimodal opinion = **Type-1-leaning structure**, as
    research-direction.md §2 predicted naive runs go to Type 1. (Tolerance not collapsed to floor —
    worth watching once asymmetric-ε / feed changes land.) This is the §4 "optional cheap diagnostic":
    it confirms the redesign is necessary, not optional.

- **2026-06-26 — (1b) velocity-primary "For You" feed implemented.** Mixed feed:
  `floor(α·S)` For-You slots + remainder chronological-from-follows (`S = FEED_CAPACITY = 10`).
  - **Knobs (swept, defaults preserve legacy):** `α` (`FEED_ALGO_SHARE`, CLI `alpha=`), `h`
    (`FEED_HOP_H`, CLI `hop=`). `α=0` ⇒ For-You machinery skipped entirely = legacy chronological feed.
  - **Velocity = relative/"soaring"** (2026-06-23 decision): `reposts / ((age+1)·(followers+1))` —
    opinion-blind, anti-rich-get-richer. Ranked once per step (global pool, `VELOCITY_WINDOW = 100`).
  - **Reach `h`** on the **undirected** follow graph (stated hop direction): `h≤0` global,
    `h=1` direct, `h≥2` BFS to depth `h`; reachable sets cached, refreshed every
    `REACH_REFRESH_INTERVAL = 100` steps (graph evolves slowly). Verified saturates fast at `h=2`
    (hubs), as the doc's density caveat predicted.
  - **Block-on-For-You is free:** For-You posts enter `agent.feed`, so the existing `unfollow()`
    block rule (uncomfortable + not-followed → block w.p. `P_u`) already applies.
  - **Files:** `Const` (5 params), `ExperimentConfig` (`alpha`/`hop` parse + tag), `AdminOptim`
    (recent-post window, `rankByVelocity`, cached undirected `h`-hop reach, rewritten `AdminFeedback`),
    `OpinionDynamics` (set knobs, per-step ranking, register posts). Dead `recommendPostQueue` left as-is.
  - **🔴 KEY FINDING (feed-only, seed=0, `extreme=sym ch=both`, α=0.6, h=0 global) — feed alone drives
    Type 1 HARDER, not Type 2.** vs legacy: assortativity **0.59 → 0.99**, crossCutting **0.31 → 0.03**,
    meanTolerance **0.69 → 0.32 (hostility ↑)**, kurtosis −1.02 → −0.79. So the open global feed
    pushed the system to the **upper-RIGHT (Type 1, intensified)**: tolerance collapsed *and* the follow
    graph became near-perfectly homophilous with cross-cutting edges almost eliminated. **This is
    exactly the doc's flagged consequence** (2026-06-23): For-You is a *block generator*; with verbatim
    repost + the block rule + bc-decline as the only divergence channel, more out-of-network exposure ⇒
    more blocking ⇒ harder sorting. **Implication for the Step-2 gate: feed alone does NOT reach Type 2;
    the burden of Type 2 rests on the (1a) mechanisms — relay distortion / quote-repost + reattribution
    bypass + asymmetric ε with recovery.** Validates building 1a next.
  - **TODO (other half of 1b):** run *feed-only* and measure equilibrium **follower-by-rank** vs the
    sustained ~20–100 mid-tier target (the network-as-precondition gate); change the generator
    (DCSBM / less-skewed) only if the mid-tier is still empty. Not yet done.
  - **`h` default parked at 3** (2026-06-26, user decision): leave `FEED_HOP_H = 3` as the working
    default; defer the `h` sweep (1, 2, 3, global) until after (1a) lands, since without a Type-2
    channel `h` can only modulate the strength of block-driven sorting, not reveal the intended
    conduit-vs-algorithm tradeoff curve.
  - **Terminology (2026-06-26, user decision):** stop using "Type 1 / Type 2" shorthand; use the
    doc's own direct terms — **structural polarization** (echo-chamber fragmentation / network
    separation) and **affective polarization** (connected-but-hostile / collapsed tolerance), matching
    the cited literature (Iyengar et al. 2019). Code comments updated; this report and future entries
    use the direct terms. Historical entries in `2026-06-19-experimental-design.md` and
    `research-direction.md` left as-is (append-only design log convention).

- **2026-06-26 — (1a) agent mechanisms implemented: asymmetric tolerance + relay distortion +
  out-of-bc relay.** Per the research-direction.md decision log's *final* (2026-06-23) form, which
  **supersedes** the original §3 items 1-2 numbered list (no reattribution/attribution-bypass
  mechanism was adopted — conduit immunity via unchanged `postUserId` stays untouched by design).
  Three changes, all new knobs default to 0 (legacy/ablation baseline):
  1. **Asymmetric tolerance (`Agent.updateMyself`):** kept the existing fast multiplicative decline
     (`bc *= BC_DEC_RATE` on uncomfortable contact); added slow multiplicative recovery
     (`bc *= 1+γ_recover` on comfortable contact), `γ_recover` = `Const.BC_RECOVER_RATE` /
     CLI `gamma_recover=`. `γ=0` recovers the old monotone-only ratchet exactly (robustness
     baseline). Fixed a latent clamp bug while here: the old bound
     `bc = max(bc, min(MINIMUM_BC,1.0))` was floor-only; added an explicit upper clamp to
     `BOUNDED_CONFIDENCE`, needed now that recovery can push `bc` back up.
  2. **Relay distortion (`Agent.relay`):** on repost, conveyed opinion
     `O_conveyed = O_orig + s·(O_reposter − O_orig)`, `s` = `Const.RELAY_DISTORTION_S` /
     CLI `relay_s=` (`s=0` verbatim, `s=1` reposter fully overwrites), clipped to `[-1,1]`. A new
     `Post` is constructed (same `postUserId`, distorted opinion, original `postedStep`) — the
     *content* changes, attribution doesn't.
  3. **Out-of-bc relay channel (`Agent.repost`):** rewritten to a single pass over the feed with two
     distinct entry gates — in-bc posts keep the existing `repostProb`; out-of-bc posts get a new,
     separate probability `P_r^out` = `Const.OUT_OF_BC_REPOST_PROB` / CLI `p_out=` (the "quote/
     critique/dunk" layer, framed per the Conover 2011 correction as distinct from ordinary
     endorsement-retweet). Both channels feed the same `relay()` distortion transform — entry
     (who gets relayed) and transformation (how much it's reframed) are kept as separate knobs
     per the doc's explicit "provably distinct jobs" requirement.
  - **Velocity-tracking correctness preserved:** `receiveLike()` is called on the *original* feed
    `Post` object (the one `admin`'s For-You ranking tracks via `recentPosts`), not on the new
    distorted copy, so repost activity still boosts the tracked object's relative-velocity score.
  - **Files:** `Const.java` (3 params), `ExperimentConfig.java` (CLI parse + tag), `OpinionDynamics.java`
    (wire knobs in `main`), `Agent.java` (`updateMyself` asymmetric bc + clamp fix, `repost`/`relay`).
    Compiles clean.
  - **Smoke test result (seed=0, `extreme=sym ch=both`, t=40000):**

    | metric | legacy (knobs=0) | 1a on (γ=.001, s=.7, p_out=.05) | direction |
    |---|---|---|---|
    | opinionVar | 0.2908 | 0.2454 | ↓ more consensus |
    | meanTolerance (y) | 0.6843 | **0.9571** | ↑ — **less hostile** |
    | opinionAssortativity (x) | 0.5828 | **0.3848** | ↓ — less separated |
    | crossCuttingFraction (x) | 0.3122 | **0.3864** | ↑ — more connected |
    | opinionKurtosis | −1.0631 | −0.8130 | less bimodal |

    **Interpretation: structural axis moved the intended direction (lower separation, more
    cross-cutting survival — the conduit did keep the network more connected than the naive
    baseline), but hostility moved the WRONG way for affective polarization** — tolerance rose,
    not fell. Net landing point: **lower-left (converged, low-separation, low-hostility) =
    de-escalation**, not the upper-left affective-polarization target. This is not a failure: the
    doc's "knob, not assumption" litmus test requires the mechanism to be *capable* of the
    opposite-of-polarizing outcome under some setting, or the headline claim is tautological — this
    run is that corner. Likely cause: `s=0.7` heavily dilutes out-of-bc extreme content toward the
    reposter's own (moderate) position before relay, so recipients rarely find it uncomfortable
    enough to trigger `bc` decline — the conduit acts as a buffer, not a shock-transmitter, at this
    parameter setting. **Next step to locate the affective-polarization corner:** sweep `s` downward
    (content stays closer to the original extreme, still routed through the moderate's identity but
    not defanged) and/or raise `P_r^out`, holding `γ_recover` fixed. Not yet run.
  - **Minor RNG-desync note:** the legacy run's numbers drifted slightly from the earlier 1c/1b
    baseline entries above (assortativity 0.5828 vs 0.5916, etc.) — benign: the rewritten `repost()`
    now draws `nextDouble()` once per feed post unconditionally (testing `entryProb`) instead of only
    for pre-filtered in-bc candidates, so it consumes one extra draw per out-of-bc post even at
    `p_out=0` (where that draw can never satisfy `< 0.0` anyway). Shifts the downstream RNG stream,
    not the behavior — legacy runs remain behaviorally identical (out-of-bc reposts still never fire
    at `p_out=0`), just on a different random trajectory.
  - **α/h status:** neither smoke test above exercised the For-You feed — both used the default
    `FEED_ALGO_SHARE=0.0`, so they were pure chronological/legacy feed. The mixed feed (`α`, `h`) and
    the 1a mechanisms have not yet been tested together; that combination is still open.

- **2026-06-26 — Parameter-role classification adopted (user-driven methodological decision).**
  Distinguish three parameter roles going forward, to avoid smuggling substrate assumptions in as if
  they were fixed background:
  1. **Fixed, data-grounded** (e.g., network degree distribution, engagement-rate constants) — should
     trace to external data/literature, not "whatever makes the result come out."
  2. **Calibrated to stylized facts** — no direct empirical analog; tuned so the simulated society
     behaves plausibly on dimensions *unrelated* to the hypothesis (stays connected, reaches stable
     equilibrium), never calibrated to the hypothesis outcome itself.
  3. **Swept treatment / phase knobs** — the small parameter set the causal claim is actually about;
     only these get the regression / phase diagram.
  Sensitivity analysis (robustness check on Tier-1/2 parameters) is kept conceptually distinct from
  the Tier-3 treatment sweep (the main design) — conflating them risks an uninterpretable factorial.
  **Corrected an earlier misclassification:** the `HolmeKim(3,1,0.3)` network generator IS a Tier-1
  parameter mis-set (inherited from `journal.tex`'s backfire-under-polarization narrative, not derived
  for this paper — also doubles as the H4 fix). The **discrete `{-1,0,+1}` opinion assignment is NOT
  the same issue** — extreme-hub opinion at exactly `±1` is a deliberate, correct, already-fixed
  exogenous anchor (confirmed in code: `InterventionSetup` always assigns exactly `±1.0`, never
  swept) matching the Step-0 causal DAG's own "source extremity HELD FIXED" decision. Only the
  **moderate hub's fixed-at-0** assignment is the live Tier-3 construct-validity question (how
  moderate is "moderate"), and per the escalation logic below it stays discrete for now.
  **Escalation contingency (pre-registered, not to be decided post-hoc):** keep moderate opinion
  pinned at exactly `0` for the primary design. If the moderate-only sweep (`n_moderate × scale ×
  channel × relay-params`) shows no detectable effect, the diagnostic order is (a) first confirm
  `±1` extremity is doing its job (per DAG: `(I,A,I) ≈ (I,I,I)` should NOT hold if a genuine source
  exists), THEN (b) only escalate to a continuous moderate-position sweep if (a) checks out fine.

- **2026-06-26 — New experimental arm identified: natural/organic extremity (`extreme=NONE` +
  `n_moderate>0`).** Corrects an oversimplification from earlier in the session: `extreme=NONE` is
  **not** "no source exists," it's "source is left natural/emergent instead of engineered." Given
  `INITIAL_OPINION_STD=0.6` with hard clipping to `[-1,1]`, a non-trivial fraction of the population
  starts already pinned at exactly `±1` from the initial draw alone (~1.67σ cutoff), dispersed at
  whatever follower count they happen to have (uncorrelated with opinion, since network generation
  and opinion assignment are independent draws) — i.e. real boundary-extreme agents exist without any
  hub engineering. This arm tests a **broader/more externally-valid** version of the claim: does the
  conduit mechanism matter when extremity is realistically diffuse (as in a real population), not just
  when a maximal, guaranteed-reach source is artificially engineered onto a top-follower node?
  **Fills a previously-implicit cell** in the existing Exp 0/A/B decomposition:
  | | extreme forced (±1) | extreme natural |
  |---|---|---|
  | **moderate forced (=0)** | Exp A/B (current main design) | **new arm** |
  | **moderate natural** | Exp 0 ("are ±1 extremes the precondition?") | E0 (pure baseline) |
  **No code change needed** — `ExperimentConfig` already supports `extreme=NONE` with `n_moderate>0`.
  **Precondition to check before trusting this arm (not yet done):** a reach diagnostic — does
  naturally-scattered extreme content (dispersed, often low-degree authors) actually reach the forced
  moderate hub's feed at a non-trivial rate, given `MAX_FOLLOW_CAPACITY=10` concentrates attention on
  a small number of hubs (the same skew underlying H4)? If reach is negligible, this arm collapses to
  data-free near-consensus, not because the hypothesis is false but because the network starves the
  channel — same "network as precondition" concern as H4/1b, recurring here. **User has accepted that
  this arm may show polarization in only a minority of runs (or none) — that is an acceptable and
  informative outcome, not a failure requiring redesign.**

- **2026-06-26 — Parsimony decision: `s` and `P_r^out` retired as independent free parameters, tied
  to existing agent fields instead.** Rather than calibrating two brand-new knobs, reuse traits the
  model already has:
  - **`s := this.stubbornness`** (`Agent.relay()`). Same self-anchoring trait (`mu`) that governs how
    much of an agent's own view dominates their FJ-updated opinion now also governs how much it
    colors what they broadcast when relaying — one psychological parameter doing both jobs, not two.
  - **`P_r^out := this.repostProb`** (`Agent.repost()`). The bc gate no longer restricts *who* can be
    reposted (out-of-bc content is now relayed at the same rate as in-bc); it only used to gate entry,
    and that gate is retired in favor of a uniform roll. This is the full "allow reposting outside
    bounded confidence" companion change, not a partial one.
  - **Removed:** `Const.RELAY_DISTORTION_S`, `Const.OUT_OF_BC_REPOST_PROB`, and the `relay_s=`/`p_out=`
    CLI keys/tag entries in `ExperimentConfig`. `repost()` simplified to a single uniform-probability
    loop (no more `withinBc` branch).
  - **Consequence:** calibrating `stubbornness` (`mu`) and `repostProb` (already-existing, already
    load-bearing parameters) now does double duty — it simultaneously calibrates FJ assimilation
    *and* relay distortion strength *and* the out-of-bc relay rate. Reduces the free-parameter count
    for 1a from 3 new knobs down to 1 (`gamma_recover`), at the cost of coupling: `s` and `P_r^out` can
    no longer be tuned independently of their host traits. If future work needs them decoupled again
    (e.g. relay distortion turns out to need a different magnitude than FJ assimilation), that's a
    deliberate un-coupling to revisit, not a silent gap.
  - **Practical note:** `stubbornness=0.8` (current global constant) implies `s=0.8`, close to the
    `s=0.7` value already smoke-tested (de-escalation corner, logged above) — so this hardcoding likely
    still lands near that corner, not yet in the affective-polarization one. Calibration of `mu` and
    `repostProb` themselves (Tier-1/2 work, not yet done) is what would move it, not a separate `s`
    sweep.
  - Compiles clean; smoke test in progress.

- **2026-06-26 — Phase 2/3 progress: DC-SBM equilibrium erosion finding, Tier-1 parameter candidate
  list, and a P_u literature-grounding correction.**
  - **DC-SBM `targetAvgDegree` empirically re-tuned to 50** (not the class docstring's recommended 10):
    a standalone diagnostic (`scratchpad/NetworkDiag.java`, not committed - throwaway) found a
    saturation cap in `normalizeThetaIn()` puts a roughly fixed ceiling on hub in-degree (~210-230)
    independent of the target, so target=10 starves the mid-tier (rank50~11 followers) while
    target=50 lands rank50~50/rank100~29 in the doc's stated ~20-100 band, matching production RNG
    order (verified target=10 reproduces the 3.89 avg in-degree seen in the live run).
  - **🔴 Phase 2b baseline (no intervention, defaults, DC-SBM target=50, t=40000) found SEVERE
    equilibrium erosion, a different failure mode than the rich-get-richer concern H4 originally
    named:** follower-by-rank collapsed from (rank1=218, rank50=50, rank100=29) at t=0 to
    (rank1=65, rank50=39, rank100=35) at t=40000, **and 425/1000 agents (42.5%) ended with ZERO
    followers.** Follow-graph opinionAssortativity=0.9955, crossCuttingFraction=0.0136 - near-total
    structural polarization, worse than any prior measurement this session. Interaction-graph
    variants less extreme (0.88 / 0.11) but still heavily sorted.
  - **Parameter-role classification candidate list produced** (Tiers A-E: engagement rates, opinion/
    psychological params, posting/vocal-minority dynamics, network structure, feed-mechanism
    constants). Confirmed **`FOLLOWER_THRESHOLD` and `TARGET_DIRECTION` are dead code** (only
    referenced inside the never-called legacy `AdminOptim.getManipulationTarget()`) - excluded from
    calibration scope. `POST_COST=0.0` confirmed live but currently a no-op.
  - **🔴 P_u literature check reveals a units mismatch, not just a magnitude correction.** Survey
    literature on politically-motivated unfriending/unfollowing/blocking (Pew ~10% 2012; "18%" Hill
    summary; 28% liberals post-2016 election; 38% UChicago 2023 GenForward/IOP poll; up to 61% in one
    survey) all measure **cumulative "ever done this" prevalence over years of exposure**, not the
    model's per-single-uncomfortable-contact-event conditional probability that `P_u` represents.
    Back-of-envelope translation via `P(ever) = 1-(1-p)^N`: even at low assumed exposure-opportunity
    counts (N=50-500), the implied per-event `p` lands **~0.0002-0.009, one to two orders of magnitude
    below the current default `P_u=0.1`**. `N` is a genuine judgment call (not independently measured
    here), so treat this as an order-of-magnitude finding, not a precise value - but it independently
    corroborates the mechanistic "low P_u -> affective polarization" hypothesis from the phase-diagram
    reasoning, giving two independent lines of argument pointing the same direction.
  - **Sources:** [Pruning the news feed (Bode 2016)](https://journals.sagepub.com/doi/10.1177/2053168016661873),
    ["You're still worth it" (PLOS ONE)](https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0243049),
    [Navigating Political Disagreement on Social Media](https://www.cogitatiopress.com/mediaandcommunication/article/viewFile/8483/4099),
    [Study finds 18% block/unfriend over politics (The Hill)](https://thehill.com/policy/technology/108391-study-finds-18-percent-of-social-media-users-block-unfriend-over-politics/),
    [Effects of disagreement/unfriending on affective polarization (JCMC)](https://academic.oup.com/jcmc/article/28/4/zmad022/7194034).
    REPOST_PROB sources (from the earlier grounding pass): [Who Will Retweet This?](https://arxiv.org/pdf/1405.3750),
    [Mechanisms of True and False Rumor Sharing](https://arxiv.org/pdf/2207.03020).
  - **Action:** re-launched the P_u x gamma_recover grid (previously killed mid-run) at
    `p_u=0.002` (literature-informed) x `{gamma_recover=0, 0.005}`, hub intervention on
    (extreme=sym n_mod=1), DC-SBM network. Result pending.

- **2026-06-26 — P_u grid result: lowering P_u alone does NOT reduce structural separation.**
  `p_u=0.002` (vs default 0.1) x `{gamma_recover=0, 0.005}`, hub intervention on, t=40000:
  `opinionAssortativity` stayed at **0.985 (gr=0) / 0.973 (gr=0.005)**, `crossCuttingFraction`
  still **~0.01** in both — essentially unchanged despite a 50x reduction in unfollow probability.
  `gr=0.005` pushed `meanTolerance` to 0.948 (de-escalation corner again, reached a different way).
  **Diagnosis: `follow()`'s evict-most-disagreeing-on-add mechanic is a P_u-independent sorting
  force, and is now suspected dominant.** `MAX_FOLLOW_CAPACITY=10` was calibrated for the old sparse
  HolmeKim network (avg degree ~3-4); the DC-SBM network realizes avg out-degree ~17.5, so most
  agents start already over the cap - every successful new follow evicts the most-opinion-different
  existing followee (`Agent.follow()` `maxDiff` logic), independent of `unfollow()`/`P_u` entirely.
  Matches the approved plan's own fallback sequencing ("target-tuning first, `MAX_FOLLOW_CAPACITY`
  second"): both prior levers tried without success, this is next.
  - **`MAX_FOLLOW_CAPACITY` made mutable + swept** (`Const`, `ExperimentConfig.maxFollowCapacity`,
    CLI `max_follow=`), same pattern as `P_u`/`gamma_recover`.
  - **🔴 Self-caught bug (found before trusting the result): `ExperimentConfig.tag()` compared
    `pU`/`maxFollowCapacity` against `Const.UNFOLLOW_PROB`/`Const.MAX_FOLLOW_CAPACITY` - but
    `OpinionDynamics.main()` mutates those exact `Const` fields from the same `cfg` *before* calling
    `cfg.tag()` to build `RESULT_FOLDER_PATH`, so the comparison always read back the just-assigned
    value and was always false.** Consequence: the first `max_follow=20` vs `max_follow=30` parallel
    test pair silently wrote to the **same** result folder and raced on the same files - the "result"
    pulled from that folder was a corrupted mix of two concurrent processes, not a valid measurement
    of either config, and was discarded (not reported past the initial pull). Confirmed the earlier
    P_u grid (E/F) was unaffected - it differed only in `gamma_recover`, whose tag check was always a
    literal `>0.0` comparison, never routed through `Const`. **Fix:** `tag()` now compares against
    fixed literal defaults (`DEFAULT_P_U=0.1`, `DEFAULT_MAX_FOLLOW_CAPACITY=10`) instead of `Const.*`,
    permanently closing this class of bug for any future knob added the same way. Re-running
    `max_follow=20`/`30` cleanly under the fix.

- **2026-06-26 — 🟢 MAX_FOLLOW_CAPACITY confirmed as the real lever: first result moving BOTH axes
  toward affective polarization simultaneously.** Clean, valid (distinct folders confirmed) results,
  `p_u=0.002 gamma_recover=0`, hub intervention on, t=40000:

  | max_follow | opinionAssortativity | crossCuttingFraction | meanTolerance | zero-follower | rank50/100 |
  |---|---|---|---|---|---|
  | 10 (baseline) | 0.985 | 0.011 | 0.657 | 339 | 51/44 |
  | 20 | 0.968 | 0.012 | 0.575 | 242 | 73/55 |
  | 30 | 0.896 | 0.017 | 0.514 | 130 | 116/90 |

  Monotonic across all 3 points: structural separation falling (assortativity, erosion) **and**
  hostility rising (tolerance falling) together - the affective-polarization signature, not
  structural-polarization or de-escalation. Also resolves the erosion problem as a side effect
  (zero-follower 339->130) and produces a genuinely healthy mid-tier (rank50~116, rank100~90).
  Not yet in the target quadrant (assortativity still high, cross-cutting still small in absolute
  terms) but the trend is unambiguous. **Testing max_follow=40,60 next to see if the trend continues
  or plateaus before reaching the target.**

- **2026-06-26 — 🟢 max_follow=40/60: trend continues strongly, closest approach yet to affective
  polarization, on the interaction-graph metric specifically.** Full table (`p_u=0.002 gamma_recover=0`,
  hub intervention on, t=40000):

  | max_follow | assort (follow) | crossCut (follow) | assort (interaction) | crossCut (interaction) | meanTolerance | zero-follower |
  |---|---|---|---|---|---|---|
  | 10 | 0.985 | 0.011 | ~0.72 | ~0.12 | 0.657 | 339 |
  | 20 | 0.968 | 0.012 | 0.692 | 0.128 | 0.575 | 242 |
  | 30 | 0.896 | 0.017 | 0.563 | 0.174 | 0.514 | 130 |
  | 40 | 0.800 | 0.030 | 0.335 | 0.249 | 0.478 | 82 |
  | 60 | 0.730 | 0.058 | **0.174** | **0.335** | **0.438** | 53 |

  On the interaction graph (the Conover-correct metric), separation collapsed to 0.17 while
  cross-cutting rose to 33.5% and tolerance kept falling - the affective-polarization signature,
  strongest result of the session, though follow-graph assortativity (0.73) is still fairly high in
  absolute terms so not unambiguously "arrived."
  - **Principled stopping point identified (not "push max_follow indefinitely"):** the original
    cap=10 was ~2.5-3x the old network's avg degree (~3-4) - a loose constraint. Restoring that same
    looseness *ratio* on the new network (avg degree ~17.5) implies **max_follow~44-52**, not an
    ever-higher escalation. This is a principled value, not an arbitrary pick.
  - **🔴 Critical gap flagged: every comparison this session has been single-seed (seed=0).** Before
    trusting this trend as a real finding vs. a seed-0 artifact, launched a 3-seed replication
    (seeds 0,1,2) at `max_follow=45` (the principled value). Result pending.

- **2026-06-26 — 🟢 Seed replication (max_follow=45, seeds 0/1/2): direction confirmed robust,
  precision not yet established.** Every seed shows the same qualitative shift toward affective
  polarization relative to the max_follow=10 baseline (assortativity 0.985 -> 0.80-0.91, tolerance
  0.657 -> 0.43-0.56, interaction-graph assortativity ~0.72 -> 0.30-0.57) - this is NOT a seed-0
  artifact. But the spread across only 3 seeds is real, especially on interactionAssortativity
  (0.30-0.57, ~2x) and zero-follower erosion (18-71, ~4x). Seed 1 looks closer to the earlier
  max_follow=30 result; seeds 0/2 look closer to max_follow=60. **Conclusion: the model is confirmed
  capable of moving substantially toward affective polarization once MAX_FOLLOW_CAPACITY is corrected
  to match the DC-SBM network's density - a genuine, seed-robust directional finding for the Step-2
  gate ("can the model reach affective polarization") - but whether it reliably ARRIVES in the target
  quadrant (vs. still depending on network realization) needs the full seed battery (~20-30, already
  planned in the 2026-06-19 design doc), not just 3.** Given the time cost per run (~9-13 min at this
  density), full seed-battery replication is deferred as a distinct, explicitly-scoped next task
  rather than continued ad hoc single/triple-seed probing.
  - **Table (seed 0/1/2 at max_follow=45):**

    | metric | seed 0 | seed 1 | seed 2 | mean |
    |---|---|---|---|---|
    | opinionAssortativity (follow) | 0.796 | 0.914 | 0.867 | 0.859 |
    | crossCuttingFraction (follow) | 0.038 | 0.016 | 0.043 | 0.032 |
    | interactionAssortativity | 0.304 | 0.566 | 0.357 | 0.409 |
    | interactionCrossCuttingFraction | 0.279 | 0.185 | 0.387 | 0.284 |
    | meanTolerance | 0.462 | 0.564 | 0.426 | 0.484 |
    | zero-follower | 71 | 18 | 40 | 43 |
