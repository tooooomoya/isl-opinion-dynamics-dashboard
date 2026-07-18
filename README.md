# Opinion Dynamics Dashboard

A read-only, model-agnostic live dashboard for opinion-dynamics simulation runs.
It tails a run's output while it's still writing, and serves a browser UI with
time-series metrics, an opinion/outcome view, and an interactive network
snapshot view — auto-discovering whatever your model's data happens to expose.

This is the **shared generic base branch** of this dashboard. Contributors
fork it per-model (adding their model's specific metric catalogue, node
attributes, help text, and data-layer wiring) on their own branch — see
"Contributor forks" below. If you're looking for a specific model's fully
wired dashboard, check the fork branches, not this one.

## Run it

```bash
python dashboard.py --serve
```

Options: `--logdir` (default `logs/`), `--seeds` (restrict to specific seeds),
`--host`/`--port` (default `127.0.0.1:8765`). A GUI fallback (`python
dashboard.py`, no `--serve`) is also available — a minimal matplotlib window
with just the metrics grid, for when a browser isn't available.

For remote access without opening ports, `serve_public.sh` wraps `--serve` in
a Cloudflare Quick Tunnel — the server still binds to `127.0.0.1`; nothing is
exposed to the LAN/internet except through the tunnel. No auth layer exists
either way: anyone with the URL can view, and can also overwrite the local
color-preset file via `POST /api/color-presets`. Fine for experiment metrics
with no sensitive data; reconsider before pointing this at anything else.

## Run-discovery model (current, unchanged from upstream)

A run is identified by a seed number. The server watches `<logdir>/run_<seed>.log`
files to find active seeds and classify them `running`/`done`/`failed` (regex
over the log text: `Exception`/`TERMINATE` → failed, `Elapsed time` → done,
else running), then reads `results/run_<seed>_*/` (newest by mtime) for that
seed's CSVs and network snapshots.

This is a known limitation for reuse: it assumes a single root and a specific
log/directory naming convention. A more general, marker-file-based, multi-root
recursive run-discovery model is a deliberately deferred follow-up — not yet
part of this generic base. If your model doesn't fit this convention, this is
the piece to replace first (on your own fork, not here).

## What's generic here (safe to build on for any model)

- **`CsvTail`**: incremental, offset-based tailing of an all-numeric CSV with
  adaptive decimation as it grows — no schema assumptions.
- **Dynamic column/metric discovery**: `/api/summary` returns whatever columns
  the tailed CSV(s) actually have; the frontend's metric picker is built from
  that, not a hardcoded list.
- **Family grouping**: any set of columns named `<base>_0`, `<base>_1`, ...,
  `<base>_N` (every index 0..N present) is collapsed into one picker entry,
  rendered as one multi-line chart. Bin count is whatever the data provides,
  not a fixed number.
- **`DERIVED`**: a small mechanism for defining a metric as a function of other
  columns (e.g. `a - b`), auto-added to the picker once its dependencies are
  present. Ships with no paper-specific formulas here — add your own.
- **Network snapshot view**: reads GEXF snapshots, computes structural metrics
  (giant-component fraction, algebraic connectivity λ₂, betweenness, degree
  power-law fit, clustering, RWC, boundary polarization/ρ) directly from the
  graph — no side-CSV dependency.
- **Configurable node encoding** (`NODE_ATTRS`/`SIZE_KEYS`/`COLOR_KEYS` in
  `dashboard.html`): node size/color pickers over whatever attributes are on
  the GEXF nodes. Ships with the universal ones (opinion, in/out/total degree,
  opinion sign) — see "Plugin contract" below to add your own.
  Two layout algorithms (force-directed, ForceAtlas2), a per-agent opinion
  trajectory view, a 3D/waterfall opinion-distribution view, resizable and
  reorderable panel cards with persisted layout, per-card PNG export, and
  user-editable color scales with saved presets.
- Color-preset read/write API (`/api/color-presets`) — fully generic, no
  schema coupling.

## Plugin contract — what your model's data needs to provide

To get metrics, network, and opinion views working with **zero code changes**:

- **Time-series columns**: any all-numeric column in a tailed CSV is picked up
  automatically. An `x`-axis column named `step` is expected.
- **Per-bin family metrics**: name grouped columns `<metric>_0`, `<metric>_1`,
  ... contiguously from 0; any bin count works.
- **Network snapshots**: GEXF files, one per step. Every node needs an
  `opinion` attribute (float) for structural metrics and the built-in opinion
  color; add any other node attribute you want selectable as a size/color
  encoding — see below.
- **Two-camp structural metrics** (RWC, boundary polarization, boundary ρ):
  computed from a plain `sign(opinion)` split of nodes by default
  (`MODERATE_BAND_HALF_WIDTH = 0.0` in `analysis.py`). If your model wants a
  "moderate"/undecided exclusion band around 0 instead, raise that constant on
  your fork.
- **Repost/interaction cascades**: `/api/repost` is stubbed (always empty) in
  this generic base, since cascade reconstruction needs a specific
  root/parent/post-id CSV schema that only some pipelines produce. Wire
  `core.api_repost` up on your fork if your model writes cascade data.

To extend the UI for your model, on your own fork:

- Add metric descriptions to `METRIC_DESC` and tab descriptions to
  `SECTION_HELP` in `dashboard.html` (both ship empty/generic here — missing
  entries just fall back to "No description available").
- Add GEXF node attributes to `NODE_ATTRS` (and list their keys in
  `SIZE_KEYS`/`COLOR_KEYS`) to make them selectable in the network view.
- Set `DEFAULT_METRICS` if you want specific charts shown on first load
  (ships empty here — the picker starts with nothing pre-selected).

## JSON API

`/api/summary`, `/api/series?cols=...`, `/api/opinion`,
`/api/network?seed=&net=&step=&structural=`, `/api/trajectories`,
`/api/repost` (stub), `/api/log`, `/api/color-presets` (GET/POST). See
`api.py`/`core.py`/`analysis.py` for exact query params and response shapes.

## Known limitations

- No history or persistence — this is a live view over whatever's currently in
  the run directories. Closing the browser loses nothing (state is either
  server-derived or in `localStorage` for display settings only); there's no
  timeline beyond what the underlying CSVs still contain.
- Decimation (for both time-series and per-agent trajectories) is
  uniform-stride, not envelope-preserving — go back to the raw CSVs/notebooks
  for rigorous analysis, don't treat the dashboard's decimated view as ground
  truth.
- `fit_powerlaw` is an MLE point estimate plus an exponential-plausibility
  check only (Clauset et al. 2009 minimum practice) — it does not compare
  against other heavy-tailed distributions (e.g. log-normal).
- `result_dir()`'s mtime-newest heuristic (see "Run-discovery model" above) is
  an assumption, not a guarantee; a manually-touched stale results folder for
  the same seed will fool it.

## Contributor forks

This package's independent GitHub repo (kept in sync with a model repo's
`dashboard/` directory via `git subtree`) hosts each contributor's
model-specific fork as its own branch off this generic `main`. `main` itself
should stay model-agnostic — land genuinely generic improvements here, and
keep paper/model-specific metrics, node attributes, help text, and data-layer
wiring on your own branch.

### Registering the remote (one-time, in your model repo)

```bash
git remote add dashboard-remote <this repo's URL>
```

### Sync commands

Push your model repo's `dashboard/` changes to your fork branch:

```bash
git subtree push --prefix=dashboard dashboard-remote <your-branch>
```

Pull your fork branch's changes back into your model repo:

```bash
git subtree pull --prefix=dashboard dashboard-remote <your-branch> --squash
```

Pulling improvements from this generic `main` (or another contributor's
branch) into your fork is a manual merge/diff, not a plain `subtree pull`,
once your branch's history has diverged enough that the subtree split points
no longer line up — diff the specific files/functions you want instead of
attempting a full merge.

> [!NOTE]
> Make sure your model repo's working tree is clean (all changes committed or
> stashed) before running a subtree sync.
