"""
2026-07-31 -- Extension of scripts/wssit_era_vs_current_comparison.py: additional metrics beyond
the first pass (structure/opinion assortativity/clustering), computed either directly from
already-generated GEXF node/edge attributes (both eras have opinion, boundedConfidence,
intrinsicOpinion on every node) or from the degrees/*.csv follower-count files. See
docs/report/2026-07-31-wssit-era-vs-current-model-diff.md for the first pass and context.

Formulas transcribed from src/analysis/Analysis.java (computeBimodalityCoefficient,
computeOpinionKurtosis, computeMeanTolerance/computeToleranceVar, computeBcExtremityCorrelation)
and from the project's existing calibration scripts (gini() in e.g.
scripts/app_pol_baseline_bo_v13_graded_bc.py) for the in-degree Gini coefficient, so results here
are on the same footing as this project's usual calibration-loss metrics.

Adds, beyond the first pass:
  - follow-network and repost-network in-degree Gini coefficient (hub concentration)
  - opinion bimodality coefficient (Sarle's b) and excess kurtosis
  - mean/var of bounded confidence ("tolerance") across the population
  - bc-extremity correlation (Pearson corr of |opinion| vs bc)
  - reciprocity (fraction of edges that are mutual)
  - largest weakly-connected-component fraction
  - structural (degree-degree) assortativity, as distinct from opinion assortativity
"""
import argparse
import csv
import numpy as np
import networkx as nx

TAG_DEFAULT = "ext-NONE_nmod-0_size-LARGEST_ch-BOTH"


def gini(x):
    x = np.sort(np.asarray(x, dtype=float))
    n = len(x)
    if n == 0 or x.sum() == 0:
        return float("nan")
    cum = np.cumsum(x)
    return (2 * np.sum((np.arange(1, n + 1)) * x) - (n + 1) * cum[-1]) / (n * cum[-1])


def load_indeg_csv(path):
    with open(path) as f:
        return [int(r["inDegree"]) for r in csv.DictReader(f)]


def indeg_gini_from_gexf(G):
    indeg = dict(G.in_degree())
    return gini(list(indeg.values()))


def bimodality_coefficient(opinions):
    n = len(opinions)
    if n < 4:
        return float("nan")
    mean = opinions.mean()
    d = opinions - mean
    m2, m3, m4 = (d ** 2).mean(), (d ** 3).mean(), (d ** 4).mean()
    if m2 < 1e-12:
        return float("nan")
    g1 = m3 / m2 ** 1.5
    g2 = m4 / m2 ** 2 - 3.0
    correction = 3.0 * (n - 1.0) ** 2 / ((n - 2.0) * (n - 3.0))
    return (g1 * g1 + 1.0) / (g2 + correction)


def excess_kurtosis(opinions):
    d = opinions - opinions.mean()
    m2, m4 = (d ** 2).mean(), (d ** 4).mean()
    return m4 / m2 ** 2 - 3.0 if m2 > 1e-12 else float("nan")


def pearson(x, y):
    x, y = np.asarray(x), np.asarray(y)
    if len(x) < 2:
        return float("nan")
    vx, vy = x.var(), y.var()
    denom = np.sqrt(vx * vy)
    return ((x * y).mean() - x.mean() * y.mean()) / denom if denom > 1e-12 else 0.0


def structural_assortativity(G):
    """Pearson correlation of (out-degree_source, in-degree_target) over directed edges --
    the degree-based analogue of Analysis.java's opinion assortativity, using total degree
    (in+out) at each endpoint as the standard networkx degree-assortativity convention."""
    deg = dict(G.degree())
    xs = [deg[u] for u, v in G.edges()]
    ys = [deg[v] for u, v in G.edges()]
    return pearson(xs, ys)


def node_level_metrics(path):
    G = load_graph(path)
    opinions = np.array([G.nodes[u]["opinion"] for u in G.nodes()])
    bc = np.array([G.nodes[u]["boundedConfidence"] for u in G.nodes()])
    n_nodes = G.number_of_nodes()
    n_wcc = nx.number_weakly_connected_components(G)
    largest_wcc_frac = max(len(c) for c in nx.weakly_connected_components(G)) / n_nodes
    return dict(
        indeg_gini=indeg_gini_from_gexf(G),
        bimodality=bimodality_coefficient(opinions),
        kurtosis=excess_kurtosis(opinions),
        mean_tolerance=bc.mean(),
        tolerance_var=bc.var(),
        bc_extremity_corr=pearson(np.abs(opinions), bc),
        reciprocity=nx.reciprocity(G) if G.number_of_edges() > 0 else float("nan"),
        largest_wcc_frac=largest_wcc_frac,
        structural_assortativity=structural_assortativity(G),
    )


def load_graph(path):
    return nx.read_gexf(path)


def follow_path(base, seed, tag, step):
    return f"{base}/run_{seed}_{tag}/GEXF/lambda_0.0/step_{step}.gexf"


def repost_path(base, seed, tag, step):
    return f"{base}/run_{seed}_{tag}/GEXF/repostNW/repost_step_{step}.gexf"


def collect(base, seeds, network_kind, tag, step):
    rows = []
    for s in seeds:
        path = (follow_path(base, s, tag, step) if network_kind == "follow"
                else repost_path(base, s, tag, step))
        m = node_level_metrics(path)
        m["seed"] = s
        rows.append(m)
    return rows


def summarize_rows(rows, label):
    print(f"\n=== {label} (n={len(rows)} seeds) ===")
    keys = ["indeg_gini", "bimodality", "kurtosis", "mean_tolerance", "tolerance_var",
            "bc_extremity_corr", "reciprocity", "largest_wcc_frac", "structural_assortativity"]
    for k in keys:
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
        print(f"\n################ {kind.upper()} NETWORK -- extra metrics ################")
        wssit_rows = collect(args.wssit_dir, args.wssit_seeds, kind, args.tag, args.step)
        cur_rows = collect(args.current_dir, args.current_seeds, kind, args.tag, args.step)
        summarize_rows(wssit_rows, f"WSSIT-era (870b318) {kind} network")
        summarize_rows(cur_rows, f"Current HEAD {kind} network")


if __name__ == "__main__":
    main()
