"""
2026-07-29 -- Cheap calibration-impact check for the For-You feed redesign
(docs/report/2026-07-29-feed-reach-redesign.md: followees-only reach BFS, hard-cutoff -> distance-decay
acceptance probability). NOT a recalibration -- the user is running the actual joint recalibration on
another server. This script's only job: isolate how much the new feed mechanism itself (decay mode/
lambda, hop) moves the four gate metrics (gini, Q_sign_repost, opinionAssortativity, SF1) and bin7,
relative to the already-recorded OLD-mechanism numbers, so that server has a starting point instead of
guessing blind.

Baseline for comparison (docs/report/2026-07-21-conduit-experiment-design.md, "20-seed confirm of the
same point", 2026-07-27, OLD mechanism -- undirected BFS + hard hop cutoff, same HEAD ExperimentConfig
values otherwise, step=20000, n=20): gini=0.8866+/-0.0031, assort=0.5954+/-0.0673 (below its 0.6 floor),
Q_sign_repost=0.3965+/-0.1024, SF1=1.3236+/-0.2860 (target band [1.19,1.26] -- overshoots).

All runs here use HEAD's current ExperimentConfig.java defaults (no CLI overrides) EXCEPT the swept
feed-mechanism dims -- i.e. exactly the same "current config" point as that confirm, just with today's
code. n=1000, steps=20000, 15 seeds/arm (matches this project's established SF1/bin7 seed-economy
convention: 5 seeds resolves gini/Q/assort, 15 needed to even rank SF1/bin7 -- see the v16 postmortem
referenced in docs/report/2026-07-27 entries).

Two independent small sweeps (not a full cross product -- kept cheap):
  A. decay mechanism, hop fixed at the calibrated value (3): hard, exp{lambda=0.3,1.0,3.0},
     inverse{lambda=0.3,1.0,3.0} = 7 arms x 15 seeds = 105 runs.
  B. hop sensitivity, decay mode fixed at the new default (exp, lambda=1.0): hop in {1,2,3,4,5}
     = 5 arms x 15 seeds = 75 runs (hop=3 arm independent from A's, fresh seeds, cheap to duplicate
     rather than thread state between the two sweeps).

bin7: empirical target is NOT sign-symmetric (bin0=0.267 vs bin6=0.230, ~16% gap) but the model has no
L/R asymmetry mechanism (conservativeBcNarrowing was only ever designed on paper, 2026-07-27 entry,
never implemented -- verified absent from Agent.java/ExperimentConfig.java). Per user decision
(2026-07-29): fit target is the SIGN-SYMMETRIZED empirical array (fold bin_i with bin_{6-i}); the raw
asymmetric-target W1 and the raw (bin0-bin6) gap are reported as diagnostics only, not chased.

Usage: nohup python3 scripts/feed_redesign_calibration_check.py > logs/feed_redesign_check_stdout.log 2>&1 &
"""
import concurrent.futures
import csv
import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy.stats import wasserstein_distance

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
_JARS = list(ROOT.glob("lib/**/*.jar"))
LIBCP = ":".join(str(p) for p in _JARS) + (":" if _JARS else "") + str(ROOT / "bin")

N = 1000
STEPS = 20000
N_SEEDS = 15
BASE_SEED = 5000000  # fresh range, unused so far this session

GINI_TARGET, Q_TARGET, RATIO_TARGET_RANGE, ASSORT_FLOOR = 0.8, 0.48, (1.19, 1.26), 0.6

BIN_CENTERS = np.arange(7)
EMPIRICAL_RAW = np.array([4328.725, 2682.863, 1503.682, 2135.798, 691.065, 1156.761, 3742.547])
EMPIRICAL_RAW = EMPIRICAL_RAW / EMPIRICAL_RAW.sum()
EMPIRICAL_SYM = np.array([
    (EMPIRICAL_RAW[0] + EMPIRICAL_RAW[6]) / 2, (EMPIRICAL_RAW[1] + EMPIRICAL_RAW[5]) / 2,
    (EMPIRICAL_RAW[2] + EMPIRICAL_RAW[4]) / 2, EMPIRICAL_RAW[3],
    (EMPIRICAL_RAW[2] + EMPIRICAL_RAW[4]) / 2, (EMPIRICAL_RAW[1] + EMPIRICAL_RAW[5]) / 2,
    (EMPIRICAL_RAW[0] + EMPIRICAL_RAW[6]) / 2,
])

# (label, extra CLI tokens beyond seed/network/n/steps)
SWEEP_A_DECAY = [
    ("hard", ["feed_decay_mode=hard"]),
    ("exp_lam0.3", ["feed_decay_mode=exp", "feed_decay_lambda=0.3"]),
    ("exp_lam1.0", ["feed_decay_mode=exp", "feed_decay_lambda=1.0"]),  # == current default
    ("exp_lam3.0", ["feed_decay_mode=exp", "feed_decay_lambda=3.0"]),
    ("inverse_lam0.3", ["feed_decay_mode=inverse", "feed_decay_lambda=0.3"]),
    ("inverse_lam1.0", ["feed_decay_mode=inverse", "feed_decay_lambda=1.0"]),
    ("inverse_lam3.0", ["feed_decay_mode=inverse", "feed_decay_lambda=3.0"]),
]
SWEEP_B_HOP = [(f"hop{h}", [f"hop={h}"]) for h in [1, 2, 3, 4, 5]]

LOG_PATH = ROOT / "docs" / "report" / "feed_redesign_calibration_check.csv"


def gini(x):
    x = np.sort(np.asarray(x, dtype=float))
    n = len(x)
    if n == 0 or x.sum() == 0:
        return float("nan")
    cum = np.cumsum(x)
    return (2 * np.sum((np.arange(1, n + 1)) * x) - (n + 1) * cum[-1]) / (n * cum[-1])


def bin7_wasserstein(post_counts, pop_counts, target):
    post_counts = np.asarray(post_counts, dtype=float)
    pop_counts = np.asarray(pop_counts, dtype=float)
    if post_counts.sum() <= 0 or np.any(pop_counts <= 0):
        return None, None
    per_capita_rate = post_counts / pop_counts
    model_props = per_capita_rate / per_capita_rate.sum()
    w1 = float(wasserstein_distance(BIN_CENTERS, BIN_CENTERS, u_weights=model_props, v_weights=target))
    return w1, model_props


def launch(seed, extra_tokens):
    tokens = [f"seed={seed}", "network=hk", f"n={N}", f"steps={STEPS}", "log_gexf=false", "force=true", *extra_tokens]
    logfile = ROOT / "logs" / f"feed_redesign_check_seed{seed}.log"
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
    lifespan_mean = float(last["postLifespanMean"]) if "postLifespanMean" in last else None
    still_active = float(last["postStillActiveAtEvictionFrac"]) if "postStillActiveAtEvictionFrac" in last else None
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
    lr_gap_model = (model_props[0] - model_props[6]) if model_props is not None else None
    lr_gap_emp = float(EMPIRICAL_RAW[0] - EMPIRICAL_RAW[6])
    if q is None or ratio is None:
        return None
    return dict(gini=g, assort=assort, q=q, ratio=ratio, bc_corr=bc_corr,
                b7w1_sym=b7w1_sym, b7w1_raw=b7w1_raw, lr_gap_model=lr_gap_model, lr_gap_emp=lr_gap_emp,
                lifespan_mean=lifespan_mean, still_active=still_active)


def evaluate_seed(seed, extra_tokens):
    p = launch(seed, extra_tokens)
    p.wait()
    return read_metrics(seed)


def run_sweep(name, arms, writer, next_seed):
    print(f"\n=== Sweep {name}: {len(arms)} arms x {N_SEEDS} seeds ===", flush=True)
    summary = []
    for label, tokens in arms:
        seeds = list(range(next_seed, next_seed + N_SEEDS))
        next_seed += N_SEEDS
        print(f"  [{label}] seeds {seeds[0]}-{seeds[-1]}, tokens={tokens}", flush=True)
        with concurrent.futures.ThreadPoolExecutor(max_workers=N_SEEDS) as ex:
            results = list(ex.map(lambda s: evaluate_seed(s, tokens), seeds))
        ok = [r for r in results if r is not None]
        for seed, r in zip(seeds, results):
            if r is None:
                writer.writerow([name, label, seed] + [None] * 11)
            else:
                writer.writerow([name, label, seed, r["gini"], r["assort"], r["q"], r["ratio"],
                                  r["bc_corr"], r["b7w1_sym"], r["b7w1_raw"], r["lr_gap_model"],
                                  r["lifespan_mean"], r["still_active"]])
        if not ok:
            print(f"  [{label}] ALL {N_SEEDS} RUNS FAILED", flush=True)
            continue
        arr = lambda k: np.array([r[k] for r in ok if r[k] is not None])
        g, a, qv, rt, bc = arr("gini"), arr("assort"), arr("q"), arr("ratio"), arr("bc_corr")
        b7s, b7r = arr("b7w1_sym"), arr("b7w1_raw")
        lm, sa = arr("lifespan_mean"), arr("still_active")
        print(f"  [{label}] n={len(ok)}/{N_SEEDS}  gini={g.mean():.4f}+/-{g.std():.4f} (tgt {GINI_TARGET})  "
              f"assort={a.mean():.4f}+/-{a.std():.4f} (floor {ASSORT_FLOOR})  "
              f"Q={qv.mean():.4f}+/-{qv.std():.4f} (tgt {Q_TARGET})  "
              f"SF1={rt.mean():.4f}+/-{rt.std():.4f} (tgt {RATIO_TARGET_RANGE})", flush=True)
        print(f"           bin7_w1_sym={b7s.mean():.4f}+/-{b7s.std():.4f}  bin7_w1_raw={b7r.mean():.4f}+/-{b7r.std():.4f}  "
              f"lifespanMean={lm.mean():.2f}  stillActiveFrac={sa.mean():.3f}", flush=True)
        summary.append((label, len(ok), g.mean(), a.mean(), qv.mean(), rt.mean(), rt.std(), b7s.mean(), b7r.mean()))
    return summary, next_seed


def main():
    with open(LOG_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["sweep", "arm", "seed", "gini", "assort", "q_sign_repost", "ratio",
                          "bc_extremity_corr", "bin7_w1_sym", "bin7_w1_raw", "lr_gap_model",
                          "post_lifespan_mean", "post_still_active_frac"])
        next_seed = BASE_SEED
        summary_a, next_seed = run_sweep("A_decay", SWEEP_A_DECAY, writer, next_seed)
        f.flush()
        summary_b, next_seed = run_sweep("B_hop", SWEEP_B_HOP, writer, next_seed)
        f.flush()

    print("\n=== FINAL SUMMARY ===")
    print(f"OLD mechanism reference (undirected BFS + hard cutoff, n=20, step=20000, recorded "
          f"2026-07-27): gini=0.8866, assort=0.5954 (below floor {ASSORT_FLOOR}), Q=0.3965, "
          f"SF1=1.3236+/-0.2860 (target {RATIO_TARGET_RANGE})")
    print(f"empirical bin7 raw L-R gap (bin0-bin6) = {EMPIRICAL_RAW[0]-EMPIRICAL_RAW[6]:.4f} "
          "(model cannot reproduce this by construction -- no L/R mechanism -- reported not chased)")
    for name, summary in [("A_decay", summary_a), ("B_hop", summary_b)]:
        print(f"\n{name}:")
        for label, n_ok, g, a, qv, rt, rt_std, b7s, b7r in summary:
            print(f"  {label:16s} n={n_ok:2d}  gini={g:.4f}  assort={a:.4f}  Q={qv:.4f}  "
                  f"SF1={rt:.4f}+/-{rt_std:.4f}  bin7_sym={b7s:.4f}  bin7_raw={b7r:.4f}")
    print(f"\nFull per-seed log: {LOG_PATH}", flush=True)


if __name__ == "__main__":
    main()
