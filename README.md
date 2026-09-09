## Getting Started

### Build & run

Compile all sources (shell-portable; `find` avoids the zsh-only `src/**` glob) and run one
simulation. The classpath is the gephi jars under `lib/` plus `bin/`:

```
LIBCP="$(find lib -name '*.jar' | tr '\n' ':')"
find src -name '*.java' > .javafiles.txt
javac -cp "$LIBCP" -d bin @.javafiles.txt && rm -f .javafiles.txt
java -cp "${LIBCP}bin" dynamics.OpinionDynamics seed=0
```

The only external dependency is the **gephi toolkit** (in `lib/gephi/`), used for GEXF graph
export; download the toolkit from the gephi website if it is missing. `log_gexf=false` skips all
gephi work entirely (useful for large sweeps).

### Configuration (CLI `key=value` tokens)

Every run parameter is a space-separated `key=value` token; unknown keys are ignored, and each
non-default knob is appended to the result-folder name (see `experiment/ExperimentConfig`). All
runtime parameters live on the immutable `experiment/SimParams`, so one JVM can run several
configurations. Common examples:

```
# a parameter sweep point
java -cp "${LIBCP}bin" dynamics.OpinionDynamics seed=3 p_u=0.05 bc_dec=0.995 alpha=0.3

# smaller/faster instance, no gephi, cascade logging on
java -cp "${LIBCP}bin" dynamics.OpinionDynamics seed=0 n=500 steps=5000 log_gexf=false
```

Frequently used keys: `seed`, `net_seed`, `n`, `steps`, `network` (`dcsbm|ba|hk|ws|dms|cnn|lfr|random|read`),
`p_u`, `bc_dec`, `bc_inc` (asymmetric tolerance recovery rate), `p_r_out`, `s_relay`, `repost_prob`,
`stub_dist`, `evict_beta`, `vel_mode`, `rel_attrib`, `rho_block`, `alpha`/`hop` (For-You feed),
`sbm_k`/`sbm_pin`/`sbm_pout`/`sbm_gamma`/`sbm_deg` (DC-SBM structural params),
`feed_capacity`/`follow_prob`/`initial_pp`/`max_pp`/`min_pp`/`comfort_pp` (2026-07-09: migrated off
`Const` literals onto `SimParams`/CLI — see `docs/report/2026-07-09-oat-sweep-findings.md`),
`access_prob` (2026-07-10: the model's global timescale knob — gates an agent's entire per-step
action set, opinion update included; was `Const.ACCESS_PROB`, now CLI-sweepable),
`log_gexf`, `log_cascades`, `assert_int`, `hostility_active` (option C: gate affective state tracking).
See `ExperimentConfig.fromArgs` for the full list.

### Tests

```
java -cp "${LIBCP}bin" test.ModelTests
```

Runs the `ModelTests` assertion harness (config round-trip, tag distinctness, relay lineage,
truncated init, hostility bounds, attribution). Exits non-zero on any failure.

## Folder Structure

Make sure you create `results` folder as we do not upload them on github.

The workspace contains two folders by default, where:

- `src`: the folder to maintain sources
- `lib`: the folder to maintain dependencies

Meanwhile, the compiled output files will be generated in the `bin` folder by default.

> If you want to customize the folder structure, open `.vscode/settings.json` and update the related settings there.

## Dependency Management

The `JAVA PROJECTS` view allows you to manage your dependencies. More details can be found [here](https://github.com/microsoft/vscode-java-dependency#manage-dependencies).


## Python virtual environment

For using analysis python files, our requirments.txt may be useful

## Parallel Processing

`run.sh` compiles once and runs many seeds in parallel. It never deletes existing results and
takes seeds / passthrough config tokens as arguments:

```
./run.sh                                        # default seeds, parallel 10
./run.sh --seeds "0 1 2 3" --parallel 4
./run.sh --seeds "0 1" -- p_u=0.05 bc_dec=0.995 # tokens after -- go to the simulator
```

A run whose result folder already exists aborts rather than overwriting, unless the config token
`force=true` is passed (deletes the existing folder first), e.g.
`./run.sh --seeds "0" -- force=true`.