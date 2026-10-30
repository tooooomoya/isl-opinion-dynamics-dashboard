# Operations manual — common "how do I do X again" commands

Quick reference for recurring tasks on this project. `README.md` covers first-time setup; this
file is the day-to-day runbook. Update it when a workflow changes (e.g. a new CLI flag, a new
gotcha found) rather than letting it drift.

## Build & test

```bash
LIBCP="$(find lib -name '*.jar' | tr '\n' ':')"
find src -name '*.java' > .javafiles.txt
javac -cp "$LIBCP" -d bin @.javafiles.txt && rm -f .javafiles.txt

java -cp "${LIBCP}bin" test.ModelTests   # assertion harness, exits non-zero on failure
```

## Running simulations

**Single run, direct:**
```bash
java -cp "${LIBCP}bin" dynamics.OpinionDynamics seed=0 [key=value ...]
```

**Batch via `run.sh`** (compiles first, then runs seeds in parallel):
```bash
./run.sh                                          # defaults: seeds 0..29, parallel 10
./run.sh --seeds "0 1 2" --parallel 4 --heap 4g
./run.sh --seeds "0 1" -- p_u=0.05 bc_dec=0.995    # tokens after `--` go to the simulator
```

Full CLI key list: `src/experiment/ExperimentConfig.java`'s `fromArgs` switch statement is the
source of truth (it silently ignores unknown keys, so a typo won't error — double-check spelling
against that file if a run doesn't behave as expected). `README.md` lists the frequently-used ones.

## Force-overwriting an existing result folder

**Default behavior (R26): a run whose target result folder already exists ABORTS rather than
overwriting** — folder names are derived from the full config (`ExperimentConfig.tag()`), so a
collision usually means "you're about to silently redo/clobber a previous run with the same
config," which the tool refuses to do by default.

**To force it anyway (R27):** pass `force=true` as a config token. This deletes the pre-existing
folder first, then proceeds normally.

```bash
java -cp "${LIBCP}bin" dynamics.OpinionDynamics seed=0 force=true
./run.sh --seeds "0" -- force=true
```

There is no partial/merge behavior — `force=true` is a full delete-then-redo. If you only want to
keep some of a folder's contents, move/copy what you need out before running with `force=true`.

## Live dashboard while `run.sh` is running

```bash
python dashboard/dashboard.py --serve          # interactive web dashboard (recommended; for SSH / VSCode Remote-SSH)
python dashboard/dashboard.py                  # minimal matplotlib GUI fallback (needs a local display)
python dashboard/dashboard.py --serve --port 8765 --seeds 0 1 2
```

`--serve` starts a local HTTP server (`dashboard/dashboard.html` + JSON APIs, no extra deps beyond
requirements.txt) with an interactive dashboard:

- **metric grid** — any `results.csv` column (or derived metric: `apparentPolarization`,
  `repostShare`) via the "metrics…" picker, plus `_0..4` opinion-class families
  (`cRateMean`, `hostility`, ...) rendered as one class-colored chart each; defaults =
  `cRateMean`/`disagreement`/`apparentPolarization`/`unfollow`/`originalPostCount`. Hover
  crosshair/tooltip, drag-to-zoom on steps (synced across charts, double-click to reset),
  smoothing, and a "show mean" toggle to overlay the average across visible seeds.
- **seed chips** — status (running/done/failed) + progress % from the same `logs/run_<seed>.log`
  markers `scripts/check_progress.sh` uses; click to show/hide a seed, ▤ to tail its log.
- **2-D outcome plane** — per-seed trajectories, both axes selectable, with a time-scrub slider.
- **opinion distribution** — stacked bin shares over time from `opinion/opinion_result.csv`.
- **network snapshot** — live force-directed layout of the GEXF snapshots (follow or repost
  graph, any 5000-step snapshot; node color = opinion, radius ∝ √followers, ringed = hub,
  cross-cutting-edge highlight). Style after soramame0518/Social-Media-Echo-Chamber.
- **network structure** — degree distributions (in/out/total) as log-log CCDFs with a
  power-law fit overlay, clustering coefficient, giant-component betweenness + λ₂
  (algebraic connectivity), Q_sign (modularity) and E-I index over time — all for the same
  seed/step as the network snapshot, matching `docs/journal.tex`'s undirected-giant-component
  convention.
- **agent behavior & attributes** — mean repost depth and repost share over time
  (`posts/repost_cascades.csv`), plus bounded-confidence and post-probability distribution
  histograms (GEXF node attributes, not available in any CSV).
- pause / refresh-interval / dark-light toggle; view settings persist in the browser.
- every card is resizable (drag its bottom-right corner) and reorderable within its row
  (drag the ✦ handle); both persist across reloads.

Full design rationale (derived-metric mechanism, family grouping, caching strategy, betweenness
cost, known limitations) is in `docs/dashboard.md` (Japanese) — read that before extending either
file. The server tails the result CSVs incrementally (byte-offset + adaptive decimation), so it
stays cheap even against 15 MB `results.csv` files while a 30-seed batch is writing. Read-only —
never edits `results/` or `logs/`; stopping it does not touch the simulations.

**Over SSH:** VSCode Remote-SSH auto-forwards the port (click the toast, or check the PORTS tab);
view it in-editor via Cmd/Ctrl+Shift+P -> "Simple Browser: Show" -> the forwarded
`http://127.0.0.1:8765` URL, or in any normal browser tab.

## Analysis scripts

- `scripts/validation_gate_pilot_analysis.py [results_dir] [steps] [min_seed] [max_seed]` —
  Step-2 gate metrics (structural separation, hub-attributable cross-camp bridging) for the
  network-type/hub-presence pilot matrix.
- `scripts/oat_sweep_analysis.py [results_dir]` — OAT calibration/robustness sweep readout.
- `scripts/heavy_tail_check_n1000.py` — degree-distribution power-law/Gini check at production
  scale (see `docs/report/2026-07-09-oat-sweep-findings.md`).

Each expects `results/run_<seed>_<tag>/` folders already produced by a run; check the script's
own docstring for exact folder-matching assumptions (they match on `tag()` substrings, so a
`network`/scale/parameter change may need the matcher pattern updated — this has been a repeat
source of silent-zero-rows bugs, see the git log for `scripts/`).

## Git workflow

Standard flow (see the repo's own commit history for message style — short imperative summary,
detail in the body, `Co-Authored-By` trailer when Claude made the change):

```bash
git status                     # review what's staged/unstaged before adding
git add <specific files>       # avoid `git add -A` — review for secrets/large binaries first
git commit -m "..."
git push origin main           # plain push; this repo has no protected-branch friction so far
```

**Force-push (`git push --force` / `--force-with-lease`): only when you specifically mean to
rewrite remote history (e.g. after an interactive rebase or amending a pushed commit).**
- Prefer `--force-with-lease` over bare `--force` — it refuses if someone else pushed to the
  branch since your last fetch, so you don't silently clobber someone else's work:
  ```bash
  git push --force-with-lease origin main
  ```
- Never do this on `main` without being certain no one else has pushed in the meantime — check
  `git fetch && git log origin/main` first.
- This is a genuinely destructive operation (can permanently lose commits on the remote); treat
  a request for it as needing fresh confirmation every time, not a standing default.

## Environment gotchas (found the hard way)

- **macOS ships bash 3.2** (`/bin/bash`, pre-GPLv3, no Apple updates) — not bash 4+. Two specific
  traps for sweep/batch shell scripts:
  - `"${array[@]}"` on an **empty** array throws `unbound variable` under `set -u` and silently
    aborts *that one command* (loop continues) — guard with `[ ${#array[@]} -gt 0 ]` before
    expanding, don't assume the expansion is a no-op.
  - `wait -n` doesn't exist before bash 4.3 — use a `sleep 1` polling loop against
    `jobs -rp | wc -l` for concurrency throttling instead.
- **A "clean exit code" is not evidence a sweep produced valid data.** Three real bugs this
  project hit (`sbm_pin`/`sbm_pout` missing from `tag()` causing folder collisions; the two bash
  issues above; a second hardcoded `feed_capacity` default in `Agent`'s constructor) all left the
  driving shell script's exit code at 0. Always check `logs/*.log` for `ABORT` lines and eyeball
  whether an aggregated result is *suspiciously exact* (e.g. bit-identical to another cell to 6
  decimal places) before trusting it.
- **Result folder collisions are silent by default (R26 abort), not loud.** If a sweep cell's
  metrics look identical to another cell's, check whether they actually landed in different
  folders (`tag()` doesn't encode every `ExperimentConfig` field — verify the specific parameter
  you're sweeping actually appears in the folder name, or two configs can collide unnoticed).

## Where things live

- `docs/research-direction.md` — canonical research objective/status (read first).
- `docs/report/*.md` — dated design-decision log, append-only (note supersessions, don't rewrite).
- `docs/reference/` — reference PDFs for literature-anchored parameters; **gitignored**
  (copyright), stays local only.
- `results/` — simulation output, gitignored.

## Viewing a run in the dashboard (attention-economy branch)

```bash
# 1. run with network snapshots (log_gexf defaults to true) and a name the dashboard can pair with the results folder
nohup ./run.sh --name myrun --seeds "0" --parallel 1 --heap 4g -- steps=20000 results_subdir=myrun > logs/myrun.out 2>&1 & disown
# 2. serve the dashboard (read-only; stop with Ctrl-C), then open http://127.0.0.1:8765
python3 dashboard/dashboard.py --serve --port 8765
```
In the page, choose the run set `myrun_seed_myrun` in the run-set picker. The Network tab needs `log_gexf=true`.
Always give `--name X` and `results_subdir=X` the same X: the dashboard matches a run set to its results folder by that name.

## Bayesian calibration of the attention-economy model

Design, observation definitions, target-data audit, and current progress:
`docs/report/2026-10-27-calibration-run.md`. Extra analysis packages:
`venv/bin/pip install -r scripts/requirements-calibration.txt`.

```bash
mkdir -p logs/calibration
nohup venv/bin/python -u scripts/bayesian_calibration.py --phase full --workers 20 --timeout 7200 > logs/calibration/full.out 2>&1 &
disown

venv/bin/python scripts/analyze_bayesian_calibration.py --surrogate-audit
```

The default run lives in `results/calibration_20261027/`. Repeating the driver
command resumes its **frozen simulator snapshot** and completed seed results;
it adopts still-running exact-configuration JVMs where possible. Earlier timeout
attempts remain in `attempts/`, and failed evaluations are excluded from surrogate
training. Up to four outstanding pilot points may overlap refinement; all pilot outcomes
are required before confirmation.

After changing scientific model code or measurement definitions, use a **new**
`--output results/calibration_<new_id>` rather than warm-starting from an incompatible
run. Every job keeps full tokens, seed, raw output and component errors. No fitted
parameter point is automatically adopted as a default. Driver logs and per-job
JSON files are authoritative for completion, not merely a process exit code.

### Uniform-initialization emergence study (2026-10-28)

Prospective specification: `docs/report/2026-10-28-uniform-calibration-run.md`.
This study uses uniform fixed opinions and three equal-side activity ratios
relative to neutral. It has its own output directory and frozen measurement
identity; it does not rescore or reuse the empirical-initialization observations.

```bash
# Check logs/calibration_uniform_20261028/pipeline.pid before launching a duplicate.
venv/bin/python -u scripts/run_uniform_calibration.py --workers 24

# Interim report (safe while simulations run):
venv/bin/python scripts/analyze_bayesian_calibration.py \
  --run results/calibration_uniform_20261028 \
  --output docs/report/bayesian-calibration-uniform-2026-10-28
```

The pipeline runs calibration, exports figures/tables, and runs held-out network
null diagnostics. Inspect `pipeline_status.json` and `PIPELINE_COMPLETE.json` in
the run directory. A simulation-only `COMPLETE.json` does not imply the later
analysis/null stages have completed. Per-stage logs are under
`logs/calibration_uniform_20261028/`. Changes to measurement code, targets, or
baseline tokens require a new output directory; uniform-study resume checks
their identity.

Future calibration policy (user update, 2026-10-28): **5 seeds per parameter
setting in both initial search and Bayesian refinement; 10 fresh confirmation
seeds**. New driver runs default to 40,000 steps for both search and confirmation,
so screening and confirmation do not change horizons. Seed counts and horizons
are persisted in `execution_design.json`; resumption preserves them and rejects
conflicting requests. Existing October 28 outputs keep the executed 2/3/20 seeds
and 20k/40k horizons. Start a new output directory to use the new policy:

```bash
venv/bin/python -u scripts/bayesian_calibration.py --study uniform-v3 \
  --output results/calibration_uniform_next --workers 24 \
  --search-seeds 5 --confirm-seeds 10 --search-steps 40000 --confirm-steps 40000
```

### Multi-network restart (HK-shuffled / random / DC-SBM)

Active replacement study and exact budget:
`docs/report/2026-10-28-multinetwork-calibration-restart.md`.

```bash
venv/bin/python -u scripts/run_multinetwork_calibration.py --workers 24
```

This runs three **independent** fits with eight workers each (24 total), five
search seeds, ten confirmation seeds, and 40k steps in both phases. Outputs are
under `results/calibration_multinetwork_20261028/{hkshuf,random,dcsbm}/`; reports
and logs have corresponding family subdirectories. The parent holds a process
lock and records its PID in `logs/calibration_multinetwork_20261028/pipeline.pid`.
Inspect `status_<network>.json` for each family. The old single-network run is
preserved; it is not reused as training data in the replacement.

For a single independent family use the driver `--network hkshuf|random|dcsbm`
and a new explicit `--output`. A run refuses a different fitting network on
resume. Random p and DC-SBM target mean degree are coordinated with `start_deg`.

## Raw identity-fit calibration (2026-10-29)

Main standing configuration now uses `fit_mode=raw` (mean feed similarity, common zero baseline). Standing output names are `standard_raw_*` / `baseline_raw_*`; previous relative-fit outputs are historical. The relative-fit multi-network sweep was stopped by the user; do not resume it as the main study.

The smaller replacement is prepared but has not been launched:

```bash
venv/bin/python -u scripts/run_multinetwork_calibration.py --compact-raw
```

This uses a separate `uniform-raw-v4` study with uniform opinions, three networks, 48 pilot + 16 BO settings per network, five search seeds, two finalists with ten fresh seeds, matched 20k search/confirmation horizons, and five paired 40k horizon checks for the winner. Total default worker count is 12; outputs go to `results/calibration_raw_20261029/`. See `docs/report/2026-10-29-raw-identity-fit-and-compact-search.md` for assumptions, unchanged empirical targets, and the reduced budget.

### Approved reduced replacement

The user approved a 13-parameter version, superseding the unlaunched 25-parameter raw plan:

```bash
venv/bin/python -u scripts/run_multinetwork_calibration.py --reduced-raw
```

Study `uniform-raw-reduced-v5` records 13 active priors and 12 fixed inputs, including equal Chronological/For You/Trend feed shares. Results and logs use `calibration_raw_reduced_20261029/`. See `docs/report/2026-10-29-reduced-raw-calibration.md`. Resume with the exact same command and saved design; do not mix output directories with earlier studies.
