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

### Result: For You 100 % and Trend 100 % (Holme–Kim, 3 seeds each; hk100_* static, hkrw100_* rewire on)
Means over seeds (last 2,000 steps; Q-table statistics at the end). 70 % rows from the earlier hk_* / hkrw_* runs, chrono for reference.
| run | identity fit | recognition | Gini | feed size | post / like / reshare (/ rewire) | reward spread (sd) | favourite lead / share | post share camp 1 / camp 5 |
|---|---|---|---|---|---|---|---|---|
| static chrono | 0.623 | 0.25 | 0.83 | 6.5 | 46 / 24 / 30 | 0.076 (0.32) | 0.96 / 61 % | 36 / 53 % |
| static For You 70 % | 0.679 | 0.27 | 0.84 | 9.4 | 36 / 29 / 36 | 0.035 (0.31) | 1.18 / 63 % | 34 / 34 % |
| static For You 100 % | 0.674 | 0.27 | 0.84 | 9.6 | 36 / 29 / 35 | 0.030 (0.31) | 1.16 / 64 % | 34 / 33 % |
| static Trend 70 % | 0.638 | 0.26 | 0.86 | 9.4 | 36 / 30 / 34 | 0.028 (0.31) | 1.02 / 61 % | 33 / 35 % |
| static Trend 100 % | 0.644 | 0.25 | 0.86 | 9.8 | 37 / 30 / 34 | 0.051 (0.31) | 0.90 / 59 % | 34 / 42 % |
| rewire For You 70 % | 0.820 | 0.14 | 0.93 | 9.3 | 29 / 21 / 27 / 23 | 0.065 (0.23) | 0.88 / 47 % | 24 / 35 % |
| rewire For You 100 % | 0.810 | 0.15 | 0.92 | 8.4 | 29 / 21 / 27 / 23 | 0.041 (0.25) | 1.09 / 50 % | 25 / 33 % |
| rewire Trend 70 % | 0.808 | 0.14 | 0.93 | 8.8 | 29 / 22 / 26 / 23 | 0.046 (0.23) | 0.90 / 47 % | 24 / 33 % |
| rewire Trend 100 % | 0.778 | 0.14 | 0.93 | 8.8 | 30 / 20 / 25 / 26 | 0.042 (0.29) | 0.86 / 47 % | 25 / 37 % |
- Going from 70 % to 100 % changes almost nothing: identity fit moves by ≤ 0.03 (within the seed sd for static runs), shares of actions are identical to the percent, recognition and Gini unchanged. For You still lifts identity fit by ≈ 0.05 over chrono (static) and Trend by ≈ 0.02.
- Network outcomes with rewire on are also unchanged: assortativity −0.01 → 0.76, zero-follower agents 24 → 50 %, top-1 % share 28 → 36–37 %, ≈ 16 k rewires done out of ≈ 490–540 k chosen (3 %).
- Only visible shift: static Trend 100 % has the most-followed camp posting more (42 % vs 34 % for camp 1) and a somewhat larger reward spread (0.051), still tiny against a single-reward sd of 0.31; one setting, three seeds, not established.
- The reward-parameter sweep has not been resumed.

## 2026-10-13 (late) — Sweep restarted on 100 % For You and 100 % Trend (user: "find any good combination of reward parameters")
The user clarified that the target of the reward-parameter search is the two algorithmic feeds at 100 % each (no chrono). Restarted [scripts/reward_search.py](../../scripts/reward_search.py) with screens `foryou100` (For You 100 %, hop 1) and `trend100` (Trend 100 %, hop 1); the 16 earlier chrono rows stay in the summary file but are not ranked.
- Grid (stage 1, seed 0, Holme–Kim, fixed graph, 20,000 steps, L = 200, τ 0.1): w_fit {1, 0.5, 0.1} × w_rec {1, 2, 4} × m {0.5, 1} × λ_r {2, 0.5} = 36 settings per screen, + the original reward (Q₀ = 7) per screen = 74 runs. The grid is wider than the first plan (w_rec up to 4, w_fit down to 0.1) because the first 16 runs showed that reward spread between actions barely moves with the milder values.
- Stages 2 and 3 as before (top-4 with seeds 1, 2; top-2 with rewire on). Driver log `logs/rsearch/driver2.out` ends with `RSEARCH_DONE`.

## Results (finished 00:48; 74 stage-1 runs + 8 stage-2 + 4 stage-3; table `results/rsearch/ranking.csv`)
Setting names: w_fit / w_rec / m (share of the fast term) / λ_r. All on Holme–Kim, fixed graph unless "rewire on", post life 200, 100 % algorithmic feed, hop 1, Q₀ = 10·(w_fit + w_rec).

**Top settings, seeds 0–2 (mean ± seed sd)**
| setting | reward spread | captured gain | recognition | identity fit | favourite share (chance 0.33) | feasible |
|---|---|---|---|---|---|---|
| For You 100 %, 0.1 / 4 / 1 / 0.5 | 0.119 ± .002 | 0.091 ± .008 | 0.53 | 0.67 | 0.35 | 3/3 |
| Trend 100 %, 0.1 / 4 / 1 / 0.5 | 0.117 ± .005 | 0.083 ± .008 | 0.52 | 0.65 | 0.35 | 3/3 |
| For You 100 %, 0.1 / 4 / 1 / 2 | 0.098 ± .013 | 0.077 ± .002 | 0.42 | 0.67 | 0.35 | 3/3 |
| For You 100 %, 0.5 / 4 / 1 / 2 | 0.082 ± .010 | 0.074 ± .009 | 0.42 | 0.67 | 0.34 | 3/3 |
| original reward, Q₀ = 7 (single seed) | 0.125 (For You) / 0.151 (Trend) | 0.081 / 0.120 | 0.27 / 0.25 | 0.68 | 0.63 / 0.59 (locked in) | yes |
| **rewire on**, For You 0.1 / 4 / 1 / 0.5 (2 seeds) | **0.249** | **0.127** | 0.27 | 0.82 | 0.27 (chance 0.25) | 2/2 |
| rewire on, For You 0.5 / 4 / 1 / 2 (2 seeds) | 0.187 | 0.103 | 0.21 | 0.83 | 0.27 | 2/2 |

**Main effects (mean over the 36 grid settings per feed, seed 0; spread / captured)**
- w_rec: 1 → 0.019 / 0.026 (For You), 2 → 0.038 / 0.043, **4 → 0.073 / 0.061** (Trend: 0.013 / −0.007, 0.029 / 0.014, 0.055 / 0.040). Monotone; 4 is the edge of the grid.
- m (fast term only): 1 beats 0.5 (0.054 vs 0.033 spread for For You).
- w_fit: smaller is slightly better (0.1: 0.048, 0.5: 0.043, 1: 0.038); a weak effect.
- λ_r: no consistent effect (0.5 helps Trend's spread, For You's captured gain is a little higher at 2).
- For You ≥ Trend in every cell.

**Reading**
1. The combination that looks best is **strong, saturating recognition and weak similarity**: w_rec = 4, m = 1, small λ_r (0.5), w_fit = 0.1 (For You). It is stable across seeds (spread sd 0.002).
2. It is not good enough by the criterion fixed in advance (spread ≥ 0.3): the best fixed-graph spread is 0.12 and agents capture ≈ 9 % of the achievable gain. The favourite action takes 35 % of decisions (chance 33 %): with an optimistic start the lock-in is gone but the agents have not learned a clear preference.
3. Only the rewire-on setting comes close (spread 0.25, captured 0.13): when actions can change who follows whom, they change the next reward more.
4. The original reward (Q₀ = 7) shows a similar spread/captured only because it is locked in; its favourite-action share (0.6) is not a learned preference. Q₀ = 10·(w_fit + w_rec) removes that.
5. Limits: single seed in stage 1; the grid edge (w_rec = 4, w_fit = 0.1) is best, so larger w_rec or w_fit → 0 are untested; spread is normalised by the sd of a single reward, which grows with w_rec (≈ 1.9), so the ratio understates the absolute difference between actions (0.23 reward units); an initial Q as high as 50 keeps agents exploring long and may depress "captured" (Q drift ≈ 0.04, near converged).

## 2026-10-14 — Design change: credit likes to the action that made the post (`credit=post`)
**Why.** Diagnosis of the earlier null result: recognition L̃ is a *stock* (likes on all my surviving posts, up to `dead_after` steps back), added to every visit's reward. A like that arrives now was produced by a post made many visits ago, and by an action (POST/RESHARE) that need not be the one just taken; so the reward an action is paid has almost no relation to what the action did. Rescaling the reward (the 10/13 sweep) cannot fix a mismatch in *which action gets paid*.

**What changed** (code: `Agent.settleCredits/registerCredit`, `Post.likesInHorizon`, params `credit`, `credit_horizon`; default `credit=stock` = unchanged behaviour).
- `credit=post`: the visit reward is `w_fit·I` only. Each POST/RESHARE registers its new post; once the post is older than H steps, `w_rec·L̃(likes it got within H steps)` is added to Q(s,a) of the (state, action) that made it (`Q += η·g`). Each POST/RESHARE decision yields exactly one such update, so Q(s,a) → E[immediate + γV] + E[credited recognition] (no drift). LIKE/REWIRE get no recognition reward (they create no post of mine). State bins still use the recognition stock.
- Logging: the credited amount is added to that (s,a)'s reward total in `td_log.csv` (meanR = immediate + credited). The logged reward variance covers only the immediate part, so `spread` (÷ sd) is overstated in this mode; read `captured`, `justified`, `rewardMean` instead.

**Check** (`scripts/credit_compare.py`; For You 100 %, HK, static, w_fit = w_rec = 1, m = 0.5, λ_r = 2, Q₀ = 20, τ = 0.1, seeds 0–2, 20,000 steps):
| arm | mean reward per decision post / like / reshare | captured gain | justified (chance 0.33) | like share | median Q lead |
|---|---|---|---|---|---|
| stock | 0.95 / 0.95 / 0.95 | 0.02 | 0.34 | 0.32 | 0.05 |
| post, H = 50 | 0.76 / 0.71 / 0.76 | 0.20–0.22 | 0.34–0.36 | 0.30 | 0.065 |
| post, H = 200 | 0.78 / 0.72 / 0.78 | 0.24–0.26 | 0.35–0.37 | 0.29 | 0.067 |
- Under `stock`, the three actions' mean rewards agree to < 0.01 (the earlier null). Under `post`, like pays ≈ 0.05 less than post/reshare, consistently over the 3 seeds; agents take it slightly less often (like share 32 % → 29–30 %).
- But the effect is small: median Q lead ≈ 0.065 against τ = 0.1, favourite share still ≈ chance (0.34), `justified` still ≈ chance. POST and RESHARE remain indistinguishable (identical mean reward to 0.01). So attribution removes the *mismatch* but the credited signal is too weak (a post collects few likes in H steps) to produce a clear learned preference at this τ and w_rec.
- Not established: whether larger `w_rec`, lower τ, or a longer H turns this into a clear preference; that is the next sweep, now meaningful because the reward pays the actions that earned it. Seeds 0–2, one config.

**Supersedes** the plan to resume the 10/13 grid under the stock reward; resume it (reduced) under `credit=post`.

### Result: `credit=post` sweep (user-approved grid; `scripts/credit_sweep.py`)
Grid: w_rec {1, 2, 4} × τ {0.1, 0.05} × H {50, 200, 500}, For You 100 %, HK static, seeds 0–2 (54 runs, all feasible). Means over seeds.
| w_rec | reward(like) − reward(post) | captured (H 50 / 200 / 500) | like share | median Q lead (top − 2nd) | justified |
|---|---|---|---|---|---|
| 1 | −0.05 … −0.065 | 0.21 / 0.25 / 0.26 | 0.29–0.30 | 0.055–0.067 | 0.35 |
| 2 | −0.09 … −0.12 | 0.24 / 0.29 / 0.29 | 0.28–0.30 | 0.09–0.10 | 0.35–0.37 |
| 4 | −0.17 … −0.24 | 0.25 / 0.30 / 0.30 | 0.28–0.29 | 0.15–0.18 | 0.35–0.36 |
- τ (0.1 vs 0.05) barely matters. H = 50 is clearly worse than 200; 200 ≈ 500 (likes arrive within ~200 steps).
- The reward gap between like and post/reshare grows linearly with w_rec (to −0.24), but the like share does not fall below ≈ 0.28 and `justified`/favourite share stay at chance (0.35). POST and RESHARE remain indistinguishable (gap ≤ 0.007), so the "median lead" is mostly a post-vs-reshare noise gap, not a real preference.
- Where the preference lives (camps = lowest vs highest-follower fifth of agents; last 5,000 steps; w_rec 4, τ 0.05, H 200): like share 0.33 / **0.18** (stock: 0.33 / 0.33), post share 0.33 / **0.41** (stock: 0.34 / 0.34). The lowest-follower fifth shows no learned preference at all; the highest-follower fifth does, in the direction the credit predicts (post and reshare over like).
- Reading: credit assignment was the missing piece for agents that can earn likes; for agents with few or no followers, almost no post ever collects a like within H, so all actions pay the same and nothing can be learned, whatever w_rec or τ. The population-level metrics (captured, justified, favourite share) average over many such agents and therefore stay close to chance. This is an explanation consistent with the camp split, not separately tested (e.g. by splitting captured/justified by follower count).
- Next options: report these metrics by follower-count group; or give low-follower agents an earnable signal (e.g. a nonzero base rate of likes, or a reward for the feed fit of the post's audience); or accept that the learned preference exists only among agents who have an audience, which is itself a substantive finding for the attention-economy story.

## 2026-10-14 — Identity fit relative to a random feed (user: "just subtract the random expectation, naively")
- New key `fit_mode=relative`: the agent's expected fit under a random feed, B_i = mean similarity to every other agent, is subtracted from the identity fit for **both the state and the reward** (`fit − B_i`; the reported meanIdentityFit stays raw). Computed once at the start (valid while values are fixed, μ = 0). Default `raw` = unchanged. ModelTests: ALL PASS.
- Cross-agent spread of the residual (final step): sd 0.125 (For You), 0.097 (Trend), 0.17 (chrono) vs 0.28 for recognition; mean ≈ 0 for fixed graphs and +0.14 with rewire on (the gain from sorting). State edges for the relative fit are ±0.06 (about the terciles).
- Comparison [scripts/fitmode_compare.py](../../scripts/fitmode_compare.py): For You 100 % and Trend 100 %, HK fixed graph, w_fit = w_rec = 1, m 0.5, λ_r 2, seeds 0–2; raw (Q₀ 20, edges 0.63/0.71) vs relative (Q₀ 15, edges ±0.06). Results below when finished (`FITMODE_DONE` in `logs/rsearch/fitmode.out`).

### Result: raw vs relative identity fit (fm_*, 3 seeds each; w_fit = w_rec = 1, HK fixed graph)
| feed, fit | reward spread | captured gain | justified favourites | favourite share | favourite lead | Q drift | identity fit (raw) | recognition |
|---|---|---|---|---|---|---|---|---|
| For You 100 %, raw (Q₀ 20) | 0.014 ± .001 | 0.023 | 0.34 | 0.337 | 0.051 | 0.044 | 0.667 | 0.283 |
| For You 100 %, relative (Q₀ 15) | 0.013 ± .004 | 0.013 | 0.34 | 0.336 | 0.050 | 0.080 | 0.667 | 0.283 |
| Trend 100 %, raw | 0.012 ± .008 | −0.007 | 0.36 | 0.336 | 0.056 | 0.039 | 0.644 | 0.277 |
| Trend 100 %, relative | 0.014 ± .001 | −0.018 | 0.35 | 0.335 | 0.057 | 0.077 | 0.647 | 0.278 |
- **No difference.** Subtracting the random-feed expectation changes neither the reward spread between actions (≈ 0.013 in all four rows, single-reward sd 0.31–0.32), nor the captured gain, nor the lock-in (favourite share 0.336 = chance), nor the policy of the lowest- vs highest-follower fifth (post 0.33–0.34 in both). The feeds are identical (raw fit and recognition match to the third decimal).
- Why: B_i is a per-agent constant while values are fixed, so it cannot change which action is better for that agent; and the state split changes only how the same decisions are filed, because actions barely change the next state. The mean action values of the actions stay equal either way.
- The relative runs have a larger Q drift (0.08 vs 0.04): their reward is ≈ L (the residual averages ≈ 0), so the true Q is ≈ 3 and Q₀ = 15 is still decaying at 20,000 steps. Use Q₀ ≈ 10 × (largest reward) = 15 only as an upper bound; a longer run or a lower Q₀ would be needed to judge convergence, but this does not change the equal-action result.
- Conclusion: the identity-fit baseline is a sensible definition (it removes the agent-trait part) but it is not a lever for making actions matter; the reward still hardly depends on the action. Candidate levers remain making actions change the next reward more (rewire on, delayed credit to the posting action as in the credit=post work) rather than reshaping the two terms.

## 2026-10-14 — Rewire ON: does liking pay only under For You? (user)
Reasoning (user): a like changes the liker's environment only when For You is on (a like pulls the platform's estimate X̂ toward the liked post), so without liking an agent cannot build a feed close to itself; with Trend a like has no effect on the liker's later feed. With rewire on, the agent can also reshape its follow list, so For You (like → X̂ → feed) and rewire (follow list → chrono-like content) both give actions a route to the next reward.
Run: [scripts/rewire_like.py](../../scripts/rewire_like.py), For You 100 % vs Trend 100 % (hop 1), rewire on, HK, seeds 0–2; two reward settings S1 (original weights, Q₀ 20) and S2 (best of the sweep: w_fit 0.1, w_rec 4, m 1, λ_r 0.5, Q₀ 41). Looking at: reward spread and captured gain, the like share and its Q relative to post/reshare, per-agent relation between like share and the agent's identity fit, and the platform's estimate error (estError). Results below when finished (`RLIKE_DONE` in `logs/rsearch/rewire_like.out`).

### Result: rewire ON, For You 100 % vs Trend 100 % (rl_*, 3 seeds each; HK start)
| feed, setting | reward spread | captured | mean reward post / like / reshare / rewire | shares post/like/reshare/rewire | identity fit | recognition | assort. |
|---|---|---|---|---|---|---|---|
| For You, S1 (1,1) | 0.057 | 0.036 | 0.968 / 0.953 / 0.966 / 0.954 | 28/24/25/23 % | 0.82 | 0.14 | 0.85 |
| Trend, S1 | 0.081 | 0.202 ± .045 | 0.898 / 0.910 / 0.917 / 0.890 | 28/22/23/26 % | 0.77 | 0.14 | 0.85 |
| For You, S2 (0.1/4/1/0.5) | 0.242 | 0.127 ± .001 | 1.415 / 1.004 / 1.324 / 1.012 | 30/22/26/22 % | 0.83 | 0.27 | 0.84 |
| Trend, S2 | 0.222 | 0.040 ± .013 | 1.378 / 0.995 / 1.296 / 1.036 | 31/20/24/25 % | 0.77 | 0.27 | 0.85 |
- **Hypothesis "liking pays only under For You" is not supported.** The mean reward of a like is the same under For You and Trend (S2: 1.004 vs 0.995; S1: 0.953 vs 0.910 with no consistent sign), and the like share is not higher under For You (22 % vs 20 % in S2, 24 % vs 22 % in S1). Per agent, the like share is unrelated to the agent's relative identity fit (correlation +0.01 to +0.03 for both feeds).
- With the recognition-heavy reward S2, posting and reshare pay about 0.3–0.4 more than like and rewire (the spread 0.22–0.24, rewire on). That is the structure the reward gives (a post can collect likes); like and rewire pay ≈ 1.0. Captured gain is higher under For You (0.127 vs 0.040), i.e. agents take the better action more often there; the shares barely move (post 30 % vs 31 %), so this is a state-wise effect, small in absolute terms.
- Rewire on raises the spread over the fixed graph (S1: 0.057–0.081 vs 0.014), but not through liking.
- Likely reasons liking does not pay under For You: ρ_L = 0.05 moves X̂ only slowly; the platform's estimate is also moved by reshares; in S1 the identity-fit term is the same size for every action to within ~0.015; in S2 it is down-weighted to 0.1.
- Next if wanted: raise ρ_L (0.2–0.3), report estError per agent against like activity, and use a large w_fit with relative fit so the only action-dependent term is the feed closeness.

## 2026-10-14 — Stronger like influence under For You (user)
Decision: raise the platform-estimate update weights a lot and set **ρ_R = ρ_L** (before: ρ_L 0.05, ρ_R 0.10), and raise the For You sharpness β_F (before 3) a lot; **reshare stays** as an action.
Run [scripts/like_strength.py](../../scripts/like_strength.py): For You 100 % (hop 1), rewire on, HK, L = 200, seeds 0–2, ρ ∈ {0.15, 0.3, 0.5} × β_F ∈ {10, 25} × reward {S1 original weights, S2 w_fit 0.1 / w_rec 4 / m 1 / λ_r 0.5} = 36 runs; references: `rl_foryou100_S1/S2` (ρ_L 0.05, ρ_R 0.10, β_F 3). Questions: does the mean reward of a like rise relative to post / reshare / rewire, does the like share rise, does a high-like agent get a closer feed (correlation of like share with relative identity fit), does the platform's estimate error fall faster? Results below (`LSTR_DONE` in `logs/rsearch/like_strength.out`).

## 2026-10-14 Like-strength result (scripts/like_strength.py, 36 runs)
ρ_L=ρ_R ∈ {0.15,0.3,0.5} × β_F ∈ {10,25} × reward S1/S2 × 3 seeds (For You 100%, rewire on, HK, L=200).
Result: no effect. Mean reward(like) − reward(post) = −0.016 (S1) / −0.40…−0.45 (S2), same as the ρ=0.05, β=3 reference (−0.015 / −0.41);
like − rewire ≈ 0 (S1) to −0.04 (S2). Like share 0.22–0.24, spread (S1 0.06, S2 0.24), captured gain, assortativity (0.84–0.85) and identity fit (0.82) are unchanged.
Conclusion: strengthening the like→X̂ feedback and sharpening For You does not make liking pay; the bottleneck is not the feedback strength
(identity fit is already saturated at 0.82 by the network/homophily itself, so the feed can hardly be made "closer"). Supersedes the hope that ρ_L/β_F is the lever.

## 2026-10-15 Production cost (scripts/cost_run.py) and action-share figures
Cost: reward of a post decision −0.5, of a reshare decision −0.25 (cost_post, cost_reshare; like and rewire free). Setting: bandit, For You 100 % hop 5, ρ_L=ρ_R=0.3, β_F=10, w_fit=w_rec=5, like_max_dist 0.3, 3 seeds.
Figure docs/report/figs/action_ratio_cost.png (scripts/plot_action_ratio.py): action share over time and in the converged window (last 5000 steps).
Converged shares (post/like/reshare/rewire): no cost, rewire off .35/.32/.33/–; cost, rewire off .08/.68/.24/–; no cost, rewire on .29/.28/.22/.21; cost, rewire on .08/.43/.10/.39.
From now on results are reported with figures of the converged action ratio (user request 2026-10-15).

## 2026-10-15 Design decision: rewire ON and production cost ON are fixed from now on; feed comparison
Decision (user): all further runs use rewire on and cost_post 0.5 / cost_reshare 0.25; the earlier rewire-off / no-cost exploration (results/rsearch etc., sweep scripts, interim figures) was deleted. The conclusions above stay in this log; raw outputs are regenerable from their parameters. Reward-weight, like-strength, reach, bandit-scale and like-range sweeps are therefore superseded by the single configuration below.
Run: scripts/feed_compare.py — Chrono / For You (hop 5) / Trend (hop 5), 100 % each, 3 seeds, bandit, HK, ρ_L=ρ_R=0.3, β_F=10, w_fit=w_rec=5, like_max_dist 0.3, L=200, 20,000 steps.
Figure: docs/report/figures/feed-compare-2026-10-15/feed_compare.png (scripts/plot_feed_compare.py).
Follow-network summary (final, 3-seed mean; chrono / For You / trend): X-assortativity .83/.90/.77; mean |Δx| over follow edges .24/.17/.28; max in-degree 527/383/633; in-degree Gini .93/.92/.96.

## 2026-10-15 (later) Rewire cost added (cost_rewire = 1.0) and identity fit / recognition panels
Reason: with cost only on post/reshare, rewire took 19–60 % of actions in the converged window. cost_rewire (new, default 0) is subtracted from the reward of every rewire decision, executed or not. feed_compare.py now uses cost 0.5 / 0.25 / 1.0 (post / reshare / rewire); old fc_ runs deleted and rerun.
Result: rewire falls to ≈2–3 % of actions in every feed; like becomes the dominant action for low-follower agents (0–4 followers: like 55–81 %). Follow-network (chrono / For You / trend): X-assortativity .72/.85/.62, mean |Δx| .32/.21/.37, max in-degree 702/478/760, Gini .91/.92/.94.
feed_compare.png gained panel B2 (identity fit and recognition by follower group, final snapshot). Rewire cost 1.0 is a single untested level and probably too high.

## 2026-10-16 Reshare credit split (reshare_alpha = 0.5)
Decision (user): likes on a reshared copy are credited α to the original's author and 1−α to the resharer (recognition only; credit=post mode unaffected; default α=0 = old behaviour). Implemented via Post.copyLikes and Agent.recognition; test testReshareAlphaSplit passes (all tests green). Caught a positional-argument swap in SimParams.from during the test.
feed_compare rerun with α=0.5 (cost 0.5/0.25/1.0): figure feed-compare-2026-10-15/feed_compare.png; the α=0 version is kept as feed_compare_alpha0.png.
Follow-network (chrono / For You / trend), α=0 → α=0.5: X-assortativity .72/.85/.62 → .71/.88/.62; mean |Δx| .32/.21/.37 → .32/.19/.37; max in-degree 702/478/760 → 731/437/735.
Action mix of low-follower agents: like rises under For You (0 followers: 69 → 89 %); high-follower posting under Chrono stays highest (5–19 followers: post 48 → 63 %).

## 2026-10-16 (later) Reshares join the original author's candidate pool (notify_original)
Decision (user): simplest form — reshares of my own posts are added to my candidate pool (hop-exempt) and each stream's own selection rule applies; no dedicated slots. Likes by the original author on a copy are credited fully to the resharer and never to the author (no self-credit); other likes on a copy split α=0.5 (resharer 1−α, author α). Tests green (testNotifyOriginal, testReshareAlphaSplit).
feed_compare rerun (cost .5/.25/1.0, α .5, notify on): figure feed_compare.png; previous no-notify version feed_compare_alpha05_nonotify.png.
Follow network (chrono / For You / trend), no-notify → notify: X-assortativity .71/.88/.62 → .72/.88/.77; mean |Δx| .32/.19/.37 → .32/.19/.28; max in-degree 731/437/735 → 629/393/629.
Action mix: under Trend low-follower agents reshare more (0 followers 20 → 30 %) and post a little more; under Chrono high-follower (20–49) agents post 55 → 70 %.

## 2026-10-16 (later) Rewire-off comparison and noisy expression of X (post_noise)
Rewire-off feed comparison (fcoff_*): figure feed_compare_rewire_off.png. The follow network is the same static graph in all feeds (X-assortativity −0.01, mean |Δx| 0.69, max in-degree 466, Gini 0.83). Low-follower agents mostly like (For You 79–85 %, Trend 66 %), high-follower agents post under Chrono (59–62 %) but much less under For You/Trend (15–22 %).
Decision (user): add noise to the X expressed in original posts, x_post = clip(x_i + N(0, post_noise²), −1, 1), to make rewiring less able to find homophilous agents. Because rewire used true opinions, post_noise > 0 also switches rewire (candidate weights and the closer-than-front gate) to the observed opinion = mean X of the agent's own posts so far (0 before the first post). Default 0 = old behaviour; tests green (testPostNoise).
Run: scripts/feed_compare.py on 0.3 (ids fcn_*), figure feed_compare_noise.png.
Result (fcn_*, post_noise 0.3, rewire on): the follow network is essentially unchanged versus exact posts — X-assortativity chrono/For You/trend .72/.87/.77 (exact: .72/.88/.77), mean |Δx| .32/.21/.30 (.32/.19/.28), max in-degree 637/434/648. Action mix shifts slightly (Trend: 0–4-follower agents post a bit more, 9–15 % vs 6–10 %; recognition now reaches 0-follower Trend agents). Noise sd 0.3 does not weaken rewire-driven homophily: rewire is rare (≈2–3 % of actions) and an agent's mean post X converges to its true X after a few posts.
Noise sweep (fcn0.3/0.5/0.7_*, rewire on): follow-network X-assortativity (chrono/For You/trend) .72/.87/.77 → .70/.86/.76 → .69/.84/.75; mean |Δx| .32/.21/.30 → .34/.23/.31 → .35/.26/.32. Even at sd 0.7 homophily falls only slightly (For You .87 → .84); the ordering For You > Trend > Chrono and the in-degree shape are unchanged. Figures: feed_compare_noise{,0.5,0.7}.png; all figures regenerated 2026-10-16. The fcn_ runs were renamed fcn0.3_.

## 2026-10-16 (later) Rewire without the similarity gate (rewire_gate=false)
Decision (user, trial): remove the check "candidate strictly closer than the oldest followee"; the drawn candidate (weight exp(−β_H|Δx|) over unfollowed originators in the feed) always replaces the oldest followee. Parameter rewire_gate (default true = old behaviour); test added (all green). Run: scripts/feed_compare.py on nogate (ids fcng_*, exact posts, α .5, notify on, costs .5/.25/1.0); figure feed_compare_nogate.png.
Executed swaps per agent per 20,000 steps (choice count): chrono 26.5 (84), For You 46.6 (66), trend 42.4 (108) — vs 12.6/15.9/14.2 with the gate.
Follow network (chrono / For You / trend), gated → ungated: X-assortativity .72/.88/.77 → .42/.49/.26; mean |Δx| .32/.19/.28 → .47/.44/.56; max in-degree 629/393/629 → 817/785/965; Gini .91/.92/.95 → .94/.96/.98. Homophily collapses and hubs concentrate (star-like snapshots, esp. trend), the pattern the gate was introduced to prevent.

## 2026-10-16 (later) Decision: rewire gate stays removed; follower inequality vs. data
Decision (user): keep rewire without the similarity gate (only For You then produces a homophilic community, as in the real world). Standing config recorded in memory (project-standing-experiment-config).
In-degree (follower) inequality: initial HK network Gini 0.83 (top 1 % of accounts hold 28 % of follows, top 20 % hold 86 %); final gated 0.91–0.95 (top 1 %: 36/23/35 % for chrono/For You/trend); final ungated 0.94/0.96/0.98 (top 1 %: 45/44/56 %, top 20 %: 97–100 %). Reference: Zhu & Lerman (2016, arXiv:1601.07200) report a follower-count Gini ≈0.94 in a Twitter sample, with the top 20 % of users holding >96 % of followers and the top 1 % about 60 %.
Hubs (≥5 followers) by |X| group in the ungated run: For You — followers per hub 106/114/163 (neutral/moderate/extreme), followers within |Δx| ≤0.3 (the like range) per hub 59/64/80; Trend — 293/380/285 and 117/155/103; recognition is similar across groups (saturated, ≈0.75). Consistent with, but not a test of, the idea that extreme hubs in For You have more reachable likers; likes received per post were not logged.

## 2026-10-16 (later) Standing config on random and SBM start networks (fcng_random_*, fcng_sbm_*)
Same standing config (no gate, cost .5/.25/1.0, α .5, notify on, hop 5, 3 seeds) with network=random (p .015) and network=dcsbm (K=4, mean degree 15 via sbm_deg=15; communities are independent of X). Figures feed_compare_random.png, feed_compare_sbm.png. For You runs on these graphs take ≈40 min each (hop-5 reach covers ~all agents). Result folder names are now truncated + hashed when the tag exceeds 190 chars (SBM runs hit the 255-char limit).
Follow network final (chrono / For You / trend): random — X-assortativity .91/.95/.78, mean |Δx| .18/.14/.27, max in-degree 150/276/287, Gini .69/.85/.86; SBM — .79/.92/.63, .23/.18/.31, 150/346/432, .84/.91/.93; (HK ungated: .42/.49/.26, .47/.44/.56, 817/785/965, .94/.96/.98).

## 2026-10-16 (later) Computation fix (For You candidate cap) and relative identity fit as standing settings
Speed: For You on dense reach (random/SBM) took ≈40 min per run because every visit weighted every live post of every reachable author. New foryou_cand_max (default 0 = off): after the hop filter, a uniform random sample (reservoir) of at most that many candidates is kept and only those are weighted (reshares of the reader's own posts are never capped). Tests green (cap size, uniform sample). Standing value 300.
Identity fit: decision (user) to subtract its random-feed expectation b(x) = 1 − (1 + x²)/4 (0.75 at X = 0, 0.50 at |X| = 1; extreme agents are allowed to be less comfortable). New fit_baseline=analytic with fit_mode=relative; the reward becomes w_fit·(fit − b(x)) + w_rec·rec − cost; figures show the excess.
Standing run: scripts/standard_run.py (ids std_<net>_<feed>) on hk / random / sbm; plot_feed_compare.py OUT.png std:<net>. These supersede the fcng_* runs (raw fit, uncapped For You).
Results (std_hk/random/sbm_*, 3 seeds; chrono / For You / trend). X-assortativity: HK .41/.41/.16, random .92/.94/.78, SBM .79/.91/.65. Mean |Δx|: .48/.48/.62, .17/.16/.27, .25/.20/.32. Max in-degree: 802/841/981, 157/317/282, 200/344/447. In-degree Gini: .94/.97/.98, .70/.85/.86, .86/.91/.94. Mean identity-fit excess (neutral/moderate/extreme): HK chrono .01/.07/.13, For You −.02/.07/.15, trend 0/.01/0; random For You .18/.23/.34, chrono .14/.21/.27, trend .03/.02/0; SBM For You .17/.22/.27, chrono .09/.10/.19, trend −.12/−.10/−.05. Executed rewires per agent 27–71 per run.
Ablation on HK For You (abl_*; X-assortativity, excess fit neutral/moderate/extreme): raw no cap (old) .49, .02/.12/.21; raw + cap 300 .49, −.04/.08/.22; relative no cap .37, −.01/.09/.18; relative + cap .41, −.02/.07/.15. The cap alone changes little; the relative-fit reward is what removed For You's extra homophily on HK (.49 → ≈.4, equal to chrono). Wall time per network stage ≈ 9 min (HK), 21 min (random), 19 min (SBM) vs. ≈45 min before for the For You runs on random/SBM.

## 2026-10-19 Speed-up of the For You pipeline; explicit hop term in the For You score
Profile (jcmd thread dumps, ≈70 samples, random start): after the reservoir cap, the time went to (i) all-sources BFS with HashMaps for the 5-hop reach (≈30 %), (ii) the scan over all live posts (still, reservoir needs a draw per valid post), (iii) per-step network-wide metrics (interaction/opinion assortativity, cross-cutting, disagreement; 35–45 %). Changes: reach distances as byte[][] arrays; candidate sample drawn by rejection from the live-post array when the reach covers ≥ 1/4 of agents (cost ≈ cap, uniform over the hop-filtered pool; small reach keeps the exact scan); the seven network-wide step metrics recomputed every metrics_heavy_every = 25 steps and carried forward (cheap per-step counters exact; default 1 = old). Tests green (cap size, uniform sample, hop term).
Check (3 seeds, For You, standing config): scan-based vs sampled — HK X-assortativity .41 vs .42, excess fit .15 vs .17 (extreme), shares post/like/reshare/rewire identical to the second decimal; random .94 vs .94. Wall time per run: HK 207 s → 101 s, random 1251 s → 169 s (7.4×).
Hop term (user request): the For You weight was already similarity × decay(hop) (feed_decay_mode exp, λ 0.11: 1 hop ≈ 1 % of an opinion unit at β_F = 10, i.e. invisible; hop 5 → 0.64). New foryou_hop_lambda makes it explicit and tunable: score = exp(−β_F|X̂−X|) · exp(−λ(d−1)); λ = 0.5 means one hop costs as much as 0.05 in |X̂−X| (hop 5 → 0.14). Applied in both the exact and the sampled path (test: selection frequency ratio 1:2:3 hops = 1 : e^−0.7 : e^−1.4 within noise). Trend keeps its own acceptance decay. Standing runs now use λ = 0.5 (ids stdh_*; the earlier std_* runs used λ 0.11).
Result of λ = 0.5 for For You (stdh_* vs std_*, 3 seeds; Chrono and Trend identical because they do not use the term): X-assortativity HK .41 → .45, random .94 → .95, SBM .91 → .79; mean |Δx| .48 → .46, .16 → .15, .20 → .26; max in-degree 841 → 815, 317 → 295, 344 → 435; identity-fit excess (neutral/moderate/extreme) HK −.00/.11/.21 (was −.02/.07/.15), random .18/.24/.34 (was .18/.23/.34), SBM .14/.17/.16 (was .17/.22/.27). The SBM drop comes from two of three seeds (per-seed assortativity .85→.53, .94→.94→.95, .94→.88; SBM seeds differ a lot, 5.7k–14.5k edges), so it is not a reliable effect with n = 3. Hypothesis (untested): in the SBM the blocks are independent of X, so favouring graph-near authors pulls the feed toward structure rather than opinion. Figures: stdh_{hk,random,sbm}.png.

## 2026-10-19 (later) New run outputs and a fuller results figure (scripts/plot_std.py)
New logging in the model (no effect on dynamics): follow-edge snapshots at t0 / T/2 / final (degrees/edges_t0|mid|final.csv); who liked / reshared whose post over the last 5,000 steps (metrics/reactions_conv.csv: type, actor, author, count); lifetime, likes and reshares of every post created in the last 5,000 steps and evicted before the end, split original vs reshared copy (metrics/post_life_hist.csv).
Figure additions (user request): initial network + mid-run and final follow graphs per feed (layouts chained from the initial one so node movement shows rewiring); repost graph of the converged window with edges filtered by weight (smallest threshold ≥ 2 reshares that keeps ≤ 2,500 pairs); post share by the 5 opinion classes of the author, accumulated over the last 5,000 steps, with the post counts; attention economy: post lifetime CCDF, reshares / likes received per agent, breadth of attention.
Attention-breadth definition (mine; I could not retrieve the full text of Weng et al. 2012, Sci. Rep. 2:335, to check their entropy measure — to be reconciled): for each agent, the Shannon entropy of its likes + reshares in the converged window over (AE3) the authors reacted to — shown as the effective number of authors exp(H) — and over (AE4) the 5 opinion classes of those authors, in bits (max log2 5 = 2.32). Entropy over stories is not used because the see-once rule makes every reaction go to a different story.
Runs stdh_* regenerated with the new outputs (same config as before).
Results (stdh_*, 3 seeds; per network and feed: original posts never reacted to / agents without a reshare received / median effective number of authors / median viewpoint entropy neutral-moderate-extreme in bits / post share by author class −1…−0.6 … 0.6…1 / original posts and reshares in the last 5,000 steps):
HK chrono 65 % / 56 % / 11 / 1.56-1.35-1.03 / 20-20-20-20-20 / 150k, 153k; HK For You 58 % / 82 % / 13 / 1.72-1.35-0.99 / 22-20-18-19-20 / 58k, 115k; HK trend 94 % / 95 % / 14 / 2.06-1.99-1.88 / 24-19-19-18-20 / 70k, 181k.
Random chrono 47 % / 33 % / 14 / 0.94-0.87-0.68 / 21-21-19-20-19 / 207k, 117k; random For You 43 % / 42 % / 94 / 0.72-0.71-0.48 / 26-18-14-23-18 / 45k, 162k; random trend 96 % / 67 % / 128 / 2.10-1.84-1.58 / 23-18-18-19-22 / 37k, 123k.
SBM chrono 61 % / 59 % / 10 / 1.01-0.97-0.82 / 21-20-18-20-20 / 191k, 125k; SBM For You 62 % / 69 % / 49 / 0.72-0.56-0.67 / 20-18-16-26-20 / 52k, 154k; SBM trend 95 % / 85 % / 61 / 1.75-1.62-1.46 / 25-18-17-20-21 / 106k, 96k.
Figures: docs/report/figures/feed-compare-2026-10-15/stdh_{hk,random,sbm}.png (generated by scripts/plot_std.py).

## 2026-10-19 (later) Figure update: post-share pies, apparent polarization, P(S) of attention breadth
Fig. 4d of Weng et al. 2012 (Sci. Rep. 2:335; text retrieved through Europe PMC) is the probability distribution P(S) of the breadth of user attention, S = −Σ_i f(i) log f(i), f(i) = share of a user's tweets about meme i. plot_std.py now has (P) pies of original posts by the author's 5 opinion classes over the last 5,000 steps, original vs reshare share of all posts, and apparent polarization (dashboard: exposureOpinionVar − opinionVar, mean over the window); (AE5) P(S) per feed, with f(i) = share of an agent's likes + reshares going to author i (nats) or to the opinion class of the author (bits). The 'meme' is the author or class because each reaction goes to a different post (see-once).

## 2026-10-19 (later) Apparent polarization as a ratio, P(S) as a share per bin, 10 seeds
Decision (user): apparent polarization in the figures = exposureOpinionVar / opinionVar (ratio, 1 = feeds as spread as the population), mean over the last 5,000 steps (the dashboard still shows the difference). AE5: y is now the share of agents in each bin (sums to 1); the earlier values above 1 were probability densities (histogram normalised by bin width, 0.175 nats / 0.077 bits), not probabilities. The reference to Weng et al. was removed from the figure text. All standing runs extended to 10 seeds per feed and network (standard_run.py, seeds 0–9; seeds 0–2 reused).

## 2026-10-20 Why reshared copies have a longer lifetime tail than originals (AE1, random start)
Share of posts with extra life (lifetime − 201) ≥ t, 10 seeds (orig / copy): Chrono ≥30: 0.00001 / 0.0019, ≥100: 0 / 0.00008; For You ≥100: 0.446 / 0.393, ≥1000: 0.029 / 0.007; Trend ≥1000: 0.0031 / 0.0057 (never-reacted: Chrono 47 % / 75 %, For You 44 % / 46 %, Trend 96 % / 98 %).
Ablation (abl2_*, 2 seeds, notify_original = 0): the Chrono copy tail disappears (≥30: 0.0019 → 0.0000), the Trend copy tail is unchanged (≥1000: 0.0056 → 0.0058). Chrono mechanism: a chrono feed draws only from a FIFO cache of 10 followee posts, so an original is shown within a few steps and dies by extra life ≈ 25; with notify_original the copy waits in the original author's pool (up to 50 entries, until seen or dead; the author visits every ≈10 steps and the pool competes with the cache for 10 slots), so the author's like can arrive tens of steps later and refreshes the copy. Trend: not caused by notify; mechanism not established (hypotheses: per-post counting — one story has one original but many copies — and lock-in at the top of the absolute-velocity ranking).

## 2026-10-20 (later) Chrono: notified copies go through the FIFO cache, not the extra pool
Decision (user): the Chrono stream no longer reads the notify pool. A reshare of my post is delivered to my postCash (the 10-slot FIFO of delivered posts, reset after each of my turns) exactly like a followee's post, at the end of the step (OpinionDynamics, skipped if I already follow the resharer, so no double delivery). Supersedes the 50-entry backlog for Chrono. For You still reads the notify pool (hop-exempt, uncapped); Trend is unchanged (it ranks originals only, so the pool is inert there). Rationale: the pool gave copies persistence and priority no ordinary post has. Consequence: a copy that is not drawn on my next visit is dropped, so the Chrono copy tail (abl2 finding above) should shrink; not yet re-measured. testNotifyOriginal updated; tests green.

## 2026-10-20 (later) Chrono rerun after the FIFO-cache change
Reran stdh_{hk,random,sbm}_chrono (10 seeds each, 20,000 steps, standing config; ~45 s per run; no failures) with notified copies delivered through the postCash instead of the extra pool. For You and Trend runs were not recomputed (they still use the pre-change code; For You's notify pool is unchanged, Trend is unaffected). Old chrono summary lines were removed (backup: results/rsearch/summary.jsonl.bak-20261020). Figures stdh_{hk,random,sbm}.png in figures/feed-compare-2026-10-15/ regenerated; plot labels now say 10 seeds (they said 3 although all seeds were read). Log: logs/std_chrono_rerun.out.

## 2026-10-20 Start networks regulated to the same mean degree
Check (user question): initial directed edges per run — Holme–Kim exactly 15,000 (15 followees each), random (p = 0.015) 14,871–15,178 (mean 15.00, out-degree sd 3.9), SBM (sbm_deg = 15) only 5,723–14,546 (mean 10,846, i.e. mean degree 10.8, very different per seed): the SBM was not regulated. Fix: DC-SBM edge probabilities are now scaled by a calibrated global factor so the expected edge count equals n × target, and every start network can be forced to exactly n × start_deg directed edges (Network.enforceEdgeCount: random removal / addition of the small remainder; test green). Random and SBM stdh_* runs deleted and redone with start_deg = 15 (10 seeds); Holme–Kim is unchanged (already exactly 15). Earlier random/SBM results in this log (mean degree 10.8 for SBM) are superseded.

## 2026-10-20 (later) like_max_dist = 1.0 and full rerun
Decision (user): turn the like range to |Δx| ≤ 1.0 (was 0.3 in all standing runs so far). All stdh_* runs (Holme–Kim, random, SBM; 10 seeds each) were deleted and rerun with like_max_dist = 1.0 together with the regulated start degree (start_deg = 15). Earlier standing results (like range 0.3) are superseded.

## 2026-10-20 (later) Gated likes counted (like_gate = noop)
Request (user): show the share of gated likes ("do nothing") as part of the LIKE area in sections A and B. Until now the range gate filtered the candidates (like_gate = filter: if no unliked post in the feed was within the range the LIKE action was unavailable, so a like was never chosen without a target and nothing could be counted). New like_gate = noop: LIKE stays available whenever an unliked post is in the feed, the post is drawn by the similarity weights as before, and if it lies farther than like_max_dist the like does nothing (no like, no life refresh, no platform-estimate update) and is counted (agent_actions.csv column nLikeGated, a subset of nLike). Standing runs now use like_gate = noop with like_max_dist = 1.0; the full set (HK, random, SBM; 10 seeds) was restarted. Figures: hatched part of the LIKE segment with the gated share in brackets; test green (filter vs noop).
