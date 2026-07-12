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

# Dynamic metric discovery: filenames already served by METRICS, and known
# non-metric files, are excluded from the generic CSV/xz scan below.
CLAIMED_FILES = {
    "modularity.csv", "active_users.csv", "triangle_closures.csv",
    "opinions.csv.xz", "diversity_bias.csv.xz", "screen_diversity.csv.xz",
    "effective_mu.csv.xz",
}
EXCLUDED_FILES = {
    "opinion_convergence_summary.csv", "user_hypotheses.csv",
    "edge_events.csv.xz", "messages.csv.xz", "screen_log.csv.xz",
    "confidences_sample.csv.xz",
}
X_AXIS_COLUMNS = ("step", "time", "t")
DISCOVERY_MAX_COLS = 20      # wider rows are treated as per-agent matrices, not metrics

DEFAULT_ROOTS = ["data", "data_hdd1"]
RESCAN_EVERY = 15.0          # seconds between run-discovery scans
STALL_AFTER = 60.0           # no file update for this long => "stalled"
OPINION_BINS = 10            # histogram bins over [-1, 1]
DEFAULT_TARGET_STEPS = 40000
TRAJ_MAX_STEPS = 300          # default per-agent opinion-trajectory decimation
TRAJ_MAX_AGENTS = 2000        # above this, agents are subsampled (equal stride)

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


def probe_xz_header(path):
    """Read only the header line of an xz CSV, closing the stream immediately after."""
    with lzma.open(path, "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if line:
                return [c.strip('"') for c in line.split(",")]
    return None


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
        self._traj_cache = None  # (stat_key, parsed) for the full per-agent opinion matrix
        # Dynamically discovered metrics: filename -> {tail, x_col, value_cols}.
        # value_cols is None until the header has been read and the file has
        # passed the exclusion rules; kind distinguishes plain/xz for a later phase.
        self._discovered = {}
        self._discovered_excluded = set()   # filenames rejected permanently
        self._discovery_scan_at = 0.0
        # Discovered xz metrics (completed runs only): filename -> probed
        # header metadata. Full parse is deferred until a series is requested.
        self._discovered_xz = {}
        self._discovered_xz_excluded = set()
        self._discovery_xz_scan_at = 0.0
        self._xz_discovery_cache = {}   # filename -> (stat_key, (header, columns))

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
        self._poll_discovered()
        self._scan_discovered_xz_files()

    # -- dynamic metric discovery (plain CSV) --------------------------------

    def _scan_discovered_files(self):
        now = time.time()
        if now - self._discovery_scan_at < RESCAN_EVERY:
            return
        self._discovery_scan_at = now
        for d in (self.dir, self.dir / "data"):
            try:
                candidates = list(d.glob("*.csv"))
            except OSError:
                continue
            for p in candidates:
                name = p.name
                if name in CLAIMED_FILES or name in EXCLUDED_FILES:
                    continue
                if name in self._discovered_excluded or name in self._discovered:
                    continue
                self._discovered[name] = {"tail": CsvTail(p), "x_col": None, "value_cols": None}

    def _poll_discovered(self):
        self._scan_discovered_files()
        for name, entry in list(self._discovered.items()):
            tail = entry["tail"]
            tail.poll()
            if tail.header is None and entry["value_cols"] is not None:
                # file disappeared after being established; drop it so a
                # fresh scan can pick it back up if it reappears.
                del self._discovered[name]
                continue
            if entry["value_cols"] is None:
                if tail.header is None:
                    continue
                stripped = [h.strip('"') for h in tail.header]
                x_idx = None
                for cand in X_AXIS_COLUMNS:
                    if cand in stripped:
                        x_idx = stripped.index(cand)
                        break
                if x_idx is None or len(tail.header) > DISCOVERY_MAX_COLS:
                    self._discovered_excluded.add(name)
                    del self._discovered[name]
                    continue
                entry["x_col"] = tail.header[x_idx]
                entry["value_cols"] = [(tail.header[i], stripped[i])
                                        for i in range(len(tail.header)) if i != x_idx]
            xs = tail.column(entry["x_col"])
            if xs and len(xs) > 1 and any(xs[i] <= xs[i - 1] for i in range(1, len(xs))):
                self._discovered_excluded.add(name)
                del self._discovered[name]

    def discovered_metrics(self):
        """id -> descriptor for every discovered value column (plain CSV or xz)."""
        result = {}
        for name, entry in self._discovered.items():
            if entry["value_cols"] is None:
                continue
            stem = name[:-4] if name.endswith(".csv") else name
            for orig, stripped in entry["value_cols"]:
                result[f"{stem}.{stripped}"] = {
                    "kind": "plain", "tail": entry["tail"],
                    "x_col": entry["x_col"], "value_col": orig,
                }
        for name, entry in self._discovered_xz.items():
            stem = name[:-len(".csv.xz")] if name.endswith(".csv.xz") else name
            for col in entry["value_cols"]:
                result[f"{stem}.{col}"] = {
                    "kind": "xz", "file": name,
                    "x_col": entry["x_col"], "value_col": col,
                }
        return result

    # -- dynamic metric discovery (xz, completed runs only) ------------------

    def _scan_discovered_xz_files(self):
        if not self.is_done():
            return
        now = time.time()
        if now - self._discovery_xz_scan_at < RESCAN_EVERY:
            return
        self._discovery_xz_scan_at = now
        try:
            candidates = list((self.dir / "data").glob("*.csv.xz"))
        except OSError:
            candidates = []
        for p in candidates:
            name = p.name
            if name in CLAIMED_FILES or name in EXCLUDED_FILES:
                continue
            if name in self._discovered_xz_excluded or name in self._discovered_xz:
                continue
            try:
                header = probe_xz_header(p)
            except (lzma.LZMAError, OSError, EOFError):
                self._discovered_xz_excluded.add(name)
                continue
            if header is None:
                self._discovered_xz_excluded.add(name)
                continue
            x_idx = None
            for cand in X_AXIS_COLUMNS:
                if cand in header:
                    x_idx = header.index(cand)
                    break
            if x_idx is None or len(header) > DISCOVERY_MAX_COLS:
                self._discovered_xz_excluded.add(name)
                continue
            self._discovered_xz[name] = {
                "path": p, "x_col": header[x_idx],
                "value_cols": [h for i, h in enumerate(header) if i != x_idx],
            }

    def _xz_discovered_series(self, name, x_col, value_col):
        """Lazily parse+cache a discovered xz file; returns (steps, values) or (None, None)."""
        entry = self._discovered_xz.get(name)
        if entry is None:
            return None, None
        path = entry["path"]
        try:
            st = path.stat()
        except OSError:
            return None, None
        key = (st.st_size, st.st_mtime)
        cached = self._xz_discovery_cache.get(name)
        if cached is not None and cached[0] == key:
            header, cols = cached[1]
        else:
            try:
                header, rows = read_xz_csv(path)
            except (lzma.LZMAError, OSError, EOFError):
                self._discovered_xz_excluded.add(name)
                del self._discovered_xz[name]
                return None, None
            if x_col not in header:
                self._discovered_xz_excluded.add(name)
                del self._discovered_xz[name]
                return None, None
            x_idx = header.index(x_col)
            try:
                xs = [float(r[x_idx]) for r in rows]
            except (ValueError, IndexError):
                self._discovered_xz_excluded.add(name)
                del self._discovered_xz[name]
                return None, None
            if len(xs) > 1 and any(xs[i] <= xs[i - 1] for i in range(1, len(xs))):
                # rule 5: x axis not strictly increasing (event-log style file)
                self._discovered_xz_excluded.add(name)
                del self._discovered_xz[name]
                return None, None
            cols = {"__x__": xs}
            for i, h in enumerate(header):
                if i == x_idx:
                    continue
                vals = []
                for r in rows:
                    try:
                        vals.append(float(r[i]))
                    except (ValueError, IndexError):
                        vals.append(float("nan"))
                cols[h] = vals
            n = len(xs)
            if n > 4000:
                stride = math.ceil(n / 4000)
                for k in cols:
                    cols[k] = cols[k][::stride]
            self._xz_discovery_cache[name] = (key, (header, cols))
        return cols.get("__x__"), cols.get(value_col)

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

    # -- per-agent opinion trajectories (Phase 4 / R5) -----------------------

    def _traj_load(self):
        """Whole-file per-agent opinion matrix for a done run, from the same
        opinions.csv.xz the heatmap reads. Kept in its own mtime-keyed cache
        (not _xz_cache) since _xz_parse deliberately discards per-agent values
        to keep the aggregate-stats cache small."""
        path = self.dir / "data" / "opinions.csv.xz"
        try:
            st = path.stat()
        except OSError:
            return None
        key = (st.st_size, st.st_mtime)
        if self._traj_cache and self._traj_cache[0] == key:
            return self._traj_cache[1]
        try:
            header, rows = read_xz_csv(path)
        except (OSError, lzma.LZMAError, EOFError):
            return None
        every = self._snapshot_every(rows)
        try:
            ids = [int(h) for h in header[1:]]
        except ValueError:
            ids = list(range(len(header) - 1))
        n_agents = len(ids)
        steps = []
        agents = [[] for _ in ids]
        for row in rows:
            try:
                idx = int(float(row[0]))
                ops = [float(c) for c in row[1:]]
            except ValueError:
                continue
            if len(ops) != n_agents:
                continue    # malformed/truncated row; keep columns aligned
            steps.append(idx * every)
            for j, v in enumerate(ops):
                agents[j].append(v)
        parsed = {"step": steps, "agents": agents, "ids": ids}
        self._traj_cache = (key, parsed)
        return parsed

    def gexf_trajectory_data(self):
        """Snapshot-cadence per-agent opinion trajectories from GEXF (running
        runs). Nodes are matched across snapshots by id (a node can be briefly
        absent from a payload without desyncing the other agents' columns)."""
        from . import analysis  # deferred: analysis imports core at module level
        steps = []
        agents = []
        id_to_idx = {}
        for s in self.network_steps():
            try:
                parsed = analysis.parse_gexf_cached(self.snapshot_path(s))
            except Exception:
                continue    # snapshot still being written; skip it
            nodes = [n for n in parsed["nodes"] if n["op"] is not None]
            if not nodes:
                continue
            col = len(steps)
            steps.append(s)
            for n in nodes:
                idx = id_to_idx.get(n["id"])
                if idx is None:
                    idx = len(agents)
                    id_to_idx[n["id"]] = idx
                    agents.append([None] * col)
                arr = agents[idx]
                while len(arr) < col:
                    arr.append(None)
                arr.append(n["op"])
        total = len(steps)
        for arr in agents:
            while len(arr) < total:
                arr.append(None)
        return {"step": steps, "agents": agents, "ids": list(id_to_idx)}

    def trajectory_data(self):
        return self._traj_load() if self.is_done() else self.gexf_trajectory_data()

    # -- series ---------------------------------------------------------------

    def metric_series(self, name):
        """(steps, values) for one catalogue metric; both [] when unavailable."""
        spec = METRICS.get(name)
        if spec is None:
            entry = self.discovered_metrics().get(name)
            if entry is None:
                return [], []
            if entry["kind"] == "plain":
                steps = entry["tail"].column(entry["x_col"])
                values = entry["tail"].column(entry["value_col"])
            else:
                steps, values = self._xz_discovered_series(
                    entry["file"], entry["x_col"], entry["value_col"])
            if not steps or not values:
                return [], []
            return [int(s) for s in steps], values
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

        for st in STORES.values():
            for mid in st.discovered_metrics():
                cols.add(mid)
                stem, _, col = mid.partition(".")
                labels.setdefault(mid, f"{stem}: {col}")

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


def api_trajectories(qs):
    """Per-agent opinion trajectories (Phase 4 / R5): wide {step, agents, ids}
    payload for the opinion tab's default canvas view. Decimated server-side
    on both axes so the response stays within a few MB even for long, large-n
    runs; the client is told how many agents it's actually seeing."""
    rid = qs.get("run", [""])[0]
    max_steps = int(qs.get("max_steps", [str(TRAJ_MAX_STEPS)])[0])
    with LOCK:
        poll_all()
        st = get_store(rid)
        empty = {"step": [], "agents": [], "ids": [], "shown": 0, "total": 0, "live": False}
        if st is None:
            return empty
        parsed = st.trajectory_data()
        if not parsed or not parsed.get("step") or not parsed.get("agents"):
            return {**empty, "live": not st.is_done()}
        steps, agents, ids = parsed["step"], parsed["agents"], parsed["ids"]
        idx = decimate(list(range(len(steps))), max_steps)
        total = len(agents)
        agent_sel = list(range(total))
        if total > TRAJ_MAX_AGENTS:
            stride = math.ceil(total / TRAJ_MAX_AGENTS)
            agent_sel = agent_sel[::stride]
        return {
            "step": [int(steps[i]) for i in idx],
            "agents": [[rnd(agents[a][i]) for i in idx] for a in agent_sel],
            "ids": [ids[a] for a in agent_sel],
            "shown": len(agent_sel), "total": total,
            "live": not st.is_done(),
        }


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
