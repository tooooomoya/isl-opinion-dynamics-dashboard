"""
App-pol baseline calibration v14 (2026-07-25): time-constrained scope cut (user, "no time left").
Fixes bc_dec, bc_recovery, p_u at v13's consistently-pinned top-5 values (identical across all 5
independent candidates -- see docs/report/2026-07-21-conduit-experiment-design.md, "Calibration v13
completed") rather than re-searching them. Loss function reduced to bin7 fit ONLY at round level
(gini/Q/assort/bc_corr dropped entirely -- not just downweighted); final top-K selection still by
SF1 at n=20 (unchanged from v9-v13 -- SF1 stays excluded from round-level loss because its n=5
measurement noise exceeds the target window, same reasoning as before, just now the round loss has
nothing else in it either). 9 free dims (down from 12): max_follow, follow_prob, alpha, hop, stub,
pp_relax_eta, feed_capacity, initial_pp, vocal_comfort_radius.

vocal_comfort_radius's box is NOT capped below bcFloor here (kept at v13's [0.02,0.5]) despite the
discomfort/comfort-threshold coherence argument discussed (comfortRadius should be < bc so a post
can't simultaneously be "too disagreeable to tolerate" and "comfortable enough to embolden speech")
-- data showed points with vcr~0.45-0.5 were among the best bin7 fits found (rank 3/5 of v13's full
96-point history) while a strict <0.2 cap measurably cost bin7 fit quality. Explicit scope
trade-off given the time constraint and the "SF1+bin7 only" reprioritization: bc_corr is no longer
an active target, so the coherence argument (which was about keeping the vocal-minority mechanism
sensible relative to bc) is deprioritized too, not resolved.

Usage: nohup python3 scripts/app_pol_baseline_v14_sf1_bin7_only.py > logs/app_pol_baseline_v14_stdout.log 2>&1 &
"""
import concurrent.futures
import csv
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from scipy.stats import wasserstein_distance
from skopt import Optimizer
from skopt.space import Real, Integer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
LIBCP = ":".join(str(p) for p in ROOT.glob("lib/*.jar")) + (":" if list(ROOT.glob("lib/*.jar")) else "") + str(ROOT / "bin")
N = 1000
STEPS = 20000
BASE_SEED = 1440000  # fresh, distinct from every prior range this session

# Reduced schedule (9 dims, single-term loss -- converges faster than v13's 12-round/96-point run).
ROUND_SCHEDULE = [(3, 10)] * 4 + [(5, 6)] * 4
N_ROUNDS = len(ROUND_SCHEDULE)

TOP_K = 5
SELECT_SEEDS = 20

OOB_TREATMENT = 0.01

RATIO_TARGET, RATIO_SCALE = 1.225, 0.05
BIN7_W1_SCALE = 0.3

EMPIRICAL_POST_BIN_PROPORTIONS = np.array(
    [4328.725, 2682.863, 1503.682, 2135.798, 691.065, 1156.761, 3742.547]
)
EMPIRICAL_POST_BIN_PROPORTIONS = EMPIRICAL_POST_BIN_PROPORTIONS / EMPIRICAL_POST_BIN_PROPORTIONS.sum()
BIN_CENTERS = np.arange(7)

# Fixed, not searched -- v13's top-5 pinned identically at these values (docs/report entry above).
BC_DEC_FIXED = 1.0
BC_RECOVERY_FIXED = 0.0005
P_U_FIXED = 0.1
BC_INIT_FIXED = 1.0

SPACE = [
    Real(5, 50, name="max_follow"),
    Real(0.01, 0.3, prior="log-uniform", name="follow_prob"),
    Real(0.5, 1.0, name="alpha"),
    Integer(1, 5, name="hop"),
    Real(0.5, 0.9, name="stub"),
    Real(0.0005, 0.1, prior="log-uniform", name="pp_relax_eta"),
    Integer(5, 40, name="feed_capacity"),
    Real(0.01, 0.5, name="initial_pp"),
    Real(0.02, 0.5, prior="log-uniform", name="vocal_comfort_radius"),
]
DIM_NAMES = [d.name for d in SPACE]

LOG_PATH = ROOT / "docs" / "report" / "app_pol_baseline_v14_bo_evaluations.csv"
SELECT_LOG_PATH = ROOT / "docs" / "report" / "app_pol_baseline_v14_topk_select.csv"


def term(mean, std, target, scale):
    if mean is None:
        return 16.0 + 16.0
    return ((mean - target) / scale) ** 2 + (std / scale) ** 2


def compute_round_loss(agg):
    """bin7 fit ONLY -- gini/Q/assort/bc_corr dropped from the round-level objective entirely
    (time-constrained scope cut, see module docstring). SF1 still excluded from round-level loss
    (n=5 noise exceeds the target window) -- selected post-hoc via top-K n=20, same as v9-v13."""
    bin7_t = term(agg["bin7_w1_mean"], agg["bin7_w1_std"], 0.0, BIN7_W1_SCALE) if agg["bin7_w1_mean"] is not None else 16.0 + 16.0
    return bin7_t


def bin7_wasserstein(post_counts, pop_counts):
    post_counts = np.asarray(post_counts, dtype=float)
    pop_counts = np.asarray(pop_counts, dtype=float)
    if post_counts.sum() <= 0 or np.any(pop_counts <= 0):
        return 6.0
    per_capita_rate = post_counts / pop_counts
    model_props = per_capita_rate / per_capita_rate.sum()
    return float(wasserstein_distance(BIN_CENTERS, BIN_CENTERS, u_weights=model_props, v_weights=EMPIRICAL_POST_BIN_PROPORTIONS))


def launch(x, seed):
    (max_follow, follow_prob, alpha, hop, stub, pp_relax_eta,
     feed_capacity, initial_pp, vocal_comfort_radius) = x
    tokens = [
        f"seed={seed}", "network=hk", f"n={N}", f"steps={STEPS}", "log_gexf=false",
        "init_dist=empirical",
        f"max_follow={max_follow:.4f}", f"follow_prob={follow_prob:.4f}",
        f"alpha={alpha:.4f}", f"hop={int(hop)}",
        f"bc_dec={BC_DEC_FIXED:.5f}", f"bc_recovery={BC_RECOVERY_FIXED:.5f}", f"bc_init={BC_INIT_FIXED:.5f}",
        "stub_dist=uniform", f"stub_min={stub:.4f}", f"stub_max={stub:.4f}",
        f"pp_relax_eta={pp_relax_eta:.6f}", f"feed_capacity={int(feed_capacity)}",
        f"initial_pp={initial_pp:.4f}", "max_pp=1.0", "min_pp=0.01",
        f"vocal_comfort_radius={vocal_comfort_radius:.4f}",
        f"p_u={P_U_FIXED:.6f}",
        f"out_of_bc_repost_prob={OOB_TREATMENT}", "force=true",
    ]
    logfile = ROOT / "logs" / f"app_pol_baseline_v14_seed{seed}.log"
    logfile.parent.mkdir(exist_ok=True)
    with open(logfile, "w") as lf:
        p = subprocess.Popen(
            ["java", "-Xmx2g", "-cp", LIBCP, "dynamics.OpinionDynamics", *tokens],
            stdout=lf, stderr=subprocess.STDOUT, cwd=ROOT,
        )
    return p


def gini(x):
    x = np.sort(np.asarray(x, dtype=float))
    n = len(x)
    if n == 0 or x.sum() == 0:
        return float("nan")
    cum = np.cumsum(x)
    return (2 * np.sum((np.arange(1, n + 1)) * x) - (n + 1) * cum[-1]) / (n * cum[-1])


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
    bc_corr = float(last["bcExtremityCorrelation"])
    q = None
    with open(mod_path, newline="") as f:
        for row in csv.DictReader(f):
            if int(row["step"]) == STEPS:
                q = float(row["Q_sign_repost"])
    with open(bin7_path, newline="") as f:
        bin7_rows = list(csv.DictReader(f))
        post_counts = [int(r["postCount"]) for r in bin7_rows]
        pop_counts = [int(r["popCount"]) for r in bin7_rows]
    b7w1 = bin7_wasserstein(post_counts, pop_counts)
    if q is None or ratio is None:
        return None
    return g, indeg, assort, q, ratio, b7w1, post_counts, pop_counts, bc_corr


def evaluate_seed(x, seed):
    p = launch(x, seed)
    p.wait()
    return read_metrics(seed)


def aggregate(metrics):
    agg = {}
    for name, i in [("gini", 0), ("assort", 2), ("q_sign_repost", 3), ("ratio", 4), ("bin7_w1", 5),
                     ("bc_extremity_corr", 8)]:
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
        point_loss = compute_round_loss(agg) if len(ok) >= 2 else 1e6
        results_by_point.append((point_loss, agg))
    return results_by_point


def run_topk_selection(candidates):
    print(f"\n=== Top-{len(candidates)} candidates by round loss (bin7 only), re-evaluating each "
          f"with {SELECT_SEEDS} seeds for SF1 selection ===", flush=True)

    with open(SELECT_LOG_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["candidate_rank", "round_loss"] + DIM_NAMES +
                         ["n_ok", "gini_mean", "gini_std", "assort_mean", "assort_std",
                          "q_sign_repost_mean", "q_sign_repost_std", "ratio_mean", "ratio_std",
                          "bin7_w1_mean", "bin7_w1_std", "bc_extremity_corr_mean", "bc_extremity_corr_std"])

        scored = []
        for k, (round_loss, pt) in enumerate(candidates):
            seeds = [BASE_SEED + 500000 + k * SELECT_SEEDS + j for j in range(SELECT_SEEDS)]
            print(f"  candidate {k} (round_loss={round_loss:.3f}): evaluating {SELECT_SEEDS} seeds "
                  f"{seeds[0]}-{seeds[-1]}...", flush=True)
            t0 = time.time()
            with concurrent.futures.ThreadPoolExecutor(max_workers=SELECT_SEEDS) as ex:
                results = list(ex.map(lambda s: evaluate_seed(pt, s), seeds))
            ok = [m for m in results if m is not None]
            agg = aggregate(ok)
            writer.writerow([k, round_loss] + list(pt) + [
                len(ok), agg["gini_mean"], agg["gini_std"], agg["assort_mean"], agg["assort_std"],
                agg["q_sign_repost_mean"], agg["q_sign_repost_std"], agg["ratio_mean"], agg["ratio_std"],
                agg["bin7_w1_mean"], agg["bin7_w1_std"],
                agg["bc_extremity_corr_mean"], agg["bc_extremity_corr_std"],
            ])
            f.flush()
            sf1_gap = abs(agg["ratio_mean"] - RATIO_TARGET) if agg["ratio_mean"] is not None else float("inf")
            print(f"  candidate {k} done in {time.time()-t0:.0f}s: n={len(ok)}/{SELECT_SEEDS}, "
                  f"SF1={agg['ratio_mean']:.4f}+/-{agg['ratio_std']:.4f}, "
                  f"bin7_w1={agg['bin7_w1_mean']:.4f}, gap-to-target={sf1_gap:.4f}", flush=True)
            scored.append((sf1_gap, round_loss, pt, agg, ok))

    scored.sort(key=lambda r: r[0])
    winner_gap, winner_round_loss, winner_pt, winner_agg, winner_ok = scored[0]

    print(f"\n=== Selected candidate: round_loss={winner_round_loss:.3f}, "
          f"SF1={winner_agg['ratio_mean']:.4f}+/-{winner_agg['ratio_std']:.4f} "
          f"(closest to target midpoint {RATIO_TARGET} among top-{len(candidates)}) ===")
    print(f"params: {dict(zip(DIM_NAMES, winner_pt))}")
    print(f"(fixed: bc_dec={BC_DEC_FIXED}, bc_recovery={BC_RECOVERY_FIXED}, p_u={P_U_FIXED})")
    for k in ["gini_mean", "assort_mean", "q_sign_repost_mean", "ratio_mean", "bin7_w1_mean", "bc_extremity_corr_mean"]:
        print(f"{k} = {winner_agg[k]}")
    print(f"Full selection log: {SELECT_LOG_PATH}", flush=True)

    print("\nAll top-K candidates, ranked by SF1 gap:")
    for rank, (gap, rl, pt, agg, ok) in enumerate(scored):
        print(f"  #{rank}: round_loss={rl:.3f}  SF1={agg['ratio_mean']:.4f}+/-{agg['ratio_std']:.4f}  "
              f"bin7_w1={agg['bin7_w1_mean']:.4f}  gap={gap:.4f}")


def main():
    opt = Optimizer(SPACE, base_estimator="GP", acq_func="EI", random_state=41)

    rows = []
    with open(LOG_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["round", "point_idx", "seeds"] + DIM_NAMES +
                         ["point_loss", "gini_mean", "gini_std",
                          "assort_mean", "assort_std", "q_sign_repost_mean", "q_sign_repost_std",
                          "ratio_mean", "ratio_std", "bin7_w1_mean", "bin7_w1_std",
                          "bc_extremity_corr_mean", "bc_extremity_corr_std"])

        next_seed = BASE_SEED
        for rnd, (seeds_per_point, n_points_this_round) in enumerate(ROUND_SCHEDULE):
            t0 = time.time()
            points = opt.ask(n_points=n_points_this_round)
            point_seeds = []
            for _ in points:
                point_seeds.append(list(range(next_seed, next_seed + seeds_per_point)))
                next_seed += seeds_per_point
            print(f"[round {rnd}] evaluating {len(points)} points x {seeds_per_point} seeds "
                  f"({len(points) * seeds_per_point} concurrent JVMs, "
                  f"seeds {point_seeds[0][0]}-{point_seeds[-1][-1]})...", flush=True)

            point_results = evaluate_round(points, point_seeds)
            losses = [r[0] for r in point_results]
            opt.tell(points, losses)

            for i, (pt, seeds, (point_loss, agg)) in enumerate(zip(points, point_seeds, point_results)):
                writer.writerow([rnd, i, ";".join(map(str, seeds))] + list(pt) + [
                    point_loss, agg["gini_mean"], agg["gini_std"],
                    agg["assort_mean"], agg["assort_std"], agg["q_sign_repost_mean"], agg["q_sign_repost_std"],
                    agg["ratio_mean"], agg["ratio_std"], agg["bin7_w1_mean"], agg["bin7_w1_std"],
                    agg["bc_extremity_corr_mean"], agg["bc_extremity_corr_std"],
                ])
                rows.append((point_loss, pt))
            f.flush()
            best = min(r[0] for r in rows)
            print(f"[round {rnd}] done in {time.time()-t0:.0f}s, best point_loss so far = {best:.3f}", flush=True)

    rows.sort(key=lambda r: r[0])
    print(f"\nTop {TOP_K} points by round loss (bin7 only, SF1 excluded):")
    for loss, pt in rows[:TOP_K]:
        print(f"  loss={loss:.3f}  {dict(zip(DIM_NAMES, pt))}")
    print(f"\nFull log: {LOG_PATH}")

    run_topk_selection(rows[:TOP_K])


if __name__ == "__main__":
    main()
