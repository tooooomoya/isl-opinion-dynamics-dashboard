"""
Stage 2b: Bayesian-optimization calibration restart, on top of two fixes since the original
Stage 2 attempt aborted at round 0 (docs/report/stage2_bo_evaluations.csv, all 5 points near-zero
Q_sign_repost):

1. Stage 1b was re-calibrated (docs/report/2026-07-17-stage1b-redo2-plan.md) after feed-mechanism
   fixes: max_follow=30, follow_prob=0.015, alpha=0.75 (anchor), hop=4 (anchor) -- replaces the old
   max_follow=55/follow_prob=0.01/alpha=0.85/hop=4 this script's predecessor held fixed.
2. Repost is now permanently bc-gated (docs/report/2026-07-17-repost-bc-gating-decision.md):
   Agent.repost() used to couple the out-of-bc repost rate to repostProb by default
   (coupleOutOfBCRepost=true), making the bc gate a no-op -- this fully explained the round-0
   collapse (repost was opinion-blind by construction, not a bad parameter draw; see the decision
   doc's code trace). outOfBCRepostProb is now a real, load-bearing parameter and is added here as
   a 6th free dimension.

Calibrates bc_dec / stub / comfort_pp / feed_capacity / initial_pp / out_bc_repost_prob against the
repost network's structural fit (Q_sign_repost, Conover et al. 2011 ~0.7-0.8).

bcIncRate is NOT an independent dimension: bcIncRate = 1 + (1 - bcDecRate) / 10 (asymmetric
tolerance recovery at 1/10 the magnitude of decline, per the original Stage 2 design).

out_bc_repost_prob's box is [0, 0.1] -- bounded above by repostProb (fixed at its 0.1 default, not
swept here), so the search can't accidentally invert "selective amplification" into
out-of-bc-reposted-MORE-than-in-bc.

IMPORTANT: stub_dist=const ignores stub_min/stub_max entirely (uses the hardcoded
Const.INITIAL_STUBBORNNESS=0.7 regardless of CLI args). To sweep a constant stubbornness value X,
pass stub_dist=uniform stub_min=X stub_max=X (same workaround the original Stage 2 script used).

Methodology fix (docs/report/2026-07-15-calibration-decisions.md methodology note): single-seed BO
point estimates were found to be extremely noisy in the Stage-1c/1d work (5-seed mean losses 10-25x
the single-seed value). This script averages SEEDS_PER_POINT=2 seeds per evaluated point inside the
loop itself, rather than relying on a post-hoc confirmation pass to catch this after the fact.

Known limitation (carried over from the original Stage 2 script): 6 free parameters against
effectively 1 scalar target (Q_sign_repost) is underdetermined -- this run characterizes a
plausible region / best-found point, not a unique identified optimum.

Usage: python3 scripts/stage2b_bo_calibration.py
"""
import concurrent.futures
import csv
import subprocess
import time
from pathlib import Path

import numpy as np
from skopt import Optimizer
from skopt.space import Real, Integer

ROOT = Path(__file__).resolve().parent.parent
LIBCP = ":".join(str(p) for p in ROOT.glob("lib/*.jar")) + (":" if list(ROOT.glob("lib/*.jar")) else "") + str(ROOT / "bin")
N = 1000
STEPS = 15000
N_ROUNDS = 5
N_POINTS_PER_ROUND = 5
SEEDS_PER_POINT = 2
Q_TARGET, Q_SCALE = 0.75, 0.05  # Conover et al. 2011 ~0.7-0.8 midpoint

SPACE = [
    Real(0.9, 0.999, name="bc_dec"),
    Real(0.2, 0.8, name="stub"),
    Real(1.0, 1.5, name="comfort_pp"),
    Integer(5, 30, name="feed_capacity"),
    Real(0.05, 0.5, name="initial_pp"),
    Real(0.0, 0.1, name="out_bc_repost_prob"),
]

LOG_PATH = ROOT / "docs" / "report" / "stage2b_bo_evaluations.csv"
BASE_SEED = 60000  # seeds assigned as BASE_SEED + round*N_POINTS_PER_ROUND*SEEDS_PER_POINT + point_index*SEEDS_PER_POINT + seed_index


def launch(bc_dec, stub, comfort_pp, feed_capacity, initial_pp, out_bc_repost_prob, seed):
    bc_inc = 1.0 + (1.0 - bc_dec) / 10.0
    tokens = [
        f"seed={seed}", "network=hk", f"n={N}", f"steps={STEPS}", "log_gexf=false",
        "max_follow=30", "follow_prob=0.015", "alpha=0.75", "hop=4",  # Stage 1b (2026-07-17) calibrated, held fixed
        f"bc_dec={bc_dec:.5f}", f"bc_inc={bc_inc:.5f}",
        "stub_dist=uniform", f"stub_min={stub:.4f}", f"stub_max={stub:.4f}",
        f"comfort_pp={comfort_pp:.4f}", f"feed_capacity={feed_capacity}",
        f"initial_pp={initial_pp:.4f}", f"out_of_bc_repost_prob={out_bc_repost_prob:.4f}",
        "force=true",
    ]
    logfile = ROOT / "logs" / f"stage2b_bo_seed{seed}.log"
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


def evaluate_seed(x, seed):
    bc_dec, stub, comfort_pp, feed_capacity, initial_pp, out_bc_repost_prob = x
    p = launch(bc_dec, stub, comfort_pp, feed_capacity, initial_pp, out_bc_repost_prob, seed)
    p.wait()
    q = read_q_sign_repost(seed)
    if q is None:
        return 1e6, None
    loss = ((q - Q_TARGET) / Q_SCALE) ** 2
    return loss, q


def evaluate_round(points, point_seeds):
    """Flatten every (point, seed) pair in the round into one pool so all
    N_POINTS_PER_ROUND*SEEDS_PER_POINT JVMs run concurrently, not point-by-point."""
    jobs = [(pt, seed) for pt, seeds in zip(points, point_seeds) for seed in seeds]
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(jobs)) as ex:
        flat_results = list(ex.map(lambda job: evaluate_seed(job[0], job[1]), jobs))

    results_by_point = []
    idx = 0
    for seeds in point_seeds:
        point_results = flat_results[idx:idx + len(seeds)]
        idx += len(seeds)
        losses = [r[0] for r in point_results]
        qs = [r[1] for r in point_results if r[1] is not None]
        point_loss = float(np.mean(losses))
        q_mean = float(np.mean(qs)) if qs else None
        q_std = float(np.std(qs)) if len(qs) > 1 else 0.0
        results_by_point.append((point_loss, q_mean, q_std))
    return results_by_point


def main():
    opt = Optimizer(SPACE, base_estimator="GP", acq_func="EI", random_state=7)
    rows = []
    with open(LOG_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["round", "point_idx", "seeds", "bc_dec", "bc_inc", "stub", "comfort_pp",
                          "feed_capacity", "initial_pp", "out_bc_repost_prob",
                          "point_loss", "q_sign_repost_mean", "q_sign_repost_std"])

        for rnd in range(N_ROUNDS):
            t0 = time.time()
            points = opt.ask(n_points=N_POINTS_PER_ROUND)
            point_seeds = [
                [BASE_SEED + (rnd * N_POINTS_PER_ROUND + i) * SEEDS_PER_POINT + j
                 for j in range(SEEDS_PER_POINT)]
                for i in range(len(points))
            ]
            print(f"[round {rnd}] evaluating {len(points)} points x {SEEDS_PER_POINT} seeds "
                  f"({len(points) * SEEDS_PER_POINT} concurrent JVMs, seeds {point_seeds[0][0]}-{point_seeds[-1][-1]})...",
                  flush=True)

            point_results = evaluate_round(points, point_seeds)

            losses = [r[0] for r in point_results]
            opt.tell(points, losses)
            for i, (pt, seeds, (point_loss, q_mean, q_std)) in enumerate(zip(points, point_seeds, point_results)):
                bc_dec, stub, comfort_pp, feed_capacity, initial_pp, out_bc_repost_prob = pt
                bc_inc = 1.0 + (1.0 - bc_dec) / 10.0
                writer.writerow([rnd, i, ";".join(map(str, seeds)), bc_dec, bc_inc, stub, comfort_pp,
                                  feed_capacity, initial_pp, out_bc_repost_prob,
                                  point_loss, q_mean, q_std])
                rows.append((rnd, i, bc_dec, bc_inc, stub, comfort_pp, feed_capacity, initial_pp,
                             out_bc_repost_prob, point_loss, q_mean, q_std))
            f.flush()
            print(f"[round {rnd}] done in {time.time()-t0:.0f}s, "
                  f"best point_loss so far = {min(r[9] for r in rows):.3f}", flush=True)

    rows.sort(key=lambda r: r[9])
    print("\nTop 5 evaluated points by point_loss (mean over seeds):")
    print(f"{'round':>5}{'bc_dec':>9}{'bc_inc':>9}{'stub':>7}{'comf_pp':>9}"
          f"{'feed_cap':>9}{'init_pp':>9}{'outbc':>8}{'loss':>9}{'Q_mean':>9}{'Q_std':>8}")
    for rnd, i, bc_dec, bc_inc, stub, comfort_pp, feed_capacity, initial_pp, out_bc_repost_prob, loss, q_mean, q_std in rows[:5]:
        print(f"{rnd:>5}{bc_dec:>9.4f}{bc_inc:>9.4f}{stub:>7.3f}{comfort_pp:>9.3f}"
              f"{feed_capacity:>9}{initial_pp:>9.3f}{out_bc_repost_prob:>8.4f}{loss:>9.3f}"
              f"{(q_mean if q_mean is not None else float('nan')):>9.4f}{q_std:>8.4f}")
    print(f"\nFull log: {LOG_PATH}")


if __name__ == "__main__":
    main()
