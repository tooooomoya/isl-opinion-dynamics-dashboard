"""
App-pol baseline calibration v5 (2026-07-22): bin7 metric fixed to compare PER-CAPITA posting rate
instead of raw total post volume. Supersedes app_pol_baseline_bo_v4_topk_sf1select.py -- v4's
winning point (max_follow=5.0, comfort_pp=2.89, ...) was diagnosed post-hoc: post_bin7.csv tracks
both popCount and postCount per bin, but every prior version (v2/v3/v4) only ever read postCount
and compared it directly against EMPIRICAL_POST_BIN_PROPORTIONS -- which is actually a per-capita
rate (mean posts per survey respondent in that bin), not a population-weighted total-volume share.
Since the model's realized bin populations are wildly unequal under init_dist=empirical (moderates
~3-5x more numerous than the extreme bins), raw-total comparison silently conflated "how much each
person posts" with "how many people are in that bin" -- comparing volume to a rate target, an
apples-to-oranges bug present since the empirical-7-bin feature was introduced.

Diagnostic finding that motivated this fix: recomputing v4's winner with popCount properly used
showed its per-capita posting rate is nearly FLAT across all 7 opinion bins (1533-1955 posts/agent,
~1.27x range) versus the real data's 6.3x spread (691-4329) -- a much sharper, more mechanistically
useful diagnosis than the raw-volume comparison's apparent "moderates over-post" pattern (which was
mostly just population size, not per-capita behavior). This directly explains why SF1 undershoots
target too: a nearly-flat per-capita posting rate means no real selective-amplification-of-extremes
mechanism is operating, so post-opinion variance stays close to population variance (SF1~1).

Fix: bin7_wasserstein(post_counts, pop_counts) now normalizes by the model's own realized popCount
per bin before comparing to the (already per-capita) empirical target -- see the function's
docstring. read_metrics()/evaluate_seed() now also return pop_counts. Everything else unchanged
from v4 (SF1 excluded from round loss, top-K post-hoc selection, gini/Q downweighting, max_follow
lower bound at 5). This version has NOT yet been used for a full 12-round search -- first doing a
quick 3-seed check (user request, 2026-07-22) against v4's winning params to see how much the
corrected metric changes the picture before committing to a full relaunch.

--- v4 docstring below, preserved for context ---

App-pol baseline calibration v4 (2026-07-22): SF1 excluded from the round-level loss, selected
post-hoc via a properly-powered top-K comparison instead. Supersedes
app_pol_baseline_bo_v3_wasserstein.py, killed after ~15min into round 0 (no completed rounds, no
opt.tell() calls yet -- nothing to warm-start from, starting the BO search from scratch). See
docs/report/2026-07-21-conduit-experiment-design.md for the full trail.

Why v3 (SF1 in the round loss at reduced weight) was itself wrong, not just v2 (full weight):
the round10/pt3 noise-check (20 fresh seeds + the original 5, pooled n=25) confirmed the
bin7-good/SF1-bad decoupling is real, not sampling noise -- but computing the typical per-point
n=5 SF1 standard error from all 72 v2-evaluated points shows why that finding argues for excluding
SF1 from the round loss entirely, not just downweighting it: mean per-point SF1 std at n=5 is
0.190, giving a typical SEM of 0.085 and a 95% CI half-width of ~0.166 -- more than DOUBLE the
entire target window's width (1.19 to 1.26 = 0.07). At the sampling budget actually used during BO
rounds, the SF1 mean-miss term cannot resolve whether a point is inside the target window at all;
it can barely distinguish "clearly low" (~0.7) from "clearly high" (~1.3), nothing finer. Keeping
it in the round loss (as v3 did) doesn't steer the search toward the target -- it injects
measurement noise into the acquisition function, which is very likely the same mechanism behind
the winner's-curse confirm-gap seen in BOTH v1's 5-dim run and v2's 11-dim run.

Design (v4):
1. Round-level loss = gini(0.5) + Q_sign_repost(0.7) + assort-floor + bin7-Wasserstein(1.0) only --
   all four have reasonable per-point SNR at n=5 (unlike SF1). SF1 is still computed and logged
   every round (visibility, not blindness) but does not feed opt.tell().
2. After N_ROUNDS complete, take the TOP_K=5 points by round-level loss (not just the single best)
   and re-evaluate each with SELECT_SEEDS=20 fresh seeds (SEM~0.043, 95% CI half-width~0.083 --
   real resolving power, unlike n=5). Pick whichever of those 5 candidates lands closest to the
   SF1 target midpoint (1.225). This uses SF1 exactly where it has statistical power (a 20-seed
   comparison among a short, already-good-on-everything-else list) and nowhere it doesn't (n=5,
   ×72 points, is not affordable and not informative anyway). This selection stage doubles as the
   final confirmation -- no separate low-n confirm run afterward.
3. All other v3 changes retained unchanged: Wasserstein-1 bin7 term, max_follow lower bound
   widened to 5, gini/Q asymmetric downweighting (still justified independent of the SF1 question
   -- see v3's docstring, preserved in git history).

Usage: python3 scripts/app_pol_baseline_bo_v5_percapita_bin7.py
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
N_ROUNDS = 12
N_POINTS_PER_ROUND = 6
SEEDS_PER_POINT = 5
BASE_SEED = 1050000  # distinct from v1/v2/v3/v4's already-used seed ranges

TOP_K = 5             # candidates carried into the properly-powered SF1 selection stage
SELECT_SEEDS = 20     # SEM~0.043 at typical per-point std=0.19, 95% CI half-width~0.083 --
                       # real resolving power against the 0.07-wide target window, unlike n=5

OOB_TREATMENT = 0.01  # fixed, not searched -- see module docstring

GINI_TARGET, GINI_SCALE = 0.8, 0.05
Q_TARGET, Q_SCALE = 0.48, 0.05
RATIO_TARGET, RATIO_SCALE = 1.225, 0.05
ASSORT_FLOOR, ASSORT_SCALE = 0.6, 0.15
BIN7_W1_SCALE = 0.3  # Wasserstein-1 distance scale, calibrated from the v2 retro-check
                      # (mean W1 across 360 v2 seed-evaluations = 0.666, so this lands the term
                      # near O(1-10), comparable to the other terms before weighting)

# Round-level loss weights -- SF1 excluded entirely (see module docstring), gini/Q still
# asymmetrically downweighted per the v3 correlation evidence (still valid, independent of the
# SF1 question):
W_GINI, W_Q, W_BIN7 = 0.5, 0.7, 1.0

# Const.EMPIRICAL_POST_BIN_WEIGHTS, normalized to proportions (see src/constants/Const.java).
EMPIRICAL_POST_BIN_PROPORTIONS = np.array(
    [4328.725, 2682.863, 1503.682, 2135.798, 691.065, 1156.761, 3742.547]
)
EMPIRICAL_POST_BIN_PROPORTIONS = EMPIRICAL_POST_BIN_PROPORTIONS / EMPIRICAL_POST_BIN_PROPORTIONS.sum()
BIN_CENTERS = np.arange(7)  # equal-width ordinal bins; unit spacing suffices for a relative W1 distance

SPACE = [
    Real(5, 50, name="max_follow"),           # lower bound widened from v2's 15 -- v2's winner
                                               # pinned there, never tested for headroom below
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
    Real(0.02, 0.5, prior="log-uniform", name="vocal_comfort_radius"),  # NEW (2026-07-22) -- fixed
        # at its 0.2 default in every prior calibration (v1-v5) despite being explicitly promoted to
        # a sweepable CLI param on 2026-07-19 to test "whether the fixed absolute window is what's
        # suppressing SF1 apparent polarization" (Agent.java comment) -- never actually tested until
        # now. Log-uniform to resolve narrow (sharper vocal-minority gating) values well.
]
DIM_NAMES = [d.name for d in SPACE]

LOG_PATH = ROOT / "docs" / "report" / "app_pol_baseline_v5_bo_evaluations.csv"
SELECT_LOG_PATH = ROOT / "docs" / "report" / "app_pol_baseline_v5_topk_select.csv"
CCDF_LOG_PATH = ROOT / "docs" / "report" / "app_pol_baseline_v5_indegree_ccdf.csv"
CCDF_PLOT_PATH = ROOT / "docs" / "report" / "app_pol_baseline_v5_indegree_ccdf.png"


def gini(x):
    x = np.sort(np.asarray(x, dtype=float))
    n = len(x)
    if n == 0 or x.sum() == 0:
        return float("nan")
    cum = np.cumsum(x)
    return (2 * np.sum((np.arange(1, n + 1)) * x) - (n + 1) * cum[-1]) / (n * cum[-1])


def term(mean, std, target, scale):
    if mean is None:
        return 16.0 + 16.0
    mean_term = ((mean - target) / scale) ** 2
    std_term = (std / scale) ** 2
    return mean_term + std_term


def compute_round_loss(agg):
    """Round-level (n=5/point) loss. SF1 excluded -- see module docstring: at n=5 its measurement
    noise (95% CI half-width ~0.166) exceeds the entire target window (0.07 wide), so including it
    here would inject noise into the acquisition function rather than real signal."""
    gini_t = term(agg["gini_mean"], agg["gini_std"], GINI_TARGET, GINI_SCALE)
    q_t = term(agg["q_sign_repost_mean"], agg["q_sign_repost_std"], Q_TARGET, Q_SCALE)
    a_mean = agg["assort_mean"]
    assort_t = max(0.0, (ASSORT_FLOOR - a_mean) / ASSORT_SCALE) ** 2 if a_mean is not None else 16.0
    bin7_t = term(agg["bin7_w1_mean"], agg["bin7_w1_std"], 0.0, BIN7_W1_SCALE) if agg["bin7_w1_mean"] is not None else 16.0 + 16.0
    return W_GINI * gini_t + W_Q * q_t + assort_t + W_BIN7 * bin7_t


def bin7_wasserstein(post_counts, pop_counts):
    """Wasserstein-1 distance between the model's PER-CAPITA posting-rate-by-bin proportions and
    the empirical per-capita posting-activity target, over the 7 ordered ideology bins.

    2026-07-22 fix: v2/v3/v4 all compared raw postCount totals (population-size-confounded) against
    EMPIRICAL_POST_BIN_PROPORTIONS, which is actually a per-capita rate (mean posts per survey
    respondent in that bin), not a population-weighted total-volume share. Since the model's bin
    populations are wildly unequal (moderates ~3-5x more numerous than the extreme bins, per
    init_dist=empirical), raw-total comparison conflated "how much each person posts" with "how
    many people are in that bin" -- comparing volume to a rate target. post_bin7.csv already tracks
    popCount per bin (written by Writer.writePostBin7, never previously read here) -- now used to
    normalize postCount into a genuine per-capita rate before comparison, matching what the
    empirical target actually represents. Ordinal-aware (unlike v2's sum-of-squared-per-bin-
    differences): a mismatch between adjacent bins costs less than one between opposite-extreme
    bins, matching the bins' actual ordered structure."""
    post_counts = np.asarray(post_counts, dtype=float)
    pop_counts = np.asarray(pop_counts, dtype=float)
    if post_counts.sum() <= 0 or np.any(pop_counts <= 0):
        return 6.0  # worst-case: all mass at one end, target at the other (max possible W1 here)
    per_capita_rate = post_counts / pop_counts
    model_props = per_capita_rate / per_capita_rate.sum()
    return float(wasserstein_distance(BIN_CENTERS, BIN_CENTERS, u_weights=model_props, v_weights=EMPIRICAL_POST_BIN_PROPORTIONS))


def launch(x, seed):
    (max_follow, follow_prob, alpha, hop, bc_dec, bc_recovery, bc_init, stub, comfort_pp,
     feed_capacity, initial_pp, vocal_comfort_radius) = x
    tokens = [
        f"seed={seed}", "network=hk", f"n={N}", f"steps={STEPS}", "log_gexf=false",
        "init_dist=empirical",
        f"max_follow={max_follow:.4f}", f"follow_prob={follow_prob:.4f}",
        f"alpha={alpha:.4f}", f"hop={int(hop)}",
        f"bc_dec={bc_dec:.5f}", f"bc_recovery={bc_recovery:.5f}", f"bc_init={bc_init:.5f}",
        "stub_dist=uniform", f"stub_min={stub:.4f}", f"stub_max={stub:.4f}",
        f"comfort_pp={comfort_pp:.4f}", f"feed_capacity={int(feed_capacity)}",
        f"initial_pp={initial_pp:.4f}", "max_pp=1.0",
        f"vocal_comfort_radius={vocal_comfort_radius:.4f}",
        f"out_of_bc_repost_prob={OOB_TREATMENT}", "force=true",
    ]
    logfile = ROOT / "logs" / f"app_pol_baseline_v5_seed{seed}.log"
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
        bin7_rows = list(csv.DictReader(f))
        post_counts = [int(r["postCount"]) for r in bin7_rows]
        pop_counts = [int(r["popCount"]) for r in bin7_rows]
    b7w1 = bin7_wasserstein(post_counts, pop_counts)
    if q is None or ratio is None:
        return None
    return g, indeg, assort, q, ratio, b7w1, post_counts, pop_counts


def evaluate_seed(x, seed):
    p = launch(x, seed)
    p.wait()
    return read_metrics(seed)


def aggregate(metrics):
    agg = {}
    for name, i in [("gini", 0), ("assort", 2), ("q_sign_repost", 3), ("ratio", 4), ("bin7_w1", 5)]:
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
        plt.title("App-pol baseline v5: empirical in-degree CCDF (validation only)")
        plt.tight_layout()
        plt.savefig(CCDF_PLOT_PATH, dpi=150)
        plt.close()
    except Exception as e:
        print(f"(CCDF plot skipped: {type(e).__name__}: {e})")


def run_topk_selection(candidates):
    """candidates: list of (round_loss, point) for the TOP_K round-loss winners. Re-evaluates each
    with SELECT_SEEDS fresh seeds (real SF1 resolving power, unlike the n=5 round loss) and picks
    whichever lands closest to the SF1 target midpoint. Doubles as the final confirmation report --
    no separate low-n confirm stage."""
    print(f"\n=== Top-{len(candidates)} candidates by round loss, re-evaluating each with "
          f"{SELECT_SEEDS} seeds for SF1 selection (out_of_bc_repost_prob={OOB_TREATMENT}) ===", flush=True)

    with open(SELECT_LOG_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["candidate_rank", "round_loss"] + DIM_NAMES +
                         ["n_ok", "gini_mean", "gini_std", "assort_mean", "assort_std",
                          "q_sign_repost_mean", "q_sign_repost_std", "ratio_mean", "ratio_std",
                          "bin7_w1_mean", "bin7_w1_std"])

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
            ])
            f.flush()
            sf1_gap = abs(agg["ratio_mean"] - RATIO_TARGET) if agg["ratio_mean"] is not None else float("inf")
            print(f"  candidate {k} done in {time.time()-t0:.0f}s: n={len(ok)}/{SELECT_SEEDS}, "
                  f"SF1={agg['ratio_mean']:.4f}+/-{agg['ratio_std']:.4f}, gap-to-target={sf1_gap:.4f}", flush=True)
            scored.append((sf1_gap, round_loss, pt, agg, ok))

    scored.sort(key=lambda r: r[0])
    winner_gap, winner_round_loss, winner_pt, winner_agg, winner_ok = scored[0]

    print(f"\n=== Selected candidate: round_loss={winner_round_loss:.3f}, "
          f"SF1={winner_agg['ratio_mean']:.4f}+/-{winner_agg['ratio_std']:.4f} "
          f"(closest to target midpoint {RATIO_TARGET} among top-{len(candidates)}) ===")
    print(f"params: {dict(zip(DIM_NAMES, winner_pt))}")
    if winner_agg["gini_mean"] is not None:
        print(f"gini   = {winner_agg['gini_mean']:.4f} +/- {winner_agg['gini_std']:.4f} (target {GINI_TARGET})")
    if winner_agg["assort_mean"] is not None:
        print(f"assort = {winner_agg['assort_mean']:.4f} +/- {winner_agg['assort_std']:.4f} (floor {ASSORT_FLOOR})")
    if winner_agg["q_sign_repost_mean"] is not None:
        print(f"Q_sign_repost = {winner_agg['q_sign_repost_mean']:.4f} +/- {winner_agg['q_sign_repost_std']:.4f} (target {Q_TARGET})")
    if winner_agg["ratio_mean"] is not None:
        print(f"apparent-polarization ratio = {winner_agg['ratio_mean']:.4f} +/- {winner_agg['ratio_std']:.4f} (target [1.19,1.26], n={len(winner_ok)})")
    if winner_agg["bin7_w1_mean"] is not None:
        print(f"7-bin posting-fit Wasserstein-1 distance = {winner_agg['bin7_w1_mean']:.4f} +/- {winner_agg['bin7_w1_std']:.4f} (0 = perfect match)")
    print(f"Full selection log: {SELECT_LOG_PATH}", flush=True)

    all_indeg = [d for m in winner_ok for d in m[1]]
    if all_indeg:
        write_ccdf(all_indeg)
        print(f"CCDF (validation only, not in loss): {CCDF_LOG_PATH} / {CCDF_PLOT_PATH}", flush=True)

    if winner_ok:
        pooled_post = np.sum([m[6] for m in winner_ok], axis=0)
        pooled_pop = np.sum([m[7] for m in winner_ok], axis=0)
        per_capita_rate = pooled_post / pooled_pop
        model_props = per_capita_rate / per_capita_rate.sum()
        print("\n7-bin PER-CAPITA posting-rate proportions (model vs. empirical target):")
        for i in range(7):
            print(f"  bin {i}: model={model_props[i]:.4f}  empirical={EMPIRICAL_POST_BIN_PROPORTIONS[i]:.4f}")

    print("\nAll top-K candidates, ranked by SF1 gap:")
    for rank, (gap, rl, pt, agg, ok) in enumerate(scored):
        print(f"  #{rank}: round_loss={rl:.3f}  SF1={agg['ratio_mean']:.4f}+/-{agg['ratio_std']:.4f}  gap={gap:.4f}")


def main():
    opt = Optimizer(SPACE, base_estimator="GP", acq_func="EI", random_state=41)

    rows = []
    with open(LOG_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["round", "point_idx", "seeds"] + DIM_NAMES +
                         ["point_loss", "gini_mean", "gini_std",
                          "assort_mean", "assort_std", "q_sign_repost_mean", "q_sign_repost_std",
                          "ratio_mean", "ratio_std", "bin7_w1_mean", "bin7_w1_std"])

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
                    agg["ratio_mean"], agg["ratio_std"], agg["bin7_w1_mean"], agg["bin7_w1_std"],
                ])
                rows.append((point_loss, pt))
            f.flush()
            best = min(r[0] for r in rows)
            print(f"[round {rnd}] done in {time.time()-t0:.0f}s, best point_loss so far = {best:.3f}", flush=True)

    rows.sort(key=lambda r: r[0])
    print(f"\nTop {TOP_K} points by round loss (SF1 excluded):")
    for loss, pt in rows[:TOP_K]:
        print(f"  loss={loss:.3f}  {dict(zip(DIM_NAMES, pt))}")
    print(f"\nFull log: {LOG_PATH}")

    run_topk_selection(rows[:TOP_K])


if __name__ == "__main__":
    main()
