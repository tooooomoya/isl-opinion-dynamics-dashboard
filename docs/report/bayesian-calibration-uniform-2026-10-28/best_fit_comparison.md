# Confirmed valley fit and standing-baseline comparison

The earlier two-seed valley did not retain its empirical fit at 40,000 steps with 20 fresh seeds. The best confirmed condition by both primary activity and combined loss has nearly flat original posting. Confirmation changes both horizon and seed sample, so the deterioration cannot be attributed to either alone.

Figures: best_confirmed_fit.png and best_search_valley_confirmation.png. Orange shading is the 10–90% range across confirmation seeds, not a confidence interval for the mean. All rates include zero posters.

| Condition | Seeds/steps | Original extreme / neutral | Original slight / neutral | Primary activity loss | Repost Q |
|---|---:|---:|---:|---:|---:|
| Earlier valley (search) | 2 / 20000 | 1.584 | 0.792 | 1.835 | 0.403 |
| Same valley (confirmation) | 20 / 40000 | 3.316 | 1.425 | 14.316 | 0.416 |
| Best confirmed | 20 / 40000 | 0.996 | 0.949 | 4.018 | 0.430 |

Empirical ratios: extreme=1.739, partisan=1.049, slight=0.702, neutral=1. Primary activity loss uses original+repost; original-only remains a measurement sensitivity because private collection filters are unknown.

## Parameter differences

Reference: the actual standing hkshuf / For You configuration in standard_run.py, including inherited reward_search.BASE and Java defaults. The standing study also runs pure Chrono and pure Trend feeds. No baseline simulation curve is invented here. `start_deg=0` means no explicit edge-count enforcement; hk_m=15 is its nominal HK growth degree.

| Parameter | Standing baseline | Best confirmed | Earlier valley |
|---|---:|---:|---:|
| beta_h | 3 | 2.311 | 5.834 |
| like_max_dist | 1 | 0.637 | 0.5577 |
| q_eta | 0.1 | 0.4879 | 0.3011 |
| q_tau | 0.1 | 0.07188 | 0.0248 |
| q_eps | 0.05 | 0.09355 | 0.05525 |
| q_init | 10 | 19.75 | 1.835 |
| cost_post | 0.5 | 1.058 | 0.9134 |
| cost_reshare | 0.25 | 0.1165 | 1.832 |
| cost_rewire | 1 | 0.8347 | 2.878 |
| recog_mix | 0.5 | 0.377 | 0.1781 |
| recog_lambda | 2 | 0.5797 | 5.922 |
| l_ref | 1000 | 68.94 | 139.2 |
| dead_after | 50 | 136 | 72 |
| access_prob | 0.1 | 0.1559 | 0.07333 |
| feed_capacity | 10 | 24 | 16 |
| fy_beta | 10 | 6.002 | 15.16 |
| foryou_hop | 5 | 9 | 2 |
| foryou_hop_lambda | 0.5 | 0.9907 | 1.733 |
| rho_l | 0.3 | 0.184 | 0.7632 |
| rho_r | 0.3 | 0.2281 | 0.3447 |
| trend_hop | 4 | 2 | 3 |
| start_deg | 0 | 41 | 8 |
| w_rec | 5 | 2.31 | 1.716 |
| w_fit | 5 | 7.69 | 8.284 |
| trend_share | 0 | 0.191 | 0.1487 |
| foryou_share | 1 | 0.3224 | 0.2479 |
| hk_m | 15 | 41 | 8 |
| fit_baseline | analytic | empirical | empirical |

Both fitted conditions retain uniform opinions, mu=0, bandit learning, rewiring without the similarity gate, and stock recognition credit. `fit_baseline=empirical` means the simulated realized-population expectation; `analytic` is the uniform-distribution expectation. This is a reward-baseline difference, not empirical opinion initialization.

Logging differs too: baseline ordinary/heavy metrics every 1/25 steps; calibration 100/100 plus exact event logs. Confirmation uses 40,000 steps versus standing 20,000; both figures measure the final 10,000 steps. Parameter differences are associations from joint fitting, not estimates of individual causal effects.

User preference for future experiments: 10 confirmation seeds. This already-running study retains its original 20.
