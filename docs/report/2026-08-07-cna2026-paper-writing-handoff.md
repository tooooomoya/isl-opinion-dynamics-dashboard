# 2026-08-07 — CNA2026 paper-writing handoff

> **Purpose of this file.** The topic shifts here from mechanism investigation
> (`docs/report/2026-08-02-delayed-moderate-conduit-pilot.md`, read that file for the full decision
> history behind every claim below) to writing `../latex-cna2026/CNA2026-1st.tex`. This file is the
> condensed, paper-writing-oriented summary — read this first when resuming; go to the 2026-08-02 file
> only when a specific number/decision needs its full derivation.

## 0. Deadline and venue facts
- **Complex Networks 2026 (CNA2026)**: submission 2026-09-02 23:59 AoE. Full paper 8–10 pages
  recommended, **12 pages max including bibliography**. Springer `svproc` format.
- Draft lives at `../latex-cna2026/CNA2026-1st.tex` (sibling repo, **not under git** — no version
  history beyond what's noted in this file and the 2026-08-02 report).

## 1. Current draft state (as of 2026-08-07)
- **Title**: "When Do Moderate Hubs Fuel Extreme Opinion Activation? A Two-Layer Homophily Mechanism in
  Adaptive Social Networks" (changed from "...Mediate..." today, to foreground the facilitator finding
  — see §2).
- **Abstract**: written, iterated several times this session (professor's proofreading pass already
  incorporated — the file now wraps Abstract/Intro in `\Blue{}` per the professor's own track-changes
  convention, plus added color macros in the preamble; don't strip these, they're the professor's, not
  ours).
- **Introduction**: written, 4 paragraphs. One open item: a commented-out placeholder
  `%[How these two layers relate to one another]` after the two-layer-mechanism paragraph — **left as a
  source-only comment by explicit user decision (2026-08-07), not filled in**. Reason: the temporal-
  precedence finding behind it (§4 below) is preliminary (single-pass, not replicated) and doesn't
  cleanly explain anything the paper currently needs explained. Revisit only if there's leftover page
  budget and appetite for one more small experiment (see §6).
- **Related Work, Model, Experimental Design, Results, Discussion, Conclusion**: all still `TODO`.
  This session's task: move Model (and ideally Related Work) out of TODO.

## 2. The headline decision (read this before writing anything)
**The paper leads with the FACILITATOR effect (moderate hub ACTIVE → boosts extreme-camp posting),
not the MEDIATOR effect (moderate hub SILENCED → boosts extreme-camp posting)**, decided 2026-08-07
after a robustness sweep across four population-shape/hub-size configurations:

| condition | facilitator mean\|d\| | mediator mean d | interaction test (permutation p) |
|---|---|---|---|
| Gaussian pop, M=20 (original design) | 0.972 | 0.894 | 0.032 (n=15) |
| Uniform pop, M=20 | 0.997 | 0.503 | 0.165 (n=30) |
| Uniform pop, M=15 | 0.887 | 0.699 (1 cell only, non-monotonic) | 0.305 (n=30) |
| Uniform pop, M=10 | 0.849 | none (max d=0.15) | 0.049 (n=30) |

- **Facilitator is robust across every configuration tested** (mean\|d\| 0.85–1.00 throughout) and is
  reachable at the more externally-plausible NARROW end of `vcr`'s range (`vcr=0.1`) — `vcr` has no
  empirical calibration anchor anywhere in this project, so "narrow is more plausible" is the best
  available argument, not a proven fact; state it as a judgment call if it comes up.
- **Mediator is fragile**: shrinks or vanishes as the population/hub design is made more uniform, and
  does **not** show a clean dose-response with hub size (M=15 is not an interpolation between M=10 and
  M=20 — it's non-monotonic). Treat mediator as a secondary, condition-dependent observation, not a
  co-equal headline finding.
- **The formal `p_u x vcr` statistical interaction on the outcome variable is itself fragile**
  (permutation p ranges 0.032–0.305 across the four configs above) — do not claim a validated
  interaction effect in the paper. This is why the "how do the two layers relate" TODO (§1) was left
  unfilled rather than answered with an interaction-based story.
- **What IS robust and paper-safe regardless of the above**: two backbone findings, replicated across
  every OAT battery/seed-block/topology tried throughout this whole project (see 2026-08-02 report,
  "robust backbone" sections) —
  1. **Moderate self-reinforcement**: active moderate hub → higher own-camp (moderate) posting rate.
  2. **Near-extreme suppression**: active moderate hub → lower near-extreme (bins 1/3) posting rate.
  These two are *not* in question and can be stated without hedging.

## 3. Model section — ready-to-use draft
(Written earlier this session, then reverted per an explicit user scope correction unrelated to its
content — the content itself was not objected to. Re-offering here as a starting point; edit freely.)

Agent-based model, $N$ agents on a directed, endogenous follow network (agents follow/unfollow over
time), initialized to a heavy-tailed (Holme–Kim) degree distribution so hub concentration exists from
the outset.

- **Opinion**: $o_i \in [-1,1]$, updated each step via Friedkin–Johnsen-style assimilation, averaged
  only over feed content within the agent's bounded-confidence window $bc_i$. $bc_i$ itself relaxes
  each step toward a target set by that step's in-tolerance feed fraction, narrowing faster than it
  widens (asymmetric, negativity-dominant).
- **Two distinct comfort thresholds** (this is the core mechanism the paper is about — explain
  carefully): $bc_i$ is a *rejection* threshold (how much disagreement is tolerated before
  disengagement); the vocal comfort radius $vcr$ is a separate *expression* threshold (how much nearby
  agreement is needed to feel safe posting at all). The feed's in-$vcr$ fraction sets a target posting
  probability that actual posting probability relaxes toward over many steps (comfort→vocality is a
  *slow*, leaky-integrator process, not instantaneous — this matters for interpreting any trajectory-
  level claims).
- **Tie dissolution**: each step, with probability $p_u$, an out-of-tolerance encounter with a
  followee triggers unfollow+block; the same encounter with a not-yet-followed author triggers a block
  only. New follow ties form *only* from in-tolerance (agreement) content — never from disagreement.
- **Feed** = chronological (from followees) + algorithmic (velocity-ranked posts within a
  distance-decayed network radius of the reader). Blocked authors excluded from both.
- **Hub-tier intervention** (the treatment): the $N_h$ highest-follower-count agents at $t=0$ are
  reassigned to one of five fixed opinion targets — extreme ($\pm1.0$), near-extreme ($\pm0.4$),
  moderate ($0.0$) — stubbornness left unpinned (opinions may still drift). This guarantees a
  controlled, non-incidental presence of extreme sources (source extremity held fixed, per the paper's
  causal question), independent of the moderate hub's own activity, which is the manipulated variable.
  A silenced hub category stops posting/reposting but still reads its feed and follows/unfollows
  normally — isolates *voice* from *network position*.

## 4. Experimental Design section — ready-to-use draft
- **Arms**: *control* (all 5 hub categories active) vs. *M-silent* (only the moderate category
  silenced; extreme and near-extreme stay active in both arms).
- **Factorial grid**: $p_u \in \{0.05, 0.15\}$ × $vcr \in \{0.1, 0.15, 0.2, 0.3\}$ (8 cells). This is
  the grid used for every number in §2's table.
- **Scale**: $N=1000$ agents, 40,000 steps, $n=15$–30 seeds per cell (Gaussian-population runs used
  n=15; the four robustness-check configurations in §2 used n=30 each).
- **Outcome**: per-capita original-posting rate for the extreme camp (bins 0/4 by live opinion,
  non-hub only), trailing-window average (last 2000 of 40,000 steps), with a **time-matched,
  per-step population denominator** (not a stale end-snapshot — population size/composition drifts
  between arms, and using a stale snapshot was an actual bug caught and fixed this project — see
  2026-08-02 report, "instrumentation round 3").
- **Robustness dimension not yet mentioned in the draft**: population initial-opinion shape (Gaussian
  vs. uniform) and hub-tier size split (M=10/15/20, moderate-heavy vs. equal) were both varied — see
  §2. Whether/how to describe this robustness sweep in the paper (own subsection? a robustness
  paragraph in Results/Discussion? an appendix?) is an open design choice, not yet made.

## 5. Numbers likely needed for Results (already computed, not yet written into any section)
- Backbone effects: moderate self-reinforcement and near-extreme suppression are significant in
  10/10 configs across every OAT battery this project ever ran (no d-values collected in one place —
  would need to be pulled from the 2026-08-02 report's earlier entries, e.g. the "OAT battery results"
  and "5-parameter OAT battery" sections, when writing Results).
- Facilitator/mediator effect-size table: §2 above, already in reportable form.
- Absolute posting-rate magnitudes and %-changes (Gaussian, original hub design): facilitator cells
  ≈ −4% to −8% relative; mediator cells ≈ +3% to +6% relative — both small relative to `vcr`'s own main
  effect on posting rate (baseline more than doubles, 0.35→0.77, across the swept `vcr` range) — worth
  a sentence in Results/Discussion so the effect isn't over-sold as dominant.
- Comfort-gated content-volume regression: R²=0.56 (near-extreme-sourced + own-camp-sourced comfortable
  content, roughly equal coefficients) explains the *magnitude* of the facilitator/mediator swing
  reasonably well but not the `p_u`-driven threshold-shift specifically — useful for a mechanism
  paragraph in Discussion, appropriately hedged (partial explanation, R²=0.56, not the whole story).
- Structural connectivity check: under control, absolute PE↔E follow-density is 12–15% lower at
  `p_u=0.15` than `p_u=0.05`; under M-silent this reverses (16–36% higher) — `p_u` is a modulator, not
  a fixed separator. Useful supporting evidence for `p_u`'s structural role even without leaning on the
  fragile interaction test.

## 6. Explicitly open / deferred items
1. **Related Work needs real literature** — do not draft this from memory or fabricate citations.
   `refs.bib` is currently empty; last year's `../LaTex-CNA/refs.bib` (opinion dynamics / bounded
   confidence / echo chamber literature) was flagged as a reuse candidate back on 2026-08-06 but never
   actually checked or merged. Needs an actual literature search pass before Related Work can be
   written — flag this to the user rather than inventing citations.
2. **The temporal-relationship TODO** (§1) — kept as a source comment, not written into the paper.
   If page budget allows revisiting: the actual (preliminary, single-pass, n=15, un-replicated) finding
   was that structural-vs-perceptual precedence itself flips with `p_u` (structure leads 3/4 cells at
   `p_u=0.05`, perceptual leads 3/4 cells at `p_u=0.15`) — NOT a fixed "structure-then-perceptual"
   order. Do not write a simple sequential-causality story; it isn't what was found, and sequential
   timing wouldn't logically explain an *absence* of interaction anyway (if anything, staged/path-
   dependent causality is a classic source of interactions, not a reason to expect none).
3. **n=30 confirmation of the ORIGINAL Gaussian 4-level `p_u` grid** (`p_u ∈ {0.01, 0.03, 0.05, 0.15}`)
   was never done — that raw data was deleted before this session started. Only the 2-level
   (`p_u ∈ {0.05, 0.15}`) subset has been formally interaction-tested. Not urgent given the facilitator-
   first pivot (§2) de-emphasizes the interaction claim anyway.
4. **Formal mediation analysis** linking comfort-volume and structural-connectivity channels to the
   outcome (currently two separately-validated correlations, not a joint mediation model) — not started.
   Likely not needed if the paper leans on facilitator-as-headline rather than the interaction/mechanism
   story.
5. **Results section number selection**: decide which of §5's numbers actually make it into tables vs.
   prose, given the 12-page limit — not yet decided.

## 7. Where things live
- Analysis scripts (all reusable, none delete data-dependent — regenerate via `nohup ... & disown` per
  project convention): `scripts/lmp_feedmech_*.py`. Key ones from today:
  `lmp_feedmech_interaction_anova.py` (Gaussian ANOVA/permutation), `lmp_feedmech_comfortvol_test2.py`
  (the R²=0.56 regression), `lmp_feedmech_pu_absolute_connectivity.py` (structural check),
  `lmp_feedmech_uniform_n30.py` / `_uniform_hub_n30.py` / `_uniform_hubM15_n30.py` (the three
  robustness batches) + their matching `_anova.py` analysis scripts.
- `results/` was cleaned up 2026-08-07 (253GB → 851MB) after this session's conclusions were written up
  — nothing left on disk from today's batches; regenerate from the scripts above if a number needs
  re-deriving.
- Full decision history / derivations for every number above: `docs/report/2026-08-02-delayed-moderate-
  conduit-pilot.md`, read chronologically from "2026-08-06" onward for the mechanism investigation, or
  the "2026-08-07" entries for today's independent-verification and robustness-sweep work.

## 8. 2026-08-14 — `vcr` sweep range trimmed to `{0.1, 0.15, 0.2}`, dropping 0.3

**Decision:** the paper's `vcr` (vocal comfort radius) factor, previously swept at
`{0.1, 0.15, 0.2, 0.3}` (§4's factorial grid), is trimmed to `{0.1, 0.15, 0.2}` — the `vcr=0.3` cell
is dropped from the grid reported in the paper. Stated as a general modeling principle in the
Experimental Design section: `vcr` is capped at the bounded-confidence floor
(`bcFloor=0.2`), so that an agent's tolerance (`bc`) can never decline below what it needs merely to
feel comfortable enough to speak (`vcr`) — i.e. the swept `vcr` range is chosen to satisfy
`vcr <= bcFloor` by construction, not left to work out empirically.

**Rationale / what this revisits:** this is the same design-consistency question the user raised on
2026-08-04 (see that date's entry in `docs/report/2026-08-02-delayed-moderate-conduit-pilot.md`,
"bc-vs-vcr design question") — surfaced independently a second time on 2026-08-14 while writing the
Experimental Design section of `tex/CNA2026/CNA2026-2nd.tex`, without initially recalling the earlier
check. The earlier investigation found: literal `bc < vcr` population is 0% for every swept `vcr` up
to 0.2, jumping to 44.4% only at `vcr=0.3`; and the posting-rate sign reversal that motivates the
paper's facilitator/mediator story already occurs at `vcr=0.2`, i.e. `bc < vcr` is NOT the mechanism
behind that reversal (comfortPostRate is the identified proximate mediator instead — see that
report's 2026-08-04 entries). So dropping `vcr=0.3` does not remove the phenomenon the paper reports;
it removes only the one condition where the two thresholds' intended nesting (comfortable-enough-to-
speak content should be a subset of tolerated content) empirically breaks down, which would otherwise
be an unaddressed interpretive loose end in the write-up.

**Practical consequence:** the factorial grid is now `3 (vcr) x 2 (p_u) x 2 (arms) = 12` conditions
(previously 16). No new simulation runs are needed — the `vcr in {0.1, 0.15, 0.2}` data already
collected under the original 4-level sweep remains valid and is simply what gets reported; the
`vcr=0.3` runs/numbers are excluded from the paper, not recomputed under a changed floor value (since
`bcFloor` was already 0.2, matching the new cap exactly — no code or parameter change was needed,
only a reporting-scope decision).

## 9. 2026-08-14 (cont.) — Discussion review (acting-as-CSS-reviewer pass); mechanism claims need
## quantitative backing before submission; experiment plan below

**Context.** User drafted the Discussion section of `tex/CNA2026/CNA2026-2nd.tex` and asked for a
review "as a CSS specialist" (this project's CLAUDE.md reviewer role). Full review delivered in-
session (not reproduced verbatim here); the three load-bearing findings, in order of severity:

1. **The `p_u`-drives-structural-segregation claim is stated unconditionally in the Discussion draft,
   but the project's own prior finding (`docs/report/2026-08-02-delayed-moderate-conduit-pilot.md`,
   2026-08-07 entry, item 3) is that this relationship REVERSES under M_silent** (control arm:
   `p_u=0.15` gives ~12-15% lower E<->NE follow-density than `p_u=0.05`; M_silent arm: reverses to
   16-36% HIGHER). Writing it as an unconditional law overclaims relative to already-measured evidence
   that this project itself generated.
2. **The facilitator regime's "isolates and purifies into an echo chamber" mechanism is asserted as
   clean, but the same 2026-08-07 entry (item 5) found a NULL distributional signature at the final
   snapshot for the facilitator cell** (Mann-Whitney p=0.880, r=0.002) — the story only survives via a
   secondary `postProb`-trajectory reconciliation (item 6: significant divergence at steps 5000-15000
   that loses significance by conventional thresholds later even as the raw gap keeps growing), checked
   for **one cell only**, not yet confirmed to generalize across the grid.
3. **The comfort-gated-content-volume regression (`scripts/lmp_feedmech_comfortvol_test2.py`) is an
   indirect test of the structural-limiting hypothesis**, not a direct one — it regresses the outcome
   on FEED-CONTENT-VOLUME differences (near-extreme-sourced + own-camp-sourced comfortable content
   reaching a reader), which is silent on *why* that volume changes. Its R²=0.560 (up from 0.259 with
   only the near-extreme term) explains part of the effect's *magnitude*, but the model does NOT
   reproduce the `p_u`-driven crossing-point shift (predicts ~vcr 0.18 for both `p_u` rows; actual
   crossing is ~0.14 at `p_u=0.05`, ~0.20 at `p_u=0.15`) — this is evidence *against* volume-mediation
   being the whole story, but it does not directly implicate structural connectivity (item 1) as the
   missing piece either; that inference is currently made by elimination, not by direct test.

**Decision (user, 2026-08-14):** given the page budget, (1) gets a one-sentence citation with real
numbers in the Discussion text now (existing data, cheap); (3) gets redesigned into a more direct
test (below) rather than cited as-is; (2) is deferred entirely to the confirmatory experiment pass
(not written into the paper text until then).

**Complication discovered while planning this:** both the item-1 numbers (12-15%/16-36%) and the
item-3 regression were computed over the ORIGINAL 4-level `vcr` sweep (`{0.1, 0.15, 0.2, 0.3}`,
predating §8's trim), and the underlying `results/2026-08-06_lmp_feedmech_stage1_gexf/` data no
longer exists on disk (cleaned up per project convention after the 2026-08-07 write-up). **Neither
number can be re-derived restricted to the paper's final `vcr in {0.1, 0.15, 0.2}` grid without a
fresh simulation run.** This is why the tasks below require new runs, not just new analysis scripts
over old data.

### 9a. Operational definition of "homophilic / heterophilic" between camps (DECIDED)

The Discussion draft uses "homophilic"/"heterophilic" between the extreme and near-extreme camps as a
narrative label without an operational anchor (flagged in review as a CLAUDE.md term-definition gap).
Decided: anchor it to the two already-instrumented per-layer metrics, one per layer, rather than
inventing a new combined index:
- **Structural layer:** the directed E<->NE follow-edge density (below, 9b) — high density = the two
  camps are structurally homophilic (well-connected); low = heterophilic (structurally separated).
- **Perceptual layer:** the comfort-gated cross-camp content fraction, i.e. what share of a reader's
  feed content from the other camp registers as within-`vcr` (already computed as `ne_diff`'s
  underlying `feedComfortClass*CountMean_*` columns in 9c, or as a ratio against total feed volume if
  a normalized fraction is preferred over a raw count) — high = perceptually homophilic; low =
  heterophilic.

Both should be reported (not just asserted narratively) for the paper's final grid once 9b/9c below
are re-run.

### 9b. Re-run needed: E<->NE structural connectivity, refined estimator, plus NE betweenness
### centrality (directed-graph-aware)

**Refined estimator for the `p_u` contrast (user-specified, corrects the original script's
methodology):** the original `lmp_feedmech_pu_absolute_connectivity.py` computed a *ratio of `vcr`-
averaged densities* (`mean_v[density(0.15,v)] / mean_v[density(0.05,v)]`). This is methodologically
weaker than pairing within each `vcr` cell first — a ratio-of-means can be distorted if density's
relationship with `vcr` itself differs in shape (not just level) between the two `p_u` rows (a
Simpson's-paradox-shaped risk). **Corrected estimator**, to compute instead:
```
delta_density(v) = density(p_u=0.15, v, arm) - density(p_u=0.05, v, arm)      # paired within v
rel_delta(v)      = delta_density(v) / density(p_u=0.05, v, arm)               # optional, as a %
mean_delta        = mean over v in {0.1, 0.15, 0.2}  of  delta_density(v)      # or rel_delta(v)
```
computed separately for `arm in {control, M_silent}`, restricted to the final 3-level `vcr` grid (not
the old 4-level range). Report both the raw and relative (%) forms, plus the per-`vcr`-cell spread
(not just the mean), so the write-up can show whether the `p_u` contrast is stable across `vcr` or
itself `vcr`-dependent (worth knowing either way).

Density itself: reuse `cross_class_density()` (`scripts/lmp_feedmech_stage1_gexf.py:76-86`, directed
E-\>NE follow-edge count divided by `|E|*|NE|`, non-hub agents, same-sign sides E-\>NE- and E+\>NE+
averaged) — definition itself does not need to change, only the aggregation-order fix above.

**New instrumentation (user-requested): near-extreme agents' betweenness centrality.** Motivation:
density only captures *direct* E<->NE ties; betweenness captures whether NE agents function as
structural *brokers* (the same concept Related Work already cites via Freeman 1977) between the camps
(or more broadly in the network), a richer bridging signal than direct-tie density alone. **Directed-
graph caveat (user-flagged, and correctly so):** this follow graph has the same in-degree/out-degree
asymmetry already flagged for the For-You hop-direction question in `research-direction.md` (hubs:
huge in-degree, `maxFollowCapacity`-capped out-degree) — running `networkx`'s directed betweenness
naively on the `DiGraph` may not behave like the intuitive "bridge" notion. **Plan:** compute BOTH (a)
standard directed betweenness (`nx.betweenness_centrality(G, normalized=True)` on the `DiGraph` as-is)
and (b) betweenness on the same graph symmetrized to undirected (or restricted to reciprocated edges
only, as an alternative symmetrization) — compare the two, and pick/justify one as primary for the
paper rather than defaulting silently to whichever `networkx` gives first. Report mean NE-camp
betweenness (both sides, non-hub) per `(p_u, vcr, arm)` cell, same grid as 9a.

**Requires fresh simulation runs** (final grid: `p_u in {0.05, 0.15}` x `vcr in {0.1, 0.15, 0.2}` x
`arm in {control, M_silent}`, Gaussian population, `M=20` hub split, `n=15` seeds, matching the
paper's Experimental Design section exactly) **with GEXF export enabled** at the final checkpoint
(step 40000) so `cross_class_density` and the new betweenness computation can both read off the same
snapshots. Reuse the existing seed block and hub-tier construction from the original grid run
(`docs/report/2026-08-02-delayed-moderate-conduit-pilot.md`, "Grid launched" entry) for continuity.

### 9c. Redesign needed: direct structural-mediation test (replaces / supplements the comfort-volume
### regression)

**User's critique (correct):** the existing `lmp_feedmech_comfortvol_test2.py` regression tests
whether FEED-CONTENT-VOLUME differences predict the outcome — it never actually puts the structural-
connectivity hypothesis (9b) into the same regression, so its "doesn't reproduce the crossing shift"
finding is only indirect (negative) evidence, not a direct test of "does `p_u`'s structural effect on
E<->NE connectivity explain the outcome." **More direct design:** regress the per-cell (or better,
per-seed, preserving n=15x6=90 observations rather than collapsing to 6 cell means) outcome — the
same M_silent-minus-control extreme-camp posting-rate difference already used as the paper's headline
metric — directly on the structural metrics from 9b (E<->NE density, NE betweenness), across the full
`p_u x vcr` grid (both arms' contrast as the response, structural metrics as predictors, computed
per-seed from that seed's own final-snapshot GEXF). This tests the actual hypothesized causal chain
(`p_u` -\> structure -\> outcome) in one step, rather than the current two-hop, partially-indirect
chain (`p_u` -\> content volume -\> outcome, with structure's role only inferred by elimination).
Keep the existing comfort-volume regression too (it remains informative about the perceptual-layer
channel specifically) — the two together, plus the operational-definition metrics from 9a, should let
the mechanism section report actual R²/coefficient numbers on both channels instead of one indirect
proxy.

### 9d. Deferred to the same experiment pass (not written into the paper until confirmed)

- **Purification/distributional check (item 2 above)** — repeat the `avgComfortRate` distributional
  check (Mann-Whitney -\> rank-biserial r) and the `postProb`-trajectory reconciliation, currently
  confirmed for one cell only, across the full final grid (6 cells) to see whether the "early
  divergence that locks in via slow `postProb` relaxation" story generalizes or was cell-specific.
- Once 9b/9c produce numbers, revisit whether the Discussion's P_u-segregation sentence should be
  hedged further (e.g. "in the control arm specifically") or whether the M_silent-reversal finding
  itself becomes citable as a positive, well-quantified result worth its own sentence.

### 9f. SUPERSEDED — see `docs/report/2026-08-15-mechanism-re-derivation.md` (added 2026-08-15, revised
### same day after two rounds of user critique — read the full file, not just this pointer)

9b and 9c were both executed (fresh 6-cell x 2-arm x 15-seed grid with GEXF export, under
`results/2026-08-14_lmp_feedmech_structural_9b/`). 9c returned R²=0.064–0.168 — a null. Investigating
*why* refuted three premises this section was built on:

1. `alpha=0` in `BASE_TOKENS` disables the algorithmic feed entirely, so **betweenness centrality has
   no channel to act through** — the BFS/hop-distance code never runs. 9b's betweenness
   instrumentation was mis-specified from the start.
2. Feeds run at **2.0–3.0 items against `feed_capacity=15`** — starved, not full. The "displacement"
   premise behind the comfort-volume regression is false.
3. Moderate-authored content is **0.5–2.3% of an extreme reader's feed** even under control, and the
   moderate hubs are purged from extreme readers' followee sets entirely (by step 5000 — before the
   first checkpoint). The moderate hub is not acting as a conduit.

**The R²=0.852 comfort-rate result in the base file's §6 is RETRACTED (Addendum 1) as tautological** —
comfort rate is the only free variable in the equation that sets posting probability, so a high R²
there is guaranteed by construction and proves nothing about mechanism. Do not cite it.

**The supported mechanism, current as of the file's two addenda, is path dependence, not sustained
suppression:** moderate content is out-of-bc for extreme agents only during the formative window
(step 0–5000, before the hubs are purged); that early perturbation selects which of two
self-reinforcing structural basins the run settles into, with `p_u` acting as the feedback loop's
gain. Everything after ~step 5000 is consequence, not ongoing cause (Addendum 1, §A3).

**Addendum 2** operationalises the paper's "homophilic/heterophilic" framing as two gates in opinion
space — `bc_inclusion` (structural, p_u-driven, non-circular) explains 53% of near-extreme-camp influx
into the extreme camp on its own; `vcr_inclusion` (perceptual) is flat and treatment-invariant, so the
division of labour is **p_u sets how much near-extreme content arrives; vcr sets whether it registers
as comfortable (the sign of the effect)**. It also found that unweighted follow-graph structural
indices (density, Louvain community co-membership) are contaminated by an artifact specific to this
treatment design — silencing a hub stops it being *encountered*, so it stops being unfollowed, so
inert ties accumulate and inflate any unweighted structural measure — and must be weighted by author
activity (`postProb`) or avoided. **§9a's operational definition (E<->NE follow density) should be
replaced with `bc_inclusion`/`vcr_inclusion` for this reason.**

**Do not write 9b/9c's raw structural numbers (density, betweenness) into the paper as a causal
channel, and do not cite the R²=0.852 figure.** Read the 2026-08-15 file (base + both addenda) before
drafting the Discussion's mechanism paragraphs.

### 9e. Where this leaves the current draft

No changes made to `CNA2026-2nd.tex` in this session as a result of 9a-9d — this is a forward plan.
The Discussion section's mechanism paragraphs remain as last edited (grammar/expression pass only);
the quantitative backing planned above still needs the fresh simulation + analysis pass before it can
be written in. Do not add the old (pre-`vcr`-trim, since-deleted-data) 12-15%/16-36% numbers or the
R²=0.560 regression result to the paper text as-is — both need re-derivation per 9b/9c first.
