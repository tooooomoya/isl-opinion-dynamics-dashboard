"""
2026-08-01 -- Activity-filtered repost-network sign modularity (Q_sign_repost), current HEAD
only. Follows up on docs/report/2026-07-31-wssit-era-vs-current-model-diff.md's third pass,
which compared our repost Q (~0.34, computed on the full simulated population) against Conover
et al. 2011's ~0.7-0.8 political-retweet-network figure. The user flagged that Conover's number
is inflated by their methodology excluding low-activity/infrequent posters -- those users are
disproportionately the camp-bridging ones, so removing them mechanically raises modularity.
This script checks how much of the 0.34-vs-0.7-0.8 gap that alone could explain, by recomputing
Q on the current model's own population after removing its least-active agents, at a few
illustrative activity-percentile cutoffs (NOT a literature-matched exact threshold -- Conover's
precise cutoff isn't reproduced here, this is a sensitivity check on the mechanism, not a
replication of their exact filter).

Uses the FULL-RUN cumulative repost network, reconstructed directly from repost_cascades.csv's
per-event log (every relay event over all 40000 steps), rather than the 5000-step windowed
snapshot used in the earlier GEXF-based passes -- this is the closer analogue to Conover's
whole-observation-window scope. "Activity" = total original posts (post_lifespan.csv `author`
column) + total reposts made (repost_cascades.csv `relayer` column) per agent, over the full run.

Node-level filtering (standard approach): drop agents below the activity percentile threshold
entirely, then compute Q on the induced subgraph of edges where BOTH endpoints survive.
"""
import glob
import numpy as np
import pandas as pd

TAG = "ext-NONE_nmod-0_size-LARGEST_ch-BOTH"
CUR_DIR = "/Users/tomoyatakeda/Documents/polarized-vocal-minority-model/results"
CUR_SEEDS = [100, 101, 102, 103, 104]
HALF_WIDTH = 0.2


def load_activity_and_edges(seed):
    base = f"{CUR_DIR}/run_{seed}_{TAG}"
    cascades = pd.read_csv(f"{base}/posts/repost_cascades.csv", usecols=["author", "relayer"])
    lifespan = pd.read_csv(f"{base}/posts/post_lifespan.csv", usecols=["author"])
    opinions = pd.read_csv(f"{base}/degrees/agent_snapshot_final.csv", usecols=["agentId", "opinion"])
    opinion_map = dict(zip(opinions["agentId"], opinions["opinion"]))

    n_agents = len(opinion_map)
    orig_counts = lifespan["author"].value_counts()
    repost_counts = cascades["relayer"].value_counts()
    activity = pd.Series(0, index=range(n_agents), dtype=float)
    activity = activity.add(orig_counts, fill_value=0).add(repost_counts, fill_value=0)

    # cumulative weighted directed edge list: relayer -> author, weight = repost count
    edge_counts = cascades.groupby(["relayer", "author"]).size().reset_index(name="weight")
    return activity, edge_counts, opinion_map


def sign_modularity_weighted_df(edges, opinion_map, keep_set, half_width=HALF_WIDTH):
    e = edges[edges["relayer"].isin(keep_set) & edges["author"].isin(keep_set)].copy()
    e["op_u"] = e["relayer"].map(opinion_map)
    e["op_v"] = e["author"].map(opinion_map)
    e = e[(e["op_u"].abs() >= half_width) & (e["op_v"].abs() >= half_width)]
    w = e["weight"].sum()
    if w == 0:
        return float("nan"), 0
    kout = e.groupby("relayer")["weight"].sum()
    kin = e.groupby("author")["weight"].sum()
    nodes = set(kout.index) | set(kin.index)
    sign = {u: (1 if opinion_map[u] >= 0 else -1) for u in nodes}
    ko_pos = sum(kout.get(u, 0) for u in nodes if sign[u] == 1)
    ki_pos = sum(kin.get(u, 0) for u in nodes if sign[u] == 1)
    ko_neg = sum(kout.get(u, 0) for u in nodes if sign[u] == -1)
    ki_neg = sum(kin.get(u, 0) for u in nodes if sign[u] == -1)
    null_term = (ko_pos * ki_pos + ko_neg * ki_neg) / w
    same_sign = e[e["op_u"].apply(lambda x: x >= 0) == e["op_v"].apply(lambda x: x >= 0)]["weight"].sum()
    return (same_sign - null_term) / w, w


def main():
    thresholds = [0.0, 0.25, 0.50, 0.75, 0.90]  # bottom-percentile-by-activity cutoffs to drop
    results = {t: [] for t in thresholds}
    edge_survival = {t: [] for t in thresholds}

    for seed in CUR_SEEDS:
        activity, edges, opinion_map = load_activity_and_edges(seed)
        total_edges_w = edges["weight"].sum()
        for t in thresholds:
            cutoff = activity.quantile(t)
            keep_set = set(activity[activity > cutoff].index) if t > 0 else set(activity.index)
            q, w = sign_modularity_weighted_df(edges, opinion_map, keep_set)
            results[t].append(q)
            edge_survival[t].append(w / total_edges_w if total_edges_w else float("nan"))

    print("=== Current HEAD repost network: Q_sign vs. activity-percentile node filter ===")
    print("(cumulative full-run network reconstructed from repost_cascades.csv; 5 seeds)\n")
    for t in thresholds:
        q_vals = np.array(results[t])
        surv = np.array(edge_survival[t])
        print(f"  drop bottom {int(t*100):>2d}% by activity: "
              f"Q = {q_vals.mean():.4f} (std {q_vals.std():.4f})  "
              f"edge-weight retained = {surv.mean()*100:5.1f}%  "
              f"(per-seed Q: {['%.3f' % v for v in q_vals]})")


if __name__ == "__main__":
    main()
