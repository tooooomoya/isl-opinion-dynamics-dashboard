"""
Joint calibration v7 (2026-07-20): variance-penalized loss + widened box -- the "does any single
credible point exist" check, following a foundation-credibility audit (docs/report/2026-07-18-
joint-stage-calibration.md).

Motivation: mining all 168 points ever evaluated across v3-v6 for one that jointly satisfies all
four structural facts (Gini~0.8, Q_sign_repost~0.48, assort high, SF1 ratio in [1.19,1.26], generous
bands) found exactly one nominal hit -- and it turned out to be v4's already-rejected "bc frozen"
degenerate point (bc_dec=0.999, bc_recovery=0.0). Its apparent 4-way success was a 3-seed sampling
fluke: the SAME point's actual 5-seed confirm gave ratio=0.871+/-0.151 (a miss), vs. 1.159+/-0.072
in the 3-seed search round. Same parameters, different seeds, wildly different answer -- the search
was rewarding lucky means, not stable points.

Two fixes:
1. SEEDS_PER_POINT raised 3 -> 5 (matches CONFIRM_SEEDS), so search-time evaluation can no longer
   be fooled by a small-sample fluke the way the case above was.
2. Explicit variance-penalty terms added to the loss (gini_std, q_std, ratio_std, same 0.05 scale
   as the mean terms -- genuine equal treatment of "off-target" and "unstable", no arbitrary
   weight). assort keeps its original one-sided floor term (0.6 floor, restored from v1 -- dropped
   from v3-v6's loss but needed now that we're checking joint feasibility, not just SF1).

Also widened the 5 contested dims back to their ORIGINAL full ranges (v3/v4's box, not v5/v6's
narrow box centered on the manual point) so the search isn't pre-biased toward the wide/frozen-bc
family before the variance penalty gets a chance to rule it out on its own merits. Other 6 dims
fixed at v1's stable, never-implicated values.

Usage: python3 scripts/stage_joint_bo_v7_robust.py
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
STEPS = 20000
N_ROUNDS = 8
N_POINTS_PER_ROUND = 6
SEEDS_PER_POINT = 5  # raised from 3 -- closes the small-sample-fluke gap found in v4's history
CONFIRM_SEEDS = 5
BASE_SEED = 840000

GINI_TARGET, GINI_SCALE = 0.8, 0.05
Q_TARGET, Q_SCALE = 0.48, 0.05
RATIO_TARGET, RATIO_SCALE = 1.225, 0.05  # SF1, JCSS-TomoyaTakeda2026.pdf Section 4.2
ASSORT_FLOOR, ASSORT_SCALE = 0.6, 0.15  # restored from v1 -- one-sided, dropped only in v3-v6

# Fixed at v1-calibrated defaults -- never implicated in any instability/pinning across v1-v6.
FIXED_MAX_FOLLOW = 57
FIXED_FOLLOW_PROB = 0.009
FIXED_ALPHA = 0.76
FIXED_FEED_CAPACITY = 15
FIXED_INITIAL_PP = 0.21
FIXED_STUB = 0.69
FIXED_MAX_POST_PROB = 1.0

SPACE = [
    Integer(1, 5, name="hop"),           # widened from v5/v6's [1,3] back to v3/v4's full range
    Real(0.5, 0.999, name="bc_dec"),     # widened from [0.9,0.999] back to v3/v4's full range
    Real(0.0, 0.3, name="bc_recovery"),  # widened back to v1/v2's original range
    Real(0.2, 1.0, name="bc_init"),      # widened from [0.8,1.0] -- full [bcFloor,bcCeiling] range
    Real(0.5, 3.0, name="comfort_pp"),   # union of v3/v4's [1,3] and v5/v6's [0.5,1.5]
]
DIM_NAMES = [d.name for d in SPACE]

LOG_PATH = ROOT / "docs" / "report" / "stage_joint_v7_bo_evaluations.csv"
CONFIRM_LOG_PATH = ROOT / "docs" / "report" / "stage_joint_v7_confirm.csv"


def gini(x):
    x = np.sort(np.asarray(x, dtype=float))
    n = len(x)
    if n == 0 or x.sum() == 0:
        return float("nan")
    cum = np.cumsum(x)
    return (2 * np.sum((np.arange(1, n + 1)) * x) - (n + 1) * cum[-1]) / (n * cum[-1])


def compute_point_loss(agg):
    """Loss on the AGGREGATED (across-seed) stats for one point -- mean-miss terms plus an explicit
    variance-penalty term per hard-target metric, same scale as the mean term (genuine equal
    treatment of 'off-target' and 'unstable'). Must be called after aggregating all seeds for a
    point; a per-seed loss can't see cross-seed variance."""
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
        "out_of_bc_repost_prob=0.0", "force=true",
    ]
    logfile = ROOT / "logs" / f"stage_joint_v6_seed{seed}.log"
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
    gf = fit_powerlaw(indeg).get("alpha")  # monitored only, not in loss
    with open(results_path, newline="") as f:
        last = list(csv.DictReader(f))[-1]
    assort = float(last["opinionAssortativity"])  # monitored only, not in loss
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
    return g, gf, assort, q, ratio


def evaluate_seed(x, seed):
    p = launch(x, seed)
    p.wait()
    return read_metrics(seed)  # (g, gf, assort, q, ratio) or None -- no per-seed loss


def aggregate(metrics):
    """metrics: list of (g, gf, assort, q, ratio) tuples (one per seed, Nones filtered)."""
    agg = {}
    for name, i in [("gini", 0), ("gamma_fit", 1), ("assort", 2), ("q_sign_repost", 3), ("ratio", 4)]:
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
        point_loss = compute_point_loss(agg) if len(ok) >= 2 else 1e6  # need >=2 for a std estimate
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
        writer.writerow(["seed"] + DIM_NAMES + ["gini", "gamma_fit", "assort", "q_sign_repost", "ratio"])
        for seed, m in zip(confirm_seeds, results):
            row = list(m) if m is not None else [None] * 5
            writer.writerow([seed] + list(best_point) + row)

    ok = [m for m in results if m is not None]
    agg = aggregate(ok)
    point_loss = compute_point_loss(agg) if len(ok) >= 2 else float("nan")
    print(f"n={len(ok)}/{CONFIRM_SEEDS} succeeded")
    print(f"point_loss (mean-miss + variance-penalty) = {point_loss:.3f}")
    if agg["gini_mean"] is not None:
        print(f"gini   = {agg['gini_mean']:.4f} +/- {agg['gini_std']:.4f} (target {GINI_TARGET})")
    if agg["gamma_fit_mean"] is not None:
        print(f"gamma_fit (monitored) = {agg['gamma_fit_mean']:.3f} +/- {agg['gamma_fit_std']:.3f}")
    if agg["assort_mean"] is not None:
        print(f"assort = {agg['assort_mean']:.4f} +/- {agg['assort_std']:.4f} (floor {ASSORT_FLOOR})")
    if agg["q_sign_repost_mean"] is not None:
        print(f"Q_sign_repost = {agg['q_sign_repost_mean']:.4f} +/- {agg['q_sign_repost_std']:.4f} (target {Q_TARGET})")
    if agg["ratio_mean"] is not None:
        print(f"apparent-polarization ratio = {agg['ratio_mean']:.4f} +/- {agg['ratio_std']:.4f} (target [1.19,1.26])")
    print(f"Full log: {CONFIRM_LOG_PATH}", flush=True)


def main():
    opt = Optimizer(SPACE, base_estimator="GP", acq_func="EI", random_state=41)

    rows = []
    with open(LOG_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["round", "point_idx", "seeds"] + DIM_NAMES +
                         ["point_loss", "gini_mean", "gini_std", "gamma_fit_mean", "gamma_fit_std",
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
                    point_loss, agg["gini_mean"], agg["gini_std"], agg["gamma_fit_mean"], agg["gamma_fit_std"],
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
