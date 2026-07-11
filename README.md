# Echo-chamber Live Dashboard

This package serves a read-only dashboard for echo-chamber run outputs.

Use:

```bash
python scripts/dashboard/dashboard.py --serve
```

The web server scans `data/` and `data_hdd1/` by default, or any roots passed
with repeated `--root` options. It reads run directories containing
`run_meta.json`, tails live CSV files, and reads completed `.xz` outputs and
`G_*.gexf.bz2` network snapshots without writing to the run data.

This branch keeps the echo-chamber additions from the earlier two-file
dashboard:

- recursive run discovery from `run_meta.json`
- live CSV tailing plus completed-run `.xz` loading
- stale fallback for partially written GEXF.bz2 snapshots
- custom color stops (arbitrary stops, saved presets) for the network color scale
- ForceAtlas2 layout, zoom, and pan in the network view

Upstream-derived UI wired to the echo-chamber catalogue:

- metric picker over the served metric catalogue, including derived metrics
  (`DERIVED`, e.g. `opinion_std`)
- 2-D outcome plane: trajectory of any two metrics with scrub and playback
- show-mean toggle over the currently visible runs
- resizable and reorderable panel cards with persisted size and order
- network snapshot time scrub over the `G_*.gexf.bz2` steps, with playback
- node size and color attribute selectors (in/out/total degree, opinion,
  opinion sign, hypothesis)

Unsupported in this branch (panels are hidden, not shown empty):

- the matplotlib GUI fallback; use `--serve`
- repost, log-tail, bounded-confidence, post-probability, and structural
  analysis panels until the data layer exposes those inputs
