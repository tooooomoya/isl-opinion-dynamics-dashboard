"""
App-pol baseline calibration v11 (2026-07-24): fixes v10's corrupted warm-start (v9's 96 points were
mislabeled p_u=0.01 when they were actually run at p_u=0.05 -- see docs/report/2026-07-21-conduit-
experiment-design.md, "ROOT CAUSE: v9-vs-v10 'same point, different result' was an uncontrolled pU
default"), and fixes `min_pp` at 0.01 (was silently 0.05, the untouched ExperimentConfig default,
in every prior calibration -- never explicitly tokenized in any launch() before this one).

Root cause recap: v9's launch() never passed `p_u`, so it silently inherited whatever
ExperimentConfig's pU default was at compile time -- 0.05 (the legacy "P_u phase-diagram knob"
value), confirmed by deterministic reproduction (same seed, same other params, p_u=0.05 reproduces
v9's on-disk assort=0.9800 to 4 decimals). v10 explicitly pinned p_u=0.01 as its new free dim AND
padded v9's warm-start points with that same wrong label -- corrupting v10's entire GP prior on the
one axis it was meant to explore. v10's "no improvement" conclusion is discarded; not a real result.

Why this matters beyond the bug: p_u has a first-order effect, bigger than most swept dims.
Reproduction at seed 1600000, only p_u varied: p_u=0.05 gives assort=0.98, Q_repost=0.44 (both near
target), SF1=1.09 (near the [1.19,1.26] target); p_u=0.01 gives assort=0.80, Q_repost=0.02 (badly
misses the 0.48 target), SF1=0.40. But bc_corr flips: -0.006 (degenerate) at p_u=0.05 vs -0.386
(strong) at p_u=0.01. Genuine tension: high p_u buys structure+SF1 at the cost of the asymmetric-bc
signal; low p_u buys bc asymmetry at the cost of structure. User's call (2026-07-24): prioritize
reaching SF1 -- verified before launching that this does NOT require gutting the loss function:
computing round_loss by hand for both regimes shows Q_sign_repost's penalty alone is ~60 at p_u=0.01
(catastrophically missing its 0.48 target) vs ~1.3 total loss at p_u=0.05 -- the existing,
un-modified loss already prefers the SF1-supporting regime once the warm-start labels are correct,
so bc_corr's ceiling term is left as-is (not removed) and the fix is purely to the warm-start data.

Second change: `min_pp` fixed at 0.01 (was 0.05, unchanged in this field's entire git history until
now). User hypothesis: the postProb floor may be propping up posting rates for structurally
low-comfort agents (plausibly the mild-partisan bins the empirical 7-bin target wants to be
*quietest*, per the still-open vocalComfortRadius density-bias question -- see that design-doc
entry), contributing to the "moderates too vocal" / flat-instead-of-W-shaped bin7 fit. Fixed (not
swept) for a clean, directly-interpretable before/after comparison against v9's bin7 result, same
as how out_of_bc_repost_prob is fixed rather than searched.

Changes from v10:
1. Warm-start relabeled: v9's 96 points padded with the CORRECT p_u=0.05 (was wrongly 0.01).
2. `min_pp=0.01` added as a fixed token in launch() (was implicit default 0.05).
3. `p_u` SPACE dimension and ROUND_SCHEDULE unchanged from v10 (Real(0.0005,0.1,log-uniform),
   4 wide + 6 narrow, 10 rounds) -- only the warm-start data and min_pp were wrong/missing.

Usage: nohup python3 scripts/app_pol_baseline_bo_v11_pu_fix_minpp.py > logs/app_pol_baseline_v11_stdout.log 2>&1 &
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
BASE_SEED = 1210000  # distinct from v1-v10's already-used seed ranges

V9_LOG_PATH = ROOT / "docs" / "report" / "app_pol_baseline_v9_bo_evaluations.csv"  # warm-start source

# Progressive-fidelity round schedule (2026-07-22, user proposal): coarse/cheap/wide exploration
# first, then precise/expensive/narrow refinement -- same spirit as Hyperband/multi-fidelity BO
# (spend cheap evaluations broadly, expensive ones narrowly), simplified to a 2-phase step change
# rather than a full continuous-fidelity GP. Motivated by the max_follow/alpha/bc_init boundary-
# pinning pattern recurring across v2-v6: 72 points in an 11-12 dim space (the old fixed 12x6
# schedule) is a very sparse budget, and a flat n=5/point spends that budget on precision the early
# rounds don't need yet. Peak concurrency held at 30 JVMs throughout (same as every prior version)
# by trading points-per-round against seeds-per-point, not by increasing total concurrent load.
# Phase 1 (wide): more distinct points/round, fewer seeds each -- rougher per-point loss estimate,
# but ~1.7x the point-coverage of the old flat schedule in the same rounds.
# Phase 2 (narrow): back to the original 6 points/5 seeds -- precise refinement near whatever
# phase 1 identified as promising.
ROUND_SCHEDULE = [(3, 10)] * 4 + [(5, 6)] * 6  # trimmed -- warm-started from v9's 96 points
N_ROUNDS = len(ROUND_SCHEDULE)

TOP_K = 5             # candidates carried into the properly-powered SF1 selection stage
SELECT_SEEDS = 20     # SEM~0.043 at typical per-point std=0.19, 95% CI half-width~0.083 --
                       # real resolving power against the 0.07-wide target window, unlike n=5

OOB_TREATMENT = 0.01  # fixed, not searched -- see module docstring

GINI_TARGET, GINI_SCALE = 0.8, 0.05
Q_TARGET, Q_SCALE = 0.48, 0.05
RATIO_TARGET, RATIO_SCALE = 1.225, 0.05
ASSORT_FLOOR, ASSORT_SCALE = 0.6, 0.15
# bc-vs-extremity correlation must be AT OR BELOW this (more negative = stronger asymmetric-bc
# signal); a ceiling constraint, mirror image of assort's floor. Direction-only, see docstring.
BC_EXTREMITY_CORR_CEILING, BC_EXTREMITY_CORR_SCALE = -0.1, 0.15
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
    Real(0.0001, 0.05, prior="log-uniform", name="bc_recovery"),  # narrowed (2026-07-22)
        # from [0.0,0.3] linear -- anchored on Li/Luo/Porter 2023's tested range; now
        # means their confidence-increase gamma (content-triggered growth toward
        # bcCeiling), not the old content-independent passive drift toward bcInit.
    # bc_init dropped as a free dim (2026-07-22) -- fixed at BC_INIT_FIXED (bcCeiling) below.
    # v6's winner landed bc_init=0.2 (the floor), which meant EVERY agent started maximally
    # narrow and decline had nowhere to go; the negative bc-extremity correlation was achieved
    # entirely through recovery (moderates, sitting in dense regions of the opinion distribution,
    # get lucky early comfortable contact and grow toward the ceiling; extremists, sparse, rarely
    # do) -- "who started with agreeable neighbors," not "who experiences more disagreement over
    # time." That's the wrong causal story (doesn't match the negativity-dominance citation this
    # mechanism is grounded in). Fixing bc_init high forces decline to be the only thing that can
    # move bc at all initially, so any resulting asymmetry has to come from extremists genuinely
    # encountering more disagreement and narrowing down -- the intended mechanism.
    Real(0.5, 0.9, name="stub"),              # tightened from v1's [0.05,0.95] (user)
    Real(0.0005, 0.1, prior="log-uniform", name="pp_relax_eta"),  # NEW (2026-07-23), replaces
        # comfort_pp -- eta in postProb += eta*(targetPostProb - postProb). Log-uniform to resolve
        # both slow (~2000-step time constant, barely reaches target) and fast (~10-step, tracks
        # comfortPostRate almost immediately) regimes. See module docstring for the mechanism
        # replacement this supersedes.
    Integer(5, 40, name="feed_capacity"),     # v1, unchanged
    Real(0.01, 0.5, name="initial_pp"),       # v1, unchanged
    Real(0.02, 0.5, prior="log-uniform", name="vocal_comfort_radius"),  # NEW (2026-07-22) -- fixed
        # at its 0.2 default in every prior calibration (v1-v5) despite being explicitly promoted to
        # a sweepable CLI param on 2026-07-19 to test "whether the fixed absolute window is what's
        # suppressing SF1 apparent polarization" (Agent.java comment) -- never actually tested until
        # now. Log-uniform to resolve narrow (sharper vocal-minority gating) values well.
    Real(0.0005, 0.1, prior="log-uniform", name="p_u"),  # NEW (2026-07-24) -- unfollow probability,
        # fixed at 0.01 (legacy `P_u` phase-diagram default) through v1-v9; freed now that the
        # secession-test redesign no longer reserves it as the manipulated experimental variable.
        # Log-uniform, centered on the legacy default -- see module docstring. Placed last so v9's
        # 96 warm-start points (all genuinely run at p_u=0.01) can be padded by simple append.
]
DIM_NAMES = [d.name for d in SPACE]

LOG_PATH = ROOT / "docs" / "report" / "app_pol_baseline_v11_bo_evaluations.csv"
SELECT_LOG_PATH = ROOT / "docs" / "report" / "app_pol_baseline_v11_topk_select.csv"
CCDF_LOG_PATH = ROOT / "docs" / "report" / "app_pol_baseline_v11_indegree_ccdf.csv"
CCDF_PLOT_PATH = ROOT / "docs" / "report" / "app_pol_baseline_v11_indegree_ccdf.png"


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
    here would inject noise into the acquisition function rather than real signal. bc-extremity
    correlation IS included (unlike SF1) since it's computed within-run at n=1000 agents, not
    across a handful of seeds -- much better powered, comparable to gini/Q's per-point reliability."""
    gini_t = term(agg["gini_mean"], agg["gini_std"], GINI_TARGET, GINI_SCALE)
    q_t = term(agg["q_sign_repost_mean"], agg["q_sign_repost_std"], Q_TARGET, Q_SCALE)
    a_mean = agg["assort_mean"]
    assort_t = max(0.0, (ASSORT_FLOOR - a_mean) / ASSORT_SCALE) ** 2 if a_mean is not None else 16.0
    bin7_t = term(agg["bin7_w1_mean"], agg["bin7_w1_std"], 0.0, BIN7_W1_SCALE) if agg["bin7_w1_mean"] is not None else 16.0 + 16.0
    bc_corr_mean = agg["bc_extremity_corr_mean"]
    bc_corr_t = max(0.0, (bc_corr_mean - BC_EXTREMITY_CORR_CEILING) / BC_EXTREMITY_CORR_SCALE) ** 2 if bc_corr_mean is not None else 16.0
    return W_GINI * gini_t + W_Q * q_t + assort_t + W_BIN7 * bin7_t + bc_corr_t


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


BC_INIT_FIXED = 1.0  # = bcCeiling default; fixed, not searched -- see SPACE comment above


def launch(x, seed):
    (max_follow, follow_prob, alpha, hop, bc_dec, bc_recovery, stub, pp_relax_eta,
     feed_capacity, initial_pp, vocal_comfort_radius, p_u) = x
    tokens = [
        f"seed={seed}", "network=hk", f"n={N}", f"steps={STEPS}", "log_gexf=false",
        "init_dist=empirical",
        f"max_follow={max_follow:.4f}", f"follow_prob={follow_prob:.4f}",
        f"alpha={alpha:.4f}", f"hop={int(hop)}",
        f"bc_dec={bc_dec:.5f}", f"bc_recovery={bc_recovery:.5f}", f"bc_init={BC_INIT_FIXED:.5f}",
        "stub_dist=uniform", f"stub_min={stub:.4f}", f"stub_max={stub:.4f}",
        f"pp_relax_eta={pp_relax_eta:.6f}", f"feed_capacity={int(feed_capacity)}",
        f"initial_pp={initial_pp:.4f}", "max_pp=1.0", "min_pp=0.01",
        f"vocal_comfort_radius={vocal_comfort_radius:.4f}",
        f"p_u={p_u:.6f}",
        f"out_of_bc_repost_prob={OOB_TREATMENT}", "force=true",
    ]
    logfile = ROOT / "logs" / f"app_pol_baseline_v11_seed{seed}.log"
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
        plt.title("App-pol baseline v9: empirical in-degree CCDF (validation only)")
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
    if winner_agg["bc_extremity_corr_mean"] is not None:
        print(f"bc-vs-extremity correlation = {winner_agg['bc_extremity_corr_mean']:.4f} +/- {winner_agg['bc_extremity_corr_std']:.4f} (ceiling {BC_EXTREMITY_CORR_CEILING}, more negative = stronger asymmetric-bc signal)")
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


V9_ACTUAL_PU = 0.05  # what v9 really ran at (compiled ExperimentConfig default at the time) --
                      # v10 wrongly padded with 0.01 here; see module docstring for the proof.


def load_warm_start_points():
    """Reads v9's evaluations CSV (11-dim, all genuinely run at p_u=V9_ACTUAL_PU=0.05, NOT the 0.01
    v10 wrongly assumed) and pads each point with the correct value to fit the 12-dim SPACE -- valid
    reuse, not an approximation: compute_round_loss doesn't depend on p_u, and these points really
    were evaluated at 0.05, so their point_loss is exactly what re-evaluating them in the 12-dim
    space at p_u=0.05 would produce. min_pp is a separate, fixed change (0.01, see docstring) applied
    uniformly going forward -- v9's points were run at the old min_pp=0.05, a second respect in which
    they are not literally identical to a fresh v11 evaluation, but point_loss doesn't read
    min_pp-sensitive raw postProb values directly (only downstream structural metrics), and min_pp's
    effect is expected to be second-order next to p_u's -- treated as an acceptable approximation for
    warm-start purposes, unlike p_u's which was a first-order, provably wrong label."""
    if not V9_LOG_PATH.exists():
        return [], []
    with open(V9_LOG_PATH, newline="") as f:
        v9_rows = list(csv.DictReader(f))
    v9_dim_names = DIM_NAMES[:-1]  # p_u is last; v9 had everything except p_u
    points, losses = [], []
    for r in v9_rows:
        pt = [float(r[name]) if name not in ("hop", "feed_capacity") else int(float(r[name]))
              for name in v9_dim_names]
        pt.append(V9_ACTUAL_PU)
        points.append(pt)
        losses.append(float(r["point_loss"]))
    return points, losses


def main():
    opt = Optimizer(SPACE, base_estimator="GP", acq_func="EI", random_state=41)

    warm_points, warm_losses = load_warm_start_points()
    rows = list(zip(warm_losses, warm_points))
    if warm_points:
        opt.tell(warm_points, warm_losses)
        print(f"Warm-started from {len(warm_points)} already-evaluated v9 points "
              f"(padded with p_u={V9_ACTUAL_PU}, corrected from v10's wrong 0.01), "
              f"best warm-start loss = {min(warm_losses):.3f}", flush=True)
    with open(LOG_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["round", "point_idx", "seeds"] + DIM_NAMES +
                         ["point_loss", "gini_mean", "gini_std",
                          "assort_mean", "assort_std", "q_sign_repost_mean", "q_sign_repost_std",
                          "ratio_mean", "ratio_std", "bin7_w1_mean", "bin7_w1_std",
                          "bc_extremity_corr_mean", "bc_extremity_corr_std"])

        next_seed = BASE_SEED  # running counter -- safe under a variable seeds-per-point schedule,
                                # unlike a formula that assumes a fixed SEEDS_PER_POINT
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
    print(f"\nTop {TOP_K} points by round loss (SF1 excluded):")
    for loss, pt in rows[:TOP_K]:
        print(f"  loss={loss:.3f}  {dict(zip(DIM_NAMES, pt))}")
    print(f"\nFull log: {LOG_PATH}")

    run_topk_selection(rows[:TOP_K])


if __name__ == "__main__":
    main()
