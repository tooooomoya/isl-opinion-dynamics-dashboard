# 2026-10-26 — Robustness check of the baseline: sweep plan (DRAFT, awaiting approval)

**Question.** Which parameters of the standing attention-economy model (baseline `baseline_{hk,random,sbm}_{chrono,foryou,trend}`)
change the *conclusions* (the feed comparison), and by how much? Many were fixed by hand or by a single search and never stress-tested.

**What counts as "robust".** A conclusion is robust to a parameter if it keeps its sign and rough size when the parameter moves to
half / double its baseline value. Conclusions tracked (all measured over the last 2,000 steps, mean over seeds):

| Outcome | Plain meaning |
|---|---|
| `assort` | opinion assortativity of the follow graph (do followers share the followee's X?) |
| `gini` | Gini of attention (likes) received per author |
| `fit` | mean identity fit of the feed (similarity of what an agent sees to itself, relative to a random feed) |
| `rec` | mean recognition (likes-based reward term) |
| shares | share of actions that are post / like / reshare / rewire |
| contrasts | **ForYou − Chrono** and **Trend − Chrono** for each outcome above (the effect of the feed, the object of the study) |
| rank flip | does the sign of a contrast, or the ordering of the three feeds, change? |

**Design.** Stage 1 = one-at-a-time (OAT) screen around the baseline on the Holme–Kim start network, 3 feeds × 3 seeds per setting
(seeds 0-2, identical across settings = common random numbers). Stage 2 = replicate the 5-6 most influential parameters on random and SBM
start networks, with 10 seeds, and test their pairwise interaction on a small 2-level grid.
Setting = baseline with exactly one token changed. Run with `scripts/robustness_sweep.py` (resumable, `nohup`, ids `rob_<param>_<level>_<net>_<feed>`).

## Stage 1 parameters (baseline value in bold)

| Group | Parameter | Levels |
|---|---|---|
| Learning | `q_tau` (softmax temperature) | 0.05, **0.1**, 0.3, 1.0 |
| | `q_eta` (learning rate) | 0.03, **0.1**, 0.3 |
| | `q_eps` (uniform exploration floor) | 0, **0.05**, 0.2 |
| | `q_init` (optimistic start) | 0, 5, **10**, 20 |
| | `learner` (bandit vs state-based Q, `q_gamma` 0.9) | **bandit**, q |
| Reward | `w_fit : w_rec` | 2:8, **5:5**, 8:2 |
| | `recog_mix` / `recog_lambda` | 0 / 0.5 / **0.5** ; 1 / **2** / 5 |
| | `cost_post`, `cost_reshare`, `cost_rewire` (scaled together) | x0, x0.5, **x1**, x2 |
| | `fit_mode` | raw, **relative** |
| Feed | `feed_capacity` | 5, **10**, 20 |
| | `access_prob` | 0.05, **0.1**, 0.2 |
| | `fy_beta` (For You sharpness) | 3, **10**, 30 |
| | `foryou_hop` / `trend_hop` (reach) | 2, **5**, 10 |
| | `foryou_hop_lambda` | 0, **0.5**, 1.5 |
| | `foryou_cand_max` (speed approximation) | 100, **300**, 0 (no cap) |
| | `rho_l`, `rho_r` (platform's estimate update) | 0.1/0.1, **0.3/0.3**, 0.5/0.5 |
| | `dead_after` (post lifetime) | 50, 100, **200**, 400 |
| Interaction rules | `like_max_dist` | 0.3, 0.6, **1.0** |
| | `reshare_alpha` | 0, **0.5**, 1 |
| | `notify_original` | 0, **1** |
| | `rewire` / `rewire_gate` | off ; gate on ; **on, no gate** |
| | `post_noise` | **0**, 0.1, 0.3 |
| Structure / scale | `start_deg` | 8, **15**, 30 |
| | `hk_a` (HK in-degree skew) | 15, **4 (baseline)**, 60 |
| | `n` (agents) | 500, **1000**, 2000 |
| | `steps` (convergence check) | 10,000, **20,000**, 40,000 |

About 55 non-baseline settings × 9 runs ≈ 500 runs. Mean wall time per run: Chrono 47 s, For You 119 s, Trend 256 s (n=1000, 20,000 steps)
→ ~21 min of CPU per setting, ~1.8 h total at 12 parallel JVMs (SEARCH_PAR=12, 2 GB each). `results/` is 2.9 GB now; per-run output is pruned.

## Status
Approved by the user 2026-10-26 as written. Stage 1 finished (486 runs, 0 failures, ~1 h 48 min); results in `2026-10-26-robustness-stage1-results.md`.
