# Network, strategies, and parameter diagnostics

Selected the strongest complete five-seed original-post profile in HK-shuffled. This is a partial fit: extreme/neutral≈1.66, slight/neutral≈1.04, so the empirical inner trough≈0.70 is absent. Selection is a diagnostic on original-only loss; the running calibration still fits original+repost. Representative graph seed is the lowest seed, chosen without inspecting graph appearance.

## Network snapshots

network_snapshots.png shows all 1,000 agents, all initial/final follow ties, and all root-attributed repost ties in the final 10k steps. The initial graph uses its own topology layout; final follow/repost graphs share a final-topology layout. Opinion determines color only. GraphML files preserve directions and weights. Follow edges point follower→followee, repost edges root author→reposter. Arrowheads are omitted in the dense PNG.

## Strategy ratios

Use the actual bandit state 0 in q_table_final.csv. The summary Q columns in agent_snapshot_final.csv average states and include unvisited states, so they are not the correct basis for bandit preferences. Final greedy preferences are unconstrained argmax Q, not a proof of convergence or the actual stochastic policy. Actual action shares include epsilon exploration and availability restrictions; chosen like no-ops are included.

| Action | Agents with final greedy preference (%) | Observed decisions, final 10k (%) |
|---|---:|---:|
| Post | 1.40 | 5.04 |
| Like | 98.50 | 87.94 |
| Repost | 0.04 | 3.51 |
| Rewire | 0.06 | 3.51 |

Dominant observed action is unchanged across the final two 5k windows for 100.0% of agents (five-seed mean); median per-agent total-variation change in action mix is 0.0154. This is a limited behavioral-stability diagnostic; it does not establish Q-value or network equilibrium. With epsilon=0.1385, uniform exploration over four available actions contributes epsilon/4≈3.46% per action. Observed repost/rewire rates are close to that floor. The floor statement is conditional on all four actions being available.

## Parameter settings

Reference is standard_run.py hkshuf / pure For You with inherited reward_search.BASE and Java defaults. The selected feed is mixed; the standing script also runs pure Chrono and pure Trend.

| Parameter | Standing baseline | Selected condition |
|---|---:|---:|
| beta_h | 3 | 2.589 |
| like_max_dist | 1 | 1.383 |
| q_eta | 0.1 | 0.2669 |
| q_tau | 0.1 | 0.05923 |
| q_eps | 0.05 | 0.1385 |
| q_init | 10 | 6.413 |
| cost_post | 0.5 | 0.4758 |
| cost_reshare | 0.25 | 0.9098 |
| cost_rewire | 1 | 0.8649 |
| recog_mix | 0.5 | 0.4977 |
| recog_lambda | 2 | 4.582 |
| l_ref | 1000 | 2059 |
| dead_after | 50 | 157 |
| access_prob | 0.1 | 0.265 |
| feed_capacity | 10 | 12 |
| fy_beta | 10 | 3.782 |
| foryou_hop | 5 | 7 |
| foryou_hop_lambda | 0.5 | 1.023 |
| rho_l | 0.3 | 0.4614 |
| rho_r | 0.3 | 0.1337 |
| trend_hop | 4 | 10 |
| start_deg | 0 | 46 |
| w_rec | 5 | 3.967 |
| w_fit | 5 | 6.033 |
| trend_share | 0 | 0.3868 |
| foryou_share | 1 | 0.3148 |
| hk_m | 15 | 46 |
| fit_baseline | analytic | empirical |

## Which parameters matter?

Exploratory analysis uses only complete valid five-seed initial Sobol settings, excluding the 28 manually chosen anchors and every adaptive BO proposal. Forests predict log1p(mean component loss), with four-fold out-of-fold validation and held-out permutation importance (five repeats per fold). This diagnostic response transformation does not change the running optimizer. Small positive predictive skill and unstable importance bars limit interpretation. Spearman associations have Benjamini–Hochberg correction across the 25 parameters within each network/outcome; cross-network analyses share parameter points and are not independent replications. No causal parameter effect is estimated, and broad-space importance need not identify the local change needed to create the missing trough.

| Network | Outcome | Settings | Out-of-fold predictive skill vs constant |
|---|---|---:|---:|
| hkshuf | original_activity_loss | 98 | -0.052 |
| hkshuf | all_activity_loss | 98 | 0.113 |
| hkshuf | network_loss | 98 | 0.616 |
| random | original_activity_loss | 92 | 0.042 |
| random | all_activity_loss | 92 | 0.116 |
| random | network_loss | 92 | 0.624 |
| dcsbm | original_activity_loss | 92 | 0.071 |
| dcsbm | all_activity_loss | 92 | -0.010 |
| dcsbm | network_loss | 92 | 0.522 |

Original-post associations with corrected q<0.10 (larger loss means worse fit):

| Network | Parameter | Spearman rho | Corrected q |
|---|---|---:|---:|
| dcsbm | beta_h | -0.307 | 0.043 |
| dcsbm | q_tau | -0.290 | 0.043 |
| dcsbm | fy_beta | 0.290 | 0.043 |
| dcsbm | rec_fraction | 0.279 | 0.044 |
| dcsbm | access_prob | -0.270 | 0.047 |
| hkshuf | beta_h | -0.294 | 0.071 |
| hkshuf | q_tau | -0.264 | 0.071 |
| hkshuf | access_prob | -0.269 | 0.071 |
| random | beta_h | -0.330 | 0.033 |
| random | q_tau | -0.296 | 0.049 |
| random | start_deg | -0.285 | 0.049 |

Each figure is based on completed outputs only. No simulator code, fitting objective, live job, or parameter default was changed.

## Interpretation of importance

The strongest predictive signal for network loss is beta_h in all three families, with For You sharpness fy_beta a smaller second contributor. Network-loss forests have out-of-fold skill about0.52–0.62 relative to a training-mean baseline; see network_parameter_importance.png. This is predictive sensitivity over the sampled box, not a causal contribution fraction. Original-post-loss forest skill is approximately−0.05 to0.07, so its importance ranking is not reliable enough to prioritize a local W-shape fix. Marginal associations suggest beta_h and q_tau across all three families; other signals depend on the family. These do not imply that raising a parameter monotonically improves the missing inner trough.

In the selected condition, epsilon/4≈3.46% with all four actions available, close to observed repost and rewire shares≈3.51%. Most agents prefer Like. Costs for Post/Repost/Rewire are positive and Like has no action cost; relative costs and temperature are therefore natural candidates for controlled local mechanism tests, but those tests have not been performed here.
