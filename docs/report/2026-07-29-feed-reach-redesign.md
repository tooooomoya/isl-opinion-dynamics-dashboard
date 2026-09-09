# 2026-07-29 — For-You feed redesign: directed reach, distance-decay sampling, self-reinforcement diagnostics

**Purpose of this file:** record a significant, user-initiated change to the For-You recommender
mechanism (`AdminOptim.java`, `ExperimentConfig.java`, `SimParams.java`, `Post.java`), the rationale
for each of its three parts, and — critically — what it invalidates in prior calibration/experiment
work. Extends research-direction.md §3 item 6 (the velocity-primary recommender spec), which flagged
hop direction as an unresolved caveat; this entry resolves it and supersedes the "undirected"
default described there.

## Motivation (user critique, 2026-07-29)

Two mechanisms in the For-You candidate-reach logic (`AdminOptim.computeReachable`/`withinReach`,
in place since the recommender was first implemented) were flagged as unrealistic, plus a standing
self-reinforcement risk in the velocity ranking itself:

1. **Undirected reach graph.** The h-hop BFS traversed both `followees[]` and `followers[]` from
   the reader, i.e. treated "who I follow" and "who follows me" as equivalent for discovery
   purposes. Real discovery-via-network-proximity (e.g. "people you follow reposted this") only
   flows in the follow direction *outward* from the reader — being followed by someone doesn't put
   their followees inside your algorithmic reach.
2. **Hard hop cutoff.** Binary in/out at depth `h` is a step function; a real feed's marginal
   probability of surfacing content should fall off smoothly with distance, not cliff at an
   arbitrary integer.
3. **Self-reinforcement.** Reposts drive velocity score, which drives surfacing, which drives more
   reposts — a structural feedback loop with no built-in brake beyond the fixed `VELOCITY_WINDOW`
   (100 steps) hard eviction. At minimum this needed to be *measured*, not assumed benign.

## Design decisions

### 1. Reach direction: fixed to followees-only (out-edges), not swept

`computeReachable`'s BFS now expands only through `followees[u]` ("u follows this account"),
starting from the reader. This is a straight correction, not a knob — the research-direction.md
caveat explicitly said hop direction "must be fixed," and undirected was never a considered default,
just what was implemented first. No ablation toggle was added for this; if a future need arises to
compare against the old undirected behavior, it's one line in `computeReachable`, not worth carrying
as a permanent option.

Side effect worth noting: this changes what "reachable at hop h" *means* for any hub with high
in-degree. Under the old undirected BFS, a popular hub's huge follower set was one hop from anyone
who followed it, in *either* direction of traversal — so hop-2/3 reach from an arbitrary agent could
balloon just by touching a hub as an intermediate node from the follower side. Under followees-only
BFS, a hub only expands *outward* through who *it* follows (typically small out-degree), so hub
in-degree no longer inflates other agents' reach. **This alone can change realized hop-reachable
fractions substantially** — the `research-direction.md` caveat "measure realized h-hop reachable
fraction on the final network, don't assume the range" applies with new force here.

### 2. Hard cutoff → distance-decay acceptance probability (`feedDecayMode`)

Replaced the binary `withinReach(userId, author, h)` check with `acceptProbability(userId, author,
h)`, applied as a per-candidate stochastic accept/reject while scanning the velocity-sorted
candidate list (order-preserving: higher-velocity posts are still tried first; distance only affects
whether each is *kept*). Modes, selected via `feed_decay_mode` (ExperimentConfig/CLI):

- `hard` — reproduces the exact legacy behavior (P=1 if d≤h else 0). Kept as a selectable ablation
  arm, not deleted, so existing calibrated `hop=3` runs remain directly reproducible for
  before/after comparison (litmus-test convention: knobs are kept, not silently removed).
- `exp` (**new default**) — `P(d) = exp(-λ(d-1))`, so a direct followee (d=1) is always accepted,
  each additional hop multiplies acceptance odds by `e^-λ`.
- `inverse` — `P(d) = 1/(1+λ(d-1))`, a harmonic (slower) decay.

`λ=0` degenerates every mode to "no decay" (P=1 for all reachable d), consistent with the existing
`h≤0` = "global, no cache" sentinel. **`feed_decay_lambda` default is 1.0, magnitude not calibrated
— DEFERRED**, same status as several other feed-mechanism magnitudes already flagged in
research-direction.md (`bc_inc`, `β`).

**Computation-time note (user's explicit constraint):** this costs no more than the old hard cutoff.
The BFS is unchanged in asymptotic cost — same traversal, same `h`-depth cap (still the computational
knob bounding search cost) — it now records the depth at which each node was first reached instead
of just a boolean. The only new runtime cost is one RNG draw per candidate scan when `0 < P < 1`
(skipped entirely for global/hard-in-range cases where P=1), which is negligible next to the BFS
itself.

### 3. Self-reinforcement: measured (always-on) + optional decay knob (default off)

- **Instrumentation (unconditional, no dynamics change):** `Post` now tracks `lastRepostStep`.
  `AdminOptim.pruneRecentPosts` records, for every post evicted from the candidate window that
  received ≥1 repost: its lifespan (`lastRepostStep - postedStep`) and whether it was still
  receiving reposts in the final 10% of `VELOCITY_WINDOW` at eviction ("still active at eviction" —
  i.e. cut off mid-virality rather than having organically gone quiet). Exposed as cumulative-to-date
  metrics `postLifespanMean` / `postStillActiveAtEvictionFrac` (`OpinionDynamics.buildMetricsRow`).
  **Smoke-test finding (n=200, steps=1500, alpha=0.7, hop=3):** ~60% of evicted reposted posts were
  still actively accumulating reposts when forcibly evicted — i.e. the fixed 100-step window is very
  plausibly truncating real, ongoing self-reinforcement rather than measuring a natural die-off. This
  is exactly the risk the user flagged; it is not yet resolved, only now measurable. **Needs a
  decision before the next calibration round that reads `crossRepostRate`/velocity-mediated metrics.**
- **Optional mechanism (`feed_time_decay_tau`, default 0 = off):** multiplies the velocity score by
  `exp(-age/tau)`, an explicit recency dampener independent of the existing age-rate normalization
  (which only makes the score a *rate*, not a guarantee that old-but-still-hot posts lose ground).
  Left off by default so it doesn't silently change any already-calibrated run; magnitude DEFERRED,
  to be set once the lifespan diagnostic above is looked at.

## What this invalidates

This is a structural change to the mechanism that essentially every completed bridging-tier result
in `docs/report/2026-07-21-conduit-experiment-design.md` (mega/mid/small tier, `algo_exclude`,
`remove_hub`) was measured under — those all used the undirected, hard-cutoff reach. **None of that
prior work needs to be treated as wrong**, but it is now explicitly "under the old feed mechanism";
comparisons against anything run after this change are not apples-to-apples until re-baselined. The
existing calibrated `alpha=0.7, hop=3` operating point (v15) was tuned under the old semantics too —
given the reach-direction side effect noted above (hub in-degree no longer inflating others' reach),
the realized hop-reachable fraction at `hop=3` is likely different now, so **this calibration should
be re-validated (Step 2 gate), not assumed to transfer**, before it's relied on for the Step-3 freeze.

## Dashboard follow-up (2026-07-29, same day)

Wired the two self-reinforcement metrics and a per-post ranking view into the live dashboard
(`dashboard/`), per user request. Treated as a generic mechanism diagnostic, not an estimand-specific
view — in scope under the dashboard's "model-agnostic monitoring tool" charter (any velocity-ranked
recommender has this self-reinforcement question, not just this paper's).

- **`postLifespanMean` / `postStillActiveAtEvictionFrac`** — already ordinary `results.csv` scalar
  columns (no backend change needed, per the dashboard's own extension convention), added to
  `dashboard.html`'s `DEFAULT_METRICS` so they show by default instead of requiring a manual picker
  search.
- **Top-reposted-lifespan ranking (new)** — the per-step scalars only give a mean; ranking needs
  per-post data, which didn't exist as a log stream before now. Added, mirroring the existing
  `repost_cascades.csv` / `api_repost` pattern exactly:
  - `Writer.logPostLifespan` — new buffered CSV stream `posts/post_lifespan.csv`, one row per post
    at eviction (`evictionStep,postId,author,postedStep,lastRepostStep,lifespan,receivedReposts,
    stillActiveAtEviction`). Gated by new `ExperimentConfig.logPostLifespan` (default `true`, CLI
    `log_post_lifespan`), same on-by-default convention as `logRepostCascade`. Volume is bounded
    below the repost-cascade log (one row per post that was ever reposted, not per repost event).
  - `AdminOptim` gained a `LifespanEvent(Post, stillActive)` record and `drainLifespanEvents()`;
    `OpinionDynamics` drains and logs these once per step, right after `rankByVelocity` (which is
    where `pruneRecentPosts`/`recordLifespan` actually fire).
  - `dashboard/core.py`: `SeedStore` gained a `lifespan` `CsvTail`; new `api_post_lifespan(qs)`
    returns the top-N posts by lifespan for one seed plus a mean/still-active-fraction summary
    computed independently from the raw rows (cross-checked against the `results.csv` scalars in
    testing — matched to rounding).
  - `dashboard/api.py`: new `GET /api/post_lifespan` route.
  - `dashboard/dashboard.html`: added `"lifespan"` as a 4th card to the existing `repostpair` card
    group (Agent Behavior & Attributes section, Network tab) — a stat-tile pair (mean lifespan,
    still-active fraction) + a ranking table styled identically to the existing betweenness
    top-10 table (`.bctable`), with a ⬤ marker on rows still gaining reposts at eviction.

**Verified in-browser** (not just curl): compiled clean, ran a real smoke simulation, confirmed via
`curl` that `/api/post_lifespan`'s independently-computed summary matches the `results.csv` scalar
metrics, then drove headless Chrome via the DevTools protocol to the dashboard's Network tab and
screenshotted the rendered panel — stat tiles and ranking table both populated correctly with live
data (mean lifespan 63.6, still-active-at-eviction fraction 0.50 on that smoke run, consistent with
the earlier finding above that eviction is often cutting off genuine ongoing virality).

## Status

Implemented and compiled clean (`javac`, full source tree). `test.ModelTests`: same 3 pre-existing
failures as on unmodified `main` (traced previously to stale hardcoded defaults in the test file
itself, unrelated to this change) — confirmed by running the test suite against both the pre-change
and post-change tree; no new failures. Smoke-tested via a real run (n=200, steps=1500) confirming
For-You slots still fill under `exp` decay and the new lifespan columns populate with plausible
values. **Not yet run through the Step-2 validation gate at production scale (n=1000+)** — that is
the next step before trusting any downstream metric that depends on the recommender.

## Recalibration restart (2026-07-29, same day) — scope correction + a cheap local pre-check

User's framing: the For-You rewrite means "we have to do the calibration again," and given the
model still has no left/right asymmetry mechanism, the empirical bin7 target's own asymmetry needs
explicit handling rather than being silently chased or silently ignored. Full joint recalibration is
being run by the user on another (more powerful) server; **this repo/session's job is narrower — a
cheap local check of just the new feed-mechanism parameters**, to hand that other server a starting
read instead of a blind search.

### Scope correction found while preparing this: there is currently no valid calibrated point at all

Re-checked what "the current calibration" actually is before designing anything. The HEAD
`ExperimentConfig.java` point (commit `7df0011`, informally called "current config" through last
week's bridging/secession/initial-state work) was **never confirmed** — the 20-seed confirm run on
2026-07-27 (`docs/report/2026-07-21-conduit-experiment-design.md`, "20-seed confirm of the same
point") found it fails all four gates at `n=20` (real resolving power): SF1 diverges *above* the
`[1.19,1.26]` band (1.324 at step 20000 → 1.548 at step 40000, still rising, not plateaued), Gini
0.887 vs 0.8 target, `opinionAssortativity` under its 0.6 floor at step 20000 (0.595), Q_sign_repost
short of 0.48 at both checkpoints. That entry's own conclusion: "should go back through the same
kind of joint BO search... now specifically penalizing SF1 for overshooting." That re-run never
happened — the project pivoted to mechanism-tracing bridging experiments on this same uncalibrated
point instead (the user's explicit, documented call, not an oversight, per that section's own
title). So today's restart is not "re-validate a good point under a new mechanism" — there was no
good point to begin with. This is consistent with, and reinforces, "start over."

### bin7 asymmetry — decision (user, 2026-07-29)

Empirical target `EMPIRICAL_POST_BIN_PROPORTIONS = [4328.725, 2682.863, 1503.682, 2135.798, 691.065,
1156.761, 3742.547]` (bin0 = most-negative extreme … bin6 = most-positive extreme) is not sign-
symmetric: normalized, bin0=0.267 vs bin6=0.230, a ~16% gap, and bin1/bin5 differ by more still. The
model has no mechanism that could produce a left/right difference — `conservativeBcNarrowing` (the
asymmetric-homophily fix scoped in the 2026-07-27 entry, Boutyline & Willer 2017 β≈3.25 anchor) was
only ever designed on paper; confirmed by grep to be **absent from `Agent.java`/
`ExperimentConfig.java`** — no code was written. Fitting bin7 against the raw asymmetric target would
therefore chase a gap no parameter in the search can close.

**Decision: symmetrize the fit target, keep the raw asymmetry as a reported-not-optimized
diagnostic.** `EMPIRICAL_SYM[i] = (EMPIRICAL_RAW[i] + EMPIRICAL_RAW[6-i]) / 2` for i=0,1,2, bin3
unchanged. The search chases `bin7_w1_sym` (Wasserstein distance to this folded target — "does the
model produce the W-shape and its amplitude," the closable part). `bin7_w1_raw` (distance to the
actual asymmetric target) and the raw `(bin0−bin6)` gap, model vs. empirical, are logged alongside
but not part of any loss — carried into the paper's limitations section, not hidden. Revisit only if/
when an asymmetric-homophily mechanism actually ships.

### Cheap local check (this session) — isolates the feed-mechanism effect only

Not a recalibration. `scripts/feed_redesign_calibration_check.py`: two small independent sweeps at
otherwise-HEAD-default `ExperimentConfig` values (same point as the failed 20-seed confirm above,
so directly comparable), `n=1000`, `steps=20000`, 15 seeds/arm (this project's established minimum
for SF1/bin7 to even rank, per the v16 postmortem's noise-vs-signal variance decomposition):
- **Sweep A (decay mechanism, hop fixed=3):** `feed_decay_mode` ∈ {hard, exp, inverse} ×
  `feed_decay_lambda` ∈ {0.3, 1.0, 3.0} where applicable = 7 arms. `hard` isolates the reach-
  direction fix alone (followees-only BFS) against the recorded OLD-mechanism (undirected+hard)
  numbers; `exp`/`inverse` add the new decay behavior on top.
- **Sweep B (hop sensitivity, decay fixed at the new default exp/λ=1.0):** `hop` ∈ {1,2,3,4,5}.

Reports gini, `opinionAssortativity`, `Q_sign_repost`, SF1 (`postOpinionVar/opinionVar`), bin7
(`w1_sym` + `w1_raw` + L/R gap), `bcExtremityCorrelation`, and the new self-reinforcement diagnostics
(`postLifespanMean`, `postStillActiveAtEvictionFrac`) — the latter two included because the
lifespan/eviction finding above (a live open question, not yet decided) plausibly interacts with
SF1/bin7 through who gets algorithmically visible. `results/` cleared of the prior week's fully-
documented (and now doubly-superseded) bridging/secession/initial-state runs first (~118GB freed;
those conclusions are already captured in `docs/report/2026-07-21-conduit-experiment-design.md`
through its final 2026-07-28 entries, so the raw output was disposable per this project's standing
disk policy). Launched `nohup … & disown`, log `logs/feed_redesign_check_stdout.log`, per-seed log
`docs/report/feed_redesign_calibration_check.csv`. Results to be logged here on completion, to be
handed to the user's other-server joint recalibration as a starting point, not a final answer.

### Cheap check results (2026-07-29) — assortativity structurally collapsed, everything else stable/noisy

`feed_redesign_calibration_check.csv`, 12 arms (7 decay configs @ hop=3, 5 hops @ exp/λ=1.0), n=15,
step=20000. **Headline: `opinionAssortativity` collapsed to 0.39–0.47 in every single new-mechanism
arm**, vs. the OLD-mechanism 20-seed-confirm reference of 0.595 (itself already borderline under its
0.6 floor) — a ~0.13–0.20 drop, far exceeding this metric's historical seed-noise SD (~0.01–0.02),
so mechanism-driven, not noise. Matches the reach-direction-fix prediction earlier in this doc (hub
in-degree no longer inflates others' reach → less within-cluster reinforcement). Gini unaffected
(0.87–0.89 in every arm, flat). Q_sign_repost mildly lower in most arms (0.31–0.41 vs old 0.40).
SF1 noisy as established (SD 0.21–0.36 at n=15), point estimates span 1.13–1.47, several near the
band but not resolved at this n; no arm shows v16's hard ~1.0 ceiling (mild positive, unconfirmed).
bin7 fit mediocre everywhere (w1_sym 0.51–0.66) — expected, since the SF1/bin7-specific levers
weren't touched by this check. Self-reinforcement: lifespan mean 28–42 steps, 16–22% still-active-
at-eviction. hop/decay_mode/λ showed little differentiation *within* the new mechanism — the
old-vs-new mechanism switch itself is the dominant effect on assort/Q, not fine-tuning within it.

### User correction (2026-07-29): assortativity is a soft signal, not a hard gate

"i think assort around 0.4 is not that bad, you always a bit too strict on assort, others are more
important maybe." Recorded as a standing preference (memory `feedback-assort-not-hard-gate`) —
gini/Q/SF1/bin7 are what calibration should optimize/select on; assort is reported but not a
blocking criterion at its historical 0.6 floor. Applied immediately below.

## v2: joint (crossed) BO over the four For-You params (2026-07-29)

The cheap check's two sweeps were independent 1-D probes (hop fixed while sweeping decay, decay
fixed while sweeping hop), so no combination was ever jointly evaluated, and `alpha` (feedAlgoShare,
the primary algorithmic-share knob) wasn't swept at all. `scripts/feed_redesign_v2_joint_bo.py` runs
a real joint GP-BO search over `hop` (int, 1-5), `feed_decay_mode` (categorical: hard/exp/inverse),
`feed_decay_lambda` (log-uniform, 0.1-5.0), `alpha` (0.3-1.0) — everything else fixed at HEAD
`ExperimentConfig` defaults (structural dims and bc/vocality-mechanism dims both explicitly out of
scope for this pass, deferred to the user's other-server joint recalibration). `feedTimeDecayTau`
left off (0.0) — its on/off semantics are an undecided design question, not a calibration magnitude,
so not conflated with this search.

Round loss = bin7-shape (symmetrized target) + `Q_sign_repost` only, 5 seeds/point (established
convention: these resolve cleanly at n=5). SF1 excluded from round loss (noise-dominated at n=5,
same reasoning as `app_pol_baseline_v14/v15`) — top-5 round-loss candidates re-evaluated at 15 seeds,
final pick is whichever is closest to the SF1 target midpoint (1.225). Gini excluded from the loss
(flat across every arm in the cheap check, no gradient to chase). Assort logged, not optimized, per
the correction above. 6 rounds x 6 points x 5 seeds (180 runs) + top-5 x 15 seeds (75 runs) = 255
runs, ~30-40min at 30 concurrent JVMs (112GB/32-core machine, well within the `-Xmx2g`-per-JVM
headroom this project tracks). Launched `nohup … & disown`, log
`logs/feed_redesign_v2_joint_bo_stdout.log`, evaluation log
`docs/report/feed_redesign_v2_bo_evaluations.csv`, selection log
`docs/report/feed_redesign_v2_topk_select.csv`. Results to be logged here on completion.

### v2 results (2026-07-29) — top-5 all converge to high-alpha/wide-hop/weak-decay; round_loss's own winner is a self-reinforcement artifact, not adopted

`feed_redesign_v2_topk_select.csv`, 5 candidates x 15 seeds:

| rank | hop | decay_mode | λ | alpha | SF1 | gap | bin7_sym | gini | Q | assort | lifespan_mean | still_active |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 (round_loss best) | 3 | hard | 0.105 | 0.987 | 1.444±0.288 | 0.219 | 0.499 | 0.888 | 0.386 | 0.502 | 62.4 | 0.441 |
| 1 (round_loss 2nd) | 5 | hard | 0.1 | 0.976 | 1.450±0.258 | 0.225 | 0.396 | 0.890 | 0.419 | 0.552 | 62.1 | 0.466 |
| 2 (SF1-gap best) | 4 | inverse | 0.328 | 0.966 | 1.386±0.313 | 0.161 | 0.466 | 0.890 | **0.445** | 0.519 | 63.4 | 0.471 |
| 3 (round_loss selected, alpha=1.0 exact) | 5 | hard | 0.1 | **1.0** | 1.348±0.336 | 0.123 | 0.450 | 0.879 | 0.440 | 0.542 | **101.0** | **0.924** |
| 4 | 4 | inverse | 0.326 | 0.981 | 1.548±0.197 | 0.323 | 0.488 | 0.887 | 0.401 | 0.514 | 61.2 | 0.453 |

**All 5 converge toward the same region** — alpha pinned near/at its upper bound (0.97-1.0), hop
wide (3-5), decay weak-to-off (hard, or inverse at small λ). Directionally informative for the
other-server search: within this knob set, more algorithmic reach + less decay is what improves
bin7/Q fit.

**But the script's own selection rule (closest SF1 to target) picked candidate 3, and that pick is
wrong to adopt.** Candidate 3 sits at `alpha=1.0` *exactly* (the search-box boundary) and its
`postStillActiveAtEvictionFrac=0.924` / `postLifespanMean=100.99` are wildly outside the other four
candidates' range (0.44-0.47 / 61-63) — essentially **every evicted post is still gaining reposts
when the fixed 100-step `VELOCITY_WINDOW` forcibly evicts it**, vs. roughly half for the others. At
`alpha=1.0` the chronological fallback slot count goes to zero, so nothing ever damps the velocity
feedback loop — this is the self-reinforcement runaway flagged as a live, undecided design question
earlier in this doc (`feedTimeDecayTau=0`/off, `VELOCITY_WINDOW=100` hardcoded), not genuine
calibrated behavior. Candidate 3's marginally-better SF1/Q numbers are plausibly an artifact of that
runaway (more forced, artificial repost accumulation before eviction), not a better fit. **Not
adopted.**

**Recommended candidate instead: #2** (`hop=4, decay_mode=inverse, decay_lambda=0.328,
alpha=0.966`) — 2nd-best SF1 gap (0.161), best Q (0.445), reasonable bin7 (0.466), and
self-reinforcement in the normal range (0.471, matching candidates 0/1/4) rather than the runaway
regime.

**Still not a calibrated point, even for #2** — every candidate overshoots the SF1 band (1.19-1.26)
at 1.35-1.55, consistent with the old-mechanism 20-seed confirm's overshoot problem. This feed-only
knob set (hop/decay/alpha) alone does not close that gap; it plausibly needs joint tuning with the
bc/vocality levers (`pp_relax_eta`, `bc_dec`, `bc_recovery`, `vocal_comfort_radius`, `bc_init`),
which were intentionally fixed/out-of-scope for this pass. **Consequence for the other-server joint
recalibration: deciding `feedTimeDecayTau`/`VELOCITY_WINDOW` semantics should be treated as a
prerequisite, not an afterthought** — this run demonstrates the self-reinforcement knob actively
distorts which point in `(hop, decay, alpha)` space looks best, not just a secondary robustness
check.

### Decision (user, 2026-07-29): fix alpha ≈ 0.7 for now, not a free dimension

Consistent with candidate 3's boundary-exploit finding above. `ExperimentConfig.feedAlgoShare`'s
code default is already `0.7` (unchanged) — no code edit needed; this is a scope decision for any
further search here and on the other server: treat `alpha` as fixed, not swept, until the
self-reinforcement question (`feedTimeDecayTau`/`VELOCITY_WINDOW`) is resolved.

## v3: feedTimeDecayTau grid scan (2026-07-29) — τ must be strictly positive, isolate it alone

User's read after the mechanism review above: `feedTimeDecayTau` should **never be exactly 0** —
some organic decay should always be present, not just the hard 100-step wall. Search space is
`(0, τ_max]`, not `[0, τ_max]`. Alpha and every other (structural + bc/vocality) dim will be
calibrated jointly on the user's other server ("i'm feeling the results will be not so different"
for alpha specifically) — this server's job narrows to τ alone, held against the shipped-default
"plausible model" (`alpha=0.7`, `hop=3`, `feed_decay_mode=exp`, `feed_decay_lambda=1.0`, everything
else at HEAD `ExperimentConfig` defaults), so the readout is a clean one-dimensional explanatory
curve, not another joint optimization.

`scripts/feed_redesign_v3_time_decay_tau_scan.py`: grid, not BO (a single, mechanistically-understood
dimension reads better as a curve than a loss-optimized black box). `τ ∈ {5, 10, 20, 40, 80, 160,
320, 640}`, log-spaced, bracketing `VELOCITY_WINDOW=100`: τ=5 → score decays to ~2e-9 of its age=0
value by the earliest possible eviction age (100), near-total suppression (degenerate floor); τ=640
→ `exp(-100/640)=0.86` at the eviction boundary, barely different from off (upper bound, converges
back toward the v2 pathological baseline, though capped below it since alpha is fixed at 0.7 here,
not 1.0). 8 arms x 15 seeds = 120 runs, n=1000, steps=20000. Primary outcomes:
`postLifespanMean`/`postStillActiveAtEvictionFrac` (what τ directly targets) plus gini/Q/SF1/bin7
(does fixing self-reinforcement move the calibration targets, and which way); assort logged, not
gated. Launched `nohup … & disown`, log `logs/feed_redesign_v3_tau_stdout.log`, per-seed log
`docs/report/feed_redesign_v3_tau_scan.csv`. Results to be logged here on completion.

### v3 results (2026-07-29)

| τ | gini | assort (monitor) | Q | SF1 | bin7_sym | lifespan | stillActive |
|---|---|---|---|---|---|---|---|
| 5 | 0.8925 | 0.5057 | 0.3730 | 1.2436±0.2978 | 0.5705 | 32.95 | **0.091** |
| 10 | 0.8910 | 0.4654 | 0.3512 | 1.3252±0.2772 | 0.5927 | 33.04 | 0.105 |
| 20 | 0.8867 | 0.4478 | 0.3640 | 1.3352±0.2962 | 0.5526 | 33.02 | 0.110 |
| 40 | 0.8815 | 0.4422 | 0.3568 | 1.4614±0.2964 | **0.4968** | 31.16 | 0.106 |
| 80 | 0.8759 | 0.4229 | 0.3323 | 1.3198±0.2608 | 0.5120 | 31.39 | 0.137 |
| 160 | 0.8712 | 0.4519 | 0.3420 | 1.2443±0.2890 | 0.5579 | 31.38 | 0.157 |
| 320 | 0.8709 | 0.4175 | 0.3575 | 1.3037±0.2504 | 0.6041 | 29.49 | 0.154 |
| 640 | 0.8745 | 0.3892 | 0.3164 | 1.1644±0.2476 | 0.6438 | 31.91 | **0.169** |

**`stillActiveFrac` rises monotonically with τ** (0.091 → 0.169), the one clean, low-noise signal —
exactly the mechanism prediction (more decay ⇒ posts genuinely quiet before forced eviction more
often). τ=640 (barely any decay: `exp(-100/640)=0.86` at the eviction boundary) converges back near
the earlier no-decay baseline (~0.17-0.19 at `alpha=0.7`, matching the cheap check's `hop3`/`exp_lam1.0`
arms) — confirms this is measuring the right thing, and also confirms that at `alpha=0.7` (not the
v2 pathological `alpha=1.0`) the runaway is much milder to start with: still-active tops out at 17%
here vs. 92% at `alpha=1.0`. **Alpha is the first-order lever on self-reinforcement; τ is second-order
on top of it** — consistent with the user's expectation that the other-server alpha calibration
won't move this finding much.

**gini/Q/SF1/bin7 show no clean trend in τ at n=15** (gini drifts down slightly and consistently,
0.893→0.874; everything else — assort, Q, SF1, bin7 — bounces within its own noise band, e.g. SF1
ranges 1.16-1.46 non-monotonically). Practical read: τ does not trade off meaningfully against the
calibration targets in this range — it can be set for self-reinforcement/realism reasons without
fighting the other-server joint search.

**Recommendation: τ ≈ 20-40.** Midpoint between the degenerate floor (τ=5, near-total velocity
suppression) and the near-off ceiling (τ≥320); still-active ~0.11, meaningfully below the no-decay
~0.17 without crushing virality; τ=40 also had the best point-estimate bin7 fit (0.497), though that
alone isn't strong evidence given the noise level. Carry this range into the other-server joint
recalibration as `feedTimeDecayTau`'s starting box, strictly excluding 0.

## v4: joint search re-run with alpha=0.7, tau=30 fixed (2026-07-29)

`scripts/feed_redesign_v4_joint_bo_fixed_alpha_tau.py` — same joint-BO methodology as v2 (round
loss = bin7-shape [symmetrized] + Q at 5 seeds/point, SF1 excluded from round loss, top-5
re-confirmed at 15 seeds, assort monitored not gated), but `alpha=0.7` and `feed_time_decay_tau=30`
now fixed (2026-07-29 decisions above) instead of free — only `hop`/`feed_decay_mode`/
`feed_decay_lambda` searched. Added an automatic self-reinforcement outlier check to
`run_topk_selection` (flags any top-K candidate whose `postStillActiveAtEvictionFrac` exceeds 2x the
top-K median) so a v2-style boundary-exploit artifact can't be silently selected again. 5 rounds x 6
points x 5 seeds (150) + top-5 x 15 seeds (75) = 225 runs.

**Result: no outlier flagged.** All 5 top-K candidates land at `still_active` 0.082-0.108 — a tight,
sane band, a qualitative improvement over v2's flagged 0.924 — confirming the alpha/tau fix
addressed the runaway structurally, not just moved it. All 5 also converged on `decay_mode=exp`
(v2's mix of hard/inverse is gone), a more internally coherent result once the alpha-boundary
distortion was removed. **Selected: `hop=4, feed_decay_mode=exp, feed_decay_lambda≈0.110`** —
SF1=1.310±0.348 (closest to target among the 5, still slightly above [1.19,1.26]), bin7_sym=0.559,
gini=0.893, Q=0.371, assort=0.472 (monitor).

**Still not a calibrated point** — SF1 overshoots in every one of the 5 candidates (1.31-1.46), gini
sits ~0.09 above its 0.8 target in all of them (0.888-0.893), Q stays short of 0.48 (0.31-0.38).
Confirms (again) that the feed-mechanism knobs alone (`hop`/`decay_mode`/`decay_lambda`, with
alpha/tau now fixed) cannot close these — needs the structural dims (`max_follow`/`follow_prob`/
`p_u`/`stub`) and bc/vocality levers (`pp_relax_eta`/`bc_init`/`bc_dec`/`bc_recovery`/
`vocal_comfort_radius`), all out of scope for this server's pass.

**Recommended starting box for the other-server joint recalibration:** `hop ∈ {3,4}`,
`feed_decay_mode=exp`, `feed_decay_lambda ∈ [0.1, 0.4]`, `alpha=0.7` (fixed per above, unless that
search finds reason to reopen it), `feed_time_decay_tau ∈ [20, 40]` (fixed per v3, strictly > 0).
Full logs: `docs/report/feed_redesign_v4_bo_evaluations.csv`,
`docs/report/feed_redesign_v4_topk_select.csv`. Dashboard set up at `localhost:9000`, scoped to v2's
top-5 seeds (6000000-6000074), for the user's separate visual confirmation of the v2 self-
reinforcement finding.

## v5: n=100 dose-response check re-run under the new mechanism, before the intervention battery (2026-07-29)

User's suggestion: before committing to the ~220-run ID-intervention battery outlined above, re-run
the cheaper n=100 control-only dose-response check (established methodology, see
`docs/report/2026-07-21-conduit-experiment-design.md` "n=100 control-seed re-check") fresh under
today's mechanism — that check previously caught a false positive (moderate-reach→SF1 correlation
evaporated from +0.53 at n=20 to -0.02 at n=100) and retargeted the planned Role/Adaptive design's
outcome away from SF1. Given the feed mechanism materially changed today (assortativity alone
dropped ~0.13-0.20 across the board), the correlational structure found under the old mechanism
cannot be assumed to hold, and this screen is far cheaper than the intervention battery.

`scripts/feed_redesign_v5_dose_response_n100.py`: 100 fresh control seeds (unmanipulated) at the
provisional point (v4 winner: hop=4/exp/λ≈0.11, alpha=0.7, τ=30 + current defaults). T0 predictors
(`agent_snapshot_t0.csv`, follower-mass reach): `reach_mod_all`, `mod_pop_share`, `reach_mod_top`,
`n_mod_top`, `reach_ext_top`, `n_ext_top` — same definitions as the original check. Outcomes at
5000/10000/20000 (moderate-reach correlations were found front-loaded/decaying before, so early
checkpoints matter): SF1, `crossCuttingFraction`, `opinionAssortativity`, `Q_sign_repost`,
`bimodalityCoeff`, `postShare_extreme`, `opinionVar`, `postOpinionVar`, plus **per-capita post rate
by t0 class** (extreme/pre-extreme), newly rebuilt as a reusable computation
(`postShare_i(t)·totalPosts(t)/popCount_i(t0)`, replicating Agent.java's actual 5-bin
`opinionClass` formula) since the original was ad hoc. Spearman + BH-FDR across the full table, plus
the two confound checks that mattered before (moderate/extreme reach independence, SF1
denominator-deflation). Launched `nohup … & disown`, log
`logs/feed_redesign_v5_dose_response_stdout.log`, per-seed log
`docs/report/feed_redesign_v5_dose_response.csv`. Results to be logged here on completion.

### v5 results (2026-07-29): the cleanest pre-redesign finding replicates almost quantitatively; structural channel replicates and strengthens; SF1 stays messy

n=100/100 runs succeeded. 180 (predictor x outcome x checkpoint) cells tested, 109 survive BH-FDR<0.10.

**Primary (per-capita post rate by t0 class) — replicates the 2026-07-28 "clean result" almost
unchanged:**
- `reach_mod_all → percapita_preextreme`: -0.557 (step5000), -0.540 (step10000), -0.520 (step20000),
  all q<5e-8, **non-decaying** — old-mechanism finding was -0.654/-0.621/-0.529 at the same
  checkpoints. `reach_mod_top` stronger still: -0.592/-0.602/-0.576.
- `percapita_extreme` (strict extremists) vs any moderate-reach predictor: **null throughout**
  (|rho|<0.11 in every cell), replicating the old contrast (extremists' individual behavior unmoved;
  only pre-extremes respond).
- **New follow-up check (not in the original n=100 analysis):** moderate/extreme reach are more
  anti-correlated now than before (rho=-0.4585, p=1.6e-6, vs. the old -0.335) — checked whether
  `percapita_preextreme`'s correlation survives partialling out `reach_ext_top`. It does: partial
  rho -0.514/-0.473/-0.489 (step5000/10000/20000), all p<1e-6. Not a compositional artifact of the
  two reach channels trading off against each other.

**Secondary (structural channel) — also replicates, and somewhat strengthens:**
- `reach_mod_all/top → crossCuttingFraction`: +0.49 to +0.62 (old: +0.31 to +0.51); survives the
  same partial-correlation check (0.38-0.48 controlling for `reach_ext_top`).
- `→ opinionAssortativity`: -0.53 to -0.55 (old: -0.32). `→ bimodalityCoeff`: -0.46 to -0.51 (old:
  -0.33). `reach_ext_top → opinionAssortativity` mirrors positively (+0.49 to +0.54).

**SF1 — honest caveat, not a clean replication:** `reach_mod_all → sf1` significant early
(rho=-0.341, step5000) but fades by step20000 (rho=-0.199, right at the FDR boundary) — same
front-loaded/decaying shape as before. **But the denominator-deflation check now differs from the
original finding**: `reach_mod_all → opinionVar` is significantly negative here (-0.366/-0.345/-0.325
across checkpoints), where the old mechanism found this null (+0.22 ns, "numerator moves, denominator
does not"). Under the new mechanism, part of any SF1 movement is a genuine denominator effect, not
purely numerator — state this precisely in any writeup rather than reusing the old framing.

**Conclusion: proceed with the ~220-run ID-intervention battery as planned**, with
`percapita_preextreme` and the structural triad (`crossCuttingFraction`/`opinionAssortativity`/
`bimodalityCoeff`) as primary outcomes — this screen confirms both channels are real and robust to
the mechanism change, not artifacts of the old feed mechanism. SF1 stays secondary/monitored, not a
headline target, consistent with the original n=100 check's own conclusion. Full correlation table
and per-seed data: `docs/report/feed_redesign_v5_dose_response.csv`.

## v6: follower-tier decomposition (top/mid/small/peripheral) of the dose-response check (2026-07-29)

User's question: how do small hubs / peripheral agents (not just top-tier >100-follower hubs)
correlate with polarization metrics? This was a known, previously-unresolved gap — the original
2026-07-28 dose-response work flagged "the follower-stratum decomposition (top>100 vs mid 50-100 vs
small 10-50 vs peripheral<=10) was inconclusive at n=20" and was never actually re-run at n=100
(the extension to n=100 was motivated by it but the decomposition itself wasn't repeated).

`scripts/feed_redesign_v6_tier_decomposed_n100.py`: 100 fresh control seeds (5500000-5500099, v5's
underlying runs were already cleaned up per policy so this is a clean rerun, not a reuse), same
provisional point as v5. Extends v5's predictor set (6 cols) with 16 tier-decomposed ones: reach/n
for both moderate and extreme classes across 4 tiers (top >100, mid 50-100, small 10-50, peripheral
<=10, matching `scripts/extend_control_equilibria.py`'s docstring convention) — 20 predictors total.
Same 10-outcome x 3-checkpoint panel, Spearman + BH-FDR (now across 600 cells), same confound checks.

**Result: 169/600 cells survive BH-FDR<0.10.**

- **Top-tier (>100) replicates v5 cleanly on an independent fresh seed set** (rho 0.5-0.67 on the
  structural triad and `percapita_preextreme`, same signs) — a good robustness check in its own
  right, not just a re-confirmation of the same data.
- **Small tier (10-50): real but weaker version of the same two mechanisms, not a distinct
  phenomenon.** `reach_ext_small`/`n_ext_small` -> opinionVar/bimodalityCoeff/crossCuttingFraction
  (neg.)/sf1: several survive FDR, rho ~0.22-0.32, same direction as top-tier extreme reach.
  `reach_mod_small` -> `percapita_preextreme`: -0.236 (step5000 only, marginal) — same suppression
  sign as top-tier moderate reach, weaker and not holding across all three checkpoints.
- **Mid tier (50-100): essentially null** — only one cell survives FDR at all (q=0.089, borderline).
  Striking given both top and small show signal on either side of it; consistent with the
  2026-07-28 finding that this band is structurally transitional (agents pass through quickly rather
  than settling there), so it may be too unstable a category to carry a stable correlational
  signature, not a power failure.
- **Peripheral (<=10): weak, likely compositional not structural.** A handful of
  `reach_ext_peripheral`/`n_ext_peripheral` -> opinionVar cells survive (rho ~0.30-0.32), but at
  <=10 followers "reach" is nearly equivalent to "headcount" — plausibly just re-detects "more
  extreme agents in the population -> more opinion variance," not a distinct peripheral-hub
  structural effect. Do not read as evidence peripheral agents matter the way top-tier hubs do.

**Consequence for the intervention battery**: if there's room, small-tier is the next tier worth an
actual causal check (real correlational signal, weaker than top-tier but not noise) — mid-tier is
not, given the null here converges with the independent churn/transitional-band finding from
2026-07-28. Full correlation table and per-seed data:
`docs/report/feed_redesign_v6_tier_decomposed.csv`.

## v7: windowed per-capita metric, fixing zero-inflation (2026-07-29)

User caught a real limitation: `percapita_extreme`/`percapita_preextreme` (v5/v6) used a
SINGLE-STEP snapshot of `postShare_i` at the checkpoint step only. Inspection of seed 5500004
(reach_mod_top=0.2248, the highest in the v6 sample) found `postShare_1=postShare_3=0.0000` exactly
at step 20000 -- literally zero of that step's 149 posts came from a currently pre-extreme-classified
agent, despite ~496 such agents existing. Verified directly against `results.csv`, not a bug -- but a
real noise/zero-inflation problem: `Analysis.computePostShareArray` recomputes fresh from `postCash`
every single step, and with `accessProb=0.1` gating ~90% of agents out of acting per step plus
posting being a further probabilistic gate, single-step class rates are noisy, especially late in a
run.

**User's fix**: use a trailing window (1000 steps) ending at each checkpoint, and define the rate
literally as "class's total post count over the window / class's member count / window length" —
average posts per agent per step, not a single-instant share.

`scripts/feed_redesign_v7_windowed_percapita_reanalysis.py` — a REANALYSIS, not a new sim batch:
v6's 100 result directories were still on disk, so this reprocesses their full per-step
`results.csv` logs (verified: every step is logged, 20001 rows for a 20000-step run) rather than
rerunning anything. For checkpoint T, sums `(postShare_i(t)+postShare_j(t)) *
(originalPostCount(t)+repostCount(t))` over `t in (T-1000, T]` for each class's two 5-bin indices
(pre-extreme = bins 1,3; extreme = bins 0,4), divides by the t0 population count (same denominator
convention as v5/v6 -- checked roughly stable over the run for pre-extreme/moderate, less so for
strict extremes) and by 1000.

**Result: fixed the noise, core finding unchanged.** Zero-inflation gone (3%->0% exact zeros in
`percapita_preextreme` at step20000; mean barely moved, 0.146->0.141 -- confirms it was noise, not
bias). `reach_mod_all/top -> percapita_preextreme_w` survives with essentially the same sign/shape/
magnitude as before: -0.565/-0.590/-0.595 (step5000/10000/20000) for `reach_mod_all`, all q<3e-9 --
not an artifact of the noisy metric. **New, cleaner signal the fix revealed**:
`reach_ext_top/all -> percapita_extreme_w` is now clearly positive (+0.44 to +0.54, q<1e-4 at every
checkpoint) — more extreme-hub reach correlates with higher individual posting rate among extremists
themselves, a coherent result that wasn't visible through the noisy single-step version.
`reach_mod -> percapita_extreme_w` stays mostly null (borderline only at step5000), consistent with
the established "moderate reach doesn't move extremists' own behavior" contrast.

Full re-analyzed table: `docs/report/feed_redesign_v7_windowed_percapita.csv`. This windowed
definition should be the standard for any future per-capita-by-class metric in this line of work,
not the single-step version.

## Verification (2026-07-30): follower-count → reposts-received concentration, quantified

User's request: confirm that the directed-BFS fix (§1 above) produces the intended-and-expected
side effect — low-follower agents structurally cannot accumulate many reposts, while hubs do —
and check it isn't instead a bug. Re-derived the mechanism, then measured it directly (code
inspection alone doesn't settle magnitude/severity).

**Mechanism (why this follows from §1, not a separate effect):** `computeReachable` BFS now
expands only through `followees[u]`. For reader R to have author A as a For-You candidate, some
node on R's BFS frontier must have A as a followee — i.e., the *last* edge on any accepted path is
someone's direct follow of A. So the population of readers who can ever discover A (at any hop ≤h)
is bounded by A's own in-edges (direct followers) fanned out through their followers' followers,
etc. A's follower count therefore gates A's discoverability as an *author*, symmetric to (and
structurally independent of) the already-documented effect on a hub's reach as a *reader* — §1's
"hub in-degree no longer inflates *others'* reach" was about intermediate-node inflation; this is
about the *terminal* node (the author) needing an in-edge to be reached at all. Both are downstream
of the same followees-only change, not two different bugs.

**Verified empirically**, one fresh run (seed 9999001, n=1000, steps=20000, v4-recommended point:
hop=4/exp/λ=0.110/α=0.7/τ=30, otherwise HEAD defaults; not kept — deleted after analysis per disk
policy, conclusions captured here):
- `repost_cascades.csv` (author, one row/repost event) joined against `agent_snapshot_t0.csv`
  (`followerCount`): **Spearman ρ(followerCount, repostsReceived) = 0.763** (p≈2e-191, n=1000).
- Tier means (matching the tier bands already used in v6): top >100 followers (2.9% of pop.) mean
  83k reposts/agent; mid 50–100: 10.3k; small 10–50: 300; peripheral ≤10 (80.6% of pop.): 15.3,
  with **46% of peripheral agents receiving literally zero reposts across the full 20k-step run**.
- Repost in-degree Gini (this project's actual calibration statistic, `scripts/
  app_pol_baseline_bo_calibration.py:gini()` over `degree_result_20000.csv` inDegree) = **0.9497**,
  with **563/1000 agents (56.3%) at exactly zero repost in-degree** by step 20000 — a starker
  number than the raw event-count zero-rate above since it collapses multi-event edges to presence/
  absence.

**Read: this is the intended, expected consequence of §1, not a defect.** It is also, very
plausibly, a large part of *why* the cheap check and v2–v4 sweeps above consistently found gini
0.87–0.89 (flat, "no gradient to chase") — repost in-degree concentration this extreme would
dominate any gini reading regardless of which decay/hop/alpha arm is active, consistent with that
metric's observed insensitivity to those knobs. Not previously connected explicitly in this doc;
worth carrying into the gini discussion of the other-server joint recalibration, since a 0.95
repost-indegree Gini run standalone (outside the composite `results.csv` gini field checked in the
sweeps, definition not yet reconciled — flagged, not resolved here) is higher than this project's
gini target (~0.8) by more than the observed 0.87–0.89 was already sitting above it. **Open
question for the other-server search, not decided here:** whether structural knobs
(`max_follow`/`follow_prob`/`stub` — the follower-count *distribution* itself) are the correct lever
to pull gini down toward target, given this finding shows the feed mechanism converts modest
follower-count inequality into much sharper repost-outcome inequality.
