"""
Stage 2c: Bayesian-optimization calibration, on top of two fixes since Stage 2b
(docs/report/stage2b_bo_evaluations.csv):

1. Target corrected 0.75 -> 0.48 (docs/report/2026-07-17-stage2-target-correction.md): the prior
   "Conover et al. 2011 ~0.7-0.8" target was never verified against the primary source. Reading
   the actual paper (docs/reference/Political Polarization on Twitter.pdf, p.91) gives "The
   modularity induced by the communities in the retweet and mention networks have values of 0.48
   and 0.17, respectively" -- 0.48 is the real number, not 0.7-0.8. (Caveat: that 0.48 is from
   algorithmic community detection, not a strict sign-partition modularity like Q_sign_repost, so
   treat it as an order-of-magnitude anchor, not an exact target.)
2. Stage 2b's best point had up to 5 of 6 dimensions pinned at search-box boundaries (bc_dec=0.90
   [lower], stub=0.20 [lower], comfort_pp=1.50 [upper], feed_capacity=30 [upper], initial_pp=0.05
   [lower]) -- same boundary-pinning pattern as Stage 1c. Widened here (all bounds safe to widen:
   Agent.java clamps bc to [bcFloor,bcCeiling] and postProb to [minPostProb,maxPostProb]
   regardless of how extreme bc_dec/comfort_pp get):
     bc_dec:        [0.9, 0.999]  -> [0.7, 0.999]
     stub:          [0.2, 0.8]    -> [0.05, 0.8]
     comfort_pp:    [1.0, 1.5]    -> [1.0, 2.0]
     feed_capacity: [5, 30]       -> [5, 40]
     initial_pp:    [0.05, 0.5]   -> [0.01, 0.5]
     out_bc_repost_prob: [0, 0.1] -> unchanged (0 is a genuine floor, not an artifact)

Also: SEEDS_PER_POINT raised 2 -> 5 (user requirement, 2 was shown to be too noisy -- Stage 2b's
round4 point0 vs point1 differed only in initial_pp yet gave Q_mean 0.033 vs 0.355, a 10x swing
that 2 seeds can't distinguish from noise).

Warm-started from all 25 of Stage 2b's evaluated points, rescored under the new target: unlike the
stage1b_redo -> stage1c transition (dynamics changed, discarded), NO simulation dynamics changed
between Stage 2b and this run -- only the target value and the box widened -- so those points are
valid observations of the same loss surface's sub-region (same logic as stage1c -> stage1d).

Usage: python3 scripts/stage2c_bo_calibration.py
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
SEEDS_PER_POINT = 5
Q_TARGET, Q_SCALE = 0.48, 0.05  # Conover et al. 2011, p.91 (verified against primary source)

SPACE = [
    Real(0.7, 0.999, name="bc_dec"),
    Real(0.05, 0.8, name="stub"),
    Real(1.0, 2.0, name="comfort_pp"),
    Integer(5, 40, name="feed_capacity"),
    Real(0.01, 0.5, name="initial_pp"),
    Real(0.0, 0.1, name="out_bc_repost_prob"),
]

WARM_START_CSV = ROOT / "docs" / "report" / "stage2b_bo_evaluations.csv"
LOG_PATH = ROOT / "docs" / "report" / "stage2c_bo_evaluations.csv"
BASE_SEED = 70000


def compute_loss(q):
    return ((q - Q_TARGET) / Q_SCALE) ** 2


def warm_start_points():
    """Stage 2b's 25 evaluated points, rescored under the corrected target -- same loss surface
    (no dynamics change since Stage 2b), just a different target and a wider box."""
    pts, losses = [], []
    with open(WARM_START_CSV, newline="") as f:
        for row in csv.DictReader(f):
            q = row["q_sign_repost_mean"]
            if not q:
                continue
            theta = [float(row["bc_dec"]), float(row["stub"]), float(row["comfort_pp"]),
                     int(row["feed_capacity"]), float(row["initial_pp"]), float(row["out_bc_repost_prob"])]
            pts.append(theta)
            losses.append(compute_loss(float(q)))
    return pts, losses


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
    logfile = ROOT / "logs" / f"stage2c_bo_seed{seed}.log"
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
    return compute_loss(q), q


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
    opt = Optimizer(SPACE, base_estimator="GP", acq_func="EI", random_state=11)

    warm_pts, warm_losses = warm_start_points()
    print(f"Warm-starting with {len(warm_pts)} rescored points from Stage 2b", flush=True)
    if warm_pts:
        opt.tell(warm_pts, warm_losses)
        print(f"  best warm-start loss = {min(warm_losses):.3f}", flush=True)

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
            best = min(warm_losses + [r[9] for r in rows]) if warm_losses else min(r[9] for r in rows)
            print(f"[round {rnd}] done in {time.time()-t0:.0f}s, best point_loss so far = {best:.3f}", flush=True)

    rows.sort(key=lambda r: r[9])
    print("\nTop 5 new evaluated points by point_loss (mean over seeds):")
    print(f"{'round':>5}{'bc_dec':>9}{'bc_inc':>9}{'stub':>7}{'comf_pp':>9}"
          f"{'feed_cap':>9}{'init_pp':>9}{'outbc':>8}{'loss':>9}{'Q_mean':>9}{'Q_std':>8}")
    for rnd, i, bc_dec, bc_inc, stub, comfort_pp, feed_capacity, initial_pp, out_bc_repost_prob, loss, q_mean, q_std in rows[:5]:
        print(f"{rnd:>5}{bc_dec:>9.4f}{bc_inc:>9.4f}{stub:>7.3f}{comfort_pp:>9.3f}"
              f"{feed_capacity:>9}{initial_pp:>9.3f}{out_bc_repost_prob:>8.4f}{loss:>9.3f}"
              f"{(q_mean if q_mean is not None else float('nan')):>9.4f}{q_std:>8.4f}")
    print(f"\nFull log: {LOG_PATH}")


if __name__ == "__main__":
    main()
