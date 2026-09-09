"""
2026-07-29 -- v4: re-run the joint decay-mechanism search (v2), now grounded by what v2/v3 found.
v2's search let `alpha` roam free and its round-loss-best candidate turned out to be silently
exploiting `alpha=1.0` (the search-box boundary) into a self-reinforcement runaway
(postStillActiveAtEvictionFrac=0.92) rather than a genuine better fit -- see
docs/report/2026-07-29-feed-reach-redesign.md "v2 results" section. User's resolution: alpha is
fixed at 0.7 (calibrated separately, jointly with all other non-feed params, on another server) and
feedTimeDecayTau is fixed at 30 (midpoint of the v3 scan's recommended 20-40 band; v3 found none of
gini/Q/SF1/bin7 respond cleanly to tau in that range, so no reason to re-open it as a free dim here).

Free dims narrow to the 3 that v2 couldn't isolate cleanly: hop, feed_decay_mode, feed_decay_lambda.
Same round-loss methodology as v2 (bin7-shape [symmetrized target] + Q_sign_repost at 5 seeds/point;
SF1 excluded from round loss, noise-dominated at n=5; assort monitored, not gated, per the
2026-07-29 user correction) -- see feed_redesign_v2_joint_bo.py's docstring for the full rationale,
unchanged here.

NEW this round: run_topk_selection flags any candidate whose postStillActiveAtEvictionFrac is a
statistical outlier relative to the other top-K candidates (>2x the median) BEFORE printing the
final selection -- v2's mistake was picking the round_loss/SF1-gap winner without checking this;
this time the check is automatic, not a manual after-the-fact catch.

5 rounds x 6 points x 5 seeds (150 runs) + top-5 x 15 seeds (75 runs) = 225 runs, n=1000, steps=20000.

Usage: nohup python3 scripts/feed_redesign_v4_joint_bo_fixed_alpha_tau.py > logs/feed_redesign_v4_stdout.log 2>&1 &
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
BASE_SEED = 5300000  # fresh range, distinct from v1(5000000s)/v2(5100000s+6000000s)/v3(5200000s)

ROUND_SCHEDULE = [(5, 6)] * 5  # 5 seeds/point, 6 points/round, 5 rounds = 150 runs
TOP_K = 5
SELECT_SEEDS = 15

RATIO_TARGET, RATIO_SCALE = 1.225, 0.05
Q_TARGET, Q_SCALE = 0.48, 0.10
BIN7_W1_SCALE = 0.3
STILL_ACTIVE_OUTLIER_MULT = 2.0  # flag if > this x the median of the top-K candidates

BIN_CENTERS = np.arange(7)
EMPIRICAL_RAW = np.array([4328.725, 2682.863, 1503.682, 2135.798, 691.065, 1156.761, 3742.547])
EMPIRICAL_RAW = EMPIRICAL_RAW / EMPIRICAL_RAW.sum()
EMPIRICAL_SYM = np.array([
    (EMPIRICAL_RAW[0] + EMPIRICAL_RAW[6]) / 2, (EMPIRICAL_RAW[1] + EMPIRICAL_RAW[5]) / 2,
    (EMPIRICAL_RAW[2] + EMPIRICAL_RAW[4]) / 2, EMPIRICAL_RAW[3],
    (EMPIRICAL_RAW[2] + EMPIRICAL_RAW[4]) / 2, (EMPIRICAL_RAW[1] + EMPIRICAL_RAW[5]) / 2,
    (EMPIRICAL_RAW[0] + EMPIRICAL_RAW[6]) / 2,
])

# Fixed at HEAD ExperimentConfig.java defaults, PLUS alpha=0.7 and feed_time_decay_tau=30
# (2026-07-29 decisions) -- out of scope for this pass.
FIXED_TOKENS = [
    "network=hk", "hk_m=15", "hk_a=4", "hk_pt=0.05",
    "max_follow=43.8638", "follow_prob=0.01", "feed_capacity=15",
    "alpha=0.7", "feed_time_decay_tau=30",
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
]
DIM_NAMES = [d.name for d in SPACE]

LOG_PATH = ROOT / "docs" / "report" / "feed_redesign_v4_bo_evaluations.csv"
SELECT_LOG_PATH = ROOT / "docs" / "report" / "feed_redesign_v4_topk_select.csv"


def term(mean, std, target, scale):
    if mean is None:
        return 16.0 + 16.0
    return ((mean - target) / scale) ** 2 + (std / scale) ** 2


def compute_round_loss(agg):
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
    hop, decay_mode, decay_lambda = x
    tokens = [
        f"seed={seed}", f"n={N}", f"steps={STEPS}", "log_gexf=false", "force=true",
        *FIXED_TOKENS,
        f"hop={int(hop)}", f"feed_decay_mode={decay_mode}", f"feed_decay_lambda={float(decay_lambda):.4f}",
    ]
    logfile = ROOT / "logs" / f"feed_redesign_v4_seed{seed}.log"
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
    b7w1_sym, _ = bin7_wasserstein(post_counts, pop_counts, EMPIRICAL_SYM)
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
                  f"Q={agg['q_mean']:.4f}, assort={agg['assort_mean']:.4f} (monitor only), "
                  f"stillActive={agg['still_active_mean']:.4f}", flush=True)
            scored.append((sf1_gap, round_loss, pt, agg, ok))

    # Self-reinforcement outlier check across the top-K candidates (2026-07-29, NEW -- v2's mistake
    # was picking a candidate that turned out to be a runaway artifact without checking this first).
    still_active_vals = [agg["still_active_mean"] for _, _, _, agg, _ in scored if agg["still_active_mean"] is not None]
    median_sa = float(np.median(still_active_vals)) if still_active_vals else None
    flagged = set()
    if median_sa is not None and median_sa > 0:
        for i, (gap, rl, pt, agg, ok) in enumerate(scored):
            sa = agg["still_active_mean"]
            if sa is not None and sa > STILL_ACTIVE_OUTLIER_MULT * median_sa:
                flagged.add(i)
        if flagged:
            print(f"\n*** SELF-REINFORCEMENT OUTLIER WARNING *** median stillActiveFrac across top-K "
                  f"= {median_sa:.4f}. Candidate(s) {sorted(flagged)} exceed {STILL_ACTIVE_OUTLIER_MULT}x "
                  f"that -- their metrics are plausibly a runaway artifact, not a genuine fit. "
                  f"Excluded from automatic selection below.", flush=True)

    eligible = [s for i, s in enumerate(scored) if i not in flagged] or scored  # fall back if all flagged
    eligible.sort(key=lambda r: r[0])
    winner_gap, winner_round_loss, winner_pt, winner_agg, winner_ok = eligible[0]
    print(f"\n=== Selected candidate (excludes self-reinforcement outliers): "
          f"{dict(zip(DIM_NAMES, winner_pt))} ===")
    print(f"round_loss={winner_round_loss:.3f}  SF1={winner_agg['ratio_mean']:.4f}+/-{winner_agg['ratio_std']:.4f} "
          f"(target (1.19, 1.26))")
    for k in ["gini_mean", "assort_mean", "q_mean", "ratio_mean", "bin7_w1_sym_mean", "bin7_w1_raw_mean",
              "lifespan_mean_mean", "still_active_mean"]:
        print(f"{k} = {winner_agg[k]}")
    print(f"\nAll top-K candidates, ranked by SF1 gap (* = self-reinforcement outlier, excluded):")
    scored.sort(key=lambda r: r[0])
    for rank, (gap, rl, pt, agg, ok) in enumerate(scored):
        flag = " *OUTLIER*" if scored.index((gap, rl, pt, agg, ok)) in flagged else ""
        print(f"  #{rank}: {dict(zip(DIM_NAMES, pt))}  round_loss={rl:.3f}  "
              f"SF1={agg['ratio_mean']:.4f}+/-{agg['ratio_std']:.4f}  bin7_sym={agg['bin7_w1_sym_mean']:.4f}  "
              f"gini={agg['gini_mean']:.4f}  Q={agg['q_mean']:.4f}  assort={agg['assort_mean']:.4f}  "
              f"stillActive={agg['still_active_mean']:.4f}  gap={gap:.4f}{flag}")
    print(f"\nFull selection log: {SELECT_LOG_PATH}", flush=True)


def main():
    opt = Optimizer(SPACE, base_estimator="GP", acq_func="EI", random_state=43)
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
