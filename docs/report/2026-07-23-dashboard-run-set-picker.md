# 2026-07-23 — Dashboard: switchable "run set" picker for non-`run.sh` experiments

## Context

The dashboard was hardwired to `run.sh`'s naming convention: `active_seeds()` only matched
`logs/run_<seed>.log`, and the seed set it tracked came from a single `--logdir`/`--seeds` CLI
choice fixed at server startup. Every AI-agent-driven calibration script (`scripts/*bo*.py`,
sweeps, etc.) writes its own log naming instead — `logs/app_pol_baseline_v5_seed<seed>.log`,
`logs/stage1b_bo_seed<seed>.log`, and so on — so the dashboard never saw these runs at all,
regardless of what `results/` contained. `results/run_<seed>_<tag>/` itself was already
convention-shared across every script (same `ExperimentConfig.tag()` derivation), so only log
discovery needed to change.

User ask: be able to point the dashboard at whichever experiment an agent just launched, "select
and load," without making the tool heavier.

## Decision

Added a "run set" concept = a `logs/*.log` filename prefix, auto-discovered with zero
per-script registration, switchable at runtime from a dropdown (no server restart):

- `dashboard/core.py`
  - `GROUP_LOG_RE = r"^(.+?)(\d+)\.log$"` replaces the old fixed `run_(\d+)\.log$` match.
    Any `logs/<prefix><seed>.log` is discovered — `run_0.log` → prefix `run_`;
    `app_pol_baseline_v5_seed3.log` → prefix `app_pol_baseline_v5_seed`. Works retroactively on
    every naming convention already present in `scripts/*.py` with no script changes.
  - `log_groups(logdir)` — groups `logs/*.log` by that prefix → `{prefix: [(seed, path), ...]}`.
  - `active_seeds(logdir, only=None, prefix=None)` gained a `prefix` param (defaults to
    `DEFAULT_GROUP = "run_"`, so `dashboard/gui.py`'s positional call keeps working unchanged).
  - New `SERVE_GROUP` module global (mirrors `SERVE_LOGDIR`/`SERVE_ONLY`) holds the
    currently-selected prefix; `poll_all()` and `api_log()` read it instead of a hardcoded `run_`.
  - `api_groups()` / `set_group(prefix)` — list available run sets (seed count, running/done/failed
    breakdown, latest mtime) and switch the active one. `set_group` rejects prefixes not currently
    present under `logs/` — this isn't just validation, it closes off using the prefix as an
    arbitrary-path primitive into `api_log`'s `f"{SERVE_GROUP}{seed}.log"` lookup.
  - Switching a group clears `STORES` under `LOCK` so the next poll rebuilds cleanly against the
    new seed set (no stale `SeedStore` from the old group lingering under a reused seed number).
- `dashboard/api.py` — `GET /api/groups`, `POST /api/group {prefix}`.
- `dashboard/dashboard.html` — new `#rungroup` `<select>` in the header, next to the refresh
  controls. Repopulated every poll cycle from `/api/groups` (cheap — just a `logs/` glob, no CSV
  parsing) so newly-started scripts appear without a page reload; `change` POSTs the new prefix,
  clears `state.opseed`/`netState.seed` (their existing "if not in current seed list, re-pick"
  fallback logic — already used at first load — handles picking new defaults), then calls
  `refresh()`.

## Why this shape, not a real folder browser

Rejected browsing `results/` directly as the unit of selection. `results/run_<seed>_<tag>/`
folders aren't grouped by experiment on disk — the `<tag>` is a parameter fingerprint that
changes every BO round, so "pick a folder" would mean picking an arbitrary, constantly-shifting
tag pattern with no stable handle. Log filenames, by contrast, are a stable per-script identity
the launching script already chose (and already had to choose something for, or its own log
tailing wouldn't work) — grouping by that prefix reuses an identity that already exists rather
than inventing a new one that scripts would need to opt into (e.g. a results-subdirectory
registry) for every future experiment.

This also deliberately leaves `result_dir()`'s mtime-newest heuristic (`docs/dashboard.md`, known
pitfall) untouched: switching run sets only changes *which seeds are tracked*, not how the "live"
results folder for a given seed is resolved. Two experiments concurrently reusing the same seed
numbers can still interleave in principle — pre-existing limitation, out of scope here.

## Verified

Started `dashboard/dashboard.py --serve` against the real (large, `.gitignore`d) `logs/`/`results/`
trees left over from the `app_pol_baseline_v4`–`v8` BO calibration runs. `/api/groups` correctly
enumerated 14 run sets (`run_`, `app_pol_baseline_v2/_v4..v8_seed`, `oob_scan_oob*_seed`,
`hubtier_seed`, ...) with accurate seed counts and running/done/failed breakdowns; `POST
/api/group` switched `/api/summary` and `/api/log` over to the new prefix's seeds; an unknown
prefix was rejected. Headless-Chrome DOM dump confirmed the `#rungroup` picker renders all 14
options with the CLI-specified default (`run_`) pre-selected.
