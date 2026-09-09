"""
App-pol baseline calibration v13 (2026-07-25): calibrates the graded-relaxation bc mechanism
(Agent.java updateMyself(), redesigned 2026-07-24, docs/report/2026-07-21-conduit-experiment-
design.md "bc mechanism redesigned to graded relaxation").

Context: dashboard GEXF inspection of v12's round0/pt4 (bc_dec=0.951 in the OLD per-post-ratchet
units) showed the bc histogram collapsed to a single spike at bcCeiling (~85% of agents) with no
separation by opinion extremity, while postProb (fixed by an analogous graded-relaxation redesign on
2026-07-23) looked properly graded. Root cause: the old mechanism applied `bc *= bcDecRate` /
`bc += bcRecoveryRate*(bcCeiling-bc)` once PER POST in the feed -- with feed_capacity ~24-32
posts/step, whichever side (comfortable/uncomfortable) held even a modest feed-majority compounded
across ~20-30 sequential hits within a single step and steamrolled bc to whichever rail that
majority favored. Fixed by aggregating once per step (inBcRate = assimNum/postNum) into a single
graded relaxation toward a shared target, mirroring postProb's fix exactly.

bc_dec/bc_recovery are RETAINED as parameter names/CLI tokens but REINTERPRETED: no longer a
per-post multiplicative-shrink constant and a per-post additive-toward-ceiling constant (two
incommensurable functional forms), but two relaxation RATES (gap-closing fraction per step) toward
the same shared target. Old calibrated values (v9-v12) do NOT carry over -- units changed -- so this
version launches a FRESH search (no warm start), same precedent as v9's fresh launch after the
postProb mechanism redesign.

Search-space note: two smoke tests (2026-07-24, single seed each) at bc_dec/bc_recovery=(0.02,0.01)
and (0.1,0.05) both still showed bc-histogram collapse toward bcCeiling (99.2% and 89.2% of agents
respectively), because bc's own "comfort" measurement (bcDist < this.bc) is self-referential --
unlike postProb's comfortPostRate, which is measured against a FIXED external window
(vocalComfortRadius) deliberately decoupled from postProb itself (R5/D4 design). A wider bc
mechanically admits more posts as "in-bc," creating a positive-feedback runaway once early homophily
sorting begins -- an expected property of adaptive-BCM designs (same self-referential structure as
Li, Luo & Porter 2023 eq. 2.3, which this mechanism follows), not a defect in the redesign itself.
Despite the histogram collapse, bc_extremity_corr=-0.2875 at the (0.1, 0.05) smoke test already beat
most of v9-v12's entire ~250-point search (median ~-0.1 to -0.15) -- promising enough to warrant a
real search rather than more hand-picked points. Ranges widened well past v9-v12's old (near-1.0
multiplicative-retention-constant) ranges to let BO explore the full [small, ~1.0] gap-closing-
fraction space, including values large enough to approximate near-instant per-step target-tracking.

Asymmetry ratio (bcDecRate/bcRecoveryRate) deliberately left free/swept, not hardcoded to a fixed
multiplier (user decision, 2026-07-24) -- neither Vallone (1985) nor Baumeister (2001) give a
precise negativity-dominance ratio to hardcode; the closer quantitative analogue (prospect-theory
loss aversion, Tversky & Kahneman 1991) is ~2-2.5x, notably weaker than the ~10x figure considered
and rejected as an unsupported assumption.

Usage: nohup python3 scripts/app_pol_baseline_bo_v13_graded_bc.py > logs/app_pol_baseline_v13_stdout.log 2>&1 &
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
BASE_SEED = 1330000  # fresh, distinct from every prior range this session (v1-v12 + smoke tests)

# Fresh 12-round/96-point schedule (same shape as v9's post-mechanism-redesign launch) -- no warm
# start, since bc_dec/bc_recovery's units changed and every prior calibration's values under them
# are not comparable (see module docstring).
ROUND_SCHEDULE = [(3, 10)] * 6 + [(5, 6)] * 6
N_ROUNDS = len(ROUND_SCHEDULE)

TOP_K = 5             # candidates carried into the properly-powered SF1 selection stage
SELECT_SEEDS = 20     # SEM~0.043 at typical per-point std=0.19, 95% CI half-width~0.083 --
                       # real resolving power against the 0.07-wide target window, unlike n=5

OOB_TREATMENT = 0.01  # fixed, not searched -- see v12 docstring

GINI_TARGET, GINI_SCALE = 0.8, 0.05
Q_TARGET, Q_SCALE = 0.48, 0.05
RATIO_TARGET, RATIO_SCALE = 1.225, 0.05
ASSORT_FLOOR, ASSORT_SCALE = 0.6, 0.15
BC_EXTREMITY_CORR_TARGET, BC_EXTREMITY_CORR_SCALE = -0.3, 0.15  # unchanged from v12 -- see that
                                                                  # module docstring for the -0.3
                                                                  # (Cohen 1988 "large effect") choice
BIN7_W1_SCALE = 0.3

W_GINI, W_Q, W_BIN7 = 0.5, 0.7, 1.0

EMPIRICAL_POST_BIN_PROPORTIONS = np.array(
    [4328.725, 2682.863, 1503.682, 2135.798, 691.065, 1156.761, 3742.547]
)
EMPIRICAL_POST_BIN_PROPORTIONS = EMPIRICAL_POST_BIN_PROPORTIONS / EMPIRICAL_POST_BIN_PROPORTIONS.sum()
BIN_CENTERS = np.arange(7)

SPACE = [
    Real(5, 50, name="max_follow"),
    Real(0.01, 0.3, prior="log-uniform", name="follow_prob"),
    Real(0.5, 1.0, name="alpha"),
    Integer(1, 5, name="hop"),
    Real(0.0005, 1.0, prior="log-uniform", name="bc_dec"),  # REDEFINED 2026-07-25: now a per-step
        # gap-closing-fraction relaxation rate on net-uncomfortable steps (targetBC < bc), not a
        # per-post multiplicative retention constant. Old v9-v12 range ([0.5,1.0], tuned as "how
        # much of bc survives one uncomfortable post") is not meaningful here -- widened to span
        # from very slow (~0.0005, thousands-of-steps time constant) to near-instant per-step
        # target-tracking (~1.0). Log-uniform since two untuned smoke-test points (0.02, 0.1) both
        # undershot badly (89-99% ceiling pile-up) -- likely needs to explore toward the high end.
    Real(0.0005, 1.0, prior="log-uniform", name="bc_recovery"),  # REDEFINED 2026-07-25: per-step
        # gap-closing-fraction relaxation rate on net-comfortable steps (targetBC >= bc). Same
        # widened range as bc_dec, for the same reason -- both dims independently swept so the
        # asymmetry ratio (negativity dominance) is calibrated, not assumed (see module docstring).
    Real(0.5, 0.9, name="stub"),
    Real(0.0005, 0.1, prior="log-uniform", name="pp_relax_eta"),
    Integer(5, 40, name="feed_capacity"),
    Real(0.01, 0.5, name="initial_pp"),
    Real(0.02, 0.5, prior="log-uniform", name="vocal_comfort_radius"),
    Real(0.0005, 0.1, prior="log-uniform", name="p_u"),
]
DIM_NAMES = [d.name for d in SPACE]

LOG_PATH = ROOT / "docs" / "report" / "app_pol_baseline_v13_bo_evaluations.csv"
SELECT_LOG_PATH = ROOT / "docs" / "report" / "app_pol_baseline_v13_topk_select.csv"
CCDF_LOG_PATH = ROOT / "docs" / "report" / "app_pol_baseline_v13_indegree_ccdf.csv"
CCDF_PLOT_PATH = ROOT / "docs" / "report" / "app_pol_baseline_v13_indegree_ccdf.png"


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
    """Round-level (n=5/point) loss. SF1 excluded (measurement noise at n=5 exceeds the target
    window). bc-extremity correlation included (within-run n=1000, well-powered). Unchanged from
    v12 -- only the search space (bc_dec/bc_recovery ranges) and warm-start policy changed here."""
    gini_t = term(agg["gini_mean"], agg["gini_std"], GINI_TARGET, GINI_SCALE)
    q_t = term(agg["q_sign_repost_mean"], agg["q_sign_repost_std"], Q_TARGET, Q_SCALE)
    a_mean = agg["assort_mean"]
    assort_t = max(0.0, (ASSORT_FLOOR - a_mean) / ASSORT_SCALE) ** 2 if a_mean is not None else 16.0
    bin7_t = term(agg["bin7_w1_mean"], agg["bin7_w1_std"], 0.0, BIN7_W1_SCALE) if agg["bin7_w1_mean"] is not None else 16.0 + 16.0
    bc_corr_mean = agg["bc_extremity_corr_mean"]
    bc_corr_t = ((bc_corr_mean - BC_EXTREMITY_CORR_TARGET) / BC_EXTREMITY_CORR_SCALE) if bc_corr_mean is not None else 16.0
    return W_GINI * gini_t + W_Q * q_t + assort_t + W_BIN7 * bin7_t + bc_corr_t


def bin7_wasserstein(post_counts, pop_counts):
    post_counts = np.asarray(post_counts, dtype=float)
    pop_counts = np.asarray(pop_counts, dtype=float)
    if post_counts.sum() <= 0 or np.any(pop_counts <= 0):
        return 6.0
    per_capita_rate = post_counts / pop_counts
    model_props = per_capita_rate / per_capita_rate.sum()
    return float(wasserstein_distance(BIN_CENTERS, BIN_CENTERS, u_weights=model_props, v_weights=EMPIRICAL_POST_BIN_PROPORTIONS))


BC_INIT_FIXED = 1.0  # = bcCeiling default; fixed, not searched


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
    logfile = ROOT / "logs" / f"app_pol_baseline_v13_seed{seed}.log"
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
        plt.title("App-pol baseline v13: empirical in-degree CCDF (validation only)")
        plt.tight_layout()
        plt.savefig(CCDF_PLOT_PATH, dpi=150)
        plt.close()
    except Exception as e:
        print(f"(CCDF plot skipped: {type(e).__name__}: {e})")


def run_topk_selection(candidates):
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
        print(f"bc-vs-extremity correlation = {winner_agg['bc_extremity_corr_mean']:.4f} +/- {winner_agg['bc_extremity_corr_std']:.4f} (target {BC_EXTREMITY_CORR_TARGET} or more negative, Cohen 'large effect')")
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
    print(f"\nTop {TOP_K} points by round loss (SF1 excluded):")
    for loss, pt in rows[:TOP_K]:
        print(f"  loss={loss:.3f}  {dict(zip(DIM_NAMES, pt))}")
    print(f"\nFull log: {LOG_PATH}")

    run_topk_selection(rows[:TOP_K])


if __name__ == "__main__":
    main()
