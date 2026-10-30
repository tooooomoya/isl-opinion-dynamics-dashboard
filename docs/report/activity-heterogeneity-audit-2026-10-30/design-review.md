# Activity heterogeneity and network-condition review — 2026-10-30

The user clarified that initial network family is an input/model condition to select, not a robustness requirement that one parameter vector fit all three families. Existing family searches were already independent (equal budgets, shared pilot points/seeds); their identical winning pilot vector was an outcome, not a shared-vector constraint. The presentation overemphasized cross-family replication. Future comparisons should rank each family's best condition on the same empirical objectives and fresh-seed evaluation, without averaging objectives across network families and without forcing either similarity or difference between the families.

## Read-only audit of the current winners

Empirical source: deduplicated 762-account panel, `counts.parquet` and survey `libcon.csv`, dates before 2021-01-08. Compute each account's mean collected-record count over 373 days, retaining all panel accounts. For each survey ideology bin, compute ordinary Gini among accounts in that bin. The proposed scalar conditional-heterogeneity summary is the equal-weight arithmetic mean of these seven Ginis. It does not reward differences in average activity between bins. Do not calculate Gini of seven bin means or use overall population Gini as a substitute.

Empirical overall Gini: 0.7010. Within-bin Ginis, in survey-bin order: 0.6577, 0.7116, 0.6927, 0.6721, 0.6077, 0.7378, 0.7150. Equal-bin mean: 0.6849. An exploratory stratified within-bin account bootstrap (2,000 replicates, seed 1729) gives SD 0.0127; this is sampling uncertainty within the selected panel, not source-definition or population-selection uncertainty.

Observation-window dependence is material: complete calendar months have overall Gini 0.737–0.850 (median 0.747), and equal-bin within-bin mean Gini 0.723–0.814 (median 0.740). Thus the user's recollection of around 0.8 is plausible for shorter windows; it must not be installed as an arbitrary fixed target. Monthly panel membership is held constant, including zero-count accounts for each month. The panel is selected for observed news sharing, not a platform-wide sample including unobserved silent people. Empirical original/repost filters remain unresolved.

For simulations, audit all five 40k horizon runs per family, same winning parameters. Compute per-agent counts over final 10k steps from `agent_actions.csv`, retaining zero posters. Compare both originals and originals+reposts. Means across five seeds:

| Network | Within-bin Gini: originals | Within-bin Gini: originals+reposts | Overall Gini: originals+reposts |
|---|---:|---:|---:|
| HK-shuffled | 0.0811 | 0.2360 | 0.2793 |
| Random ER | 0.0823 | 0.1304 | 0.2246 |
| DC-SBM | 0.0815 | 0.1344 | 0.2235 |

These describe the current winners, not a claim that no setting of the model can generate stronger inequality. The observational duration and event mapping need to be aligned before defining a new loss; no equivalence between 10k model steps and a calendar year is established. Still, the observed gap is large and consistent with nearly uniform original posting at the epsilon floor.

## Rewiring diagnostic

The baseline graphs/history count selected Rewire actions, which can be no-ops. Inspecting the final-5k logged `results.csv` steps shows about 37.3–37.6% executed rewires per visit and nearly 100% of selected Rewire actions executing. These are sampled steps (50 logged points per run, every 100 steps), not exact complete-window swap totals. Choice shares have rounding, so a computed execution fraction can exceed one by approximately 1e-5; interpret as approximately one.

At 40k, the fraction of initial directed follow edges still present averages 5.66% (HK), 4.70% (ER), 4.69% (SBM). Mid-run-to-final edge retention is 35.3%, 27.2%, 28.0%. Retention is endpoint overlap, not a count of edges never removed: ties can be removed and recreated. Rapid turnover is consistent with loss of initial topology, but is not a causal ablation. The families are not identical: conditional originals+reposts inequality is larger for HK even when Q scores are similar.

## Revised exploration design, not yet launched or scored

Three objective blocks are appropriate to evaluate prospectively:

1. Opinion-conditioned activity profile (the existing symmetric empirical target; no opportunistic event-definition changes).
2. Within-bin activity heterogeneity, summarized by one scalar such as equal-bin mean Gini. Seven separate Ginis remain diagnostics, avoiding seven new fitted objectives.
3. Root-repost empirical network separation Q, as before.

Standardize block discrepancies on defensible uncertainty/tolerance scales and compare objective trade-offs. An equal mean of three squared residual blocks is a candidate engineering score, not a likelihood; adding a block changes the effective weighting of the existing blocks and must be documented. Target choice and observation window must be settled before evaluating a new objective. Network family is categorical input/condition. Match search budgets and fresh-seed evaluation for model selection, report seed uncertainty, and do not average family losses to require one common vector.

Rewire frequency, successful swaps, follow-edge retention, and differences/persistence across initial networks remain post-exploration diagnostics as requested. Do not add a rewiring penalty, force network-family differences, change rewiring cost bounds, or silently apply a network-preference constraint.

A plausible explanation of the original-post gap is that nearly every agent has the same access probability and similar exploration-floor Post probability. A single opinion-independent dispersion parameter for access/activity propensity is a possible later extension if rescoring existing settings shows inadequate heterogeneity. It would represent assumed individual heterogeneity rather than explain its origin. Endogenous reward/learning heterogeneity is an alternative mechanism to examine. No simulator change or new latent-activity distribution is implemented here.

Before launching another sweep, assess the new conditional-Gini diagnostic over existing candidate settings and compare profile/Q/Gini trade-offs. This audit has not changed any old score, frozen target, model code, or running process. No new sweep or Gaussian comparison was launched during this review.

Artifacts: `summary.json`, `within_bin_gini.csv`, `empirical_monthly_gini.csv`, `rewire_sampled_steps.csv`.

## Subsequent complete existing-run audit

The requested search over existing results is now complete: see `../existing-heterogeneity-search-2026-10-30/report.md`. Across 3,685 completed uniform runs, some raw-fit settings show within-bin Gini near the empirical reference and low Rewire choice shares. Thus the low inequality of the previous winners must not be interpreted as evidence that the model necessarily requires new exogenous agent heterogeneity. Those heterogeneous candidates still miss the desired activity profile, and persistence has not been freshly confirmed. No new sweep was launched.
