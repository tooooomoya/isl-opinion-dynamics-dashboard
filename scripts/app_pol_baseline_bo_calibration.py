"""
App-pol baseline calibration (2026-07-21): find "the condition where app-pol happens" for the
moderate-hub secession experiment (docs/report/2026-07-21-conduit-experiment-design.md).

Direct adaptation of scripts/stage_joint_bo_v7_robust.py (same search space, same joint
Gini+Q_sign_repost+assort+SF1 loss with variance penalties) with exactly one substantive change:
out_of_bc_repost_prob is FIXED at 0.05 -> 0.01 (2026-07-21 decision: repost_prob=0.1 (in-bc) :
out_of_bc_repost_prob=0.01 (out-of-bc), a ~10x asymmetry approximating the empirical ~13x ratio
from Wojcieszak et al. 2022 (Science Advances) for in-group vs out-group content sharing) instead
of v7's out_of_bc_repost_prob=0.0. This calibrates the OTHER free knobs (hop, bc_dec, bc_recovery,
bc_init, comfort_pp) conditional on the out-of-bc repost channel being live, on the organic
(hub-present, NOT swapped) network -- out_of_bc_repost_prob itself is deliberately NOT a free/
searched parameter here (it IS the treatment channel for the later secession experiment; letting
the search re-tune it would just fight the manipulation, reproducing the hub-identity-vs-conduit-
activity confound already flagged for the original hub-swap series).

Including SF1 (apparent-polarization ratio) in this loss is legitimate here specifically because
this step establishes a PRECONDITION (does realistic app-pol emerge at all, with moderate hubs
present in their organic/unswapped state?), not the treatment CONTRAST under test. The causal
question -- does seceding the moderate hubs (swap to extreme, same methodology as the 2026-07-18
hub-swap series) move SF1 away from this calibrated point? -- is answered by measuring afterward,
not by fitting the swapped configuration itself (see the "how about do calibration with app-pol"
exchange in the report for why that would be circular).

Gini stays a scalar calibration target here (2026-07-21 decision: not replaced with a CCDF-fit
loss -- no real, lightweight empirical reference distribution was available to fit against; see the
report's CCDF discussion). Instead, after confirmation, this script writes out the confirmed
point's empirical in-degree CCDF as a validation artifact (CSV, log-log PNG) -- descriptive only,
not part of the loss.

Usage: python3 scripts/app_pol_baseline_bo_calibration.py
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
N_ROUNDS = 8
N_POINTS_PER_ROUND = 6
SEEDS_PER_POINT = 5
CONFIRM_SEEDS = 5
BASE_SEED = 990000  # distinct from v7 (840000) and the oob OAT scan (970000) -- avoid folder collisions

OOB_TREATMENT = 0.01  # 2026-07-21 decision: fixed, not searched (see module docstring)

GINI_TARGET, GINI_SCALE = 0.8, 0.05
Q_TARGET, Q_SCALE = 0.48, 0.05
RATIO_TARGET, RATIO_SCALE = 1.225, 0.05  # SF1, JCSS-TomoyaTakeda2026.pdf Section 4.2
ASSORT_FLOOR, ASSORT_SCALE = 0.6, 0.15  # one-sided floor, same as v7

# Fixed at v1-calibrated defaults -- never implicated in any instability/pinning across v1-v7.
FIXED_MAX_FOLLOW = 57
FIXED_FOLLOW_PROB = 0.009
FIXED_ALPHA = 0.76
FIXED_FEED_CAPACITY = 15
FIXED_INITIAL_PP = 0.21
FIXED_STUB = 0.69
FIXED_MAX_POST_PROB = 1.0

SPACE = [
    Integer(1, 5, name="hop"),
    Real(0.5, 0.999, name="bc_dec"),
    Real(0.0, 0.3, name="bc_recovery"),
    Real(0.2, 1.0, name="bc_init"),
    Real(0.5, 3.0, name="comfort_pp"),
]
DIM_NAMES = [d.name for d in SPACE]

LOG_PATH = ROOT / "docs" / "report" / "app_pol_baseline_bo_evaluations.csv"
CONFIRM_LOG_PATH = ROOT / "docs" / "report" / "app_pol_baseline_bo_confirm.csv"
CCDF_LOG_PATH = ROOT / "docs" / "report" / "app_pol_baseline_indegree_ccdf.csv"
CCDF_PLOT_PATH = ROOT / "docs" / "report" / "app_pol_baseline_indegree_ccdf.png"


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
    return gini_t + q_t + ratio_t + assort_t


def launch(x, seed):
    hop, bc_dec, bc_recovery, bc_init, comfort_pp = x
    tokens = [
        f"seed={seed}", "network=hk", f"n={N}", f"steps={STEPS}", "log_gexf=false",
        f"max_follow={FIXED_MAX_FOLLOW}", f"follow_prob={FIXED_FOLLOW_PROB}",
        f"alpha={FIXED_ALPHA}", f"hop={int(hop)}",
        f"bc_dec={bc_dec:.5f}", f"bc_recovery={bc_recovery:.5f}", f"bc_init={bc_init:.5f}",
        "stub_dist=uniform", f"stub_min={FIXED_STUB}", f"stub_max={FIXED_STUB}",
        f"comfort_pp={comfort_pp:.4f}", f"feed_capacity={FIXED_FEED_CAPACITY}",
        f"initial_pp={FIXED_INITIAL_PP}", f"max_pp={FIXED_MAX_POST_PROB}",
        f"out_of_bc_repost_prob={OOB_TREATMENT}", "force=true",
    ]
    logfile = ROOT / "logs" / f"app_pol_baseline_seed{seed}.log"
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
    if q is None or ratio is None:
        return None
    return g, indeg, assort, q, ratio


def evaluate_seed(x, seed):
    p = launch(x, seed)
    p.wait()
    return read_metrics(seed)  # (g, indeg, assort, q, ratio) or None


def aggregate(metrics):
    agg = {}
    for name, i in [("gini", 0), ("assort", 2), ("q_sign_repost", 3), ("ratio", 4)]:
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
    """Validation-only artifact: empirical in-degree CCDF of the confirmed point, pooled across
    confirm seeds. NOT part of the calibration loss (Gini stays the scalar target there --
    2026-07-21 decision, see module docstring)."""
    x = np.sort(np.asarray(all_indeg, dtype=float))[::-1]
    n = len(x)
    ccdf = (np.arange(1, n + 1)) / n
    with open(CCDF_LOG_PATH, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["in_degree", "ccdf"])
        # collapse to distinct degree values (last CCDF value at each degree tier)
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
        plt.title("App-pol baseline: empirical in-degree CCDF (validation only)")
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
        writer.writerow(["seed"] + DIM_NAMES + ["gini", "assort", "q_sign_repost", "ratio"])
        for seed, m in zip(confirm_seeds, results):
            row = [m[0], m[2], m[3], m[4]] if m is not None else [None] * 4
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
    print(f"Full log: {CONFIRM_LOG_PATH}", flush=True)

    all_indeg = [d for m in ok for d in m[1]]
    if all_indeg:
        write_ccdf(all_indeg)
        print(f"CCDF (validation only, not in loss): {CCDF_LOG_PATH} / {CCDF_PLOT_PATH}", flush=True)


def main():
    opt = Optimizer(SPACE, base_estimator="GP", acq_func="EI", random_state=41)

    rows = []
    with open(LOG_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["round", "point_idx", "seeds"] + DIM_NAMES +
                         ["point_loss", "gini_mean", "gini_std",
                          "assort_mean", "assort_std", "q_sign_repost_mean", "q_sign_repost_std",
                          "ratio_mean", "ratio_std"])

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
                    agg["ratio_mean"], agg["ratio_std"],
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
