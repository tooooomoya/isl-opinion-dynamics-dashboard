"""
2026-08-01 -- Third pass: path-length/diameter, global transitivity, and a corrected
weighted sign-modularity Q for the repost network (the first pass's sign_modularity() was
unweighted -- fine for the follow graph, where Analysis.java's computeSignModularity is
also unweighted, but wrong for the repost graph, where Analysis.java uses
computeSignModularityFromMatrix, weighted by repost COUNT, matching how
computeInteractionAssortativity already weights -- see that function's 2026-07-15 comment).

Path-length metrics are computed on the undirected simplification of the graph, restricted to
the largest connected component (standard convention -- these eras' follow-graphs are not fully
connected, see largest_wcc_frac in the previous pass, and average_shortest_path_length is
undefined on a disconnected graph).

Adds:
  - weighted sign modularity Q (follow: unweighted, matches computeSignModularity; repost:
    weighted by repost count, matches computeSignModularityFromMatrix)
  - average shortest path length + diameter (undirected, largest connected component)
  - global transitivity (triangle/triple ratio -- distinct from the average per-node
    clustering coefficient already reported in the first pass)
  - networkx's built-in degree_assortativity_coefficient, as a cross-check on the first
    extra-metrics pass's custom structural_assortativity
"""
import argparse
import numpy as np
import networkx as nx

TAG_DEFAULT = "ext-NONE_nmod-0_size-LARGEST_ch-BOTH"


def load_graph(path):
    return nx.read_gexf(path)


def sign_modularity_weighted(G, half_width=0.2, weighted=False):
    nodes = [n for n in G.nodes() if abs(G.nodes[n]["opinion"]) >= half_width]
    node_set = set(nodes)
    kout = {u: 0.0 for u in nodes}
    kin = {u: 0.0 for u in nodes}
    edges = []
    for u, v, data in G.edges(data=True):
        if u not in node_set or v not in node_set:
            continue
        c = data.get("weight", 1.0) if weighted else 1.0
        if c <= 0:
            continue
        kout[u] += c
        kin[v] += c
        edges.append((u, v, c))
    w = sum(c for _, _, c in edges)
    if w == 0:
        return 0.0
    sign = {u: (1 if G.nodes[u]["opinion"] >= 0 else -1) for u in nodes}
    ko_pos = sum(kout[u] for u in nodes if sign[u] == 1)
    ki_pos = sum(kin[u] for u in nodes if sign[u] == 1)
    ko_neg = sum(kout[u] for u in nodes if sign[u] == -1)
    ki_neg = sum(kin[u] for u in nodes if sign[u] == -1)
    null_term = (ko_pos * ki_pos + ko_neg * ki_neg) / w
    same_sign_weight = sum(c for u, v, c in edges if sign[u] == sign[v])
    return (same_sign_weight - null_term) / w


def path_metrics(G):
    UG = G.to_undirected()
    components = list(nx.connected_components(UG))
    giant = UG.subgraph(max(components, key=len)).copy()
    apl = nx.average_shortest_path_length(giant)
    diam = nx.diameter(giant)
    return dict(avg_shortest_path=apl, diameter=diam, giant_frac=giant.number_of_nodes() / UG.number_of_nodes())


def structural_metrics(path, weighted_q):
    G = load_graph(path)
    q = sign_modularity_weighted(G, weighted=weighted_q)
    transitivity = nx.transitivity(G.to_undirected())
    try:
        deg_assort = nx.degree_assortativity_coefficient(G)
    except Exception:
        deg_assort = float("nan")
    pm = path_metrics(G)
    return dict(q_sign=q, transitivity=transitivity, degree_assortativity_nx=deg_assort, **pm)


def follow_path(base, seed, tag, step):
    return f"{base}/run_{seed}_{tag}/GEXF/lambda_0.0/step_{step}.gexf"


def repost_path(base, seed, tag, step):
    return f"{base}/run_{seed}_{tag}/GEXF/repostNW/repost_step_{step}.gexf"


def collect(base, seeds, kind, tag, step):
    rows = []
    for s in seeds:
        path = follow_path(base, s, tag, step) if kind == "follow" else repost_path(base, s, tag, step)
        m = structural_metrics(path, weighted_q=(kind == "repost"))
        m["seed"] = s
        rows.append(m)
    return rows


def summarize_rows(rows, label):
    print(f"\n=== {label} (n={len(rows)} seeds) ===")
    for k in ["q_sign", "avg_shortest_path", "diameter", "giant_frac", "transitivity", "degree_assortativity_nx"]:
        vals = np.array([r[k] for r in rows], dtype=float)
        print(f"  {k:26s}: mean={vals.mean():8.4f}  std={vals.std():8.4f}  "
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
        print(f"\n################ {kind.upper()} NETWORK -- structural coefficients ################")
        wssit_rows = collect(args.wssit_dir, args.wssit_seeds, kind, args.tag, args.step)
        cur_rows = collect(args.current_dir, args.current_seeds, kind, args.tag, args.step)
        summarize_rows(wssit_rows, f"WSSIT-era (870b318) {kind} network")
        summarize_rows(cur_rows, f"Current HEAD {kind} network")


if __name__ == "__main__":
    main()
