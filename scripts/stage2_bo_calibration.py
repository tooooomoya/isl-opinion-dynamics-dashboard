"""
Stage 2 Bayesian-optimization calibration (systematic-A/B calibration plan).

Calibrates bcDecRate / stubbornness / comfortPpFactor / feedCapacity / initialPostProb against the
repost network's structural fit (Q_sign_repost, Conover et al. 2011 ~0.7-0.8), on top of the
Stage-1a/1b-calibrated HK generator + follow-dynamics/recommender params (now ExperimentConfig
defaults: hk_m=15/hk_a=4/hk_pt=0.05, max_follow=55, follow_prob=0.01, alpha=0.85, hop=4).

bcIncRate is NOT an independent dimension: bcIncRate = 1 + (1 - bcDecRate) / 10 (asymmetric
tolerance recovery at 1/10 the magnitude of decline, per this session's design discussion).

IMPORTANT: stub_dist=const ignores stub_min/stub_max entirely (uses the hardcoded
Const.INITIAL_STUBBORNNESS=0.7 regardless of CLI args — verified in Agent.java before writing this
script). To sweep a constant stubbornness value X, pass stub_dist=uniform stub_min=X stub_max=X
(same workaround the 2026-07-09 OAT sweep used), not stub_dist=const.

Lessons applied from the Stage-1b BO run (docs/report/calibration-sweep-results.md):
- Reduced parallelism (5 points/round, 1 seed each -> 5 concurrent JVMs, not 12) after Stage 1b's
  12-concurrent-JVM rounds took 4-8x longer than a single-run timing estimate predicted.
- Seeds are pre-assigned per point BEFORE dispatching to the thread pool (fixes Stage 1b's
  thread-safety bug: a shared mutable counter incremented from multiple threads made seed-to-point
  attribution unreliable for any evaluation that outlived the process).
- 1 seed per point (not 2) given 5 free dimensions need more evaluations for the same budget;
  promising candidates get a multi-seed confirmation pass afterward, same as Stage 1b.

Known limitation (stated up front): 5 free parameters against effectively 1 scalar target
(Q_sign_repost) is underdetermined -- this run characterizes a plausible region / best-found point,
not a unique identified optimum. Treat the result as a starting point for a robustness pass, not a
final answer.

Usage: python3 scripts/stage2_bo_calibration.py
"""
import csv
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from skopt import Optimizer
from skopt.space import Real, Integer

ROOT = Path(__file__).resolve().parent.parent
LIBCP = ":".join(str(p) for p in ROOT.glob("lib/*.jar")) + (":" if list(ROOT.glob("lib/*.jar")) else "") + str(ROOT / "bin")
N = 1000
STEPS = 15000
N_ROUNDS = 4
N_POINTS_PER_ROUND = 5
Q_TARGET, Q_SCALE = 0.75, 0.05  # Conover et al. 2011 ~0.7-0.8 midpoint

SPACE = [
    Real(0.9, 0.999, name="bc_dec"),
    Real(0.2, 0.8, name="stub"),
    Real(1.0, 1.5, name="comfort_pp"),
    Integer(5, 30, name="feed_capacity"),
    Real(0.05, 0.5, name="initial_pp"),
]

LOG_PATH = ROOT / "docs" / "report" / "stage2_bo_evaluations.csv"
BASE_SEED = 50000  # seeds assigned as BASE_SEED + round*N_POINTS_PER_ROUND + point_index (pre-allocated, no shared counter)


def launch(bc_dec, stub, comfort_pp, feed_capacity, initial_pp, seed):
    bc_inc = 1.0 + (1.0 - bc_dec) / 10.0
    tokens = [
        f"seed={seed}", "network=hk", f"n={N}", f"steps={STEPS}", "log_gexf=false",
        "max_follow=55", "follow_prob=0.01", "alpha=0.85", "hop=4",  # Stage 1b calibrated, held fixed
        f"bc_dec={bc_dec:.5f}", f"bc_inc={bc_inc:.5f}",
        "stub_dist=uniform", f"stub_min={stub:.4f}", f"stub_max={stub:.4f}",
        f"comfort_pp={comfort_pp:.4f}", f"feed_capacity={feed_capacity}",
        f"initial_pp={initial_pp:.4f}", "force=true",
    ]
    logfile = ROOT / "logs" / f"stage2_bo_seed{seed}.log"
    logfile.parent.mkdir(exist_ok=True)
    with open(logfile, "w") as lf:
        p = subprocess.Popen(
            ["java", "-Xmx2g", "-cp", LIBCP, "dynamics.OpinionDynamics", *tokens],
            stdout=lf, stderr=subprocess.STDOUT, cwd=ROOT,
        )
    return p


def read_q_sign_repost(seed):
    candidates = sorted(ROOT.glob(f"results/run_{seed}_*"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        return None
    d = candidates[-1]
    mod_path = d / "metrics" / "modularity.csv"
    if not mod_path.exists():
        return None
    with open(mod_path, newline="") as f:
        for row in csv.DictReader(f):
            if int(row["step"]) == STEPS:
                return float(row["Q_sign_repost"])
    return None


def evaluate_point(x, seed):
    bc_dec, stub, comfort_pp, feed_capacity, initial_pp = x
    p = launch(bc_dec, stub, comfort_pp, feed_capacity, initial_pp, seed)
    p.wait()
    q = read_q_sign_repost(seed)
    if q is None:
        return 1e6, None
    loss = ((q - Q_TARGET) / Q_SCALE) ** 2
    return loss, q


def main():
    opt = Optimizer(SPACE, base_estimator="GP", acq_func="EI", random_state=7)
    rows = []
    with open(LOG_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["round", "seed", "bc_dec", "bc_inc", "stub", "comfort_pp",
                          "feed_capacity", "initial_pp", "loss", "q_sign_repost"])

        for rnd in range(N_ROUNDS):
            t0 = time.time()
            points = opt.ask(n_points=N_POINTS_PER_ROUND)
            seeds = [BASE_SEED + rnd * N_POINTS_PER_ROUND + i for i in range(len(points))]
            print(f"[round {rnd}] evaluating {len(points)} points in parallel "
                  f"(seeds {seeds[0]}-{seeds[-1]})...", flush=True)

            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=N_POINTS_PER_ROUND) as ex:
                results = list(ex.map(lambda ps: evaluate_point(*ps), zip(points, seeds)))

            losses = [r[0] for r in results]
            opt.tell(points, losses)
            for pt, seed, (loss, q) in zip(points, seeds, results):
                bc_dec, stub, comfort_pp, feed_capacity, initial_pp = pt
                bc_inc = 1.0 + (1.0 - bc_dec) / 10.0
                writer.writerow([rnd, seed, bc_dec, bc_inc, stub, comfort_pp,
                                  feed_capacity, initial_pp, loss, q])
                rows.append((rnd, seed, bc_dec, bc_inc, stub, comfort_pp, feed_capacity, initial_pp, loss, q))
            f.flush()
            print(f"[round {rnd}] done in {time.time()-t0:.0f}s, "
                  f"best loss so far = {min(r[8] for r in rows):.3f}", flush=True)

    rows.sort(key=lambda r: r[8])
    print("\nTop 5 evaluated points by loss:")
    print(f"{'round':>5}{'bc_dec':>9}{'bc_inc':>9}{'stub':>7}{'comf_pp':>9}"
          f"{'feed_cap':>9}{'init_pp':>9}{'loss':>9}{'Q_repost':>10}")
    for rnd, seed, bc_dec, bc_inc, stub, comfort_pp, feed_capacity, initial_pp, loss, q in rows[:5]:
        print(f"{rnd:>5}{bc_dec:>9.4f}{bc_inc:>9.4f}{stub:>7.3f}{comfort_pp:>9.3f}"
              f"{feed_capacity:>9}{initial_pp:>9.3f}{loss:>9.3f}"
              f"{(q if q is not None else float('nan')):>10.4f}")
    print(f"\nFull log: {LOG_PATH}")


if __name__ == "__main__":
    main()
