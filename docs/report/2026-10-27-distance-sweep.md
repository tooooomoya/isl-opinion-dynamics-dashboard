# 2026-10-27 — Is the two-camp split under For You produced by opinion-distance weighting?

**Hypothesis (user).** The follow graph splits into two camps under For You because the like / reshare / rewire rules weight opinion distance (bounded-confidence-like role).
**Knobs.** `beta_h`: weight exp(-beta_h |x_i - x_j|) when picking the post to react to and the rewire target (0 = distance ignored; baseline 3).
`like_max_dist`: a like on a post farther than this does nothing (baseline 1.0, noop gate; "none" = 2.0).
**Design (user-approved scope: random and hkshuf starts, both parameters).** `scripts/distance_sweep_run.py`, ids `dsw_<net>_b<beta_h>_d<like_max_dist>_<feed>`.
For You 100 %, rewire ON, standing config otherwise, 20,000 steps, seeds 0-2. Grid beta_h {0,1,3,6} x like_max_dist {0.3,1.0,none}; Chrono control at (0,none), (3,1.0), (6,0.3). 90 runs, 0 failed.
**Metrics.** Q_sign = modularity of the final follow graph for the partition {X<0, X>=0} (0 = no camps, ~0.5 = two disconnected camps); own-side = share of follow edges whose ends share the sign of X (0.5 = none);
disag_norm = mean edge (X_i-X_j)^2 / (2 Var X) (1 = X unrelated across ties). Table: `figures/distance-sweep/distance_sweep_table.csv`; figures in the same folder.

## Result (3 seeds; treat differences < ~0.05 as noise)
- **Yes, the split is controlled by beta_h.** beta_h 0 -> Q_sign ~0 (no camps, own-side 0.47-0.49) at like range 1.0 / none; beta_h 1 -> still ~0 there; beta_h 3 -> Q_sign 0.50, own-side 0.95; beta_h 6 -> 0.50 / 0.96-0.97 and edge disagreement ~0.03. Sharp transition between beta_h 1 and 3, same on both start networks.
- **The like range matters only when beta_h is small.** At beta_h 3-6 the range changes nothing (0.3 vs 1.0 vs none: Q_sign 0.48-0.50). At beta_h 0-1 a tight range 0.3 *creates* partial camps (Q_sign 0.07-0.31, own-side 0.6-0.8) while range 1.0 / none gives none. So a hard cutoff alone is a weaker (and, at beta_h 0, mostly weak) route to sorting than the soft distance weight.
- **Not specific to For You.** Chrono control: Q_sign 0.49 at the baseline cell and 0.50 at beta_h 6 (vs For You 0.50), and ~-0.02 at beta_h 0, on both nets. At baseline the camps are as sharp under Chrono as under For You in this metric, so the metric (sign-based) saturates; earlier assortativity results (For You < Chrono) are not contradicted but this metric cannot separate the feeds.
- Camp *shape* differs with beta_h 6 (snapshots): not two blobs but a continuum / 4 clusters ordered by X (range 0.3), i.e. graded sorting along X, which sign-modularity reports as "two camps".
- Reading of the earlier robustness stage 1: the sign flips of the For You - Chrono contrast at like range 0.3 on HK are consistent with range acting only as a secondary dial.

Caveats: 3 seeds; one rewire cost setting; Q_sign saturates at ~0.5 for any sign-sorted graph; beta_h grid has no point between 1 and 3 (transition location unresolved); interaction with learner speed / costs untested.
Next (needs approval): beta_h {1.5, 2, 2.5} and a For You vs Chrono contrast with a metric that does not saturate (assortativity, disag_norm) at those points.

---
# 2026-10-27 (later) — Mixed feed: 50 % For You + 50 % Trend on hkshuf and ER starts
Run: `scripts/mix_run.py` (ids `baseline_{hkshuf,random}_mix`, standing config, foryou_hop 5, trend_hop 5, 10 seeds, 20,000 steps, 20 runs, 0 failed). Figure: `figures/mix-feed/mix_hkshuf_er.png` (`scripts/plot_mix.py`, same sections as `plot_std.py`, columns = start networks).
Final-graph summary, 10 seeds (X-assort = Pearson r of X over follow edges; Q_sign = sign-modularity; Gini = attention (likes received) Gini, last 5,000 steps; metric differs from the opinionAssortativity of the robustness screen, so not comparable to it):

| Net | Feed | X-assort | Q_sign | attn Gini |
|---|---|---|---|---|
| hkshuf | Chrono / For You / Trend | 0.88 / 0.85 / 0.78 | 0.48 / 0.49 / 0.44 | 0.89 / 0.66 / 0.79 |
| hkshuf | **50/50 mix** | **0.21** | **0.26** | 0.75 |
| random | Chrono / For You / Trend | 0.91 / 0.85 / 0.77 | 0.49 / 0.49 / 0.43 | 0.67 / 0.46 / 0.71 |
| random | **50/50 mix** | **0.15** | **0.31** | 0.62 |

Reading: the mix is NOT between its two components; follow-graph sorting collapses (assort 0.15-0.21 vs 0.77-0.85 for either pure feed) on both networks. Not yet explained (hypothesis, untested: half the feed slots show posts from far-away opinions, which raises the share of cross-opinion followees picked at rewire, and the two rankers' candidate sets do not reinforce one another). Needs a mix-share dial (0, .25, .5, .75, 1) before any claim; 10 seeds, so the gap is far beyond noise, but one mixing point only.
