# Existing-run search for within-bin activity heterogeneity

Read-only audit requested before any new sweep. Inspected 3,685 successful uniform-start runs: 1,035 from the raw reduced study, 2,026 from the stopped three-network relative-fit study, and 624 from the earlier uniform study. No missing source logs or parse errors. All recomputed population Ginis match stored Ginis to within 1.2e-16. Original scores, simulator configurations and frozen targets are untouched.

The main conclusion changes the interpretation of the previous winning-condition audit: **the existing raw-fit model can generate substantial within-bin inequality, and low rewiring can coexist with it. The currently selected winners are not representative of all available model behaviors.** We have not found a validated condition that also reproduces the desired activity profile.

## Measurement and eligibility

For each successful run, use exact `calibration_activity.csv` counts in its final 10k steps, keeping every agent including zero posters. Compute Gini separately in each of the seven fixed-opinion bins, then average the seven Ginis with equal weights. Record originals and originals+reposts separately. The empirical reference is 0.68494 from the existing 373-day panel window; this is a diagnostic reference, not a newly installed objective. Model steps have not been mapped to calendar duration, empirical filtering is unresolved, and monthly empirical conditional Ginis are higher (0.723–0.814).

Aggregate repeated seeds only for the identical full simulator configuration, horizon and stage within a source study. Compare initial network families independently. Main screening tables require at least five distinct seeds and valid structure/event counts in all runs. Early two/three-seed searches remain in the complete CSV, but cannot enter the main comparison. Never combine relative-fit observations with raw-fit observations for parameter inference. Population composition is uniform for every included job.

Of 192 raw search configurations (64 per family), 191 meet the all-seeds-valid criterion. Across those 191, mean within-bin Gini ranges from 0.015 to 0.715 for originals+reposts and 0.021 to 0.807 for originals. Seven raw network/configuration combinations exceed 0.5 in originals+reposts conditional Gini.

## Notable raw configurations (five search seeds, 20k horizon)

| Initial network / configuration | Within-bin Gini: originals | Within-bin Gini: originals+reposts | Rewire share of choices, final 5k | Repost Q | Extreme/neutral, originals+reposts |
|---|---:|---:|---:|---:|---:|
| HK, recognition-heavy condition | 0.807 | 0.588 | 0.13% | 0.445 | 1.024 |
| HK, closest available Gini condition | 0.770 | 0.715 | 1.21% | 0.396 | 0.943 |
| ER, closest available Gini condition | 0.724 | 0.681 | 1.21% | 0.426 | 0.759 |
| DC-SBM, closest available Gini condition | 0.733 | 0.689 | 1.20% | 0.426 | 0.790 |

Compare empirical extreme/neutral≈1.739 and Q≈0.478. The matching-Gini conditions generally make extremes quieter than neutrals; the recognition-heavy HK condition is approximately flat in originals+reposts and extreme-suppressed in originals. They demonstrate heterogeneity and infrequent rewiring, not a satisfactory joint fit. They have not received fresh ten-seed confirmation or 40k horizon checks, so persistence is unestablished.

The closest-Gini conditions in all three families share one initial Sobol vector. They are separately evaluated initial-network conditions, not independent parameter discoveries or a requirement for a shared vector. Its original+repost conditional Gini has five-seed SD 0.0041 (HK), 0.0105 (ER), 0.0055 (SBM). The same vector yields different Q and profile behavior by initial network. Full parameters and seed references are in `promising_raw_conditions.json`.

The recognition-heavy HK condition uses beta_h≈8.037, identity/recognition weights≈0.996/9.004, tau≈0.0561, epsilon≈0.00494, initial Q≈3.953, post/repost/rewire costs≈0.963/0.639/3.798, lifetime28, access≈0.0752, For You sharpness≈6.084, degree47. Within-bin original Gini is high partly because original posting is concentrated: 14.6% of agents produce zero originals in the evaluation window. The matching-Gini condition has no zero posters in those windows, so its inequality is not merely a nearly empty event count. Neither observation establishes a causal mechanism or a persistent distribution of latent propensities.

## Interpretation for the next design

Do not conclude that introducing exogenous activity heterogeneity is already necessary. Existing parameters can produce it. Adding a within-bin inequality block can change which part of the existing parameter space is selected; its trade-off with the opinion-conditioned activity profile and Q needs explicit evaluation.

Keep network family as a selectable categorical model condition. Keep rewiring frequency and initial-topology persistence as post-fit diagnostics, as requested. Do not impose a rewiring penalty or reward network-family differences. A possible follow-up is to assess persistence and local trade-offs around the existing heterogeneous configurations before a new broad search. This audit launches no simulations and creates no new scalar objective.

Outputs:

- `per_seed_heterogeneity.csv`: all 3,685 inspected runs, source references and complete configurations.
- `condition_heterogeneity.csv`: seed aggregates, including lower-seed exploratory rows with explicit seed counts.
- `selected_conditions.csv`: best old joint-fit and closest-Gini valid five-seed search conditions per family/study.
- `raw_search_pareto.csv`: nondominated raw configurations for activity-profile loss, network loss and conditional-Gini reference gap; no new weights.
- `promising_raw_conditions.json`: four diagnostic candidates above, profiles, final-window action shares and job keys.
- `audit_summary.json`: coverage, exclusions and measurement notes.

Reproduce with `venv/bin/python scripts/audit_existing_activity_heterogeneity.py`. Raw results and source data remain local under the repository's existing ignore policy.
