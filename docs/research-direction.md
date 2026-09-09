# Research Direction — Moderate Conduit & Two Types of Polarization

> **Standing north-star note.** Captures the final research goal, the agreed conceptual frame, the
> code-grounded reality of the current model, and the required model changes. Detailed dated design
> decisions live in `docs/report/`. This file is the canonical "what we are ultimately doing and why."
> Created 2026-06-23.

> **⚠️ UPDATE 2026-07-08 — Type-2 redefined, hostility/affective axis deprioritized.** The
> conceptual frame in §1 below (Type 2 = "connected but hostile," measured via `hostility`) has been
> **superseded**. Working definition now: **Type 1 (structural separation) is the base state; Type 2
> is the phenomenon of a moderate hub creating cross-cutting opinion flow *between* otherwise-separated
> communities**, measured structurally (cross-cutting exposure / cross-repost fraction attributable to
> the hub), not via affective hostility. Hypothesis: this requires a scale-free-like (heavy-tailed
> degree) network — plain modular/segregated topologies without hub concentration may not produce it.
> The moderate hub's *existence and structural role* is the object of study, not escalating affective
> polarization per se. Consequently `hostilityActive=false` and `relayEnabled=false` (both set
> 2026-07-08, see `docs/report/2026-07-08-relay-ablation-diagnostic.md`) are **not** stopgap
> simplifications to revisit later — they are consistent with this redefinition, since neither
> hostility nor relay-distortion is load-bearing for a purely structural bridging question. §1–§3
> below are kept for historical record of the prior frame; treat any claim there **tied to hostility
> or affective polarization** as superseded until this file's body is rewritten to match.

---

## 0. Target & timeline (absolute dates)

- **Venue:** Complex Networks 2026 (submission target).
- **Simulation working to some extent:** by **mid-July 2026**.
- **First paper draft:** by **end of July 2026**.
- Base code/paper: `docs/wssit2026-TomoyaTakeda.tex` (this line of work). `docs/journal.tex` is a **separate** paper — out of scope.
- We **accept that the model must change drastically.** The immediate aim is to *tidy the objective* so editing is principled, not to preserve the current model.

---

## Working method (claim-driven loop — run in this order)

The naive loop "fix the model → design the experiment → see results → refine" has a trap: **model
structure and experiment design are co-constraining**, measurement must be designed up front, and the
network is a *precondition* (not a setting) for this theme. So we run a **claim-driven** loop, with a
**freeze gate** before the main batch to avoid garden-of-forking-paths / model-overfitting under the
deadline.

- **Step 0 — Pin the estimand & causal chain (DAG below).** What exactly are we identifying? It *drives* every model degree of freedom below. Do this **first**.
- **Step 1 — Co-design (driven by Step 0), three things together:**
  - **(a) Agent behavior** — only the knobs the causal chain requires: `P_u` (tie-dissolution), reactance strength, commentary blend `λ`, repost **attribution** (source vs conduit), influencer **scale**.
  - **(b) Initial network = precondition, not a setting.** The network is *endogenous* (follow/unfollow rewires it), so what matters is the **equilibrium** structure. It must **host mid-scale moderate hubs at equilibrium** — the current winner-take-all network (`MAX_FOLLOW_CAPACITY=10`, H4) does not. If it can't host them, the hypothesis is untestable. Likely the single biggest task.
  - **(c) Outcome instrumentation** — the **2-D plane** (structural separation × affective polarization) wired into the model from the start. *Not* a downstream step.
- **Step 2 — Validation gate (pilots):** equilibrium reproduces stylized facts; network actually yields mid-scale hubs; confirm the model can reach **both** Type 1 and Type 2 (if it can't produce both, nothing is identifiable).
- **Step 3 — Freeze + pre-specify experiment, then run main batch:** factors/levels + identification strategy (see DAG). Model is frozen here.
- **Step 4 — Results → bounded refinement:** analysis/design refinements stay in-phase; any *model* change loops back to Step 2 (re-validate, don't silently refit).

## Step-0 causal DAG (the estimand)

**Estimand:** the marginal effect of *moderate-conduit activity* on **Type-2 vs Type-1** polarization,
**holding source-extremity fixed**.

```
  [Source extremity]                         (exogenous background; HELD FIXED)
   extreme ±1 hubs                            without it the conduit has nothing to carry:
        │                                     (I,A,I) ≈ (I,I,I)
        ▼
  ┌─────────────────────┐   T (treatment)
  │ Moderate-conduit     │◄──── scale (mid vs large)   ← confounded w/ position in current model;
  │ activity (repost/    │      λ commentary blend       must be an INDEPENDENT factor
  │ quote, mid-scale)    │
  └─────────┬───────────┘
            ▼
   [Cross-cutting exposure]   (mediator M1: out-group content reaching agents)
            │
            ├──────────────► [Attribution] ── to conduit (bypass) ─┐  mechanism switch
            ▼                                  to source           │
   [Reactance / ε-decline]  (mediator M2: hostility ↑)             │
            │                                                       │
            ▼                                                       ▼
     ┌──────┴───────────── P_u (tie-dissolution) = PHASE KNOB ─────┴──────┐
     │ high P_u (cut ties)                       low P_u (+ bypass)        │
     ▼                                                                     ▼
  OUTCOME-x ↑  structural separation            OUTCOME-x ↓  stays connected
  OUTCOME-y ↑  hostility                         OUTCOME-y ↑  hostility
  = TYPE 1 (upper-right)                          = TYPE 2 (upper-left)  ← target
```

**Identification plan (what each arrow buys us):**
- **Treatment:** manipulate conduit activity while holding source extremity fixed (isolates T, not the source).
- **Phase knob:** sweep `P_u × reactance` → the **phase diagram**; locate where the conduit's effect *flips* harmful.
- **Mechanism:** mediation through cross-cutting exposure (M1) and hostility (M2); toggle **attribution** (source vs conduit) to test the Type-2 bypass.
- **Counterfactuals:** (i) ablate Confidence Decline (is backfire doing the work?); (ii) **degree-matched rewiring** that delivers the *same* cross-cutting exposure *without* a moderate conduit (is it the bridge, or just the exposure?).
- **Deconfound:** make **scale** an independent factor from **position** (currently entangled).

---

## 1. Final goal (the "will")

Establish, via a network ABM, that **mid-scale, moderate-but-vocal influencers ("explainers/commentators") act as the conduit that produces society-wide affective polarization** — *not* by being extreme themselves, but by circulating all kinds of opinion across the network so that **backfire happens everywhere**. The honest framing is **transmission/amplification**, not "sole culprit": extremes are the *source*, the moderate is the *transmission path*. (`(I,A,I) ≈ (I,I,I)` already shows: no source ⇒ the conduit alone is harmless.)

### The two polarizations (core conceptual contribution)
- **Type 1 — Completely separate.** Structural echo chambers; communities mutually invisible; "I don't even get why the other side is excited" (e.g. 参政党 vs 安野 type mutual incomprehension). = network fragmentation.
- **Type 2 — Controversial polarization.** Affective polarization. The network **stays connected**, hostile content is *continuously supplied* via "explanation/dunking," so the society **keeps burning**. ← **This is what we simulate.**

### Key insight (correct, and central)
In the model a verbatim repost carries the *original* opinion to followers, i.e. **"a moderate reposting an extreme = the moderate expressing that extreme in their own voice."** Followers direct moral outrage at the *messenger who brought it in*. This is the mechanistic seed of Type 2.

---

## 1a. Redefinition (2026-07-08) — structural bridging, not affective escalation

**Supersedes the "two polarizations" framing above and the hostility-centric Type-2 axis.**

- **Type 1 (base state):** structural separation — the follow graph settles into mutually-invisible
  communities (high modularity / opinion-assortativity, low cross-cutting-edge fraction). This is
  the *default* equilibrium the model is expected to reach, not a failure mode to escape.
- **Type 2 (the phenomenon of interest):** **given** that Type-1-style separation is the base
  structural state, a moderate hub's presence causes opposing-camp opinions to still cross between
  otherwise-separated communities — via repost, regardless of whether the reposted content is
  distorted en route. The object of study is the **existence and structural role of the moderate
  hub as a bridge**, not an escalating affective/hostility state.
- **Working hypothesis:** this bridging effect requires a **scale-free-like (heavy-tailed in-degree)
  topology** — a plain segregated/modular network without hub concentration may not produce
  measurable cross-cutting flow even with a moderate agent present. Testable directly via
  `networkType` + `sbmGamma` (DC-SBM's Pareto exponent) sweeps, or `networkType` comparisons
  (dcsbm vs ws/random/lfr).
- **Consequently not required for this question:** `hostility` (affective state) and relay
  content-distortion (`relAttrib`, `coupleRelayDistortion`, `thetaDist`). Verbatim repost (no
  content distortion) already achieves "opposing opinion reaches the hub's audience" — distortion
  was only load-bearing for the *old* affective-backfire/reattribution-bypass story. Both are set to
  `false`/inert (2026-07-08, `docs/report/2026-07-08-relay-ablation-diagnostic.md`) as a considered
  match to this redefinition, not a placeholder simplification.
- **Measurement:** use the already-implemented structural instrumentation in `Analysis.java`
  (`computeCrossCuttingFraction`, `computeInteractionCrossCuttingFraction`,
  opinion-assortativity, directed Newman modularity) rather than hostility. The key comparison is
  cross-cutting exposure **attributable to the moderate hub specifically** — e.g. with vs. without
  the hub, or degree-matched rewiring without a moderate conduit (already named as a counterfactual
  in the DAG above, and still valid under this redefinition).

**Not yet decided / open for the validation phase:** exact operationalization of "cross-cutting flow
attributable to the hub" (a mediation-style decomposition vs. a simple with/without-hub contrast),
and which network types to include in the scale-free-dependency check.

---

## 2. Code-grounded reality (verified 2026-06-23) — 1 win, 2 losses

The current model has the *seed* of Type 2 but two mechanisms that actively **destroy** it. Naively run, **it produces Type 1 (gradual fragmentation) and only looks like Type 2.**

1. **✅ Conduit immunity.** Reposts keep the original author id (`Post.java`); unfollow targets `post.getPostUserId()` = **original author** (`Agent.java:436-442`). So a follower who dislikes a moderate-relayed extreme post unfollows/blocks the **extreme source**, *not* the moderate. The moderate bridge is structurally immune → it persists. (This is the Type-2 seed and confirms the key insight.)
2. **❌ Per-source block filter (self-limiting).** `addToPostCash`/`addPostToFeed` (`Agent.java:199-204, 225-229`) drop any post whose author is in `unfollowList`. Once a follower blocks an extreme source, that source's content **never reaches them again, even via the moderate.** So "backfire everywhere" **burns out its own fuel** → source-by-source fragmentation = slow **Type 1**.
3. **❌ ε-gate on repost.** A moderate `O≈0` can only repost an extreme `O≈1` while `ε ≥ 1.0`; Confidence Decline drops ε on the first uncomfortable contact, so the bridge opens at `t≈0` and immediately closes. Without a quote-repost mechanism the conduit barely operates.

### Reframing that this forces (and that strengthens the paper)
**Type 1 and Type 2 are not different phenomena but two phases of the same model**, separated by the **tie-dissolution rate `P_u` (and reactance strength)**, not by opinion:
- high `P_u` (cut on discomfort) → homophilous sorting → **Type 1**.
- low `P_u` + strong reactance ("hate-follow"/doomscroll: can't look away, can't cut) → connected but hostile → **Type 2**.
The model's `uncomfortable → unfollow w.p. P_u` rule is fundamentally a **Type-1 (sorting) rule**, which is why naive runs go to Type 1.

> **The paper = a phase diagram.** Over `P_u × reactance`, find the threshold where the moderate conduit's effect **flips** from harmless/de-escalating to "fuel for Type 2." The moderate is a "culprit" only in the low-`P_u` phase. This is far more robust and counter-intuitive than a binary "moderates are bad."

---

## 3. Required model changes (to make Type 2 *emergent*, not assumed)

> **Modeling principle — "knob, not assumption" (litmus test).** Every mechanism must be a knob whose
> polarizing effect is *measured*, not assumed. Test each rule: **can it produce the opposite outcome
> under some parameter/topology setting?** If no, it's an assumption masquerading as a mechanism and it
> makes the headline tautological. Failed the test: monotone ε (can only lower tolerance), a
> recommender that deliberately injects in-group-viral content into out-group feeds (can only raise
> uncomfortable exposure). Passed: asymmetric ε with recovery, an opinion-blind velocity recommender.

1. **Quote-repost (commentary) — lifts the ε-gate.** A moderate may relay out-of-tolerance content as "explanation" w.p. `P_r^out`; conveyed opinion `O_conveyed = λ·O(p_j) + (1−λ)·O_rep` (λ=1 verbatim ↔ λ→0 heavy reframing). This single lever also lets the model produce the **de-escalation counter-hypothesis** (otherwise the result is non-informative / equifinality).
2. **Reattribution bypass — decouple hostility from tie-cutting.** Let the receiver attribute relayed content to the **moderate conduit**, not the hidden original source. Then ε declines (hostility ↑) **without** triggering a block of the source → the self-limiting filter (#2 above) stops, connection persists → **true Type 2**. This is the correct implementation of the "moderate spoke in their own voice" insight.
3. **Make backfire emergent/conditional — ε recovery DECIDED (2026-06-23).** Replace the monotone (decrement-only) ε ratchet with an **asymmetric** rule: ε declines fast on uncomfortable contact, **recovers slowly** on comfortable contact, with `γ_recover ≪ δ_decline`. This (a) correctly operationalizes the cited negativity bias (Baumeister 2001 / Vallone 1985 support *asymmetry*, not *irreversibility* — Baumeister's own thesis is good can offset bad, just slowly), (b) makes monotone-only the special case `γ_recover = 0` ⇒ free robustness panel, (c) lets the system **sustain Type 2** (a ratchet structurally forbids it), (d) adds `γ_recover` as a phase knob alongside `P_u`. Backfire is empirically contested (Guess & Coppock 2020) so it must be discovered, not wired in.
4. **Scale as an explicit factor.** Select influencers by in-degree percentile band; sweep **scale × position (continuous) × λ**. Test "mid-scale moderate worse than large extreme." NB current network is winner-take-all (`MAX_FOLLOW_CAPACITY=10`), so genuine mid-tier hubs need a **denser initial network** (H4) first.
5. **2-D outcome measurement.** Plot trajectories in **(x) structural separation (modularity / assortativity / cross-cutting-edge fraction) × (y) affective/opinion polarization (bimodality: dip test / kurtosis over ALL `O_i`)**. Type 1 = upper-right, Type 2 = **upper-left** (low separation, high hostility). Also: decompose cross-cutting *exposure* attributable to the moderate hub; mediation analysis (source vs conduit). Variance-of-posted-opinions alone **cannot** tell Type 1 from Type 2.

6. **Recommender = opinion-blind, velocity-primary feed ("For You" as high-α default).** Model the 2026 default feed as **recency-biased engagement ranking**: a For You feed surfaces *recently rapidly-fueled* posts, so it *reads* chronological without being chronological. Formalize: feed capacity `S`; fill `⌊α·S⌋` slots with top **velocity-ranked recent** posts, the rest with **chronological-from-follows**.
   - **`α` = algorithmic share, swept [0,1]:** pure chronological (α=0, Mastodon) ↔ pure For You (α=1, TikTok). The velocity-primary inversion = a **high-α default operating point**, kept as a *parameter* (not hardcoded) to preserve identification and place real platforms on the axis. Justify chronological as a *tunable substrate*, NOT as "how feeds work" (false for 2026 — soft target).
   - **Trigger = absolute velocity (reposts per unit time), NOT follower-normalized (SUPERSEDES 2026-06-23, decided 2026-07-09, reaffirmed 2026-07-16).** The earlier "soaring small-account" requirement is retired: follower-count normalization was found to suppress the moderate hub's own algorithmic visibility (`docs/report/2026-07-09-oat-sweep-findings.md`), and small-account discovery is **not a research goal** of this paper — the mechanism only needs to plausibly model *an* engagement-ranked feed, not specifically a diversity-promoting one. Consequence, stated plainly: with no normalization and no content-intensity signal on `Post` (opinion is the only per-post attribute), velocity ranking functionally reduces to **"surface whichever account is currently accumulating reposts fastest"** — an influencer/hub-visibility mechanism, not a divisive-content amplifier and not a small-account amplifier. Frame it this way in the writeup; don't cite content-intensity-amplification literature (e.g. Milli et al. 2023) as motivation since that mechanism isn't implemented.
   - **Reach = hop-count `h` (positive integer), the now load-bearing parameter (governs the whole system at high α).** For each agent `i`, the For-You candidate pool = velocity-fueled posts among accounts within `h` hops of `i` (recipient-centered). `h=1` ≈ direct network (mild reorder of chronological, effectively a control) → `h=2` friends-of-friends (out-of-network injection begins) → large `h` ≈ global trending. Small `h` → within-cluster reinforcement → **Type 1**; large `h` → cross-cutting → **Type 2**. `h` is also exactly the **conduit-vs-algorithm tradeoff knob** (small `h` keeps the follow graph → conduit matters; large `h` washes it out → conduit redundant). Selection is **opinion-blind**; comfortable/uncomfortable landing is **emergent**. Caveats: (i) **hop direction** on the *directed* scale-free graph must be fixed (out-edge / in-edge / undirected differ sharply — hubs have huge in-degree, capped out-degree; default undirected proximity or out-edge discovery, state it); (ii) **hop resolution depends on network density** — densifying for mid-scale hubs (1b) makes `h` saturate faster, so `h=2-3` may already ≈ global; **measure realized `h`-hop reachable fraction on the *final* network**, don't assume the range.
     - **⚠️ UPDATE 2026-07-29 — caveat (i) resolved; hard cutoff replaced by distance decay; self-reinforcement now measured.** See `docs/report/2026-07-29-feed-reach-redesign.md` for full detail. Reach BFS now traverses **followees-only (out-edges)** — a hub's in-degree no longer inflates other agents' hop-reach, which likely *shifts the realized reachable fraction at any given `h`* relative to everything calibrated so far (v15's `alpha=0.7, hop=3` included) — re-validate, don't assume it transfers. The binary hop cutoff is now a distance-decay **acceptance probability** (`feedDecayMode`: `exp`/`inverse`, `hard` kept as the legacy ablation arm), swept via `feedDecayLambda` (magnitude DEFERRED). Post lifespan / self-reinforcement is now instrumented (`postLifespanMean`, `postStillActiveAtEvictionFrac`); an initial smoke test found ~60% of evicted reposted posts were still actively gaining reposts at eviction — the fixed 100-step window plausibly truncates real virality rather than measuring natural die-off; an optional `feedTimeDecayTau` dampener exists (default off) but its magnitude is undecided.
   - **CRITICAL risk of the inversion — conduit redundancy.** At high α with *global* reach, everyone sees the same hot posts ⇒ the follow graph (and thus the moderate conduit) can be washed out and become redundant — this would silently kill the main research object. Global velocity-primary is essentially **Törnberg 2022's** algorithmic-exposure Type-2 engine on its own; you must then **show the conduit adds incremental Type-2 beyond the algorithm** (algorithm-on-vs-off + degree-matched contrast), or the paper reduces to reproducing Törnberg.
   - **Block/unfollow applies to For-You-delivered posts (DECIDED 2026-06-23).** Reuse the existing rule: an uncomfortable post from a *not-yet-followed* author triggers block w.p. `P_u` — and For-You delivers exactly such out-of-network content, so it is treated identically. Consequence: For-You is also a **block generator** → another **Type-1-leaning** choice (stacks with deferred reactance); reinforces that Type-2 production rests on the reattribution bypass. `P_u` (phase knob) applies here too.
   - **Posting-probability rule DEFERRED to calibration (2026-06-23):** unresolved code/paper mismatch — received-likes marginal utility (`Agent.java:239-248`) vs spiral-of-silence (comfortable fraction). Don't yet know which is better; decide in Step 2. (Watch: the spiral-of-silence variant silences moderates, contradicting "vocal moderate.")
   - **Keep it a toggle / swept factor** for conduit × recommender interaction. Useful deliberate contrast: **local recommender (deepens Type 1)** vs **moderate conduit (creates Type 2)**. Keep reach variable or it's a hidden ratchet (litmus test). Cite Guess et al. 2023 (chronological barely moved polarization) ⇒ studying the *mix* is the open question.

7. **Keep Social Influence (FJ) — it is the convergent pole (DECIDED 2026-06-23).** Retain Friedkin-Johnsen assimilation. Reasons: (a) it is the **only opinion-movement channel** — without it `O_i` is frozen and the affective/opinion axis (y-axis of the 2-D outcome plane) is dead, leaving only structural Type 1; (b) by the litmus test it is the **convergent force that keeps consensus/collective-agreement reachable** — removing it leaves only divergence ⇒ polarization is guaranteed ⇒ tautological. FJ alone is *purely assimilative* (can only converge). **Reactance term DEFERRED (2026-06-23):** the divergence pole is provided for now by the **structural backfire effect** (bounded-confidence decline → unfollow/block → sorting; the term defined in `journal.tex`), which produces segregation-driven divergence *without* an opinion-repulsion term. Add reactance only **if** the Step-2 gate shows the model cannot reach Type 2 (it is the first knob to restore). **Consequence to track:** without reactance the only divergence channel is *structural sorting*, which is intrinsically **Type-1-leaning**; the burden of producing **Type 2** (connected-but-hostile) therefore rests on the **reattribution bypass (item 2)** plus measuring affective hostility via **ε/tolerance**, not opinion variance (affective ≠ opinion polarization — people can hold near positions yet have collapsed tolerance). **`β` retuning DEFERRED to calibration** (don't know optimal value; `β=0.8` may be too anchoring for consensus to be reachable — revisit in Step 2).

### Known code/paper mismatch to resolve (potential reviewer-killer)
Post probability in code uses a **received-repost marginal-utility** rule (`Agent.java:239-248`), **not** the paper's spiral-of-silence (comfortable-fraction) rule. Decide which is canonical and make text/code consistent. (The code version — "more reposted ⇒ more vocal" — actually favors this theme.)

---

## 4. Status & next session (updated 2026-07-09)

**Planning (Step 0–1a) and implementation (R0–R26, phases 1–4) are done.** Outcome instrumentation,
the DC-SBM network switch, the velocity-primary feed, and the asymmetric-tolerance/relay mechanisms
are all in place (`docs/report/2026-07-07-implementation-phase1.md`). **We are now inside Step 2
(the validation gate)**, not about to start implementation.

**Step-2 progress so far (2026-07-08 → 2026-07-09), see `docs/report/2026-07-08-validation-gate-pilot.md`
and `docs/report/2026-07-09-oat-sweep-findings.md` for full detail:**
- Pilot v1/v2 (n=500, steps=15000→30000): structural-separation metrics are still slowly trending
  even at 30000 steps (not a clean plateau — likely needs a late-window average rather than a
  point-in-time reading, not just a longer run); DC-SBM/LFR host real mid-scale hubs, ws/random do
  not (supports the scale-free-dependency hypothesis so far, not yet definitive).
- Fixed several measurement bugs found along the way: hub-attributable cross-camp bridging now
  uses opinion-at-relay-time (not a final-snapshot proxy that drifted with run duration); DC-SBM
  structural params (`sbm_pin`/`sbm_pout`/etc.) are now tagged so sweeps over them don't silently
  collide folders.
- Removed `MU_PARAM` (conflicted with `COMFORT_PP_FACTOR`; hub growth reassigned to the For-You
  recommender) and then found and fixed a real problem this created: the recommender's velocity
  score divided by `(followers+1)` ("anti-rich-get-richer", decided 2026-06-23) was suppressing the
  moderate hub's *own* algorithmic visibility. Removed that normalization; confirmed at `n=1000`
  that the moderate-hub growth penalty resolves and whole-network degree concentration moves
  *toward* (not away from) the realistic range (real Twitter follower-Gini ≈0.8).
- An OAT calibration/robustness screen (`repost_prob`, `bc_inc`, stubbornness, `sbm_pout`, `alpha`,
  and four previously-unswept "scale" knobs newly exposed to CLI) found most of these are **not**
  inert — they move the Step-2 gate metrics, some substantially. `bc_inc`'s effect could not be
  pinned down even at 10 seeds (the readout metric — hub-mediated cascade count — is heavy-tailed/
  rare-event-dominated; needs a variance-robust summary, not more seeds).

**Open items before the Step-3 freeze:**
1. Gate 1 (plateau) still not clean at 30000 steps — decide on a late-window-average reporting
   convention rather than chasing a point-equilibrium.
2. `bc_inc` needs a better metric (median/exceedance-probability) before its magnitude can be picked.
3. Tier-D "scale" knobs (`feed_capacity`, `follow_prob`, `comfort_pp`) turned out load-bearing, not
   inert — need a proper robustness pass (can be deferred to a post-Step-3 robustness appendix,
   per this session's methodological discussion, since these are nuisance-parameter *levels*, not
   the treatment contrast itself).
4. `alpha=0.6`'s residual (smaller, not fully resolved) moderate-hub growth penalty.
5. The degree-distribution/heavy-tail check should be re-run at `n=1000` for any other network
   type or `alpha` value not yet covered (only `alpha∈{0.3,0.6}` vs. baseline done so far).

Once these are resolved (or explicitly deferred with a stated reason, as several already are),
proceed to Step 3: freeze the model, pre-specify the Tier-A experimental factors (`p_u`, network
type, hub scale-vs-position — deliberately not touched during Step 2, "the model needs to stand on
its own as credible first"), and run the main batch.

---

## 5. Pointers
- Detailed dated design log: `docs/report/2026-06-19-experimental-design.md` (see 2026-06-23 entry for the 5-point critique + redesign directions).
- Implementation handoff: `docs/report/2026-07-07-implementation-phase1.md`; pre-freeze structural critique: `docs/report/2026-07-07-model-structure-review.md`.
- Step-2 validation gate + calibration sweep (current work): `docs/report/2026-07-08-validation-gate-pilot.md`, `docs/report/2026-07-09-oat-sweep-findings.md`.
- Base paper: `docs/wssit2026-TomoyaTakeda.tex`.
