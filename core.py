import os
import json
import lzma
import math
import re
import threading
import time
from bisect import bisect_left
from pathlib import Path

# Path discovery with CWD fallback for standalone executions.
# The package lives at scripts/dashboard/ inside the echo-chamber repo, so the
# repo root (which holds data/) is three levels up from this file.
ROOT = Path(__file__).resolve().parent.parent.parent
if not (ROOT / "data").exists() and Path("data").exists():
    ROOT = Path(".").resolve()

# dataviz skill categorical palette (fixed order, not cycled by rank)
COLORS = [
    "#2a78d6", "#1baf7a", "#eda100", "#008300",
    "#4a3aa7", "#e34948", "#e87ba4", "#eb6834",
]

# Metrics served by /api/series. source: which loader provides the values.
# (echo-chamber catalogue; "label" is what the metric picker displays.)
METRICS = {
    "modularity": {"label": "modularity (Q)", "source": "modularity"},
    "communities": {"label": "communities", "source": "modularity"},
    "active_users": {"label": "active users", "source": "active_users"},
    "triangles": {"label": "triangles", "source": "triangles"},
    "opinion_mean": {"label": "opinion mean", "source": "opinions"},
    "opinion_var": {"label": "opinion variance", "source": "opinions"},
    "opinion_abs_mean": {"label": "|opinion| mean", "source": "opinions"},
    "diversity_bias_mean": {"label": "diversity bias mean", "source": "diversity_bias"},
    "screen_diversity_mean": {"label": "screen diversity mean", "source": "screen_diversity"},
    "effective_mu_SUPPRESSION": {"label": "effective mu (SUP)", "source": "effective_mu"},
    "effective_mu_AMPLIFICATION": {"label": "effective mu (AMP)", "source": "effective_mu"},
    "effective_mu_INDIFFERENCE": {"label": "effective mu (IND)", "source": "effective_mu"},
}
DEFAULT_METRICS = ["modularity", "opinion_var", "opinion_mean",
                   "diversity_bias_mean", "screen_diversity_mean", "active_users"]

# xz-backed sources are only read once a run is done (mid-run xz streams are
# not decodable); plain-CSV sources are tailed live.
XZ_SOURCES = {"opinions", "diversity_bias", "screen_diversity", "effective_mu"}

DEFAULT_ROOTS = ["data", "data_hdd1"]
RESCAN_EVERY = 15.0          # seconds between run-discovery scans
STALL_AFTER = 60.0           # no file update for this long => "stalled"
OPINION_BINS = 10            # histogram bins over [-1, 1]
DEFAULT_TARGET_STEPS = 40000

DERIVED = {
    "opinion_std": (("opinion_var",), lambda v: math.sqrt(v) if v >= 0 else None),
}
DERIVED_IN_PICKER = ("opinion_std",)
FAMILY_RE = re.compile(r"^(.+)_([0-4])$")

STORES = {}          # run id (path relative to a root's parent) -> RunStore
LOCK = threading.Lock()
SERVE_ROOTS = []     # set at startup
LAST_SCAN = 0.0


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


def read_xz_csv(path):
    """Read a whole .xz CSV; returns (header, rows) with unquoted cells."""
    with lzma.open(path, "rt", encoding="utf-8", errors="replace") as f:
        header = None
        rows = []
        for line in f:
            line = line.strip()
            if not line:
                continue
            cells = [c.strip('"') for c in line.split(",")]
            if header is None:
                header = cells
            else:
                rows.append(cells)
        return header, rows


def opinion_histogram(ops):
    counts = [0] * OPINION_BINS
    for op in ops:
        if op is None:
            continue
        b = int((op + 1.0) / 2.0 * OPINION_BINS)
        counts[min(max(b, 0), OPINION_BINS - 1)] += 1
    return counts


class RunStore:
    """Per-run state: run_meta.json, live CSV tails, and xz parse caches."""

    def __init__(self, run_dir, rid):
        self.dir = Path(run_dir)
        self.id = rid
        self.meta = None
        self.main = CsvTail(self.dir / "modularity.csv")
        self.active = CsvTail(self.dir / "data" / "active_users.csv")
        self.tri = CsvTail(self.dir / "data" / "triangle_closures.csv")
        self._xz_cache = {}     # source -> (stat_key, parsed)

    # -- metadata / status ---------------------------------------------------

    def load_meta(self):
        if self.meta is not None:
            return self.meta
        try:
            with open(self.dir / "run_meta.json", encoding="utf-8") as f:
                self.meta = json.load(f)
        except (OSError, ValueError):
            self.meta = {}
        return self.meta

    def poll(self):
        self.load_meta()
        self.main.poll()
        self.active.poll()
        self.tri.poll()

    def is_done(self):
        # written once by the Java side when a run finishes (early stop included)
        p = self.dir / "data" / "opinion_convergence_summary.csv"
        try:
            return p.stat().st_size > 0
        except OSError:
            return False

    def newest_mtime(self):
        newest = 0.0
        probes = [self.dir / "modularity.csv",
                  self.dir / "data" / "active_users.csv",
                  self.dir / "data" / "triangle_closures.csv"]
        try:
            probes.extend((self.dir / "network_data").iterdir())
        except OSError:
            pass
        for p in probes:
            try:
                newest = max(newest, p.stat().st_mtime)
            except OSError:
                continue
        return newest

    def current_step(self):
        step = 0
        for tail, col in ((self.main, "step"), (self.active, "step"), (self.tri, "time")):
            s = tail.column(col)
            if s:
                step = max(step, int(s[-1]))
        steps = self.network_steps()
        if steps:
            step = max(step, steps[-1])
        return step

    def status(self):
        if self.is_done():
            return "done"
        age = time.time() - self.newest_mtime()
        return "running" if age < STALL_AFTER else "stalled"

    def summary(self):
        meta = self.load_meta()
        step = self.current_step()
        target = meta.get("tMax") or DEFAULT_TARGET_STEPS
        return {
            "run": self.id,
            "group": os.path.dirname(self.id),
            "status": self.status(),
            "step": step,
            "target": max(target, step),
            "seed": meta.get("seed"),
            "n": meta.get("nAgents"),
            "mix": meta.get("weightingHypothesisMixConfigured"),
            "networkExportEvery": meta.get("networkExportEvery"),
        }

    # -- xz-backed sources (done runs only) ----------------------------------

    def _xz_load(self, source):
        paths = {
            "opinions": self.dir / "data" / "opinions.csv.xz",
            "diversity_bias": self.dir / "data" / "diversity_bias.csv.xz",
            "screen_diversity": self.dir / "data" / "screen_diversity.csv.xz",
            "effective_mu": self.dir / "data" / "effective_mu.csv.xz",
        }
        path = paths[source]
        try:
            st = path.stat()
        except OSError:
            return None
        key = (st.st_size, st.st_mtime)
        cached = self._xz_cache.get(source)
        if cached and cached[0] == key:
            return cached[1]
        try:
            header, rows = read_xz_csv(path)
        except (OSError, lzma.LZMAError, EOFError):
            return None
        parsed = self._xz_parse(source, header, rows)
        self._xz_cache[source] = (key, parsed)
        return parsed

    def _snapshot_every(self, rows):
        """stateSnapshotEvery, inferred from the data when the (older) meta
        lacks it: wide-matrix time columns are snapshot indices, so the real
        step is index * every."""
        meta = self.load_meta()
        every = meta.get("stateSnapshotEvery")
        if every:
            return every
        max_idx = 0
        for row in rows:
            try:
                max_idx = max(max_idx, int(float(row[0])))
            except (ValueError, IndexError):
                continue
        last = self.current_step()
        if max_idx > 0 and last > max_idx:
            return max(1, round(last / max_idx))
        return 1

    def _xz_parse(self, source, header, rows):
        every = self._snapshot_every(rows)
        if source == "opinions":
            steps, means, variances, abs_means, hists = [], [], [], [], []
            for row in rows:
                try:
                    idx = int(float(row[0]))
                    ops = [float(c) for c in row[1:]]
                except ValueError:
                    continue
                if not ops:
                    continue
                m = sum(ops) / len(ops)
                steps.append(idx * every)
                means.append(m)
                variances.append(sum((o - m) ** 2 for o in ops) / len(ops))
                abs_means.append(sum(abs(o) for o in ops) / len(ops))
                hists.append(opinion_histogram(ops))
            return {"step": steps, "opinion_mean": means, "opinion_var": variances,
                    "opinion_abs_mean": abs_means, "hist": hists}
        if source == "screen_diversity":
            steps, means = [], []
            for row in rows:
                try:
                    idx = int(float(row[0]))
                    vals = [float(c) for c in row[1:] if c not in ("", "NaN")]
                except ValueError:
                    continue
                if not vals:
                    continue
                steps.append(idx * every)
                means.append(sum(vals) / len(vals))
            return {"step": steps, "screen_diversity_mean": means}
        if source == "diversity_bias":
            by_step = {}
            for row in rows:
                try:
                    step = int(float(row[0]))
                    val = float(row[2])
                except (ValueError, IndexError):
                    continue
                acc = by_step.setdefault(step, [0.0, 0])
                acc[0] += val
                acc[1] += 1
            steps = sorted(by_step)
            means = [by_step[s][0] / by_step[s][1] for s in steps]
            return {"step": steps, "diversity_bias_mean": means}
        if source == "effective_mu":
            series = {}
            for row in rows:
                try:
                    step = int(float(row[0]))
                    hyp = row[1]
                    val = float(row[2]) if row[2] not in ("", "NaN") else None
                except (ValueError, IndexError):
                    continue
                key = f"effective_mu_{hyp}"
                s = series.setdefault(key, {"step": [], key: []})
                if val is not None:
                    s["step"].append(step)
                    s[key].append(val)
            return series
        return None

    # -- network snapshots (GEXF parsing itself lives in analysis.py) ---------

    def network_steps(self):
        steps = []
        try:
            for p in (self.dir / "network_data").iterdir():
                m = re.match(r"G_(\d+)\.gexf\.bz2$", p.name)
                if m:
                    steps.append(int(m.group(1)))
        except OSError:
            pass
        return sorted(steps)

    def snapshot_path(self, step):
        return self.dir / "network_data" / f"G_{step:07d}.gexf.bz2"

    def gexf_opinion_series(self):
        """Snapshot-cadence opinion stats from GEXF (for running runs)."""
        from . import analysis  # deferred: analysis imports core at module level
        out = {"step": [], "hist": [], "opinion_mean": [], "opinion_var": [],
               "opinion_abs_mean": []}
        for s in self.network_steps():
            try:
                parsed = analysis.parse_gexf_cached(self.snapshot_path(s))
            except Exception:
                continue    # snapshot still being written; skip it
            ops = [n["op"] for n in parsed["nodes"] if n["op"] is not None]
            if not ops:
                continue
            m = sum(ops) / len(ops)
            out["step"].append(s)
            out["opinion_mean"].append(m)
            out["opinion_var"].append(sum((o - m) ** 2 for o in ops) / len(ops))
            out["opinion_abs_mean"].append(sum(abs(o) for o in ops) / len(ops))
            out["hist"].append(opinion_histogram(ops))
        return out

    # -- series ---------------------------------------------------------------

    def metric_series(self, name):
        """(steps, values) for one catalogue metric; both [] when unavailable."""
        spec = METRICS.get(name)
        if spec is None:
            return [], []
        source = spec["source"]
        steps, values = [], []
        if source == "modularity":
            col = "modularity_mean" if name == "modularity" else "communities"
            steps, values = self.main.column("step"), self.main.column(col)
        elif source == "active_users":
            steps, values = self.active.column("step"), self.active.column("active_count")
        elif source == "triangles":
            steps, values = self.tri.column("time"), self.tri.column("triangle_count")
        elif source in XZ_SOURCES:
            if self.is_done():
                parsed = self._xz_load(source)
                if parsed:
                    if source == "effective_mu":
                        sub = parsed.get(name)
                        if sub:
                            steps, values = sub["step"], sub[name]
                    else:
                        steps, values = parsed["step"], parsed.get(name, [])
            elif source == "opinions":
                live = self.gexf_opinion_series()
                steps, values = live["step"], live.get(name, [])
        if not steps or not values:
            return [], []
        return [int(s) for s in steps], values


def scan_runs(force=False):
    """Discover run directories (marked by run_meta.json) under the roots."""
    global LAST_SCAN
    now = time.time()
    if not force and now - LAST_SCAN < RESCAN_EVERY:
        return
    LAST_SCAN = now
    for root in SERVE_ROOTS:
        root = Path(root)
        if not root.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            if "run_meta.json" in filenames:
                rid = os.path.relpath(dirpath, root.parent)
                if rid not in STORES:
                    STORES[rid] = RunStore(Path(dirpath), rid)
                dirnames[:] = []  # never descend into a run directory
    for rid in list(STORES):
        if not STORES[rid].dir.is_dir():
            del STORES[rid]


def poll_all():
    """Refresh discovery and tail every store. Call under LOCK."""
    scan_runs()
    for st in STORES.values():
        st.poll()


def get_store(rid):
    store = STORES.get(rid)
    if store is None:
        scan_runs(force=True)
        store = STORES.get(rid)
    return store


def rnd(v):
    if v is None:
        return None
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return None
        return round(v, 6)
    return v


def decimate(arr, max_pts):
    if len(arr) <= max_pts:
        return arr
    k = math.ceil(len(arr) / max_pts)
    return arr[::k]


def api_summary():
    with LOCK:
        poll_all()
        runs = [STORES[rid].summary() for rid in sorted(STORES)]
        cols = set(METRICS)

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

        labels = {k: v["label"] for k, v in METRICS.items()}
        return {"runs": runs, "columns": sorted(cols), "labels": labels,
                "families": families, "defaultMetrics": DEFAULT_METRICS}


def derived_series(st, name):
    """Compute a DERIVED metric; secondary deps are aligned onto the first
    dep's step grid by nearest-step lookup."""
    deps, fn = DERIVED[name]
    dep_series = [st.metric_series(d) for d in deps]
    if any(not s[0] for s in dep_series):
        return [], []
    steps = dep_series[0][0]
    out = []
    for i, stp in enumerate(steps):
        args = [dep_series[0][1][i]]
        for ss, vv in dep_series[1:]:
            j = min(max(bisect_left(ss, stp), 0), len(ss) - 1)
            args.append(vv[j])
        if any(a is None or (isinstance(a, float) and math.isnan(a)) for a in args):
            out.append(None)
            continue
        try:
            v = fn(*args)
        except (ValueError, ZeroDivisionError):
            v = None
        out.append(v)
    return steps, out


def api_series(qs):
    want = [c for c in qs.get("cols", [""])[0].split(",") if c]
    max_pts = int(qs.get("max", ["1200"])[0])
    only = qs.get("runs", [None])[0]
    only = set(r for r in only.split(",") if r) if only is not None else None
    with LOCK:
        poll_all()
        out = {}
        for rid, st in sorted(STORES.items()):
            if only is not None and rid not in only:
                continue
            # every metric has its own step grid in the echo-chamber layout,
            # so each one is served in the {step, values} "aux" form.
            entry = {"step": [], "cols": {}, "aux": {}}
            for c in want:
                if c in DERIVED:
                    steps, values = derived_series(st, c)
                else:
                    steps, values = st.metric_series(c)
                if not steps:
                    continue
                idx = decimate(list(range(len(steps))), max_pts)
                entry["aux"][c] = {"step": [steps[i] for i in idx],
                                   "values": [rnd(values[i]) for i in idx]}
            out[rid] = entry
        return {"runs": out}


def api_opinion(qs):
    rid = qs.get("run", [""])[0]
    max_pts = int(qs.get("max", ["800"])[0])
    with LOCK:
        poll_all()
        st = get_store(rid)
        if st is None:
            return {"step": [], "bins": []}
        parsed = st._xz_load("opinions") if st.is_done() else st.gexf_opinion_series()
        if not parsed or not parsed.get("step"):
            return {"step": [], "bins": []}
        idx = decimate(list(range(len(parsed["step"]))), max_pts)
        hists = [parsed["hist"][i] for i in idx]
        bins = [[h[b] for h in hists] for b in range(OPINION_BINS)]
        return {"step": [int(parsed["step"][i]) for i in idx], "bins": bins,
                "live": not st.is_done()}


def api_repost(qs):
    """No repost data exists in the echo-chamber layout; the route stays (the
    frontend hides the panels) and always answers the empty shape."""
    return {"step": [], "meanDepth": [], "structVirality": [], "depthHist": {}, "n": 0}


def api_meta(qs):
    rid = qs.get("run", [""])[0]
    with LOCK:
        st = get_store(rid)
        return {"run": rid, "meta": st.load_meta() if st else None}


def api_log(qs):
    """No per-run log files exist in the echo-chamber layout; empty response."""
    return ""
