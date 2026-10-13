# 2026-09-22 — Dashboard multi-tab state isolation bug, and a cold-load performance fix

## Context
While comparing the alpha dose-response scan's per-alpha networks/metrics in the dashboard
(see `2026-09-11-alpha-dose-response-broad-scan.md`), opening two tabs on two different run-set
groups (`alpha_scan_a0.00_seed` / `alpha_scan_a0.40_seed`) showed identical metrics in both tabs.

## Bug: server-global run-set selection, not per-tab
`dashboard/core.py`'s `SERVE_GROUP` was a single module-level global, mutated by `POST
/api/group`. Two browser tabs picking two different run sets were fighting over the same
server-wide variable; whichever tab (or periodic poll) last switched it won for both. Fixed
(independently, in parallel, in `Dev-ComplexNetworks2026` — pushed to `dashboard-remote/toomoya`
as "Fix dashboard state isolation and responsiveness", pulled into this repo's `dashboard/`
wholesale, superseding an initial local fix attempted here first) by making every group-scoped
endpoint (`/api/summary`, `/api/series`, `/api/opinion`, `/api/repost`, `/api/post_lifespan`,
`/api/log`, `/api/network`) take an explicit `?group=` query param, resolved per-request
(`selected_group`/`resolve_group`), with `STORES` keyed by `(group, seed)` instead of `seed`
alone. The frontend keeps its chosen group in **its own tab's URL** (`?group=...`), not
localStorage (shared across all tabs of the same origin, which would defeat the isolation).

**Sync note:** this repo (`polarized-vocal-minority-model`) has no established `git subtree`
history with `dashboard-remote` (its `dashboard/` was copied in via `git archive`, not `git
subtree add`, at the 2026-09-09 fork) — the same "was never added" failure mode documented in
`Dev-ComplexNetworks2026/docs/report/2026-07-17-dashboard-yabe-feature-port.md` would hit a plain
`git subtree pull` here. Sync was done by diffing `dashboard-remote/toomoya`'s tree directly
against this repo's committed `dashboard/` and taking the changed files wholesale (only
`analysis.py`/`api.py`/`core.py`/`dashboard.html` differed; the other 8 files were already
byte-identical).

## Performance: cold group-load was ~107s on this project's data, now ~3s
Diagnosed while verifying the isolation fix: a cold `/api/summary` for a 21-seed group took
~107 seconds (mistakable for a hang — likely the same "loading never finishes" symptom hit
earlier in this session). Root causes, both in `CsvTail` (not specific to either isolation fix —
pre-existing since the class's introduction):

1. **`column(name)` eagerly float-converted every cell of every kept row on ingest**, before
   any caller ever asked for that column. A "done" 20000-step/~150-column `results.csv` means
   ~3M wasted `float()` calls per seed just to populate columns nothing reads.
2. **`SeedStore.poll()` unconditionally polled `repost`/`lifespan`/`op` CsvTails for every seed
   in a group**, even though `api_opinion`/`api_repost`/`api_post_lifespan` each only ever read
   *one* seed at a time (`opseed`/`netSeed` in the frontend). `repost_cascades.csv` was observed
   at ~152MB / 2.7M rows for one seed on this project's alpha-sweep data — parsing that for all
   21 seeds on every group load when at most 1 is ever displayed is pure waste.

Fixes (both behavior-preserving, verified against raw CSV values — see below):
- `CsvTail.rows`/`.latest` now hold raw string tokens; `column(name)` parses floats lazily, only
  for the requested column. A line whose stride-index says "decimate away" and isn't the chunk's
  last line skips comma-splitting entirely (cheap truthiness check only) — the actual remaining
  cost on this project's repost CSVs, once float-parsing was no longer the bottleneck.
- `SeedStore.poll()` now only tails `main`/`mod` (needed group-wide, by `api_summary`/
  `api_series`). `op`/`repost`/`lifespan` moved to `poll_op()`/`poll_repost()`/`poll_lifespan()`,
  called on demand by their respective single-seed endpoint.

**Measured (this project's alpha dose-response run set, 21 seeds/group, cold cache):**
`/api/summary` ~107s -> ~3s per group. Per-seed `/api/repost` (the 2.7M-row file, now read for
just the one requested seed) ~1.4s. Values cross-checked against the raw CSV (e.g.
`opinionVar`'s last row) match exactly pre/post-fix.

**Not yet done:** pushing this performance fix back to `dashboard-remote/toomoya` (the shared
base other forks/collaborators use) — ask before doing so, since it touches shared code outside
this repo and this repo's `dashboard/` has no working subtree link back to it yet (see sync note
above; would need the same manual-diff approach, or re-establishing a proper subtree split
point).
