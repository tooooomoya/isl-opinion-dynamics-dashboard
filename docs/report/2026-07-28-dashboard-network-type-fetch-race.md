# 2026-07-28 — Dashboard: repost/follow network panel silently stuck on stale graph type

## Context

User report: the repost-graph and follow-graph views in the Network Snapshot panel looked
visually identical, and setting the edge-weight filter's lower bound to 2 on the repost graph
removed every edge — which shouldn't be possible, since a repost pair reposting fewer than 2
times in a 5000-step window across ~1000 agents is not the norm.

## Investigation

Raw-data check first, to rule out a Java/export bug: parsed `repost_step_20000.gexf` directly
(bypassing the dashboard entirely) — of 51,885 repost edges, 38,841 (75%) carry an explicit
`weight` attribute (Gephi omits it only at the default 1.0), ranging up to 130, mean ~18. The
follow-graph GEXF for the same run has **zero** edges with an explicit weight — every follow edge
is weight 1, which is correct: a follow relationship is a 0/1 adjacency, not a count, so it having
no weight variation is by design, not a bug. So `RepostVisualize.java`'s
`edge.setWeight(homophilyW[i][j] + hostileW[i][j])` (repost-count accumulator, reset every
5000-step snapshot window) is working correctly.

Checked `dashboard/analysis.py:load_network`/`api_network` next, both via direct function call and
via `curl` against the live `--serve` process (port 9000) for `net=follow` vs `net=repost` across
6 seeds (the small 5-seed test group and seed 4050012 from the running `bridgecur_seed` sweep) —
every case correctly returned unweighted (all 1.0) edges for `net=follow` and properly varied
weights (60–80%+ of edges ≥ 2) for `net=repost`. Backend layer is not the bug.

Reproduced in an actual browser (headless Chrome via `puppeteer-core`, attached to the system
Chrome — no browser download needed) since the 2026-07-21 edge-type-viz report had explicitly
flagged that this code path was never verified in a real browser (only parse-checked). Traced
`fetchNetwork()` invocations directly:

```
fetchNetwork called, loading=false type=follow seed=0   <- initial tab-open fetch (structural=1,
                                                             several seconds: betweenness_centrality etc.)
fetchNetwork called, loading=true  type=repost seed=0   <- #nettype change listener's call, dropped
fetchNetwork returned normally                              here by `if(netState.loading) return;`
```

**Root cause**: `fetchNetwork()`'s concurrency guard (`if(netState.loading || !seedList().length)
return;`, `dashboard/dashboard.html`) silently drops any call that arrives while a fetch is already
in flight. The `#nettype` change listener always sets `netState.type` *before* calling
`fetchNetwork()`, so if the user flips follow→repost while the initial (slow, `structural=1`)
fetch is still running, `netState.type` becomes `"repost"` but the dropped call never issues the
request — `netState.data` keeps the stale follow-graph payload. Nothing self-heals: the periodic
`maybeRefetchNetwork()` only refetches on a run-tag change or +5000-step advance, never on a
type/seed mismatch with `netState.data`. For a finished run (steps no longer advancing), this
mismatch is permanent until the user happens to re-toggle the dropdown while no fetch is in
flight. This exactly reproduces both symptoms: the panel keeps showing the (unweighted) follow
graph mislabeled as "repost graph," so any weight ≥ 2 filter zeroes every edge.

## Fix

`dashboard/dashboard.html:fetchNetwork` — replaced the silent drop with a one-shot pending-retry
flag: a call arriving mid-flight sets `netState.pendingRefetch=true` and returns; the `finally`
block of the in-flight call checks the flag and immediately re-invokes `fetchNetwork()` (which by
then reads the up-to-date `netState.type`/`seed`/`step`). No debouncing/coalescing beyond the
single pending flag — the guard's job is only to avoid concurrent requests, not to rate-limit.

## Verification

Re-ran the same puppeteer trace after the fix:

```
fetchNetwork called, loading=false type=follow seed=0
fetchNetwork called, loading=true  type=repost seed=0   <- queued via pendingRefetch
fetchNetwork returned normally
fetchNetwork called, loading=false type=repost seed=0   <- auto-retried
fetchNetwork returned normally
```

Resulting panel state for seed 0 / repost graph, weight filter min=2: 36,851 total edges, weight
range 1–108, 30,405 edges (82%) surviving the ≥2 filter (previously 0). Matches the raw-GEXF-level
expectation from the investigation above.

## Supersedes / relates to

- Confirms the open verification gap flagged in
  `2026-07-21-dashboard-repost-edge-type-viz.md` ("did not get a pixel-level headless-Chrome
  screenshot... no puppeteer/CDP automation available") — puppeteer-core against the system Chrome
  (no bundled browser download) closes that gap for future dashboard JS verification.
- Not a data/model bug — `RepostVisualize.java` and `dashboard/analysis.py` needed no changes.
