# 2026-07-07 — Model-structure review (pre-freeze critique)

Full-code structural review (Agent / OpinionDynamics / AdminOptim / Analysis / InterventionSetup /
DCSBMNetwork / Const) against the north-star estimand in `docs/research-direction.md`. Scope:
model structure only — experiment/simulation plan excluded by request. Findings ranked by threat
to the headline claim. No code changed in this pass; each item is a discrete decision to take.

## Tier 1 — validity threats (the paper's claim is currently untestable or inflated)

1. **Treatment lever λ is pinned, and pinned at a value that neuters the conduit.**
   The 2026-06-26 parsimony decision set relay distortion `s := stubbornness = 0.8`
   (`Agent.relay()`), i.e. λ = 1−s = 0.2 fixed. A moderate (O≈0) relaying an extreme post (O=+1)
   conveys 0.2 — inside almost every receiver's tolerance (initial bc=1.0, floor 0.2). The
   estimand's treatment ("conduit activity, λ commentary blend") is not manipulable and, at the
   pinned value, the conduit-backfire mechanism can barely fire at all. The Step-0 DAG lists λ as
   an independent factor; the code contradicts the DAG. **Fix: decouple λ from stubbornness and
   sweep it.** Parsimony argument fails here because λ is the *treatment*, not a nuisance.

2. **The reattribution bypass — declared load-bearing for Type 2 (§3 item 2 + item 7
   "burden of producing Type 2 rests on the reattribution bypass") — is not implemented.**
   `relay()` deliberately keeps `postUserId` = original source; `unfollow()`/block and the
   per-source feed filter (`addToPostCash`, `addPostToFeed`) still target the source. Of the three
   code-grounded pathologies in research-direction §2, only the ε-gate (#3) is fixed; conduit
   immunity (#1, wanted) and the self-limiting block filter (#2, Type-2-destroying) are both still
   live. The DAG's attribution mechanism-switch cannot be run. **Fix: Post carries both `sourceId`
   and `relayerId`; an attribution parameter a∈[0,1] (or toggle) decides which id unfollow/block
   and the feed filter act on.** Note the recent affective-polarization movement came from
   `MAX_FOLLOW_CAPACITY`, i.e. a density knob, not from the conduit mechanism — as it stands the
   paper risks demonstrating "capacity relaxation reduces sorting", with the conduit causally idle.

3. **Construct validity of the y-axis: mean ε is generalized intolerance, not affective
   polarization.** Affective polarization in the literature (Iyengar et al.) is *group-indexed*
   negative affect (out-party thermometer gap). Mean bc falls from any disagreement, including
   within-camp. A reviewer can collapse the headline by noting Type 2 is asserted from a scalar
   that never references out-group. **Fix (measurement, cheap): report hostility conditioned on
   camp — e.g. block/unfollow events split by same- vs cross-camp target, ε decline attributable
   to cross-camp content, or a dyadic in/out affect gap.** Keep mean ε as a companion, not the
   definition.

4. **Cumulative interaction-graph metrics mechanically inflate the Type-2 signal.**
   `repostNetworkCumulative` accumulates from t=0; if the system sorts over time, early
   high-mixing edges keep cross-cutting high and assortativity low forever. The strongest result
   to date (interactionAssortativity 0.17 at max_follow=60) may partly be a transient average, not
   the equilibrium regime. **Fix: windowed (sliding or post-burn-in) interaction metrics alongside
   cumulative.** Must be resolved before the Step-3 freeze — it touches the headline table.

5. **x-axis lacks the definitional quantity: connectivity.** Type 1 vs Type 2 is *defined* by
   "network fragments" vs "stays connected", yet no component/reachability metric is exported.
   Assortativity can be ~1 while the graph is still one weak component. **Fix: export largest
   weakly-connected-component share, component count, and cross-camp reachable fraction.**

## Tier 2 — mechanism consistency (reviewer-catchable contradictions)

6. **Two posting-probability feedbacks are BOTH active**, though research-direction §3 item 6
   records the choice as *deferred either/or*: marginal-utility (`updatePostProb`, MU_PARAM) AND
   comfort-rate spiral-of-silence (`updateMyself`, COMFORT_PP_FACTOR ×1.1 / ÷1.1) compound
   multiplicatively every step. The spiral-of-silence half also silences the vocal moderate — the
   doc's own flagged contradiction — and it is currently ON. **Fix: pick one (or gate one off by
   default), matching the doc.**
   **RESOLVED 2026-07-09:** `MU_PARAM` removed entirely (`docs/report/2026-07-08-validation-gate-pilot.md`,
   "MU_PARAM removed" section); `COMFORT_PP_FACTOR` is now the sole posting-probability feedback.

7. **`follow()` eviction is an assumption masquerading as a mechanism (fails the litmus test) and
   uses omniscient information.** Evict-most-disagreeing can only increase homophily — it is a
   second, hard-coded sorting force confounding P_u (empirically confirmed dominant, 2026-06-26).
   It also reads `agents[i].getOpinion()` — ground-truth current opinions of all followees —
   whereas every other decision uses observed posts. **Fix: parameterize eviction policy
   {most-distant | random | least-recently-seen}, computed from last-seen post opinion.**

8. **Intervened hubs are not actually clamped.** `InterventionSetup` sets `intrinsicOpinion` only;
   with μ=0.8 an "extreme" hub posts 0.8·(±1)+0.2·feedmean and the "moderate" hub drifts ±0.2 with
   its feed. "Holding source extremity fixed" (the estimand's conditioning) is only approximate.
   **Fix: `setStubbornness(1.0)` for target hubs.**

9. **Two inconsistent notions of "comfort".** `updateMyself` counts comfort against fixed
   `MINIMUM_BC=0.2` (the code comment claims dynamic bc — stale comment) while ε-dynamics and
   like/follow use dynamic bc. Pick one; state it.

10. **ε dynamics are per-post multiplicative ⇒ tolerance velocity scales with feed size.** The
    effective per-step decline is 0.99^(#uncomfortable-in-feed), so FEED_CAPACITY and α silently
    rescale the ε time-constant, confounding feed-design knobs with hostility dynamics. **Fix:
    normalize (e.g. update on the feed's uncomfortable *fraction* once per step), or state the
    coupling explicitly and keep S fixed across all conditions.**

## Tier 3 — plumbing & polish

11. **`like()` is dead code** — never called in `evolve()`; agent-level like counts actually come
    from reposts (OpinionDynamics:184). The "100 likes ⇒ 1.46×" marginal-utility story is really
    a repost-count story. Remove or wire; align paper terminology.
12. **Velocity plumbing leaks:** likes on relayed copies accrue to the copy object and never reach
    the original's velocity score; relayed (distorted) posts never enter the For-You pool, so at
    high α the algorithmic channel carries only *undistorted* originals — a structural λ×α
    asymmetry worth either fixing or stating.
13. **"Soaring" not implemented as decided:** `velocityScore` = cumulative likes/((age+1)(followers+1)) —
    a normalized average rate, not relative velocity/acceleration vs the author's baseline.
    Acceptable first pass; rename or upgrade before the freeze.
    **PARTIALLY REVISITED 2026-07-09:** the `(followers+1)` divisor was removed entirely (not
    replaced with the originally-envisioned relative-to-baseline version) after it was found to
    suppress the moderate hub's own algorithmic visibility — see
    `docs/report/2026-07-09-oat-sweep-findings.md`'s velocity-formula section. `velocityScore` is
    now plain `receivedReposts/(age+1)`; the original "soaring" spec (rate relative to the
    author's own historical baseline) is still not implemented, and this critique's core point
    (name/behavior mismatch) still applies in a different form.
14. **Blocks are unobservable:** `unfollow()`'s block-only branch returns −1 and is counted
    nowhere; the self-limiting-filter mechanism can't be monitored. Log block events + list sizes.
15. **Initialization inconsistency:** at DC-SBM avg out-degree ~17.5, agents start above their own
    follow capacity; the cap binds only on new follows. State or reconcile.
16. **Bimodality metric:** excess kurtosis ≠ bimodality; compute Hartigan dip / Sarle's b in
    post-processing (already noted in doc, still unimplemented).
17. **crossCuttingFraction sign-split is noisy near O=0** (intrinsics ~N(0,0.6)): exclude a
    |O|<τ neutral band or use quantile camps.

## Analytical backbone (cheap wins for a top-tier venue)

- **FJ band-limit:** o_i,t = μ·o_int + (1−μ)·feedmean ⇒ |o − μ·o_int| ≤ 1−μ = 0.2 and opinions are
  memoryless given the feed. Frame the model honestly as a **fast–slow system**: opinions are fast
  and band-limited; ε and the graph are the slow state variables where polarization actually
  lives. This preempts "why doesn't opinion variance move" and justifies the tolerance axis.
- **ε stationarity condition:** with decline factor δ=0.99 and recovery (1+γ), tolerance drifts
  down iff the uncomfortable feed share u > u* = ln(1+γ)/(ln(1+γ) − ln δ) (γ=0.005 ⇒ u*≈0.33).
  A closed-form phase boundary — derive it in the paper.
- **DC-SBM hub ceiling is a finite-size law, not just the soft-cap:** natural cutoff
  k_max ~ n^{1/(γ−1)} ≈ 1000^{0.77} ≈ 200, matching the observed ~210–230 ceiling. State it; also
  motivates an N-scaling robustness check.

## Suggested resolution order (model structure only)

Tier 1 items 1–2 (λ decoupling + dual attribution) are the paper's treatment and mechanism —
do first. Items 3–5 are measurement and must precede the Step-3 freeze. Tier 2 items 6–8 are
one-line-to-small fixes with outsized reviewer exposure. Tier 3 during calibration.
