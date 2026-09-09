# 2026-07-11 — Dashboard metric layout: fixed 2-tier (carousel + featured) instead of free resize

## Decision
Replaced the metric charts' free-resize/reorder model with a **fixed 2-row layout**:
- **Row 1 — carousel** (`#gridCarousel`): horizontal, scroll-snapping strip of small metric
  cards, ~4.5 visible at a time (`flex:0 0 clamp(240px,22%,340px)`), holds any number.
  New metrics (added via the picker) land here. `‹ ›` buttons page-scroll it.
- **Row 2 — featured** (`#gridFeature`): up to **2** large cards (`flex:1 1 calc(50%-6px)`);
  may be empty (`:empty` hides the row). A single featured card grows to full width.

A card's size is now determined by **which row it is in**. Each metric card has a **⤢/⤡
button** that promotes it to row 2 / demotes it back. Promoting when row 2 is full evicts
the **oldest** featured card (front of the list) back to the carousel.

State: `state.featured` (array of metric ids, max 2, oldest-first) persisted to
`localStorage["dash.featured"]`. Carousel scroll position is preserved across the
poll-driven rebuilds of `renderGrid`.

## Rationale
- Free per-card resize (`resize:both` + per-id size persistence) gave inconsistent,
  fiddly layouts. Quantizing to two sizes (overview vs. detail) is faster to read and
  removes the need to hand-tune each card.
- Carousel keeps the overview compact regardless of how many metrics are selected;
  the featured row is the explicit "look closer" surface.

## Scope / what is unchanged
- **Metric charts only.** The 2-D plane, opinion heatmap, network snapshot, and the
  degree/structstats/qsignei/repostpair/attrpair groups keep their existing
  resizable + drag-reorder behavior (`makeCard`, `initStaticCards`). Chosen deliberately
  (see 2026-07-11 clarification) to keep the change contained.

## Supersedes
- Metric cards built via `makeCard(..., "metrics", ...)` in the old flex-wrap `#grid`
  (free-resize + drag-reorder). `#grid` and the `"metrics"` reorder group are gone;
  `makeCard`/`attachDrag`/`watchCardSize` remain in use by the other card groups.
