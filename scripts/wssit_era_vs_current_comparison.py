"""
2026-07-31 -- Compare follow-network and repost-network structure between the WSSIT2026-era
model (commit 870b318, the last commit before the Type-1/Type-2 pivot in
docs/research-direction.md) and the current HEAD model. See
docs/report/2026-07-31-wssit-era-vs-current-model-diff.md for the full writeup and static
param diff; this script only reproduces the metric computation over already-generated GEXF
snapshots.

Both eras must be run with `extreme=none n_neutral=0` (matches current HEAD's default; WSSIT-era's
own default is `extreme=SYM n_neutral=1`, i.e. with the intervention harness active -- forcing NONE
on both isolates baseline network/opinion dynamics from that harness, which differs in shape
between eras and isn't the object of this comparison).

Metric formulas are transcribed line-for-line from src/analysis/Analysis.java so both eras are
scored under one metric definition rather than two independently-coded implementations that
could silently diverge:
  - opinion assortativity: Pearson correlation of (opinion_i, opinion_j) over directed edges
    (computeOpinionAssortativity / computeInteractionAssortativity).
  - cross-cutting fraction / sign modularity Q: computeCrossCuttingFraction /
    the R16.4 directed-Newman-modularity-of-sign-partition formula.
  - clustering coefficient: per-node, neighborhood = union of in- and out-neighbors, linkCount =
    ordered pairs (u,v) in the neighborhood with an edge u->v, coefficient = linkCount /
    (k*(k-1)) (computeClusteringCoefficients -- NOT the same as networkx's built-in directed
    clustering, which uses a different formula).

Usage:
  python3 scripts/wssit_era_vs_current_comparison.py \
      --wssit-dir /path/to/wssit_era_worktree/results --wssit-seeds 0 1 2 3 4 \
      --current-dir results --current-seeds 100 101 102 103 104
"""
import argparse
import numpy as np
import networkx as nx

TAG_DEFAULT = "ext-NONE_nmod-0_size-LARGEST_ch-BOTH"


def load_graph(path):
    return nx.read_gexf(path)


def opinion_assortativity(G, weight=None):
    sx = sy = sxy = sx2 = sy2 = 0.0
    m = 0.0
    for u, v, data in G.edges(data=True):
        x = G.nodes[u]["opinion"]
        y = G.nodes[v]["opinion"]
        c = data.get(weight, 1.0) if weight else 1.0
        sx += c * x; sy += c * y; sxy += c * x * y
        sx2 += c * x * x; sy2 += c * y * y
        m += c
    if m == 0:
        return 0.0
    cov = sxy / m - (sx / m) * (sy / m)
    vx = sx2 / m - (sx / m) ** 2
    vy = sy2 / m - (sy / m) ** 2
    denom = np.sqrt(vx * vy)
    return cov / denom if denom > 1e-12 else 0.0


def clustering_java_formula(G):
    nodes = list(G.nodes())
    idx = {u: i for i, u in enumerate(nodes)}
    n = len(nodes)
    succ = [set() for _ in range(n)]
    pred = [set() for _ in range(n)]
    for u, v in G.edges():
        succ[idx[u]].add(idx[v])
        pred[idx[v]].add(idx[u])

    clustering = np.zeros(n)
    for i in range(n):
        neighbors = (succ[i] | pred[i]) - {i}
        k = len(neighbors)
        if k < 2:
            continue
        link_count = sum(len(succ[u] & neighbors) for u in neighbors)
        clustering[i] = link_count / (k * (k - 1))
    return clustering


def cross_cutting_fraction(G, half_width=0.2):
    cross = total = 0
    for u, v in G.edges():
        ou, ov = G.nodes[u]["opinion"], G.nodes[v]["opinion"]
        if abs(ou) < half_width or abs(ov) < half_width:
            continue
        total += 1
        if ou * ov < 0:
            cross += 1
    return cross / total if total else 0.0


def sign_modularity(G, half_width=0.2):
    nodes = [n for n in G.nodes() if abs(G.nodes[n]["opinion"]) >= half_width]
    node_set = set(nodes)
    edges = [(u, v) for u, v in G.edges() if u in node_set and v in node_set]
    m = len(edges)
    if m == 0:
        return 0.0
    kout = {u: 0 for u in nodes}
    kin = {u: 0 for u in nodes}
    for u, v in edges:
        kout[u] += 1
        kin[v] += 1
    sign = {u: (1 if G.nodes[u]["opinion"] > 0 else -1) for u in nodes}
    same_sign_edges = sum(1 for u, v in edges if sign[u] == sign[v])
    kout_pos = sum(kout[u] for u in nodes if sign[u] == 1)
    kin_pos = sum(kin[u] for u in nodes if sign[u] == 1)
    kout_neg = sum(kout[u] for u in nodes if sign[u] == -1)
    kin_neg = sum(kin[u] for u in nodes if sign[u] == -1)
    return (same_sign_edges - (kout_pos * kin_pos + kout_neg * kin_neg) / m) / m


def follow_path(base, seed, tag, step):
    return f"{base}/run_{seed}_{tag}/GEXF/lambda_0.0/step_{step}.gexf"


def repost_path(base, seed, tag, step):
    return f"{base}/run_{seed}_{tag}/GEXF/repostNW/repost_step_{step}.gexf"


def collect(base, seeds, network_kind, tag, step):
    rows = []
    for s in seeds:
        path = (follow_path(base, s, tag, step) if network_kind == "follow"
                else repost_path(base, s, tag, step))
        G = load_graph(path)
        degs = np.array([d for _, d in G.out_degree()])
        clus = clustering_java_formula(G)
        weight = "weight" if network_kind == "repost" else None
        rows.append(dict(
            seed=s, e=G.number_of_edges(), deg_mean=degs.mean(), deg_std=degs.std(),
            clustering=clus.mean(), assortativity=opinion_assortativity(G, weight=weight),
            cross_cutting=cross_cutting_fraction(G), modularity=sign_modularity(G),
        ))
    return rows


def summarize_rows(rows, label):
    print(f"\n=== {label} (n={len(rows)} seeds) ===")
    for k in ["e", "deg_mean", "deg_std", "clustering", "assortativity", "cross_cutting", "modularity"]:
        vals = np.array([r[k] for r in rows])
        print(f"  {k:15s}: mean={vals.mean():8.4f}  std={vals.std():8.4f}  "
              f"(per-seed: {['%.3f' % v for v in vals]})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wssit-dir", required=True)
    ap.add_argument("--wssit-seeds", nargs="+", type=int, required=True)
    ap.add_argument("--current-dir", required=True)
    ap.add_argument("--current-seeds", nargs="+", type=int, required=True)
    ap.add_argument("--tag", default=TAG_DEFAULT)
    ap.add_argument("--step", type=int, default=40000)
    args = ap.parse_args()

    for kind in ("follow", "repost"):
        print(f"\n################ {kind.upper()} NETWORK ################")
        wssit_rows = collect(args.wssit_dir, args.wssit_seeds, kind, args.tag, args.step)
        cur_rows = collect(args.current_dir, args.current_seeds, kind, args.tag, args.step)
        summarize_rows(wssit_rows, f"WSSIT-era (870b318) {kind} network")
        summarize_rows(cur_rows, f"Current HEAD {kind} network")


if __name__ == "__main__":
    main()
