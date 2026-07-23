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
    ("Q_sign_repost", "repost-graph modularity (Q_sign)"),
    ("bimodalityCoeff", "bimodality coeff."),
    ("opinionKurtosis", "opinion kurtosis"),
    ("disagreement", "disagreement"),
]

RESULTS_COLS = ["step", "opinionAssortativity", "crossCuttingFraction",
                "bimodalityCoeff", "opinionKurtosis", "disagreement"]

SEED_RE = re.compile(r"run_(\d+)\.log$")
DEFAULT_TARGET_STEPS = 40000

# Generic "run set" discovery: run.sh writes logs/run_<seed>.log, but every AI-agent-driven
# script (BO calibrations, sweeps, ...) picks its own name, e.g.
# logs/app_pol_baseline_v5_seed<seed>.log or logs/stage1b_bo_seed<seed>.log. Both conventions
# share the shape "<prefix><seed>.log" where <prefix> is whatever text precedes the trailing
# digit run - so grouping logs/*.log by that prefix, with no per-script registration needed,
# is enough to let the dashboard discover and switch between them. results/run_<seed>_<tag>/
# itself is already shared across all scripts (same ExperimentConfig.tag() convention), so only
# log discovery needs to become group-aware.
GROUP_LOG_RE = re.compile(r"^(.+?)(\d+)\.log$")
DEFAULT_GROUP = "run_"

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
SERVE_GROUP = DEFAULT_GROUP  # currently-selected log-prefix "run set", switchable via /api/group


def log_groups(logdir: Path):
    """logs/*.log grouped by filename prefix (text before the trailing seed number).

    Returns {prefix: [(seed, path), ...]}. "run_0.log" -> prefix "run_"; a BO script's
    "app_pol_baseline_v5_seed3.log" -> prefix "app_pol_baseline_v5_seed". No registration
    required - any script that writes logs/<anything><seed>.log is auto-discovered.
    """
    groups = {}
    for f in logdir.glob("*.log"):
        m = GROUP_LOG_RE.match(f.name)
        if not m:
            continue
        groups.setdefault(m.group(1), []).append((int(m.group(2)), f))
    return groups


def active_seeds(logdir: Path, only=None, prefix=None):
    """seed -> status ('running' | 'done' | 'failed'), from logs/<prefix><seed>.log."""
    out = {}
    prefix = DEFAULT_GROUP if prefix is None else prefix
    for seed, f in sorted(log_groups(logdir).get(prefix, [])):
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


def api_groups():
    """Available run sets for the picker: one entry per discovered logs/*.log prefix."""
    groups = log_groups(SERVE_LOGDIR)
    out = []
    for prefix, entries in groups.items():
        statuses = active_seeds(SERVE_LOGDIR, prefix=prefix)
        counts = {"running": 0, "done": 0, "failed": 0}
        for st in statuses.values():
            counts[st] += 1
        out.append({
            "prefix": prefix,
            "seedCount": len(entries),
            "counts": counts,
            "latestMtime": max((f.stat().st_mtime for _, f in entries), default=0),
        })
    out.sort(key=lambda g: -g["latestMtime"])
    return {"groups": out, "active": SERVE_GROUP}


def pick_default_group(logdir: Path):
    """Startup default for SERVE_GROUP: whichever run set actually has activity, not always
    run.sh's "run_". Prefers a group with running seeds (most running wins ties), else the
    most recently touched group; DEFAULT_GROUP only if logs/ has no matches at all - this is
    what a fresh `--serve` should show without the user needing to touch the picker first."""
    groups = log_groups(logdir)
    if not groups:
        return DEFAULT_GROUP
    def key(prefix):
        running = sum(1 for s in active_seeds(logdir, prefix=prefix).values() if s == "running")
        latest = max((f.stat().st_mtime for _, f in groups[prefix]), default=0)
        return (running > 0, running, latest)
    return max(groups, key=key)


def set_group(prefix):
    """Switch the active run set. Rejects unknown prefixes (also closes off using this as
    an arbitrary-path primitive into api_log's f"{SERVE_GROUP}{seed}.log")."""
    global SERVE_GROUP
    if prefix not in log_groups(SERVE_LOGDIR):
        raise ValueError(f"unknown run set: {prefix!r}")
    with LOCK:
        SERVE_GROUP = prefix
        STORES.clear()
    return api_groups()


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
    statuses = active_seeds(SERVE_LOGDIR, SERVE_ONLY, SERVE_GROUP)
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
        cols.discard("Q_sign_repost")

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
            # Q_sign/Q_sign_repost both live in modularity.csv (Writer.writeModularity),
            # tailed separately from st.main since they're written on a sparser (5000-step) cadence.
            for aux_name in ("Q_sign", "Q_sign_repost"):
                if aux_name in want:
                    qstep, qval = st.mod.column("step"), st.mod.column(aux_name)
                    if qstep:
                        entry.setdefault("aux", {})[aux_name] = {
                            "step": [int(v) for v in qstep], "values": [rnd(v) for v in qval]}
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
    f = SERVE_LOGDIR / f"{SERVE_GROUP}{seed}.log"
    if not f.exists():
        return f"(no log file for seed {seed})"
    return "\n".join(f.read_text(errors="replace").splitlines()[-lines:])
