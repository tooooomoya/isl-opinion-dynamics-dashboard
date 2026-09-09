# 2026-07-09 — OAT calibration/robustness sweep: method, literature anchors, results, conclusions

**Purpose of this file:** a self-contained record of the one-at-a-time (OAT) sweep run to answer
"which parameters actually matter" before the Step-3 freeze — written so it can be reproduced later
in a notebook (e.g. for an availability/reproducibility package) without re-deriving context from
the rest of `docs/report/`. Supersedes nothing; extends
`docs/report/2026-07-08-validation-gate-pilot.md`'s calibration discussion with actual run results.

## Scope decision (recorded before running anything)

Three-tier triage agreed this session:
- **Tier A** (`p_u`, network type, hub scale-vs-position) — the Step-3 *experimental* factors
  (research-direction.md's Step-0 DAG). Deliberately **not** touched here — "the model needs to
  stand on its own as credible first," before spending runs on the actual treatment variables.
- **Tier B** — light calibration check on parameters with partial literature anchors:
  `repost_prob`, `bc_inc` (asymmetric tolerance recovery magnitude), flat stubbornness, `sbm_pout`.
- **Tier C** — the velocity-primary "For You" recommender (`alpha`/`hop`), checked against a real
  empirical target (Kwak et al. 2010's Twitter follower-distribution exponent) rather than picked
  arbitrarily, and checked for whether it actually grows the moderate hub now that `MU_PARAM` was
  removed (rationale for removal: hub growth should come from the recommender instead).
- **Tier D** — parameters believed to be pure "scale" knobs with no correct external value
  (`feed_capacity`, `follow_prob`, `comfort_pp`, `max_pp`); swept **to confirm-or-refute inertness**,
  not to find a "right" value.

## Method

- **Design:** one-at-a-time (OAT). Baseline (current defaults) + one changed parameter per cell;
  not full-factorial (infeasible with ~18 candidate values across tiers). OAT answers "does this
  knob move the outcome at all" — sufficient to triage, not to characterize interactions.
- **Scale:** `n=300, steps=15000` — deliberately lighter than the `n=500, steps=30000`
  validation-gate pilots in `2026-07-08-validation-gate-pilot.md`, since this is a screening pass,
  not a precision run. Fixed background: `network=dcsbm, n_mod=1, extreme=sym, channel=both`.
- **Seeds:** `{200, 201, 202}` (3 per cell) — chosen to avoid collision with the validation-gate
  pilots' `100-104` range.
- **19 cells** (baseline + 18): `run_oat_sweep.sh`. **57 runs total, all completed with 0 assertion
  errors** (after the bug fixes below).
- **Readout:** the Step-2 gate battery — `opinionAssortativity`, `crossCuttingFraction`,
  `interactionCrossCuttingFraction`, `signModularity` (population-level structural separation,
  excludes hub-touching edges by design — see `2026-07-08-validation-gate-pilot.md`'s first entry),
  `hub_cross_camp_fraction`/`n_hub_mediated_cascades` (hub-attributable bridging, using the
  event-time `relayerOpinion` fix, not the final-snapshot proxy). For Tier-C `alpha` cells only:
  power-law fit (`powerlaw` package) of the final in-degree distribution, and moderate-hub follower
  growth (`followers_final − followers_t0`).
- **Analysis code:** `scripts/oat_sweep_analysis.py` (reuses `scripts/validation_gate_pilot_analysis.py`'s
  gate functions). Raw per-run output: `docs/report/2026-07-09-oat-sweep-results.csv`.

## Literature anchors used (per parameter)

| Parameter | Baseline | Alt. values | Anchor | What the anchor licenses |
|---|---|---|---|---|
| `repost_prob` | 0.25 | 0.01, 0.10 | Meng et al. 2025 (PNAS) ψ≈10⁻³ population avg.; Sasahara/Qiu (0.25, now known mechanically inflated — see prior entry) | floor/ceiling bracket, not a point estimate |
| `bc_inc` | 0.0 | 0.001, 0.005 | Baumeister 2001 / Rozin & Royzman 2001 | direction only (decline ≫ recovery); no magnitude |
| stubbornness (flat) | 0.8 | 0.6, 0.95 | Das et al. 2014 | qualitative only (stable per-user trait); no numeric anchor found |
| `sbm_pout` | 0.002 | 0.005, 0.01 | Bakshy/Messing/Adamic 2015; Boutyline & Willer 2017 | calibration *target* (~20-25% cross-cutting exposure), not a direct value |
| `alpha` (feedAlgoShare) | 0.0 | 0.3, 0.6 | Kwak et al. 2010 (γ≈2.276, same anchor as `sbm_gamma`) | target for the *emergent* final degree exponent |
| `feed_capacity`, `follow_prob`, `comfort_pp`, `max_pp` | 10, 0.1, 1.1, 0.5 | ±40-100% | none — pure scale, being tested for inertness | — |

## Three implementation bugs caught during this pass (all fixed before trusting results)

1. **`sbm_pin`/`sbm_pout`/`sbm_k`/`sbm_gamma`/`sbm_deg` were never tagged** in `ExperimentConfig.tag()`
   → two cells differing only in `sbm_pout` at the same seed produced identical folder names → the
   second silently hit `run.sh`'s R26 "abort if exists" guard. Fixed: all five now tagged when
   non-default.
2. **macOS's stock bash (3.2, pre-GPLv3)**: `"${array[@]}"` on an *empty* array throws "unbound
   variable" under `set -u` (killed the `baseline` cell silently, 0/3 ran, loop continued regardless);
   `wait -n` doesn't exist pre-4.3. Fixed: branch on `[ ${#arr[@]} -gt 0 ]` before expanding; replaced
   `wait -n` with a `sleep 1` polling loop.
3. **`Agent`'s constructor had a second, independent hardcoded feed-capacity literal**
   (`setNumOfPosts(10)`), never updated when `feed_capacity` was migrated to `SimParams` — `postCash`'s
   real capacity stayed pinned at 10 regardless of the CLI value, so `feed_capacity=20` (above the
   hidden 10-cap) silently had zero effect (caught because its aggregated metrics were bit-identical
   to baseline to 6 decimal places — too exact to be a real null result) while `feed_capacity=5`
   (below the hidden cap) happened to still work correctly. Fixed: `setNumOfPosts(p.feedCapacity())`;
   re-ran the 3 affected seeds after the fix.

**Lesson, stated plainly for reproduction:** a clean exit code / "ALL ... COMPLETE" message is not
sufficient evidence a sweep produced valid data. All three bugs were caught by checking logs for
`ABORT` markers and by noticing a suspiciously *exact* null result, not by the tooling failing loudly.

## Results and conclusions, by tier

### Tier B — not inert; some effects are large

- **`repost_prob`**: both 0.01 and 0.10 move `opinionAssortativity`/`crossCuttingFraction` clearly
  away from baseline, **and both show zero hub-mediated cascades** (vs. baseline's 6) — at
  `n=300/steps=15000`, hub-mediated bridging did not occur at all outside the current default rate.
  **Conclusion: load-bearing, confirms the calibration concern from the prior entry was real; do not
  treat as a free parameter.** Needs a longer run or more seeds to see bridging emerge at the lower
  rates at all before picking a final value.
- **`bc_inc`**: 0.001 produced a large jump in `interactionCrossCuttingFraction` (0.337 vs. 0.269)
  **and a 25x increase in hub-mediated cascades** (153 vs. 6) — consistent with the mechanistic
  story (even slight tolerance recovery lets a hub's audience relationship survive instead of
  permanently souring, sustaining more relay opportunities). **0.005, however, showed similarly
  elevated `interactionCrossCuttingFraction` but zero hub-mediated cascades** — inconsistent with a
  simple monotonic story. **Conclusion: `bc_inc` is clearly load-bearing (large, real effect), but
  3 seeds cannot resolve the dose-response shape — more seeds needed before picking a value, not a
  "settled" result.**
- **Stubbornness**: 0.6 (more assimilative) → 0 hub-mediated cascades; 0.95 (near-total resistance)
  → 0.519 cross-camp fraction, 17.7 cascades (≈3x baseline's 6). **Conclusion: also load-bearing**,
  plausible mechanism (higher stubbornness keeps opinions — and therefore "camp" — stable long
  enough for sustained bridging patterns to be measurable at all).
- **`sbm_pout`**: 0.01 (5x baseline) → 0.392 cross-camp fraction, 33.3 cascades (≈5.5x baseline).
  **Conclusion: real, substantial lever — supports treating it as a genuine calibration target
  (per the Bakshy/Boutyline-Willer anchor) rather than a free structural choice**; 0.01 moves
  meaningfully toward more realistic cross-cutting exposure. Calibration search not yet completed
  (would need to check the resulting *initial* `crossCuttingFraction` against the ~20-25% target
  directly).

### Tier C — recommender: degree-check retracted as confounded by n=300; hub-growth concern stands

- **Degree-distribution target check — CORRECTED, do not trust the original framing below.**
  Initial reading: final in-degree power-law exponent fits to **α≈2.86 (alpha=0.3) and α≈2.93
  (alpha=0.6)**, both higher (thinner-tailed) than the `sbm_gamma≈2.3`/Kwak et al. `γ≈2.276` target,
  read as "the recommender flattens the tail." **This was wrong** — checked baseline's (alpha=0,
  no recommender) own `t0` fit directly and found it *already* sits at α≈2.50-2.85 (mean ≈2.64)
  **before any dynamics run at all**, with max in-degree only 70-75. This is the finite-size law
  already named in `2026-07-07-model-structure-review.md` (`k_max ~ n^{1/(γ-1)}`, ≈200 at n=1000
  but only ≈80 at `n=300`) — **`n=300` (this OAT screen's scale) is simply too small for the DC-SBM
  generator to express the intended heavy tail in the first place**, independent of `alpha`.
  Comparing the alpha-on final exponent against the `γ≈2.3` target was comparing against a target
  the *baseline* network couldn't hit either. **Residual finding, still worth noting:** baseline's
  own final exponent is wildly seed-variable (1.795, 2.365, 2.953 across 3 seeds — no consistent
  drift direction), while `alpha=0.3`/`0.6`'s final exponents are tightly clustered (2.86±0.03,
  2.93±0.05) — the recommender may make the outcome more *deterministic* across seeds rather than
  systematically flatter. **This whole check needs to be re-run at `n=1000` (production scale)
  before drawing any conclusion about the recommender's effect on degree-distribution shape.**
- **Moderate hub growth — the important negative finding:** growth (`followers_final − followers_t0`)
  is **-43.7 (alpha=0.3) and -48.3 (alpha=0.6), *more negative* than baseline's -28.0.** The
  recommender being on made the moderate hub **lose more followers**, not fewer, at these `alpha`
  values and this scale. **This does not support the stated rationale for removing `MU_PARAM`**
  (`docs/report/2026-07-08-validation-gate-pilot.md`'s "MU_PARAM removed" entry: "the mechanism's
  original purpose — explaining hub growth — is better served by the velocity-primary recommender").
  At `alpha∈{0.3, 0.6}`, `hop=3` (default), n=300/steps=15000, that channel is **not** demonstrating
  hub growth either. **Open question, not yet resolved: does growth appear at higher `alpha`, a
  different `hop`, a longer run, or does the recommender genuinely not rescue hub growth at all in
  this model** — if the latter, the `MU_PARAM` removal decision may need revisiting, or a different
  growth channel identified.

### Tier D — NOT confirmed inert; only one candidate looks close

The premise going in was "sweep to confirm these don't matter." Result: **most of them do move the
gate metrics**, at least at this OAT-screening sample size (3 seeds):

- **`feed_capacity`**: 5 → real shift (assortativity 0.931 vs. 0.965); 20 (after the bugfix above) →
  real shift (`interactionCrossCuttingFraction` 0.215 vs. 0.269, cross-camp fraction 1.0 but from
  only ~1 cascade — too sparse to trust the ratio). **Not inert.**
- **`follow_prob`**: the biggest surprise. 0.05 → 133.7 hub-mediated cascades; 0.2 → 113 — both
  **far above baseline's 6.** Follow-graph formation rate strongly shapes how much bridging is even
  observable. **Clearly not inert — arguably the most load-bearing "Tier D" parameter tested.**
- **`comfort_pp`**: 1.05 and 1.2 both show real movement (e.g. `crossCuttingFraction` 0.126 at 1.2 vs.
  baseline 0.072), though hub-cascade counts are small (2-4) and noisy. **Probably not inert, but
  weaker evidence than `follow_prob`.**
- **`max_pp`**: 0.8 (higher ceiling) is close to baseline across every metric (`interactionCrossCuttingFraction`
  0.247 vs. 0.269; cross-camp fraction 0.077/6 cascades — nearly identical to baseline's own 0.077/6).
  0.3 (lower ceiling) shows a smaller cascade count (5 vs. 6) but is otherwise close too.
  **This is the one Tier-D parameter that looks genuinely close to inert** — plausibly because
  `postProb` rarely approaches its ceiling in practice, so raising/lowering the ceiling doesn't bind.

**Honest caveat for all of the above:** 3 seeds per cell is a screening sample, not a precision
estimate — several of these readings (especially small hub-cascade counts like 2-6) are consistent
with substantial sampling noise. Treat "not inert" conclusions as "worth a bigger sweep before
declaring frozen," and "looks inert" (`max_pp`) as "closest to a free pass," not as final.

## Follow-up: 10-seed re-check of the two open questions (2026-07-09, same day)

Extended `baseline`, `bcinc-0001`, `bcinc-0005`, `alpha-03`, `alpha-06` from 3 to 10 seeds
(`run_oat_extra_seeds.sh`, seeds 203-209 added to 200-202; all 35 new runs clean, 0 errors) to
check whether the two flagged findings above were real effects or 3-seed noise. They resolved in
opposite directions:

- **`bc_inc` dose-response — does NOT hold up; retract the "load-bearing, large effect" reading.**
  Per-seed `n_hub_mediated_cascades` for `bcinc-0001`: `0, 459, 0, 0, 296, 9, 0, 104, 29, 0` — mean
  89.7, **std 159.7 (larger than the mean)**. `bcinc-0005`: mean 13.6, std 36.2. `baseline`: mean
  24.8, std 34.9. The original "0.001 → 25x more cascades" reading from 3 seeds was driven by one
  outlier (seed 201's 459); with 10 seeds, `bcinc-0001`/`bcinc-0005`/`baseline` are not
  distinguishable from each other given the variance. **This is not a sample-size problem that a
  few more seeds fixes — hub-mediated cascade count is a heavy-tailed, rare-event-dominated
  statistic at this scale, and the mean is the wrong summary for it.** Before this parameter can be
  calibrated at all, switch to a variance-robust summary (median, or P(cascade count > threshold))
  or accept that this metric needs a much larger run to characterize its dose-response.
- **`alpha`/hub-growth — CONFIRMED, and more clearly than before.** Moderate-hub growth: `baseline`
  mean **-21.0 (std 23.0)**, `alpha-03` mean **-44.7 (std 5.8)**, `alpha-06` mean **-44.9 (std 6.9)**.
  The recommender-on cells are not just lower on average, they are **far tighter** (std ~6 vs. ~23) —
  consistent, low-variance evidence that turning the recommender on reliably makes the moderate hub
  lose more followers, not fewer. Standard errors at n=10 (baseline ≈±7.3, alpha-03 ≈±1.8) do not
  overlap. **This is a robust finding, not 3-seed noise: the recommender does not rescue moderate-hub
  growth at `alpha∈{0.3,0.6}, hop=3` — if anything it actively hurts it.**

## Bottom-line recommendation

1. **Tier D is not a free pass.** Only `max_pp` looks close to inert; `feed_capacity`, `follow_prob`,
   and `comfort_pp` all moved gate metrics non-trivially. These need to move into the "worth a
   proper calibration/robustness pass" bucket, not stay as arbitrarily-fixed scale constants.
2. **The `alpha`/hub-growth finding is confirmed at 10 seeds and is the most urgent open issue.**
   It directly contradicts the stated rationale for removing `MU_PARAM`
   (`docs/report/2026-07-08-validation-gate-pilot.md`: "the mechanism's original purpose —
   explaining hub growth — is better served by the velocity-primary recommender"). At the settings
   tested, that channel does not deliver hub growth — it makes it reliably worse. Needs resolution
   before Step-3 freeze: test a wider `alpha`/`hop` range, or identify a different growth channel,
   or reconsider the `MU_PARAM` removal.
3. **`bc_inc`'s dose-response remains unresolved, but the fix is not "more seeds" — it's a better
   metric.** Hub-mediated cascade count is heavy-tailed/rare-event-dominated at `n=300/steps=15000`;
   report median or an exceedance probability instead of the mean, or move this specific check to
   the full validation-gate scale, before attempting to pick a value.
4. Everything else identified as "load-bearing" in the original OAT pass (`repost_prob`,
   stubbornness, `sbm_pout`, `follow_prob`) still stands as worth a proper post-Step-3 robustness
   pass — but note the `bc_inc` lesson: check the variance/distribution shape of any metric before
   trusting a small-sample mean comparison, not just its point estimate.
5. **`n=300` is too small for at least one diagnostic (the degree-distribution power-law check) —
   check before reusing this scale for anything else.** Confirmed the DC-SBM finite-size law
   (`k_max ~ n^{1/(γ-1)}`) already binds at `n=300` (max in-degree ≈70-75 vs. the model-structure-
   review's own ≈200 at `n=1000`), so the *initial* network's own fitted exponent (≈2.5-2.85) sits
   above the `γ≈2.3` target before any dynamics run — this OAT screen's scale cannot be used to
   validate anything that depends on the network actually being heavy-tailed enough. Re-run the
   Tier-C degree-distribution check specifically at `n=1000` before trusting either the original or
   corrected reading above.

---

## Root-cause fix for the alpha/hub-growth finding: velocity formula was follower-normalized

Traced *why* the recommender hurt moderate-hub growth (confirmed robust at 10 seeds above) to
`AdminOptim.velocityScore`/`windowedVelocityScore`: both divided by `(followers+1)`, a deliberate
"anti-rich-get-richer" design decided 2026-06-23 (`research-direction.md` §3 item 6: "Absolute
count = rich-get-richer... relative = the pro-mid-size-hub variant"). Consequence not anticipated
at the time: the moderate hub (mean 68.5 initial followers at `n=300`, vs. a typical small account's
single digits) had its own algorithmic score suppressed ~7-14x relative to small accounts for the
*same* raw repost count — the recommender was actively working against the specific mid-large hub
this study is about, while diverting feed slots away from its organic (chronological) reach.

**Decision: removed the `/(followers+1)` normalization, superseding the 2026-06-23 decision.**
Rationale: real engagement-ranked feeds (the actual referent for this mechanism) do not divide by
poster reach — small accounts occasionally break through because their *raw* engagement is large
relative to peers, not because an algorithm discounts large accounts. `velocityScore` is now simply
`receivedReposts / (age+1)` (and the windowed variant analogously), opinion-blind as before.
**Known accepted tradeoff going in:** this also removes the throttle on the *extreme* hubs (also
large accounts), risking further entrenching them, not just helping the moderate one.

**Re-ran `alpha-03`/`alpha-06` at 10 seeds (`baseline` unaffected — it never calls `rankByVelocity`
when `alpha=0`, reused as-is). Results** (`docs/report/2026-07-09-alpha-recheck-results.csv`):

| | moderate hub growth (before fix) | moderate hub growth (after fix) |
|---|---|---|
| baseline | -21.0 ± 23.0 | -21.0 ± 23.0 (unaffected) |
| alpha=0.3 | -44.7 ± 5.8 | **-22.8 ± 12.4** — statistically indistinguishable from baseline |
| alpha=0.6 | -44.9 ± 6.9 | **-34.1 ± 7.7** — improved by roughly half, still somewhat worse than baseline |

**The feared tradeoff did not materialize:** extreme-hub follower growth is essentially identical
across `baseline`/`alpha-03`/`alpha-06` both before and after this fix (≈-69 to -72 in all three
cells) — removing the normalization did not additionally entrench the extreme hubs.
`interactionCrossCuttingFraction` rose with the recommender on (0.371/0.388 vs. baseline 0.281),
a sensible effect of network-wide (not just-follow-graph) content injection.

**Conclusion: the root cause was found and fixed, not merely patched.** `alpha=0.3` no longer shows
a hub-growth penalty at all. `alpha=0.6` still shows a smaller residual penalty (-34.1 vs. -21.0,
≈1.7 combined-SE apart — suggestive, not fully conclusive at n=10) worth another look before the
Step-3 freeze, but the original, larger finding ("the recommender does not support and may
actively work against the stated `MU_PARAM`-removal rationale") is substantially resolved. Verified:
recompile clean, `ModelTests` 28/28 pass, 20/20 re-run seeds clean (0 assertion errors).

## Follow-up: the *right* metric was the whole-network heavy tail, not one hub's follower count

Correction raised immediately after the above: a single hub's follower-count trajectory is a
noisy, narrow proxy (extreme-hub follower loss is *expected* — that's `P_u`/conduit-immunity
sorting working as designed, not a problem to fix). **The metric that actually matters for the
Type-1/Type-2 framing is whether the recommender collapses or preserves the whole-network degree
distribution's heavy tail.** Re-ran at **`n=1000`** (production scale — `n=300`'s finite-size
truncation, documented earlier in this file, made any degree-distribution reading there
untrustworthy): `baseline`/`alpha=0.3`/`alpha=0.6`, 5 seeds each
(`docs/report/2026-07-09-heavy-tail-n1000-results.csv`).

|  | power-law exponent (final) | Gini (final) | max in-degree (final) |
|---|---|---|---|
| t0 (all cells, identical) | 2.385 | 0.451 | 228.8 |
| `baseline` | 2.871 (tail *shortens*) | 0.551 | 192.2 |
| `alpha=0.3` | **1.983** (tail *lengthens*) | **0.694** | 314.6 |
| `alpha=0.6` | **1.512** (tail lengthens further) | **0.755** | 248.0 |

**Reads in the opposite direction from the original concern.** The worry was "does the
recommender flatten the tail (degree differences disappear)" — instead, **`baseline` (no
recommender) is the one drifting toward a shorter tail** (exponent 2.385→2.871) while turning the
recommender on makes the network *more* concentrated (exponent drops to 1.5-2.0, Gini rises to
0.69-0.76). Checked against a real benchmark: real Twitter follower-distribution Gini is
reportedly **≈0.8**, so **both conditions are still less concentrated than reality, and `alpha>0`
moves *toward* the realistic regime, not away from it.** Conclusion: this is not a regression —
accept the un-normalized velocity formula as correctly reasoned, and note the whole-network
degree-Gini check (not a single hub's follower count) as the metric to use for this question going
forward.

**No broader OAT-sweep re-run needed.** The velocity-formula change only executes inside
`AdminOptim.rankByVelocity`, which is only ever called when `feedAlgoShare (alpha) > 0`
(`params.feedAlgoShare() > 0.0 ? admin.rankByVelocity(step) : null`). Every other OAT cell
(`repostprob-*`, `bcinc-*`, `stub-*`, `sbmpout-*`, `feedcap-*`, `followprob-*`, `comfortpp-*`,
`maxpp-*`, and `baseline` itself) runs at `alpha=0` and never touches this code path — their
results in `docs/report/2026-07-09-oat-sweep-results.csv` are unaffected and stand as recorded.
Only `alpha-03`/`alpha-06` needed the re-run already done above.
