"""
App-pol baseline calibration v2 (2026-07-21): 11-dim search + empirical 7-bin posting fit +
empirical initial-opinion distribution. Supersedes app_pol_baseline_bo_calibration.py /
_resume.py (5-dim, gamma-free-loss-checked but otherwise v7-inherited space; see
docs/report/2026-07-21-conduit-experiment-design.md for the full decision trail).

Changes from v1 (app_pol_baseline_bo_calibration.py):
1. init_dist=empirical (fixed, not searched): agents' intrinsic opinions are drawn directly from
   the real, asymmetric 7-bin survey distribution (Const.EMPIRICAL_OPINION_BIN_COUNTS -- Buntain &
   Snegovaya 2025 / OSF 10.17605/OSF.IO/KQFM6) instead of the symmetric mean-0 Gaussian default.
   Deliberately NOT symmetrized -- fitting to the real (liberal-skewed, ~2:1) shape directly avoids
   an arbitrary symmetrization choice.
2. New loss term: 7-bin posting-activity fit. Compares the model's cumulative post-count-by-bin
   proportions (Writer.writePostBin7 -> metrics/post_bin7.csv, binned by INTRINSIC opinion, whole
   run, population filter matching postOpinionVar) against Const.EMPIRICAL_POST_BIN_WEIGHTS'
   proportions. This scores the EXISTING postProb mechanism (comfort_pp/initial_pp etc., still free
   params below) against the real per-bin posting-activity shape -- including the empirically real,
   non-monotonic "somewhat" dip -- rather than replacing the posting mechanism itself (user
   decision, 2026-07-21: "just scoring with the existing mechanism").
3. Search space widened from 5 to 11 dims, reopening v1's (stage_joint_bo_calibration.py) six
   "never touched since" dims (max_follow, follow_prob, alpha, feed_capacity, initial_pp, stub) now
   that gamma_fit is confirmed not to have swung v1's original selection (retrospective check,
   same report entry) -- with three dims tightened (max_follow, alpha, stub -- user's proposal) and
   two widened past v1/v7's box edges (bc_dec -> 1.0, comfort_pp floor -> 0.1) specifically because
   the just-finished 5-dim run's winning point sat pinned on both those edges. bc_init (didn't exist
   in v1) added at v7's range.
4. out_of_bc_repost_prob still fixed (0.01, not searched) -- unchanged rationale: it IS the
   secession-experiment treatment channel, must not be re-optimized away by this baseline search.

Usage: python3 scripts/app_pol_baseline_bo_v2_empirical7bin.py
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

ROOT = Path(__file__).resolve().parent.parent
LIBCP = ":".join(str(p) for p in ROOT.glob("lib/*.jar")) + (":" if list(ROOT.glob("lib/*.jar")) else "") + str(ROOT / "bin")
N = 1000
STEPS = 20000
N_ROUNDS = 12
N_POINTS_PER_ROUND = 6
SEEDS_PER_POINT = 5
CONFIRM_SEEDS = 5
BASE_SEED = 1010000  # distinct from every prior run in this project

OOB_TREATMENT = 0.01  # fixed, not searched -- see module docstring

GINI_TARGET, GINI_SCALE = 0.8, 0.05
Q_TARGET, Q_SCALE = 0.48, 0.05
RATIO_TARGET, RATIO_SCALE = 1.225, 0.05
ASSORT_FLOOR, ASSORT_SCALE = 0.6, 0.15
BIN7_SCALE = 0.05  # per-bin proportion-difference scale, same convention as the other terms

# Const.EMPIRICAL_POST_BIN_WEIGHTS, normalized to proportions (see src/constants/Const.java).
EMPIRICAL_POST_BIN_PROPORTIONS = np.array(
    [4328.725, 2682.863, 1503.682, 2135.798, 691.065, 1156.761, 3742.547]
)
EMPIRICAL_POST_BIN_PROPORTIONS = EMPIRICAL_POST_BIN_PROPORTIONS / EMPIRICAL_POST_BIN_PROPORTIONS.sum()

SPACE = [
    Real(15, 50, name="max_follow"),          # tightened from v1's [15,100] (user)
    Real(0.01, 0.3, prior="log-uniform", name="follow_prob"),  # v1, unchanged
    Real(0.5, 1.0, name="alpha"),             # tightened from v1's [0.0,1.0] (user)
    Integer(1, 5, name="hop"),                # v1/v7, unchanged
    Real(0.5, 1.0, name="bc_dec"),             # widened from v7's [0.5,0.999] -- boundary fix
    Real(0.0, 0.3, name="bc_recovery"),       # v1/v7, unchanged
    Real(0.2, 1.0, name="bc_init"),           # v7 range; didn't exist in v1
    Real(0.5, 0.9, name="stub"),              # tightened from v1's [0.05,0.95] (user)
    Real(0.1, 3.0, name="comfort_pp"),        # widened from v7's [0.5,3.0] floor -- boundary fix
    Integer(5, 40, name="feed_capacity"),     # v1, unchanged
    Real(0.01, 0.5, name="initial_pp"),       # v1, unchanged
]
DIM_NAMES = [d.name for d in SPACE]

LOG_PATH = ROOT / "docs" / "report" / "app_pol_baseline_v2_bo_evaluations.csv"
CONFIRM_LOG_PATH = ROOT / "docs" / "report" / "app_pol_baseline_v2_bo_confirm.csv"
CCDF_LOG_PATH = ROOT / "docs" / "report" / "app_pol_baseline_v2_indegree_ccdf.csv"
CCDF_PLOT_PATH = ROOT / "docs" / "report" / "app_pol_baseline_v2_indegree_ccdf.png"


def gini(x):
    x = np.sort(np.asarray(x, dtype=float))
    n = len(x)
    if n == 0 or x.sum() == 0:
        return float("nan")
    cum = np.cumsum(x)
    return (2 * np.sum((np.arange(1, n + 1)) * x) - (n + 1) * cum[-1]) / (n * cum[-1])


def compute_point_loss(agg):
    def term(mean, std, target, scale):
        if mean is None:
            return 16.0 + 16.0
        mean_term = ((mean - target) / scale) ** 2
        std_term = (std / scale) ** 2
        return mean_term + std_term

    gini_t = term(agg["gini_mean"], agg["gini_std"], GINI_TARGET, GINI_SCALE)
    q_t = term(agg["q_sign_repost_mean"], agg["q_sign_repost_std"], Q_TARGET, Q_SCALE)
    ratio_t = term(agg["ratio_mean"], agg["ratio_std"], RATIO_TARGET, RATIO_SCALE)
    a_mean = agg["assort_mean"]
    assort_t = max(0.0, (ASSORT_FLOOR - a_mean) / ASSORT_SCALE) ** 2 if a_mean is not None else 16.0
    bin7_t = agg["bin7_loss_mean"] if agg["bin7_loss_mean"] is not None else 16.0
    return gini_t + q_t + ratio_t + assort_t + bin7_t


def bin7_loss(post_counts):
    """Sum of squared proportion differences vs. the empirical posting-activity target."""
    post_counts = np.asarray(post_counts, dtype=float)
    total = post_counts.sum()
    if total <= 0:
        return 49.0 / (BIN7_SCALE ** 2)  # worst case: max possible sq-diff (2.0) per bin, all 7
    model_props = post_counts / total
    diff = (model_props - EMPIRICAL_POST_BIN_PROPORTIONS) / BIN7_SCALE
    return float(np.sum(diff ** 2))


def launch(x, seed):
    max_follow, follow_prob, alpha, hop, bc_dec, bc_recovery, bc_init, stub, comfort_pp, feed_capacity, initial_pp = x
    tokens = [
        f"seed={seed}", "network=hk", f"n={N}", f"steps={STEPS}", "log_gexf=false",
        "init_dist=empirical",
        f"max_follow={max_follow:.4f}", f"follow_prob={follow_prob:.4f}",
        f"alpha={alpha:.4f}", f"hop={int(hop)}",
        f"bc_dec={bc_dec:.5f}", f"bc_recovery={bc_recovery:.5f}", f"bc_init={bc_init:.5f}",
        "stub_dist=uniform", f"stub_min={stub:.4f}", f"stub_max={stub:.4f}",
        f"comfort_pp={comfort_pp:.4f}", f"feed_capacity={int(feed_capacity)}",
        f"initial_pp={initial_pp:.4f}", "max_pp=1.0",
        f"out_of_bc_repost_prob={OOB_TREATMENT}", "force=true",
    ]
    logfile = ROOT / "logs" / f"app_pol_baseline_v2_seed{seed}.log"
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
    bin7_path = d / "metrics" / "post_bin7.csv"
    if not (deg_path.exists() and results_path.exists() and mod_path.exists() and bin7_path.exists()):
        return None
    with open(deg_path, newline="") as f:
        indeg = [int(r["inDegree"]) for r in csv.DictReader(f)]
    g = gini(indeg)
    with open(results_path, newline="") as f:
        last = list(csv.DictReader(f))[-1]
    assort = float(last["opinionAssortativity"])
    opinion_var = float(last["opinionVar"])
    post_var = float(last["postOpinionVar"])
    ratio = post_var / opinion_var if opinion_var > 0 else None
    q = None
    with open(mod_path, newline="") as f:
        for row in csv.DictReader(f):
            if int(row["step"]) == STEPS:
                q = float(row["Q_sign_repost"])
    with open(bin7_path, newline="") as f:
        post_counts = [int(r["postCount"]) for r in csv.DictReader(f)]
    b7l = bin7_loss(post_counts)
    if q is None or ratio is None:
        return None
    return g, indeg, assort, q, ratio, b7l, post_counts


def evaluate_seed(x, seed):
    p = launch(x, seed)
    p.wait()
    return read_metrics(seed)


def aggregate(metrics):
    agg = {}
    for name, i in [("gini", 0), ("assort", 2), ("q_sign_repost", 3), ("ratio", 4), ("bin7_loss", 5)]:
        vals = [m[i] for m in metrics if m[i] is not None]
        agg[name + "_mean"] = float(np.mean(vals)) if vals else None
        agg[name + "_std"] = float(np.std(vals)) if len(vals) > 1 else 0.0
    return agg


def evaluate_round(points, point_seeds):
    jobs = [(pt, seed) for pt, seeds in zip(points, point_seeds) for seed in seeds]
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(jobs)) as ex:
        flat_results = list(ex.map(lambda job: evaluate_seed(job[0], job[1]), jobs))

    results_by_point = []
    idx = 0
    for seeds in point_seeds:
        point_metrics = flat_results[idx:idx + len(seeds)]
        idx += len(seeds)
        ok = [m for m in point_metrics if m is not None]
        agg = aggregate(ok)
        point_loss = compute_point_loss(agg) if len(ok) >= 2 else 1e6
        results_by_point.append((point_loss, agg))
    return results_by_point


def write_ccdf(all_indeg):
    x = np.sort(np.asarray(all_indeg, dtype=float))[::-1]
    n = len(x)
    ccdf = (np.arange(1, n + 1)) / n
    with open(CCDF_LOG_PATH, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["in_degree", "ccdf"])
        seen = {}
        for deg, c in zip(x, ccdf):
            seen[float(deg)] = c
        for deg in sorted(seen.keys(), reverse=True):
            w.writerow([deg, seen[deg]])
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        plt.figure(figsize=(5, 4))
        plt.loglog(x[x > 0], ccdf[x > 0], marker=".", linestyle="none", markersize=3)
        plt.xlabel("in-degree (k)")
        plt.ylabel("P(K >= k)")
        plt.title("App-pol baseline v2: empirical in-degree CCDF (validation only)")
        plt.tight_layout()
        plt.savefig(CCDF_PLOT_PATH, dpi=150)
        plt.close()
    except Exception as e:
        print(f"(CCDF plot skipped: {type(e).__name__}: {e})")


def run_confirmation(best_point):
    print(f"\n=== Confirming best point with {CONFIRM_SEEDS} seeds: "
          f"{dict(zip(DIM_NAMES, best_point))} (out_of_bc_repost_prob={OOB_TREATMENT}) ===", flush=True)
    confirm_seeds = [BASE_SEED + 900000 + j for j in range(CONFIRM_SEEDS)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONFIRM_SEEDS) as ex:
        results = list(ex.map(lambda s: evaluate_seed(best_point, s), confirm_seeds))

    with open(CONFIRM_LOG_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["seed"] + DIM_NAMES + ["gini", "assort", "q_sign_repost", "ratio", "bin7_loss"])
        for seed, m in zip(confirm_seeds, results):
            row = [m[0], m[2], m[3], m[4], m[5]] if m is not None else [None] * 5
            writer.writerow([seed] + list(best_point) + row)

    ok = [m for m in results if m is not None]
    agg = aggregate(ok)
    point_loss = compute_point_loss(agg) if len(ok) >= 2 else float("nan")
    print(f"n={len(ok)}/{CONFIRM_SEEDS} succeeded")
    print(f"point_loss (mean-miss + variance-penalty) = {point_loss:.3f}")
    if agg["gini_mean"] is not None:
        print(f"gini   = {agg['gini_mean']:.4f} +/- {agg['gini_std']:.4f} (target {GINI_TARGET})")
    if agg["assort_mean"] is not None:
        print(f"assort = {agg['assort_mean']:.4f} +/- {agg['assort_std']:.4f} (floor {ASSORT_FLOOR})")
    if agg["q_sign_repost_mean"] is not None:
        print(f"Q_sign_repost = {agg['q_sign_repost_mean']:.4f} +/- {agg['q_sign_repost_std']:.4f} (target {Q_TARGET})")
    if agg["ratio_mean"] is not None:
        print(f"apparent-polarization ratio = {agg['ratio_mean']:.4f} +/- {agg['ratio_std']:.4f} (target [1.19,1.26])")
    if agg["bin7_loss_mean"] is not None:
        print(f"7-bin posting-fit loss = {agg['bin7_loss_mean']:.4f} +/- {agg['bin7_loss_std']:.4f} (0 = perfect match)")
    print(f"Full log: {CONFIRM_LOG_PATH}", flush=True)

    all_indeg = [d for m in ok for d in m[1]]
    if all_indeg:
        write_ccdf(all_indeg)
        print(f"CCDF (validation only, not in loss): {CCDF_LOG_PATH} / {CCDF_PLOT_PATH}", flush=True)

    if ok:
        pooled_bins = np.sum([m[6] for m in ok], axis=0)
        model_props = pooled_bins / pooled_bins.sum()
        print("\n7-bin posting proportions (model vs. empirical target):")
        for i in range(7):
            print(f"  bin {i}: model={model_props[i]:.4f}  empirical={EMPIRICAL_POST_BIN_PROPORTIONS[i]:.4f}")


def main():
    opt = Optimizer(SPACE, base_estimator="GP", acq_func="EI", random_state=41)

    rows = []
    with open(LOG_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["round", "point_idx", "seeds"] + DIM_NAMES +
                         ["point_loss", "gini_mean", "gini_std",
                          "assort_mean", "assort_std", "q_sign_repost_mean", "q_sign_repost_std",
                          "ratio_mean", "ratio_std", "bin7_loss_mean", "bin7_loss_std"])

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
                    point_loss, agg["gini_mean"], agg["gini_std"],
                    agg["assort_mean"], agg["assort_std"], agg["q_sign_repost_mean"], agg["q_sign_repost_std"],
                    agg["ratio_mean"], agg["ratio_std"], agg["bin7_loss_mean"], agg["bin7_loss_std"],
                ])
                rows.append((point_loss, pt))
            f.flush()
            best = min(r[0] for r in rows)
            print(f"[round {rnd}] done in {time.time()-t0:.0f}s, best point_loss so far = {best:.3f}", flush=True)

    rows.sort(key=lambda r: r[0])
    print("\nTop 5 points by point_loss:")
    for loss, pt in rows[:5]:
        print(f"  loss={loss:.3f}  {dict(zip(DIM_NAMES, pt))}")
    print(f"\nFull log: {LOG_PATH}")

    best_loss, best_point = rows[0]
    run_confirmation(best_point)


if __name__ == "__main__":
    main()
