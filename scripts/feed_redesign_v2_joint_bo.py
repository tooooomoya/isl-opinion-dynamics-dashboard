"""
2026-07-29 -- Follow-up to feed_redesign_calibration_check.py (same day). That check found the two
new-mechanism knobs (hop, feed_decay_mode/lambda) barely differentiate gini/Q/assort/bin7 from each
other, and alpha (feedAlgoShare) wasn't swept at all despite being the primary For-You knob. This
script does a genuinely JOINT (crossed, not independent 1-D) BO search over the four For-You
recommender params -- hop, feed_decay_mode, feed_decay_lambda, alpha -- while everything else
(structural dims: max_follow/follow_prob/p_u/stub/feed_capacity/access_prob; bc/vocality mechanism
dims: pp_relax_eta/initial_pp/vocal_comfort_radius/bc_init/bc_dec/bc_recovery) stays fixed at HEAD
ExperimentConfig defaults -- those are explicitly out of scope for this pass (deferred to the user's
joint recalibration on another server).

Scope correction from user (2026-07-29), after the cheap check's assortativity finding: assort~0.4
is acceptable, the project has been over-weighting its 0.6 floor -- gini/Q/SF1/bin7 matter more.
Round-level loss below therefore does NOT include assort (monitored/reported only, not optimized).
Same reasoning for gini: the cheap check found it essentially flat (0.87-0.89) across every feed-
mechanism arm, so it carries no gradient here and is excluded from the loss too (still reported).

bin7 fit target is the SIGN-SYMMETRIZED empirical array, not the raw asymmetric one (2026-07-29
decision, see docs/report/2026-07-29-feed-reach-redesign.md "bin7 asymmetry" section) -- the model
has no L/R mechanism, so the raw target isn't closable by any parameter here.

Round loss = bin7_w1_sym term + Q_sign_repost term (5 seeds/point -- this project's established
convention: gini/Q/assort/bin7 resolve at 5 seeds, SF1 needs more). SF1 excluded from round loss
(noise-dominated at n=5, same reasoning as app_pol_baseline v14/v15) -- top-K candidates re-evaluated
at 15 seeds and the final pick is closest to the SF1 target midpoint among those, same convention as
scripts/app_pol_baseline_v15_more_fixed.py's run_topk_selection.

feed_time_decay_tau left OFF (0.0, the shipped default) -- its on/off semantics and magnitude are an
undecided design question (see redesign doc), not a magnitude-only calibration target; not searched
here to avoid conflating a design decision with a calibration knob.

Time-boxed for an unattended ~30-40min run: 6 rounds x 6 points x 5 seeds = 180 runs, then top-5 x 15
seeds = 75 runs. 30 concurrent JVMs (-Xmx2g) x round = 60GB, fine on this machine (112GB/32 cores).

Usage: nohup python3 scripts/feed_redesign_v2_joint_bo.py > logs/feed_redesign_v2_joint_bo_stdout.log 2>&1 &
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
from skopt.space import Real, Integer, Categorical

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
_JARS = list(ROOT.glob("lib/**/*.jar"))
LIBCP = ":".join(str(p) for p in _JARS) + (":" if _JARS else "") + str(ROOT / "bin")

N = 1000
STEPS = 20000
BASE_SEED = 5100000  # fresh range, distinct from the cheap-check's 5000000-5000179

ROUND_SCHEDULE = [(5, 6)] * 6  # 5 seeds/point, 6 points/round, 6 rounds = 180 runs
TOP_K = 5
SELECT_SEEDS = 15

RATIO_TARGET, RATIO_SCALE = 1.225, 0.05
Q_TARGET, Q_SCALE = 0.48, 0.10
BIN7_W1_SCALE = 0.3

BIN_CENTERS = np.arange(7)
EMPIRICAL_RAW = np.array([4328.725, 2682.863, 1503.682, 2135.798, 691.065, 1156.761, 3742.547])
EMPIRICAL_RAW = EMPIRICAL_RAW / EMPIRICAL_RAW.sum()
EMPIRICAL_SYM = np.array([
    (EMPIRICAL_RAW[0] + EMPIRICAL_RAW[6]) / 2, (EMPIRICAL_RAW[1] + EMPIRICAL_RAW[5]) / 2,
    (EMPIRICAL_RAW[2] + EMPIRICAL_RAW[4]) / 2, EMPIRICAL_RAW[3],
    (EMPIRICAL_RAW[2] + EMPIRICAL_RAW[4]) / 2, (EMPIRICAL_RAW[1] + EMPIRICAL_RAW[5]) / 2,
    (EMPIRICAL_RAW[0] + EMPIRICAL_RAW[6]) / 2,
])

# Fixed at HEAD ExperimentConfig.java defaults -- out of scope for this pass.
FIXED_TOKENS = [
    "network=hk", "hk_m=15", "hk_a=4", "hk_pt=0.05",
    "max_follow=43.8638", "follow_prob=0.01", "feed_capacity=15",
    "access_prob=0.1", "p_u=0.05",
    "bc_dec=0.500000", "bc_recovery=0.000100", "bc_floor=0.2", "bc_ceiling=1.0", "bc_init=0.800000",
    "vocal_comfort_radius=0.1", "repost_prob=0.1", "relay_enabled=false",
    "out_of_bc_repost_prob=0.01", "rel_attrib=original",
    "stub_dist=uniform", "stub_min=0.82", "stub_max=0.82",
    "evict_beta=-1", "init_prune=trim",
    "initial_pp=0.25537", "max_pp=1.0", "min_pp=0.01", "pp_relax_eta=0.100000",
    "neutral_band=0.2",
]

SPACE = [
    Integer(1, 5, name="hop"),
    Categorical(["hard", "exp", "inverse"], name="decay_mode"),
    Real(0.1, 5.0, prior="log-uniform", name="decay_lambda"),
    Real(0.3, 1.0, name="alpha"),
]
DIM_NAMES = [d.name for d in SPACE]

LOG_PATH = ROOT / "docs" / "report" / "feed_redesign_v2_bo_evaluations.csv"
SELECT_LOG_PATH = ROOT / "docs" / "report" / "feed_redesign_v2_topk_select.csv"


def term(mean, std, target, scale):
    if mean is None:
        return 16.0 + 16.0
    return ((mean - target) / scale) ** 2 + (std / scale) ** 2


def compute_round_loss(agg):
    """bin7 (symmetrized target) + Q_sign_repost. SF1 excluded (n=5 noise-dominated, selected
    post-hoc at n=15). gini/assort excluded (flat / soft per 2026-07-29 user correction)."""
    if agg["bin7_w1_sym_mean"] is None or agg["q_mean"] is None:
        return 16.0 + 16.0
    return (term(agg["bin7_w1_sym_mean"], agg["bin7_w1_sym_std"], 0.0, BIN7_W1_SCALE)
            + term(agg["q_mean"], agg["q_std"], Q_TARGET, Q_SCALE))


def bin7_wasserstein(post_counts, pop_counts, target):
    post_counts = np.asarray(post_counts, dtype=float)
    pop_counts = np.asarray(pop_counts, dtype=float)
    if post_counts.sum() <= 0 or np.any(pop_counts <= 0):
        return None, None
    per_capita_rate = post_counts / pop_counts
    model_props = per_capita_rate / per_capita_rate.sum()
    w1 = float(wasserstein_distance(BIN_CENTERS, BIN_CENTERS, u_weights=model_props, v_weights=target))
    return w1, model_props


def gini(x):
    x = np.sort(np.asarray(x, dtype=float))
    n = len(x)
    if n == 0 or x.sum() == 0:
        return float("nan")
    cum = np.cumsum(x)
    return (2 * np.sum((np.arange(1, n + 1)) * x) - (n + 1) * cum[-1]) / (n * cum[-1])


def launch(x, seed):
    hop, decay_mode, decay_lambda, alpha = x
    tokens = [
        f"seed={seed}", f"n={N}", f"steps={STEPS}", "log_gexf=false", "force=true",
        *FIXED_TOKENS,
        f"hop={int(hop)}", f"alpha={float(alpha):.4f}",
        f"feed_decay_mode={decay_mode}", f"feed_decay_lambda={float(decay_lambda):.4f}",
    ]
    logfile = ROOT / "logs" / f"feed_redesign_v2_seed{seed}.log"
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
    lifespan_mean = float(last.get("postLifespanMean", "nan") or "nan")
    still_active = float(last.get("postStillActiveAtEvictionFrac", "nan") or "nan")
    q = None
    with open(mod_path, newline="") as f:
        for row in csv.DictReader(f):
            if int(row["step"]) == STEPS:
                q = float(row["Q_sign_repost"])
    with open(bin7_path, newline="") as f:
        bin7_rows = list(csv.DictReader(f))
        post_counts = [int(r["postCount"]) for r in bin7_rows]
        pop_counts = [int(r["popCount"]) for r in bin7_rows]
    b7w1_sym, model_props = bin7_wasserstein(post_counts, pop_counts, EMPIRICAL_SYM)
    b7w1_raw, _ = bin7_wasserstein(post_counts, pop_counts, EMPIRICAL_RAW)
    if q is None or ratio is None or b7w1_sym is None:
        return None
    return dict(gini=g, assort=assort, q=q, ratio=ratio, bin7_w1_sym=b7w1_sym, bin7_w1_raw=b7w1_raw,
                lifespan_mean=lifespan_mean, still_active=still_active)


def evaluate_seed(x, seed):
    p = launch(x, seed)
    p.wait()
    return read_metrics(seed)


def aggregate(metrics):
    agg = {}
    for name in ["gini", "assort", "q", "ratio", "bin7_w1_sym", "bin7_w1_raw", "lifespan_mean", "still_active"]:
        vals = [m[name] for m in metrics if m.get(name) is not None and not np.isnan(m[name])]
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
    print(f"\n=== Top-{len(candidates)} candidates by round loss (bin7_sym + Q), re-evaluating each "
          f"with {SELECT_SEEDS} seeds for SF1 selection ===", flush=True)
    with open(SELECT_LOG_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["candidate_rank", "round_loss"] + DIM_NAMES +
                         ["n_ok", "gini_mean", "gini_std", "assort_mean", "assort_std",
                          "q_mean", "q_std", "ratio_mean", "ratio_std",
                          "bin7_w1_sym_mean", "bin7_w1_sym_std", "bin7_w1_raw_mean",
                          "lifespan_mean_mean", "still_active_mean"])
        scored = []
        for k, (round_loss, pt) in enumerate(candidates):
            seeds = [BASE_SEED + 900000 + k * SELECT_SEEDS + j for j in range(SELECT_SEEDS)]
            print(f"  candidate {k} (round_loss={round_loss:.3f}, {dict(zip(DIM_NAMES, pt))}): "
                  f"evaluating {SELECT_SEEDS} seeds {seeds[0]}-{seeds[-1]}...", flush=True)
            t0 = time.time()
            with concurrent.futures.ThreadPoolExecutor(max_workers=SELECT_SEEDS) as ex:
                results = list(ex.map(lambda s: evaluate_seed(pt, s), seeds))
            ok = [m for m in results if m is not None]
            agg = aggregate(ok)
            writer.writerow([k, round_loss] + list(pt) + [
                len(ok), agg["gini_mean"], agg["gini_std"], agg["assort_mean"], agg["assort_std"],
                agg["q_mean"], agg["q_std"], agg["ratio_mean"], agg["ratio_std"],
                agg["bin7_w1_sym_mean"], agg["bin7_w1_sym_std"], agg["bin7_w1_raw_mean"],
                agg["lifespan_mean_mean"], agg["still_active_mean"],
            ])
            f.flush()
            sf1_gap = abs(agg["ratio_mean"] - RATIO_TARGET) if agg["ratio_mean"] is not None else float("inf")
            print(f"  candidate {k} done in {time.time()-t0:.0f}s: n={len(ok)}/{SELECT_SEEDS}, "
                  f"SF1={agg['ratio_mean']:.4f}+/-{agg['ratio_std']:.4f}, gap={sf1_gap:.4f}, "
                  f"bin7_sym={agg['bin7_w1_sym_mean']:.4f}, gini={agg['gini_mean']:.4f}, "
                  f"Q={agg['q_mean']:.4f}, assort={agg['assort_mean']:.4f} (monitor only)", flush=True)
            scored.append((sf1_gap, round_loss, pt, agg, ok))

    scored.sort(key=lambda r: r[0])
    winner_gap, winner_round_loss, winner_pt, winner_agg, winner_ok = scored[0]
    print(f"\n=== Selected candidate: {dict(zip(DIM_NAMES, winner_pt))} ===")
    print(f"round_loss={winner_round_loss:.3f}  SF1={winner_agg['ratio_mean']:.4f}+/-{winner_agg['ratio_std']:.4f} "
          f"(target (1.19, 1.26))")
    for k in ["gini_mean", "assort_mean", "q_mean", "ratio_mean", "bin7_w1_sym_mean", "bin7_w1_raw_mean",
              "lifespan_mean_mean", "still_active_mean"]:
        print(f"{k} = {winner_agg[k]}")
    print(f"\nAll top-K candidates, ranked by SF1 gap:")
    for rank, (gap, rl, pt, agg, ok) in enumerate(scored):
        print(f"  #{rank}: {dict(zip(DIM_NAMES, pt))}  round_loss={rl:.3f}  "
              f"SF1={agg['ratio_mean']:.4f}+/-{agg['ratio_std']:.4f}  bin7_sym={agg['bin7_w1_sym_mean']:.4f}  "
              f"gini={agg['gini_mean']:.4f}  Q={agg['q_mean']:.4f}  assort={agg['assort_mean']:.4f}  "
              f"gap={gap:.4f}")
    print(f"\nFull selection log: {SELECT_LOG_PATH}", flush=True)


def main():
    opt = Optimizer(SPACE, base_estimator="GP", acq_func="EI", random_state=42)
    rows = []
    with open(LOG_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["round", "point_idx", "seeds"] + DIM_NAMES +
                         ["point_loss", "gini_mean", "gini_std", "assort_mean", "assort_std",
                          "q_mean", "q_std", "ratio_mean", "ratio_std",
                          "bin7_w1_sym_mean", "bin7_w1_sym_std", "bin7_w1_raw_mean",
                          "lifespan_mean_mean", "still_active_mean"])
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
                    point_loss, agg["gini_mean"], agg["gini_std"], agg["assort_mean"], agg["assort_std"],
                    agg["q_mean"], agg["q_std"], agg["ratio_mean"], agg["ratio_std"],
                    agg["bin7_w1_sym_mean"], agg["bin7_w1_sym_std"], agg["bin7_w1_raw_mean"],
                    agg["lifespan_mean_mean"], agg["still_active_mean"],
                ])
                rows.append((point_loss, pt))
            f.flush()
            best = min(r[0] for r in rows)
            print(f"[round {rnd}] done in {time.time()-t0:.0f}s, best point_loss so far = {best:.3f}", flush=True)

    rows.sort(key=lambda r: r[0])
    print(f"\nTop {TOP_K} points by round loss (bin7_sym + Q):")
    for loss, pt in rows[:TOP_K]:
        print(f"  loss={loss:.3f}  {dict(zip(DIM_NAMES, pt))}")
    print(f"\nFull log: {LOG_PATH}")
    run_topk_selection(rows[:TOP_K])


if __name__ == "__main__":
    main()
