# 2026-08-02 — Delayed-conduit-entry mechanism: pilot, mechanism investigation, robustness, paper framing

## Context / motivation

Session opened on a structural observation: this model's network is a "hub plateau" (~10
comparably-dominant hubs, top-1% holds ~31% of follow-edges) rather than WSSIT-era's single
star-dominant hub (top-1% held ~73%, see `docs/report/2026-07-31-wssit-era-vs-current-model-diff.md`).
Prior work (`docs/report/2026-07-21-conduit-experiment-design.md`, 2026-07-27 through 2026-07-31
entries) already established via counterfactual node-removal that individual mega/middle-tier
moderate hubs are **not individually necessary** for cross-camp cascade reach (necessity 0.07-0.64%,
"founder-clique redundancy" — many hubs have overlapping reach, so removing any one has almost no
effect). This raised the question: does a moderate conduit matter at all, or only as a collective
class?

Reframed via discussion: the intended real-world analogue is a figure who is popular for reasons
**orthogonal to the topic at hand** (e.g. a celebrity unrelated to politics who is broadly followed
across camps because of unrelated fame) and who only starts speaking on a contentious topic once
it's already heated — as opposed to hubs that grew their following endogenously through this
topic's own opinion-homophily dynamics (which is what the mega/middle/small/peripheral tiers used
in the prior removehub battery are). This motivated a new intervention mechanism.

## Implementation: delayed-conduit-entry mechanism

New `ExperimentConfig` fields (`src/experiment/ExperimentConfig.java`), wired into
`OpinionDynamics.evolve()`:

- **`pinModerateIds`**: for the given agent IDs, `intrinsicOpinion`/`opinion` are reset to exactly
  `0.0` at `t=0` (a ONE-TIME reset, not a permanent freeze) and `setTarget()` is called (excludes
  them from natural-intrinsic-opinion population counts and from `computeOpinionAssortativity`/
  `computeCrossCuttingFraction`, same convention as `InterventionSetup.pinHub`). **Stubbornness is
  deliberately left at its normal per-agent draw, NOT forced to 1.0** (user decision, 2026-08-02:
  "this agent isn't stubbornly moderate, they simply weren't engaged with the topic yet — once
  engaged, their opinion should be free to move like anyone else's"). Verified via smoke test: final
  |opinion| for pinned agents drifts to mean 0.02-0.04 (max ~0.12), confirming genuine but modest
  post-activation drift, not frozen.
- **`silentUntilIds` + `activationStep`**: agents in the set get `ChannelMode.NONE` at `t=0`
  (complete silence — no posting/reposting); at `step == activationStep` their channel switches to
  `cfg.channel` (default `BOTH`). `activationStep` beyond the run length = permanent silence.
- Both fields are deliberately independent (not coupled), matching the existing
  `muteAccessIds`/`muteRepostIds`/`algoExcludeIds`/`removeHubIds` precedent of orthogonal,
  combinable single-purpose ID-list knobs.

**Bug found and fixed during implementation**: `AssertionCheck.java`'s R4 invariant ("pinned hub
must keep its assigned opinion") checked `getTarget()` alone, implicitly assuming every target agent
is fully pinned (`stubbornness==1`, from the legacy `InterventionSetup.pinHub` path). Since
`pinModerateIds` sets `target=true` but leaves stubbornness free, this produced false-positive `AC
Error` reports. Fixed by gating the check on `stubbornness>=1.0` as well as `getTarget()`. Verified
both paths after the fix: legacy full-pin (`extreme=sym n_mod=1`) still asserts correctly (0 errors,
still enforces frozen opinion); new soft-pin mechanism no longer false-flags (0 errors, opinion
genuinely drifts).

**New instrumentation** (`Writer.writeClassFollowerComposition`, `degrees/
class_follower_composition_<step>.csv`): per class-member, current follower count broken down by
5-bin opinion classification, at t=0 and every periodic (5000-step) checkpoint. Zero cost when
`pinModerateIds` is empty. Added to test whether a class member's audience skews toward a
particular opinion bin (raised but not yet resolved — see Open Items).

## Pilot design (5 seeds, 4 arms)

Common config: `extreme=none n_mod=0` (no artificially-pinned ±1 background hubs — natural
emergent extremity from the initial opinion distribution instead, more consistent with
`research-direction.md`'s "knob, not assumption" principle than forced pinning), `alpha=0` (For-You
feed off entirely, isolating follow-graph-mediated dynamics, matching the WSSIT-era regime and this
project's own `alpha0_conduit_replication.py` precedent), `n=1000 steps=40000`, v15 calibration
point otherwise (bc_dec=0.5, bc_init=0.8, max_follow=43.8638, etc.).

**Class selection** (`scripts/delayed_moderate_conduit_pilot.py`): two-phase per seed — (1) a cheap
`steps=0` dry run to read the pure generator's t0 network (before any opinion-homophily rewiring);
(2) from that snapshot, select the **top-20 agents by t0 followerCount among those with
`|intrinsicOpinion| < 0.2`** (rank-based, not an absolute cutoff, so it's robust to seed/generator
scale). Because `network()` and `dynamics()` RNG streams are independent (`rand/randomGenerator.java`
— network topology seeded by `netSeed`, initial opinions by `seed`), and this HK generator forms
edges via preferential attachment independent of opinion, the class's t0 audience is a
population-representative cross-section, NOT homophily-shaped — this is the mechanism that
distinguishes this class from the endogenously-grown mega/middle-tier hubs used in the prior
removehub battery.

Four arms, same seed shared across all four (common-random-numbers pairing — trajectories are
bit-identical up to first behavioral divergence, confirmed directly in later analysis):
- **A_never**: class permanently silent (closest analogue to "exclude the redundant hub plateau
  entirely," the framing this investigation started from).
- **B_always**: class active from `t=0` (no silence — the WSSIT-original-style baseline).
- **C_10k**: silent until step 10000, then activates.
- **D_30k**: silent until step 30000, then activates.

Seeds 7300000-7300004, results under `results/2026-08-02_delayed-moderate-pilot/`. Ran in ~5-6
minutes wall time (20 full runs + 5 dry runs, `alpha=0` is cheap — no velocity-ranking overhead).

**Disk cleanup before this work started**: `results/` had grown to 42GB (300 run directories) from
entirely already-documented, CSV-backed prior investigations (wssit-era comparison, moderate-hub
tier battery, feed-redesign v6 pass, alpha0 replication) with no in-flight dependencies (no running
JVMs). Deleted per the standing `CLAUDE.md` convention (conclusions already in `docs/report/`, raw
output disposable). Freed the full 42GB.

## Pilot findings: timing/erosion mechanics

**Follower-count trajectory** (risk-1 diagnostic, mean class followerCount pooled 5 seeds):
silence does NOT erode the class's follower base (A_never/C_10k/D_30k all track flat at 142.1
through their respective silent periods — the earlier-flagged capacity-eviction risk did not
materialize). But **activation triggers an immediate, sharp follower loss**: C_10k drops
142.1→97.5 (-31%) within 5000 steps of activating at step 10000; D_30k drops 142.1→111.0 (-22%)
within 5000 steps of activating at step 30000; B_always (active from t=0, no "cold open") only
drops to a minimum of 124.2 (-13%) before recovering to 140.8 by step 40000. **The longer the
silence, the sharper the rejection on activation** — confirmed mechanistically via windowed
block/unfollow event rates, which show sharp spikes exactly at each arm's activation step (e.g.
C_10k's blockCount trailing-2000 mean spikes to 1.057 at step 12000, ~4.6x A_never's 0.231; D_30k
spikes to 0.745 at step 32000, ~23x A_never's 0.033).

**Trajectory-level Type1/2 metrics**: B_always diverges from A_never immediately (from step 2000)
and the gap widens monotonically through the whole run. C_10k/D_30k track A_never exactly until
their activation step (confirms common-random-numbers), then show a **short-lived INCREASE in
opinionAssortativity right after activation** (a transient backfire/hardening shock) before slowly,
weakly settling below A_never by the run's end — much smaller and slower than B_always's effect.

**Cascade-level** (pooled 5 seeds, `repost_cascades.csv`): class's share of all extreme-authored
relay events (i.e. how much of the network-wide volume of extreme-camp-originated content the class
personally relays) drops sharply with delay: B_always 2.35%, C_10k 1.73%, D_30k 0.53% — a 4.4x gap
between always-active and 30000-step-delayed entry, directly explaining why timing arms converge
toward "no effect."

**Practical upshot**: continuous presence from the start matters far more than timing of a delayed
entry — C_10k and D_30k end up much closer to A_never (never) than to B_always (always) on every
headline metric, opposite of the naive expectation that delayed entry might dodge redundancy and
land a bigger effect.

## The basic question: does moderate presence change polarization, and how?

Direct A_never vs B_always contrast (moderate absent vs continuously present), n=5 initially,
later confirmed at n=15 (see below):

- **crossCuttingFraction**: consistently higher with B_always throughout the run (ratio to A_never
  grows from 1.17x at step 2000 to ~1.5x by step 40000).
- **opinionAssortativity**: consistently lower with B_always (mirror finding).
- **Extreme-camp (bin0+bin4) per-capita posting rate**: consistently **higher** with B_always
  (+17-25% depending on checkpoint) — i.e. moderate presence does NOT quiet extreme voices, it
  amplifies their posting activity.
- **Pre-extreme-camp (bin1+bin3) per-capita posting rate**: modestly lower with B_always early on
  (-29% at step 2000) but the gap fades to near-zero (-0.7%) by step 40000 — a transient, not
  durable, effect.
- **Final population composition**: extreme-camp (bin0/bin4) population size is essentially
  unchanged between arms (~107-118 each) — moderate presence does not change how many agents end
  up genuinely extreme. What shifts is pre-extreme (bin1/bin3) agents partially staying nearer
  center instead (bin2 population 282→305).

**Important scope clarification confirmed by reading `Analysis.java`**: `computeOpinionAssortativity`
and `computeCrossCuttingFraction` BOTH skip any edge touching a `getTarget()==true` agent (i.e. the
pinned class itself) entirely. So the observed structural differences are NOT a tautology from
counting the class's own edges as cross-cutting — they reflect a genuine second-order/emergent
change in how the REST of the population (~980 non-class agents) organizes itself. This is
important for the paper's novelty framing (see below).

## Mechanism investigation

Grounded directly in code (`Agent.java updateMyself()`): `postProb` is driven SOLELY by
`comfortPostRate` = fraction of an agent's feed within `vocalComfortRadius` (0.1) of their OWN
opinion — NOT by how many times they get reposted (the received-repost marginal-utility rule
mentioned in `research-direction.md` is legacy/superseded; current mechanism is the
`postProbRelaxRate` graded-relaxation-toward-comfort-target redesign from 2026-07-23).

Three candidate explanations tested against data (user's hypotheses), all evaluated on real data,
not assumed:

1. **Mean bc (tolerance) among extreme-camp agents**: essentially unchanged (A=0.2995 vs
   B=0.2911) — **not supported**.
2. **Denser/higher-clustering follow-graph structure among extreme-camp agents**: **refuted in the
   proposed direction** — clustering coefficient among extreme-camp agents is consistently LOWER in
   B_always than A_never (diff -0.057 to -0.079 across checkpoints), not higher. Structurally
   sensible: a bridging hub adds hub-and-spoke ties that don't close triangles among the extremes
   it connects, diluting local clustering rather than raising it.
3. **In-camp circulation volume**: nuanced. Total extreme-authored relay events pooled is nearly
   identical between arms (~7.82M both), and the SHARE reaching extreme-camp relayers (directly or
   via the moderate class) is actually slightly LOWER in B (66.44% vs A's 68.23% direct-only) — the
   moderate substitutes for some direct extreme-to-extreme relay rather than purely adding to it.
   But overall repostCount is +27% higher in B_always and cascade mean size is +26% larger
   (5.44→6.86 relay events/cascade), so a "rising tide" of overall network throughput is a candidate
   secondary driver.

**Proximate-mechanism check (comfort rate directly)**: single-step snapshot reads of
`cRateMean_0`/`cRateMean_4` were too noisy at n=5 to read cleanly (sign flips across checkpoints).
Switching to a **trailing-2000-step windowed average** cleaned the signal substantially:
`feedChronoCountMean` and `feedRepostCountMean` (raw feed item counts landing in extreme agents'
feeds) are consistently higher in B_always at nearly every checkpoint, while `feedPostOpinionVar`
(variance of opinion in that feed) is flat-to-marginally-HIGHER in B, not lower — i.e. the comfort
rate rise is not from feed content becoming more homogeneous/concentrated near the agent's own
opinion, it's from more raw volume landing in the feed, a meaningful fraction of which is
mechanically comfortable simply because the follow network is already homophily-sorted.

**User's counter-hypothesis, tested directly and found more compelling**: is the moderate
structurally embedded in/adjacent to the extreme cluster (so its relayed content — carrying the
ORIGINAL extreme author's opinion tag verbatim, confirmed in `Post.java`: `relayOf` sets
`postOpinion = conveyedOpinion`, and `relayEnabled=false` means no distortion) reaches extreme
agents disproportionately? Tested via cascade chains: of relay events immediately downstream of a
class-authored relay (i.e., someone further relaying what the class relayed), **36.84% are
extreme-camp relayers**, vs. the extreme camp's ~22.5% population share — a **1.64x
over-representation**. Because `postOpinion` on a relayed post is the conveyed (original) opinion,
not the relayer's own, this content reads as fully "comfortable" to a same-camp extreme recipient
regardless of having passed through a near-zero-opinion moderate.

**"Is this a fluke of these 5 seeds" check (user's concern, directly tested)**: two robustness
checks on the existing cascade data, no new simulation needed:
- Concentration check: no single downstream extreme relayer dominates — top-5 relayers account for
  only 2.9%-11.7% of extreme-downstream events per seed (max single-agent share 3.4%), spread
  across 576-739 distinct extreme relayers per seed. Not driven by one lucky-positioned outlier.
- Confirmed directly that non-moderate high-t0-followerCount hubs DO exist in the network (60-75%
  of the top-20 t0-followerCount agents per seed are extreme/pre-extreme, i.e. outside the selected
  moderate class — the "hub plateau" is camp-mixed, as expected) — but these specific non-moderate
  hub agents' own contribution to the extreme-downstream-relay count is negligible (0.5%-3.8% per
  seed). The over-representation is a diffuse effect across many ordinary extreme agents, not
  driven by a coincidentally-connected big hub.

**Still open (not yet resolved)**: whether the 1.64x over-representation reflects (a) the class's
audience genuinely containing more extreme followers than proportional, or (b) extreme-leaning
followers having a higher RELAY PROPENSITY (more likely to repost content matching their camp once
it reaches them) than non-extreme followers — these are conflated in the current cascade-only data
(which only observes relay events, not the full follower list). The newly-added
`class_follower_composition_<step>.csv` log (see Implementation) was built specifically to resolve
this but has not yet been analyzed for this purpose.

## n=15 confirmation

Extended A_never/B_always with 10 more seeds (7300005-7300014, `scripts/
delayed_moderate_conduit_pilot_extend.py`), reusing the original 5 for a combined n=15. Paired
(same-seed) t-tests, final checkpoint (step 40000):

| metric | A_never | B_always | diff | t (n=15) |
|---|---|---|---|---|
| opinionAssortativity | 0.7367±0.0956 | 0.6436±0.1050 | -0.0930 | **-4.29** |
| crossCuttingFraction | 0.0478±0.0248 | 0.0998±0.0612 | +0.0520 | **3.07** |
| extreme per-capita post rate | 0.0859±0.0160 | 0.1102±0.0243 | +0.0242 (+28.2%) | **3.81** |

All three now robust at t=3-5 (up from t≈2 at n=5). Extreme-rate effect is not just present but
**growing over time** (+21.5% at step 10000 → +28.2% at step 40000, t=2.43→3.81) — a durable,
compounding effect, not transient noise. `cRateMean` (comfort rate) shows a clear, significant
B>A gap at the final checkpoint (+0.092, t=2.73) though not perfectly monotonic across the whole
trajectory (sign flips at steps 5000/35000) — directionally consistent with the proximate mechanism
but not a clean, fully-resolved signal yet.

## Light robustness sweep (n=5, OAT)

Motivation: confirm the finding isn't specific to the single v15-calibration HK point. Swept
`p_u` (this project's own stated "phase knob," `research-direction.md`) and
`vocal_comfort_radius` (the exact threshold gating the established proximate mechanism), plus one
different network-generator family (`network=dcsbm`) at **matched t0 mean degree** — HK's own t0
mean in-degree measured at exactly 15.0 across all 5 baseline seeds (confirmed: `hk_m=15` gives
mean degree exactly `m`), so `sbm_deg=15` (not DC-SBM's default 50) was used so the comparison is
about topology *shape*, not shape+density. `ws`/`random` (non-scale-free) were deliberately
excluded from this round — `research-direction.md` already hypothesizes hub-mediated bridging
requires heavy-tailed degree, so a null result there would confirm an already-stated prior rather
than test this specific finding's robustness.

Smoke-tested DC-SBM class selection first (`sbm_k=4 sbm_pin=0.08 sbm_pout=0.002 sbm_gamma=2.3
sbm_deg=15`): realized avg in-degree 13.39 (close to target), 272 moderate agents found, top-20
selection non-degenerate (range 27-128 followers) — viable.

Results (`scripts/delayed_moderate_pilot_robustness.py`, seeds 7300000-7300004, n=5, final
checkpoint):

| config | assort diff (B-A) | ccf diff (B-A) | extreme-rate diff (B-A) |
|---|---|---|---|
| baseline (hk, p_u=0.05, vcr=0.1) | -0.0666 (t=-2.06) | +0.0233 (t=1.20) | +16.9% (t=1.28) |
| p_u=0.01 | -0.0712 (t=-2.69) | +0.0444 (t=1.88) | **+1.9% (t=0.15)** |
| p_u=0.15 | -0.0695 (t=-1.18) | +0.0280 (t=1.47) | +23.2% (t=1.34) |
| vcr=0.05 | -0.1119 (t=-1.83) | +0.0520 (t=1.50) | +32.2% (t=1.06) |
| vcr=0.2 | -0.0453 (t=-1.47) | +0.0210 (t=1.80) | +8.5% (t=1.41) |
| dcsbm (deg-matched) | -0.0392 (t=-2.51) | +0.0023 (t=0.88) | **+23.8% (t=3.85)** |

**Direction is consistent across all 18 metric×config cells (3 metrics × 6 configs, including
baseline) — zero sign flips.** At n=5 this is a "does the sign survive" check, not a precision
check (individual t-stats are naturally weaker than the n=15 baseline), but the qualitative
consistency across a structurally different network generator and a 15x range of `p_u` is a
meaningful robustness signal.

**One genuine exception worth flagging, not explaining away**: at `p_u=0.01` (near-zero
tie-dissolution), the structural effects (assortativity, crossCuttingFraction) hold as strongly as
elsewhere, but the **extreme-rate amplification effect nearly vanishes** (+1.9%, t=0.15 — clean
null). Candidate reading: structural bridging and extreme-vocality amplification may be two
distinct mechanisms with different sensitivity to `p_u` — bridging is close to `p_u`-independent
across the tested range, while the vocality-amplification channel may depend on some baseline level
of unfollow-driven exposure churn to operate. Not yet explained mechanistically; flagged as the
most important open item before finalizing the paper's claim scope (see below).

`dcsbm`'s crossCuttingFraction effect is the weakest of the batch (t=0.88) but likely a floor
effect, not evidence against the mechanism — DC-SBM's own baseline crossCuttingFraction (0.013-0.015)
is far lower than HK's (0.03-0.09) due to explicit community structure with low `sbm_pout=0.002`,
leaving less room for the metric to move. Its assortativity and extreme-rate effects are as strong
or stronger than HK's.

## Paper framing discussion (2026-08-02, not yet finalized)

**Venue split, agreed**: Complex Networks 2026 (CNA) for the current alpha=0, mechanism-focused
finding; a separate, later journal extension for whether the For-You algorithmic feed
substitutes/complements the conduit's bridging role as `alpha` rises (directly extends the
already-flagged "conduit redundancy at high alpha" risk in `research-direction.md`). CNA deadline
noted as first week of September 2026 — meaningfully after `research-direction.md`'s internal
"end-July" draft-target milestone, which has already passed; the actual CNA deadline gives more
room than that internal milestone implied. Journal-side work explicitly deferred, not started.

**Claim framing, discussed and refined** (not yet finalized in exact wording): the initial framing
("a moderate network bridge counter-intuitively activates extreme activity") was flagged as a real
risk of reading as a restatement of Granovetter (1973) weak-ties / Burt (1992) structural-holes
theory — both already predict that a bridging node increases cross-camp information flow and
reduces structural separation, so that alone isn't novel for a network-science audience. Discussed
what IS novel relative to classical bridging theory:
1. Bridging does NOT produce the naively-expected moderating effect (contact-hypothesis intuition)
   — it can amplify vocal extremism instead, closer to the Bail et al. 2018 backfire-effect line
   than to classical diffusion theory.
2. Individual bridges in this heavy-tailed/plateau topology are redundant (near-zero necessity,
   already established pre-2026-08-02) — classical theory implicitly assumes bridges are
   scarce/non-redundant; this model's regime breaks that assumption, and the paper should show BOTH
   the individual-removal-is-a-no-op result AND the class-level-continuous-engagement-matters
   result together, requiring two manipulation methods in the experimental design
   (individual-hub-removal, already done pre-2026-08-02; class-wide silence/delayed-activation, this
   session's new mechanism).
3. The verbatim-opinion-tag-preservation-through-relay mechanism is platform-mechanics-specific,
   outside classical (pre-social-media) bridging theory's scope.
4. The timing/audience-erosion dynamic (this session's finding) is absent from classical bridging
   theory, which treats bridge presence as static.

**Precision correction on "activates extreme activity"**: confirmed the finding is about posting
*vocality* (rate), not extremity magnitude or population radicalization — final extreme-camp
population size is unchanged between arms (see above). This ties directly to the project's own
naming (`polarized-vocal-minority-model`) — framed as amplifying the *vocal minority* phenomenon,
not radicalizing the population, which is both more precise and arguably a stronger/more specific
contribution than a generic "polarization increases" claim.

**Scope correction from the robustness sweep**: given the `p_u=0.01` null, the claim should likely
be scoped as phase-dependent (structural bridging robust across tested `p_u`; vocality-amplification
specific to non-negligible tie-dissolution regimes) rather than universal — ties directly into
`research-direction.md`'s existing `P_u`-as-phase-knob framing rather than fighting it.

**Next-step decisions made**: n=30 per arm for the main battery (down from an initially-discussed
n=50, judged sufficient given n=15 already yields t=3-5 on the headline metrics, and cheap
compute — this project's own history notes n=20 barely improves over n=10 for noisier metrics
like SF1, and the metrics here are comparatively well-behaved). DC-SBM robustness point kept in
main text (most persuasive single generality signal); `p_u`/`vcr` OAT sweep and the individual-hub
redundancy contrast are candidates for main text if the 12-page CNA limit allows, appendix
otherwise. Mechanism resolution prioritized as necessary (not optional) for the paper, specifically
because it directly determines how precisely the phase-dependent claim (item above) can be scoped —
two concrete open items before the claim can be finalized: (a) audience-composition vs.
relay-propensity decomposition (needs the new follower-composition log, not yet analyzed), (b)
understanding the `p_u=0.01` mechanism boundary.

## Process note: CLAUDE.md updated

Added an "Output Style" rule (this session, user-flagged): define any new/ad-hoc analysis term
(e.g. "downstream extreme relay events") in plain language on first use, every time — don't assume
a term coined mid-analysis is self-explanatory from context. Also saved as a standing feedback
memory (`feedback-define-adhoc-terms`).

## Open items (not yet resolved, going into next session)

1. Audience-composition vs. relay-propensity decomposition for the 1.64x extreme-downstream
   over-representation — analyze the new `class_follower_composition_<step>.csv` log (already
   collected for the n=15 batch and the robustness sweep, not yet read).
2. Mechanistic understanding of the `p_u=0.01` boundary (why vocality-amplification specifically
   vanishes while structural bridging persists).
3. n=30 main-battery run not yet launched.
4. Individual-hub-removal + class-wide-silence dual-manipulation experimental design (for the
   Granovetter-redundancy contrast) not yet drafted as a concrete plan.
5. Exact claim wording, page-budget allocation (main text vs. appendix), and full experimental
   design writeup not yet finalized — this report captures the discussion inputs, not a locked
   decision document.

## Calibration-transparency decision (2026-08-02, methodology)

User raised whether the model's current calibration state is too ambiguous to support the paper,
specifically on reproducibility and persuasiveness grounds. Re-grounded the concern directly in
`ExperimentConfig.java`'s inline calibration history: v15 (current default, used throughout this
session's experiments) explicitly misses its own SF1 target (1.148±0.130 vs. [1.19,1.26], short by
0.077), misses Q_sign_repost (0.417 vs. 0.48 target), and shows an essentially-unimproved bin7 fit
(W1=0.434) despite that being v15's specific search objective; several parameters (bcDecRate,
bcRecoveryRate, vocalComfortRadius, p_u) remain pinned at the edge of their search box across >350
evaluated points, meaning the search may not have reached an interior optimum. Also found, while
re-reading, an internal inconsistency between two inline comments and their fields' actual current
default values (`pU`'s comment says "boundary-pinned at v13's search-box upper edge (0.1)" but the
field default is `0.05`; `bcDecRate`'s comment says "pinned at the hard ceiling (zero inertia)" —
which only holds at exactly 1.0 — but the field default is `0.5`) — a small but real reproducibility
issue (reconstructing "what v15 actually is" from the file's comments alone would give the wrong
answer for these two fields; the CLI-token defaults are authoritative, not the prose).

**Decision**: do not attempt to fully close the SF1/Q_sign_repost/bin7 gap before the CN2026
deadline — the >350-point search history suggests these targets are in tension under the current
parameterization, so further search time has uncertain payoff. Instead:
- Report the calibration search honestly in the paper (target-vs-achieved table, see draft
  paragraph below), rather than presenting the model as a validated replica of real-world
  polarization statistics.
- Frame the central claim as the *directional/mechanism* effect of the delayed-conduit-entry
  intervention relative to a matched control, not as "a realistic model implies this happens in
  the real world" — this claim type is not dependent on hitting SF1/Q/bin7 exactly.
- Lean on the already-completed OAT robustness sweep (p_u, vocal_comfort_radius, DC-SBM topology)
  as the primary defense against an "arbitrary single calibration point" critique, since it already
  shows the directional finding survives perturbation.
- Fix the two comment/field-value inconsistencies found above as a cheap, separate reproducibility
  correction (not a calibration change).

**Draft paper text** (Methods — calibration reporting, to be refined at drafting time):

> We calibrated model parameters against four target statistics: the apparent-polarization ratio
> SF1 (target [1.19, 1.26]), the bc–extremity correlation (target ≤ −0.3), repost-network modularity
> Q_sign_repost (target 0.48), and the Wasserstein-1 distance between simulated and empirical
> posting-rate-by-ideology-bin distributions (Buntain & Snegovaya, 2025). A parameter search (>350
> evaluated points) converged on a point that satisfies the bc–extremity target but falls short on
> the remaining three: SF1 = 1.148 ± 0.130 (vs. [1.19, 1.26]), Q_sign_repost = 0.417 (vs. 0.48), and
> bin-distribution W1 = 0.434. Several parameters remain pinned at the edge of their search range,
> indicating the search did not reach an interior optimum under the current parameterization. Even
> with these discrepancies, we treat the model as fit for the present study's purpose rather than as
> a validated replica of real-world polarization levels: our central claim concerns the *directional
> effect* of a specific structural intervention relative to a matched control, not the model's
> absolute fit to empirical statistics, and this directional effect was consistent across a
> one-at-a-time robustness sweep (§[robustness]), suggesting it is not an artifact of this specific
> calibration point.

## 2026-08-03 — Class-selection OAT + mechanism resolution (audience composition vs. relay propensity)

### Class-selection-criterion OAT (n=5, seeds 7300000-7300004)

Per the reviewer punch-list from the previous session (novelty/robustness gaps beyond the
dynamics-parameter sweep), added a light OAT on the class-selection criterion itself: top-K by t0
follower count (10/20/40, baseline 20) and the eligibility threshold on |intrinsicOpinion| (0.1/0.2/0.3,
baseline 0.2) used to decide which agents even qualify as "moderate" candidates before ranking by
reach. Script: `scripts/delayed_moderate_pilot_robustness_classdef.py`. Class IDs were re-derived
from the already-existing t0 network snapshots (class membership depends only on t0 followerCount +
intrinsicOpinion, fixed before dynamics run) — no fresh dry runs needed except for the earlier
dcsbm arm.

Results (paired A_never vs B_always, final checkpoint):

| config | opinionAssortativity diff | crossCuttingFraction diff | extreme per-capita rate diff |
|---|---|---|---|
| baseline (top20, thresh0.2) | −0.067 (t=−2.06) | +0.023 (t=1.20) | +16.9% (t=1.28) |
| topk10 | −0.075 (t=−2.19) | +0.025 (t=1.44) | +16.5% (t=1.47) |
| topk40 | −0.068 (t=−2.36) | +0.027 (t=1.27) | +22.0% (t=1.83) |
| thresh0.1 | −0.001 (t=−0.03) | +0.005 (t=1.39) | +8.4% (t=2.16) |
| thresh0.3 | −0.084 (t=−2.26) | +0.034 (t=2.57) | +44.8% (t=2.13) |

**top-K is robust** (16.5-22.0% across 10/20/40, no meaningful sensitivity). **The eligibility
threshold is NOT flat**: at the strict end (0.1, only near-dead-center agents eligible), the
opinionAssortativity effect is essentially zero (t=−0.03); at the loose end (0.3, agents drifting
toward the pre-extreme boundary are eligible), every effect roughly doubles-to-triples vs. baseline.
Magnitude scales monotonically with threshold width. Direction is consistent across all 5 configs
(the central claim is not threatened), but the effect *size* depends on how tightly "moderate" is
defined — worth reporting as a scoping nuance in the paper, and plausibly connected to the p_u=0.01
boundary below (both seem to hinge on how close the intervened population sits to the extreme
fringe / how much cross-camp exposure actually occurs).

### Mechanism resolution: audience composition vs. relay propensity

Using the `class_follower_composition_<step>.csv` log (collected but unanalyzed since 2026-08-02),
decomposed the previously-reported 1.64x extreme-camp over-representation among downstream relayers
of class-relayed extreme-authored content into two candidate explanations: **audience composition**
(are the class's own direct followers disproportionately extreme-camp?) vs. **relay propensity**
(are extreme-camp agents simply more likely to re-relay content once it reaches them, regardless of
how they were exposed?).

Tracked direct-follower opinion-bin composition over time, n=10-15 seeds, p_u=0.05 baseline:

| step | A_never (class silent) | B_always (class active) |
|---|---|---|
| 0 | 23.74% extreme | 23.74% extreme |
| 5,000 | 23.00% | 5.64% |
| 15,000 | 22.86% | 1.44% |
| 25,000 | 22.87% | 0.69% |
| 35,000 | 22.84% | 0.42% |

**Result: audience-composition hypothesis directly refuted.** In A_never the class's audience stays
population-representative throughout (flat ~23%; follower count itself never changes at all across
the whole run for a silent class — worth separately confirming this isn't a bug, since it implies
silent accounts are structurally invisible to this model's follow-discovery process). In B_always,
extreme followers flee almost entirely within the first 5,000 steps and the purge continues
monotonically to 0.42% by step 35,000. This is the opposite direction from the "moderate embedded
in extreme cluster" hypothesis raised in the previous session's mechanism investigation — once
active, the class's own audience becomes almost exclusively moderate/pre-extreme, so the downstream
extreme-relayer over-representation cannot be explained by who directly follows the class. It must
be a **relay-propensity effect**: extreme-tagged content (opinion tag preserved verbatim through
relay per `Post.relayOf()`) is disproportionately picked up and re-relayed by extreme-camp agents
wherever it reaches them in the cascade tree, not because they are in the class's own audience.

### p_u=0.01 boundary — narrowed, not fully closed

Re-checked directly at p_u=0.01 (n=5): extreme per-capita posting-rate effect is null there (+1.9%,
t=0.15, vs. +16.9%/t=1.28 at p_u=0.05). Two candidate explanations ruled out with direct data:
- Not a throughput effect: overall repost-count increase (B_always vs A_never) persists at both
  p_u=0.01 (+19.9%) and p_u=0.05 (+26.9%) — the class still drives materially more circulation at
  low p_u, so it's not that activity simply stops mattering.
- Not an audience-composition effect: purification still happens at p_u=0.01 (22.65%→3.55% extreme
  by step 35,000), just less completely than at p_u=0.05 (→0.42%). If direct-audience composition
  drove the amplification, the *more* extreme-heavy residual audience at p_u=0.01 should predict a
  *stronger* effect, not a weaker/null one — the data goes the opposite way, reinforcing that
  audience composition isn't the lever here either.

**Remaining hypothesis (not yet tested)**: p_u gates network rewiring reaching new parts of the
extreme cluster. At p_u=0.05 enough follow/unfollow churn occurs that the class's relayed content
reaches extreme agents who would not otherwise be exposed to equivalent content via their existing
ties (a genuine marginal contribution); at p_u=0.01 the network is close to frozen, so the
extreme agents who would relay this content are already saturated with similar content from
pre-existing ties, making the class's marginal contribution ~0. Would need hop-distance-to-class
tracking for the eventual extreme relayer, checked against p_u, to confirm — treated as
optional/appendix-level rather than blocking for the current draft.

### Status: both open items from the previous session's punch-list are now resolved or narrowed
enough to write up. Remaining before/alongside drafting: n=30 main battery, individual-hub-removal
dual-manipulation design (Granovetter-redundancy contrast), related-work survey, full Methods
writeup, and the page-budget decision — all previously flagged, still open.

## 2026-08-03 — CRITICAL CORRECTION: extreme-camp per-capita posting-rate metric bug

While tracing the mechanism behind the extreme-camp posting-rate increase (feed composition,
comfort-rate timing, bc, repost-event counts), found that every "extreme_percapita_rate" figure
reported in this pilot since 2026-08-02 (initial pilot's +16.9%, the n=15 confirmation, the
dynamics-parameter OAT sweep, the class-selection-criterion OAT sweep) was computed with a bug:

```python
total = originalPostCount + repostCount          # WRONG
total_posts += postShare_b * total
```

`Analysis.computePostShareArray` (`Analysis.java:588`) documents `postShare_b` as the share of
**ORIGINAL posts only** (`postCash` — same population as `postOpinionVar`, explicitly **excludes
reposts and manipulated-hub posts**). Multiplying it by `originalPostCount + repostCount` silently
folded the entire repost-volume increase (a real, large, already-separately-reported effect) into
what was being presented as a same-individuals'-behavior posting-rate effect. This was caught by
directly reconciling three independent measurements that should agree and didn't (combined
postShare-based rate vs. `posts/post_result.csv`-direct original-post counts vs. direct
`repost_cascades.csv` relayer counts in a matched time window) — the discrepancy was off by roughly
an order of magnitude, which is what exposed the bug rather than being explainable as noise.

**Corrected metric**: `postShare_b * originalPostCount / pop_b` (equivalently, direct per-bin sums
of `posts/post_result.csv`'s `bin_b` column — cross-validated to match). Also checked and ruled out
as an alternative explanation: population membership churn in bin0/bin4 (agent-level overlap between
A_never/B_always is 90-100% per seed — not a compositional artifact) and a hard-coded sign-conditional
bias mechanism (searched exhaustively across `Agent.java`/`ExperimentConfig.java`/`OpinionDynamics.java`
/`Analysis.java`/`Const.java` for opinion-sign conditionals, boost/inflate/skew/tilt/favor keywords,
and `initial_pp` handling — none found; the only related item is a **never-implemented** design
proposal, `conservativeBcNarrowing`, logged in [[project-asymmetric-homophily-mechanism]], explicitly
marked "write-up only, no code changes yet" — irrelevant here). Also confirmed these runs use the
default `initOpinionDist=gaussian` (symmetric), not `init_dist=empirical` — the left/right asymmetry
below is not an artifact of an asymmetric initial-opinion draw either.

**Re-verified at n=30** (seeds 7300000-7300029, 15 new seeds 7300015-7300029 added specifically for
this re-check, `scripts/delayed_moderate_pilot_extend_n30_verify.py`), corrected metric, final window:

| bin | corrected diff | t | n |
|---|---|---|---|
| bin0 extreme(-) | +5.1% | t=2.73 | 30 |
| bin1 pre-extreme(-) | -22.6% | t=-4.19 | 30 |
| bin2 moderate | +69.2% | t=8.24 | 30 |
| bin3 pre-extreme(+) | -21.1% | t=-4.21 | 30 |
| bin4 extreme(+) | +0.8% | t=0.33 (null) | 30 |

**Implications for the paper's central claim**: the previously-reported "moderate conduit raises
extreme-camp posting activity by ~17-37%" headline is **not correct as stated**. The corrected,
n=30-confirmed effect is much smaller (bin0 +5.1%, real but modest) and **asymmetric — bin4 (right/
positive-opinion extreme) shows no effect at all** (t=0.33). Both estimates moved toward a smaller
magnitude as n increased from 15 to 30 (bin0: +8.4%→+5.1%; bin4: +1.3%→+0.8%), consistent with the
n=15 estimates having been somewhat noise-inflated, not with the effect strengthening. By contrast,
the moderate-camp (bin2) self-reinforcement effect (+69-108% depending on n/window) is large,
robust, and NOT what the paper had been centering — but per 2026-08-03 discussion this effect is
also the more mechanically expected/less novel one (moderate hub posts moderate content -> moderate
agents get more like-minded content -> they post more).

**Not yet done**: recompute the corrected metric for the earlier dynamics-parameter OAT sweep
(p_u/vcr/dcsbm) and the class-selection-criterion OAT sweep (top-K/threshold) — both currently still
report figures computed with the buggy formula. Also unresolved: what (if anything) drives even the
small, real, asymmetric bin0 effect — the mechanism-investigation chain (feed composition, comfort
rate, bc, repost-event timing) that was built around explaining the larger buggy effect size has not
been re-run against this smaller corrected target.

**Decision pending**: whether to re-center the paper's central claim on the moderate self-reinforcement
effect (larger, robust, but more mechanically obvious) or keep the small asymmetric extreme-camp
effect as a claim (smaller, novel, but now needs its own mechanism and doesn't generalize to bin4) —
not yet decided as of this entry.

## 2026-08-03 — Root-cause investigation of the bin0/bin4 asymmetry; extreme-camp claim withdrawn

User pushed back hard on the bin0-significant/bin4-null asymmetry ("非対称性が出る意味がわからない…
分析コードの方が変とかない？"), requesting an exhaustive investigation into whether it was an analysis
bug or a real, hard-coded model asymmetry. Ruled out, in order, with direct evidence each time:

1. **`init_dist=empirical`**: not used by any script in this pilot (confirmed via grep — no script
   passes `init_dist`; default is `initOpinionDist=gaussian`, symmetric).
2. **A hard-coded sign-conditional bias mechanism**: exhaustively grepped `Agent.java`,
   `ExperimentConfig.java`, `OpinionDynamics.java`, `Analysis.java`, `Const.java` for opinion-sign
   conditionals and boost/inflate/skew/tilt/favor keywords — none found. The only related item,
   [[project-asymmetric-homophily-mechanism]]'s proposed `conservativeBcNarrowing` fix, is
   documented as "write-up only, no code changes yet" — not implemented anywhere in this codebase.
3. **Skewed initial-opinion generation**: directly measured the t0 `intrinsicOpinion` distribution
   pooled across all 30 seeds (30,000 agents) — mean +0.0033 (t=1.34, ns), skewness -0.0062,
   bin0/bin4 population 119.9 vs 123.5 (t=1.32, ns), boundary counts (x<=-1 vs x>=1) exactly 4 vs 4.
   Confirmed symmetric.
4. **agentId-opinion correlation** (network growth gives low IDs systematically higher in-degree via
   preferential attachment — a real, confirmed structural fact): correlation(agentId, opinion)
   pooled per-seed = -0.0087 (t=-1.63, ns); mean agentId bin0 vs bin4 = 504.3 vs 499.1 (t=-0.82, ns);
   t0 followerCount bin0 vs bin4 = 14.64 vs 14.80 (t=0.13, ns). No ID/degree link to opinion sign.
5. **Timing trace** (A_never only, isolating the model's own dynamics from any treatment question):
   `feedPostOpinionMean` (mean opinion of content in an agent's feed) diverges between bin0/bin4
   within ~200 steps (t=6.07) and grows to t=43 by step 40000 — a leading indicator by tens of
   thousands of steps ahead of `cRateMean`/`highComfortRateNum`/posting-rate (all only becoming
   significant around step 20000-40000). `feedPostOpinionVar` does NOT diverge — it's specifically
   directional content-mean, not volume/variance.
6. **Mechanism candidate identified** (not confirmed): `OpinionDynamics.java` lines 257-360 process
   agents each step in an order re-shuffled fresh every step (`Collections.shuffle(shuffledAgents,
   randomGenerator.dynamics())`), and broadcast each post/repost to followers'
   `postCash` **immediately** within the same step's loop (lines 314-316, 348-350) rather than
   batching broadcasts to the end of the step. This means whether a follower sees a post in the SAME
   step or has to wait until next step depends on the poster's random position in that step's
   shuffle relative to the follower's — a same-step cascade effect that is order-dependent by
   construction. Plausible root cause of a stochastic (not sign-determined) leading asymmetry, but
   not proven — would need new per-step instrumentation to confirm directly.

**Decisive replication check**: re-ran the full A_never/B_always comparison on a completely
unrelated seed block (8811000-8811014, n=15, vs. the original 7300000-7300029) —
`scripts/delayed_moderate_pilot_diffseed_check.py`:

| bin | 7300000s block (n=30) | 8811000s block (n=15) |
|---|---|---|
| bin0 extreme(-) | +5.1% (t=2.73) | +0.0% (t=0.01) |
| bin1 pre-extreme(-) | -22.6% (t=-4.19) | -14.3% (t=-2.73) |
| bin2 moderate | +69.2% (t=8.24) | +85.4% (t=8.09) |
| bin3 pre-extreme(+) | -21.1% (t=-4.21) | -16.4% (t=-2.17) |
| bin4 extreme(+) | +0.8% (t=0.33) | +5.8% (t=1.42) |

**The asymmetry flips which bin shows an effect between seed blocks** (bin0 in the first block,
bin4 in the second) — this is the decisive evidence that "which extreme camp responds" is noise, not
a fixed structural left/right property of the model. bin1/bin2/bin3 are consistent in direction and
magnitude across both independent seed blocks; bin0/bin4 are not.

**Claim revision**: the "moderate conduit raises extreme-camp posting activity" claim is withdrawn —
not supported at a level distinguishable from noise. What survives as robust across two independent
seed blocks: moderate-camp (bin2) self-reinforcement (+69-108%) and pre-extreme (bin1/bin3)
suppression (-14% to -23%). The paper's central claim should be reframed around this
moderate/pre-extreme redistribution effect, not an extreme-camp activation effect.

**Not yet done**: implementing the batched-broadcast fix (deferring `addToPostCash` calls to end of
step) to remove the same-step order-dependent cascade mechanism identified in item 6 above — flagged
by the user as plausibly worth doing, but would likely shift calibrated structural facts (SF1,
Q_sign_repost, etc., all calibrated under the current same-step-cascade-permitting behavior) and
require re-calibration; not started, scope/priority undecided given the CN2026 timeline.

## 2026-08-03 — Batched-postCash-delivery fix implemented, tested, and calibration-checked

Implemented the fix discussed above: `OpinionDynamics.java` now buffers each step's post/repost
broadcasts into a `PendingDelivery` list (follower ID captured at broadcast time, same as before)
and flushes them into followers' `postCash` only after the full `shuffledAgents` loop completes,
instead of immediately mid-loop. This removes the same-step, shuffle-order-dependent cascade
mechanism identified as the leading candidate for the bin0/bin4 asymmetry (previous entry, item 6).
Compiled clean; 2000-step smoke test (n=1000) ran with 0 assertion errors.

**Asymmetry check after the fix** (`scripts/delayed_moderate_pilot_batched_postcash_check*.py`,
A_never only, fresh unused seed block 5500000-5500029, n=30, matching methodology to the pre-fix
diffseed check):

| | diff(bin4-bin0), original-post per-capita rate | t |
|---|---|---|
| pre-fix, 7300000s block, n=30 | +0.0079 | 2.34 (significant) |
| pre-fix, 8811000s block, n=15 | +0.0051 | 1.17 |
| post-fix, 5500000s block, n=10 | +0.0026 | 0.44 |
| post-fix, 5500000s block, n=30 | +0.0033 | 1.15 |

At matched n=30, effect size roughly halved (0.0079 -> 0.0033) and t dropped below the conventional
significance threshold (2.34 -> 1.15). Characterization: substantially reduced, now within the same
noise-level range already seen pre-fix in one of the two pre-fix blocks (8811000s, t=1.17) -- not
provably reduced to exactly zero, but no longer a reliably-significant effect either.

**Calibration-impact check**: re-ran `scripts/confirm_current_config_20seed.py` (no CLI overrides,
pure `ExperimentConfig.java` defaults, n=20, seeds 1900000-1900019, checkpoints 20000/40000) with
and without the fix. Critically, did this as a SAME-DAY clean comparison (git-stashed the fix,
rebuilt, ran "today, no-fix" fresh -- rather than reusing the existing 2026-07-27 baseline CSV,
which would have confounded the fix with ~1 week of unrelated default-parameter drift):

| metric (checkpoint=40000) | today, no-fix | today, with fix | diff |
|---|---|---|---|
| gini | 0.9006 +/- 0.0038 | 0.8978 +/- 0.0056 | -0.0028 |
| assort | 0.4821 +/- 0.0873 | 0.5008 +/- 0.0900 | +0.0187 |
| Q_sign_repost | 0.4075 +/- 0.0452 | 0.4082 +/- 0.0557 | +0.0007 |
| SF1 (ratio) | 1.3742 +/- 0.2099 | 1.4428 +/- 0.3128 | +0.0686 |

All four differences are within SEM of each other -- **the fix does not meaningfully disturb
calibrated structural facts**. Safe to adopt.

**Separate, unrelated finding surfaced by this check**: both today's runs (fix and no-fix) show
`assort` ~0.48-0.50, well below the 0.6 floor target -- but the OLD 2026-07-27 baseline (preserved
in `docs/report/current_config_20seed_confirm_PREFIX_backup.csv`) had assort=0.674, comfortably
clearing the floor. Since this drift is IDENTICAL in both of today's runs (with and without the
postCash fix), it is not caused by this fix -- something else changed `ExperimentConfig.java`
defaults between 2026-07-27 and today (candidate: the feed-reach redesign commit, `5ffc790`) in a
way that dropped assortativity below its calibrated floor. Flagged for separate investigation, not
addressed here. Raw comparison data preserved in `docs/report/current_config_20seed_confirm_TODAY_NOFIX.csv`
and `docs/report/current_config_20seed_confirm_TODAY_FIX.csv`.

**Status**: fix is implemented, compiled, smoke-tested, shown to substantially reduce (though not
provably zero out) the bin0/bin4 asymmetry, and confirmed not to disturb calibration. Committed
(`684d6fc`, "fix: batch postCash delivery to end-of-step; root-cause and re-verify extreme-camp
asymmetry"). Not yet re-run against the full delayed-moderate-conduit pilot battery (n=15/n=30
A_never/B_always, OAT sweeps) -- those all predate this fix and would need re-running under it if
adopted as the new baseline.

## 2026-08-03 — Full 5-parameter OAT battery under the fix: extreme-camp claim decisively dropped

Re-ran the complete 5-parameter OAT battery (p_u, vocal_comfort_radius, class top-K, class
threshold, network topology -- same 5 dimensions as the two earlier OAT rounds, user's own
recollection of "about 5 parameters") under the batched-postCash fix and the corrected per-capita
metric, motivated by the concern that the extreme-camp effect might be real but suppressed at the
default parameter point specifically. `scripts/delayed_moderate_pilot_postfix_oat_battery.py`: n=15,
fresh seed block (6600000-6600014), 10 configs (baseline + 2 non-baseline levels each for
p_u/vcr/topK/threshold + 1 for dcsbm topology) x 2 arms x 15 seeds = 300 full runs.

**bin0/bin4 (extreme camps), all 10 configs**:

| config | bin0 diff% (t) | bin4 diff% (t) |
|---|---|---|
| baseline | -3.2% (-0.63) | +3.1% (0.47) |
| pu_001 | -5.8% (-1.47) | -8.5% (-1.51) |
| pu_015 | +4.2% (0.67) | +6.1% (1.21) |
| vcr_005 | -10.8% (-1.70) | -2.0% (-0.26) |
| vcr_02 | +0.5% (0.39) | +2.3% (1.42) |
| topk10 | -4.3% (-0.76) | -3.8% (-0.67) |
| topk40 | -3.8% (-0.70) | -1.1% (-0.29) |
| thresh01 | +3.6% (1.59) | +1.9% (1.12) |
| thresh03 | -5.4% (-0.77) | -3.0% (-0.54) |
| dcsbm | -3.3% (-1.26) | -7.8% (-1.42) |

**No config among the 10 reaches conventional significance for either extreme bin** (max |t| = 1.70
for bin0, 1.51 for bin4), and the sign flips inconsistently across configs. This rules out the
"suppressed at default parameters specifically" hypothesis directly: across this entire 5-parameter
neighborhood, the extreme-camp effect never resolves out of noise.

**bin1/bin2/bin3, same 10 configs** -- for contrast, robust essentially everywhere:

| config | bin1 t | bin2 t | bin3 t |
|---|---|---|---|
| baseline | -2.82 | 6.13 | -2.49 |
| pu_001 | -2.62 | 8.73 | -2.85 |
| pu_015 | -5.44 | 5.81 | -4.58 |
| vcr_005 | -3.06 | 7.74 | -3.01 |
| vcr_02 | -2.08 | 1.89 | -2.60 |
| topk10 | -2.56 | 5.11 | -2.24 |
| topk40 | -2.78 | 10.36 | -2.68 |
| thresh01 | -0.88 | 0.49 | -0.35 |
| thresh03 | -4.91 | 4.49 | -3.95 |
| dcsbm | -2.58 | 5.07 | -3.57 |

bin2 (moderate) is strongly significant (t>4) in 8/10 configs, always positive sign; bin1/bin3
(pre-extreme) are significant in 8/10 configs, always negative sign. Only `thresh01` (strictest
moderate-eligibility threshold, class is closest to pure dead-center) and `vcr_02` (widest comfort
radius) weaken the moderate/pre-extreme effect noticeably -- but never flip its sign.

**Decision**: the "moderate conduit raises extreme-camp posting activity" claim is dropped, not just
softened -- checked across the full parameter neighborhood a reviewer would ask about, not just the
default point, and it does not appear anywhere in it. The paper's central claim is the
moderate-self-reinforcement / pre-extreme-suppression redistribution effect, which is now confirmed
robust across: 2 independent seed blocks, 2 network topology families (HK/DC-SBM), and this full
5-parameter OAT grid.

**Housekeeping**: `results/` grew to 69GB over the course of this session's re-verification work
(diffseed check, batched-postcash checks, calibration comparison, this 300-run battery). Conclusions
from all of it are now written up here; raw run directories are disposable and should be cleaned up
(`rm -rf`) once this entry is confirmed sufficient, per project convention.

## 2026-08-03 — bc_init/bc_dec and bc_floor/bc_recovery screens toward WSSIT-era-like calibration

Follow-up on the earlier WSSIT-vs-current diff investigation (bc-extremity correlation -0.83 vs
WSSIT-era's -0.47; repost-network opinion assortativity 0.74 vs WSSIT-era's 0.39) -- both overshoot
this project's own calibration targets (bc_extremity_corr <= -0.3, Q_sign_repost = 0.48), not just
WSSIT-era's values. Explored minimal-change parameter levers to pull the model back toward its own
targets. General-model-calibration screens (no moderate-hub intervention, `extreme=none n_mod=0`),
n=5 per grid point, checkpoint=40000.

### Screen 1: bc_init x bc_dec (`scripts/bc_init_dec_objective_screen.py`)

Hypothesis going in: WSSIT-era's much slower bc-narrowing (flat 0.99-multiplicative decay from
bc_init=1.0) should be mimicked by slowing the current graded-relaxation mechanism's `bc_dec` (gap-
closing rate per step) and/or raising `bc_init` toward 1.0. **Wrong** -- empirically, decreasing
`bc_dec` moved `bc_extremity_corr` *further* from the -0.3 target (more negative: baseline
bc_init=0.8/bc_dec=0.5 gives -0.43; bc_dec=0.05 gives -0.76) and `Q_sign_repost` further from 0.48
(0.46 at baseline down to 0.27-0.31 at slow bc_dec). Full 3x5 grid (bc_init in {0.8,0.9,1.0}, bc_dec
in {0.5,0.2,0.1,0.05,0.01}):

| bc_init | bc_dec | gini | assort | Q_repost | SF1 | bc_corr |
|---|---|---|---|---|---|---|
| 0.8 | 0.5 (baseline) | 0.8954 | 0.7044 | 0.4617 | 0.9901 | -0.4322 |
| 0.8 | 0.2 | 0.8931 | 0.6103 | 0.4124 | 1.0561 | -0.6289 |
| 0.8 | 0.1 | 0.8928 | 0.5289 | 0.3996 | 1.1764 | -0.7280 |
| 0.8 | 0.05 | 0.8898 | 0.4593 | 0.3084 | 1.1570 | -0.7591 |
| 0.8 | 0.01 | 0.8884 | 0.4453 | 0.2677 | 1.0304 | -0.6589 |
| 0.9 | 0.5 | 0.8955 | 0.6593 | 0.4461 | 0.9829 | -0.4905 |
| 0.9 | 0.2 | 0.8934 | 0.5517 | 0.3725 | 1.0866 | -0.6032 |
| 0.9 | 0.1 | 0.8925 | 0.5155 | 0.3559 | 0.9815 | -0.6588 |
| 0.9 | 0.05 | 0.8892 | 0.3684 | 0.2376 | 0.9930 | -0.7467 |
| 0.9 | 0.01 | 0.8870 | 0.3353 | 0.1833 | 1.1954 | -0.6607 |
| 1.0 | 0.5 | 0.8932 | 0.6011 | 0.4209 | 1.1185 | -0.5183 |
| 1.0 | 0.2 | 0.8912 | 0.4856 | 0.3267 | 1.1940 | -0.6786 |
| 1.0 | 0.1 | 0.8882 | 0.3822 | 0.2014 | 1.1715 | -0.7486 |
| 1.0 | 0.05 | 0.8877 | 0.3071 | 0.1554 | 1.0420 | -0.7201 |
| 1.0 | 0.01 | 0.8867 | 0.2136 | 0.0623 | 0.9291 | -0.6367 |

Root cause of the wrong-direction hypothesis: `bc_dec` in the current graded-relaxation mechanism
is a per-step gap-closing rate inside a feedback loop, not a per-event decay constant like
WSSIT-era's -- slowing it doesn't preserve broad tolerance the way WSSIT-era's genuinely-slow decay
did, it instead produces a smoother/less-noisy (hence more strongly-measured) convergence toward
whatever the comfort-driven target already is. Side finding: SF1 gets unusually close to its
[1.19,1.26] target at several grid points (bc_init=0.9/bc_dec=0.01: 1.195; bc_init=1.0/bc_dec=0.2:
1.194) -- notable given ~350+ prior search points across this project's history never closed this
gap, but n=5 here, not confirmed.

### Screen 2: bc_floor x bc_recovery (`scripts/bc_floor_recovery_objective_screen.py`)

Reconsidered levers after Screen 1's negative result: `bc_floor` (hard minimum bc, direct mechanical
cap rather than dynamics-mediated) and `bc_recovery` (content-independent mean-reversion rate,
currently tiny at 0.0001 -- raising it lets bc genuinely rebound toward bc_init, unlike bc_dec).
`out_of_bc_repost_prob` was considered and dropped per user (already known low-probability lever).
bc_init/bc_dec held at defaults (0.8/0.5). Full 3x3 grid (bc_floor in {0.2,0.35,0.5}, bc_recovery in
{0.0001,0.001,0.01}):

| bc_floor | bc_recovery | gini | assort | Q_repost | SF1 | bc_corr |
|---|---|---|---|---|---|---|
| 0.2 (baseline) | 0.0001 (baseline) | 0.8964 | 0.7177 | 0.4718 | 0.9815 | -0.4685 |
| 0.2 | 0.001 | 0.8926 | 0.6125 | 0.3924 | 1.1464 | **-0.3711** |
| 0.2 | 0.01 | 0.8887 | 0.4969 | 0.3616 | **1.2281** | -0.3931 |
| 0.35 | 0.0001 | 0.8908 | 0.6941 | 0.4163 | 1.0429 | -0.5360 |
| 0.35 | 0.001 | 0.8879 | 0.5886 | 0.3842 | 1.1021 | -0.4778 |
| 0.35 | 0.01 | 0.8867 | 0.4512 | 0.3007 | 1.1156 | -0.3923 |
| 0.5 | 0.0001 | 0.8872 | 0.5350 | 0.2758 | 0.9244 | -0.7294 |
| 0.5 | 0.001 | 0.8856 | 0.4297 | 0.2211 | 0.9012 | -0.6911 |
| 0.5 | 0.01 | 0.8828 | 0.3225 | 0.1529 | 0.6036 | -0.5359 |

**`bc_recovery` (raising it, floor held at 0.2) works as hypothesized**: bc_corr moves from -0.469
toward -0.371 at bc_recovery=0.001 -- the closest any point in either screen gets to the -0.3
target -- while assort (0.613) still clears its 0.6 floor. **`bc_floor` does NOT work as
hypothesized**: raising it alone (recovery held at baseline) makes bc_corr *worse* (-0.469 to
-0.536 to -0.729 as floor rises 0.2->0.35->0.5), alongside worsening assort and Q_repost -- the
"cap how narrow bc can get" mechanical-ceiling intuition doesn't hold up empirically, mechanism not
yet understood. Genuine trade-off found: raising bc_recovery improves bc_corr but worsens Q_repost
(0.472 -> 0.392 -> 0.362 as recovery rises) -- no point in either 15-point or 9-point grid clears
all 5 targets simultaneously. Same SF1-approaches-target side finding recurs (bc_recovery=0.01 hits
SF1=1.228, inside target range).

**Status**: exploratory only (n=5 both screens). `bc_recovery=0.001` (bc_floor=0.2, bc_init=0.8,
bc_dec=0.5 otherwise default) identified as the most promising single-lever candidate for the
original goal (bc_corr toward -0.3) without breaking the assort floor. Seeds 4400100-4400104 (5
runs at this exact config) kept in `results/2026-08-03_bc_floor_recovery_screen/bcfloor0.2_bcrec0.001/`
for dashboard inspection at user's request; not yet confirmed at n=20; not yet decided whether/how
to fold into this project's actual calibration defaults (this is a general-model-realism question,
separate from the delayed-moderate-conduit pilot's own findings above).

**Note (user, 2026-08-03): Q_sign_repost's own empirical target is itself edge-weight-filtered**
(low-repost-count edges excluded before computing modularity on the target side) -- comparable in
spirit to the already-documented [[conover-2011-modularity-activity-filter-bias]] poster-activity
filter, but a distinct filter (edge weight, not poster activity). Our simulated repost network's
`Q_sign_repost` is currently computed unfiltered (every repost edge counted regardless of weight),
so the current 0.42-0.47 vs. 0.48-target gap may be partly a measurement-methodology mismatch, not a
real dynamics gap: diluting a network with many single-repost noise edges (which the filtered target
never included) mechanically lowers modularity. Candidate fix: recompute `Q_sign_repost` restricted
to edges above some minimum repost-count threshold, matching the target's own filtering, before
concluding this metric needs further dynamics tuning. Not yet implemented or tested.

## 2026-08-04 — bc_recovery OAT (extreme-camp effect not found), natural-extreme-hub confound found,
## new L/M/P hub-tier experimental design (planning only, not implemented)

### bc_recovery OAT: no robust extreme-camp effect anywhere on this axis either

Following up on `bc_recovery=0.001` showing the first-ever significant bin4 result since the metric
bug fix (t=2.38, n=15, seeds 7700000-7700014) -- swept `bc_recovery` in
{0.0001, 0.0005, 0.001, 0.002, 0.005, 0.01} on the SAME seed block (paired comparison),
`scripts/delayed_moderate_pilot_bcrecovery_oat.py` (first attempt had a path bug -- A_never/B_always
outputs collided into the same directory since the results_subdir was missing `/{arm}`; fixed and
rerun cleanly):

| bc_recovery | bin0 t | bin4 t |
|---|---|---|
| 0.0001 | 0.67 | 0.64 |
| 0.0005 | -0.61 | 0.26 |
| 0.001 | 1.02 | **2.38** |
| 0.002 | 0.58 | -1.28 |
| 0.005 | -0.55 | -0.95 |
| 0.01 | 1.41 | 0.85 |

Only one of 12 (6 points x 2 bins) tests crosses conventional significance, with no neighboring-point
replication and no monotonic trend -- the signature of a multiple-comparisons false positive, not a
real effect at bc_recovery=0.001. bin1/bin2/bin3 (pre-extreme/moderate) and structural bridging
(opinionAssortativity/crossCuttingFraction) remained robust and significant at every point, matching
the whole day's pattern. **Conclusion: bc-parameter tuning does not surface a robust extreme-camp
effect anywhere searched.**

### Natural-extreme-hub confound identified

User noted: `extreme=none` (used throughout this entire pilot) means no ARTIFICIALLY PINNED extreme
hub, but does NOT mean no extreme hub at all -- the population's naturally-drawn opinions can still
put a genuinely extreme agent (|intrinsicOpinion| >= 0.6) among the top-follower-count "hub tier" by
chance. Checked directly on the 7700000-7700014 t0 snapshots (top-10-by-followerCount per seed):
**13 of 15 seeds already had at least one natural extreme agent in the top 10**, sign unsystematic.
Classified each seed as BOTH (both signs present, n=11), POS_ONLY (n=2), or NEITHER (n=2, seeds
7700001/7700008), then looked up each seed's already-computed B_always-minus-A_never effect
(bc_recovery=0.001 run) by category:

| category | n | d_bin0 | d_bin4 | d_assort | d_cross |
|---|---|---|---|---|---|
| BOTH | 11 | +0.0054 | +0.0022 | -0.0819 | +0.0388 |
| NEITHER | 2 | -0.0001 | +0.0010 | **-0.1639** | **+0.1434** |
| POS_ONLY | 2 | -0.0088 | -0.0009 | -0.1230 | +0.0332 |

Descriptive only (n=2 in two of three groups -- not a statistical test). Suggestive pattern: extreme-
camp behavioral effect (d_bin0/d_bin4) is near-zero specifically when no natural extreme hub exists,
while structural bridging (d_assort/d_cross) is if anything STRONGEST in that same group -- shape-
consistent with WSSIT's own claim (moderate conduit alone, without an extreme hub, doesn't worsen
polarization) but far too small-n to treat as confirmed. Motivates the design below rather than
concluding anything on its own.

### New experimental design (PLANNING ONLY -- not yet implemented)

Replaces "extreme=none, moderate class only" with a hub tier deliberately spanning the full opinion
spectrum, so extreme-hub presence is guaranteed and controlled per seed rather than left to chance.

**Hub-tier construction**: select top-N agents by t0 followerCount, reassign their intrinsicOpinion
into 5 categories symmetric left-right, bell-shaped (more weight toward moderate, per user's
"正規分布的"/Gaussian-like spec) -- proposed N=60, 20 each in Extreme (10 left/10 right), Pre-extreme
(10 left/10 right), Moderate (20), sized to match the existing N=20 moderate-class precedent per
category. Stubbornness left at normal per-agent draw (not pinned), matching this project's existing
"wasn't stubborn, wasn't engaged yet" rationale for `pinModerateIds`.

**Intervention categories** (3, extending WSSIT's own L/M/R with a 4th group WSSIT didn't test):
- **M** = Moderate (20 agents)
- **E** = Extreme, both signs combined (20 agents) -- WSSIT's own L+R
- **P** = Pre-extreme, both signs combined (20 agents) -- new, not in WSSIT's original design

**Arms** (6 of the full 2^3=8 WSSIT-style factorial; control = everyone active, unlike this whole
pilot's earlier A_never/B_always convention where "all silent" was the control):

| arm | M | E | P |
|---|---|---|---|
| control | active | active | active |
| M-silent | silent | active | active |
| E-silent | active | silent | active |
| P-silent | active | active | silent |
| E-only-active | silent | active | silent |
| P-only-active | silent | silent | active |

(M-only-active and all-silent, the other 2 of the full 8, deliberately dropped for this first pass --
easy to add later.)

**Required code change**: `pinModerateIds` only resets to intrinsicOpinion=0.0 -- this design needs a
generalization (pin an explicit ID list to an explicit target opinion, not just 0.0) since 4 of the 5
new categories are non-zero. Selection (top-N by t0 followerCount, category assignment) stays in
Python per this project's existing pattern; Java needs the more general pin-to-value primitive.
Silencing itself reuses the existing generic `silentUntilIds` unchanged.

### Handoff: hub-tier magnitude/strength dimension deferred to a future experiment

User (2026-08-04): also wants to test whether hub-tier STRENGTH matters -- mega-hub (very high
follower count, near the top of the plateau) vs. middle-tier (moderately-followed but still
above-average) -- i.e. does the L/M/P silencing design above produce different results depending on
how influential the reassigned hub tier actually is. **Explicitly deferred to a follow-up
experiment, not part of the design above.** When picked up: likely wants an additional factor
(hub-tier selection band -- e.g. top-20 vs. rank-100-150 -- crossed with the E/M/P silencing arms
above), reusing the existing tier-characterization work
(`docs/report/`'s hub_tier_characterization/hub_tier_v15_synth files from earlier sessions) as a
starting point for what "mega" vs "middle" should mean quantitatively in this model.

## 2026-08-04 (cont.) — L/M/P hub-tier design implemented and launched

**Code change** (`src/experiment/ExperimentConfig.java`, `src/dynamics/OpinionDynamics.java`): added
`pinOpinionIds` (`Map<Integer,Double>`, token `pin_opinion_ids=id:val,id:val,...`) as the required
generalization of `pinModerateIds` -- same one-time t=0 reset + stubbornness-left-free semantics, but
to an explicit per-agent target instead of a fixed 0.0. `pinModerateIds` kept unchanged (not replaced)
so existing scripts (bc_recovery OAT/retest, both bc screens) keep working. Both
`writeClassFollowerComposition` call sites (t0 + periodic) extended to log the union of
`pinModerateIds` and `pinOpinionIds.keySet()`. Compiled clean; smoke-tested end-to-end (one seed,
short run) confirming t0 `intrinsicOpinion`/`opinion` land exactly on the requested pin targets.

**Resolved open design points** (asked user, 2026-08-04):
- Pin targets: Extreme=±1.0 (matches existing `ExtremeMode.SYM` convention), Pre-extreme=±0.4
  (midpoint of the camp-bin range [0.2,0.6)/[-0.6,-0.2)), Moderate=0.0 (matches pre-existing
  `pinModerateIds` precedent).
- Category assignment: top-60 agents by t0 followerCount (unfiltered by opinion, unlike the earlier
  moderate-only |intrinsicOpinion|<0.2 selection), randomly split per-seed (seeded by the run's own
  seed, reproducible) into fixed sizes E(-1.0)=10, P(-0.4)=10, M(0.0)=20, P(+0.4)=10, E(+1.0)=10.
- bc regime: user chose the exploratory bc_recovery=0.001 point (2026-08-03 screen) over project
  defaults (0.0001), to keep testing under the most WSSIT-consistent bc regime found so far --
  despite that point alone not yet showing a robust extreme-camp effect (2026-08-04 bc_recovery OAT).
  This design's question (confound control: guaranteed vs. by-chance extreme-hub presence) is
  treated as separate from that bc-tuning question.

**Launched** (`scripts/lmp_hubtier_pilot.py`, PID 88279, `nohup`+`disown`, log
`logs/lmp_hubtier_pilot_stdout.log`): n=15 fresh seeds (8800000-8800014), steps=40000, 6 arms
(control, M_silent, E_silent, P_silent, E_only_active, P_only_active) = 90 runs, results under
`results/2026-08-04_lmp_hubtier_pilot/`. Completed cleanly (~28min, no errors).

**First-pass result (all-agent per-capita, hub+non-hub mixed): E_silent, not M_silent, dominates
the structural effect.** opinionAssortativity/crossCuttingFraction moved far more from silencing the
Extreme tier (assort -0.258, t=-12.57 -- the largest of any arm) than from silencing the Moderate
tier (assort +0.134, t=5.51). Signs are conduit-hypothesis-consistent throughout (M_silent and
E_only_active move the same direction; E_silent and P_silent move the opposite direction), but the
*magnitude* is dominated by the extreme-tier manipulation, not the moderate one -- an unplanned
reframing of which manipulation is doing the work, relative to what this whole pilot originally set
out to test (moderate hub's own causal role).

**Caveat raised (user) and follow-up needed**: bin-level per-capita rates mix each bin's PINNED
hub-tier agents (whose posting behavior is being directly manipulated by that arm) together with
ordinary non-hub agents who happen to land in the same camp -- so a bin's rate change conflates a
direct/compositional effect (the manipulated hub agents' own post count changing) with a genuine
spillover effect (ordinary camp members changing their own behavior in response). The two were not
separable in the first-pass numbers above.

## 2026-08-04 (cont. 2) — hub-vs-non-hub decomposition: numOfPosts/avgComfortRate added to agent
## snapshots, re-run in progress

**Code change**: `Writer.writeAgentSnapshot` (`src/writer/Writer.java`) gained two columns,
`numOfPosts` (`Agent.getNumOfPosts()`, cumulative-since-t0) and `avgComfortRate`
(`Agent.getAverageComfortRate()`, an internal trailing-100-step average already computed for the
bc/postProb feedback loop) -- both pre-existing Agent accessors, newly exposed. `OpinionDynamics`'s
existing step%5000==0 periodic-checkpoint block (already writing degrees/clustering/composition at
each checkpoint) now also calls `writeAgentSnapshot` there, giving a periodic per-agent snapshot at
no new checkpoint cadence. Diffing `numOfPosts` between the step=35000 snapshot and the "final"
(step=40000) snapshot gives a windowed (5000-step, not this pilot's usual 2000-step -- reusing the
existing 5000-step periodic cadence rather than adding a dedicated checkpoint, user's choice
2026-08-04) per-agent post count, without per-step per-agent logging. Compiled clean; smoke-tested
(short run, explicit pin_opinion_ids) confirming both new columns populate correctly and the
periodic label (`agent_snapshot_5000.csv` etc.) is written.

`scripts/lmp_hubtier_pilot.py` extended with `percapita_by_hubstatus`/`comfort_by_hubstatus`
(split any bin's population into the 60 known pinned hub-tier IDs vs everyone else, using each
agent's own ID membership, not a bin-derived proxy) and three new report sections: non-hub-only
per-capita post rate per arm vs control, non-hub-only mean comfort rate per arm vs control, and
hub-only per-capita post rate per arm vs control (to check whether the arm's effect on the hub
tier's own posting is itself just a mechanical consequence of silencing, vs. something else).
Motivating question (user, 2026-08-04): if the moderate-conduit hypothesis holds, M_silent should
show non-hub Extreme-camp per-capita posting *higher* than control (removing the bridge lets the
ordinary extreme camp post more freely) -- a spillover-only reading was not extractable from the
first-pass numbers above and needed this decomposition.

Prior 90-run output deleted (`rm -rf results/2026-08-04_lmp_hubtier_pilot/`, per project convention
-- conclusions above already written up) and the full 6-arm x 15-seed battery re-launched fresh
under the new instrumentation. Re-run completed cleanly (~28min, no errors, identical seeds so the
combined per-capita numbers exactly reproduced the first-pass run above -- a useful sanity check that
the new instrumentation didn't perturb core dynamics).

## 2026-08-04 (cont. 3) — numOfPosts dead end corrected; corrected non-hub result: conduit
## hypothesis's specific directional prediction NOT supported, but a real and different M_silent
## effect found concentrated in the pre-extreme camp

**`Agent.numOfPosts` is not a post counter -- implementation mistake, caught before being reported
as a finding.** All hub-vs-non-hub numbers from the previous entry came back degenerate (every
agent's `numOfPosts` identical at the step=35000 and "final" snapshots, diff=0 everywhere, hub AND
non-hub). Root cause: `Agent.java:93`, `setNumOfPosts(p.feedCapacity())`, called once in the
constructor and never updated again -- despite the name, this field is a static feed-read-capacity
value (matches `feed_capacity=15` exactly), not a cumulative post-authored count. No such per-agent
counter exists anywhere in the codebase currently.

**Better fix found, needing no further Java change or re-run.** `OpinionDynamics.java`'s existing
post-authoring block (lines ~383-390, comment "C3") already gates `writer.setPostBins(post)` behind
`if (!agent.getTarget())` -- i.e. `posts/post_result.csv`'s `bin_i` counts have ALWAYS excluded every
target/hub agent's own original posts, for every arm, regardless of that agent's active/silent
status (a pre-existing model design choice, not something added today, originally for the unrelated
reason of keeping `postOpinionVar` from reflecting an exogenously-fixed hub opinion). This means the
per-capita numbers reported in every entry of this pilot -- not just today's -- already had a
hub-post-free numerator; the only bug was the POPULATION denominator (`pop_counts()`) counting hub
agents alongside everyone else. Corrected in Python only: `pop_counts_nonhub()` filters
`agent_snapshot_final.csv`'s pre-existing `isTarget` column (unrelated to today's changes) before
binning. A genuine **hub-only** post rate is not recoverable from this file for the same reason (the
gate makes it identically zero) -- dropped from the script rather than reported as a real zero.

Reverted the now-pointless `numOfPosts` column/periodic snapshot (`Writer.java`, `OpinionDynamics
.java`) -- kept `avgComfortRate` (genuinely per-agent, unaffected by this bug, already gave sane
non-degenerate numbers in the first attempt). Recompiled; no re-run needed since existing
`post_result.csv`/`agent_snapshot_final.csv` data was already correct, only the Python aggregation
needed fixing.

**Corrected non-hub-only per-capita post rate (n=15, window=2000, this pilot's usual window --
denominator-only fix, no longer 5000):**

| arm vs control | bin0 extreme(-) | bin1 pre-ext(-) | bin2 moderate | bin3 pre-ext(+) | bin4 extreme(+) |
|---|---|---|---|---|---|
| M_silent | -6.3% (t=-2.65) | **+26.9% (t=3.83)** | -14.4% (t=-2.12) | **+29.9% (t=3.27)** | -9.6% (t=-3.04) |
| E_silent | -46.9% (t=-8.64) | -64.6% (t=-5.93) | -18.8% (t=-1.21 ns) | -52.5% (t=-3.53) | -44.3% (t=-7.32) |
| P_silent | -3.2% (t=-1.82 ns) | -50.1% (t=-9.01) | +24.8% (t=5.68) | -53.8% (t=-8.39) | -2.5% (t=-1.18 ns) |
| E_only_active | -6.2% (t=-2.69) | -10.0% (t=-1.18 ns) | -0.5% (t=-0.10 ns) | -10.7% (t=-1.22 ns) | -5.5% (t=-1.79 ns) |
| P_only_active | -46.6% (t=-9.25) | +17.6% (t=2.02) | -86.9% (t=-16.50) | +17.0% (t=1.64 ns) | -37.6% (t=-7.57) |

Essentially unchanged from the (already hub-post-free-numerator) first-pass numbers -- the
denominator correction was a ~5-10% adjustment, not a qualitative one, since hub-tier agents are a
small fraction (up to ~20 of ~100-300) of any one bin's population.

**User's specific hypothesis (2026-08-04) -- "if the conduit hypothesis holds, M_silent's non-hub
Extreme-camp per-capita posting should be HIGHER than control" -- is NOT supported.** bin0/bin4
(extreme camp) both move the WRONG direction under M_silent: -6.3% (t=-2.65) and -9.6% (t=-3.04),
both significant decreases, not the predicted increase. Non-hub comfort rate (mean `avgComfortRate`,
already hub-excluded via `isTarget`) shows the same direction: bin0 -0.013 (t=-1.72, ns), bin4 -0.022
(t=-2.71) -- the ordinary extreme camp does not become more vocal or more "comfortable" (a smaller
share of its feed within bounded-confidence range, this model's stand-in for feeling epistemically at
home) when the moderate hub tier is silenced.

**What DOES move under M_silent, robustly: the pre-extreme camp (bins 1 and 3), not the extreme
camp.** Both the ordinary population's per-capita posting (+26.9%/+29.9%, t=3.83/3.27) and comfort
rate (+0.106/+0.124, t=3.67/3.24) rise substantially and significantly in bins 1 and 3 -- the
"pre-extreme" bins (camp_bin range [-0.6,-0.2) and [0.2,0.6), one step short of the |op|>=0.6
"extreme" boundary used throughout this pilot). Silencing the moderate hub tier does not radicalize
the already-extreme camp; it energizes the partisan-but-not-fully-extreme camp specifically, while
the moderate bin itself (bin2) posts LESS (-14.4%, t=-2.12) -- consistent with a "moderate hub
removal pushes engagement toward partisan-but-bounded voices, not toward the poles" reading, distinct
from both the originally-hypothesized conduit mechanism and from straightforward radicalization.
E_silent and P_silent/P_only_active remain the larger-magnitude arms overall, as in the first pass.

**Caveat**: this is one seed block (n=15), one bc regime (bc_recovery=0.001, not project default),
and camp_bin's fixed 5-bin edges are somewhat arbitrary relative to where this pre-extreme-camp
effect concentrates -- not yet checked whether it's robust to a finer opinion-bin resolution or a
second seed block.

## 2026-08-04 (cont. 4) — user pushback discussion, WSSIT abstract cross-check, and a candidate
## north-star pivot pending robustness confirmation

**Discussion (not code) with user, working through what the M_silent finding does/doesn't support:**
- User's hypothesis going in (conduit): M_silent's non-hub Extreme camp should post MORE than
  control. Rejected above -- it posts LESS (both signs, significant).
- User asked whether "moderate present -> extreme relatively more active, pre-extreme relatively
  quieter" is consistent with WSSIT's own hypothesis. Checked `docs/wssit2026-TomoyaTakeda.tex`
  abstract/intro directly (not just `research-direction.md`'s paraphrase, per user's prompt that the
  literature is in `docs/`): the actual claim (lines 113-119, 166-175) is that the moderate's
  diffusion activity pushes **already-extreme** users into **more closed echo chambers**, accelerating
  **overall** polarization -- a structural/population-level claim, not specifically a posting-volume
  claim.
- Checked this pilot's own already-existing population-level metrics (all of which, per
  `Analysis.java` R16.1/R16.2 comments, already exclude target/hub agents -- `!agent.getTarget()`
  gates at lines 88, 131, 204, 227 -- so hub-tier contamination was never the issue here, contrary to
  a hypothesis raised mid-discussion): under M_silent, non-hub `opinionVar` and `bimodalityCoeff` are
  BOTH *higher* than control (t=8.04, t=8.57), and `opinionAssortativity` is higher too (already
  reported). I.e. on the metrics this project already treats as its own polarization/separation
  readouts, moderate PRESENCE is associated with a *less* polarized, *less* separated non-hub
  population -- the opposite direction from "moderate presence worsens overall polarization."
- User's next pushback: the extreme-camp per-capita boost might just be an echo of "any active hub
  boosts its own nearby camp" (a generic, expected effect, present in WSSIT too), not something
  specific to moderate. Checked by comparing sign patterns by opinion-distance from the silenced hub:
  M_silent moves bin2 (own camp) and bin0/bin4 (far/extreme) the SAME direction, but bin1/bin3
  (nearer/pre-extreme) the OPPOSITE direction -- not a monotonic distance-decay, which a pure "activity
  spillover fades with distance" story would predict. E_silent, by contrast, moves every bin (own,
  near, far) the SAME direction -- a much more ordinary decay pattern. This asymmetry argues the
  M_silent pre-extreme/extreme sign-flip is not simply an artifact of the generic own-camp-activation
  baseline, though the actual mechanism remains unexplained.

**User's conclusion (2026-08-04): "moderate hub's presence is linked to extreme-camp activation" is
interesting enough on its own to be a candidate north-star pivot (away from the structural-bridging
framing `research-direction.md` currently states) -- IF it survives a robustness check.** Explicitly
scoped as pending, not yet adopted -- `research-direction.md` not yet edited.

**Robustness check launched** (`scripts/lmp_hubtier_robustness.py`, PID 90187, `nohup`+`disown`, log
`logs/lmp_hubtier_robustness_stdout.log`), two axes, user's choice to start narrow (control/M_silent
only, not the full 6-arm battery) before widening:
1. **n increase**: 15 new seeds (8800015-8800029) added to the original 15, n=30 total, same
   bc_recovery=0.001 point.
2. **bc-regime dependence**: all 30 seeds re-run at bc_recovery=0.0001 (this project's own default,
   vs. the exploratory 2026-08-03-screen point the first-pass run used) -- checks whether the effect
   is specific to that not-yet-validated point.

90 new runs (30 reused from the first-pass run for the original-15-seeds/bc=0.001/control+M_silent
cell). Completed cleanly, ~28min, no errors.

**Results: the extreme-camp effect replicates and is bc-regime-robust; the pre-extreme sign-flip
does NOT hold up the same way -- it is largely a bc_recovery=0.001-specific artifact.**

| bin | n=15, bc=0.001 (first pass) | n=30, bc=0.001 (axis 1) | n=30, bc=0.0001 default (axis 2) |
|---|---|---|---|
| extreme(-) | -6.3% (t=-2.65) | -7.9% (t=-3.40) | **-5.1% (t=-3.10)** |
| pre-extreme(-) | +26.9% (t=3.83) | +20.2% (t=5.24) | **+5.7% (t=2.22)** |
| moderate | -14.4% (t=-2.12) | -9.9% (t=-2.32) | **-27.0% (t=-12.89)** |
| pre-extreme(+) | +29.9% (t=3.27) | +21.4% (t=4.38) | **+7.9% (t=2.54)** |
| extreme(+) | -9.6% (t=-3.04) | -5.7% (t=-2.95) | **-5.4% (t=-3.47)** |

**Axis 1 (n=30, same bc point): clean replication.** Every sign and significance from the n=15
first pass holds at n=30, magnitudes only mildly attenuated. Population-level metrics
(opinionVar/bimodalityCoeff/opinionAssortativity/crossCuttingFraction, all already non-hub via the
pre-existing `!agent.getTarget()` gates) replicate too, more strongly (t=8-13 vs t=5-9 at n=15).

**Axis 2 (n=30, project-default bc_recovery=0.0001): the extreme-camp magnitude is essentially
unchanged (-5.1%/-5.4% vs -7.9%/-5.7%) -- this part of the effect does NOT depend on the
not-yet-validated bc=0.001 point, a meaningfully more robust result than it looked going in.**
BUT the pre-extreme sign-flip shrinks by roughly 3x (+20-21% -> +6-8%) while the moderate camp's own
silencing effect roughly triples in the opposite direction (-9.9% -> -27.0%). This directly
undercuts the earlier (2026-08-04 cont.3) argument that the pre-extreme/extreme sign-flip couldn't
be explained by a simple own-camp-activation-with-decay story (based on E_silent's monotonic
same-sign pattern by contrast) -- under the default bc regime, pre-extreme's opposite sign is much
smaller relative to the now-dominant own-camp (moderate) effect, consistent with it being mostly
generic decay after all, at least at this bc point. **That specific argument is retracted.**
Population-level metrics again replicate in direction and significance under default bc, so the
"moderate presence -> less non-hub polarization/separation" finding (opposite of `wssit2026`'s
population-level claim) is not a bc_recovery=0.001 artifact either.

**Net assessment for the candidate north-star pivot**: the core, portable finding is narrower than
what motivated the pivot discussion -- "moderate hub's presence is associated with a higher
per-capita original-post rate in the non-hub extreme camp, by a stable ~5-8%, independent of the
bc_recovery point checked so far" survives both robustness axes tried. The "pre-extreme camp
specifically goes quiet, in a way distance-decay can't explain" argument does not survive and should
not be used to support the pivot. Not yet checked: a second, fully independent replication of the
bc=0.0001 point (only one n=30 block done so far for each bc value), sensitivity to the hub-tier
construction itself (pin magnitude, N_HUB size), and reconciling *why* an artificial hub-tier's
presence would robustly raise non-hub extreme-camp posting while simultaneously lowering non-hub
population-level opinion variance/bimodality/assortativity -- no mechanistic account exists yet for
either half of that pairing.

## 2026-08-04 (cont. 5) — independent measurement-pathway audit, prompted by the prior
## postShare/originalPostCount incident (684d6fc, e07e214)

**Context for why this audit happened**: this exact project already had one "extreme-camp effect"
claim inflated by a metric bug and withdrawn (2026-08-03, commit 684d6fc: `postShare_b` -- original-
posts-only, hub-excluded -- multiplied by `originalPostCount + repostCount`, inflating every
extreme-camp per-capita figure; caught via a direction-flip between two independent n=30 seed
blocks after the fix). Given today's candidate north-star pivot rests on a similar-shaped claim
("moderate present -> non-hub extreme camp posts more"), user (2026-08-04) asked for an independent
check of the measurement pathway before investing further in the mechanism/CN-submission question.
CN2026 submission deadline: **2026-09-02** (user, 2026-08-04).

**Check 1 -- bin-edge/classification formula consistency.** `Writer.setPostBins` (post_result.csv,
bins by `post.getPostOpinion()`) and `Agent.setOpinionClass` (drives `postShare_i`/`cRateMean_i`,
bins by `agent.getOpinion()`) both use `floor((x+1)/binWidth)` with `binWidth = 2/5`, tied to the
same `Const.NUM_OF_BINS_OF_POSTS = NUM_OF_BINS_OF_OPINION = 5` constant -- identical to this
session's Python `camp_bin()`. `setOpinionClass()` is called from inside `setOpinion()` itself
(`Agent.java:197-200`), so it can never go stale relative to the opinion value it classifies.

**Check 2 -- independent Java-computed pathway cross-check.** Naively cross-checking
`posts/post_result.csv`'s `bin_i` (this session's primary metric, hub-excluded numerator via the
pre-existing `!agent.getTarget()` gate) against `postShare_i * originalPostCount`
(`metrics/results.csv`) turned up an 8-14% systematic gap. Root cause, found by re-reading
`OpinionDynamics.java:369-392`: `stepStats.originalPostCount++` (line 373) happens BEFORE the
`!agent.getTarget()` gate (line 386) that both `writer.setPostBins` and `analyzer.setPostCash` (the
source of `postShare_i`) sit behind -- i.e. `originalPostCount` is hub-*inclusive* while
`postShare_i` is hub-*exclusive*. Multiplying them together is **the same category of error** as the
684d6fc bug (a hub-exclusive share times a hub-inclusive total), just smaller (no `+repostCount`
term this time). This was never used in any of this session's actual reported numbers -- it was
constructed fresh as a cross-check and immediately shown to be the wrong pathway -- but it's a
useful confirmation that this specific failure mode is easy to reintroduce by accident and worth
checking for explicitly each time a new cross-validation is attempted. Redone with `postShare_i *
sumOfPosts` (both hub-excluded -- `sumOfPosts` is post_result.csv's own row total) instead: matches
this session's primary `bin_i`-direct numbers to within floating-point rounding (single-digit-to-
tens differences against totals in the thousands, consistent with `postShare_i`'s ~4-decimal CSV
precision accumulated over a 2000-step window) for every (seed, arm, bin) spot-checked. This
independently confirms the classification+counting pipeline behind this session's reported numbers,
via a second Java-side code path (`Analysis.computePostShareArray`), not just a restatement of the
same computation.

**Check 3 -- split-block direction-flip check (the exact method that caught the 684d6fc bug).**
Split the n=30 robustness-check data into its two independent n=15 halves (original 8800000-14 vs
new 8800015-29) and re-checked M_silent-vs-control sign/significance separately in each half, at
both bc points:

| bin | bc=0.001 ORIG | bc=0.001 NEW | bc=0.0001 ORIG | bc=0.0001 NEW |
|---|---|---|---|---|
| extreme(-) | t=-2.65 | t=-2.37 | t=-1.86 | t=-2.47 |
| pre-extreme(-) | t=+3.83 | t=+4.11 | t=+2.06 | t=+0.93 (ns) |
| moderate | t=-2.12 | t=-1.03 (ns) | t=-11.65 | t=-7.63 |
| pre-extreme(+) | t=+3.27 | t=+3.63 | t=+2.05 | t=+1.47 (ns) |
| extreme(+) | t=-3.04 | t=-1.01 (ns) | t=-2.43 | t=-2.51 |

**No sign flips anywhere** across all 4 (bc x seed-half) cells -- the 684d6fc bug's signature. Some
cells lose significance at n=15 alone (expected, matches n=30-pooled t's being roughly
sqrt(2)x larger), but never reverse direction. Notably, **the extreme-camp bins (0 and 4) are the
most consistently significant across all four cells** -- more so than pre-extreme or moderate, which
each go non-significant in at least one half. This reverses this entry's earlier framing (extreme
as the "more robust, bc-independent" part vs. pre-extreme as the fragile part) into an even stronger
version of the same conclusion.

**Audit conclusion: no bug of the 684d6fc type found.** The extreme-camp per-capita effect is not a
measurement artifact of the kind that killed the earlier claim; it is currently this pilot's single
most robust result across bc regime and independent seed halves. This does not certify the finding
as submission-ready on its own (mechanism still unexplained; hub-tier construction still stylized;
population-level metrics still move the opposite direction from what a naive reading of `wssit2026`
would predict) -- it clears the specific, well-precedented failure mode this project has already
been burned by once, not every possible failure mode.

**CN2026 submission deadline confirmed: 2026-09-02** (user, 2026-08-04) -- roughly 4 weeks from
today. Sequencing agreed: OAT robustness sweep first, then mechanism investigation.

## 2026-08-04 (cont. 6) — compositional read of the population-metric "paradox"; 5-parameter OAT
## battery launched

**User's proposed resolution of the "extreme posts more, but population polarization metrics go
down" pairing**: two separate sub-effects exist under moderate-hub presence -- (1) the moderate
camp's own posting increases (intuitive: an active hub directly engages its own audience) and (2)
the non-hub extreme camp's posting increases (the counterintuitive finding under audit) -- and (1)
dominates (2) in raw volume, so the *net* effect on population-level opinion metrics leans toward
de-escalation rather than polarization.

Checked directly against already-collected data (raw window post counts, non-hub, control minus
M_silent, n=30): moderate camp's own absolute volume increase is **5.1x** (bc=0.001) to **11.0x**
(bc=0.0001) larger than the extreme camp's combined absolute volume increase. Quantitatively
confirms the volume-dominance claim as stated. **Caveat**: pre-extreme camp's volume DECREASE
(-13312 posts at bc=0.001, -8149 at bc=0.0001) is comparable to or larger than the moderate camp's
increase in the same window -- the three-way net (moderate + extreme + pre-extreme) is negative at
bc=0.001 and positive at bc=0.0001, i.e. it doesn't resolve to a single consistent sign across bc
regimes on its own. More importantly, posting VOLUME by camp is not mechanically the same quantity
as population-level opinion VARIANCE (`opinionVar`/`bimodalityCoeff`) -- translating one into the
other requires an exposure/assimilation step (more moderate content circulating pulls other agents'
opinions toward moderate via bounded-confidence assimilation) that hasn't been directly measured.
The volume comparison supports the *plausibility* of the user's story; it is not yet a demonstrated
causal mechanism.

**5-parameter OAT battery launched** (`scripts/lmp_hubtier_oat_battery.py`, PID 92001, `nohup`+
`disown`, log `logs/lmp_hubtier_oat_battery_stdout.log`), modeled on the project's own precedent
battery (`delayed_moderate_pilot_postfix_oat_battery.py`, e07e214) for comparability. Baseline now
uses bc_recovery=0.0001 (project default, not the exploratory point) since both bc points already
passed the robustness check and default is more citable. Axes (2 non-baseline levels each, +1
topology change = 10 configs): `p_u` (0.01/0.15, reused verbatim from the precedent),
`vocal_comfort_radius` (0.05/0.2, reused verbatim), `N_HUB` hub-tier size (30/90 vs default 60 --
substitute for the precedent's "class top-K", which doesn't translate since this design's selection
is unfiltered by opinion), Extreme-category pin magnitude (+-0.8/+-0.6 vs default +-1.0 -- substitute
for the precedent's "class threshold"; +-0.6 doubles as this project's own natural-extreme
classification boundary), and `network=dcsbm` (verbatim). control/M_silent only, n=15 seeds
(8900000-8900014, fresh block), n=15 chosen as a screen per this project's established two-stage
pattern (screen at n=15, confirm promising points at n=30) -- 300 runs, estimated 1.5-2hr. Both the
HK and dcsbm class-selection/pin/launch code paths were smoke-tested end-to-end (short runs) before
the full launch. Results pending.

## 2026-08-04 (cont. 7) — OAT battery results: extreme-camp effect does NOT survive; north-star
## pivot dropped; converges with this project's own prior (e07e214) conclusion

Completed cleanly (10 configs x 15 seeds x 2 arms = 300 runs, no errors). Per-bin robustness count
across all 10 configs (significant = |t|>=2):

| bin | significant, baseline direction | significant, REVERSED | not significant |
|---|---|---|---|
| extreme(-) (bin0) | pu_015, dcsbm (2/10) | **pu_001 (t=+2.83)** | 7/10 |
| extreme(+) (bin4) | baseline, pu_015, pinext08 (3/10) | **pu_001 (t=+2.72)** | 6/10 |
| pre-extreme (bin1/3) | 6-8/10 (sign consistent 10/10, significance varies) | 0/10 | rest |
| moderate (bin2) | **10/10** | 0/10 | 0/10 |
| opinionVar/bimodalityCoeff/opinionAssortativity/crossCuttingFraction | **10/10 each** | 0/10 | 0/10 |

**The extreme-camp effect (bin0/bin4) does not survive this OAT.** Significant in only 2-3 of 10
configs, and at `p_u=0.01` it **significantly reverses sign** (t=+2.83/+2.72 -- moderate PRESENCE
associated with LESS non-hub extreme-camp posting there, opposite of every other config). A real
effect surviving a nuisance-parameter change should not flip sign; a minority-significant,
sign-flipping pattern across an OAT sweep is the same category of evidence that killed the original
single-moderate-class-design "extreme-camp activation" claim in e07e214 ("no config reaches
significance") -- if anything this is a clearer kill signal, since it also flips sign rather than
just staying null.

**Everything else is completely robust: 10/10 configs, no exceptions, no flips.** Moderate camp's
own-activation effect (bin2, control > M_silent always), pre-extreme's suppression (sign-consistent
in all 10, though significance varies with power), and all four population/structural metrics
(opinionVar, bimodalityCoeff, opinionAssortativity, crossCuttingFraction -- all non-hub via the
pre-existing `!agent.getTarget()` gates) move the same direction and reach significance in every
single config tried, across p_u, vocal_comfort_radius, hub-tier size, pin magnitude, and network
topology.

**Decision: the candidate north-star pivot (moderate hub -> extreme-camp activation) is dropped.**
It does not clear this OAT, on top of already being this pilot's weakest link going in (unexplained
mechanism, tension with population-level metrics). What DOES survive -- moderate self-reinforcement
+ pre-extreme suppression + structural bridging (opinionAssortativity down / crossCuttingFraction up
when moderate present) -- is not a new finding: it is the **same conclusion this project already
reached once before**, via the entirely different single-moderate-class experimental design
(e07e214, 2026-08-04: "Paper's central claim moves to this redistribution effect"). Reaching it
again independently, via a structurally different hub-tier design (multi-category, opinion-
unfiltered top-N selection, explicit pin-to-value) that was specifically built to control for the
natural-extreme-hub confound the earlier design didn't address, is convergent evidence for this
being the real, portable finding -- not an artifact of either design's specific construction.

**Revised plan for the CN2026 submission (deadline 2026-09-02)**: anchor on moderate self-
reinforcement + pre-extreme suppression + structural bridging (all 10/10-robust), not extreme-camp
activation. `research-direction.md`'s existing structural-bridging framing (§1a) does not need to be
abandoned after all -- the pivot discussion (cont.4-6 above) is superseded. Next: mechanism
investigation for the now-confirmed-robust redistribution effect (why pre-extreme specifically, not
extreme; how it connects to the structural cross-cutting-exposure story already in
`research-direction.md`'s open mediation-analysis item).

**Follow-up (user, 2026-08-04): population-weighted bin0+bin4 combined ("extreme camp" as one
group) with Cohen's d effect size, per config:**

| config | control | M_silent | diff | pct | t | d |
|---|---|---|---|---|---|---|
| baseline | 0.03491 | 0.03344 | -0.00147 | -4.2% | -2.90 | -0.748 |
| pu_001 | 0.02485 | 0.02780 | +0.00295 | +11.9% | **+3.41** | **+0.881** |
| pu_015 | 0.03803 | 0.03501 | -0.00302 | -8.0% | -4.26 | -1.101 |
| vcr_005 | 0.01619 | 0.01653 | +0.00034 | +2.1% | +0.63 | +0.163 |
| vcr_02 | 0.07106 | 0.07299 | +0.00194 | +2.7% | **+2.30** | **+0.593** |
| nhub30 | 0.03721 | 0.03642 | -0.00079 | -2.1% | -1.22 | -0.314 |
| nhub90 | 0.03314 | 0.03178 | -0.00136 | -4.1% | -2.47 | -0.638 |
| pinext08 | 0.05794 | 0.05679 | -0.00115 | -2.0% | -2.17 | -0.561 |
| pinext06 | 0.03819 | 0.03756 | -0.00063 | -1.7% | -0.35 | -0.090 |
| dcsbm | 0.03790 | 0.03598 | -0.00192 | -5.1% | -2.23 | -0.575 |

Pooling bin0+bin4 (population-weighted) raises power and pushes 5/10 configs to significance in the
baseline direction (baseline, pu_015, nhub90, pinext08, dcsbm) -- more than either bin alone. But it
ALSO raises a SECOND config (vcr_02, d=+0.593, joining pu_001's d=+0.881) to significance in the
REVERSED direction. **This makes the case for a real, single underlying effect weaker, not
stronger**: added power should sharpen a true signal toward one consistent direction, not surface
additional large-effect-size (|d| 0.59-1.10) reversals. The effect-size spread across configs
(-1.101 to +0.881, both "large" by Cohen's convention, on the SAME sign-flipped quantity) is itself
evidence against treating this as one stable phenomenon with sampling noise around a fixed true
value -- that would predict a tighter, one-signed distribution of d even where individual configs
miss significance. Reinforces this entry's earlier decision to drop the extreme-camp-activation
pivot.

**User's follow-up read of the p_u/vcr shapes (2026-08-04), corrected against the actual numbers**:
user initially described "effect vanishes at large vcr and small p_u, small-vcr reversal is
confusing" -- checking the actual d values, it's the other way around: p_u=0.01 REVERSES (d=+0.881,
not null) and vcr=0.05 goes toward NULL (d=+0.163, not reversed), while vcr=0.2 is the one that
REVERSES (d=+0.593). Corrected, the shapes are: **p_u looks monotonic** (d: +0.881 at 0.01 -> -0.748
at 0.05 -> -1.101 at 0.15, i.e. baseline-direction effect strengthens smoothly as p_u rises, tying
directly to `research-direction.md`'s own P_u-driven Type-1/Type-2 phase-diagram framing) -- flagged
as a plausible, mechanistically-motivated axis worth resolving finely. **vcr looks non-monotonic**
(d: +0.163 at 0.05 -> -0.748 at 0.1 -> +0.593 at 0.2, an apparent inverted shape) with only 3 points,
too coarse to interpret yet.

**Finer sweep launched** (`scripts/lmp_hubtier_pu_vcr_finegrain.py`, PID 95280, `nohup`+`disown`, log
`logs/lmp_hubtier_pu_vcr_finegrain_stdout.log`): same seed block (8900000-8900014) and hub-tier
construction as the OAT battery (reuses its HK class-selection dry run -- membership is identical,
verified the reused baseline config reproduces d=-0.748 exactly before launching). New points: p_u
in {0.02, 0.03, 0.10, 0.25} (brackets the 0.01->0.05 sign-flip region and extends past 0.15); vcr in
{0.075, 0.15, 0.3} (fills both gaps and extends past 0.2). Combined with the existing 3+3 OAT-battery
points (reused, not re-run): 7 p_u points, 6 vcr points total. control/M_silent only, n=15, 210 new
runs.

**Bug caught immediately on first run (before any wrong numbers were reported)**: the new-config job
loop built `results_subdir` as `f"{SUBDIR}/{name}"` -- missing the `/{arm}` component the reporting
code expects (`f"{subdir}/{arm}"`) and that the OAT battery/robustness scripts already got right.
control and M_silent collided into the same output directory per (config, seed) -- the exact same
category of path bug flagged in this same report's 2026-08-04 bc_recovery-OAT entry ("first attempt
had a path bug -- A_never/B_always outputs collided... since results_subdir was missing /{arm}").
Surfaced immediately as a crash (`result_dir` returning `None` for the mismatched path) while
printing the reused `pu_001` point, not a silently-wrong number -- caught before reaching the vcr
report or being read as a finding. Fixed (`jobs.append((s, FULL_STEPS, f"{SUBDIR}/{name}/{arm}",
tokens))`), corrupted output deleted, re-launched clean (PID 98313, same log path).

**Results (completed cleanly, ~50min, no errors): p_u traces a sharp, orderly transition; vcr does
not.**

| p_u | diff | t | d |
|---|---|---|---|
| 0.01 | +0.00295 | +3.41 | **+0.881** (reversed, sig) |
| 0.02 | -0.00023 | -0.52 | -0.134 (~null) |
| 0.03 | -0.00101 | -1.96 | -0.506 (borderline) |
| 0.05 (baseline) | -0.00147 | -2.90 | -0.748 (sig) |
| 0.10 | -0.00205 | -3.13 | -0.807 (sig) |
| 0.15 | -0.00302 | -4.26 | **-1.101** (peak, sig) |
| 0.25 | -0.00240 | -3.52 | -0.909 (sig, slightly relaxed from peak) |

| vcr | diff | t | d |
|---|---|---|---|
| 0.05 | +0.00034 | +0.63 | +0.163 (~null) |
| 0.075 | -0.00152 | -3.12 | -0.807 (sig) |
| 0.1 (baseline) | -0.00147 | -2.90 | -0.748 (sig) |
| 0.15 | +0.00034 | +0.44 | +0.114 (~null) |
| 0.2 | +0.00194 | +2.30 | +0.593 (sig, reversed) |
| 0.3 | +0.00229 | +2.11 | +0.544 (sig, reversed) |

**p_u**: the sign crossing is confined to a narrow region between 0.01 and 0.02 -- from 0.03 through
0.25 (almost a full order of magnitude), the effect is consistently baseline-direction and
significant, peaking near 0.15 and relaxing only slightly by 0.25. This is NOT the profile of pure
noise (which would not produce a single narrow crossing followed by a wide, smooth, one-signed
plateau) -- it looks like a genuine, sharp transition near a critical p_u, directly evocative of
`research-direction.md`'s own P_u-driven Type-1/Type-2 phase-diagram framing (high P_u = discomfort-
triggered sorting; low P_u = ties persist through disagreement). **Revises the prior "effect-size
spread argues against a single stable phenomenon" conclusion for the p_u axis specifically**: outside
a narrow critical band, the effect is now one of this pilot's more orderly results.

**vcr**: the shape crosses sign TWICE (null -> negative at 0.075-0.1 -> null at 0.15 -> positive at
0.2-0.3), not a single clean transition. Six points isn't enough to tell a real double-crossover
structure (e.g. two competing vcr-sensitive pathways) from residual noise. Left open.

**Implication for next steps**: the p_u critical-transition shape is now a plausible entry point for
the mechanism investigation of the already-robust redistribution effect (moderate self-reinforcement
+ pre-extreme suppression + structural bridging) -- if that effect shares the same P_u-dependence
shape, it would tie both findings to one underlying phase-transition mechanism rather than two
unrelated phenomena. Not yet checked whether moderate-self/pre-extreme/structural metrics trace the
same p_u shape (same narrow 0.01-0.02 crossing, same ~0.15 peak) as the extreme-camp effect does.

## 2026-08-04 (cont. 8) — novelty pivot decided; bc-vs-vcr design question; comfortPostRate
## identified as the likely proximate mediator

**User (2026-08-04): the "robust redistribution" north star (moderate self-reinforcement +
pre-extreme suppression + structural bridging) has too little novelty on its own -- prefers a paper
built around explaining the extreme-camp effect's MECHANISM, including its reversal, rather than
reporting it as a clean main effect.** Agreed this is more novel IF it can be explained, but flagged
three gaps before it's submission-ready: (1) n=30 confirmation at the key boundary points (currently
only n=15-screened), (2) an actual mechanistic account of the reversal (not just "it reverses
here"), (3) a real p_u x vcr 2-D grid if the paper is going to invoke `research-direction.md`'s own
"phase diagram" framing (current data is two independent 1-D slices, not a joint map). Agreed
sequencing: n=30 confirmation -> small 2D grid -> mechanism, but mechanism work started immediately
below since it was cheap (no new runs) and directly responsive to the next question raised.

**User's design-consistency question**: given `vocalComfortRadius` (vcr, an expression/comfort
threshold) and `bc` (bounded confidence, a rejection/assimilation threshold) are deliberately
decoupled by design (`Agent.java:324-338` javadoc), shouldn't vcr be smaller than bc's floor
(`bc_floor=0.2`) on interpretive grounds -- otherwise there exist agents who'd find a post
"comfortable enough to voice support near" (within vcr) that they wouldn't even let move their OWN
opinion (outside bc)?

Checked directly (non-hub extreme-camp agents' final-snapshot `bc`, across the vcr sweep, control
arm): mean bc rises monotonically with vcr (0.255 at vcr=0.05 -> 0.306 at vcr=0.3) despite `bc_floor`
being a fixed constant (0.2) across all these runs -- vcr and bc are empirically coupled through the
dynamics even though structurally independent by design. The literal "bc < vcr" population is 0% at
every vcr up to 0.2, jumping to 44.4% only at vcr=0.3 -- i.e. NOT a clean single-threshold story
lining up with the sign reversal that already happens at vcr=0.2. The user's intuition was
directionally right (vcr and bc interact in a way that matters) but the specific mechanism isn't a
literal bc-floor crossing.

**comfortPostRate identified as the likely proximate mediator.** `Writer.writeAgentSnapshot`'s
`avgComfortRate` column (added earlier this session for an unrelated hub-split check, still present)
gives a direct per-agent read on the variable vcr actually drives (`comfortPostRate`, feeding
`postProb` via the existing graded comfort-to-vocality mechanism, `Agent.java`). Computed the same
control-vs-M_silent, non-hub, extreme-camp-only comparison on `avgComfortRate` across both sweeps:

| vcr | posting-rate d | comfortRate d | | p_u | posting-rate d | comfortRate d |
|---|---|---|---|---|---|---|
| 0.05 | +0.163 (ns) | +0.214 (ns) | | 0.01 | +0.881 (sig) | +0.892 (sig) |
| 0.075 | -0.807 (sig) | -0.518 (sig) | | 0.02 | -0.134 (ns) | +0.100 (ns) |
| 0.1 (baseline) | -0.748 (sig) | -0.495 (border) | | 0.03 | -0.506 (border) | +0.211 (ns) |
| 0.15 | +0.114 (ns) | **+0.608 (sig)** | | 0.05 (baseline) | -0.748 (sig) | -0.495 (border) |
| 0.2 | +0.593 (sig) | +0.882 (sig) | | 0.10 | -0.807 (sig) | -0.668 (sig) |
| 0.3 | +0.544 (sig) | +0.791 (sig) | | 0.15 | -1.101 (sig, peak) | -0.743 (sig) |
| | | | | 0.25 | -0.909 (sig) | -0.210 (ns) |

**vcr axis: comfortRate's sign matches posting-rate's at every point, and LEADS it at vcr=0.15**
(comfortRate already significantly reversed there while posting-rate is still null) -- strong
evidence `comfortPostRate` is the proximate driver, not a coincidental correlate, for this axis.
**p_u axis: directionally matches at both extremes (0.01 reversal, 0.05-0.15 baseline-direction) but
diverges in the crossover region (0.02-0.03, comfortRate still positive while posting-rate already
trends negative) and weakens at 0.25** -- comfortPostRate likely still part of the p_u story but not
the whole of it; p_u probably also acts through a slower, structural (network-rewiring) channel that
comfortPostRate alone doesn't capture.

**Next**: understand WHY comfortPostRate itself flips sign with vcr (control vs. M_silent) -- likely
requires looking at feed composition (share of an extreme-camp agent's feed authored by the pinned
moderate hub tier vs. by other extreme/pre-extreme agents) as a function of vcr, not yet done.

## 2026-08-04 (cont. 9) — story-level critique; "let the thesis emerge" decision; p_u x vcr joint
## grid launched

**Story-level critique requested by user (explicitly separate from the mechanism/evidence critique
above)**: is "moderate hub's psychological effect on the out-group flips sign with structural
regime" a good CN *narrative*, independent of whether it's proven yet? Assessment: the narrative
TYPE (a threshold/regime-reversal of an intervention's effect) is a well-trodden, well-received CN/
opinion-dynamics archetype (bounded-confidence consensus/polarization/fragmentation regimes, cascade-
threshold models). But the specific realization risks reading as idiosyncratic to this model's own
bespoke `vocal_comfort_radius` construct (not a widely-recognized theoretical construct, unlike
`p_u`/tie-dissolution which IS recognizable from echo-chamber literature) unless tied back to a more
general theoretical distinction. This project already has one sitting unused: `research-direction
.md`'s own Type-1 (structural separation) / Type-2 (connected-but-hostile) distinction. Strongest
version of the story: "the moderate's psychological effect on the out-group flips sign at the Type-1/
Type-2 boundary" -- reframes an idiosyncratic parameter-dependence into a phase-transition result
tied to this project's own established conceptual frame, rather than an ad-hoc empirical curiosity.
Also recommended NOT treating this as competing with the already-robust moderate-self-reinforcement/
pre-extreme-suppression finding, but as a two-part story: robust "own-camp consolidation + adjacent-
camp suppression" as the backbone, with the regime-dependent far-extreme-camp effect as a novel
twist on top -- addresses both the "too obvious" critique (of the robust part alone) and the
"unproven/fragile" critique (of the regime-dependent part alone) by having each compensate for the
other's weakness.

**Decision (user, 2026-08-04): proceed empirically first ("let the thesis emerge from the data")
rather than pre-committing to the Type-1/Type-2 framing or any other specific thesis before more
data exists.** Immediate next step per the already-agreed priority order: the p_u x vcr joint grid
(a single 1-D slice at a time cannot distinguish a real 2-D phase boundary from two unrelated
marginal effects, which is the single largest evidentiary gap flagged in the mechanism critique).

**Grid launched** (`scripts/lmp_hubtier_pu_vcr_grid.py`, PID 98850, `nohup`+`disown`, log
`logs/lmp_hubtier_pu_vcr_grid_stdout.log`): p_u in {0.01, 0.03, 0.05, 0.15} x vcr in {0.1, 0.15, 0.2,
0.3}, 4x4=16 cells. Deliberately reuses 7 already-completed cells (the baseline-row and baseline-
column marginal points already run in the OAT battery / finegrain sweep, verified present with 15
control runs each before launching) -- only 9 off-diagonal (both-non-baseline) cells are new: (0.01,
0.15/0.2/0.3), (0.03, 0.15/0.2/0.3), (0.15, 0.15/0.2/0.3). Same seed block (8900000-8900014) and
hub-tier construction (reused HK class-selection) as both prior sweeps. control/M_silent only, n=15,
270 new runs, reports both combined-bin0+bin4 posting-rate d and avgComfortRate d per cell as a 4x4
grid.

**Results (completed cleanly, ~67min, no errors). Reused-cell values match their earlier 1-D sweep
values exactly (e.g. p_u=0.05/vcr=0.1 baseline: d=-0.748 both times; p_u=0.01/vcr=0.1: d=+0.881 both
times) -- confirms the cell-reuse logic worked correctly.**

Posting-rate d, full grid:

| p_u \ vcr | 0.1 | 0.15 | 0.2 | 0.3 |
|---|---|---|---|---|
| 0.01 | +0.881 | +0.686 | +0.698 | +0.559 |
| 0.03 | -0.506 | +0.240 | +0.824 | +0.802 |
| 0.05 (baseline) | -0.748 | +0.114 | +0.593 | +0.544 |
| 0.15 | -1.101 | -1.032 | +0.199 | **+1.365** (grid max) |

avgComfortRate d, full grid:

| p_u \ vcr | 0.1 | 0.15 | 0.2 | 0.3 |
|---|---|---|---|---|
| 0.01 | +0.892 | +0.763 | +0.782 | +0.615 |
| 0.03 | +0.211 | +0.655 | +0.825 | +1.121 |
| 0.05 (baseline) | -0.495 | +0.608 | +0.882 | +0.791 |
| 0.15 | -0.743 | -0.517 | +0.390 | **+1.778** (grid max) |

**This is NOT a simple additive/two-independent-marginal-effects pattern -- there is a genuine
interaction.** Under an additive model (effect = f(p_u) + g(vcr)), every row's shape across vcr would
be the same curve shifted up/down by a row-specific constant. Instead:
- The p_u=0.01 row is nearly FLAT across the entire vcr range (+0.56 to +0.88) -- p_u=0.01 sits in
  the reversed regime regardless of vcr, essentially insensitive to it.
- The p_u=0.03 and p_u=0.05 rows both show a smooth, similar-shaped rise from negative (vcr=0.1) to
  positive (vcr=0.2-0.3), crossing near vcr≈0.13-0.15.
- **The p_u=0.15 row has a qualitatively different shape from every other row**: it starts as the
  MOST negative of any row at vcr=0.1-0.15 (deepest baseline-direction trough, -1.10/-1.03), stays
  negative through vcr=0.15 (where every other row has already crossed to positive or near-zero),
  then swings past zero and OVERSHOOTS to the single largest effect anywhere in the grid at vcr=0.3
  (d=+1.365 posting / +1.778 comfort). A late, then sharpest, crossing -- not a shifted copy of the
  other rows' curves.

**Reading**: higher p_u (more willingness to prune uncomfortable ties) appears to sharpen and delay
the vcr-driven sign transition rather than simply shifting it -- consistent with a genuine 2-D
regime structure (interaction), not two independent 1-D effects that happen to both exist. This is
still a coarse 4x4 grid at n=15/cell -- several cells are individually non-significant (e.g.
p_u=0.03/vcr=0.15: t=+0.93; p_u=0.15/vcr=0.2: t=+0.77) and no formal interaction test (e.g. 2-way
ANOVA on the interaction term) has been run -- but the qualitative shape (one row behaving
categorically differently from the other three) is visually clear and not easily dismissed as
per-cell noise. Candidate next steps (not yet decided): finer resolution specifically around the
p_u=0.15 row's vcr=0.15-0.3 transition (where the sharpest, largest swing is); n=30 confirmation of
the p_u=0.15/vcr=0.3 extreme cell specifically, since it's both the grid's largest effect and the
best evidence for genuine interaction.

## 2026-08-04 (cont. 10) — frank "is this a good thesis" critique; moderate-specificity check
## launched

**User asked for a frank, harsh assessment of whether this interaction, if mechanistically
explained, would make a genuinely interesting thesis.** Verdict: possibly, but one load-bearing
check is missing and must come before investing in mechanism. Two specific risks flagged:
1. **Moderate-specificity is unverified.** The p_u=0.15 row's "trough then largest-in-grid overshoot"
   shape could be a property of silencing ANY hub-tier category under low-p_u/wide-vcr conditions
   (e.g. "low p_u = less noise = bigger effect for any manipulation"), not something specific to
   moderate's structural bridging role. If a placebo manipulation shows the same shape, the
   "moderate" framing collapses into a generic statement about model sensitivity.
2. **vcr has no obvious real-world referent** (unlike p_u, which maps loosely to platform
   unfollow/block friction), weakening external resonance even if the internal mechanism is clean.
Recommended checking (1) first since it is cheap and would immediately kill or validate the thesis
before further investment.

**Specificity check launched** (`scripts/lmp_hubtier_specificity_check.py`, PID 3232, `nohup`+
`disown`, log `logs/lmp_hubtier_specificity_check_stdout.log`): P_silent (Pre-extreme hub tier
silenced instead of Moderate) as the placebo, chosen over E_silent because P_silent's effect size in
the original 6-arm pilot was comparable in magnitude to M_silent's (E_silent dominated every arm and
would trivially show large effects regardless of p_u/vcr, an unfair/uninformative placebo). Same 8
diagnostic cells as the most informative slice of the grid: p_u=0.15 row (the qualitatively distinct
row) and p_u=0.05/baseline row (the ordinary-looking row), each across all 4 vcr points. Reuses the
already-collected control-arm data at those 16 grid cells (verified present before launching) --
only the 8x15=120 new P_silent runs were needed. If P_silent's shape at these 8 cells resembles
M_silent's (same qualitative pattern: ordinary crossover at p_u=0.05, distinct trough-then-overshoot
at p_u=0.15), the interaction is likely generic, not moderate-specific -- reframe or drop this
thesis line. If P_silent's shape looks qualitatively different (e.g. flat, monotonic, or no sharp
p_u=0.15 anomaly), that supports moderate-specificity and justifies moving to mechanism.

**Results (completed cleanly, 120 runs, no errors): specificity check PASSES clearly.** P_silent
(placebo) shows NO sign reversal across vcr at either p_u row -- posting-rate d stays negative
throughout (p_u=0.05: -0.305/-0.824/-0.613/-0.941; p_u=0.15: -0.607/-0.942/-0.641/-0.556), and
avgComfortRate d actually grows MORE negative as vcr rises (opposite trend from M_silent's
negative-to-positive crossing). Compare M_silent's shape at the identical 8 cells: posting-rate d
p_u=0.05: -0.748/+0.114/+0.593/+0.544 (crosses to positive); p_u=0.15: -1.101/-1.032/+0.199/+1.365
(delayed crossing, then overshoots to the grid's largest effect). The two placebo metrics
(posting-rate AND comfortRate) both show P_silent monotonic/one-signed where M_silent shows a clean
crossing -- a qualitative difference, not just smaller magnitude.

**Conclusion: the p_u x vcr interaction (sign reversal, and the p_u=0.15 row's qualitatively
distinct trough-then-overshoot shape) is specific to silencing the Moderate hub-tier category, not
a generic "any silenced category behaves this way under low-p_u/high-vcr" artifact.** This was the
single cheap, load-bearing check identified as necessary before investing further in mechanism work
(risk #1 from the cont.10 critique) -- it passes. Risk #2 from that critique (vcr has no obvious
real-world referent, unlike p_u) remains open and unaddressed by this check. Next: mechanism
investigation (feed composition) can now proceed with justified confidence that there is a real,
moderate-specific phenomenon to explain, not a modeling artifact.

---

## HANDOFF (2026-08-04, end of session) — next step is the mechanism ("why"), read this first

**What's robust and safe to build on (do not re-litigate without new evidence):**
- Moderate hub's presence reinforces its OWN camp's posting (non-hub bin2 per-capita rate) --
  significant in 10/10 OAT-battery configs, no exceptions.
- Moderate's presence suppresses the adjacent PRE-EXTREME camp's posting (bins 1/3) -- sign-
  consistent in 10/10 configs (significance varies with power, but never reverses).
- Moderate's presence is associated with LOWER non-hub `opinionVar`/`bimodalityCoeff`/
  `opinionAssortativity` and HIGHER `crossCuttingFraction` -- i.e. less structural separation --
  10/10 configs, no exceptions. (Opposite direction from a naive reading of `wssit2026`'s population-
  level claim; not yet reconciled, but robust as measured.)
- These three findings are the credible backbone/north-star anchor regardless of what happens with
  the thread below.

**What's provisional, in-progress, and NOT yet paper-ready (this is the live thread):**
- The FAR-EXTREME camp (non-hub bin0+bin4) does NOT show a simple, one-direction main effect from
  moderate silencing -- earlier attempts to claim "moderate activates extreme camp" as a blanket
  effect were tested via a 10-config OAT battery and DID NOT survive (only 2-4/10 configs
  significant in one direction, with a significant reversal at p_u=0.01) -- **do not resurrect the
  simple-main-effect framing.**
- What DOES survive: a genuine p_u x vcr (`vocal_comfort_radius`) INTERACTION -- a 4x4 grid
  (p_u in {0.01,0.03,0.05,0.15}, vcr in {0.1,0.15,0.2,0.3}) shows a non-additive shape, most notably
  the p_u=0.15 row behaving qualitatively differently from the other three (deepest baseline-
  direction trough at low vcr, then overshoots to the grid's single largest effect, d=+1.365 posting
  / +1.778 comfort, at vcr=0.3).
- This interaction is MODERATE-SPECIFIC, not a generic "any silenced category looks complicated at
  low-p_u/high-vcr" artifact -- confirmed via a placebo check (P_silent at the same 8 diagnostic
  cells shows NO sign reversal anywhere, qualitatively different shape from M_silent).
- The likely proximate mediator is `avgComfortRate` (an already-logged per-agent field, added this
  session to `Writer.writeAgentSnapshot`) -- it tracks, and on the vcr axis even LEADS, the posting-
  rate sign flip, consistent with the model's existing built-in `comfortPostRate -> postProb` graded-
  vocality mechanism.
- **NOT yet done, and this is the actual next step**: WHY does `avgComfortRate` itself flip sign
  between control and M_silent as p_u/vcr vary? This requires a FEED-COMPOSITION analysis -- for
  non-hub extreme-camp agents, what fraction of their feed is authored by the pinned Moderate hub
  tier vs. other sources, and how does that fraction (and its relationship to each reader's own bc/
  opinion) change with p_u and vcr, comparing control vs M_silent. **This data is very likely NOT
  currently logged anywhere** -- check first, but expect this needs new Java instrumentation (a
  per-agent or per-step feed-composition counter), similar in scope to the `avgComfortRate` column
  added this session (`Writer.java`/`OpinionDynamics.java`, small, additive, non-breaking changes
  each time so far).

**Known weaknesses to keep in mind while pursuing the mechanism (don't let these get lost):**
- `vocal_comfort_radius` has no established real-world referent (unlike `p_u`, which maps loosely to
  platform unfollow/block friction) -- even a clean internal mechanism may not translate into a
  compelling external story. Revisit connecting the eventual mechanism to `research-direction.md`'s
  existing Type-1 (structural separation) / Type-2 (connected-but-hostile) framing -- discussed as a
  way to give the vcr-dependence a theoretically-grounded name instead of a bespoke-parameter one,
  but not yet attempted.
- All grid/interaction data is n=15 screens; the interaction shape (especially the p_u=0.15/vcr=0.3
  cell, the largest effect and best evidence for genuine interaction) has NOT been confirmed at
  n=30. Do this before treating the interaction shape as settled, not after.
- Only ONE placebo (P_silent) has been checked against the interaction shape; E_silent has not
  (deliberately skipped as an uninformative placebo due to its much larger, dominant main effect --
  reconsider if a cleaner E_silent-specific comparison becomes useful).
- No formal statistical interaction test (e.g. 2-way ANOVA on the interaction term) has been run --
  only qualitative/visual shape-reading of the 4x4 grid so far.
- **This project has real prior history of a similar false claim from a measurement bug** (commit
  684d6fc/e07e214: an earlier "extreme-camp activation" claim was inflated by a `postShare_b *
  (originalPostCount+repostCount)` mixing error, caught via cross-pathway + split-seed-block checks).
  Apply the same two checks (independent-pathway cross-validation, split-seed-block direction-flip
  check -- both already done once this session for the non-interaction-based claim, see the
  "independent measurement-pathway audit" entry above) to any NEW result from the mechanism work
  before trusting it.

**Deadline**: CN2026 submission is **2026-09-02** (~4 weeks from today, 2026-08-04).

**Where things live**: all scripts in `scripts/lmp_hubtier_*.py`; all result data under
`results/2026-08-04_lmp_hubtier_*/` (not committed, per project convention -- regenerable from seeds/
params, see each script's docstring); this file is the single source of truth for the day's decision
history -- read chronologically from the "2026-08-04" entries onward for full context, or just this
HANDOFF section to resume quickly.

---

## 2026-08-06 -- feed-composition/structure instrumentation, terminology corrections, disk cleanup,
## Stage 1 diagnostic run launched

Picking up the mechanism thread from the 2026-08-04 HANDOFF above.

### Terminology corrections (shared with user before proceeding)

Two imprecisions caught and corrected in how the live hypothesis was being described:
1. `vocal_comfort_radius` (vcr) is NOT "conformity" -- conformity implies adjusting one's own stated
   opinion toward the group, which is `bc`'s job (the assimilation/tolerance threshold), a DIFFERENT
   parameter not implicated in the `p_u x vcr` interaction. `vcr` is specifically an
   activation/expression threshold -- whether an agent feels safe enough to POST at all, independent
   of whether its opinion moves. Kept `bc` and `vcr` as distinct vocabulary going forward.
2. `p_u` and `vcr` are individual agent-level BEHAVIORAL PARAMETERS (swept inputs), not measured
   NETWORK PROPERTIES (which are outputs/diagnostics like `opinionAssortativity`,
   `crossCuttingFraction`, degree distribution). The far-extreme effect depends on two
   disconnection/expression decision-rule parameters which, via their effect on who unfollows whom
   and who feels safe posting, reshape the EMERGENT network structure the extreme camp sits in --
   "parameter" and "emergent structural property" are being kept as distinct terms.

Also reconfirmed for the record: the `p_u x vcr` interaction is a WORKING HYPOTHESIS, not a settled
finding (n=15 seeds max so far, one placebo checked, no formal interaction test run) -- see the
HANDOFF above for the full caveat list, unchanged by today's work.

### New instrumentation (Java, additive/non-breaking, same pattern as `avgComfortRate`)

Three additions, all read-only diagnostics with no effect on simulation dynamics:

1. **`Agent.hubTier`** (`src/agent/Agent.java`): an int label, -1 for non-hub agents, frozen ONCE at
   pin time (in `OpinionDynamics`' `pinModerateIds`/`pinOpinionIds` setup loop) from
   `getOpinionClass()`'s 5-bin classification of the pin target value (bin 2 = Moderate). Deliberately
   a frozen snapshot, not re-derived from live opinion later, because pinned hubs in the current L/M/P
   design are NOT `stubbornness=1` (user's 2026-08-02 decision, see earlier in this file) -- their
   opinion can drift after t=0, so a live re-classification could silently relabel a hub mid-run.

2. **Feed composition by author class** (`StepStats`/`AdminOptim.AdminFeedback`/
   `OpinionDynamics.buildMetricsRow`): extends the existing `feedForYouCountMean_i`-style
   reader-camp-indexed metrics (i = reader's 5-bin opinion class) with:
   - `feedModCountMean_i` / `feedHubCountMean_i` -- mean feed posts per reader-of-camp-i authored by
     the pinned Moderate hub specifically / by any pinned hub tier (the latter isolates a pure
     crowding-out signal: M's own content, opinion~0, is far outside an extreme reader's vcr in every
     grid cell tested, so M's effect on that reader's comfort more likely runs through "who fills the
     feed slots M's silencing frees up" than "M's content itself feels comfortable").
   - `feedAuthorClass{0..4}CountMean_{0..4}` (25 columns) -- full reader-camp x author-camp matrix,
     ALL authors (hub + organic) by LIVE opinion class, directly answering the user's "ratio of each
     opinion class's post in the feed, control vs M_silent" ask.

3. **Per-opinion-class echo-chamber structure** (`Analysis.computeEchoChamberByClass`,
   `Writer.writeEchoChamberByClass`, wired into the existing 5000-step checkpoint block): follow-graph
   only (not repost/interaction graph -- user's choice), periodic (user's choice, matches the existing
   Gephi-export cadence). Restricts to the graph's largest connected component (BFS, undirected
   reachability) and population agents (excludes pinned hubs, same convention as
   `opinionAssortativity`), then for each opinion-class bin reports the induced subgraph's node count,
   directed-edge density, STANDARD undirected local clustering coefficient (`2*links/(k*(k-1))`) --
   deliberately NOT reusing `computeClusteringCoefficients`'s legacy directed-ordered-pair convention,
   since this is a fresh cohesion metric), and triangle count. Written to
   `degrees/echo_chamber_by_class_{step}.csv`.

All three compiled clean, existing unit tests pass unchanged (one test-only NPE surfaced --
`ModelTests.testChronoRootDedup` used a sparse `Agent[]` that only populated the reader's slot; the
new author-lookup in `AdminFeedback` now touches every post's author, so the test's `agentSet` was
extended to match what production always guarantees, a fully-populated array -- not a production bug).
Smoke-tested at n=200/steps=5000: `echo_chamber_by_class` node counts partition the population exactly
(17+50+55+55+17=194 of 194 non-hub agents), all values in sane ranges, `feedModCountMean <=
feedHubCountMean` holds everywhere as it must.

### Disk cleanup

`results/` had grown to 146GB. Cross-checked each subdirectory's findings against this report before
deleting anything (CLAUDE.md convention: safe once conclusions are written up, since nothing under
`results/` is version-controlled and everything regenerates from seed+params). Confirmed all of
`lmp_hubtier_oat_battery` (34G), `lmp_hubtier_pu_vcr_grid` (30G), `lmp_hubtier_pu_vcr_finegrain` (23G),
`bcrecovery_conduit_retest` (22G, via the bc_recovery-OAT entry above), `lmp_hubtier_specificity_check`
(16G), `lmp_hubtier_pilot` (10G), and `lmp_hubtier_robustness` (9.9G) are captured in this file --
deleted all seven (~145GB freed). Left `2026-08-03_bc_floor_recovery_screen` (849M) untouched -- the
2026-08-03 entry above explicitly flags it as kept for pending dashboard inspection, not yet decided.
Preserved the tiny (1.9M) `_class_selection_hk` t0-snapshot subfolder (all 15 seeds, needed by every
`lmp_hubtier_*`/`lmp_feedmech_*` script's `derive_groups()` for deterministic hub-tier pinning) by
moving it out to a stable shared location, `results/_shared/class_selection_hk/`, before deleting its
old parent directory.

### Stage 1 diagnostic run launched

`scripts/lmp_feedmech_stage1.py` (`nohup`+`disown`, log `logs/lmp_feedmech_stage1_stdout.log`,
results under `results/2026-08-06_lmp_feedmech_stage1/`): reuses the same 8 diagnostic cells as the
specificity check (`p_u` in {0.05, 0.15} x `vcr` in {0.1, 0.15, 0.2, 0.3}), control vs M_silent only
(no placebo arm -- specificity already confirmed, this pass is about mechanism). DIAGNOSTIC scope:
only the first 5 of the original 15-seed block (8900000-8900004), a genuine subset so it extends
cleanly to the full 15 without discarding anything if the pattern looks promising. 80 runs total
(8 cells x 2 arms x 5 seeds), n=1000/steps=40000, ~20 concurrent (this project's established
`max_workers`), est. ~7GB / ~15-25 min wall clock. Rerun from scratch was required even though
control/M_silent data existed for these cells before today -- the new feed/structure columns don't
exist in any prior output.

**Analysis plan once complete**: trailing-2000-step mean of the feed-composition columns +
final-checkpoint (step=40000) echo-chamber stats for classes 0/4 (far-extreme), control vs M_silent,
compared cell-by-cell against the already-known `avgComfortRate` d-values recalled from the
specificity check (not recomputed -- that raw data was part of today's cleanup):
`p_u=0.05: [-0.495, +0.608, +0.882, +0.791]`, `p_u=0.15: [-0.743, -0.517, +0.390, +1.778]` (vcr order:
0.1, 0.15, 0.2, 0.3). If feed composition and/or structural cohesion tracks this sign-crossover
pattern, extend to the remaining 10 seeds (Stage 2) for statistical parity with the existing
posting-rate/comfort-rate numbers. If not, the feed-composition mediator hypothesis needs rethinking
before further spend.

**Next step for whoever resumes this**: check `logs/lmp_feedmech_stage1_stdout.log` for completion,
then read the printed per-cell report (script prints control/M_silent/diff for every feed-composition
and echo-chamber column, plus the recalled comfort-rate d's for visual cross-reference -- no
statistical test is run yet at n=5, this is a qualitative shape-check).

### Stage 1 results (first pass) and two follow-ups

Stage 1 completed (80/80 runs). Read the full per-cell report (`logs/lmp_feedmech_stage1_stdout.log`).
Findings, in the same "far-extreme camp" = bins 0/4, "same-side pre-extreme" = class 3 for bin-4
readers / class 1 for bin-0 readers vocabulary as above:

1. **Robust across all 8 cells**: M_silent reallocates feed capacity toward same-side pre-extreme
   content specifically (not toward more own-camp echo) -- `feedAuthorClass3CountMean_4` and
   `feedAuthorClass1CountMean_0` both rise in every cell, while Moderate-authored content
   (`feedAuthorClass2CountMean`) drops as expected. Bigger at p_u=0.15 than p_u=0.05 (2-5x at matched
   vcr) -- consistent with p_u governing the SUPPLY-side reallocation.
2. **Does not by itself explain the `avgComfortRate` sign crossover**: the reallocation's magnitude
   doesn't track where comfort flips sign (e.g. it's LARGEST at p_u=0.15/vcr=0.1, exactly where
   comfort is most negative) -- raw volume of pre-extreme content reaching the feed isn't the
   mediator; what fraction of it falls inside each reader's comfort window might be (not measured in
   this first pass, only raw counts).
3. **Unexpected, likely-important side finding**: the far-extreme camp's own POPULATION SIZE
   (`nodeCount` in `echo_chamber_by_class`, i.e. how many agents' live opinion lands in bins 0/4 at
   all) is larger under M_silent in every single cell (+5 to +17.6 agents out of ~90-115). Structural
   cohesion (density/clustering) inside that camp mostly drops slightly (mechanical consequence of a
   bigger, more diffuse camp) but doesn't track the p_u x vcr crossover shape either -- looks like a
   robust side-effect of M's absence, not the mediator.

**User's question (2026-08-06): does finding 3 conflict with "moderate activates extreme camp"?**
Not necessarily -- population SIZE (a headcount) and per-capita posting/comfort RATE (the established
`avgComfortRate`/posting-rate `d` metric) are different quantities that can move independently. BUT: the
established per-capita metric divides each arm's post count by THAT ARM'S OWN population count, and
since M_silent's bin-0/4 population is now known to be systematically larger in every cell, part of the
existing "moderate activates extreme camp at narrow vcr" signal (the negative d's) could be a
mechanical denominator-inflation artifact (a bigger, more diluted M_silent camp mechanically producing
a lower per-capita rate) rather than genuine per-individual behavior change -- structurally the same
kind of risk as the project's prior `postShare_b * (originalPostCount+repostCount)` measurement bug
(commit 684d6fc). **Not yet resolved** -- a fixed-control-denominator recomputation of posting-rate d
was added to the Stage 1 script (see below) specifically to check whether the sign survives a fair
per-capita comparison.

### Instrumentation round 2: within-comfort content-class fraction + fixed-denominator check

Added `StepStats.feedClassComfortCountSum` (`[readerClass][authorClass]`, the subset of
`feedAuthorClassCountSum` that also satisfies the reader's own `vocal_comfort_radius` check) --
exposed as `feedComfortClass{0..4}CountMean_{0..4}` in `results.csv`. Required changing
`Agent.updateMyself()`'s signature to accept `Agent[] agentSet` and `StepStats stepStats` (the only
place a reader's own vcr/opinion and each feed post's author are both in scope at once), since the
comfort check happens reader-side in `Agent`, not admin-side in `AdminOptim.AdminFeedback` where the
existing `feedAuthorClassCountSum` is tallied -- both tallies use the identical
`agentSet[post.getPostUserId()].getOpinionClass()` lookup in the same agent's turn (feed build then
feed read happen back-to-back, no other agent's turn in between), so the ratio
`feedComfortClass/feedAuthorClass` is on a self-consistent basis. Updated the one production call site
(`OpinionDynamics.java`) and two test call sites (`ModelTests.java`, which needed a fully-populated
`agentSet` for the same reason `testChronoRootDedup` did earlier today). Compiled clean, same 3
pre-existing test failures (unrelated), smoke-tested: `feedComfortClass <= feedAuthorClass` holds in
every reader/author-class cell, ratios in [0,1] and vary sensibly by class-pair distance.

`scripts/lmp_feedmech_stage1.py` extended (not a new script -- same 8 cells/5 seeds/design) with:
- the within-comfort ratio for the two same-side pre-extreme cells (reader=0/author=1,
  reader=4/author=3), pooled-count ratio rather than per-seed-mean-of-ratios (avoids small-n ratio
  instability).
- the fixed-control-denominator posting-rate `d` recomputation described above.

Old Stage 1 run directories (11GB, produced by the pre-round-2 binary, missing the new columns)
deleted and the full 80-run batch relaunched from scratch (`nohup`+`disown`, log
`logs/lmp_feedmech_stage1_v2_stdout.log`) -- unavoidable, new columns don't exist in old output.

**Next step for whoever resumes this**: read `logs/lmp_feedmech_stage1_v2_stdout.log` once complete;
in particular check whether `d_fixed` flips sign relative to `d_own` at the narrow-vcr cells
(p_u=0.05/vcr=0.1, p_u=0.15/vcr=0.1&0.15) where the ESTABLISHED metric currently reads as "moderate
activates extreme camp" -- if it flips, that claim needs to be retracted/reframed as a measurement
artifact rather than a real effect, which would also simplify the mechanism story (one less thing to
explain). Also check whether the within-comfort ratio for same-side pre-extreme content now tracks the
p_u x vcr crossover shape better than raw feed-composition counts did.

### Instrumentation round 3: population denominator was ALSO stale (user caught this)

User question (2026-08-06, right after v2 finished): is the opinion-class population count used as
the per-capita denominator actually kept live, given both individual opinions and camp membership
drift continuously?

Checked precisely. Two different answers for two different layers:
- **Java model itself: yes, always live.** `Agent.opinionClass` is refreshed via `setOpinionClass()`
  unconditionally at the end of every `updateMyself()` (after that step's FJ update + clipping,
  regardless of whether opinion actually moved), plus at construction and on every external
  `setOpinion()` call. Never more than the current step stale.
- **The Python analysis (both the original specificity check AND today's `lmp_feedmech_stage1.py`):
  no, this was a real bug.** `pop_counts_nonhub()` read `agent_snapshot_final.csv`, a snapshot written
  ONCE at the very last step (40000), and used that single number as the denominator for a rate summed
  over the TRAILING 2000-STEP WINDOW (38000-40000). Given finding 3 above (far-extreme population still
  growing under M_silent), this end-of-window snapshot doesn't represent the population averaged
  across that window, and could differentially bias control vs M_silent if their growth trajectories
  inside the window differ -- compounds (doesn't just duplicate) the earlier denominator-inflation
  concern.

**Fix**: `StepStats.feedClassAgentCount[cls]` (population count per opinion class) was already being
recomputed every single step in `AdminOptim.AdminFeedback()`, just never exposed as its own column --
only used internally to normalize the feed-composition metrics. Added one line
(`row.put("popCountByClass_" + i, cnt)`) to `OpinionDynamics.buildMetricsRow` to expose it. Smoke-
tested: a single step's count is noisy by design (e.g. `[2,2,8,2,4]` out of an expected ~194 non-hub
population at `access_prob=0.1` -- each agent is only processed ~10% of steps, matching the token
exactly), but a 2000-step trailing MEAN averages this out and, since `access_prob` is fixed and
identical across control/M_silent, doesn't bias the arm comparison.

`lmp_feedmech_stage1.py` updated: `pop_counts_nonhub` split into `pop_counts_nonhub_final` (old,
kept only for side-by-side comparison) and `pop_counts_nonhub_windowed` (new, trailing-window mean of
`popCountByClass_i`, time-matched to the same window as the posting-count numerator). The
posting-rate-d report now prints THREE variants side by side: final-snapshot-n (OLD), trailing-
window-mean-n (NEW, time-matched), and fixed-control-n (windowed) -- so both denominator problems
(stale snapshot, and arm-specific population size) can be inspected independently.

Old v2 run directories (11GB, missing `popCountByClass_i`) deleted, full 80-run batch relaunched a
third time (`nohup`+`disown`, log `logs/lmp_feedmech_stage1_v3_stdout.log`).

**Next step**: read `logs/lmp_feedmech_stage1_v3_stdout.log` once complete. This is (hopefully) the
last rerun needed for Stage 1 -- compare all three posting-rate-d variants at the narrow-vcr cells, and
the within-comfort pre-extreme ratio, against the crossover shape from the original (now-superseded)
specificity-check numbers.

### Stage 1 v3 results, and a reframe: PE<->E homophily/heterophily gate

v3 completed (80/80). Denominator-artifact question: the sign of "moderate activates extreme camp at
narrow vcr" never flips across final-snapshot-n vs trailing-window-mean-n vs fixed-control-n, so the
qualitative pattern is real -- but at p_u=0.15/vcr=0.15 the effect size collapses from d=-0.703
(own-denominator) to d=-0.139 (fixed-denominator), so exact magnitudes from the old numbers shouldn't
be trusted, only the sign pattern.

The comfort-ratio decomposition (feedComfortClass/feedAuthorClass) was the key result: the FRACTION of
same-side pre-extreme content that falls inside a far-extreme reader's own comfort window is LOWER
under M_silent in all 16 reader x cell measurements (no exceptions) -- e.g. 0.865->0.420 at
p_u=0.15/vcr=0.2. Combined with the comfort-GATED count (ratio x volume, computed by hand from the
printed columns): the net "additional comfortable content" (same-side pre-extreme + own-echo) swings
from negative to positive as vcr widens, in both p_u rows -- a real crossover, roughly matching the
established `avgComfortRate` crossover location (exact location doesn't line up cell-by-cell, likely
n=5 noise or a genuine partial gap, not yet resolved).

**User's reframe (2026-08-06)**: the vcr-dependence is really about whether PE and E should be treated
as HOMOPHILIC (same in-group) or HETEROPHILIC (different groups) to each other -- vcr literally IS
that boundary (it's defined as "how much nearby agreement is needed to feel safe to speak," i.e. the
threshold for treating incoming content as in-group). Chain: PE activates under M-silent (ALREADY
ESTABLISHED, robust 10/10 OAT-battery finding, not from today) -> this activation transmits to E only
if E treats PE as homophilic (vcr wide) -> E activates too; if heterophilic (vcr narrow), it doesn't
transmit. This fits the comfort-ratio data precisely (ratio ~0-15% at vcr=0.1 = heterophilic
classification, ~90-98% at vcr=0.3 = homophilic classification) and is a cleaner single-mechanism
explanation than the earlier two-separate-channels framing (posting-suppression vs crowding-out) --
those are just downstream symptoms of the same homophily gate being open or shut.

**Extending the reframe to p_u** (assistant's proposal, user agreed to test it): vcr is a PERCEPTUAL
homophily gate (given exposure, does content register as comfortable). p_u can't be that (it's
structural, not a comfort threshold) -- but could be a STRUCTURAL homophily gate instead: whether PE
remains reachable in E's follow-network at all, given p_u governs unfollow-driven pruning speed and M's
established bridging role (lower opinionAssortativity/higher crossCuttingFraction when present)
counteracts that pruning. Prediction: the control-vs-M_silent gap in PE<->E follow-graph connectivity
should be bigger at p_u=0.15 than p_u=0.05, if this holds.

### PE<->E structural connectivity check launched

`scripts/lmp_feedmech_stage1_gexf.py` (imports shared helpers from `lmp_feedmech_stage1.py` rather than
duplicating them) -- same 8 cells/5 seeds/control+M_silent design, but with `log_gexf=true` added (the
ONLY new token; GraphVisualize.java already embeds `opinionClass`/`target` as GEXF node attributes, so
no new Java code was needed, confirmed by inspecting an actual GEXF file's schema before writing the
parser). Computes directed follow-edge density from E-class members to same-side PE-class members
(source follows target, non-hub only) at the final checkpoint, control vs M_silent, across all 8 cells.
Output to a NEW subdir (`2026-08-06_lmp_feedmech_stage1_gexf`) so Stage 1 v3's already-analyzed data
isn't touched. Smoke-tested end-to-end (small run, GEXF parse, density computation) before the full
launch -- sane, non-degenerate values. Launched `nohup`+`disown`, log
`logs/lmp_feedmech_stage1_gexf_stdout.log`.

**Next step**: read the log once complete; check whether the p_u=0.15 row shows a bigger
control-vs-M_silent connectivity gap than the p_u=0.05 row (both E-/PE- and E+/PE+ sides) -- if so, the
structural-homophily-gate hypothesis for p_u is supported; if the gap is similar or smaller at
p_u=0.15, the hypothesis needs revision or dropping.

### PE<->E connectivity result: hypothesis supported

Completed (80/80). p_u=0.15's control-vs-M_silent connectivity gap averages ~3x larger than p_u=0.05's
(0.000626 vs 0.000194 across the 8 E-/PE- and E+/PE+ measurements), and is consistent in sign (8/8
positive at p_u=0.15, i.e. M_silent always shows MORE PE<->E connectivity than control; 7/8 positive at
p_u=0.05, with one sign flip and smaller magnitudes throughout). Supports the structural-homophily-gate
reading of p_u: at high p_u, silencing M's bridging role measurably reconnects PE to E's follow-network
more than at low p_u.

**Resulting two-level mechanism** (user's framing, 2026-08-06): this positions the paper's contribution
as a connection between a NETWORK layer and a PSYCHOLOGICAL layer, both gating the same underlying
pathway (PE activates when M is silenced -- established, prior work -- and that activation reaches E
only if both gates are open):
- p_u = STRUCTURAL homophily gate (is PE reachable in E's follow-network at all) -- shown above.
- vcr = PERCEPTUAL homophily gate (does reached PE content register as in-group/comfortable to E) --
  shown via the comfort-ratio decomposition earlier.

### Stage 2 launched: full 15 seeds + population-only follow/unfollow counts

User (2026-08-06): before trusting the p_u story, wants absolute follow/unfollow ACTION COUNTS analyzed
too (not just the endpoint connectivity snapshot), since the p_u finding implies network-connection
dynamism itself matters, not just where things land. Also requested population-only gating first --
the existing `follow`/`unfollow` metrics-row columns count ALL agents' actions including pinned hubs
(no population guard on `agent.follow()`/`agent.unfollow()`'s call sites), unlike `unfollowCount`
(discovered already population-gated, sharing the same `if (population)` block as blockCount/
evictionCount) which had no `follow` counterpart. Added `StepStats.followCount`, incremented alongside
the existing `unfollowCount` in the same population-gated block, exposed as a `followCount` column next
to `unfollowCount`. Compiled clean, same 3 pre-existing test failures, smoke-tested (population counts
<= all-agents counts as required, e.g. unfollow 869 population vs 900 all-agents in one test run --
hub-attributable unfollow actions are a real, non-trivial share, confirming the gating was worth doing
before trusting a raw aggregate).

`lmp_feedmech_stage1.py` extended to the full 15-seed block (8900000-8900014) -- the first 5 reuse
Stage 1 v3's already-completed runs via the existing `is_done()` check (confirmed working: "reusing
existing" printed for all pre-existing seed/cell/arm combos), so only 160 new runs needed (10 new seeds
x 8 cells x 2 arms), not 240. Also added a `followCount`/`unfollowCount` trailing-window-sum report
(control vs M_silent, per cell) to the same script's `report_cell()`. No GEXF this round (not
re-confirming the PE<->E connectivity finding at n=15 unless asked -- it already got a clean, consistent
n=5 signal). Launched `nohup`+`disown`, log `logs/lmp_feedmech_stage1_stage2_stdout.log`.

### Two-level homophily-gate mechanism: VALIDATED (2026-08-06, `scripts/lmp_feedmech_validate.py`)

Full statistical validation battery, per the project's own handoff-mandated checks (independent-pathway
cross-validation, split-seed-block direction-flip check -- the same checks that caught the prior
`postShare_b` measurement-bug false claim, commit 684d6fc), plus formal significance testing (nothing
run earlier today had an actual test, only means/diffs). n=15 GEXF connectivity data used (rerun from
the earlier n=5 diagnostic once seeds 8900005-8900014 finished).

- **Check 1 (p_u structural gate)**: is the PE<->E connectivity gap (M_silent-control) bigger at
  p_u=0.15 than p_u=0.05? YES, strongly -- E-/PE-: t=+6.04, p<0.0001, d=+0.78, n=60; E+/PE+: t=+5.03,
  p<0.0001, d=+0.65, n=60.
- **Check 2 (vcr perceptual gate)**: is the comfort ratio lower under M_silent, per seed (paired
  t-test, not the pooled-count ratio used in earlier reports)? Direction is universal, 16/16 cells;
  10/16 reach p<0.05, concentrated exactly where predicted -- all 8 of p_u=0.15's cells significant
  (several p<0.005), the 6 non-significant cells are p_u=0.05 at narrow/mid vcr where the ratio sits
  near floor in both arms (less room to detect a proportional difference, not evidence of no effect).
- **Check 3 (split-seed-block)**: splitting the 15 seeds into two independent halves, all four effect
  estimates (GEXF E-/PE-, E+/PE+, comfort-ratio pooled) keep the same sign and comparable magnitude in
  both halves. No flip.
- **Check 4 (independent-pathway cross-check)**: the GEXF-derived connectivity-gap ranking and the
  feed-composition-volume-gap ranking (separate measurement pathways -- one from the follow graph, one
  from `StepStats`/`AdminOptim`) correlate at Spearman rho=+0.833, p=0.0102 across the 8 cells.

**Verdict: the two-level homophily-gate mechanism (p_u = structural gate on whether PE is reachable in
E's follow-network; vcr = perceptual gate on whether reached PE content registers as in-group/
comfortable) is validated, not just a well-fitting story.** Significant on both gates, robust to
seed-splitting, cross-confirmed by an independent measurement pathway. This satisfies the validation
bar for writing up as a real finding, not a provisional pattern.

Script note: the first version of `lmp_feedmech_validate.py` re-read each seed's full 40000-row
`results.csv` from scratch on every call (hundreds of redundant reads) -- 40+ minutes and still not
done. Rewritten with per-(seed,subdir) caching (read once, reuse across all cells/checks); the full
battery then completed in under a minute.

**Next step**: write up the mechanism section using this validated result. The established backbone
(own-camp reinforcement, pre-extreme suppression, reduced structural separation) plus this two-level
gate finding together give a complete, statistically-grounded mechanistic account of the moderate hub's
effect on the far-extreme camp, ready for the paper draft.

---

**Bug caught mid-run**: the reuse-the-first-5-seeds optimization (`is_done()` detecting Stage 1 v3's
already-completed runs) doesn't check SCHEMA, only step-completion -- v3's data predates today's
`followCount` addition (`unfollowCount` existed, `followCount` didn't), so the analysis crashed with
`KeyError: 'followCount'` partway through, after all 240 runs' simulation had already completed.
Deleted the full 34GB `2026-08-06_lmp_feedmech_stage1/` and relaunched all 15 seeds fresh (no reuse this
time) rather than patch around the schema mismatch -- guarantees every one of the 240 runs has
consistent instrumentation. Lesson for future reuse-via-is_done() optimizations: step-completion is not
the same as schema-completeness when instrumentation changed since the reused data was generated.

### Stage 2 v2 complete; terminology rename: "pre-extreme" -> "near-extreme"

Stage 2 v2 (full 15 seeds, `followCount` schema fixed) completed clean
(`logs/lmp_feedmech_stage1_stage2_v2_stdout.log`). Fixed-control-denominator posting-rate `d`
crossover holds at full n=15, both `p_u` rows:
- `p_u=0.05`: vcr=0.1 d=-0.770, vcr=0.15 d=+0.047, vcr=0.2 d=+0.572, vcr=0.3 d=+0.547
- `p_u=0.15`: vcr=0.1 d=-1.049, vcr=0.15 d=-0.467, vcr=0.2 d=+0.267, vcr=0.3 d=+1.180

Same sign pattern as the n=5 pilot, and the `p_u=0.15` row still shows a wider negative-to-positive
swing than `p_u=0.05`, consistent with the structural-homophily-gate reading -- the denominator-artifact
concern from the 2026-08-06 entries above does not overturn the crossover shape once the fair per-capita
comparison is used.

**User (2026-08-06): "pre-extreme" renamed to "near-extreme"** going forward -- "pre-extreme" reads as
implying a temporal/developmental step toward extreme, which isn't the intended meaning (it's a
distance-from-center bin label, bins 1/3, not a stage). All NEW writing (paper drafts, this report's
future entries) should say "near-extreme". Existing occurrences of "pre-extreme" above (52 in this file)
are left as-is -- historical entries are not being retroactively edited; readers should treat
"pre-extreme" in anything dated 2026-08-06 or earlier in this file as synonymous with "near-extreme".

---

## 2026-08-07 — Independent verification pass on the two-level homophily-gate mechanism; CNA2026 draft
## abstract/intro editing

Follow-up review session (fresh context, acting as critical reviewer per this project's own CLAUDE.md
role) auditing the model logic and analysis pipeline behind the two-level homophily-gate mechanism
validated 2026-08-06. Code-level audit (`Agent.follow()`/`unfollow()`, `StepStats`/`AdminOptim` feed-
composition tallies, GEXF attribute-id matching cross-checked against an actual exported file) found no
implementation bugs. All new analysis below reuses already-completed data
(`results/2026-08-06_lmp_feedmech_stage1/`, `..._gexf/`, both still on disk) -- no new simulation runs.
New scripts: `scripts/lmp_feedmech_interaction_anova.py`, `_volume_sign_test.py`, `_comfortvol_test.py`,
`_comfortvol_test2.py`, `_distribution_check.py`, `_distribution_effectsize.py`,
`_pu_absolute_connectivity.py`, `_effect_magnitude.py`, `_temporal_sequencing.py`,
`_postprob_reconcile.py`.

**1. Formal interaction test (previously missing -- flagged in the 2026-08-04 HANDOFF as "no formal
statistical interaction test... only qualitative/visual shape-reading").** On the available 2x4 subset
of the original grid (`p_u` in {0.05, 0.15}, the 4-level `p_u` grid's raw data for 0.01/0.03 was already
deleted per project convention once written up): a balanced 2-way ANOVA on the per-seed M_silent-minus-
control posting-rate contrast gives F(3,112)=4.70, p=0.0039 for the `p_u x vcr` interaction term; a
label-permutation cross-check (20000 shuffles, distribution-free) gives p=0.032 -- weaker but still
conventionally significant. The gap between the two p-values indicates real heteroscedasticity across
cells (cell SDs range 0.018-0.036); **the permutation p=0.032 should be cited as the more defensible
number**, not the parametric one. Crossing-point analysis (linear interpolation of the sign change) finds
the `p_u=0.05` row crosses zero at `vcr~0.14` and the `p_u=0.15` row at `vcr~0.20` -- a genuine ~0.06
rightward shift, not merely a rescaled/amplified version of the same shape as initially assumed when
recalling the 2026-08-06 numbers from memory.

**2. Mechanistic decomposition via regression (comfort-gated content volume).** Regressing the per-seed
posting-rate contrast on `feedComfortClass` (volume x already-in-`vcr` gating, i.e. "comfortable content
delivered") for near-extreme-sourced content alone gives R2=0.259. Adding the OWN-CAMP comfort-gated
volume (content from the reader's own class, also crowds into feed slots freed by M's silencing) as a
second predictor roughly doubles this to **R2=0.560**, with near-identical coefficients for the two
sources (+0.142 each) -- i.e. it is the TOTAL comfortable content reaching a reader, regardless of
source, that predicts the outcome, not near-extreme-sourced content specifically. This model does NOT
reproduce the `p_u`-driven crossing-point shift found in (1): it predicts nearly identical crossing
points (~0.18) for both `p_u` rows. **Conclusion: ~56% of the effect's magnitude is explained by total
comfortable-content volume; the remaining ~44%, including specifically the crossing-point shift, is not
-- consistent with an independent structural channel (below) doing work the volume regression does not
capture.**

**3. Absolute (not just gap) structural connectivity by `p_u`.** Checked whether `p_u` alone (independent
of M's active/silent status) structurally separates near-extreme (PE) from extreme (E) camps. Under
CONTROL, absolute E<->PE follow-density is ~12-15% LOWER at `p_u=0.15` than `p_u=0.05` -- a real, if
modest, standalone separating effect of `p_u`, confirming part of a user hypothesis floated this session.
BUT under M_SILENT, the relationship REVERSES: density is 16-36% HIGHER at `p_u=0.15` than `p_u=0.05`.
`p_u`'s effect on E<->PE connectivity is therefore not a fixed, M-independent property -- it interacts
with M's active/silent state, consistent with `p_u` functioning as a gate/modulator rather than a
standalone separator. Also directly falsifies a stronger version of the same hypothesis ("`p_u` large
enough makes vcr irrelevant, camps become permanently heterophilic") -- the grid's single largest
mediator-regime effect occurs at `p_u=0.15, vcr=0.3`, the opposite of what that stronger claim predicts.

**4. Effect magnitude, contextualized.** Facilitator-regime (control > M_silent) cells average Cohen's
d=-0.972 (~-5.2% relative posting-rate change); mediator-regime (M_silent > control) cells average
d=+0.894 (~+4.1%). Both are "large" by Cohen's convention but SMALL relative to `vcr`'s own main effect
on posting rate (baseline posting rate more than doubles, 0.35->0.77, from `vcr=0.1` to `vcr=0.3`,
regardless of arm) -- the M-silencing effect is a second-order modulation on top of a much larger
`vcr` main effect, not a dominant driver on its own. `p_u=0.15` cells show ~1.5-2x larger |d| than
`p_u=0.05` cells in both regimes, consistent with (1)'s amplification finding.

**5. Distributional check (user-prompted: does the mean posting-rate/comfort-rate hide a within-camp
compositional effect, given the model explicitly targets a Buntain & Snegovaya 2025-style hyper-vocal-
minority pattern?).** Per-agent `avgComfortRate` at the final checkpoint is strongly bimodal (spikes near
0 and 1, not a smooth unimodal distribution) for the extreme camp. Proper rank-based effect sizes
(Mann-Whitney -> rank-biserial r) found: the MEDIATOR cell (`p_u=0.15, vcr=0.3`) shows a real, small
effect (p=1.1e-8, r=+0.070, frac(comfortRate>0.5) rises 69.7%->77.5%) -- the "M_silent creates more loud
posters" reading holds here. The FACILITATOR cell (`p_u=0.15, vcr=0.1`) shows an essentially NULL
distributional difference at the final snapshot (p=0.880, r=+0.002) -- flagged as a red flag structurally
resembling the project's prior `postShare_b` measurement-bug incident (two measurements that should
roughly agree, don't).

**6. Facilitator-cell puzzle reconciled via `postProb` trajectory (not a bug).** `avgComfortRate` is a
fast, ~100-step trailing signal; `postProb` (the actual posting-probability gate) is a slow leaky-
integrator that relaxes toward a comfort-set target over many steps (`Agent.java`). Tracking `postProb`
(available as a GEXF node attribute at every 5000-step checkpoint, no new instrumentation needed) for the
facilitator cell shows a clear, significant divergence EARLY in the run (Mann-Whitney p=1.7e-5 at step
5000, p=6.1e-3 at step 10000, p=0.043 at step 15000) that later loses significance by conventional
thresholds (p=0.13-0.41 from step 25000 on) even as the raw mean difference continues to grow in
magnitude (-0.008 at step 10000 -> -0.030 at step 40000) -- variance grows faster than the mean gap,
diluting a mean-based test's power. **Reading: the facilitator effect is likely real, driven by an early
comfort-signal divergence that gets "locked in" via `postProb`'s slow relaxation, persisting into the
final window even after the proximate (`avgComfortRate`) driver has largely re-converged between arms.**
Only checked for one cell so far -- not yet confirmed this pattern generalizes across the grid.

**7. Temporal-sequencing check (does the structural layer settle before the perceptual layer, as a user
hypothesis proposed?): NOT supported as a universal ordering.** Across the 8 cells, which of
(connectivity-gap, comfort-ratio-gap) reaches 80% of its own final magnitude first split roughly by `p_u`
row (structure tends to lead at `p_u=0.05`, comfort tends to lead at `p_u=0.15`) rather than following one
fixed precedence. A separate, more striking pattern: at `p_u=0.05`, the comfort-ratio-gap trajectory
starts POSITIVE (steps 5000-10000) and flips negative around step 15000-20000 before settling into the
established final-window sign; at `p_u=0.15`, no such transient reversal occurs (negative from the
start). This early-transient-reversal-present-vs-absent split by `p_u` is a new, unexplained observation,
not yet connected to (6)'s finding, and not yet checked for robustness.

**Net effect on the paper's central claim**: the two-level homophily-gate mechanism survives this
independent audit -- no implementation bugs found, and the `p_u x vcr` interaction now has a formal
(if modest, permutation p=0.032) significance test behind it for the first time. But several specific
sub-claims from the 2026-08-06 write-up need softening before submission: (a) the "structural layer
determines reachability" framing overstates a binary effect that is actually a graded, ~12-15% modulation
that also reverses sign depending on M's state; (b) the "purifies into a purer echo chamber" facilitator
mechanism is not yet supported by a clean distributional signature at the final snapshot and required a
secondary, single-cell trajectory analysis to reconcile; (c) the comfort-gated-volume mediator explains
the effect's magnitude reasonably well (R2=0.56) but not the `p_u`-driven threshold shift, which remains
open; (d) whichever of the mediator/facilitator regimes is chosen as the paper's headline should account
for `vcr`'s complete lack of empirical calibration -- the facilitator regime is reachable at the
comparatively more plausible `vcr=0.1`, while the largest mediator effect requires `vcr=0.3`, an
uncalibrated and possibly unrealistic value.

**CNA2026 draft**: in parallel, iteratively revised the Abstract and Introduction of
`../latex-cna2026/CNA2026-1st.tex` (not a git repository -- no version history beyond this note) to (i)
name the two-layer mechanism explicitly in the Abstract to match the title, (ii) remove a duplicated
two-parameter explanation across two consecutive Introduction paragraphs, and (iii) soften an overclaimed
"network-reachable at all" phrase into a threshold-shift framing consistent with finding (3) above. Model/
Experimental-Design/Results sections remain TODO by explicit user request (scope for this session was
abstract/intro polish only, "見せる程度" for a professor direction-check, not full drafting).

**Open items for next session**: n=30 confirmation of the interaction (currently n=15 only); re-running
`p_u=0.01/0.03` cells to test the interaction against the full originally-explored `p_u` range (that raw
data was deleted); a formal mediation analysis linking the comfort-volume and structural-connectivity
channels to the outcome rather than the current separately-validated-correlations patchwork; checking
whether finding (6)'s postProb-reconciliation and finding (7)'s transient-reversal generalize beyond the
single cells/rows checked so far.

---

## 2026-08-07 (cont.) — Population-shape and hub-size robustness checks; decision to lead with the
## facilitator effect, not mediator

Follow-up to the independent verification pass above. User noted the current hub-tier design's size
split (10 E-/10 P-/20 M/10 P+/10 E+) was explicitly "bell-shaped, more weight toward moderate" per the
2026-08-04 design decision -- the same Gaussian-concentration assumption now worth stress-testing on
the population side too. Ran three new n=30 batches (all reusing the existing 30-seed block
9990000-9990029 and its class-selection t0 snapshots where possible; no re-run of Phase 1 needed for
the hub-size variants since follower-count ranking depends only on network topology, not hub
allocation) against the same 8-cell (`p_u` in {0.05, 0.15} x `vcr` in {0.1, 0.15, 0.2, 0.3}) grid used
throughout this investigation:

**Code change**: `Agent.java` gained `init_dist=uniform` (`intrinsicOpinion ~ U[-1,1]`), alongside the
existing `gaussian`/`empirical` options -- additive, no behavior change to existing configs. Smoke-
tested (n=200, quartile counts [49,56,54,41], confirms near-uniform).

**Batch 1 -- uniform population, original hub split (M=20, N_HUB=60)**
(`results/2026-08-07_lmp_feedmech_uniform_n30/`, `scripts/lmp_feedmech_uniform_n30.py`): interaction
ANOVA F(3,232)=2.60 p=0.053 (parametric, borderline), permutation p=0.165 (NOT significant) -- weaker
than the Gaussian n=15 result (permutation p=0.032) despite double the seeds. Crossing point still
shifts rightward with `p_u` (~0.18 at `p_u=0.05` vs ~0.26 at `p_u=0.15`, same direction as Gaussian's
~0.14/~0.20) but the `p_u=0.15` row's amplitude-amplification ratio shrinks (~1.5x vs Gaussian's ~2.1x).

**Batch 2 -- uniform population, uniform hub split (M=10, N_HUB=50, 10 each of
E-/P-/M/P+/E+)** (`results/2026-08-07_lmp_feedmech_uniform_hub_n30/`,
`scripts/lmp_feedmech_uniform_hub_n30.py`): the MEDIATOR regime (M_silent > control, d>0.3) essentially
disappears -- max cell d=0.152, below the classification threshold everywhere. Interaction test
significance actually returns (ANOVA p=0.021, permutation p=0.049), driven by amplitude differences
between `p_u` rows even without a mediator/facilitator sign split. FACILITATOR regime remains robust
(mean |d|=0.849 across 5 clearly-facilitator cells).

**Batch 3 -- uniform population, M=15 dose-response midpoint (N_HUB=55)**
(`results/2026-08-07_lmp_feedmech_uniform_hubM15_n30/`,
`scripts/lmp_feedmech_uniform_hubM15_n30.py`): does NOT show a clean monotonic dose-response between
M=10/15/20. Mediator-regime presence is non-monotonic across the three M sizes (e.g. `p_u=0.15,
vcr=0.3` -- the grid's flagship mediator cell at M=20 -- goes d=+0.140 (M=10, null) -> d=-0.119 (M=15,
flips to facilitator-direction, still null) -> d=+0.558 (M=20, clear mediator)); interaction-test
significance is also non-monotonic (permutation p: 0.049 at M=10, 0.305 at M=15, 0.165 at M=20).
FACILITATOR effect, by contrast, shows a mild, roughly monotonic INCREASE with M size (mean|d|:
0.849 (M=10) -> 0.887 (M=15) -> 0.997 (M=20)).

**Consolidated cross-condition summary (all four configurations tested: Gaussian/M=20, uniform/M=20,
uniform/M=15, uniform/M=10):**

| condition | facilitator mean\|d\| | mediator mean d | interaction permutation p |
|---|---|---|---|
| Gaussian, M=20 | 0.972 | 0.894 | 0.032 (n=15) |
| uniform, M=20 | 0.997 | 0.503 | 0.165 (n=30) |
| uniform, M=15 | 0.887 | 0.699 (1 cell only) | 0.305 (n=30) |
| uniform, M=10 | 0.849 | none (max d=0.15) | 0.049 (n=30) |

**Decision (user, 2026-08-07): lead the paper with the facilitator effect, not the mediator effect.**
Rationale: the facilitator effect (control > M_silent -- an ACTIVE moderate hub, not its silencing,
drives extreme-camp activation) is robust across every population-shape/hub-size combination tested
(mean|d| 0.85-1.00 throughout) and is reachable at the more externally-plausible narrow end of `vcr`'s
uncalibrated range. The mediator effect is fragile -- present under the original Gaussian/M-heavy
design, shrinking or vanishing as the design is made more uniform, and NOT explained by a clean
dose-response in hub size. The facilitator finding is also the more counter-intuitive, narratively
stronger result (an active moderate hub *fuels* rather than dampens extreme-camp posting) -- the
regime-shift structure of the current draft is kept, but with the facilitator direction promoted to
the headline and the mediator regime reframed as a secondary, condition-dependent observation.

**CNA2026 draft**: title changed from "When Do Moderate Hubs Mediate Extreme Opinion Activation?" to
"When Do Moderate Hubs **Fuel** Extreme Opinion Activation?" (`../latex-cna2026/CNA2026-1st.tex`) to
match. Abstract/Introduction reordering to lead with the facilitator framing (currently "when treated
as one group -> mediates" is presented first, facilitator second) is flagged as the next editing task,
not yet done -- scope for today's session was the title only.

**Housekeeping**: all three new batches (Batches 1-3 above) plus the 2026-08-06 `lmp_feedmech_stage1`/
`_gexf` directories they extended (32GB + 40GB) total 253GB in `results/`. Conclusions from all of it
are captured above and in the earlier 2026-08-07 entry; per project convention, deleting all five
directories after this write-up (regenerable from seed+params if needed again).

**Open items carried to next session**: (a) Abstract/Introduction reordering to lead with facilitator;
(b) the mediator regime's non-monotonic hub-size dependence is unexplained and possibly not worth
pursuing further given the facilitator-first decision; (c) all previously-listed open items (n=30
confirmation of the ORIGINAL Gaussian grid's `p_u=0.01/0.03` cells, formal mediation analysis, Model/
Experimental-Design/Results sections of the paper) remain open.
