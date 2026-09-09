# 2026-07-14 — bc clamp-bound robustness check

## Question

User observed that the dynamic bounded-confidence (`bc`) distribution across agents piles up
almost entirely at the two clamp values, `Const.MINIMUM_BC=0.2` and `Const.BOUNDED_CONFIDENCE=1.0`
(`Agent.java` `updateMyself()`). Is this a bug in the BC update rule?

## Analytical answer (before running anything)

No — it is the expected consequence of the update rule as parameterized:

```java
if (Math.abs(post.getPostOpinion() - this.opinion) > this.bc) {
    this.bc *= p.bcDecRate();   // uncomfortable contact
} else {
    this.bc *= p.bcIncRate();   // comfortable contact
}
```

This is a **multiplicative ratchet with self-reinforcing feedback in both directions**: a
narrower `bc` makes future contact more likely to register as "uncomfortable" (narrower
tolerance window), which shrinks `bc` further; a wider `bc` makes future contact more likely
"comfortable", which grows `bc` further. There is no interior restoring force. With
`bcIncRate=1.001` / `bcDecRate=0.99` (current defaults), the per-contact log-drift is zero only
when the comfortable-contact fraction ≈ `ln(bcDecRate)/(ln(bcDecRate)-ln(bcIncRate))` ≈ 90.9%. Below
that fraction, `bc` decays without bound; above it, `bc` grows without bound. The clamp bounds
therefore aren't producing the bimodality — they're truncating two divergent (0-ward / ∞-ward)
attractors into a finite range.

## Methodological question raised by the user

If the two peaks are genuine emergent bistability rather than a clamp artifact, they should
appear (with near-zero density in between) **regardless of where the clamp walls are placed**,
not just track wherever the walls happen to be.

## Experiment

Added `bc_floor` / `bc_ceiling` as sweepable `ExperimentConfig` fields (previously
`Const.MINIMUM_BC` / `Const.BOUNDED_CONFIDENCE`, static-final with no CLI path — moved per this
repo's own hard invariant that runtime-tunable values live in `ExperimentConfig`, never `Const`).
Kept `Const.VOCAL_COMFORT_RADIUS` (fixed at the old 0.2) as a **separate** constant for the R5/D4
perceptual comfort radius (`Agent.java` `withinComfort`, vocal-minority mechanism) — it must not
move with the bc-bound sweep, or an intolerant extremist's vocality would silence itself as soon
as its `bc` collapses, defeating that mechanism's purpose.

Added `bc` to the per-agent final-state CSV (`writeAgentSnapshot`,
`results/run_*/degrees/agent_snapshot_final.csv`) for post-hoc histogram analysis (previously not
logged anywhere).

**First attempt was confounded.** `bc`'s initial value was hardwired to `bcCeiling`
(`Agent.java:76`, old `this.bc = Const.BOUNDED_CONFIDENCE`). Sweeping the ceiling therefore also
swept the day-0 tolerance window and hence the day-0 comfort probability — at `bc_ceiling=1.4` or
higher, the initial window was already wide enough that ~100% of contacts registered comfortable
from step 0, so 100% of agents (900/900 across 3 seeds) sat exactly at the ceiling the whole run
with zero variance. This wasn't evidence of anything — it was a different confound. Fixed by
adding a third field, `bc_init` (default 1.0, decoupled from `bc_ceiling`), so a wall-location
sweep can hold the starting point fixed.

**Corrected sweep** (n=300, steps=15000, `bc_init=1.0` fixed, network/feed defaults unchanged,
3 seeds — 500/501/502 — per condition):

| condition | floor | ceiling | % at floor | % at ceiling | % interior |
|---|---|---|---|---|---|
| baseline | 0.2 | 1.0 | 21.1% | 78.6% | 0.3% |
| relax-D | 0.05 | 1.6 | 1.9% | 98.1% | 0.0% |
| relax-C | 0.01 | 3.0 | 1.9% | 98.1% | 0.0% |

## Conclusion

1. **Bimodality is not a clamp artifact.** Interior mass stays ≈0% across wall placements
   spanning a 30x floor range and a 3x ceiling range. This is consistent with the "two divergent
   attractors truncated by a box constraint" characterization above, not with an emergent interior
   equilibrium being masked by the walls.
2. **The floor/ceiling split *ratio* is not wall-invariant**, and shifts in an explicable
   direction: widening the ceiling lets agents that escape the initial danger zone climb further
   before any single uncomfortable event can pull them back under the ~90.9% breakeven fraction,
   converting some baseline "capped-then-fell" trajectories into "climbed safely away"
   trajectories — hence fewer end up at the floor as the ceiling relaxes (21.1% → 1.9%).
3. **Implication for the paper**: if the specific split fraction (e.g. "~21% of the population
   becomes closed-minded") is ever reported as a substantive finding, it must be flagged as a
   function of the chosen `(bc_floor, bc_ceiling, bcIncRate, bcDecRate)` quadruple, not a
   model-intrinsic constant. The *qualitative* bimodal-collapse phenomenon is robust; the
   *quantitative* split is not.

## Code changes

- `src/experiment/ExperimentConfig.java`: added `bcFloor` (CLI `bc_floor`, default 0.2),
  `bcCeiling` (`bc_ceiling`, default 1.0), `bcInit` (`bc_init`, default 1.0); tagged in `tag()`
  when non-default.
- `src/experiment/SimParams.java`: threaded the three fields through.
- `src/constants/Const.java`: removed `BOUNDED_CONFIDENCE` / `MINIMUM_BC`; added
  `VOCAL_COMFORT_RADIUS` (fixed 0.2, R5/D4 comfort radius only).
- `src/agent/Agent.java`: `bc` init uses `p.bcInit()`; clamp uses `p.bcFloor()`/`p.bcCeiling()`;
  `withinComfort` uses `Const.VOCAL_COMFORT_RADIUS`.
- `src/writer/Writer.java`: `writeAgentSnapshot` now includes a `bc` column.

No change to default behavior (`bc_floor=0.2`, `bc_ceiling=1.0`, `bc_init=1.0` reproduce the prior
hardcoded values exactly; `tag()` omits them when at defaults, so existing result-folder naming is
unaffected).
