# 2026-07-10 — `accessProb` promoted from `Const` to `ExperimentConfig`/CLI

**Decision:** `Const.ACCESS_PROB` (a hardcoded `0.1`) removed; replaced by
`ExperimentConfig.accessProb` (same default `0.1`), CLI key `access_prob`, threaded through
`SimParams` and set on each `Agent` at construction (`Agent.java`: `this.accessProb =
p.accessProb();`, mirroring how `postProb`/`repostProb` are already seeded from `SimParams`).
Tagged in `tag()` as `_ap-<value>` (4 d.p., same precision as `p_u`) only when non-default, so
existing folder names are unaffected.

**Why this knob specifically:** raised during a dashboard conversation about rescaling the
model's overall time axis. Code walk (`OpinionDynamics.java`'s per-agent loop) confirmed
`accessProb` is not just another rate parameter — it gates an agent's **entire** per-step action
set behind one Bernoulli draw (`if (nextDouble() > accessProb) continue;`), including
`repost`/`follow`/`unfollow`/`post` **and** `updateMyself()` (the FJ/bounded-confidence opinion
update itself). Nothing else in the model has that property: every other rate knob
(`repost_prob`, `follow_prob`, `bc_dec`, `bc_inc`, ...) governs one mechanism conditional on the
agent already being active this step. `accessProb` is therefore the single principled place to
put a global timescale rescaling, rather than co-scaling every mechanism's rate knob by hand.
Previously this couldn't be swept at all — no CLI key existed, and the `Const.java` docstring's
own hard invariant ("the moment a value becomes runtime-tunable, it must move to
`ExperimentConfig` entirely ... and be deleted from here") flags exactly this kind of
Const-that-should-be-a-knob.

**Caveat carried over to the CLI (not resolved by this change):** raising `access_prob` increases
the *density* of activity per absolute step, but does **not** itself shrink `steps`, and all
per-step instrumentation (`results.csv` — one row per absolute step; modularity/GEXF snapshots at
`step % 5000`) is anchored to absolute step count, not to active-tick count. Compressing the
visible trajectory (fewer steps to reach the same settled state) requires lowering `steps`
alongside raising `access_prob`, and re-checking that the fixed 5000-step snapshot cadence still
lands at meaningful fractions of the shorter run. Not attempted here — this pass only wires the
knob up; no sweep or recalibration against it has been run yet.

**Also fixed in passing:** `test.ModelTests`'s `testSimParamsSentinels` asserted
`bcDecRate() == 0.99`, stale since `bcDecRate`'s default moved to `0.999` (commit after `479e59a`)
without updating the test — unrelated to this change, caught because it was the one `ModelTests`
failure after this edit. Updated the assertion to `0.999`.

**Verified:** recompile clean; `ModelTests` all pass; smoke run
(`seed=999 n=100 steps=200 access_prob=0.5 log_gexf=false`) completes with no errors and produces
`results/run_999_..._ap-0.5000/`, confirming the CLI key, `SimParams` wiring, and `tag()` all
round-trip correctly.

**Not done:** no sweep over `access_prob` itself yet; no re-derivation of what `steps` value would
be needed to hold the settled-state trajectory shape constant under a rescaled `access_prob`.
