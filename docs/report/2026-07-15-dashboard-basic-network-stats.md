# 2026-07-15 — dashboard: basic network descriptive stats

## Decision
Added standard network-descriptive fields to the network-structure summary panel
(`renderStructSummary` in `dashboard/dashboard.html`, backed by `compute_structural`
in `dashboard/analysis.py`), alongside the existing RWC / Hartigan dip / λ2 / giant
component fraction:

- `nNodes` / `nEdges` — full graph (not just giant component)
- `avgDegree` = 2·|E|/|V| (undirected)
- `density` = `nx.density`
- `avgPathLength` and `diameter` — computed on the giant component only, via
  `nx.average_shortest_path_length` / `nx.eccentricity`

## Rationale
User asked for "the basic stuff — mean degree, path length, roughly that" to sit
next to the more specialized polarization/connectivity metrics already there. These
are standard descriptive baselines any CSS reviewer expects before the
RWC/dip/λ2 numbers mean anything.

## Implementation notes
- APL/diameter require O(n·m) BFS sweeps (`average_shortest_path_length` /
  `eccentricity` both do a full BFS per node). At the model's typical n≈1000 giant
  component this is fast (<1s, verified against `results/run_.../seed 2` — 1000
  nodes, 9934 edges, avgDegree≈19.87, density≈0.0199, avgPathLength≈1.98,
  diameter=3). Capped at 3000 nodes (`Gg.number_of_nodes() <= 3000`) so a much
  larger snapshot doesn't stall the `/api/network?structural=1` request; beyond
  that the panel shows "–" with a note that it was skipped.
- `nNodes`/`nEdges`/`avgDegree`/`density` are on the *full* undirected graph
  (matches how degree/clustering CSVs are already reported), while
  `avgPathLength`/`diameter`/λ2/RWC stay giant-component-only since they're
  undefined (or degenerate) on a disconnected graph.
- This follows [[dashboard-generic-tool]] — these are model-agnostic descriptive
  stats, not experiment-specific.

## Verified
Ran `python3 -m dashboard --serve --logdir logs` against live results
(`results/run_..._seed2`, done at step 40000) and hit
`/api/network?seed=2&net=follow&step=40000&structural=1` directly — all six new
fields populated as expected.
