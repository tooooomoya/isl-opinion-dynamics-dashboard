# 2026-07-11 — Opinion-distribution panel: density heatmap + selectable 5/10 bins

## Decision
Replaced the dashboard's "opinion distribution over time" panel from a **stacked-share
area chart** to a **density heatmap** (x = step, y = opinion bin −1→+1, color = per-step
share, viridis). Added a `bins` selector offering **5 or 10** opinion bins.

## Rationale
- The stacked-share view conflates bin identity via a diverging palette and makes it hard
  to read *when* a second mode emerges. A heatmap makes bimodality legible as two bright
  horizontal bands and their split-off time — the object of interest for Type-1/Type-2
  polarization (see `docs/research-direction.md`).
- Color scale is fixed to the panel-global max share, so density is comparable across time
  (not per-column renormalized).
- Chose heatmap over a 3-D surface (view-dependent, occlusion) and over quantile/fan bands
  (a median line and IQR collapse onto the empty center of a bimodal distribution and hide
  the very polarization we study).

## Bin resolution
- The opinion histogram is precomputed in Java (`opinion/opinion_result.csv` as
  `bin_0..bin_{N-1}`); the raw per-agent opinions are not persisted, so a stored 5-bin
  histogram cannot be refined to 10. To make 10 available, bumped
  `Const.NUM_OF_BINS_OF_OPINION_FOR_WRITER` 5 → **10** (decoupled from the analysis-side
  5-class binning `NUM_OF_BINS_OF_OPINION`, which is unchanged and used elsewhere).
- 10 is a multiple of 5 with aligned edges, so the dashboard re-aggregates pairs 10→5
  **exactly**; both resolutions come from one dataset.
- Backward compatible: `api_opinion` reads the bin count from the CSV header. Existing
  5-bin runs display 5 and the "10" option is disabled; **new runs must be produced with
  the rebuilt Java to get true 10-bin resolution.**

## Update (same day) — reverted the 10-bin change; kept histogram at 5
Reverted `Const.NUM_OF_BINS_OF_OPINION_FOR_WRITER` back to 5
(= `NUM_OF_BINS_OF_OPINION`). Reasoning that settled it:
- Raw per-agent opinion is **not persisted per step** — only the histogram is
  (GEXF snapshots carry raw opinion but at ~5000-step cadence, 0–1 snapshots in most
  runs). So a stored 5-bin histogram cannot be re-split to 10 without re-running.
- Re-running solely to get 10 bins would leave the opinion histogram **out of step with
  the analysis-side 5-class binning** (`NUM_OF_BINS_OF_OPINION`, used across
  `Analysis.java` / `OpinionDynamics.java` for feed/comfort/hostility-by-class metrics).
  Consistency with those files was judged more important than heatmap bin count.
- Dashboard consequence: removed the 5/10 `bins` selector; the heatmap now reads whatever
  bin count the CSV header carries (currently 5). The heatmap rendering itself (replacing
  the stacked-share view) is **kept** — that was the endorsed improvement. `dashboard.py`
  still reads the bin count from the header (robust if the writer constant ever changes).
- `Writer.setOpinionBins` local var kept renamed `opinionClass`→`binIndex` (clarifies it
  bins straight from raw opinion, independent of `Agent.opinionClass`).

## Supersedes
- The stacked-share rendering of the opinion panel (previous `renderOpinion`).

## Follow-up (not yet done)
- Companion ridgeline (joyplot) of representative-step snapshots, per the
  heatmap-primary + ridgeline-secondary plan.
