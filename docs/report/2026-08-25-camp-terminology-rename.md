# 2026-08-25 — Camp terminology rename: moderate/near-extreme/extreme -> neutral/moderate/extreme

## Decision

The 3-way opinion-camp split (`|O|<0.2` / `0.2<=|O|<0.6` / `|O|>=0.6`, defined in
`tex/CNA2026/CNA2026-5th.tex` L294-300 and mirrored throughout the code as the 5-bin ->
3-camp collapse) is renamed from `moderate` / `near-extreme` / `extreme` to
`neutral` / `moderate` / `extreme`.

**Rationale:** "near-extreme" reads as "adjacent to the extreme camp, count it with them," when
structurally it is the bulk/majority band (0.2-0.6), not a near-extreme fringe. Meanwhile
"moderate" was reserved for the narrow near-zero band, which conflicts with how CSS/political-
science literature normally uses "moderate" (a mild lean, not "no lean"). `neutral/moderate/
extreme` matches that convention: near-zero = no lean, mid-range = mild lean, tail = strong lean.

**Consequence for the paper's central object:** the paper's title concept, the intervention fixed
at `O=0.0` — previously "moderate hub" — is renamed **"neutral hub"** throughout (title, abstract,
body), since it sits exactly in the renamed near-zero/neutral band and "moderate" now means the
*other* (mid-range) camp. Leaving it as "moderate hub" while the camp scheme changed would have
created the exact same confusion this rename exists to fix, just at the level of the paper's title.

## Naming map

| Old | New |
|---|---|
| `moderate` camp (`\|O\|<0.2`) | `neutral` camp |
| `near-extreme` camp (`0.2<=\|O\|<0.6`, or `0.2-0.8` in the band08 probe) | `moderate` camp |
| `extreme` camp | `extreme` camp (unchanged) |
| "moderate hub(s)" | "neutral hub(s)" |
| `moderateBandHalfWidth` / CLI `moderate_band` | `neutralBandHalfWidth` / CLI `neutral_band` |
| `Analysis.isModerate()` | `Analysis.isNeutral()` |
| `nModerate` / CLI `n_mod` | `nNeutral` / CLI `n_neutral` |
| `pinModerateIds` / CLI `pin_moderate_ids` | `pinNeutralIds` / CLI `pin_neutral_ids` |
| `StepStats.feedModCountSum` / CSV `feedModCountMean_*` | `feedNeutCountSum` / `feedNeutCountMean_*` |
| `Const.band08Of` bin labels (0=extreme/1=near-extreme/2=moderate) | 0=extreme/1=moderate/2=neutral |
| CSV `cRateMean08_ext/near/mod`, `popCount08_ext/near/mod` | `..._ext/mod/neu` |
| Figure `figures/NE-E-influx.pdf`, label `NE-E-influx` | `figures/mod-extreme-influx.pdf`, label `mod-extreme-influx` |

## Scope

**In scope (renamed):**
- `tex/CNA2026/CNA2026-5th.tex` (the only active draft — `-1st` through `-4th` are frozen
  past-submission snapshots, left untouched).
- Live Java source: `Const`, `Analysis`, `OpinionDynamics`, `StepStats`, `AdminOptim`, `Agent`,
  `Writer`, `InterventionSetup`, `SimParams`, `ExperimentConfig`, `AssertionCheck`, `NetworkFactory`,
  `ModelTests` — field names, CLI flag strings, `tag()` folder-identity suffixes, comments.
- `dashboard/analysis.py` (`MODERATE_BAND_HALF_WIDTH` -> `NEUTRAL_BAND_HALF_WIDTH`).
- `scripts/lmp_band08_probe.py`, `scripts/lmp_uniform_probe.py` (both created today, uncommitted).
- 32 currently-active `scripts/*.py`/`*.sh` that pass the renamed CLI flags (`pin_moderate_ids`,
  `moderate_band`, `n_mod`) — flag tokens updated so they remain runnable, plus the literal phrase
  "moderate hub(s)" -> "neutral hub(s)" where it appeared as narrative/print text.
- `scripts/lmp_feedmech_paper_figures.py` — camp labels, `NE_COLS` -> `MOD_COLS`, and the output
  figure renamed `NE-E-influx.pdf` -> `mod-extreme-influx.pdf`. Regenerated all three figures
  (`outcome-heatmap.pdf`, `mod-extreme-influx.pdf`, `control-minus-msilent.pdf`) from the existing
  `results/2026-08-14_lmp_feedmech_structural_9b/` grid — no new simulation, values unchanged,
  labels only. Paper recompiled clean (`latexmk`, 12 pages, no undefined-reference warnings).

**Explicitly out of scope (left as-is, intentionally):**
- The 17 historical script filenames containing "moderate" (`delayed_moderate_pilot_*.py`,
  `moderate_hub_5tier_removehub.py`, `cascade_moderate_tier_composition.py`, etc.) and their CSV
  artifacts under `docs/report/` — these are frozen historical record of the since-superseded
  "moderate conduit" research phase (see `docs/research-direction.md`, itself stale/superseded and
  also not touched here).
- Prose inside pre-existing dated `docs/report/*.md` entries (e.g.
  `2026-07-18-moderate-band-and-boundary-metrics.md`, `2026-08-02-delayed-moderate-conduit-pilot.md`)
  — per this project's append-only convention for the progress log, past entries are not retrofitted.
- Generic/colloquial uses of "moderate(s)" that predate and are independent of the formal camp
  definition (e.g. "extremists hold tighter tolerance than moderates" in `Analysis.java`, similar
  phrasing in `ExperimentConfig.java`/`Agent.java` calibration comments) — left as informal prose,
  not a reference to the renamed identifier.
- Deeper internal Python identifiers in ~15 more analysis scripts (e.g. `moderate_hub_ids()`
  function names, `bin_label` dicts using the older, already-inconsistent "pre-extreme" wording for
  bins 1/3) — out of the approved scope (code identifiers + CLI flags + the paper-figure script),
  and these scripts' `bin_label`/`"pre-extreme"` inconsistency with the paper's own "near-extreme"
  wording predates this session.
- `M-silent`/`M_silent` (the hub-silencing experimental condition name) and the `github.com/
  tooooomoya/moderate-hubs-beyond-direct-transmission` repo URL in the paper's footnote — a
  different naming axis (experimental condition / external repo identity, not the opinion-camp
  taxonomy) not part of this rename.

## Addendum — `M-silent`/`M_silent` → `N-silent`/`N_silent`

Same-day follow-up (user request): the hub-silencing experimental condition name `M-silent` (`M`
stood for the old "Moderate" hub) is renamed `N-silent` for the same reason as the main rename —
the hub is now called "neutral." This is a different naming axis from the camp taxonomy above
(an experimental-condition label, not an opinion-camp name), but was left inconsistent after the
main rename and is fixed here for the same consistency reason.

**Renamed:** `tex/CNA2026/CNA2026-5th.tex` (10 occurrences), `src/dynamics/StepStats.java` (comments),
`dashboard/core.py`, `dashboard/dashboard.html`, and 39 currently-active `scripts/lmp_feedmech_*.py`
/ `lmp_hubtier_*.py` / `lmp_band08_probe.py` / `lmp_uniform_probe.py` files (literal string token
only — internal Python variable abbreviations like `m_sub`/`msil`/`mr`/`mi` were left as-is, same
scope-boundary reasoning as the main rename's CLI-flag scripts).

**Also renamed: 30 on-disk result directories** literally named `M_silent` under
`results/2026-08-14_lmp_feedmech_structural_9b/` → `N_silent`, via plain directory rename (not a
data rewrite — confirmed `M_silent` was never stored as a literal value inside any CSV row, only
used as a path component, so this doesn't touch the ~94GB of underlying run data). This was
necessary, not optional: `scripts/lmp_feedmech_paper_figures.py` constructs paths like
`f"{SUBDIR}/{cell}/N_silent"`, so the on-disk directories had to move in lockstep with the code for
that already-fixed figure pipeline (see main entry above) to keep working.

**Explicitly out of scope (same reasoning as main rename):** `tex/CNA2026/CNA2026-{2nd,2nd-rev,3rd,
3rd-rev,4th,4th-rev}.tex` (frozen snapshots); the historical `delayed_moderate_*`/`moderate_hub_
*tier_removehub.py` scripts (none of them referenced `M_silent` anyway).

**Verification:** full `javac` rebuild clean; `test.ModelTests` unchanged (same 3 pre-existing
failures); `scripts/lmp_feedmech_paper_figures.py` re-run end-to-end against the renamed
`N_silent` directories — resolved paths correctly, regenerated all three figures with no errors;
`latexmk -pdf` on `CNA2026-5th.tex` rebuilds clean, fresh PDF, no undefined-reference warnings.

Note: mid-edit, `CNA2026-5th.tex` was found reverted to its pre-rename `M-silent` text once
(likely an external file-watch/autosave interaction, given a VSCode LaTeX-autobuild extension is
active on this file — see main entry's figure-regeneration section for the earlier, similar
`out/CNA2026-5th.pdf` deletion from the same cause). Re-applied and verified stable across a
subsequent full `latexmk` rebuild.

## Verification
- `javac` full rebuild: clean, zero errors.
- `test.ModelTests`: renamed neutral-band tests pass; the 3 remaining failures
  (`p_u tagged only when non-default`, `distinct configs => distinct tags`,
  `truncate default + bc_dec 1.0`) are pre-existing and unrelated — confirmed via `git stash`
  A/B comparison against the pre-rename code, same 3 failures present there.
- `latexmk -pdf` on `CNA2026-5th.tex`: builds clean, no undefined-reference/missing-file warnings.
- Figure regeneration: values in `outcome-heatmap.pdf`/`mod-extreme-influx.pdf`/
  `control-minus-msilent.pdf` numerically unchanged from before the rename (spot-checked); only
  labels/filenames changed.
