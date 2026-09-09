"""
Stage 1c: Bayesian optimization re-run of Stage 1b after the 2026-07-16 feed-mechanism fixes.

Since the Stage 1b (redo) run (docs/report/stage1b_redo_bo_evaluations.csv), three uncommitted
changes landed that change how alpha/hop shape the follow graph:
  1. bcGateAssim made permanent (docs/report/2026-07-16-bc-gated-assimilation-decision.md) --
     FJ assimilation now always averages only in-bc posts (was: whole feed by default). That
     decision doc explicitly flags stage1a/1b/2 as needing recalibration.
  2. AdminOptim.rankByVelocity now caches its ranking and only rescores every
     round(1/accessProb) steps instead of every step (docs/report/2026-07-16-feed-mechanism-
     design-review.md issue 1).
  3. chrono/For-You duplicate suppression switched from postId to rootPostId, removing an
     implicit repost-multiplicity weighting that used to leak into the "popularity-blind" chrono
     channel (same doc, issue 4).

Same targets and search space as the Stage 1b redo (docs/report/2026-07-17-stage1b-redo2-plan.md):
Gini~0.8, degree-exponent fit~2.276, opinionAssortativity floor 0.6, over
(max_follow, follow_prob, alpha, hop). Unlike the redo, this run does NOT warm-start from the
prior evaluation points -- those were scored under dynamics that no longer exist, and reusing them
would bias the GP posterior toward alpha/hop dependence that isn't real anymore (see plan doc).
5 rounds instead of 3 to compensate for the lost warm start.

Usage: python3 scripts/stage1c_bo_calibration.py
"""
import concurrent.futures
import csv
import subprocess
import sys
import time
import warnings
from pathlib import Path

import numpy as np
from skopt import Optimizer
from skopt.space import Real, Integer

warnings.filterwarnings("ignore")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dashboard.analysis import fit_powerlaw

ROOT = Path(__file__).resolve().parent.parent
LIBCP = ":".join(str(p) for p in ROOT.glob("lib/*.jar")) + (":" if list(ROOT.glob("lib/*.jar")) else "") + str(ROOT / "bin")
N = 1000
STEPS = 15000
N_ROUNDS = 5
N_POINTS_PER_ROUND = 5
GINI_TARGET, GINI_SCALE = 0.8, 0.05
GAMMA_TARGET, GAMMA_SCALE = 2.276, 0.3
ASSORT_FLOOR, ASSORT_SCALE = 0.6, 0.15

SPACE = [
    Real(15, 100, name="max_follow"),
    Real(0.01, 0.3, prior="log-uniform", name="follow_prob"),
    Real(0.0, 1.0, name="alpha"),
    Integer(1, 5, name="hop"),
]

LOG_PATH = ROOT / "docs" / "report" / "stage1c_bo_evaluations.csv"
BASE_SEED = 80000


def gini(x):
    x = np.sort(np.asarray(x, dtype=float))
    n = len(x)
    if n == 0 or x.sum() == 0:
        return float("nan")
    cum = np.cumsum(x)
    return (2 * np.sum((np.arange(1, n + 1)) * x) - (n + 1) * cum[-1]) / (n * cum[-1])


def compute_loss(g, gf, assort):
    gamma_term = ((gf - GAMMA_TARGET) / GAMMA_SCALE) ** 2 if gf is not None else 4.0
    assort_term = max(0.0, (ASSORT_FLOOR - assort) / ASSORT_SCALE) ** 2
    return ((g - GINI_TARGET) / GINI_SCALE) ** 2 + gamma_term + assort_term


def launch(max_follow, follow_prob, alpha, hop, seed):
    tokens = [
        f"seed={seed}", "network=hk", f"n={N}", f"steps={STEPS}", "log_gexf=false",
        f"max_follow={max_follow:.4f}", f"follow_prob={follow_prob:.4f}",
        f"alpha={alpha:.4f}", f"hop={hop}", "force=true",
    ]
    logfile = ROOT / "logs" / f"stage1c_seed{seed}.log"
    logfile.parent.mkdir(exist_ok=True)
    with open(logfile, "w") as lf:
        p = subprocess.Popen(
            ["java", "-Xmx2g", "-cp", LIBCP, "dynamics.OpinionDynamics", *tokens],
            stdout=lf, stderr=subprocess.STDOUT, cwd=ROOT,
        )
    return p


def evaluate_point(theta, seed):
    max_follow, follow_prob, alpha, hop = theta
    p = launch(max_follow, follow_prob, alpha, hop, seed)
    p.wait()
    candidates = sorted(ROOT.glob(f"results/run_{seed}_*"), key=lambda x: x.stat().st_mtime)
    if not candidates:
        return 1e6, None, None, None
    d = candidates[-1]
    deg_path = d / "degrees" / f"degree_result_{STEPS}.csv"
    if not deg_path.exists():
        return 1e6, None, None, None
    with open(deg_path, newline="") as f:
        indeg = [int(r["inDegree"]) for r in csv.DictReader(f)]
    g = gini(indeg)
    gf = fit_powerlaw(indeg).get("alpha")
    with open(d / "metrics" / "results.csv", newline="") as f:
        last = list(csv.DictReader(f))[-1]
    assort = float(last["opinionAssortativity"])
    return compute_loss(g, gf, assort), g, gf, assort


def main():
    opt = Optimizer(SPACE, base_estimator="GP", acq_func="EI", random_state=99)

    rows = []
    with open(LOG_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["round", "seed", "max_follow", "follow_prob", "alpha", "hop",
                          "loss", "gini", "gamma_fit", "opinion_assortativity"])

        for rnd in range(N_ROUNDS):
            t0 = time.time()
            points = opt.ask(n_points=N_POINTS_PER_ROUND)
            seeds = [BASE_SEED + rnd * N_POINTS_PER_ROUND + i for i in range(len(points))]
            print(f"[round {rnd}] evaluating {len(points)} points in parallel "
                  f"(seeds {seeds[0]}-{seeds[-1]})...", flush=True)

            with concurrent.futures.ThreadPoolExecutor(max_workers=N_POINTS_PER_ROUND) as ex:
                results = list(ex.map(lambda ps: evaluate_point(*ps), zip(points, seeds)))

            losses = [r[0] for r in results]
            opt.tell(points, losses)
            for pt, seed, (loss, g, gf, assort) in zip(points, seeds, results):
                mf, fp, al, hp = pt
                writer.writerow([rnd, seed, mf, fp, al, hp, loss, g, gf, assort])
                rows.append((rnd, seed, mf, fp, al, hp, loss, g, gf, assort))
            f.flush()
            best = min(r[6] for r in rows)
            print(f"[round {rnd}] done in {time.time()-t0:.0f}s, best loss so far = {best:.3f}", flush=True)

    rows.sort(key=lambda r: r[6])
    print("\nTop 5 evaluated points by loss:")
    print(f"{'round':>5}{'max_follow':>12}{'follow_prob':>13}{'alpha':>8}{'hop':>5}"
          f"{'loss':>9}{'gini':>9}{'gamma':>9}{'assort':>9}")
    for rnd, seed, mf, fp, al, hp, loss, g, gf, assort in rows[:5]:
        print(f"{rnd:>5}{mf:>12.2f}{fp:>13.4f}{al:>8.3f}{hp:>5}{loss:>9.3f}"
              f"{(g or float('nan')):>9.4f}{(gf or float('nan')):>9.3f}{(assort or float('nan')):>9.4f}")
    print(f"\nFull log: {LOG_PATH}")


if __name__ == "__main__":
    main()
