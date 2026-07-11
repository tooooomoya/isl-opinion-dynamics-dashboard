#!/usr/bin/env python3
"""Live dashboard for a run.sh batch: tails logs/ + results/*/metrics/ while
seeds are still running.

Usage (while ./run.sh is running in another terminal):
    python dashboard/dashboard.py                    # local GUI window (needs a display)
    python dashboard/dashboard.py --serve             # interactive web dashboard (for SSH)
    python dashboard/dashboard.py --serve --port 8765
    python dashboard/dashboard.py --seeds 0 1 2 --interval 10

--serve is for working over SSH (e.g. VSCode Remote-SSH): it starts a tiny local
HTTP server that serves dashboard/dashboard.html (an interactive SVG dashboard:
hover tooltips, drag-zoom, per-seed toggles, metric picker, the 2-D outcome
plane, opinion-distribution evolution, log tails, dark mode) plus JSON APIs.
VSCode auto-forwards the port — open the PORTS tab (or the toast it pops) and
click the forwarded link, or Cmd/Ctrl+Shift+P -> "Simple Browser: Show" ->
http://127.0.0.1:<port>.

Data comes straight from results/run_<seed>_*/{metrics,opinion}/ CSVs, read
incrementally (byte-offset tailing + adaptive decimation), so a 15 MB
results.csv is never re-parsed from scratch on each poll. Seed status
(running/done/failed) comes from the same logs/run_<seed>.log markers
scripts/check_progress.sh uses. Read-only — never edits results/ or logs/.
"""
import argparse
import csv
import json
import math
import os
import random
import re
import sys
import threading
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
HTML_PATH = Path(__file__).resolve().parent / "dashboard.html"

# dataviz skill categorical palette (fixed order, not cycled by rank)
COLORS = [
    "#2a78d6", "#1baf7a", "#eda100", "#008300",
    "#4a3aa7", "#e34948", "#e87ba4", "#eb6834",
]

METRICS = [
    ("opinionAssortativity", "opinion assortativity"),
    ("crossCuttingFraction", "cross-cutting fraction"),
    ("Q_sign", "modularity (Q_sign)"),
    ("bimodalityCoeff", "bimodality coeff."),
    ("opinionKurtosis", "opinion kurtosis"),
    ("disagreement", "disagreement"),
]
RESULTS_COLS = ["step", "opinionAssortativity", "crossCuttingFraction",
                "bimodalityCoeff", "opinionKurtosis", "disagreement"]

SEED_RE = re.compile(r"run_(\d+)\.log$")
DEFAULT_TARGET_STEPS = 40000

# Metrics computed from existing results.csv columns rather than written by the
# simulator. (deps, fn): fn is applied elementwise to the same-index values of
# each dep column; any missing/NaN dep at an index yields None for that point.
#   apparentPolarization: exposureOpinionVar - opinionVar — how much more spread
#     out the posts people are EXPOSED to are than the opinions they actually HOLD.
#   EI_index: Krackhardt & Stern E-I index, rescaled from the already-tracked
#     crossCuttingFraction (= E/(E+I) on the follow graph, sign-camp grouping —
#     see Analysis.computeCrossCuttingFraction), so EI = 2*fraction - 1. Not a
#     new computation, just the signed [-1,1] convention (-1 = all-internal
#     echo chamber, +1 = all-external) instead of the [0,1] fraction. Lives in
#     the network-structure panel, not the general metric picker (see
#     api_summary) — request it explicitly via /api/series?cols=EI_index.
#   repostShare: repostCount / (repostCount + originalPostCount) — what fraction
#     of a step's content is relayed rather than original.
DERIVED = {
    "apparentPolarization": (("exposureOpinionVar", "opinionVar"), lambda a, b: a - b),
    "repostShare": (("repostCount", "originalPostCount"),
                     lambda r, o: (r / (r + o)) if (r + o) > 0 else None),
    "EI_index": (("crossCuttingFraction",), lambda c: 2 * c - 1),
}
# Advertised in api_summary's general "columns" list (metric-picker-visible).
# EI_index is deliberately excluded — it's fetched directly by the structural panel.
DERIVED_IN_PICKER = ("apparentPolarization", "repostShare")

FAMILY_RE = re.compile(r"^(.+)_([0-4])$")


def active_seeds(logdir: Path, only=None):
    """seed -> status ('running' | 'done' | 'failed'), from logs/run_<seed>.log."""
    out = {}
    for f in sorted(logdir.glob("run_*.log")):
        m = SEED_RE.search(f.name)
        if not m:
            continue
        seed = int(m.group(1))
        if only is not None and seed not in only:
            continue
        text = f.read_text(errors="ignore")
        if re.search(r"Exception|TERMINATE", text):
            status = "failed"
        elif "Elapsed time" in text:
            status = "done"
        else:
            status = "running"
        out[seed] = status
    return out


def result_dir(seed: int):
    """Newest results/run_<seed>_<tag>/ folder for this seed (mtime-based —
    a stale folder from an older sweep with the same seed won't be touched
    by the current run, so the live one is always the most recently modified)."""
    candidates = list(ROOT.glob(f"results/run_{seed}_*"))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


# ---------------------------------------------------------------- GUI mode --

def load_seed_data(seed: int):
    import pandas as pd
    d = result_dir(seed)
    if d is None:
        return None
    try:
        df = pd.read_csv(d / "metrics" / "results.csv", usecols=RESULTS_COLS,
                          on_bad_lines="skip")
    except (FileNotFoundError, pd.errors.EmptyDataError, pd.errors.ParserError):
        return None
    try:
        mod = pd.read_csv(d / "metrics" / "modularity.csv", on_bad_lines="skip")
        df = df.merge(mod, on="step", how="left")
    except (FileNotFoundError, pd.errors.EmptyDataError, pd.errors.ParserError):
        df["Q_sign"] = float("nan")
    return df


def redraw(fig, axes, logdir: Path, only, interval: float):
    statuses = active_seeds(logdir, only)
    seeds = sorted(statuses)

    for ax, (_col, label) in zip(axes, METRICS):
        ax.clear()
        ax.set_title(label, fontsize=10)
        ax.set_xlabel("step")
        ax.grid(True, color="#e1e0d9", linewidth=0.6)
        for spine in ax.spines.values():
            spine.set_color("#c3c2b7")

    for i, seed in enumerate(seeds):
        df = load_seed_data(seed)
        if df is None or df.empty:
            continue
        color = COLORS[i % len(COLORS)]
        style = "-" if i < len(COLORS) else "--"
        for ax, (col, _label) in zip(axes, METRICS):
            if col in df.columns:
                sub = df[["step", col]].dropna()
                ax.plot(sub["step"], sub[col], style, color=color,
                        linewidth=1.5, label=f"seed {seed} ({statuses[seed]})")

    handles, labels = axes[0].get_legend_handles_labels()
    if handles:
        fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.94),
                   ncol=min(len(labels), 8), fontsize=8, frameon=False)
    n_run = sum(1 for s in statuses.values() if s == "running")
    n_done = sum(1 for s in statuses.values() if s == "done")
    n_fail = sum(1 for s in statuses.values() if s == "failed")
    fig.suptitle(f"run.sh live dashboard — running={n_run} done={n_done} "
                 f"failed={n_fail}  (refresh {interval:.0f}s)", fontsize=11, y=0.99)
    fig.tight_layout(rect=(0, 0, 1, 0.88))


def run_gui(logdir: Path, only, interval: float):
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation
    fig, axes = plt.subplots(2, 3, figsize=(15, 8))
    axes = axes.flatten()
    ani = FuncAnimation(fig, lambda _frame: redraw(fig, axes, logdir, only, interval),
                         interval=interval * 1000, cache_frame_data=False)
    plt.show()


# -------------------------------------------------------------- serve mode --

class CsvTail:
    """Incrementally tail-parse an all-numeric CSV.

    Keeps a byte offset and only parses appended complete lines on each poll.
    Storage is bounded by adaptive decimation: when kept rows exceed max_rows,
    every other row is dropped and the keep-stride doubles, so memory stays
    O(max_rows) no matter how long the run gets. Detects file replacement
    (force=true deletes and recreates the folder) via inode/size and resets.
    """

    def __init__(self, path: Path, max_rows: int = 4000):
        self.path = path
        self.max_rows = max_rows
        self.reset()

    def reset(self):
        self.offset = 0
        self.header = None
        self.rows = []
        self.stride = 1
        self.row_i = 0
        self.ino = None

    def poll(self):
        try:
            st = os.stat(self.path)
        except FileNotFoundError:
            self.reset()
            return
        if self.ino is not None and (st.st_ino != self.ino or st.st_size < self.offset):
            self.reset()
        self.ino = st.st_ino
        if st.st_size == self.offset:
            return
        with open(self.path, "rb") as f:
            f.seek(self.offset)
            chunk = f.read(st.st_size - self.offset)
        nl = chunk.rfind(b"\n")
        if nl < 0:
            return  # no complete new line yet; keep offset, retry next poll
        self.offset += nl + 1
        for line in chunk[:nl].decode("utf-8", errors="replace").split("\n"):
            line = line.strip()
            if not line:
                continue
            if self.header is None:
                self.header = line.split(",")
                continue
            if self.row_i % self.stride == 0:
                vals = []
                for tok in line.split(","):
                    try:
                        vals.append(float(tok))
                    except ValueError:
                        vals.append(float("nan"))
                if len(vals) == len(self.header):
                    self.rows.append(vals)
            self.row_i += 1
            if len(self.rows) > self.max_rows:
                # kept rows are row_i % stride == 0; [::2] keeps % (2*stride) == 0
                self.rows = self.rows[::2]
                self.stride *= 2

    def column(self, name):
        if self.header is None or name not in self.header:
            return None
        i = self.header.index(name)
        return [r[i] for r in self.rows]


class SeedStore:
    """The tailed CSVs of one seed's live result folder."""

    def __init__(self, seed: int, d: Path):
        self.seed = seed
        self.dir = d
        self.main = CsvTail(d / "metrics" / "results.csv")
        self.mod = CsvTail(d / "metrics" / "modularity.csv")
        self.op = CsvTail(d / "opinion" / "opinion_result.csv", max_rows=2000)
        # repost_cascades.csv is an EVENT log (one row per repost, not per step) —
        # can have far more rows than steps, hence the larger cap. Only present
        # when log_repost_cascade=true (the default); CsvTail.poll() is a no-op
        # (not an error) while the file doesn't exist.
        self.repost = CsvTail(d / "posts" / "repost_cascades.csv", max_rows=8000)

    def poll(self):
        self.main.poll()
        self.mod.poll()
        self.op.poll()
        self.repost.poll()


STORES = {}          # seed -> SeedStore
LOCK = threading.Lock()
SERVE_LOGDIR = None  # set at startup
SERVE_ONLY = None


def poll_all():
    """Refresh statuses and tail every store. Call under LOCK."""
    statuses = active_seeds(SERVE_LOGDIR, SERVE_ONLY)
    for seed in statuses:
        d = result_dir(seed)
        if d is None:
            STORES.pop(seed, None)
            continue
        st = STORES.get(seed)
        if st is None or st.dir != d:
            STORES[seed] = st = SeedStore(seed, d)
        st.poll()
    for seed in list(STORES):
        if seed not in statuses:
            del STORES[seed]
    return statuses


def rnd(v):
    return None if (v is None or math.isnan(v)) else round(v, 6)


def decimate(arr, max_pts):
    if len(arr) <= max_pts:
        return arr
    k = math.ceil(len(arr) / max_pts)
    return arr[::k]


def api_summary():
    with LOCK:
        statuses = poll_all()
        cols = set()
        seeds = []
        for seed in sorted(statuses):
            st = STORES.get(seed)
            step, tag, target = 0, "", DEFAULT_TARGET_STEPS
            if st is not None:
                tag = st.dir.name.removeprefix(f"run_{seed}_")
                m = re.search(r"_st-(\d+)", st.dir.name)
                if m:
                    target = int(m.group(1))
                s = st.main.column("step")
                if s:
                    step = int(s[-1])
                if st.main.header:
                    cols.update(st.main.header)
        # steps=N below the default also shrinks the target; trust data when it
        # overruns the parsed target (older folders without _st- in the tag)
            seeds.append({"seed": seed, "status": statuses[seed], "step": step,
                          "target": max(target, step), "tag": tag})
        cols.discard("step")
        # Q_sign moved to the network-structure panel (it's on the GEXF/5000-step
        # cadence, not the per-step grid) — no longer offered in the general picker.
        cols.discard("Q_sign")

        # group <base>_0.._4 columns (cRateMean_0..4, hostility_0..4, ...) into one
        # picker entry each, rendered as a single class-colored chart instead of 5
        # separate ones (see FAMILY_RE). Only expose complete 0..4 sets.
        families = {}
        for c in list(cols):
            m = FAMILY_RE.match(c)
            if m:
                families.setdefault(m.group(1), [None] * 5)[int(m.group(2))] = c
        for base, arr in list(families.items()):
            if all(arr):
                for c in arr:
                    cols.discard(c)
            else:
                del families[base]

        for name in DERIVED_IN_PICKER:
            deps, _fn = DERIVED[name]
            if all(dep in cols for dep in deps):
                cols.add(name)

        return {"seeds": seeds, "columns": sorted(cols), "families": families}


def derived_column(st, name, idx):
    """Compute a DERIVED metric at the given row indices from st.main's raw
    (unrounded, undecimated) columns, so e.g. a subtraction isn't done on
    already-rounded inputs. Returns None if a dependency column is missing."""
    deps, fn = DERIVED[name]
    dep_cols = [st.main.column(d) for d in deps]
    if any(dc is None for dc in dep_cols):
        return None
    out = []
    for i in idx:
        args = [dep_cols[k][i] for k in range(len(deps))]
        if any(a is None or math.isnan(a) for a in args):
            out.append(None)
            continue
        try:
            v = fn(*args)
        except ZeroDivisionError:
            v = None
        out.append(rnd(v) if v is not None else None)
    return out


def api_series(qs):
    want = [c for c in qs.get("cols", [""])[0].split(",") if c]
    max_pts = int(qs.get("max", ["1200"])[0])
    with LOCK:
        poll_all()
        out = {}
        for seed, st in sorted(STORES.items()):
            steps = st.main.column("step")
            if not steps:
                continue
            idx = list(range(len(steps)))
            idx = decimate(idx, max_pts)
            entry = {"step": [int(steps[i]) for i in idx], "cols": {}}
            for c in want:
                if c in DERIVED:
                    vals = derived_column(st, c, idx)
                    if vals is not None:
                        entry["cols"][c] = vals
                    continue
                col = st.main.column(c)
                if col is not None:
                    entry["cols"][c] = [rnd(col[i]) for i in idx]
            if "Q_sign" in want:
                qstep, qval = st.mod.column("step"), st.mod.column("Q_sign")
                if qstep:
                    entry["aux"] = {"Q_sign": {"step": [int(v) for v in qstep],
                                                "values": [rnd(v) for v in qval]}}
            out[str(seed)] = entry
        return {"seeds": out}


def api_opinion(qs):
    seed = int(qs.get("seed", ["-1"])[0])
    max_pts = int(qs.get("max", ["800"])[0])
    with LOCK:
        poll_all()
        st = STORES.get(seed)
        if st is None:
            return {"step": [], "bins": []}
        steps = st.op.column("step")
        if not steps:
            return {"step": [], "bins": []}
        idx = decimate(list(range(len(steps))), max_pts)
        # Bin count is read from the CSV header, not hardcoded: older runs wrote 5
        # bins (bin_0..bin_4), newer runs write 10 (Const.NUM_OF_BINS_OF_OPINION_FOR_WRITER).
        # The dashboard adapts and, for 10-bin data, can re-aggregate pairs down to 5.
        hdr = st.op.header or []
        nb = sum(1 for c in hdr if c.startswith("bin_"))
        bins = []
        for b in range(nb):
            col = st.op.column(f"bin_{b}")
            bins.append([rnd(col[i]) for i in idx] if col else [])
        return {"step": [int(steps[i]) for i in idx], "bins": bins}


def _cascade_virality(edges, root):
    """Structural virality (Goel et al. 2015) of one reconstructed cascade tree
    = average shortest-path distance between all node pairs = 2*W/(n(n-1)),
    W the Wiener index (via the tree edge-decomposition sum s*(n-s), exact in
    O(n)). Distinguishes a deep viral chain (high virality) from a shallow
    broadcast where everyone reposts the root directly (virality -> 1). Returns
    (virality, n) for the connected component reachable from `root`, or None if
    that component has < 2 nodes. Robust to the event log's decimation (missing
    parents just split the cascade into a forest — we score the root's tree)."""
    adj = {}
    for a, b in edges:
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    if root not in adj:
        return None
    # root the component at `root`, BFS order, parent pointers -> subtree sizes
    order, parent, seen = [], {root: None}, {root}
    stack = [root]
    while stack:
        u = stack.pop()
        order.append(u)
        for v in adj[u]:
            if v not in seen:
                seen.add(v); parent[v] = u; stack.append(v)
    n = len(order)
    if n < 2:
        return None
    size = {u: 1 for u in order}
    for u in reversed(order):          # children processed before parents
        p = parent[u]
        if p is not None:
            size[p] += size[u]
    wiener = sum(size[u] * (n - size[u]) for u in order if parent[u] is not None)
    return (2.0 * wiener / (n * (n - 1)), n)


def api_repost(qs):
    """Repost behavior over time from posts/repost_cascades.csv (one row per
    repost event: step, rootPostId, parentPostId, postId, depth, ...).
    Aggregated into fixed-size step buckets (mean depth + mean structural
    virality) plus an all-time depth histogram, rather than returned as raw
    events — the file can have far more rows than steps, and per-bucket
    summaries are what the relay/cascade questions actually want (see
    docs/research-direction.md's relay/reattribution discussion).

    NB structural virality is reconstructed from the *tailed* (decimated) event
    log, so on long runs it is an approximation — a monitoring read, not the
    number for the paper (recompute from the full CSV for that; same caveat as
    all dashboard series)."""
    seed = int(qs.get("seed", ["-1"])[0])
    bucket = max(1, int(qs.get("bucket", ["1000"])[0]))
    with LOCK:
        poll_all()
        st = STORES.get(seed)
        empty = {"step": [], "meanDepth": [], "structVirality": [], "depthHist": {}, "n": 0}
        if st is None:
            return empty
        steps = st.repost.column("step")
        depths = st.repost.column("depth")
        if not steps:
            return empty
        roots = st.repost.column("rootPostId")
        parents = st.repost.column("parentPostId")
        posts = st.repost.column("postId")
        buckets = {}
        hist = {}
        for s, dep in zip(steps, depths):
            b = int(s // bucket) * bucket
            sm, ct = buckets.get(b, (0.0, 0))
            buckets[b] = (sm + dep, ct + 1)
            di = int(dep)
            hist[di] = hist.get(di, 0) + 1
        bkeys = sorted(buckets)
        # Group events into cascades by rootPostId; reconstruct each tree from
        # (parent, post) edges, score its structural virality, bucket by root time.
        vir_buckets = {}
        if roots and parents and posts:
            casc = {}  # rootId -> {"edges": [...], "step": min step}
            for s, r, pa, po in zip(steps, roots, parents, posts):
                if any(math.isnan(v) for v in (r, pa, po)):
                    continue
                r, pa, po = int(r), int(pa), int(po)
                c = casc.get(r)
                if c is None:
                    c = casc[r] = {"edges": [], "step": s}
                c["edges"].append((pa, po))
                if s < c["step"]:
                    c["step"] = s
            for r, c in casc.items():
                res = _cascade_virality(c["edges"], r)
                if res is None:
                    continue
                b = int(c["step"] // bucket) * bucket
                sm, ct = vir_buckets.get(b, (0.0, 0))
                vir_buckets[b] = (sm + res[0], ct + 1)
        return {
            "step": bkeys,
            "meanDepth": [round(buckets[b][0] / buckets[b][1], 4) for b in bkeys],
            "structVirality": [round(vir_buckets[b][0] / vir_buckets[b][1], 4)
                               if b in vir_buckets else None for b in bkeys],
            "depthHist": {str(k): v for k, v in sorted(hist.items())},
            "n": len(steps),  # tailed (possibly decimated) event count, not the true total
        }


# GEXF snapshots carry no layout coordinates; layout is a client-side live
# force simulation (after github.com/soramame0518/Social-Media-Echo-Chamber),
# so the server only parses the graph. The parsed networkx graph is cached by
# file size (snapshot files are write-once, so size is a stable key) — both the
# lightweight force-sim payload (load_network) and the structural-metrics
# computation (compute_structural) below read from this one cache, so a cold
# request pays one XML parse, not two.
GRAPH_CACHE = {}
GRAPH_LOCK = threading.Lock()


def parse_gexf_cached(path: Path):
    st = os.stat(path)
    key = str(path)
    with GRAPH_LOCK:
        hit = GRAPH_CACHE.get(key)
        if hit and hit[0] == st.st_size:
            return hit[1]
    import networkx as nx  # deferred: only --serve + network panel needs it
    G = nx.read_gexf(path)
    with GRAPH_LOCK:
        GRAPH_CACHE[key] = (st.st_size, G)
        while len(GRAPH_CACHE) > 6:  # full graphs, not the stripped payload — smaller cap
            GRAPH_CACHE.pop(next(iter(GRAPH_CACHE)))
    return G


def load_network(path: Path):
    """Lightweight per-node payload for the client-side force layout + the
    agent-attribute-distribution panel (bc/pp are GEXF-only — not in any CSV)
    + the echo-chamber scatter (nbrOp)."""
    G = parse_gexf_cached(path)
    ids = list(G.nodes)
    idx = {nid: i for i, nid in enumerate(ids)}
    op = {nid: float(G.nodes[nid].get("opinion", 0.0)) for nid in ids}
    nodes = []
    for nid in ids:
        d = G.nodes[nid]
        # Echo-chamber diet (Cinelli et al. 2021): mean opinion of the accounts
        # this node *follows* (out-neighbours on the directed follow graph — an
        # edge u->v is written for W[u][v]>0, i.e. u follows v), which is what
        # fills its feed. None when it follows no one (isolated source). The
        # scatter of op vs nbrOp reveals echo chambers as a positive diagonal
        # (you mostly hear your own side) vs. a well-mixed blob.
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
    edges = [[idx[u], idx[v]] for u, v in G.edges()]
    return {"n": len(nodes), "m": len(edges), "nodes": nodes, "edges": edges}


def _read_col(path: Path, col: str, caster):
    try:
        with open(path, newline="") as f:
            return [caster(row[col]) for row in csv.DictReader(f)]
    except (FileNotFoundError, KeyError, ValueError):
        return None


def fit_powerlaw(values):
    """MLE power-law fit (mirrors scripts/heavy_tail_check_n1000.py's convention:
    discrete=True, since degree is integer-valued) + a plausibility read via
    Clauset-style comparison against an exponential alternative — R>0 means the
    power law is the better-fitting of the two (not proof of heavy-tailedness on
    its own, just the standard first check).

    Always returns a dict. On success it carries the fit; otherwise it carries an
    ``unavailable`` reason so the front-end can distinguish the two failure modes
    that used to collapse into one misleading "n<20" label:
      - ``"too-few"``: fewer than 20 nonzero-degree nodes — a deliberate guard,
        the fit is not attempted (MLE is meaningless on so few points).
      - ``"error"``: the fit actually threw (most often ``powerlaw`` not
        installed) — n may be ample; ``detail`` carries the exception text."""
    arr = [v for v in values if v and v > 0] if values else []
    if len(arr) < 20:
        return {"unavailable": "too-few", "n": len(arr)}
    try:
        import powerlaw  # deferred: only the structural panel needs it
        fit = powerlaw.Fit(arr, discrete=True, verbose=False)
        R, p = fit.distribution_compare("power_law", "exponential")
        # Lognormal is the standard rival heavy tail (Clauset-Shalizi-Newman): a
        # degree distribution can beat the exponential yet still be better
        # explained by a lognormal, so "power-law-like vs. exponential" alone
        # over-claims. R_ln > 0 favors the power law; p_ln large = the two are
        # statistically indistinguishable on this sample (the common, honest
        # outcome), which the front-end surfaces rather than hiding.
        R_ln, p_ln = fit.distribution_compare("power_law", "lognormal")
        return {"alpha": round(float(fit.power_law.alpha), 3), "xmin": float(fit.power_law.xmin),
                "R": round(float(R), 3), "p": round(float(p), 4), "plausible": bool(R > 0),
                "R_lognormal": round(float(R_ln), 3), "p_lognormal": round(float(p_ln), 4)}
    except Exception as e:
        return {"unavailable": "error", "detail": f"{type(e).__name__}: {e}"[:200], "n": len(arr)}


def hartigan_dip(values):
    """Hartigan & Hartigan (1985) dip statistic: the sup-norm distance between
    the empirical CDF and the closest *unimodal* CDF. ~0 = compatible with
    unimodality; larger = more multimodal (theoretical max 0.25). Unlike
    Sarle's bimodality coefficient (results.csv's bimodalityCoeff, computed
    from skew/kurtosis), the dip does not false-positive on skewed unimodal
    distributions — the two are complementary reads.

    Faithful pure-Python port of Hartigan's published AS 217 algorithm
    (greatest convex minorant / least concave majorant), following Maechler's
    reference C in the R ``diptest`` package — the standard formulation, working
    on the full sorted sample in index space so heavy ties/atoms (opinions
    saturated at +/-1, or a spiral-of-silence spike) are handled exactly. No GPL
    code is vendored; numerically cross-validated to ~1e-17 against the PyPI
    ``diptest`` C extension over 3000 random samples (Gaussian/bimodal/uniform/
    heavy-tie/saturated/dominant-spike) — see
    docs/report/2026-07-11-dashboard-enhancement-review.md.

    Returns None for < 4 samples (too few to say anything); a single distinct
    value returns 0.0 (a point mass is degenerately unimodal). ``min_is_0`` is
    fixed True (dip floor 0, matching diptest's default allow_zero=True)."""
    n = len(values)
    if n < 4:
        return None
    x = [0.0] + sorted(values)          # 1-indexed working copy: x[1..n]
    if x[n] == x[1]:
        return 0.0                      # all identical -> unimodal point mass
    mn = [0] * (n + 1)                  # GCM: mn[j] = preceding minorant touchpoint
    mj = [0] * (n + 1)                  # LCM: mj[k] = following majorant touchpoint
    gcm = [0] * (n + 2)                 # reusable touchpoint-chain buffers
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

    # Work with (2n * dip) throughout, dividing by 2n only at the end (Maechler's
    # speedup); dip accumulates the max GCM/LCM deviation over the modal-interval
    # refinement, terminating when the GCM-LCM separation can't beat it.
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
        dip_l = 0.0                     # deviation within the convex-minorant segments
        for j in range(ig, l_gcm):
            max_t = 1.0
            jb = gcm[j + 1]; je = gcm[j]
            if je - jb > 1 and x[je] != x[jb]:
                C = (je - jb) / (x[je] - x[jb])
                for jj in range(jb, je + 1):
                    t = (jj - jb + 1) - (x[jj] - x[jb]) * C
                    if max_t < t: max_t = t
            if dip_l < max_t: dip_l = max_t
        dip_u = 0.0                     # deviation within the concave-majorant segments
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
            break                       # interval unchanged -> converged (Maechler's guard)
        low = gcm[ig]; high = lcm[ih]
    return dip / (2 * n)


# n -> sorted bootstrap dips under the uniform null. Keyed by sample size only,
# so the (~200 x dip) cost is paid once per population size, not per snapshot.
DIP_BOOT = {}
DIP_BOOT_LOCK = threading.Lock()


def dip_diagnostics(values, boots=200):
    """Dip + bootstrap p-value against the uniform null (H&H's calibration:
    the uniform is the least-favorable unimodal distribution, so this p is
    conservative). p < 0.05 => reject unimodality. Fixed RNG seed keeps the
    null table identical across polls/snapshots."""
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
    """Random Walk Controversy (Garimella et al. 2018): how much more likely a
    random walker starting on one opinion side is to reach that side's own
    high-degree hubs than the other side's. Sides = opinion sign (>= 0 / < 0,
    the same camp convention as Q_sign / crossCuttingFraction); absorbing hubs
    = top-k degree nodes within each side (k = 1% of nodes, min 3, capped at
    side size), on the undirected giant component — same graph convention as
    betweenness/lambda2 above. Computed analytically as absorbing-Markov-chain
    absorption probabilities (the exact version of the paper's Monte Carlo
    estimator): RWC = pXX*pYY - pXY*pYX, in [-1, 1]. ~1 = segregated echo
    chambers, ~0 = well-mixed, < 0 = walks cross sides more than they stay.
    Complements modularity/E-I: those count edges, RWC measures *reachability*
    (multi-hop flow), so it also sees separation that per-edge counts miss."""
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
                continue  # can't happen inside a giant component of n >= 2
            w = 1.0 / len(nbrs)
            for v in nbrs:
                if v in abs_x:
                    b_x[tidx[u]] += w
                elif v not in abs_y:
                    rows.append(tidx[u]); cols.append(tidx[v]); data.append(w)
        Q = coo_matrix((data, (rows, cols)), shape=(len(trans), len(trans))).tocsr()
        p_x = spsolve((identity(len(trans), format="csr") - Q).tocsr(), b_x)
        # giant component + nonempty absorbing set => absorption is a.s., so
        # P(absorbed in Y hubs) = 1 - P(absorbed in X hubs)
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
    """Snapshot-level structural read: giant-component betweenness + algebraic
    connectivity (lambda2) on whichever graph (follow/repost) was requested —
    undirected, giant-component-only, matching journal.tex's "hub betweenness /
    lambda2 (giant component)" convention (directed full-graph betweenness is
    uninformative here since hubs are near-pure in-degree sinks). Degree
    distribution + heavy-tail fit and clustering coefficient come from the
    per-snapshot CSVs Java already writes (degrees/, clusterings/) rather than
    being recomputed from the GEXF — those files only ever describe the FOLLOW
    graph (there's no repost-graph equivalent), so they're the same regardless
    of which graph's betweenness/lambda2 was requested.
    Cached by gexf_path's file size — betweenness_centrality alone is ~4s for
    n=1000/m~10000, so this must not be recomputed on every poll."""
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
        rwc = compute_rwc(Gg)

    # Opinion multimodality of ALL nodes (not just the giant component — the dip
    # is a distributional property of the opinion sample, independent of who is
    # connected to whom). Node opinions are GEXF-only; this is the raw-value
    # multimodality read to sit alongside the CSV's skew/kurtosis bimodalityCoeff.
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
    # Snapshot files are written non-atomically (Gephi's exportController writes
    # straight to the target path), so while a run is live the newest snapshot can
    # be mid-write — parsing it then raises an XML parse error. Fall back to
    # progressively older snapshots (already flushed; a step's file is never
    # touched again once the next one starts) instead of surfacing a 500.
    candidates = [s for s in reversed(steps) if s <= step] or [steps[-1]]
    last_err = None
    for i, s in enumerate(candidates):
        try:
            payload = load_network(snaps[s])
            result = {"steps": steps, "step": s, "stale": i > 0, **payload}
            if want_structural:
                try:
                    result["structural"] = compute_structural(
                        snaps[s], d / "degrees" / f"degree_result_{s}.csv",
                        d / "clusterings" / f"clustering_result_{s}.csv")
                except Exception as e:
                    result["structuralError"] = f"{type(e).__name__}: {e}"
            return result
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            continue
    return {"steps": steps, "step": None, "n": 0, "m": 0, "nodes": [], "edges": [],
            "error": f"snapshot(s) unreadable (likely still being written): {last_err}"}


def api_log(qs):
    seed = int(qs.get("seed", ["-1"])[0])
    lines = int(qs.get("lines", ["200"])[0])
    f = SERVE_LOGDIR / f"run_{seed}.log"
    if not f.exists():
        return f"(no log file for seed {seed})"
    return "\n".join(f.read_text(errors="replace").splitlines()[-lines:])


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # quiet; the terminal is for run.sh output

    def _send(self, code, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj):
        self._send(200, json.dumps(obj).encode(), "application/json")

    def do_GET(self):
        u = urlparse(self.path)
        qs = parse_qs(u.query)
        try:
            if u.path == "/" or u.path == "/index.html":
                self._send(200, HTML_PATH.read_bytes(), "text/html; charset=utf-8")
            elif u.path == "/api/summary":
                self._json(api_summary())
            elif u.path == "/api/series":
                self._json(api_series(qs))
            elif u.path == "/api/opinion":
                self._json(api_opinion(qs))
            elif u.path == "/api/repost":
                self._json(api_repost(qs))
            elif u.path == "/api/network":
                self._json(api_network(qs))
            elif u.path == "/api/log":
                self._send(200, api_log(qs).encode(), "text/plain; charset=utf-8")
            elif u.path == "/favicon.ico":
                self._send(204, b"", "image/x-icon")
            else:
                self._send(404, b"not found", "text/plain")
        except BrokenPipeError:
            pass
        except Exception as e:  # keep the server alive; surface the error to the client
            self._send(500, f"{type(e).__name__}: {e}".encode(), "text/plain")


def run_server(logdir: Path, only, host: str, port: int):
    global SERVE_LOGDIR, SERVE_ONLY
    SERVE_LOGDIR, SERVE_ONLY = logdir, only
    httpd = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}"
    print(f"Serving interactive dashboard at {url}")
    print("Over SSH / VSCode Remote-SSH: check the PORTS tab for an auto-forward "
          "toast, or Cmd/Ctrl+Shift+P -> 'Simple Browser: Show' -> paste the URL above.")
    print("Ctrl-C to stop (does not affect the simulations).")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--interval", type=float, default=5.0,
                    help="GUI-mode refresh period, seconds (web UI has its own control)")
    ap.add_argument("--seeds", type=int, nargs="*", default=None,
                    help="restrict to these seeds (default: all seeds found in logs/)")
    ap.add_argument("--logdir", default="logs")
    ap.add_argument("--serve", action="store_true",
                    help="serve the interactive web dashboard instead of a GUI window")
    ap.add_argument("--host", default="127.0.0.1", help="--serve bind address")
    ap.add_argument("--port", type=int, default=8765, help="--serve port")
    args = ap.parse_args()

    logdir = ROOT / args.logdir
    only = set(args.seeds) if args.seeds else None

    if args.serve:
        run_server(logdir, only, args.host, args.port)
    else:
        run_gui(logdir, only, args.interval)


if __name__ == "__main__":
    main()
