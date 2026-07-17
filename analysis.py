import os
import csv
import re
import math
import random
import threading
from pathlib import Path
from .core import result_dir, rnd

GRAPH_CACHE = {}
GRAPH_LOCK = threading.Lock()


def parse_gexf_cached(path: Path):
    st = os.stat(path)
    key = str(path)
    with GRAPH_LOCK:
        hit = GRAPH_CACHE.get(key)
        if hit and hit[0] == st.st_size:
            return hit[1]
    import networkx as nx  # deferred to keep core startup fast
    G = nx.read_gexf(path)
    with GRAPH_LOCK:
        GRAPH_CACHE[key] = (st.st_size, G)
        while len(GRAPH_CACHE) > 6:
            GRAPH_CACHE.pop(next(iter(GRAPH_CACHE)))
    return G


def load_network(path: Path):
    """Lightweight per-node payload for the client-side force layout + metrics."""
    G = parse_gexf_cached(path)
    ids = list(G.nodes)
    idx = {nid: i for i, nid in enumerate(ids)}
    op = {nid: float(G.nodes[nid].get("opinion", 0.0)) for nid in ids}
    nodes = []
    for nid in ids:
        d = G.nodes[nid]
        outs = list(G.successors(nid))
        nbr = round(sum(op[v] for v in outs) / len(outs), 4) if outs else None
        nodes.append({
            "op": round(op[nid], 4),
            "indeg": G.in_degree(nid), "outdeg": G.out_degree(nid),
            "hub": bool(d.get("target", False)),
            "bc": round(float(d.get("boundedConfidence", 0.0)), 4),
            "pp": round(float(d.get("postProb", 0.0)), 4),
            "nbrOp": nbr,
        })
    # weight: repost count on that edge (repostNW); Gephi's GEXF exporter omits the
    # attribute entirely when it equals the default (1.0), so a missing key means 1.
    edges = [[idx[u], idx[v], round(float(dat.get("weight") or 1.0), 4)]
             for u, v, dat in G.edges(data=True)]
    return {"n": len(nodes), "m": len(edges), "nodes": nodes, "edges": edges}


def _read_col(path: Path, col: str, caster):
    try:
        with open(path, newline="") as f:
            return [caster(row[col]) for row in csv.DictReader(f)]
    except (FileNotFoundError, KeyError, ValueError):
        return None


def fit_powerlaw(values):
    """MLE power-law fit + exponential plausibility check."""
    arr = [v for v in values if v and v > 0] if values else []
    if len(arr) < 20:
        return {"unavailable": "too-few", "n": len(arr)}
    try:
        import powerlaw
        fit = powerlaw.Fit(arr, discrete=True, verbose=False)
        R, p = fit.distribution_compare("power_law", "exponential")
        R_ln, p_ln = fit.distribution_compare("power_law", "lognormal")
        return {"alpha": round(float(fit.power_law.alpha), 3), "xmin": float(fit.power_law.xmin),
                "R": round(float(R), 3), "p": round(float(p), 4), "plausible": bool(R > 0),
                "R_lognormal": round(float(R_ln), 3), "p_lognormal": round(float(p_ln), 4)}
    except Exception as e:
        return {"unavailable": "error", "detail": f"{type(e).__name__}: {e}"[:200], "n": len(arr)}


def hartigan_dip(values):
    """Hartigan & Hartigan (1985) dip statistic for unimodality check."""
    n = len(values)
    if n < 4:
        return None
    x = [0.0] + sorted(values)
    if x[n] == x[1]:
        return 0.0
    mn = [0] * (n + 1)
    mj = [0] * (n + 1)
    gcm = [0] * (n + 2)
    lcm = [0] * (n + 2)
    mn[1] = 1
    for j in range(2, n + 1):
        mn[j] = j - 1
        while True:
            mnj = mn[j]; mnmnj = mn[mnj]
            if mnj == 1 or (x[j] - x[mnj]) * (mnj - mnmnj) < (x[mnj] - x[mnmnj]) * (j - mnj):
                break
            mn[j] = mnmnj
    mj[n] = n
    for k in range(n - 1, 0, -1):
        mj[k] = k + 1
        while True:
            mjk = mj[k]; mjmjk = mj[mjk]
            if mjk == n or (x[k] - x[mjk]) * (mjk - mjmjk) < (x[mjk] - x[mjmjk]) * (k - mjk):
                break
            mj[k] = mjmjk

    low, high, dip = 1, n, 0.0
    while True:
        gcm[1] = high
        i = 1
        while gcm[i] > low:
            gcm[i + 1] = mn[gcm[i]]; i += 1
        ig = l_gcm = i
        ix = ig - 1
        lcm[1] = low
        i = 1
        while lcm[i] < high:
            lcm[i + 1] = mj[lcm[i]]; i += 1
        ih = l_lcm = i
        iv = 2
        d = 0.0
        if l_gcm != 2 or l_lcm != 2:
            while gcm[ix] != lcm[iv]:
                gcmix = gcm[ix]; lcmiv = lcm[iv]
                if gcmix > lcmiv:
                    gcmi1 = gcm[ix + 1]
                    dx = ((lcmiv - gcmi1 + 1)
                          - (x[lcmiv] - x[gcmi1]) * (gcmix - gcmi1) / (x[gcmix] - x[gcmi1]))
                    iv += 1
                    if dx >= d:
                        d = dx; ig = ix + 1; ih = iv - 1
                else:
                    lcmiv1 = lcm[iv - 1]
                    dx = ((x[gcmix] - x[lcmiv1]) * (lcmiv - lcmiv1) / (x[lcmiv] - x[lcmiv1])
                          - (gcmix - lcmiv1 - 1))
                    ix -= 1
                    if dx >= d:
                        d = dx; ig = ix + 1; ih = iv
                if ix < 1: ix = 1
                if iv > l_lcm: iv = l_lcm
        if d < dip:
            break
        dip_l = 0.0
        for j in range(ig, l_gcm):
            max_t = 1.0
            jb = gcm[j + 1]; je = gcm[j]
            if je - jb > 1 and x[je] != x[jb]:
                C = (je - jb) / (x[je] - x[jb])
                for jj in range(jb, je + 1):
                    t = (jj - jb + 1) - (x[jj] - x[jb]) * C
                    if max_t < t: max_t = t
            if dip_l < max_t: dip_l = max_t
        dip_u = 0.0
        for j in range(ih, l_lcm):
            max_t = 1.0
            jb = lcm[j]; je = lcm[j + 1]
            if je - jb > 1 and x[je] != x[jb]:
                C = (je - jb) / (x[je] - x[jb])
                for jj in range(jb, je + 1):
                    t = (x[jj] - x[jb]) * C - (jj - jb - 1)
                    if max_t < t: max_t = t
            if dip_u < max_t: dip_u = max_t
        dipnew = dip_u if dip_u > dip_l else dip_l
        if dip < dipnew:
            dip = dipnew
        if low == gcm[ig] and high == lcm[ih]:
            break
        low = gcm[ig]; high = lcm[ih]
    return dip / (2 * n)


DIP_BOOT = {}
DIP_BOOT_LOCK = threading.Lock()


def dip_diagnostics(values, boots=200):
    """Dip + bootstrap p-value against the uniform null."""
    try:
        d = hartigan_dip(values)
        if d is None:
            return {"unavailable": "degenerate", "n": len(values)}
        n = len(values)
        with DIP_BOOT_LOCK:
            boot = DIP_BOOT.get(n)
        if boot is None:
            rng = random.Random(180571)
            boot = sorted(hartigan_dip([rng.random() for _ in range(n)]) or 0.0
                          for _ in range(boots))
            with DIP_BOOT_LOCK:
                DIP_BOOT[n] = boot
                while len(DIP_BOOT) > 8:
                    DIP_BOOT.pop(next(iter(DIP_BOOT)))
        p = (sum(1 for b in boot if b >= d) + 1) / (len(boot) + 1)
        return {"dip": round(d, 4), "p": round(p, 4), "n": n, "B": len(boot)}
    except Exception as e:
        return {"unavailable": "error", "detail": f"{type(e).__name__}: {e}"[:200]}


def compute_rwc(Gg):
    """Random Walk Controversy (Garimella et al. 2018) via absorbing Markov chains."""
    n = Gg.number_of_nodes()
    if n < 20:
        return {"unavailable": "too-few", "n": n}
    try:
        nodes = list(Gg.nodes)
        op = {u: float(Gg.nodes[u].get("opinion", 0.0)) for u in nodes}
        side_x = [u for u in nodes if op[u] >= 0]
        side_y = [u for u in nodes if op[u] < 0]
        if not side_x or not side_y:
            return {"unavailable": "one-sided"}
        k = min(max(3, int(round(0.01 * n))), len(side_x), len(side_y))
        deg = dict(Gg.degree())
        abs_x = set(sorted(side_x, key=lambda u: -deg[u])[:k])
        abs_y = set(sorted(side_y, key=lambda u: -deg[u])[:k])
        absorbing = abs_x | abs_y
        trans = [u for u in nodes if u not in absorbing]
        tidx = {u: i for i, u in enumerate(trans)}
        import numpy as np
        from scipy.sparse import coo_matrix, identity
        from scipy.sparse.linalg import spsolve
        rows, cols, data = [], [], []
        b_x = np.zeros(len(trans))
        for u in trans:
            nbrs = list(Gg.neighbors(u))
            if not nbrs:
                continue
            w = 1.0 / len(nbrs)
            for v in nbrs:
                if v in abs_x:
                    b_x[tidx[u]] += w
                elif v not in abs_y:
                    rows.append(tidx[u]); cols.append(tidx[v]); data.append(w)
        Q = coo_matrix((data, (rows, cols)), shape=(len(trans), len(trans))).tocsr()
        p_x = spsolve((identity(len(trans), format="csr") - Q).tocsr(), b_x)
        p_xx = (float(sum(p_x[tidx[u]] for u in side_x if u in tidx)) + len(abs_x)) / len(side_x)
        p_yx = float(sum(p_x[tidx[u]] for u in side_y if u in tidx)) / len(side_y)
        p_yy = 1.0 - p_yx
        p_xy = 1.0 - p_xx
        rwc = p_xx * p_yy - p_xy * p_yx
        return {"rwc": round(rwc, 4), "pXX": round(p_xx, 4), "pYY": round(p_yy, 4),
                "k": k, "sideX": len(side_x), "sideY": len(side_y)}
    except Exception as e:
        return {"unavailable": "error", "detail": f"{type(e).__name__}: {e}"[:200]}


STRUCT_CACHE = {}
STRUCT_LOCK = threading.Lock()


def compute_structural(gexf_path: Path, degree_csv: Path, clustering_csv: Path):
    """Snapshot-level structural metrics from follow/repost graph + Java outputs."""
    st = os.stat(gexf_path)
    key = str(gexf_path)
    with STRUCT_LOCK:
        hit = STRUCT_CACHE.get(key)
        if hit and hit[0] == st.st_size:
            return hit[1]
    import networkx as nx
    G = parse_gexf_cached(gexf_path)
    Gu = G.to_undirected()
    giant_frac, lambda2, bc_mean, bc_top = None, None, None, []
    rwc = None
    n_nodes, n_edges = Gu.number_of_nodes(), Gu.number_of_edges()
    avg_degree = round(2 * n_edges / n_nodes, 4) if n_nodes else None
    density = round(nx.density(Gu), 6) if n_nodes > 1 else None
    avg_path_length, diameter = None, None
    if Gu.number_of_nodes() > 0:
        giant_nodes = max(nx.connected_components(Gu), key=len)
        Gg = Gu.subgraph(giant_nodes).copy()
        giant_frac = round(len(giant_nodes) / Gu.number_of_nodes(), 4)
        if Gg.number_of_nodes() > 2:
            try:
                lambda2 = round(float(nx.algebraic_connectivity(Gg, method="tracemin_pcg")), 6)
            except Exception:
                lambda2 = None
            bc = nx.betweenness_centrality(Gg)
            bc_vals = list(bc.values())
            bc_mean = round(sum(bc_vals) / len(bc_vals), 6) if bc_vals else None
            top = sorted(bc.items(), key=lambda kv: -kv[1])[:10]
            bc_top = [{"id": nid, "value": round(v, 6), "hub": bool(G.nodes[nid].get("target", False))}
                      for nid, v in top]
            # exact APL/diameter is O(n*m) BFS sweeps; fine at ~1e3 nodes, so only
            # skip it once the giant component gets too large to stay responsive
            if Gg.number_of_nodes() <= 3000:
                try:
                    ecc = nx.eccentricity(Gg)
                    avg_path_length = round(nx.average_shortest_path_length(Gg), 4)
                    diameter = max(ecc.values())
                except Exception:
                    avg_path_length, diameter = None, None
        rwc = compute_rwc(Gg)

    opinions = [float(G.nodes[nid].get("opinion", 0.0)) for nid in G.nodes]
    dip = dip_diagnostics(opinions)

    degree = {
        "in": _read_col(degree_csv, "inDegree", int),
        "out": _read_col(degree_csv, "outDegree", int),
    }
    if degree["in"] is not None and degree["out"] is not None:
        degree["total"] = [a + b for a, b in zip(degree["in"], degree["out"])]
    degree_fit = {k: fit_powerlaw(v) for k, v in degree.items()}

    clustering_vals = _read_col(clustering_csv, "clusteringCoefficient", float)
    clustering = {
        "values": clustering_vals,
        "mean": round(sum(clustering_vals) / len(clustering_vals), 6) if clustering_vals else None,
    }

    payload = {
        "giantComponentFrac": giant_frac, "lambda2": lambda2,
        "betweenness": {"mean": bc_mean, "top": bc_top},
        "degree": degree, "degreeFit": degree_fit, "clustering": clustering,
        "rwc": rwc, "dip": dip,
        "nNodes": n_nodes, "nEdges": n_edges, "avgDegree": avg_degree,
        "density": density, "avgPathLength": avg_path_length, "diameter": diameter,
    }
    with STRUCT_LOCK:
        STRUCT_CACHE[key] = (st.st_size, payload)
        while len(STRUCT_CACHE) > 8:
            STRUCT_CACHE.pop(next(iter(STRUCT_CACHE)))
    return payload


def api_network(qs):
    seed = int(qs.get("seed", ["-1"])[0])
    net = qs.get("net", ["follow"])[0]
    want_step = qs.get("step", ["latest"])[0]
    want_structural = qs.get("structural", ["0"])[0] == "1"
    d = result_dir(seed)
    empty = {"steps": [], "step": None, "nodes": [], "edges": []}
    if d is None or not (d / "GEXF").is_dir():
        return empty
    if net == "repost":
        sub = d / "GEXF" / "repostNW"
    else:
        subs = [p for p in (d / "GEXF").iterdir() if p.is_dir() and p.name != "repostNW"]
        sub = subs[0] if subs else None
    if sub is None or not sub.is_dir():
        return empty
    snaps = {}
    for f in sub.glob("*.gexf"):
        m = re.search(r"step_(\d+)\.gexf$", f.name)
        if m:
            snaps[int(m.group(1))] = f
    if not snaps:
        return empty
    steps = sorted(snaps)
    step = steps[-1] if want_step == "latest" else int(want_step)
    if step not in snaps:
        step = steps[-1]
    candidates = [s for s in reversed(steps) if s <= step] or [steps[-1]]
    last_err = None
    for i, s in enumerate(candidates):
        try:
            payload = load_network(snaps[s])
            result = {"steps": steps, "step": s, "stale": i > 0, **payload}
            if want_structural:
                try:
                    # 2026-07-15: repost graph structural CSVs are a distinct pair
                    # (Writer.writeRepostDegrees/writeRepostClusteringCoefficients) written from
                    # the SAME windowed repostNetwork matrix repostGephi exports here — using the
                    # follow-graph CSVs for net=repost would silently describe the wrong graph
                    # (the bug this migration fixes: the degree/clustering panel used to always
                    # read the follow-graph CSVs regardless of which graph was on screen).
                    deg_prefix = "repost_degree_result_" if net == "repost" else "degree_result_"
                    clu_prefix = "repost_clustering_result_" if net == "repost" else "clustering_result_"
                    result["structural"] = compute_structural(
                        snaps[s], d / "degrees" / f"{deg_prefix}{s}.csv",
                        d / "clusterings" / f"{clu_prefix}{s}.csv")
                except Exception as e:
                    result["structuralError"] = f"{type(e).__name__}: {e}"
            return result
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            continue
    return {"steps": steps, "step": None, "n": 0, "m": 0, "nodes": [], "edges": [],
            "error": f"snapshot(s) unreadable (likely still being written): {last_err}"}
