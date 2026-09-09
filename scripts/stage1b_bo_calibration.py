"""
Stage 1b Bayesian-optimization calibration (systematic-A/B calibration plan).

Calibrates maxFollowCapacity/followProb/feedAlgoShare(alpha)/feedHopH(hop) against the emergent
(post-dynamics) follow-graph Gini coefficient (~0.8, Kwak et al. 2010) and in-degree power-law
exponent (~2.276, same source), on top of the Stage-1a-calibrated HK generator (m=15/A=4/pt=0.05,
now ExperimentConfig's default).

Design (approved 2026-07-16): GP-based Bayesian optimization via scikit-optimize, batched
ask/tell (n_points per round, evaluated in parallel) rather than a sequential loop, since each
simulation takes ~3.5 min at this scale and the machine has 32 cores. Each point is averaged over
2 seeds to damp simulation noise before being reported to the optimizer.

Loss (normalized/History-Matching-style implausibility measure):
    ((gini - 0.8) / 0.05)^2 + ((gamma_fit - 2.276) / 0.3) ^2
Known limitation (stated up front, not hidden): gamma_fit inherits the finite-size MLE bias
documented in Stage 1a (docs/report/calibration-sweep-results.md) — there is no analytic ground
truth for the emergent degree exponent to cross-check against here (unlike Stage 1a's pure
generator), so this loss can only rank candidates relative to each other under a consistent
(biased) measurement procedure, not certify an unbiased absolute match to Kwak et al.'s real-data
figure (measured on a network many orders of magnitude larger).

Usage: python3 scripts/stage1b_bo_calibration.py
"""
import csv
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from skopt import Optimizer
from skopt.space import Real, Integer

sys.path.insert(0, str(Path(__file__).parent.parent))
from dashboard.analysis import fit_powerlaw

ROOT = Path(__file__).resolve().parent.parent
LIBCP = ":".join(str(p) for p in ROOT.glob("lib/*.jar")) + (":" if list(ROOT.glob("lib/*.jar")) else "") + str(ROOT / "bin")
N = 1000
STEPS = 15000
SEEDS_PER_POINT = [0, 1]
N_ROUNDS = 5
N_POINTS_PER_ROUND = 6
GINI_TARGET, GINI_SCALE = 0.8, 0.05
GAMMA_TARGET, GAMMA_SCALE = 2.276, 0.3

SPACE = [
    Real(15, 100, name="max_follow"),
    Real(0.01, 0.3, prior="log-uniform", name="follow_prob"),
    Real(0.0, 1.0, name="alpha"),
    Integer(1, 5, name="hop"),
]

LOG_PATH = ROOT / "docs" / "report" / "stage1b_bo_evaluations.csv"
_seed_counter = [30000]  # unique global seed per individual java run, for unambiguous folder lookup


def gini(x):
    x = np.sort(np.asarray(x, dtype=float))
    n = len(x)
    if n == 0 or x.sum() == 0:
        return float("nan")
    cum = np.cumsum(x)
    return (2 * np.sum((np.arange(1, n + 1)) * x) - (n + 1) * cum[-1]) / (n * cum[-1])


def launch(max_follow, follow_prob, alpha, hop, seed):
    tokens = [
        f"seed={seed}", "network=hk", f"n={N}", f"steps={STEPS}", "log_gexf=false",
        f"max_follow={max_follow:.4f}", f"follow_prob={follow_prob:.4f}",
        f"alpha={alpha:.4f}", f"hop={hop}", "force=true",
    ]
    logfile = ROOT / "logs" / f"stage1b_bo_seed{seed}.log"
    logfile.parent.mkdir(exist_ok=True)
    with open(logfile, "w") as lf:
        p = subprocess.Popen(
            ["java", "-Xmx2g", "-cp", LIBCP, "dynamics.OpinionDynamics", *tokens],
            stdout=lf, stderr=subprocess.STDOUT, cwd=ROOT,
        )
    return p, seed


def read_result(seed):
    candidates = sorted(ROOT.glob(f"results/run_{seed}_*"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        return None
    d = candidates[-1]
    deg_path = d / "degrees" / f"degree_result_{STEPS}.csv"
    if not deg_path.exists():
        return None
    with open(deg_path, newline="") as f:
        indeg = [int(row["inDegree"]) for row in csv.DictReader(f)]
    g = gini(indeg)
    fit = fit_powerlaw(indeg)
    gamma_fit = fit.get("alpha")
    return g, gamma_fit


def evaluate_point(x):
    max_follow, follow_prob, alpha, hop = x
    procs = []
    for s in SEEDS_PER_POINT:
        seed = _seed_counter[0]
        _seed_counter[0] += 1
        procs.append((launch(max_follow, follow_prob, alpha, hop, seed)))
    ginis, gammas = [], []
    for p, seed in procs:
        p.wait()
        res = read_result(seed)
        if res is None:
            continue
        g, gf = res
        if g is not None and not np.isnan(g):
            ginis.append(g)
        if gf is not None:
            gammas.append(gf)
    if not ginis:
        return 1e6, None, None  # simulation failed; penalize heavily rather than crash the loop
    gini_mean = float(np.mean(ginis))
    gamma_mean = float(np.mean(gammas)) if gammas else None
    gamma_term = ((gamma_mean - GAMMA_TARGET) / GAMMA_SCALE) ** 2 if gamma_mean is not None else 4.0
    loss = ((gini_mean - GINI_TARGET) / GINI_SCALE) ** 2 + gamma_term
    return loss, gini_mean, gamma_mean


def main():
    opt = Optimizer(SPACE, base_estimator="GP", acq_func="EI", random_state=42)
    rows = []
    with open(LOG_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["round", "max_follow", "follow_prob", "alpha", "hop", "loss", "gini", "gamma_fit"])

        for rnd in range(N_ROUNDS):
            t0 = time.time()
            points = opt.ask(n_points=N_POINTS_PER_ROUND)
            print(f"[round {rnd}] evaluating {len(points)} points in parallel...", flush=True)
            # launch all points' seed-runs concurrently (this process just waits on subprocesses;
            # evaluate_point() itself blocks per-point, so run points via a thread pool to overlap)
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=N_POINTS_PER_ROUND) as ex:
                results = list(ex.map(evaluate_point, points))
            losses = [r[0] for r in results]
            opt.tell(points, losses)
            for pt, (loss, g, gf) in zip(points, results):
                mf, fp, al, hp = pt
                writer.writerow([rnd, mf, fp, al, hp, loss, g, gf])
                rows.append((rnd, mf, fp, al, hp, loss, g, gf))
            f.flush()
            print(f"[round {rnd}] done in {time.time()-t0:.0f}s, "
                  f"best loss so far = {min(r[5] for r in rows):.3f}", flush=True)

    rows.sort(key=lambda r: r[5])
    print("\nTop 5 evaluated points by loss:")
    print(f"{'round':>5}{'max_follow':>12}{'follow_prob':>13}{'alpha':>8}{'hop':>5}"
          f"{'loss':>10}{'gini':>10}{'gamma_fit':>11}")
    for rnd, mf, fp, al, hp, loss, g, gf in rows[:5]:
        print(f"{rnd:>5}{mf:>12.2f}{fp:>13.4f}{al:>8.3f}{hp:>5}{loss:>10.3f}"
              f"{(g if g is not None else float('nan')):>10.4f}"
              f"{(gf if gf is not None else float('nan')):>11.3f}")
    print(f"\nFull log: {LOG_PATH}")


if __name__ == "__main__":
    main()
