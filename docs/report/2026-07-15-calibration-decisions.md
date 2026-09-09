# Calibration decisions log (systematic-A/B calibration plan)

Running ledger of locked-in calibration values, kept separate from the narrative process reports
(e.g. `2026-07-15-hk-calibration-stage1a.md`) so "what is the current calibrated value of X" doesn't
require re-reading a full sweep writeup. Append one row per decision; do not edit past rows except to
correct an error — if a later stage revises a value, add a new row and mark the old one superseded.
**Full sweep result tables (not just the decided value) live in
`docs/report/calibration-sweep-results.md`** — this file is the "what's decided now" summary only.

| Date | Parameter | Value | Stage | Rationale (link) |
|---|---|---|---|---|
| 2026-07-16 | `hk_m` | **15** | 1a | Compute-cost tradeoff (Stage 1b/2 production-scale runs at n=1000 compound with initial density): m=15 gives 40% fewer initial edges than m=25. Clustering fit is worse (0.1424 vs. target 0.072, ~2x too high) — accepted tradeoff. m=20/m=25 deferred to a final robustness check after the main calibration is done, not a full separate pass. See `calibration-sweep-results.md`. |
| 2026-07-16 | `hk_a` | 4 | 1a | Paired with m=15 to target γ_analytic=2.267 (Kwak et al. 2010 γ≈2.276). |
| 2026-07-16 | `hk_pt` | 0.05 | 1a | Best clustering match among m=15 rows (0.1424); still ~2x the 0.072 target — known, accepted limitation of the m=15 choice. |
| 2026-07-16 | (γ_fit vs γ_analytic gap) | **accepted, not fixable at n=1000** | 1a | Confirmed finite-size artifact of preferential-attachment MLE fitting (xmin selection dominated by not-yet-converged low-degree nodes at small n; converges toward analytic as n grows, per the n-scaling check). Standard, well-documented limitation (Clauset/Shalizi/Newman 2009; Broido & Clauset 2019), not specific to this codebase. Trust analytic γ=2+A/m for parameter choice; state the finite-n caveat in writeups. |
| 2026-07-16 | `maxFollowCapacity` | ~~55~~ ~~50~~ | 1b (redo) | Superseded 2026-07-17 — see 1c/1d row below (feed-mechanism changes invalidated this run's dynamics). |
| 2026-07-16 | `followProb` | ~~0.01~~ ~~0.13~~ | 1b (redo) | Superseded 2026-07-17 — see 1c/1d row below. |
| 2026-07-16 | `feedAlgoShare` (alpha) | ~~0.85~~ ~~0.15~~ | 1b (redo) | Superseded 2026-07-17 — see 1c/1d row below. |
| 2026-07-16 | `feedHopH` (hop) | ~~4~~ ~~1~~ | 1b (redo) | Superseded 2026-07-17 — see 1c/1d row below. |
| 2026-07-17 | `maxFollowCapacity` | ~~29.3~~ **30** | 1c/1d | Re-calibration triggered by 3 pre-commit feed-mechanism/assimilation changes that landed after the 1b-redo run (`bcGateAssim` made permanent, `rankByVelocity` caching, chrono/For-You `rootPostId` dedup — see `docs/report/2026-07-17-stage1b-redo2-plan.md`). GP+BO's single-seed best point (`max_follow=100, follow_prob=0.01, alpha=0.884, hop=5`, loss=0.072) sat on 3/4 search-box boundaries; widening the box (stage1d) found nothing better, but a 5-seed confirmation showed it fails the opinionAssortativity floor in 4/5 seeds (one seed as low as 0.163) — the same `follow_prob≈0.01` instability the original (pre-redo) Stage 1b hit. This row's value is the best **fully-interior** point instead (5-seed confirmed: gini=0.814±0.024, assort=0.666±0.104, floor cleared 4/5 seeds), chosen over the nominally-lower-loss boundary point because it reliably satisfies the assortativity floor. Raw BO value 29.32 rounded to 30 (user, 2026-07-17) for a clean round-number starting point going into the next phase. |
| 2026-07-17 | `followProb` | ~~0.0145~~ **0.015** | 1c/1d | Same re-calibration. See rationale above — chosen for stability over the boundary point's `follow_prob=0.01` (unstable near this exact value; see structural note below). Rounded from raw 0.01447. |
| 2026-07-17 | `feedAlgoShare` (alpha) | ~~0.763~~ **0.75** | 1c/1d | Same re-calibration, same anchor-point caveat as the superseded 1b-redo row (see Note below — not an experimental fixed value). Rounded from raw 0.763. |
| 2026-07-17 | `feedHopH` (hop) | **4** | 1c/1d | Same re-calibration, same anchor-point caveat. Already integer-valued, no rounding. |

**Methodology note (2026-07-17):** single-seed BO point estimates in this loss landscape are unreliable —
both the boundary and interior stage1c/1d candidates had 5-seed mean losses 10-25x their single-seed
BO value. Future BO stages (Stage 2 in particular) should average 2-3 seeds per evaluated point inside
the loop itself rather than relying on a post-hoc confirmation pass to catch this after the fact.

**Deferred caveat (2026-07-17, user observation, not investigated further this session):**
`max_follow=100` (the rejected boundary point) implies an out-degree cap equal to 10% of the n=1000
population — plausibly unrealistic on its own terms regardless of the assortativity-floor argument
above, and may partly explain why the search kept pushing toward that edge of the box. Not dug into
now; worth revisiting if `max_follow` becomes relevant again (e.g. a robustness check at larger n,
or if Stage 2 pushes back toward that region).

## Note (2026-07-16, updated 2026-07-17): `feedAlgoShare`/`feedHopH` rows above are calibration-time anchors, not experimental fixed values

The `alpha`/`hop` values in the Stage 1b(-redo)/1c/1d rows above were found by including `alpha`/`hop`
in the BO search space jointly with `follow_prob`/`max_follow`, fit to network-structure targets
(Gini/gamma_fit/opinion_assortativity). This predates (1b-redo) or postdates (1c/1d) the 2026-07-16
feed-mechanism review (`docs/report/2026-07-16-feed-mechanism-design-review.md`) that re-confirmed
`research-direction.md` item 6: **α and h are the paper's primary swept experimental factors**, not
nuisance parameters to be calibrated to a single value — locking either in would silently neutralize
the algorithm-reach axis the whole conduit-vs-algorithm question depends on.

**Resolution:** treat `alpha=0.75`/`hop=4` (2026-07-17 rounded values) as the anchor point used to jointly fit
`follow_prob`/`max_follow` (and any later Stage-2 params) to realistic network-structure targets —
those other parameters stay fixed at their calibrated values. The main experiment sweeps `alpha`/`hop`
independently (e.g. `alpha`∈[0,1], `hop`∈{1,2,3,...}) around/away from this anchor, holding everything
else fixed. `stage1c_bo_evaluations.csv`/`stage1d_bo_evaluations.csv` remain valid for that purpose;
this is not a decision to fix `alpha`/`hop` themselves. (The superseded 1b-redo row's `alpha=0.15`/
`hop=1` anchor is no longer current — it was fit under pre-feed-mechanism-fix dynamics.)

## Repost bc-gating (DECIDED 2026-07-17, mechanism change, see `docs/report/2026-07-17-repost-bc-gating-decision.md`)

`Agent.repost()` is now permanently bc-gated (in-bc posts repost at `repostProb`, out-of-bc posts at
a separate `outOfBCRepostProb`, default **0.02**) — the `coupleOutOfBCRepost` toggle (default `true`,
which made the gate a no-op) is removed, same precedent as `bcGateAssim`. Root-caused via code trace:
the original Stage-2 round-0 collapse (`Q_sign_repost` ~0 across all 5 points, see below) was not a
parameter-search problem — the repost mechanism was opinion-blind by construction under defaults, no
point in Stage 2's old 5D box could have fixed it. Sanity-checked post-fix: `Q_sign_repost` at t=15000
went from 0.043 (old code) to 0.109 (new code, same moderate params) to 0.291 (new code, `bc_dec=0.90,
stub=0.9` — still short of the 0.75 target but respondinig strongly to parameters now, unlike before).
`outOfBCRepostProb` is a new free Stage-2 calibration dimension going forward (see below).

**Caveat:** Stage 1c/1d (follow-graph structure calibration) predates this change. Repost dynamics
don't directly drive follow-graph Gini/gamma/assortativity, but could indirectly (repost-driven
exposure -> hostility -> unfollow). Not re-run — flagged as a future robustness check, not blocking.

## Superseded / not yet decided
- `sbm_pin`/`sbm_pout`/`sbm_gamma`/`sbm_deg`: not calibrated — HK is now the calibration-baseline
  network per this session's design discussion; DC-SBM gets only a post-hoc qualitative check.
- Stage 2 (`bcDecRate`, stubbornness, `comfortPpFactor`, `feedCapacity`, `initialPostProb`, and now
  `outOfBCRepostProb`): first attempt aborted after round 0 (uniformly near-zero `Q_sign_repost`,
  root-caused to the repost-mechanism issue above, not a bad parameter draw). Restarting on top of
  the 2026-07-17 (1c/1d) Stage-1b values AND the repost bc-gating fix — in progress.
- Deferred robustness check: re-run with `hk_m=20` and `hk_m=25` (Stage 1a's better-fitting but
  costlier alternatives) once Stage 2 is also done, holding all other calibrated values fixed. Also:
  re-check Stage 1c/1d's follow-graph metrics under the repost bc-gating fix (see caveat above).
- Stage 2's BO loop should evaluate each point over 2-3 seeds rather than 1 (see methodology note
  above) — a design change to make before restarting Stage 2, not after.

## Process note (2026-07-15)
User instruction: before running any calibration sweep, report the parameters and ranges to be
swept and get explicit approval first; record results in a file (this one, plus the dated narrative
report for each stage) rather than only in conversation. Applies to all remaining stages.
