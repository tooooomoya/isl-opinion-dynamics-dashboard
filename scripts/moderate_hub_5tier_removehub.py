"""
2026-07-30 -- Phase 1 of the resumed moderate-hub causal experiment: `remove_hub` re-validation
under the CURRENT (post-2026-07-29 directed-BFS) feed mechanism, across five follower-count tiers.

Context: the entire prior ID-intervention battery (swap/mute_access/mute_repost/algo_exclude/
remove_hub across mega/mid/small tiers, docs/report/2026-07-21-conduit-experiment-design.md) ran
under the OLD (undirected, hard-cutoff) feed mechanism, which that doc's own "What this invalidates"
section flags as not directly reusable post-fix. This script re-validates the core `remove_hub`
finding (structural triad moves, sf1_ratio doesn't) under the new mechanism, before committing to the
larger Role/Adaptive build. `remove_hub` only (not swap/mute_access/mute_repost/algo_exclude) --
2026-07-28 found it strictly dominates the other four arms in resolving power, so re-testing all five
just to re-validate would be wasted compute.

Five tiers (user-specified 2026-07-30), by REALIZED (step-20000-equilibrium) followerCount:
  mega        > 500   (>50% of n=1000 agents)
  middle      100-500
  small        50-100
  grassroot    10-50
  peripheral    0-10

Design (matches the established two-phase pattern in scripts/bridging_current_config_removehub.py):
  1. Build N_SEEDS=10 fresh equilibria (unmanipulated, current mechanism, steps=20000, log_gexf=true
     for the GEXF snapshot). Fresh, not reused from any pre-fix run -- the mechanism changed, so old
     equilibria would splice old-mechanism dynamics into a new-mechanism continuation.
  2. From each equilibrium's final snapshot, derive the realized moderate-hub id list per tier
     (|opinion| < MODERATE_THRESHOLD AND tier's followerCount band).
  3. Continue each equilibrium seed for CONTINUE_STEPS=20000 more steps under 6 arms: one shared
     `control` (no manipulation -- shared across all 5 tiers, since it doesn't depend on which tier's
     hub list would otherwise be removed) + 5 tier-specific `remove_hub_<tier>` arms (that tier's
     realized hub ids severed via `remove_hub_ids`, at continuation t=0).
  4. Metrics read at CONTINUATION-relative checkpoints [5000, 20000] -- 5000 (not the previously-used
     10000) chosen per the 2026-07-28 "trajectory check" finding that moderate-reach effects are
     front-loaded and decay by step 20000; an early checkpoint is needed to not just measure the
     tail of an already-decayed signal.

Outcome tiering (user, 2026-07-30): primary = pre-extreme AND extreme per-capita post rate (windowed,
1000-step trailing window ending at each checkpoint, per the 2026-07-29 v7 fix -- avoids the
zero-inflation of a single-step snapshot); secondary = sf1_ratio, opinionAssortativity; tertiary =
crossCuttingFraction, bimodalityCoeff (user's own framing: these are the "easy to predict" outcomes).
Broader metric set still logged to CSV for completeness even though not all are headlined.

Feed-mechanism params: the "provisional" point from docs/report/2026-07-29-feed-reach-redesign.md's
v4 recommendation (hop=4, feed_decay_mode=exp, feed_decay_lambda=0.10992130598108527, alpha=0.7,
feed_time_decay_tau=30) -- explicitly NOT a final calibration (pending the user's other-server joint
search); flagged here so results are read as provisional too.

Usage: nohup python3 scripts/moderate_hub_5tier_removehub.py > logs/moderate_hub_5tier_stdout.log 2>&1 &
       (then disown)
"""
import concurrent.futures
import csv
import subprocess
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
_JARS = list(ROOT.glob("lib/**/*.jar"))
LIBCP = ":".join(str(p) for p in _JARS) + (":" if _JARS else "") + str(ROOT / "bin")

N = 1000
EQUIL_STEPS = 20000
CONTINUE_STEPS = 20000
CHECKPOINTS = [5000, 20000]
N_SEEDS = 10
MODERATE_THRESHOLD = 0.2
WINDOW = 1000  # windowed per-capita rate, matches the 2026-07-29 v7 fix

TIERS = {
    "mega": (500, float("inf")),
    "middle": (100, 500),
    "small": (50, 100),
    "grassroot": (10, 50),
    "peripheral": (0, 10),
}

EQUIL_BASE_SEED = 9100000
CONTROL_BASE_SEED = 9200000
REMOVE_HUB_BASE = {
    "mega": 9310000,
    "middle": 9320000,
    "small": 9330000,
    "grassroot": 9340000,
    "peripheral": 9350000,
}

# Provisional current-mechanism point (v4 recommendation, 2026-07-29) -- NOT the final calibration.
FIXED_TOKENS = [
    "network=hk", "hk_m=15", "hk_a=4", "hk_pt=0.05",
    "max_follow=43.8638", "follow_prob=0.01", "feed_capacity=15",
    "alpha=0.7", "hop=4", "feed_decay_mode=exp", "feed_decay_lambda=0.10992130598108527",
    "feed_time_decay_tau=30",
    "access_prob=0.1", "p_u=0.05",
    "bc_dec=0.500000", "bc_recovery=0.000100", "bc_floor=0.2", "bc_ceiling=1.0", "bc_init=0.800000",
    "vocal_comfort_radius=0.1", "repost_prob=0.1", "relay_enabled=false",
    "out_of_bc_repost_prob=0.01", "rel_attrib=original",
    "stub_dist=uniform", "stub_min=0.82", "stub_max=0.82",
    "evict_beta=-1", "init_prune=trim",
    "initial_pp=0.25537", "max_pp=1.0", "min_pp=0.01", "pp_relax_eta=0.100000",
    "moderate_band=0.2",
]

LOG_PATH = ROOT / "docs" / "report" / "moderate_hub_5tier_removehub.csv"


def result_dir(seed):
    candidates = sorted(ROOT.glob(f"results/run_{seed}_*"), key=lambda p: p.stat().st_mtime)
    return candidates[-1] if candidates else None


def is_done(seed, steps):
    d = result_dir(seed)
    if d is None:
        return False
    rp = d / "metrics" / "results.csv"
    if not rp.exists():
        return False
    with open(rp, newline="") as f:
        rows = list(csv.DictReader(f))
    return bool(rows) and int(rows[-1]["step"]) >= steps


def equil_gexf_path(seed):
    d = result_dir(seed)
    return d / "GEXF" / "lambda_0.0" / f"step_{EQUIL_STEPS}.gexf"


def launch(seed, steps, extra_tokens, log_gexf):
    tokens = [f"seed={seed}", f"steps={steps}", f"n={N}", "force=true", f"log_gexf={str(log_gexf).lower()}"] \
        + FIXED_TOKENS + extra_tokens
    logfile = ROOT / "logs" / f"modhub5t_seed{seed}.log"
    logfile.parent.mkdir(exist_ok=True)
    with open(logfile, "w") as lf:
        p = subprocess.Popen(["java", "-Xmx2g", "-cp", LIBCP, "dynamics.OpinionDynamics", *tokens],
                              stdout=lf, stderr=subprocess.STDOUT, cwd=ROOT)
    return p


def run_wave(seed_steps_tokens_gexf, max_workers=20):
    """seed_steps_tokens_gexf: list of (seed, steps, tokens, log_gexf). Skips seeds already done."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = []
        for seed, steps, tokens, log_gexf in seed_steps_tokens_gexf:
            if is_done(seed, steps):
                print(f"  seed={seed}: reusing existing", flush=True)
                continue
            futs.append(ex.submit(lambda s=seed, st=steps, tk=tokens, g=log_gexf: launch(s, st, tk, g).wait()))
        for f in futs:
            f.result()


def population_counts(equil_seed):
    """Pre-extreme (bins 1,3) and extreme (bins 0,4) population counts at continuation t=0."""
    d = result_dir(equil_seed)
    pre_extreme = extreme = 0
    with open(d / "degrees" / "agent_snapshot_final.csv", newline="") as f:
        for r in csv.DictReader(f):
            op = float(r["opinion"])
            shifted = op + 1.0
            cls = min(int(shifted / 0.4), 4)
            if cls in (1, 3):
                pre_extreme += 1
            elif cls in (0, 4):
                extreme += 1
    return pre_extreme, extreme


def moderate_hub_ids(equil_seed, tier):
    d = result_dir(equil_seed)
    lo, hi = TIERS[tier]
    hits = []
    with open(d / "degrees" / "agent_snapshot_final.csv", newline="") as f:
        for r in csv.DictReader(f):
            op, fo = float(r["opinion"]), int(r["followerCount"])
            if lo < fo <= hi and abs(op) < MODERATE_THRESHOLD:
                hits.append(int(r["agentId"]))
    return hits


def read_windowed_percapita(cont_seed, checkpoint, pre_extreme_pop, extreme_pop):
    d = result_dir(cont_seed)
    with open(d / "metrics" / "results.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    lo = checkpoint - WINDOW
    window = [r for r in rows if lo < int(r["step"]) <= checkpoint]
    pre_sum = ext_sum = 0.0
    for r in window:
        total = float(r["originalPostCount"]) + float(r["repostCount"])
        pre_sum += (float(r["postShare_1"]) + float(r["postShare_3"])) * total
        ext_sum += (float(r["postShare_0"]) + float(r["postShare_4"])) * total
    pre_rate = pre_sum / pre_extreme_pop / WINDOW if pre_extreme_pop > 0 else None
    ext_rate = ext_sum / extreme_pop / WINDOW if extreme_pop > 0 else None
    return pre_rate, ext_rate


def read_metrics_at(cont_seed, checkpoint, pre_extreme_pop, extreme_pop):
    d = result_dir(cont_seed)
    with open(d / "metrics" / "results.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    at = next(r for r in reversed(rows) if int(r["step"]) == checkpoint)
    q = None
    with open(d / "metrics" / "modularity.csv", newline="") as f:
        for row in csv.DictReader(f):
            if int(row["step"]) == checkpoint:
                q = float(row["Q_sign_repost"])
    opinion_var = float(at["opinionVar"])
    post_opinion_var = float(at["postOpinionVar"])
    sf1 = post_opinion_var / opinion_var if opinion_var > 0 else None
    pre_rate, ext_rate = read_windowed_percapita(cont_seed, checkpoint, pre_extreme_pop, extreme_pop)
    return dict(
        percapita_preextreme=pre_rate, percapita_extreme=ext_rate,
        sf1_ratio=sf1, opinionAssortativity=float(at["opinionAssortativity"]),
        crossCuttingFraction=float(at["crossCuttingFraction"]), bimodalityCoeff=float(at["bimodalityCoeff"]),
        Q_sign_repost=q, opinionVar=opinion_var, postOpinionVar=post_opinion_var,
        interactionCrossCuttingFraction=float(at["interactionCrossCuttingFraction"]),
        opinionKurtosis=float(at["opinionKurtosis"]), disagreement=float(at["disagreement"]),
        crossRepostRate=float(at["crossRepostRate"]),
    )


def main():
    equil_seeds = [EQUIL_BASE_SEED + i for i in range(N_SEEDS)]

    print("=== Phase A: building/verifying 10 fresh equilibria (current mechanism) ===", flush=True)
    run_wave([(s, EQUIL_STEPS, [], True) for s in equil_seeds], max_workers=10)
    for s in equil_seeds:
        assert is_done(s, EQUIL_STEPS), f"equilibrium seed {s} failed"

    print("\n=== Deriving realized hub lists + t0 population counts per seed ===", flush=True)
    pop_counts = {}
    hub_lookup = {tier: {} for tier in TIERS}
    for s in equil_seeds:
        pop_counts[s] = population_counts(s)
        print(f"  seed={s}: pre_extreme_pop={pop_counts[s][0]}, extreme_pop={pop_counts[s][1]}", flush=True)
        for tier in TIERS:
            ids = moderate_hub_ids(s, tier)
            hub_lookup[tier][s] = ids
            print(f"    tier={tier}: {len(ids)} moderate hubs -> {ids}", flush=True)

    print("\n=== Phase B: control continuations (shared across tiers) ===", flush=True)
    control_seeds = {s: CONTROL_BASE_SEED + i for i, s in enumerate(equil_seeds)}
    run_wave(
        [(control_seeds[s], CONTINUE_STEPS,
          ["network=read", f"read_path={equil_gexf_path(s)}"], False) for s in equil_seeds],
        max_workers=10,
    )

    remove_hub_seeds = {tier: {} for tier in TIERS}
    for tier in TIERS:
        print(f"\n=== Phase B: remove_hub continuations, tier={tier} ===", flush=True)
        rh_seeds = {s: REMOVE_HUB_BASE[tier] + i for i, s in enumerate(equil_seeds)}
        remove_hub_seeds[tier] = rh_seeds
        jobs = []
        for s in equil_seeds:
            ids = hub_lookup[tier][s]
            idstr = ",".join(str(a) for a in ids)
            tokens = ["network=read", f"read_path={equil_gexf_path(s)}"]
            if idstr:
                tokens.append(f"remove_hub_ids={idstr}")
            jobs.append((rh_seeds[s], CONTINUE_STEPS, tokens, False))
        run_wave(jobs, max_workers=10)

    print("\n=== Reading metrics + writing log ===", flush=True)
    metric_names = ["percapita_preextreme", "percapita_extreme", "sf1_ratio", "opinionAssortativity",
                     "crossCuttingFraction", "bimodalityCoeff", "Q_sign_repost", "opinionVar",
                     "postOpinionVar", "interactionCrossCuttingFraction", "opinionKurtosis",
                     "disagreement", "crossRepostRate"]

    with open(LOG_PATH, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["tier", "arm", "base_seed", "checkpoint", "n_hubs"] + metric_names)
        for s in equil_seeds:
            pre_pop, ext_pop = pop_counts[s]
            for cp in CHECKPOINTS:
                m = read_metrics_at(control_seeds[s], cp, pre_pop, ext_pop)
                w.writerow(["ALL", "control", s, cp, 0] + [m[k] for k in metric_names])
        for tier in TIERS:
            for s in equil_seeds:
                pre_pop, ext_pop = pop_counts[s]
                n_hubs = len(hub_lookup[tier][s])
                for cp in CHECKPOINTS:
                    m = read_metrics_at(remove_hub_seeds[tier][s], cp, pre_pop, ext_pop)
                    w.writerow([tier, "remove_hub", s, cp, n_hubs] + [m[k] for k in metric_names])
    print(f"Full log: {LOG_PATH}", flush=True)

    print("\n=== Paired remove_hub vs control, by tier and checkpoint ===", flush=True)
    for tier in TIERS:
        for cp in CHECKPOINTS:
            print(f"\n### tier={tier}, checkpoint={cp} (n={N_SEEDS}) ###")
            n_hubs_list = [len(hub_lookup[tier][s]) for s in equil_seeds]
            print(f"  n_hubs per seed: {n_hubs_list}")
            control_vals = {s: read_metrics_at(control_seeds[s], cp, *pop_counts[s]) for s in equil_seeds}
            treat_vals = {s: read_metrics_at(remove_hub_seeds[tier][s], cp, *pop_counts[s]) for s in equil_seeds}
            for m in metric_names:
                paired = [(control_vals[s][m], treat_vals[s][m]) for s in equil_seeds
                          if control_vals[s][m] is not None and treat_vals[s][m] is not None]
                if len(paired) < 2:
                    continue
                c = np.array([cv for cv, tv in paired]); t = np.array([tv for cv, tv in paired])
                diff = t - c
                tstat = diff.mean() / (diff.std(ddof=1) / np.sqrt(len(diff))) if diff.std(ddof=1) > 0 else float("nan")
                print(f"  {m:>32}: control={c.mean():.4f}+/-{c.std():.4f}  remove_hub={t.mean():.4f}+/-{t.std():.4f}  "
                      f"diff={diff.mean():+.4f}+/-{diff.std():.4f}  t={tstat:.2f}  n={len(paired)}")


if __name__ == "__main__":
    main()
