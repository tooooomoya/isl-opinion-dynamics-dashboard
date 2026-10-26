#!/usr/bin/env python3
"""Summarise the start-network dial (rewire OFF): per net x feed, posting ratio by |X| group, extreme-minus-moderate gap, hub / sorting stats.
Usage: python3 scripts/analyze_dial.py > docs/report/_dial_table.md   (reads results/rsearch/dial_*/run_*)"""
import glob, re, numpy as np, pandas as pd, networkx as nx
from networkx.algorithms.community import modularity
XB = {"neutral": (0, 1/3), "moderate": (1/3, 2/3), "extreme": (2/3, 9)}
def one(d):
    a = pd.read_csv(d + "/metrics/agent_actions.csv"); a = a[a.step > a.step.max() - 5000]
    a = a.groupby("agentId")[["nPost", "nLike", "nReshare", "nRewire"]].sum(); a = a[a.sum(axis=1) > 0]
    pr = a.nPost / a.sum(axis=1)
    s = pd.read_csv(d + "/degrees/agent_snapshot_t0.csv").set_index("agentId"); x = s.intrinsicOpinion
    e = pd.read_csv(d + "/degrees/edges_t0.csv"); src, dst = e.columns[0], e.columns[1]
    r = {g: pr[(x.loc[pr.index].abs() >= lo) & (x.loc[pr.index].abs() < hi)].mean() for g, (lo, hi) in XB.items()}
    r["gap"] = r["extreme"] - r["moderate"]
    indeg = e.groupby(dst).size().reindex(x.index, fill_value=0).sort_values(ascending=False); n = len(x)
    p = indeg / indeg.sum(); r["inGini"] = 1 - 2 * ((np.cumsum(np.sort(p.values)) ).sum() / len(p)) + 1 / len(p)
    top = indeg.index[:max(1, n // 100)]; r["hubExtreme"] = (x.loc[top].abs() >= 2/3).mean(); r["top1share"] = indeg.loc[top].sum() / indeg.sum()
    hub5 = set(indeg.index[:n // 20]); h = e[e[src].isin(hub5) & e[dst].isin(hub5)]
    r["hubHubCross"] = (np.sign(x.loc[h[src]].values) != np.sign(x.loc[h[dst]].values)).mean() if len(h) else np.nan
    r["ownSideFollowee"] = (np.sign(x.loc[e[src]].values) == np.sign(x.loc[e[dst]].values)).mean()
    G = nx.Graph(); G.add_nodes_from(x.index); G.add_edges_from(zip(e[src], e[dst]))
    r["signMod"] = modularity(G, [set(x.index[x > 0]), set(x.index[x <= 0])]) if G.number_of_edges() else np.nan
    D = nx.DiGraph(); D.add_edges_from(zip(e[src], e[dst])); r["sccFrac"] = max(len(c) for c in nx.strongly_connected_components(D)) / n   # share of agents in the largest mutually-reachable set (HK is acyclic except its 16-node seed)
    return r
rows = []
for d in sorted(glob.glob("results/rsearch/dial_*/run_*")):
    m = re.search(r"dial_(.+)_(foryou|chrono)/", d + "/")
    try: rows.append({"net": m.group(1), "feed": m.group(2), **one(d)})
    except Exception as ex: print("skip", d, ex)
df = pd.DataFrame(rows); g = df.groupby(["net", "feed"]); out = g.mean().join(g.size().rename("seeds")).join(g.gap.sem().rename("gap_se"))
pd.set_option("display.width", 250); print(out.round(3).to_string())
