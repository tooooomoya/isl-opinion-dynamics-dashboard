# 2026-07-09 — Sensitivity analysis (Tier B/C/D) design + literature anchors

> **Superseded:** this is the pre-run design doc, kept for the record. The actual sweep (57 runs,
> seeds 200-202 not 300-302 as drafted below) and its results, plus the follow-up 10-seed
> re-checks and the velocity-formula fix, are in `docs/report/2026-07-09-oat-sweep-findings.md` —
> read that file for current information; treat this one as historical intent only.

**Context:** continues `docs/report/2026-07-08-validation-gate-pilot.md` (Step-2 validation gate).
That file's calibration discussion produced a long list of parameters with unresolved values; rather
than keep digging into individual parameters one at a time (which was starting to diverge — see the
"何も変数が決められない" discussion), switched to **screening first**: run a scoped one-at-a-time
(OAT) sensitivity sweep to find which parameters actually move the headline Step-2 gate metrics,
and only invest further calibration effort in those. Parameters that don't move the metrics get
recorded as "confirmed inert, left at current default" rather than silently ignored.

**Timeline note:** `research-direction.md` §0 targets "simulation working" by **mid-July 2026**;
today is 2026-07-09. This sweep is intentionally scoped small (lighter than the validation-gate
pilots) to fit the remaining time.

## Parameter inventory (full list, for future reference)

- **Tier A (experiment-design factors, NOT swept here)** — `p_u`, `network` type, `n_mod`/`size`/
  `topk`. These are the Step-3 experimental design's own independent variables (the DAG in
  `research-direction.md` §0), not calibration nuisance parameters. Deliberately out of scope for
  this pass — "the model needs to stand on its own first."
- **Tier B (calibration, "light" sweep)** — `repost_prob`, `bc_inc` magnitude, flat stubbornness
  level, `sbm_pin`/`sbm_pout`.
- **Tier C (recommender / degree-distribution match)** — `feedAlgoShare` (alpha). Doubles as a
  check that hub growth actually occurs via the For-You recommender now that `MU_PARAM` was
  removed (`docs/report/2026-07-08-validation-gate-pilot.md`, "MU_PARAM removed" section) — with
  alpha=0 (this model's pilots so far), there is currently **no** growth channel for the moderate
  hub at all, which is exactly what this sweep needs to check.
- **Tier D (confirm-inertness sweep)** — `feed_capacity`, `follow_prob`, `comfort_pp` (formerly
  `Const.FEED_CAPACITY`/`FOLLOW_PROB`/`COMFORT_PP_FACTOR`), `max_pp`. **Implementation note:**
  these were plain `Const` literals never migrated to `SimParams`/CLI in the R20 pass (an
  oversight — `Const.java`'s own docstring says runtime knobs belong on `SimParams`). Migrated
  today: new `ExperimentConfig`/`SimParams` fields `feedCapacity`/`followProb`/`initialPostProb`/
  `maxPostProb`/`minPostProb`/`comfortPpFactor`, new CLI keys `feed_capacity=`/`follow_prob=`/
  `initial_pp=`/`max_pp=`/`min_pp=`/`comfort_pp=`, read sites in `Agent.java`/`AdminOptim.java`
  switched from `Const.X` to `p.x()`. Verified: recompile clean, `ModelTests` 28/28 pass, smoke
  run's folder tag shows `_fc-20_folp-0.500_cpf-1.300` confirming the new keys take effect.

## Literature anchors used for candidate values (traceable for future citation)

| Parameter | Candidate values | Anchor |
|---|---|---|
| `repost_prob` | 0.01, 0.10, (0.25 baseline) | Floor `Meng et al. 2025` (PNAS) ψ≈10⁻³ population average (not directly used — see caveat below); ceiling = current default, inherited from `Sasahara et al. 2021` → `Qiu et al. 2017` (Nature Human Behaviour, **retracted** for unrelated Fig. 4d/5 model-fit bugs, not for the μ≈0.75 raw Twitter tweet/retweet-ratio statistic used here) |
| `bc_inc` (magnitude) | 0.001, 0.005 | Direction only: `Baumeister et al. 2001` "Bad is stronger than good"; `Rozin & Royzman 2001` "Negativity Bias, Negativity Dominance, and Contagion" (distinguishes rate-asymmetry "negativity bias" — what this model implements — from threshold "negativity dominance"). No magnitude given by either; both candidate values are engineering choices to bracket a plausible range |
| flat stubbornness | 0.6, 0.95 (0.8 baseline) | `Das, Gollapudi, Munagala 2014` (WSDM) checked directly (PDF in `docs/reference/`): supports stubbornness as a *stable per-user trait* (Fig. 8b) but reports no population-average numeric estimate transferable here — no literature anchor for the value itself |
| `sbm_pout` (pin held at 0.08) | 0.005, 0.01 | Calibration-target framing, not direct import: `Bakshy, Messing, Adamic 2015` (Science) and `Boutyline & Willer 2017` report empirical cross-cutting-exposure figures on the order of 20-25%; candidates chosen to probe whether raising `sbm_pout` moves this model's own *initial* `crossCuttingFraction`/`opinionAssortativity` toward that range |
| `feedAlgoShare` (alpha) | 0.3, 0.6 (0 baseline) | `Kwak et al. 2010` (WWW) Twitter follower-distribution power-law exponent 2.276 (already used for `sbm_gamma`) reused here as the **target** for the *emergent* (post-dynamics) degree distribution — checks whether recommender-driven growth distorts the exponent away from the empirically realistic 2-3 range |
| `feed_capacity`, `follow_prob`, `comfort_pp`, `max_pp` | ±~50-100% of current default each | No literature anchor sought — these are the Tier-D "pure scale" parameters; the sweep's purpose is to confirm they do *not* move the headline gate metrics, not to calibrate them |

**Caveat on `repost_prob`'s floor:** `Meng et al. 2025`'s ψ≈10⁻³ is an *unconditional* population
average across all message salience levels; this model's `repostProb` only ever gates content that
already passed the bounded-confidence tolerance check (pre-filtered for relevance/agreement), so
the true analogous rate is expected to sit above this floor. Kept as a recorded reference point,
not a candidate value in this sweep (0.01 already sits an order of magnitude above it).

## OAT design

**Baseline:** `network=dcsbm extreme=sym channel=both n_mod=1 n=300 steps=15000`, all other knobs
at current defaults (`repost_prob=0.25, bc_inc=0.0, stub_dist=const(0.8), sbm_pin=0.08/pout=0.002,
alpha=0, feed_capacity=10, follow_prob=0.1, comfort_pp=1.1, max_pp=0.5`). Deliberately smaller than
the validation-gate pilots (`n=500, steps=15000-30000`) — this is a screening pass, not a
gate-decision pass; if a parameter shows a large effect here it gets a proper follow-up at pilot
scale, not a conclusion drawn directly from this run.

**Cells:** baseline + one changed parameter per cell (18 OAT cells + baseline = 19), 3 seeds each
(`300,301,302`) = 57 runs.

**Readout:** the already-established Step-2 gate metrics (`opinionAssortativity_final`,
`crossCuttingFraction_final`, `interactionCrossCuttingFraction_final`, `signModularity_final`,
`hub_cross_camp_fraction` — now using the event-time-opinion fix from the previous file's last
section, not the final-snapshot proxy) plus, for the `alpha` cells specifically, a fitted power-law
exponent on the end-of-run in-degree distribution (target: `Kwak et al. 2010`'s 2.276, same anchor
as `sbm_gamma`) and the moderate hub's follower growth (t0 vs final).

**Decision rule:** for each swept parameter, compare its cells' gate metrics against the baseline's
distribution (3 seeds). If within the baseline's own seed-to-seed spread → confirmed inert / robust
at this parameter, freeze at current default. If clearly outside → flagged as load-bearing, escalate
to a proper calibration pass (own pilot, more seeds) before the Step-3 freeze.

Results recorded in a following section once the sweep completes.
