# 2026-09-11 — alpha (feedAlgoShare) broad dose-response scan: design decision

## Context
This repo (forked from `Dev-ComplexNetworks2026`, see
`docs/report/2026-09-09-repo-split-rec-feed-fork.md`) has no research-direction doc yet for
its new "recommendation algorithm in agents' feed" line. First concrete step: characterize how
the model's existing recommendation mechanism (`feedAlgoShare`, i.e. `alpha`) affects the
model's standard outcome measures, before committing to a specific hypothesis or paper framing.

## Mechanism being probed (plain-language, first use)
Each agent's feed is filled from two sources: a **chronological/follower stream** (posts from
accounts the agent follows, in cache order) and a **"For You" algorithmic stream**, in a ratio
set by `alpha` (0 = fully chronological, 1 = fully algorithmic). The algorithmic stream is
**opinion-blind**: it ranks candidate posts purely by repost velocity (how fast they are already
spreading) and reaches beyond the agent's own follow graph (hop-limited BFS, decay by distance).
Raising `alpha` therefore does two things at once, which pull in opposite directions:
- **Bridging effect (candidate depolarizing mechanism):** exposure to accounts outside one's own
  homophilous follow neighborhood increases, since the algorithmic stream isn't restricted to
  followees.
- **Amplification effect (candidate polarizing mechanism):** attention concentrates on whatever
  content is already virally spreading, which could disproportionately be extreme/high-reaction
  content, since it is chosen by velocity, not content.

A single scalar polarization outcome cannot distinguish which of these two mechanisms is driving
any observed change, but a **first broad scan** across a battery of the model's standard outcome
metrics can at least establish which direction(s) `alpha` moves things, before designing the
mechanism-diagnostic follow-up (comparing exposure composition, e.g. `feedForYouCountMean_i` /
`feedChronoCountMean_i` per opinion bin, already logged by the simulator but not analyzed in this
first pass).

## Decision
- **Design intent, per user:** run a broad, unopinionated first look across the model's existing
  polarization/structure metrics — not yet the bridging-vs-amplification diagnostic split — to
  get a sense of `alpha`'s overall effect before deciding what to dig into.
- **Swept parameter:** `alpha` (feedAlgoShare) ∈ {0.0, 0.2, 0.4, 0.6, 0.8, 1.0} (6 points).
  Rationale for range: covers the full [0,1] domain including both boundaries. Note `alpha=1.0`
  is a known runaway/self-reinforcement point in prior BO work on this model
  (`scripts/feed_redesign_v4_joint_bo_fixed_alpha_tau.py`), so it is included deliberately as an
  extreme-behavior reference point, not excluded.
- **Fixed baseline (all other params):** identical to `scripts/feed_redesign_v5_dose_response_n100.py`'s
  `FIXED_TOKENS` (hop=4, feed_decay_mode=exp, feed_decay_lambda=0.10992130598108527,
  feed_time_decay_tau=30, feed_capacity=15, network=hk/hk_m=15/hk_a=4/hk_pt=0.05,
  max_follow=43.8638, follow_prob=0.01, access_prob=0.1, p_u=0.05, bc_dec=0.5, bc_recovery=0.0001,
  bc_floor=0.2, bc_ceiling=1.0, bc_init=0.8, vocal_comfort_radius=0.1, repost_prob=0.1,
  relay_enabled=false, out_of_bc_repost_prob=0.01, rel_attrib=original, stub_dist=uniform,
  stub_min=stub_max=0.82, evict_beta=-1, init_prune=trim, initial_pp=0.25537, max_pp=1.0,
  min_pp=0.01, pp_relax_eta=0.1, neutral_band=0.2) — reusing this repo's inherited, previously
  validated CNA2026 baseline config so the only manipulated variable is `alpha` itself.
- **Scale:** 20 seeds/point × 6 points = 120 runs. n=1000, steps=20000. Checkpoints 5000/10000/20000
  (not endpoint-only — prior work on this model found effects can be front-loaded and decay by
  the final step, see `feed_redesign_v5`'s docstring).
- **Outcome battery (all pre-existing simulator output, `metrics/results.csv`, no new Java code):**
  `opinionVar`, `postOpinionVar`, `bimodalityCoeff`, `opinionAssortativity`, `crossCuttingFraction`,
  `interactionAssortativity`/`interactionAssortativityW`,
  `interactionCrossCuttingFraction`/`interactionCrossCuttingFractionW`, `postShare_0..4`,
  `shannonIndex`, `meanTolerance`, `toleranceVar`, `outGroupSanctionRate`,
  `outGroupBlockPropensity`, `Q_sign_repost` (from `metrics/modularity.csv`; per
  [[feedback-noise-tolerance-in-metrics]] this one is known-noisy across seeds — read small
  deltas cautiously).
- **Seeds:** fresh range, base 9100000 (offset from all prior `feed_redesign_*`/`stage_*` seed
  ranges to avoid any accidental collision with `Dev-ComplexNetworks2026`-era result directories,
  though this is now a fully separate repo/results dir anyway).

## What this supersedes
Nothing — first experiment in this repo's own line of work.

## Next step (not yet decided)
Once this scan's results are in, decide with the user whether the pattern points toward
bridging, amplification, both (at different alpha ranges), or neither, and design the
mechanism-diagnostic follow-up accordingly (e.g. comparing per-opinion-bin ForYou/chrono feed
composition, or content-concentration metrics on repost velocity).

## Results (n=20 seeds/point, checkpoints 5000/10000/20000)

Full per-run CSV: `docs/report/alpha_dose_response_broad_scan.csv`. Three distinct constructs,
each answering a different notion of "polarization," move differently with alpha — conflating
them produces an incorrect headline claim, so they are kept separate below.

**1. Held-opinion distribution (population-level, `opinionVar`/`bimodalityCoeff`): flat, not
significant.** Spearman rho vs alpha at step 20000: opinionVar rho=0.017 (p=0.86), bimodalityCoeff
rho=0.153 (p=0.095, BH-FDR q=0.33). The population's actual opinion distribution does not become
more spread out or more bimodal as alpha rises, in this config/range.

**2. Network-structure homophily (`opinionAssortativity`, `crossCuttingFraction`): non-monotonic
hump, not a monotonic rise.** opinionAssortativity: 0.63(a=0)->0.49->0.47->0.43(min,a=0.6)->0.45
->0.55(a=1.0); crossCuttingFraction (inverse-ish): 0.10(a=0)->0.19->0.21->0.23(max,a=0.6)->0.23
->0.18(a=1.0). Cross-camp exposure/interaction is HIGHEST at mid-alpha, not at alpha=1. A plain
Spearman correlation on opinionAssortativity is not significant (rho=-0.134, p=0.14) precisely
*because* the relationship is non-monotonic -- reporting "no effect" from that alone would be a
methodological error; the shape itself is the finding.

**3. Vocal/expressed layer (`postOpinionVar`, `postShare_0`/`postShare_4`, absolute posting
volume by class): rises with alpha, clearly and closer to monotonically.** SF1
(=postOpinionVar/opinionVar) steps from 0.93 (a=0, expression is LESS spread than the underlying
population) to ~1.2-1.4 for any alpha>0 (expression MORE spread than the population) --
significant (rho=0.433, q<0.001 at step 20000) -- with most of the jump between a=0 and a=0.2,
roughly flat after. Absolute posting volume summed over the two extreme classes (bins 0+4) grows
~3.6x from a=0 (20.6 posts/step) to a=1.0 (74.1 posts/step) and each active extreme-class agent's
per-turn posting/reposting intensity roughly triples (0.9->3.2), vs. ~1.6x for the neutral class
(bin 2) -- i.e. the volume increase is concentrated in behavioral intensification of the extreme
classes specifically, not a uniform rise across all classes.

**Conclusion so far: this is NOT "the network polarizes as alpha rises."** opinionVar/
bimodalityCoeff (the direct measures of population-level polarization) show no effect. What
changes is which layer speaks (Type 2/expressed, not Type 1/structural, in the CNA2026 paper's
Type 1 vs Type 2 framing terms -- see `Dev-ComplexNetworks2026/docs/research-direction.md` for
that framework's origin, reused here only as a naming convention, not as this repo's research
claim) -- and even the network-structure homophily measure moves in the OPPOSITE direction from a
simple "echo chamber deepens" story through most of the alpha range.

**Echo-chamber locus, decomposed by reader class x author class
(`feedAuthorClass{author}CountMean_{reader}`, step 20000):** "same-class share" = fraction of a
reader-class's feed authored by its own class.

| alpha | ext(-) reader | mod(-) reader | neutral reader | mod(+) reader | ext(+) reader |
|---|---|---|---|---|---|
| 0.0 | 0.809 | 0.629 | 0.532 | 0.724 | 0.696 |
| 0.2 | 0.569 | 0.344 | 0.452 | 0.298 | 0.763 |
| 0.4 | 0.742 | 0.255 | 0.454 | 0.371 | 0.756 |
| 0.6 | 0.604 | 0.404 | 0.356 | 0.333 | 0.660 |
| 0.8 | 0.693 | 0.390 | 0.383 | 0.334 | 0.663 |
| 1.0 | 0.800 | 0.300 | 0.303 | 0.247 | 0.758 |

The three middle classes (mod(-), neutral, mod(+)) show a clear, roughly monotonic same-class
share COLLAPSE (~53-72% down to ~25-38%) -- the moderate middle's insulation from other camps
erodes as alpha rises. The two extreme classes' same-class share is flat/non-monotonic and ends
at alpha=1.0 close to or at its alpha=0 baseline (0.809->0.800; 0.696->0.758) -- **no evidence of
extreme-camp echo-chamber deepening**; the moderate-insulation-weakening half of the
bridging/amplification hypothesis is the one supported by this decomposition, not the
extreme-echo-chamber-deepening half. At alpha=1.0 the feed is 100% algorithmic (zero
chronological/follower share) yet extreme readers still see ~76-80% same-class content from an
opinion-blind ranker -- consistent with the hop-limited ("feedHopH", exp-decay) recommender reach
inheriting pre-existing follow-graph homophily around peripherally-clustered extreme agents, while
more centrally-positioned moderate agents' same hop-radius naturally spans multiple camps. This is
a hypothesis about the follow-graph's degree/clustering structure by opinion class, not yet
directly verified (would need per-class degree/clustering-coefficient analysis on the follow
graph, not yet done here).

## Dashboard network visualization (2026-09-22)

To let the user visually inspect the follow/repost network at each alpha value, added one
GEXF-logging run per alpha point (`log_gexf=true`; the original 120-run scan used
`log_gexf=false` for speed/disk, so those runs have no network snapshots). No dashboard code was
changed — `dashboard/core.py`'s existing generic log-prefix grouping (`log_groups()`,
`GROUP_LOG_RE`/`MID_SEED_RE`) already auto-discovers any `logs/<prefix><seed>.log` naming with no
per-experiment registration, per this project's standing policy that the dashboard stays
model/experiment-agnostic (no alpha-specific UI). Reusing the original sweep's exact log-name
convention (`alpha_scan_a{alpha:.2f}_seed{seed}.log`) means each new seed joins the SAME run-set
group as that alpha's original 20 seeds, so no new group appears in the picker beyond what's
already there.

**Seeds added (fresh range, do not overlap the original 120-run dataset):**

| alpha | seed | result dir tag |
|---|---|---|
| 0.0 | 9200000 | `..._a-0.00_st-20000` |
| 0.2 | 9201000 | `..._a-0.20_h-4_lam-0.11_st-20000` |
| 0.4 | 9202000 | `..._a-0.40_h-4_lam-0.11_st-20000` |
| 0.6 | 9203000 | `..._a-0.60_h-4_lam-0.11_st-20000` |
| 0.8 | 9204000 | `..._a-0.80_h-4_lam-0.11_st-20000` |
| 1.0 | 9205000 | `..._a-1.00_h-4_lam-0.11_st-20000` |

Same baseline config as the broad scan (`feed_redesign_v5`'s FIXED_TOKENS), n=1000, steps=20000.
Each has follow-graph (`GEXF/lambda_0.0/step_{0,5000,10000,15000,20000}.gexf`) and repost-graph
(`GEXF/repostNW/repost_step_{5000,...,20000}.gexf`) snapshots.

**To view:** `./dashboard/serve_public.sh` (or `python dashboard/dashboard.py --serve`), open the
dashboard, use the run-set/group picker to select the `alpha_scan_a{X}_seed` group for the alpha
of interest, then pick the seed from the table above within that group, and open the network
panel (step slider selects which 5000-step checkpoint's GEXF to render; follow vs. repost graph
toggle). Only 1 seed per alpha has a network view — the other 19 seeds in each group are the
original non-GEXF runs and will show no network data, which is expected.
