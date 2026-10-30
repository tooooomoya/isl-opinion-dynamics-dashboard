# Predictors of simple extreme posting elevation

Read-only analysis; no live objective, simulation, or default was changed. Use completed valid five-seed initial Sobol settings only; exclude anchors and adaptive BO. Outcomes are mean per-seed log(original activity contrast): equal-side extreme per-person rate divided by neutral, or by the equal-bin mean of all five inner bins. All agents including zero posters contribute to bin rates. The existing half-event stabilization is retained. The second contrast checks that a result is not solely a low-neutral effect.

Marginal Spearman associations use BH correction over 25 inputs within each network/outcome. Forests use four-fold held-out prediction and permutation importance. Shared parameter points across network families are not independent replications. Predictive associations over the sampled box do not establish local causal effects.

| Network | Contrast | Settings | Predictive skill vs constant |
|---|---|---:|---:|
| hkshuf | log_extreme_neutral | 98 | -0.073 |
| hkshuf | log_extreme_inner | 98 | -0.115 |
| random | log_extreme_neutral | 95 | -0.063 |
| random | log_extreme_inner | 95 | 0.067 |
| dcsbm | log_extreme_neutral | 95 | 0.175 |
| dcsbm | log_extreme_inner | 95 | 0.234 |

Consistent candidate directions: higher homophily, greater identity-fit weight relative to recognition, higher access probability, and lower For You sharpness. Access is tested at a fixed step horizon: it changes both decision opportunities and learning progress relative to post lifetime, so it is not evidence of a clock-independent equilibrium effect. Ratios above one do not ensure a full U shape at every inner bin, nor the empirical W-shaped target.

| Network | Contrast | Parameter | Spearman rho | Corrected q |
|---|---|---|---:|---:|
| hkshuf | log_extreme_neutral | beta_h | 0.295 | 0.026 |
| hkshuf | log_extreme_neutral | rec_fraction | -0.271 | 0.044 |
| hkshuf | log_extreme_neutral | access_prob | 0.338 | 0.017 |
| hkshuf | log_extreme_neutral | fy_beta | -0.301 | 0.026 |
| hkshuf | log_extreme_inner | beta_h | 0.278 | 0.034 |
| hkshuf | log_extreme_inner | rec_fraction | -0.292 | 0.029 |
| hkshuf | log_extreme_inner | access_prob | 0.304 | 0.029 |
| hkshuf | log_extreme_inner | fy_beta | -0.310 | 0.029 |
| random | log_extreme_neutral | beta_h | 0.347 | 0.014 |
| random | log_extreme_neutral | rec_fraction | -0.265 | 0.072 |
| random | log_extreme_neutral | access_prob | 0.263 | 0.072 |
| random | log_extreme_neutral | fy_beta | -0.258 | 0.072 |
| random | log_extreme_inner | beta_h | 0.308 | 0.060 |
| random | log_extreme_inner | rec_fraction | -0.236 | 0.108 |
| random | log_extreme_inner | access_prob | 0.260 | 0.108 |
| random | log_extreme_inner | fy_beta | -0.240 | 0.108 |
| dcsbm | log_extreme_neutral | beta_h | 0.370 | 0.006 |
| dcsbm | log_extreme_neutral | rec_fraction | -0.330 | 0.014 |
| dcsbm | log_extreme_neutral | access_prob | 0.314 | 0.016 |
| dcsbm | log_extreme_neutral | fy_beta | -0.303 | 0.018 |
| dcsbm | log_extreme_inner | beta_h | 0.291 | 0.027 |
| dcsbm | log_extreme_inner | rec_fraction | -0.303 | 0.023 |
| dcsbm | log_extreme_inner | access_prob | 0.331 | 0.013 |
| dcsbm | log_extreme_inner | fy_beta | -0.361 | 0.008 |

## Simpler-model check

Also fit standardized ridge regressions, with alpha selected by three-fold inner CV inside each of the same four outer folds (scaling inside the inner pipeline). This is an exploratory model comparison, not independent confirmation after model selection.

| Network | Contrast | Ridge skill vs constant |
|---|---|---:|
| hkshuf | log_extreme_neutral | 0.053 |
| hkshuf | log_extreme_inner | 0.016 |
| random | log_extreme_neutral | 0.084 |
| random | log_extreme_inner | 0.048 |
| dcsbm | log_extreme_neutral | 0.091 |
| dcsbm | log_extreme_inner | 0.078 |

## Interpretation

No single dominant predictor of the activity contrast is established. Marginal associations consistently favor higher beta_h, lower recognition fraction (higher identity-fit weight), higher access probability, and lower FY sharpness. Forest and ridge rankings are diffuse and have limited held-out accuracy; epsilon also appears in multivariate models. Thus beta_h is a robust activity association but its clear dominance for network fit must not be transferred to the activity ratio. Identity-fit/reward balance and homophily are sensible priorities for controlled joint tests. These are hypotheses about interactions, not measured causal effects. Current fitting still uses the W-shaped target; this auxiliary analysis did not switch the live objective.

Most sampled settings are approximately flat; these marginal trends partly distinguish suppression of extreme posting from flat activity. They must not be described as a validated predictor of robust extreme elevation.

## Strong actual extreme-elevation cases

The two independently sampled HK settings with geometric-mean extreme/neutral>1.5 also elevate extreme posting across random and DC-SBM at the same settings. Both have high identity-fit reward share (about83% and94%) and low action temperature (about0.025 and0.035), with beta_h about5.83 and2.43. These are only two settings, so this is a targeted interaction hypothesis, not an identified necessary/sufficient mechanism. Most settings at high beta_h alone remain flat. Detailed seed ranges and cross-network means are in strong_contrast_cases.json.

Important shape qualification: case B has extreme/neutral≈2.1 but its folded partisan bin is slightly higher than its outermost extreme bin (e.g.HK seven-bin means≈[2.078,2.174,1.631,1,1.595,2.161,2.056]). It is therefore strong extreme-versus-neutral elevation, not proof that the outermost categories exceed every inner category. An extreme/average-inner contrast also remains above1, but does not enforce a strictly monotone U.
