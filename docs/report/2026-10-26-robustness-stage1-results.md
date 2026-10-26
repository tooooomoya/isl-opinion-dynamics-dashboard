# 2026-10-26 — Robustness check, Stage 1 (one-at-a-time screen, Holme–Kim start)

Design and parameter list: `2026-10-26-robustness-sweep-plan.md`. Data: `robustness_stage1_hk.csv` (means per setting/feed), `robustness_stage1_hk_noise.csv`,
heat-map `figures/robustness_stage1_hk.png`. Code: `scripts/robustness_sweep.py`, `scripts/robustness_analysis.py`. 53 non-baseline settings x 3 feeds x seeds 0-2, last 2,000 steps.
Baseline rerun reproduces the earlier `baseline_hk_*` seeds 0-2 exactly (deterministic).

**Noise yardstick.** Between-seed sd (10 baseline seeds) of the *feed contrast* (a feed's value minus Chrono's, same seed): opinion assortativity 0.050 (For You − Chrono) / 0.036 (Trend − Chrono),
identity fit 0.024 / 0.042, attention Gini 0.003 / 0.002. With 3 seeds the standard error of a contrast is about 0.03 (assortativity). Read |shift| < 0.06 in assortativity as noise (cf. feedback-noise-tolerance).
Baseline contrasts (10 seeds): assortativity For You − Chrono −0.15, Trend − Chrono −0.28; fit Trend − Chrono −0.10, For You − Chrono −0.015; Gini +0.033 / +0.044.

## Findings
1. **Robust (holds in 53/53 settings unless noted):**
   - Attention Gini ordering Chrono < For You < Trend (all 53). Algorithmic feeds concentrate attention; the Gini contrast moves by at most 0.03 across any parameter.
   - Posting share lower under For You and Trend than Chrono (all 53).
   - Trend lowers assortativity vs Chrono (51/53) and vs For You (52/53); Trend lowers identity fit vs Chrono (52/53). Exceptions are only `rewire=off` (assortativity undefined, ~0 everywhere) and, for Trend vs Chrono assortativity, `rewire=gated`.
2. **Fragile: the For You effect on assortativity.** "For You lowers follow-graph assortativity relative to Chrono" holds in 40/53 settings only; it flips sign (For You ≥ Chrono) at `learner=q` (+0.19), `start_deg=30` (+0.20), `rewire` gated (+0.16), `like_max_dist` 0.3 (+0.15) and 0.6 (+0.06), `dead_after` 50 (+0.08) and 100 (0.00), `q_init=0` (+0.05), `q_eta=0.3`, `access_prob=0.05`, `cost` x2, `w_fit:w_rec` 2:8 (+0.02..+0.03). Its size is the most parameter-dependent quantity in the model (range across levels: start_deg 0.43, q_eta 0.25, q_init 0.22, rho 0.21, dead_after 0.21, access_prob 0.19). The sign that matters for the paper-type claim ("homophilic communities form only under For You", user 2026-10-16) therefore depends on the rewire gate (user-chosen: off), on the like range, and on how fast/optimistic the learners are; only the "no gate" setting keeps For You below Chrono.
3. **Most influential parameters overall (by effect on the contrasts and levels):** `rewire` on/off and gate; `start_deg` (density); learning speed/optimism (`q_eta`, `q_init`, `q_tau`; `q_tau`=1 collapses all assortativity to ~0.05-0.2 because choices become near-random); `dead_after`; `rho` (platform's estimate update); `access_prob`; `like_max_dist`; `cost` scale (cost x0 removes the post suppression and cuts assortativity to ~0.19 in all feeds); `learner` (bandit vs state-based Q).
4. **Insensitive (within noise):** `fit_mode`, `notify_original`, `recog_*`, `post_noise`, `reshare_alpha`, `hop` 2/5/10, `fy_beta` 3-30 (mild), `q_eps`, `foryou_cand_max` (the speed approximation shifts For You assortativity by +0.05 (no cap) / +0.08 (cap 100): small but on the edge of noise; sign unchanged).
5. **Scale/convergence caveats.** `n`=500/2000 and `steps`=10k/40k keep orderings but move For You assortativity −0.18 (40k) .. −0.02 (10k): the For You − Chrono gap is still drifting at 20,000 steps (Chrono rises 0.44 -> 0.49, For You falls 0.42 -> 0.31 from 10k to 40k), i.e. the baseline is not at equilibrium for that quantity. HK in-degree skew (`hk_a` 15/60) lifts Chrono assortativity to 0.62-0.68 but leaves For You near 0.5, strengthening the Trend contrast (−0.38..−0.41).
6. **Level effects worth knowing** (not contrasts): lowering `start_deg` to 8 makes everything more concentrated and raises the algorithmic feeds' post share (0.14 / 0.26); `rewire=off` drops Gini (0.81) and lets For You gain fit (+0.19 vs Chrono).

## Limits of this screen
- OAT: no interactions. The sign flips in finding 2 co-occur with parameters that plausibly interact (density x like range x learning speed) — Stage 2 should test pairs.
- 3 seeds, one start network (HK). Random/SBM start networks showed different For You structure earlier (2026-10-21), so robustness there is untested.
- Only summary outcomes (assortativity, Gini, fit, recognition, action shares). Opinion/posting-class (U-shape vs moderate-peak) results from 2026-10-21/22 were not re-screened.

## Proposed Stage 2 (needs approval, not started)
Replicate the 6 most influential parameters (rewire gate, start_deg, q_eta, q_init, dead_after, like_max_dist) on random and SBM starts with 10 seeds, plus a 2x2 grid of start_deg x like_max_dist and q_eta x q_init; and run baseline to 40,000 steps with 10 seeds to settle the For You assortativity drift.

## Addendum (same day): edge-disagreement index added
Request (user): add the polarization index "sum over follow edges of the squared opinion difference". The model already logs it as `disagreement` = mean over directed follow edges i -> j (target hubs excluded) of (X_i - X_j)^2; it is the per-edge mean of the user's sum (the 1/2 of the Dirichlet-energy convention omitted), so it does not grow with the number of edges (start_deg, n).
`robustness_analysis.py` now reads it from each run's `metrics/results.csv` (last 2,000 steps; no rerun needed) and also reports `disag_norm` = disagreement / (2 Var X): 1 = X unrelated across ties, 0 = followers identical to their followees. Columns `disag_*`, `disag_norm_*` in `robustness_stage1_hk.csv`; included in the heat-map.
Baseline (3 seeds) disag_norm: Chrono 0.52, For You 0.74, Trend 0.83 (assortativity 0.48 / 0.36 / 0.23). Seed sd of the contrast: 0.069 (For You - Chrono), 0.056 (Trend - Chrono).
- disag_norm ~ 1 - assortativity whenever followers' and followees' X distributions match (Pearson r vs squared distance), so the two indices agree: sign of the For You - Chrono contrast concordant in 47/53 settings (the 6 discordant ones have both contrasts within noise).
- Same fragility: For You has *lower* disagreement than Chrono (more sorted) in 8/53 settings with |shift| beyond noise in 5-6: `learner=q` (-0.18), `start_deg=30` (-0.16), `like_max_dist` 0.3 (-0.16), rewire gated (-0.15), `dead_after=50` (-0.10), `q_init=0` (-0.07). Trend has higher disagreement than Chrono in 53/53.
- `rewire=off` gives 1.06 in all feeds (no sorting; slightly above 1 because the in-degree-weighted followee distribution differs from the population's).
