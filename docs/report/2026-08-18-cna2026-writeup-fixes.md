# 2026-08-18 — CNA2026 writeup fixes (Discussion restructure, NE-E-influx normalization, network validation)

Continuation of the CNA2026 paper-writing work in `docs/report/2026-08-15-mechanism-re-derivation.md`.
That file covers the mechanism findings; this one covers writeup/figure-correctness decisions made
directly in `tex/CNA2026/`.

## 1. Discussion section restructured around reviewer's 3-claim skeleton

External review (relayed by user) identified the Discussion as logically sound but too verbose, and
asked for it to be organized explicitly around three claims (direct moderate/near-extreme effects;
indirect near-extreme-mediated pathway to extreme; openness×comfort sign-flip), plus terminology
fixes: "prove"→"support/evidence", "κ alone decides"→"κ determines the evaluation of admitted
content", "facilitator/mediator region"→"facilitating/suppressing regime", "insulator"→"upstream
regulator" (already applied).

Applied to `CNA2026-2nd.tex` (§`sec:discussion`): grammar cleanup throughout (the user's own draft had
typos/fragments — "alignes", "environemnt", "themsselves", etc.), the terminology swaps above, and one
substantive correctness fix — the opening sentence had "amplified and suppressed" swapped relative to
which camp each applies to (silencing moderate hubs *reduces* moderate-camp posting = vocalization
*amplifies* it; the reverse for near-extreme). Compiled clean, still 13 pages (no page-count effect from
this pass since it was net-neutral in length).

**`CNA2026-3rd.tex`** is a separate, further-hand-edited fork the user is now maintaining in parallel —
it already contained a tightened version of this same Discussion restructure (user's own further edits
on top of the 2nd.tex version), so no changes were needed there for this item.

## 2. NE-E-influx figure: two normalization bugs, both fixed

`scripts/lmp_feedmech_paper_figures.py` generates `figures/NE-E-influx.pdf`, shared by both `2nd.tex`
and `3rd.tex`.

**Bug 1 (fixed first):** figure originally reported *raw counts* of near-extreme-authored posts sitting
in an extreme agent's feed (`feedAuthorClass{1,3}CountMean_{0,4}`, un-normalized). Converted to % by
dividing by `\maxfeed=15`.

**Bug 2 (user caught it: "そんな少ないの？... それでもcomfort rateに変化がおこるわけ？"):** dividing by
`\maxfeed=15` is itself wrong — the extreme camp's *actual realized* feed size (`S_fd`, computed as
`sum(feedAuthorClass{0..4}CountMean_{0,4})`) converges to only ~2–3 posts, nowhere near the 15-slot
capacity. Normalizing by capacity understated the true share several-fold (spot-check: facilitating
cell 0.53%→1.42% become 3.92%→9.40% of actual S_fd; suppressing cell 1.25%→4.16% become 7.77%→20.98%).
Verified this larger scale is self-consistent with the observed `cRateMean` shift (extreme camp,
control vs. M-silent) at the same two cells: -0.62pp / +0.94pp — i.e. the comfort-rate swing and the
NE-share swing are now both properly proportioned to each other, whereas against the capacity-based
denominator the NE share alone (a few %) looked implausibly small to be driving even that modest a
comfort-rate change.

Fixed by normalizing against per-seed, per-cell `S_fd` instead of the fixed `\maxfeed`. New range:
control 2.8%–9.8%, M-silent 10.0%–22.2%, diff 4.3–16.4pp (`lmp_feedmech_paper_figures.py`,
`rates_and_influx()`). Caption/body text in both `2nd.tex` and `3rd.tex` updated to describe this as a
share of the agent's *actual, realized* feed size, explicitly not `\maxfeed`, with the ~2–3-post
context stated inline. `2nd.tex` was updated too (not just `3rd.tex`, the active target) because the
underlying image file is shared — leaving `2nd.tex`'s caption on the old "% of `\maxfeed`" wording would
have mismatched the regenerated image.

**Colorbar tick labels** for this figure now carry `%` (`FuncFormatter`) to match the in-cell
annotations, which already did.

## 3. Network-validation footnote added to Experimental Design (§4, `3rd.tex` only)

User wanted a minimal-footprint way to let a reader verify basic structural properties of the
Holme–Kim network and where the `N_hub=60` follower-selected hub pool sits structurally, given the
paper is already over the 12-page CN2026 budget (13 pages). Chose the cheapest of three proposed
options (footnote with numbers only; small table; appendix + pointer) — a single footnote, no new
figure/table.

Numbers used:
- Mean degree, degree exponent γ=2.267 (analytic, `γ=2+A/m`), clustering coefficient ≈0.14: **reused
  from already-completed calibration** (`docs/report/calibration-sweep-results.md` Stage 1a, `m=15,
  A=4, pt=0.05`, 3-seed mean) — no new simulation needed for these.
- Betweenness-centrality percentile of the top-60 hub pool: **newly computed** (not previously done —
  `structural_9b`'s betweenness computations were on the *converged* (t=40000) network, not the t=0
  generator output the hub-selection ranking actually uses). Ran 3 fresh single-seed, `steps=0,
  log_gexf=true` runs (results deleted after use — throwaway diagnostic, not a headline result) to get
  actual t=0 edge lists, computed `nx.betweenness_centrality` on the directed graph, found the top-60
  (by initial `followerCount`, matching `derive_groups()`'s selection rule) spans roughly the
  30th–100th percentile, mean ≈70th, stable within a few percentage points across all 3 seeds.
- Note: a same-seed sanity check of clustering coefficient via `networkx` (`to_undirected()` +
  `average_clustering`) gave ≈0.33, not matching either this seed's own Java-computed value (0.21,
  `clustering_result_0.csv`) or the documented 3-seed mean (0.1424) — almost certainly a methodological
  mismatch (undirected conversion inflates clustering by adding reciprocal-closure opportunities the
  directed graph doesn't have), not a real discrepancy in the network. Decided **not** to use this ad
  hoc value; cited the already-vetted calibration-log figure (0.1424) instead. Betweenness centrality
  was computed directly on the directed graph (no undirected conversion), so it doesn't have this issue.

Rendered as footnote 3 on the Experimental Design page; compiles clean, page count unchanged (13).

### 3a. Follow-up: 10-seed refresh + metric-selection decision

User asked to (a) redo the betweenness check at 10 seeds instead of 3, (b) clarify exactly what
"percentile" meant in the reported numbers, (c) also compute in-degree (not just betweenness) for the
hub pool, and (d) compute the same set at a converged checkpoint (~step 20000) purely for their own
sanity-check, not necessarily for the paper.

**Percentile clarification, made explicit to the user:** the reported numbers are *rank* percentiles
(fraction of the 1000 nodes with a value ≤ this node's value; decimals come from `rank/1000·100`, not
from any cumulative-mass weighting). Also computed the distinct "mass share" statistic (Σ hub-pool
value / Σ all-node value × 100) since that's the other plausible reading of "how much of the cumulative
total does it explain" — reported both, let the user pick.

**10-seed t=0 results** (fresh seeds 999001–999010, `steps=0, log_gexf=true`, results deleted after
use): in-degree top-60 rank-percentile 93.96–99.90 (mean 96.93), mass share 66.8% — expected, since
hub selection *is* in-degree (`followerCount`) by construction; confirmed exactly (`in-degree ==
followerCount` for all 1000 nodes, zero mismatches, checked directly rather than assumed). Betweenness
top-60 rank-percentile 29.5–99.9 (mean 70.6), mass share 9.75% — the non-trivial, independent structural
fact.

**Converged check (~step 20000, control, $P_u$=0.05, $\VCR$=0.1, 10 of the existing 15 seeds under
`2026-08-14_lmp_feedmech_structural_9b`, reused — no new simulation)**: same fixed hub IDs (via
`derive_groups(seed)`) tracked into the evolved graph. Edge count drops from 15000 (t=0) to ~9430
average (~37% pruned by step 20000 under this cell's `p_u`). Hub-pool in-degree percentile mean drops
only slightly (96.93→93.44) but its *minimum* drops more (93.96→49.75). Betweenness percentile mean
drops modestly (70.6→66.3) but its minimum collapses to **0.0** in several seeds — i.e., a subset of
hub agents lose all shortest-path mediating role once the network has rewired, even though they remain
high in-degree. Betweenness mass share actually *rises* slightly (9.75%→14.2%), consistent with a
"some hubs drop out, survivors concentrate more of the remaining betweenness" pattern. **Not written
into the paper** — user explicitly scoped this as their own verification, and the footnote's own
"$t=0$, pre-dynamics" framing means a converged-state number would need its own condition/step scoping
to state correctly, which conflicts with the minimal-footprint goal.

**Metric-selection decision (user: "これ以外の指標も含めてどの情報を使うのが、最低限かつ、ハブ集合の性質を
示せるか決めよう")**: kept exactly the original two-clause footnote content (network-generator
stats, reused from existing calibration; hub-pool betweenness percentile range+mean, t=0 only),
refreshed to the 10-seed numbers. Explicitly decided **not** to add: in-degree percentile for the hub
pool (tautological — it's the selection criterion restated, not new information), mass-share (redundant
second phrasing of the same betweenness fact, less standard/intuitive than percentile for a reader),
or any converged-state number (out of paper scope per above). Considered but declined (user's explicit
call) a one-clause contrast noting in-degree is trivially ~97th percentile "by construction" against
betweenness's non-trivial spread, to preempt a "isn't this obvious" objection — judged not worth the
extra line at this page budget.
