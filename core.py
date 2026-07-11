import os
import csv
import re
import math
import threading
from pathlib import Path

# Path discovery with CWD fallback for standalone executions
ROOT = Path(__file__).resolve().parent.parent
if not (ROOT / "results").exists() and Path("results").exists():
    ROOT = Path(".").resolve()

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

DERIVED = {
    "apparentPolarization": (("exposureOpinionVar", "opinionVar"), lambda a, b: a - b),
    "repostShare": (("repostCount", "originalPostCount"),
                     lambda r, o: (r / (r + o)) if (r + o) > 0 else None),
    "EI_index": (("crossCuttingFraction",), lambda c: 2 * c - 1),
}
DERIVED_IN_PICKER = ("apparentPolarization", "repostShare")
FAMILY_RE = re.compile(r"^(.+)_([0-4])$")

STORES = {}          # seed -> SeedStore
LOCK = threading.Lock()
SERVE_LOGDIR = None  # set at startup
SERVE_ONLY = None


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
    """Newest results/run_<seed>_<tag>/ folder for this seed (mtime-based)."""
    candidates = list(ROOT.glob(f"results/run_{seed}_*"))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


class CsvTail:
    """Incrementally tail-parse an all-numeric CSV with adaptive decimation."""
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
            return
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
        self.repost = CsvTail(d / "posts" / "repost_cascades.csv", max_rows=8000)

    def poll(self):
        self.main.poll()
        self.mod.poll()
        self.op.poll()
        self.repost.poll()


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
            seeds.append({"seed": seed, "status": statuses[seed], "step": step,
                          "target": max(target, step), "tag": tag})
        cols.discard("step")
        cols.discard("Q_sign")

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
    """Compute a DERIVED metric at the given row indices from st.main's raw columns."""
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
        hdr = st.op.header or []
        nb = sum(1 for c in hdr if c.startswith("bin_"))
        bins = []
        for b in range(nb):
            col = st.op.column(f"bin_{b}")
            bins.append([rnd(col[i]) for i in idx] if col else [])
        return {"step": [int(steps[i]) for i in idx], "bins": bins}


def _cascade_virality(edges, root):
    """Structural virality (Goel et al. 2015) of one reconstructed cascade tree."""
    adj = {}
    for a, b in edges:
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    if root not in adj:
        return None
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
    for u in reversed(order):
        p = parent[u]
        if p is not None:
            size[p] += size[u]
    wiener = sum(size[u] * (n - size[u]) for u in order if parent[u] is not None)
    return (2.0 * wiener / (n * (n - 1)), n)


def api_repost(qs):
    """Repost behavior over time from posts/repost_cascades.csv."""
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
        vir_buckets = {}
        if roots and parents and posts:
            casc = {}
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
            "n": len(steps),
        }


def api_log(qs):
    seed = int(qs.get("seed", ["-1"])[0])
    lines = int(qs.get("lines", ["200"])[0])
    f = SERVE_LOGDIR / f"run_{seed}.log"
    if not f.exists():
        return f"(no log file for seed {seed})"
    return "\n".join(f.read_text(errors="replace").splitlines()[-lines:])
