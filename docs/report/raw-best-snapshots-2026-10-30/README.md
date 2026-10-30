# Best raw-fit condition: baseline-style figures

Generated from the completed `uniform-raw-reduced-v5` study. These figures reuse the existing `scripts/plot_std.py` baseline layout. Columns are HK-shuffled, Random (ER), and DC-SBM initial networks, rather than three feed modes. All columns use equal Chronological / For You / Trend mixtures and the same best joint-fit behavioral parameters. See `selected_runs.json` for complete configurations and source job keys.

- `baseline_raw_best_fit.png`: complete baseline-style sheet, including action mixes, raw identity fit, attention statistics, and network snapshots. Final-window summaries use the last 5,000 steps; five 40,000-step runs per network. Empty follower groups have no action average.
- `baseline_raw_best_network_snapshots.png`: extracted native network panels from the same figure. Rows show initial follow, follow at 20k, follow at 40k, and final-5k immediate repost graph. Representative is seed 272000 for each family, selected as the lowest seed, without choosing for appearance. Follow networks show all ties; node color is fixed opinion, node size follows follower count. Layouts start from each family's own initial topology and continue through its mid/final topology. Arrows are omitted.
- `baseline_raw_best_action_selection.png`: baseline-style final-window action breakdowns by follower and absolute-opinion groups. They are per-agent means, averaged across seeds, as in the baseline script.
- `baseline_raw_best_strategy_history.png`: observed action-choice histories (500-step intervals), histories of Post/Repost choice shares by opinion group, and final greedy-Q versus observed action shares. Histories average per-seed decision shares; shading is one seed standard deviation, not a confidence interval. Greedy preferences use final bandit state-0 Q values, independent of current action availability. They are a final snapshot, not a reconstruction of individual greedy preferences over time.

The repost snapshot follows the baseline convention: resharer — immediate author of the reshared post, aggregated from `reactions_conv.csv`, last 5k steps. It filters repeated ties to at most 2,500 pairs, starting at weight 2. The threshold and retained pair counts appear in each panel. Only about 5–6% of distinct pairs survive in these runs; filtering can make clusters look cleaner. These displayed graphs differ from the root-author-attributed, final-10k network used for calibration Q. Do not assign fitted Q values to the filtered pictures.

Choice logs count selected actions; Like includes gated no-ops, and Rewire choices need not execute a swap when no candidate exists. Continuing exploration prevents an absorbing policy. Average final-5k choice shares are approximately 4.8% Post, 47.8–49.5% Like, 8.2–9.9% Repost, and 37.5% Rewire. Nearly no agents have Post as their final unconstrained greedy action; observed Post is close to the epsilon exploration floor (epsilon/4≈4.71% when all four actions are available). That is suggestive of exploration-driven original posting, not proof of a causal mechanism.

Reproduce:

```bash
venv/bin/python scripts/plot_raw_best_baseline.py
```

CSV files preserve the per-seed histories, group histories and final preference/choice summaries. No simulation, model parameter, calibration score, or historical baseline image was changed. The native plotting script now accepts explicit run directories in `PLOT_COLS`, renders raw identity fit without subtracting a baseline when requested, and can export its action/network sections separately.
