# 2026-10-13 — Reward-parameter sweep (autonomous run)

Driver: [scripts/reward_search.py](../../scripts/reward_search.py) (resumable; summaries append to `results/rsearch/summary.jsonl`, table `results/rsearch/ranking.csv`, run logs `logs/rsearch/`, driver log `logs/rsearch/driver.out` ending with `RSEARCH_DONE`). New model keys: `w_fit`, `w_rec` (reward = w_fit·I + w_rec·L; defaults 1, 1 = the previous reward).

## Request (user)
Sweep the parameters that set the reward from received likes and from X similarity: make the reward **stronger for fewer likes** and **less reactive to X similarity** (taking the average into account); report the seemingly good ones.

## How the request is read
- **Stronger for fewer likes** → recognition L̃ = m·(1 − e^(−ℓ/λ_r)) + (1−m)·min(1, ln(1+ℓ)/ln(1+L_ref)): larger weight `w_rec`, more of the fast term (`m` → 1), smaller `λ_r` (the first like is worth most; with λ_r = 0.5 one like already gives 0.86 of the fast term).
- **Less reactive to X similarity, considering the average** → identity fit varies little around its average (≈ 0.65 ± 0.1), so a smaller `w_fit` shrinks how much similarity moves the reward. A constant offset in the identity term would not change which action is best (it only shifts Q), so only the weight is varied; the other levers (Q₀ and bins) are untouched.
- Optimistic start: Q₀ = 10·(w_fit + w_rec), the largest possible discounted return at γ = 0.9, so every untried action looks at least as good as the truth. One baseline per screen keeps the original Q₀ = 7. (This also removes one cause of the lock-in found earlier.)

## Grid (stage 1, seed 0, Holme–Kim, static graph, 20,000 steps, L = 200, τ 0.1)
Screens {chrono, For You 70 % hop 1} × w_fit {1, 0.5, 0.25} × w_rec {1, 2} × m {0.5, 1} × λ_r {2, 0.5} = 48 runs + 2 baselines (original reward, Q₀ = 7). Stage 2: top-4 settings with seeds 1, 2. Stage 3: top-2 with rewire on (gated), seeds 0, 1.

## What "good" means (fixed before looking at results)
- **spread** = (highest − lowest mean immediate reward among actions) ÷ (sd of a single reward): do the actions pay differently at all?
- **captured** = share of the achievable reward gain that agents take: (reward of what agents did − reward of choosing uniformly) ÷ (reward of the best action in each state − uniform), using each state's population-mean reward per action. 1 = always the better action, 0 = no better than random.
- **justified** = share of agent-state favourites that equal the state's best-paying action (chance 1/3).
- Also reported: favourite lead and share (lock-in), Q drift (converged if ≤ 0.05), post share of the lowest- vs highest-follower fifth, identity fit, recognition, Gini, feed size.
- Feasible: 0 assertion errors; feed ≥ 6 posts and ≤ 15 % empty; recognition in [0.05, 0.9]; Gini ≤ 0.93. Rank: feasible, spread ≥ 0.3, then captured.
- Caveat: a reward with a larger spread makes the learning problem easier by construction; "good" here means the reward design lets agents find and use a better action, not that it is realistic.

## Results
(filled in when the run finishes)

## 2026-10-13 — Interrupted; screens redefined as 100 % algorithmic (user)
The sweep was stopped after 16+ stage-1 runs (chrono only; results in `results/rsearch/summary.jsonl` kept). Interim reading of those chrono runs: with Q₀ = 10·(w_fit + w_rec) the favourite-action lock-in disappears (favourite takes ≈ 33.5 % of decisions = chance, median lead ≈ 0.05), but mean rewards still hardly differ by action (spread ≤ 0.08 of a single reward's sd; captured gain 5–10 %), for all tried weights and recognition shapes. All chrono runs failed the feed-size check (HK chrono feed 5.7 < 6). The user then asked to rerun For You and Trend as **100 % of the feed each** (no chrono slots); the reward sweep should be resumed on that basis (For You 100 %, Trend 100 %) if still wanted.

## 2026-10-13 — Runs: For You 100 % and Trend 100 % (Holme–Kim, 3 seeds each, rewire off and on)
`hk100_foryou`, `hk100_trend` (rewire off) and `hkrw100_foryou`, `hkrw100_trend` (rewire on, similarity-gated), `foryou_share=1.0` / `trend_share=1.0`, hop 1, L = 200, Q₀ = 7, τ 0.1. Results below when finished.
