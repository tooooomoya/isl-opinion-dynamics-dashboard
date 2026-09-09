# 2026-07-21 — Dashboard: repost edge-type coloring (homophily vs hostile)

## Context

Earlier the same day, `RepostVisualize.java`/`OpinionDynamics.java` (uncommitted at time of
writing) added a homophily/hostile split on repost edges: each directed repost edge in the GEXF
export now carries `homophilyReposts`/`hostileReposts` integer counts and a `dominantEdgeType`
string (`"homophily"` | `"hostile"` | `"mixed"`), tagging whether the relay crossed the relayer's
bc window at read time (`Post.isOutOfBcRelay()` — repostProb-gated in-bc relay vs
outOfBCRepostProb-gated out-of-bc relay). This was Java-side only; the dashboard's live network
panel had no way to visually distinguish the two edge types on a repost-graph snapshot.

## Decision

Wired the existing `dominantEdgeType` GEXF edge attribute through to the dashboard's network
snapshot panel as an opt-in coloring mode, rather than building a new panel:

- `dashboard/analysis.py:load_network` — edge tuples extended from `[u, v, weight]` to
  `[u, v, weight, dominantEdgeType]` (4th element `None` when absent — follow-graph edges, and
  repost snapshots written before today).
- `dashboard/dashboard.html` — new checkbox `#netedgetype` ("color edges by relay type"), next to
  the existing `#netcross` (highlight cross-cutting edges) control. When checked, `drawNet()` draws
  edges in three passes by `dominantEdgeType` using a **fixed** (non-user-editable) 3-color palette
  (`getEdgeTypePalette`, green/red/purple — chosen to avoid the diverging blue↔red opinion scale and
  to not fully overlap opsign's blue/cyan/green triple), falling back to the plain edge color for
  untyped edges so nothing silently disappears. Legend (`updateNetLegend`) and persistence
  (`localStorage` key `netedgetype`) mirror the `netcross` wiring exactly.

## Why this shape

- Reused the GEXF pipeline that already existed for node attributes (`bc`/`pp`/`hub`/etc.) rather
  than adding a new API endpoint — `dominantEdgeType` is just another edge attribute Gephi already
  writes, so `load_network`/`api_network`/`GRAPH_CACHE` needed no new plumbing.
- Fixed (not user-editable) palette: node categorical colors are user-editable because they're a
  general-purpose encoding (`opsign`, `hub`, arbitrary future attrs); this is a narrow, one-off
  diagnostic view for a single mechanism, so a fixed palette avoids UI surface for a feature with a
  much smaller audience.
- No effect on the follow graph (attribute doesn't exist there) or on any repost snapshot from
  before today — verified by hand: `load_network()` against a real pre-existing `repostNW` GEXF
  (`results/run_2_ext-NONE_.../GEXF/repostNW/repost_step_40000.gexf`) returns
  `[u, v, weight, None]`, and the frontend's fallback path draws those with the plain edge color.

## Verification

- `dashboard/analysis.py` parses (`ast.parse`) and imports cleanly.
- Inline `<script>` block in `dashboard.html` parses cleanly under Node (`new Function(source)`).
- `/api/network?net=repost&step=latest` against a real seed's result dir returns the new 4-element
  edge tuples with `null` type (pre-existing snapshots, as expected).
- Did **not** get a pixel-level headless-Chrome screenshot of the checked/colored state — no
  puppeteer/CDP automation available in this environment to click the network tab + checkbox
  non-interactively, and installing new global tooling for a one-off check wasn't warranted. Code
  path was verified by exact mirroring of the already-shipped, already-tested `#netcross` control
  (same event wiring, same legend/persistence pattern), plus the data-layer checks above.
- Manual visual confirmation in a real browser (toggle `#netedgetype` on a repost-graph snapshot
  produced by the still-uncommitted Java change) is still open — do this once a fresh run has
  produced GEXF snapshots with the new attribute.

## Supersedes / relates to

- Builds on the uncommitted 2026-07-21 Java change (homophily/hostile repost-edge split in
  `OpinionDynamics.java`/`RepostVisualize.java`/`Post.java`) — that change is not yet committed as
  of this entry.
- Does not touch `compute_structural`/degree-CCDF (`2026-07-15-dashboard-basic-network-stats.md`) —
  user confirmed CCDF is already covered there; this entry is edge-level, not degree-distribution.
