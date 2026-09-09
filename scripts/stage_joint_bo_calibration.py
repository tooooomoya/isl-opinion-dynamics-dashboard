"""
Joint Stage 1 + bc-mechanism + Stage 2 calibration (2026-07-18).

Supersedes the staged Stage 1 (follow-graph: max_follow/follow_prob/alpha/hop) -> Stage 2
(repost-network: bc_dec/stub/comfort_pp/feed_capacity/initial_pp) split. That split broke when
Agent.java's bc update was redesigned from a symmetric multiplicative ratchet (bc *= bcIncRate on
comfortable contact) to content-independent mean-reversion (bc += bcRecoveryRate * (bcInit - bc)),
docs/report/2026-07-18-bc-pp-boundary-collapse-diagnosis.md. A quick recheck of Stage 1c/1d's
calibrated point (max_follow=29.32, follow_prob=0.0145, alpha=0.763, hop=4) under the new bc
mechanism's defaults found gamma_fit collapsed from 2.357 to ~1.39 (2 seeds, well outside the
existing noise band) -- bc gates unfollowing (Agent.java ~530), so it feeds the follow-graph shape
directly, unlike the repost-bc-gating change which had no such path back into Stage 1's metrics.
User decision (2026-07-18): fold everything into one joint search rather than re-doing Stage 1
standalone and re-discovering the same coupling in Stage 2 again.

out_of_bc_repost_prob is NOT swept here (user decision, 2026-07-18) -- fixed at 0.0.

No warm start: none of Stage 1b/1c/1d's or Stage 2b/c/d's evaluation points are valid observations
of this loss surface (different bc mechanism entirely, plus bc_recovery is a new, previously-unswept
dimension) -- same reasoning as the Stage 1b -> Stage 1c warm-start exclusion.

Usage: python3 scripts/stage_joint_bo_calibration.py
"""
import concurrent.futures
import csv
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from skopt import Optimizer
from skopt.space import Real, Integer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dashboard.analysis import fit_powerlaw

ROOT = Path(__file__).resolve().parent.parent
LIBCP = ":".join(str(p) for p in ROOT.glob("lib/*.jar")) + (":" if list(ROOT.glob("lib/*.jar")) else "") + str(ROOT / "bin")
N = 1000
STEPS = 15000
N_ROUNDS = 8
N_POINTS_PER_ROUND = 6
SEEDS_PER_POINT = 3
CONFIRM_SEEDS = 5
BASE_SEED = 100000

GINI_TARGET, GINI_SCALE = 0.8, 0.05
GAMMA_TARGET, GAMMA_SCALE = 2.276, 0.3
ASSORT_FLOOR, ASSORT_SCALE = 0.6, 0.15
Q_TARGET, Q_SCALE = 0.48, 0.05  # Conover et al. 2011 p.91 (docs/report/2026-07-17-stage2-target-correction.md)

SPACE = [
    Real(15, 100, name="max_follow"),
    Real(0.01, 0.3, prior="log-uniform", name="follow_prob"),
    Real(0.0, 1.0, name="alpha"),
    Integer(1, 5, name="hop"),
    Real(0.7, 0.999, name="bc_dec"),
    Real(0.0, 0.3, name="bc_recovery"),
    Real(0.05, 0.95, name="stub"),
    Real(1.0, 2.0, name="comfort_pp"),
    Integer(5, 40, name="feed_capacity"),
    Real(0.01, 0.5, name="initial_pp"),
]
DIM_NAMES = [d.name for d in SPACE]

LOG_PATH = ROOT / "docs" / "report" / "stage_joint_bo_evaluations.csv"
CONFIRM_LOG_PATH = ROOT / "docs" / "report" / "stage_joint_confirm.csv"


def gini(x):
    x = np.sort(np.asarray(x, dtype=float))
    n = len(x)
    if n == 0 or x.sum() == 0:
        return float("nan")
    cum = np.cumsum(x)
    return (2 * np.sum((np.arange(1, n + 1)) * x) - (n + 1) * cum[-1]) / (n * cum[-1])


def compute_loss(g, gf, assort, q):
    gamma_term = ((gf - GAMMA_TARGET) / GAMMA_SCALE) ** 2 if gf is not None else 16.0
    assort_term = max(0.0, (ASSORT_FLOOR - assort) / ASSORT_SCALE) ** 2
    q_term = ((q - Q_TARGET) / Q_SCALE) ** 2
    return ((g - GINI_TARGET) / GINI_SCALE) ** 2 + gamma_term + assort_term + q_term


def launch(x, seed):
    max_follow, follow_prob, alpha, hop, bc_dec, bc_recovery, stub, comfort_pp, feed_capacity, initial_pp = x
    tokens = [
        f"seed={seed}", "network=hk", f"n={N}", f"steps={STEPS}", "log_gexf=false",
        f"max_follow={max_follow:.4f}", f"follow_prob={follow_prob:.4f}",
        f"alpha={alpha:.4f}", f"hop={int(hop)}",
        f"bc_dec={bc_dec:.5f}", f"bc_recovery={bc_recovery:.5f}",
        "stub_dist=uniform", f"stub_min={stub:.4f}", f"stub_max={stub:.4f}",
        f"comfort_pp={comfort_pp:.4f}", f"feed_capacity={int(feed_capacity)}",
        f"initial_pp={initial_pp:.4f}", "out_of_bc_repost_prob=0.0",
        "force=true",
    ]
    logfile = ROOT / "logs" / f"stage_joint_bo_seed{seed}.log"
    logfile.parent.mkdir(exist_ok=True)
    with open(logfile, "w") as lf:
        p = subprocess.Popen(
            ["java", "-Xmx2g", "-cp", LIBCP, "dynamics.OpinionDynamics", *tokens],
            stdout=lf, stderr=subprocess.STDOUT, cwd=ROOT,
        )
    return p


def read_metrics(seed):
    candidates = sorted(ROOT.glob(f"results/run_{seed}_*"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        return None
    d = candidates[-1]
    deg_path = d / "degrees" / f"degree_result_{STEPS}.csv"
    results_path = d / "metrics" / "results.csv"
    mod_path = d / "metrics" / "modularity.csv"
    if not (deg_path.exists() and results_path.exists() and mod_path.exists()):
        return None
    with open(deg_path, newline="") as f:
        indeg = [int(r["inDegree"]) for r in csv.DictReader(f)]
    g = gini(indeg)
    gf = fit_powerlaw(indeg).get("alpha")
    with open(results_path, newline="") as f:
        last = list(csv.DictReader(f))[-1]
    assort = float(last["opinionAssortativity"])
    q = None
    with open(mod_path, newline="") as f:
        for row in csv.DictReader(f):
            if int(row["step"]) == STEPS:
                q = float(row["Q_sign_repost"])
    if q is None:
        return None
    return g, gf, assort, q


def evaluate_seed(x, seed):
    p = launch(x, seed)
    p.wait()
    m = read_metrics(seed)
    if m is None:
        return 1e6, (None, None, None, None)
    g, gf, assort, q = m
    return compute_loss(g, gf, assort, q), (g, gf, assort, q)


def evaluate_round(points, point_seeds):
    jobs = [(pt, seed) for pt, seeds in zip(points, point_seeds) for seed in seeds]
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(jobs)) as ex:
        flat_results = list(ex.map(lambda job: evaluate_seed(job[0], job[1]), jobs))

    results_by_point = []
    idx = 0
    for seeds in point_seeds:
        point_results = flat_results[idx:idx + len(seeds)]
        idx += len(seeds)
        losses = [r[0] for r in point_results]
        metrics = [r[1] for r in point_results if r[1][0] is not None]
        point_loss = float(np.mean(losses))
        agg = {}
        for name, i in [("gini", 0), ("gamma_fit", 1), ("assort", 2), ("q_sign_repost", 3)]:
            vals = [m[i] for m in metrics if m[i] is not None]
            agg[name + "_mean"] = float(np.mean(vals)) if vals else None
            agg[name + "_std"] = float(np.std(vals)) if len(vals) > 1 else 0.0
        results_by_point.append((point_loss, agg))
    return results_by_point


def run_confirmation(best_point):
    print(f"\n=== Confirming best point with {CONFIRM_SEEDS} seeds: "
          f"{dict(zip(DIM_NAMES, best_point))} ===", flush=True)
    confirm_seeds = [BASE_SEED + 900000 + j for j in range(CONFIRM_SEEDS)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONFIRM_SEEDS) as ex:
        results = list(ex.map(lambda s: evaluate_seed(best_point, s), confirm_seeds))

    with open(CONFIRM_LOG_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["seed"] + DIM_NAMES + ["loss", "gini", "gamma_fit", "assort", "q_sign_repost"])
        for seed, (loss, (g, gf, assort, q)) in zip(confirm_seeds, results):
            writer.writerow([seed] + list(best_point) + [loss, g, gf, assort, q])

    losses = np.array([r[0] for r in results])
    ginis = np.array([r[1][0] for r in results if r[1][0] is not None])
    gammas = np.array([r[1][1] for r in results if r[1][1] is not None])
    assorts = np.array([r[1][2] for r in results if r[1][2] is not None])
    qs = np.array([r[1][3] for r in results if r[1][3] is not None])
    print(f"n={len(ginis)}/{CONFIRM_SEEDS} succeeded")
    print(f"loss   = {losses.mean():.3f} +/- {losses.std():.3f}")
    if len(ginis):
        print(f"gini   = {ginis.mean():.4f} +/- {ginis.std():.4f} (target {GINI_TARGET})")
    if len(gammas):
        print(f"gamma  = {gammas.mean():.3f} +/- {gammas.std():.3f} (target {GAMMA_TARGET})")
    if len(assorts):
        print(f"assort = {assorts.mean():.4f} +/- {assorts.std():.4f} (floor {ASSORT_FLOOR})")
    if len(qs):
        print(f"Q_sign_repost = {qs.mean():.4f} +/- {qs.std():.4f} (target {Q_TARGET})")
    print(f"Full log: {CONFIRM_LOG_PATH}", flush=True)


def main():
    opt = Optimizer(SPACE, base_estimator="GP", acq_func="EI", random_state=17)

    rows = []
    with open(LOG_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["round", "point_idx", "seeds"] + DIM_NAMES +
                         ["point_loss", "gini_mean", "gini_std", "gamma_fit_mean", "gamma_fit_std",
                          "assort_mean", "assort_std", "q_sign_repost_mean", "q_sign_repost_std"])

        for rnd in range(N_ROUNDS):
            t0 = time.time()
            points = opt.ask(n_points=N_POINTS_PER_ROUND)
            point_seeds = [
                [BASE_SEED + (rnd * N_POINTS_PER_ROUND + i) * SEEDS_PER_POINT + j
                 for j in range(SEEDS_PER_POINT)]
                for i in range(len(points))
            ]
            print(f"[round {rnd}] evaluating {len(points)} points x {SEEDS_PER_POINT} seeds "
                  f"({len(points) * SEEDS_PER_POINT} concurrent JVMs, "
                  f"seeds {point_seeds[0][0]}-{point_seeds[-1][-1]})...", flush=True)

            point_results = evaluate_round(points, point_seeds)
            losses = [r[0] for r in point_results]
            opt.tell(points, losses)

            for i, (pt, seeds, (point_loss, agg)) in enumerate(zip(points, point_seeds, point_results)):
                writer.writerow([rnd, i, ";".join(map(str, seeds))] + list(pt) + [
                    point_loss, agg["gini_mean"], agg["gini_std"], agg["gamma_fit_mean"], agg["gamma_fit_std"],
                    agg["assort_mean"], agg["assort_std"], agg["q_sign_repost_mean"], agg["q_sign_repost_std"],
                ])
                rows.append((point_loss, pt))
            f.flush()
            best = min(r[0] for r in rows)
            print(f"[round {rnd}] done in {time.time()-t0:.0f}s, best point_loss so far = {best:.3f}", flush=True)

    rows.sort(key=lambda r: r[0])
    print("\nTop 5 points by point_loss (mean over seeds):")
    for loss, pt in rows[:5]:
        print(f"  loss={loss:.3f}  {dict(zip(DIM_NAMES, pt))}")
    print(f"\nFull log: {LOG_PATH}")

    best_loss, best_point = rows[0]
    run_confirmation(best_point)


if __name__ == "__main__":
    main()
