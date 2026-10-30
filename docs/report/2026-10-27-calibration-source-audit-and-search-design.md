# 2026-10-27 — Primary-source audit and broad calibration design

Status: research and a concrete search proposal; no ABM runs launched. This supersedes the historical target numbers in the rediscovery memo. Current model source and existing simulation results were not edited.

## Recommended scope

Use two main objective blocks: (1) the seven-bin per-person vocal-activity profile; (2) repost-network segregation. Keep follower-degree distribution as a third validation block initially. If a comparable follower-degree target is established, it can become a third objective. Avoid adding polarization variance, attention Gini, clustering, path length, and assortativity as independent optimization targets at this stage.

One useful extra check belongs inside activity validation: individual activity inequality. Means alone can conceal a model in which everybody posts at similar rates. Use the empirical distribution/CV/upper-tail share as a held-out check; do not automatically add a fourth objective.

The historical empirical datasets cover different populations and years. This is calibration to several stylized facts, not inference from one jointly observed Twitter population. A claim that repost modularity is universally 0.48, or follower degrees universally follow one power law, would be too strong.

## 1. Vocal activity: retrieved code and daily data

Primary sources:

- Paper: Buntain & Snegovaya, *Post-January 6 deplatforming shows long-term effects on ideological polarization among Twitter users*, PNAS Nexus 4(11), pgaf333 (2025), https://doi.org/10.1093/pnasnexus/pgaf333 . Full-text XML retrieved from https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12624514/fullTextXML .
- Author release: https://doi.org/10.17605/OSF.IO/KQFM6 . Its README states that original Twitter/Reddit data are withheld for privacy, while anonymized daily counts/ideology and analysis code are public.
- `01-twitter.ideology/00-SurveyCollectionToIdeology.ipynb`: https://osf.io/download/293da/ . Counts nonmissing tweet IDs by date in the supplied RDS records; no original/retweet/reply exclusion appears in this public notebook. The private RDS input's own collection filters are not available. Thus the public evidence establishes “supplied tweet records,” not an independently verified original-only or all-tweet event definition.
- `01-twitter.ideology/01-MergeTwitterCollections.ipynb`: https://osf.io/download/4a23q/ . Merges two collection waves, preferring the first pull on overlapping dates; selects users observed in both ideological-sharing regimes. Sample selection depends on news sharing, not merely having an account.
- `03-its.models/01-ActivityModel.ipynb`: https://osf.io/download/68ee6a57cafd9791162e7a0e/ . Reads the daily parquet, restricts to matched handles, and explicitly drops duplicate label handles, keeping the first.

### Correction: 765 rows are 762 people

The label CSV contains three identical duplicate rows, for handles `tw_user_2007`, `tw_user_3041`, `tw_user_5197`. They propagated into the local summary and historical Java/Python constants. The daily count parquet has exactly 762 unique handles × 737 dates (2020-01-01 through 2022-01-06), no missing cells, and 1,957,401 total tweet records. All 762 are in the matching file. Deduplicating labels, as the authors do, gives:

| Bin | Unique people | Mean full-window count | Mean/day before 2021-01-08 | Mean/day from 2021-01-08 |
|---|---:|---:|---:|---:|
| Very liberal | 160 | 4328.725 | 4.203 | 7.585 |
| Liberal | 130 | 2703.169 | 3.163 | 4.185 |
| Somewhat liberal | 85 | 1503.682 | 2.088 | 1.992 |
| Middle of the road | 207 | 2094.329 | 2.294 | 3.402 |
| Somewhat conservative | 46 | 691.065 | 1.133 | 0.737 |
| Conservative | 71 | 1156.761 | 1.649 | 1.488 |
| Very conservative | 63 | 3779.921 | 3.780 | 6.511 |

The outer-bin elevation persists, but its strength depends on the period. Mean and median also differ sharply: full-window daily means/medians are 5.873/1.342 (very liberal), 2.842/0.672 (middle), 5.129/0.817 (very conservative). Activity CV by bin spans about 1.45–3.19. Do not treat the sample means as exact targets or claim the same contrast describes a typical individual. Generated CSVs include 5,000 account-bootstrap intervals; they describe sampling uncertainty within this selected panel, not representativeness or collection bias.

The paper reports 793 respondents sharing news in both regimes and 762 Twitter–Reddit matches. Its main event date is 2021-01-08. For a model with no deplatforming intervention, a defensible primary calibration window is pre-event (or calendar 2020), with full/post windows as sensitivity analyses. This choice must be declared before selecting winning parameters. The public matched panel remains selected on behavior in both regimes even when measuring its pre-event activity.

### Measurement proposal

Keep seven self-report categories and their asymmetry. Do not collapse them to a single monotone extremity slope or impose a smooth U: there is an inner-bin dip, and Middle exceeds both neighboring “somewhat” bins. Rates divide by **all agents in the bin, including zero posters**, and by a common observation window.

Fit the relative rate profile to avoid inventing a calendar-day mapping. For instance compare seven log rates relative to an overall population-weighted rate, with uncertainty assessed by resampling accounts and simulator seeds; the normalized vector has only six independent components. An ordered-bin Wasserstein distance can be a secondary summary, but binwise residuals preserve the local dip and avoid assuming equal psychological distance between survey labels. Do not give tiny denominators or sparsely populated bins unlimited influence.

Originals and reshares must be logged separately by the acting agent's intrinsic ideology. Pending the unavailable upstream collection definition, neither labeling the target original-only nor silently asserting that it includes every retweet is justified. A declared measurement-sensitivity analysis of originals versus originals+reshares is possible, but the optimizer must not choose the event definition opportunistically. Likes are not tweet records and do not belong in either count.

## 2. Repost network: raw data obtained and recomputed

Paper: Conover et al., *Political Polarization on Twitter* (ICWSM 2011), §§2.3, 3.1, 3.3:
https://www.cse.cuhk.edu.hk/~cslui/CMSC5734/Conover_PoliticalPolarizationTwitter.pdf .
Author dataset: https://zenodo.org/records/4589065 , file `icwsm_polarization.zip`, MD5 verified against the published value `0adf9e2dd0a60547556a00450cd9fa68` during the audit.

The analysis is of political hashtag tweets during six weeks before the 2010 election, on the largest connected component. Edges run from the source author to the retweeter. Community detection uses two labels, leading-eigenvector initialization plus label propagation, repeated 100 times to assess stability. The left/right labels in the release are **detected-cluster labels**, not individual ground-truth ideology. “Undecidable” is a later content-coding category; it is not a reason to remove all near-zero model agents before structural community detection.

Parsing the supplied node/edge text files (no downloaded pickle executed) gives:

| Construction, published cluster partition | Nodes | Edges/events | Q | Cross-cluster fraction |
|---|---:|---:|---:|---:|
| Directed, event-weighted | 18470 | 61157 | 0.477874 | 0.020341 |
| Directed, unique ties | 18470 | 48365 | 0.475510 | 0.023054 |
| Undirected, unique ties | 18470 | 48053 | 0.475375 | 0.023183 |

Cluster sizes are left 11,355 and right 7,115. These computations use the released partition, not a new run of the paper's clustering algorithm. Weighted directed Q happens to reproduce the reported rounded 0.48, but rounding alone does not establish the original weighting/direction implementation. Preserve the construction variants rather than claim exact historical reproduction.

### Measurement proposal

Use a declared window, the largest weak component for directed versions, and matched event weighting/unique-tie conventions. Infer **two structural communities** in both empirical and simulated networks using the same procedure. Current `Q_sign_repost` is a supplementary ideology-alignment diagnostic, not a substitute for detected-community Q. Unrestricted Louvain with an arbitrary number of communities is also a different estimand.

Important code mismatch: the current ABM records resharer → immediate copy-author (`src.getPostUserId()`), while the paper describes original/source author → retweeter. Direction reversal alone leaves directed modularity of a fixed partition unchanged, but changing immediate-copy author to root author changes the graph. Log both root-attributed and immediate-source graphs; use root attribution for the closest native-retweet-style comparison, explicitly retaining uncertainty about historical manual RT chains.

Cross-cluster share is useful for interpreting Q but strongly related to it; avoid giving both full independent weight without accounting for redundancy. The paper itself controls for graph structure using degree-preserving randomizations. At n=1000, compare excess Q against an appropriate randomized baseline and examine observation-window effects, rather than demanding an exact 0.48 from every seed. Excess Q is an extra check on size/density effects, not by itself proof of cross-size comparability. Candidate validation should use new seeds and alternate windows; graph events are dependent, so a naive edge bootstrap is not a full empirical uncertainty model.

## 3. Follower degree: validation, with construction limits explicit

Kwak et al., *What is Twitter, a Social Network or a News Media?* (WWW 2010):
https://www.cs.cornell.edu/courses/cs6241/2019sp/readings/Kwak-2010-Twitter.pdf . The abstract describes a non-power-law follower distribution. Figure 1/§3.1 fits exponent 2.276 over a limited range and discusses deviations in the upper tail. A global “gamma = 2.276” objective would therefore misstate the source.

The corresponding large follower-network release is available at https://snap.stanford.edu/data/twitter-2010.html (41,652,230 nodes, 1,468,364,884 edges). SNAP's orientation is followed account → follower, opposite to this model's follower → followee; reverse consistently before labeling in/out degrees. The full graph was located, not downloaded/analyzed in this audit. The old author-hosted page returns 404. SNAP's much smaller ego-network dataset is available but is an ego-selected sample and should not silently replace the full-network degree target.

For now, report follower-count CCDF, zero-follower fraction, and upper-tail concentration from the same final network, considering size/density. Do not use attention/like Gini as follower-degree Gini. A raw 41-million-node distribution cannot simply be imposed on a 1000-node simple graph; induced-node sampling, BFS, and degree-preserving downscaling imply different observation models.

Current rewiring swaps one followee for another and **conserves every agent's out-degree**. In HK/WS starts this is initially essentially constant. Parameter search cannot create a realistic heterogeneous following-count distribution under that mechanism. In-degree can evolve and is the sensible first structural check. If matching out-degree becomes required, heterogeneous initialization or a changed mechanism would be needed.

## Broad parameter proposal

The recent robustness screen is useful for allocating search resolution, not deleting dimensions: it measured feed contrasts in assortativity/attention/action shares, not the bin7 profile or the proposed repost objective. It used HK and three seeds, before the standing lifetime was changed from 200 to 50. Distance sweep locates a sharp follow-structure transition between beta_h 1 and 3; it does not establish the same transition in the repost graph. The mixed-feed result is strongly nonlinear, so feed mixture cannot be assumed to interpolate between pure feeds.

Proposed boxes below are engineering exploration ranges, not inferred empirical priors or final calibrated values. They include the standing settings and generally extend beyond the OAT screen. Reward weights sum to 10 so the optimizer cannot multiply all rewards, costs, and temperature by a common factor without changing behavior. For the first pass keep learner=bandit, mu=0, existing action definitions, relative-fit convention, and rewiring ON without the gate. Categorical alternatives below can be screened in explicit branches.

| Family | Dimensions and proposed ranges | Sampling/notes |
|---|---|---|
| Distance | `beta_h` 0–12; `like_max_dist` 0.1–2 | Include beta=0 and no-cutoff anchors; extra initial points at beta 1,1.5,2,2.5,3,6. Both can interact. |
| Learning | `q_eta` 0.01–0.5; `q_tau` 0.02–2; `q_eps` 0–0.3; `q_init` 0–20 | Log eta/tau. q_init can exploit transients; monitor learning drift and validate at longer horizons. |
| Reward | recognition weight fraction 0.05–0.95 (`w_rec=10*f`, `w_fit=10*(1-f)`); `cost_post` 0–2; `cost_reshare` 0–2; `cost_rewire` 0–4 | Costs vary independently; joint scaling alone cannot explore their relative incentives. |
| Recognition | `recog_mix` 0–1; `recog_lambda` 0.25–10; `l_ref` 10–3000 | Log lambda/l_ref; a parameter can be inactive at mix endpoints. |
| Availability/time | `dead_after` 10–400; `access_prob` 0.02–0.3; `feed_capacity` 5–40 | Integer lifetime/capacity; lifetime/access are partially confounded. Track lifetime × access as well as both inputs. |
| For You | `fy_beta` 0–40; `foryou_hop` 1–10; `foryou_hop_lambda` 0–2; `rho_l`, `rho_r` independently 0.01–0.8 | Only active with For You; do not confuse fy_beta with beta_h. Include beta=0. |
| Trend | `trend_hop` 1–10 | Only active with Trend; keep the corrected ranking/tie convention. |
| Feed composition | two shares over the Chrono/For You/Trend simplex | Include corners, half-and-half, interior; avoid combinations summing above 1. |
| Network | mean out-degree `start_deg` 5–50; conditional HK `hk_a` 1–60, `hk_pt` 0–0.8 | Discrete initial-network strata: random, hkshuf, HK, SBM. Coordinate hk_m with density for HK starts. start_deg overrides must be checked per generator. |

This is 25 dimensions before conditional network-shape dimensions, not a small GP search. Proposed categorical branches: learner bandit vs state-based Q (with q_gamma 0–0.95 active only for Q), rewire gate, notify_original, fit_mode, post_noise 0–0.3, and stock vs delayed-post credit. These are distinguishable mechanism specifications; report them explicitly rather than present one optimizer-selected mechanism as the standing model. Simulator size, horizon, logging frequency and candidate cap are validation/accuracy choices rather than scientific fitting knobs. Do not include removed `reshare_alpha` merely because the old screen listed it.

### Search procedure proposal

1. After event-definition and objective choices are declared, run a broad space-filling pilot. A concrete initial budget is 128 parameter points × 2 seeds at a declared mixed-feed/network calibration condition (256 simulations), plus designated baseline/control anchors. Measure actual runtime before setting the continuation budget. Include corners/zero anchors and extra coverage of beta_h 1–3. Categorical mechanism alternatives can receive a separate balanced pilot rather than an enormous full factorial.
2. Retain the broad box. Fit a surrogate suited to mixed/conditional dimensions (e.g. a tree ensemble), compare held-out prediction/noise against a GP, and use sequential batches for exploration and good candidates. Do not trust a high-dimensional vanilla GP simply because the earlier seven-dimensional code used one. OAT insensitivity alone is not grounds to freeze a dimension.
3. Calibrate against one declared observed-feed mixture or treat mixture as a nuisance parameter. Evaluate pure-feed counterfactuals at the **same behavioral parameters**. Forcing every feed to match the same empirical profile, or refitting behavior separately for each feed, can absorb the effect we want to study. Keep initial-network strata separate in summaries and validate candidate regions across them.
4. Inspect activity/network tradeoffs before collapsing to one weighted loss. Empirical bootstrap uncertainty can scale activity residuals; Q's single historical observation is not an empirically known narrow Gaussian target. Keep component errors and raw summaries in every log. This is Bayesian optimization for calibration, not automatically a Bayesian posterior over model parameters.
5. Advance several non-dominated/promising candidates, use 3–5 seeds as needed during search and 20 fresh seeds for finalists, and extend runs to 40k or until a declared stability check passes. The robustness report documents drift at 20k; a candidate's success cannot depend on a convenient transient. Confirm whole regions, not only a best point. Longer horizons, n changes, and starting-network changes are validation stages, not selectable tricks for lowering loss.

## Reproduction and artifacts

`scripts/audit_calibration_sources.py` downloads/caches public sources, computes corrected means for four temporal windows with 5,000 account-bootstrap replicates, and reconstructs three network variants using the released cluster labels. Output:

- `empirical-target-audit-2026-10-27/activity_targets.csv`
- `empirical-target-audit-2026-10-27/conover_targets.json`
- `empirical-target-audit-2026-10-27/source_manifest.json` (URLs, byte counts, SHA256)

Audit run used the existing project venv with pyarrow installed into a temporary isolated dependency directory, without modifying project dependencies. Raw source cache: `/tmp/pvm-calibration-sources-20261027`. To reproduce elsewhere, install pandas/numpy/pyarrow in an analysis environment and run `python scripts/audit_calibration_sources.py`; default cache is under ignored `results/empirical_source_audit`. The downloaded notebooks were inspected as data and never executed. Historical summary CSV and Java constants were retained for traceability.
