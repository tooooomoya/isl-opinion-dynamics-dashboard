# 2026-07-15 — Systematic-A/B calibration plan, Stage 1a: HK generator (m, A, pt)

**Context:** this session settled the calibration/validation design (separate conversation, not yet
written up as its own report file — summarized here for the record): calibration targets split into
系統A (network structure: degree distribution, Gini, HK generator params) and 系統B (repost/cascade
dynamics: bcDecRate, stubbornness, comfortPpFactor, feedCapacity, initialPostProb, targeted at the
repost network's own structural fit — Conover et al. 2011 modularity ~0.7-0.8 — not a follow-graph
metric). `repostProb` fixed at 0.1 (not calibrated — the model's repost mechanism doubles as "like",
so Meng et al. 2025's narrow repost-rate figure isn't a comparable target). `crossCuttingFraction`/
`interactionCrossCuttingFraction` reserved for **validation only** (Barberá et al. 2015), never used
as a calibration objective — this is the paper's own headline outcome metric. HK (Holme-Kim) replaces
DC-SBM as the baseline network for calibration ("if degree distribution + clustering are realistic,
dynamics should be reasonably realistic regardless of generator" — DC-SBM/ws/random/lfr get only a
post-hoc qualitative check after HK calibration, not their own calibration pass).

**Prerequisite implementation (this session, same day):**
- `ExperimentConfig`/`NetworkFactory`: HK's `m/A/pt` promoted from hardcoded `(3,1,0.3)` to CLI
  (`hk_m`/`hk_a`/`hk_pt`), mirroring the earlier DC-SBM `sbm_*` migration.
- `Analysis.computeSignModularityFromMatrix` + `Writer.writeRepostDegrees`/
  `writeRepostClusteringCoefficients` + `Writer.writeModularity`'s new `Q_sign_repost` column:
  repost-network structural fit, computed on the same windowed `repostNetwork` matrix
  `repostGephi` exports (so the numbers always describe the graph the dashboard's repost-graph
  view is showing — fixed a latent bug where `dashboard/analysis.py`'s `net=repost` selector
  changed which graph was *drawn* but the structural panel silently kept reading follow-graph CSVs).
  Wired into the dashboard (`core.py` METRICS/aux handling, `dashboard.html`'s qsignei panel).
- **Bug fix:** t=0 network snapshot was missing a clustering-coefficient CSV (`writeDegrees` was
  called pre-loop, `writeClusteringCoefficients` was not — only the periodic step%5000==0
  checkpoints wrote it). Without this, Stage 1a's generator-only fit would have been contaminated
  by up to 5000 steps of follow/unfollow dynamics. Added the missing t=0 call.

## Stage 1a design

Target: Kwak et al. 2010 ("What is Twitter, a Social Network or a News Media?", WWW'10) — Twitter
follow-graph in-degree power-law exponent γ≈2.276 (already used elsewhere in this project, e.g.
`sbm_gamma`), and average local clustering coefficient ≈0.072 (same paper; confirmed via search this
session — previously an open "needs literature check" item).

HK's γ = 2 + A/m is analytic (`HolmeKimNetwork.java` docstring), so `A` was chosen per `m` to target
γ≈2.276 up front (`A = round(0.276·m)`); the grid swept `m` (also the density/mid-scale-hub-hosting
knob per `research-direction.md`) × `pt` (clustering — no analytic formula, must be measured):
`m ∈ {3(default),5,10,15,20,25,50}` × `pt ∈ {0.05,0.1,0.2,0.3}`, 3 seeds each, `n=1000, steps=1`
(only the t=0 pre-loop snapshot is needed — generator fit, not dynamics; cheap: 84 runs completed in
under a minute). Script: `run_hk_calibration_sweep.sh`; analysis: `scripts/hk_calibration_analysis.py`
(reuses `dashboard.analysis.fit_powerlaw`); raw output: `docs/report/2026-07-15-hk-calibration-stage1a-results.txt`.

## Finding: γ_fit systematically undershoots γ_analytic — confirmed as finite-size, not a generator bug

Every cell's empirically-fit power-law exponent (via `powerlaw.Fit`, MLE) came in **0.3-0.5 below**
its analytic `2+A/m`, uniformly across the whole grid (e.g. m25a07: analytic 2.280, fit 1.864).
Before trusting the analytic formula over the measurement, checked the finite-size hypothesis
directly: re-ran the single cell `m=25,A=7,pt=0.05` at `n∈{1000,3000,5000,10000}`:

| n | fit α | xmin | max in-degree |
|---|---|---|---|
| 1000 | 1.866 | 5 | 205 |
| 3000 | 1.960 | 7 | 455 |
| 5000 | 2.011 | 8 | 664 |
| 10000 | 2.049 | 9 | 1148 |

**Monotonically converging toward the analytic 2.280 as n grows, still not fully there at n=10000.**
This is the same finite-size truncation already documented for DC-SBM (`2026-07-09-oat-sweep-findings.md`:
`k_max ~ n^{1/(γ-1)}`) — the empirical MLE fit at the model's actual working scale (n=1000) is a
biased *measurement* of the true generative exponent, not evidence the generator deviates from it.
**Conclusion: trust the analytic `γ=2+A/m` for calibration purposes, not the raw n=1000 fit.** This
also means `gamma_fit` should not be used to rank grid cells against each other (its bias is roughly
constant across cells at fixed n) — only `clustering` (a direct, un-biased-by-asymptotics measurement)
usefully differentiates cells here.

## Result: current default (m=3, A=1, pt=0.3) overshoots clustering 2-3x

Default clustering measured 0.13-0.20 vs. the 0.072 target — HK's current hardcoded starting point
was too clustered (unsurprising: high `m` and any `pt>0` compound quickly at low density). Larger `m`
(with `A` tracking γ) plus low `pt` (0.05-0.1) brings clustering down toward target:

| cell | pt | clustering | Δ from 0.072 |
|---|---|---|---|
| m50a14 | 0.20 | 0.0684 | 0.0036 (closest) |
| m50a14 | 0.05 | 0.0571 | 0.0149 |
| m25a07 | 0.05 | 0.0917 | 0.0197 |
| m50a14 | 0.10 | 0.0613 | 0.0107 |

## Open decision, not yet made: m=25 vs m=50 band

Both `A/m` pairings hit γ_analytic≈2.28-2.30. `m` also sets average out-degree (=m exactly, by HK's
construction — every node adds exactly `m` edges), i.e. it is simultaneously the
mid-scale-hub-hosting density knob flagged in `research-direction.md` (prior DC-SBM study used
`sbmDeg=50` for the same reason). `m=50` gives the closest clustering match (0.068 at pt=0.2) and the
denser substrate; `m=25` is cheaper (fewer edges) and still reasonably close (0.092 at pt=0.05).
**Not resolved this session** — deferred to whoever runs Stage 1b (`maxFollowCapacity`/`followProb`
calibration operates on top of whichever `m` is picked here, so this choice should be locked before
Stage 1b starts, not revisited mid-sweep).

## Next: Stage 1b (maxFollowCapacity, followProb, alpha, hop vs. emergent Gini≈0.8 + degree exponent)
