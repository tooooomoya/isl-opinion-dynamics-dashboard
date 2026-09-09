"""
2026-07-29 -- Follow-up to feed_redesign_v2_joint_bo.py. That run showed alpha pinned near/at its
upper bound produces a self-reinforcement runaway (still_active_frac=0.92 at alpha=1.0) because
feedTimeDecayTau defaults to 0 (off) -- nothing ever penalizes a post just for being old, only its
current repost rate, which can stay high indefinitely under sustained algorithmic exposure. User's
review conclusion: tau should NEVER be exactly 0 (some organic decay should always be present) --
search space is (0, tau_max], not [0, tau_max]. Alpha itself is being calibrated jointly with all
other (structural + bc/vocality) params on the user's other server; this script isolates tau alone,
holding everything else -- including alpha=0.7 (2026-07-29 decision above) and hop/decay_mode/lambda
-- at HEAD ExperimentConfig's shipped defaults ("more or less plausible model"), so the readout is a
clean one-dimensional mechanism explanation, not another black-box joint search.

Grid, not BO -- a single, mechanistically-understood dimension is more useful read as a monotonic
(or non-monotonic) curve than optimized against a loss. Log-spaced from aggressive decay to
effectively-off, bracketing VELOCITY_WINDOW=100 (Const.java) since that's the natural timescale tau
competes against: tau=[5, 10, 20, 40, 80, 160, 320, 640]. At tau=5, score decays to ~2e-9 of its
age=0 value by the time a post could be evicted (age=100) -- near-total suppression, included to see
the degenerate floor. At tau=640, exp(-100/640)=0.86 at the eviction boundary -- barely different
from tau=0/off, included to see convergence back toward the v2 pathological baseline
(still_active~0.92 at alpha=1.0; expect a lower asymptote here since alpha is fixed at 0.7, not 1.0).

Primary outcomes: postLifespanMean / postStillActiveAtEvictionFrac (what tau directly targets) +
gini/Q/SF1/bin7 (does fixing self-reinforcement move the calibration targets, and if so which way).
assort logged, not gated (2026-07-29 user correction -- see docs/report/2026-07-29-feed-reach-
redesign.md "feedback-assort-not-hard-gate"). bin7 fit target is the sign-symmetrized empirical array
(2026-07-29 decision, model has no L/R mechanism).

8 arms x 15 seeds = 120 runs, n=1000, steps=20000.

Usage: nohup python3 scripts/feed_redesign_v3_time_decay_tau_scan.py > logs/feed_redesign_v3_tau_stdout.log 2>&1 &
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
BASE_SEED = 5200000  # fresh range

GINI_TARGET, Q_TARGET, RATIO_TARGET_RANGE, ASSORT_FLOOR = 0.8, 0.48, (1.19, 1.26), 0.6
TAU_GRID = [5, 10, 20, 40, 80, 160, 320, 640]

BIN_CENTERS = np.arange(7)
EMPIRICAL_RAW = np.array([4328.725, 2682.863, 1503.682, 2135.798, 691.065, 1156.761, 3742.547])
EMPIRICAL_RAW = EMPIRICAL_RAW / EMPIRICAL_RAW.sum()
EMPIRICAL_SYM = np.array([
    (EMPIRICAL_RAW[0] + EMPIRICAL_RAW[6]) / 2, (EMPIRICAL_RAW[1] + EMPIRICAL_RAW[5]) / 2,
    (EMPIRICAL_RAW[2] + EMPIRICAL_RAW[4]) / 2, EMPIRICAL_RAW[3],
    (EMPIRICAL_RAW[2] + EMPIRICAL_RAW[4]) / 2, (EMPIRICAL_RAW[1] + EMPIRICAL_RAW[5]) / 2,
    (EMPIRICAL_RAW[0] + EMPIRICAL_RAW[6]) / 2,
])

# Fixed at HEAD ExperimentConfig.java defaults ("more or less plausible model") -- alpha=0.7 per the
# 2026-07-29 decision, hop/decay_mode/lambda at their shipped defaults (not re-optimized here).
FIXED_TOKENS = [
    "network=hk", "hk_m=15", "hk_a=4", "hk_pt=0.05",
    "max_follow=43.8638", "follow_prob=0.01", "feed_capacity=15",
    "alpha=0.7", "hop=3", "feed_decay_mode=exp", "feed_decay_lambda=1.0",
    "access_prob=0.1", "p_u=0.05",
    "bc_dec=0.500000", "bc_recovery=0.000100", "bc_floor=0.2", "bc_ceiling=1.0", "bc_init=0.800000",
    "vocal_comfort_radius=0.1", "repost_prob=0.1", "relay_enabled=false",
    "out_of_bc_repost_prob=0.01", "rel_attrib=original",
    "stub_dist=uniform", "stub_min=0.82", "stub_max=0.82",
    "evict_beta=-1", "init_prune=trim",
    "initial_pp=0.25537", "max_pp=1.0", "min_pp=0.01", "pp_relax_eta=0.100000",
    "neutral_band=0.2",
]

LOG_PATH = ROOT / "docs" / "report" / "feed_redesign_v3_tau_scan.csv"


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


def launch(seed, tau):
    tokens = [f"seed={seed}", f"n={N}", f"steps={STEPS}", "log_gexf=false", "force=true",
              *FIXED_TOKENS, f"feed_time_decay_tau={tau:.4f}"]
    logfile = ROOT / "logs" / f"feed_redesign_v3_seed{seed}.log"
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


def evaluate_seed(seed, tau):
    p = launch(seed, tau)
    p.wait()
    return read_metrics(seed)


def main():
    with open(LOG_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["tau", "seed", "gini", "assort", "q_sign_repost", "ratio",
                          "bin7_w1_sym", "bin7_w1_raw", "post_lifespan_mean", "post_still_active_frac"])
        next_seed = BASE_SEED
        summary = []
        for tau in TAU_GRID:
            seeds = list(range(next_seed, next_seed + N_SEEDS))
            next_seed += N_SEEDS
            print(f"\n=== tau={tau} === seeds {seeds[0]}-{seeds[-1]}", flush=True)
            with concurrent.futures.ThreadPoolExecutor(max_workers=N_SEEDS) as ex:
                results = list(ex.map(lambda s: evaluate_seed(s, tau), seeds))
            ok = [r for r in results if r is not None]
            for seed, r in zip(seeds, results):
                if r is None:
                    writer.writerow([tau, seed] + [None] * 8)
                else:
                    writer.writerow([tau, seed, r["gini"], r["assort"], r["q"], r["ratio"],
                                      r["bin7_w1_sym"], r["bin7_w1_raw"], r["lifespan_mean"], r["still_active"]])
            f.flush()
            if not ok:
                print(f"  tau={tau} ALL {N_SEEDS} RUNS FAILED", flush=True)
                continue
            arr = lambda k: np.array([r[k] for r in ok if r[k] is not None])
            g, a, qv, rt = arr("gini"), arr("assort"), arr("q"), arr("ratio")
            b7s, b7r, lm, sa = arr("bin7_w1_sym"), arr("bin7_w1_raw"), arr("lifespan_mean"), arr("still_active")
            print(f"  n={len(ok)}/{N_SEEDS}  gini={g.mean():.4f}+/-{g.std():.4f} (tgt {GINI_TARGET})  "
                  f"assort={a.mean():.4f}+/-{a.std():.4f} (floor {ASSORT_FLOOR}, monitor only)  "
                  f"Q={qv.mean():.4f}+/-{qv.std():.4f} (tgt {Q_TARGET})  "
                  f"SF1={rt.mean():.4f}+/-{rt.std():.4f} (tgt {RATIO_TARGET_RANGE})", flush=True)
            print(f"  bin7_w1_sym={b7s.mean():.4f}+/-{b7s.std():.4f}  bin7_w1_raw={b7r.mean():.4f}+/-{b7r.std():.4f}  "
                  f"lifespanMean={lm.mean():.2f}  stillActiveFrac={sa.mean():.3f}+/-{sa.std():.3f}", flush=True)
            summary.append((tau, len(ok), g.mean(), a.mean(), qv.mean(), rt.mean(), rt.std(),
                             b7s.mean(), lm.mean(), sa.mean()))

    print("\n=== FINAL SUMMARY (tau grid) ===")
    print(f"{'tau':>6} {'n':>3} {'gini':>7} {'assort':>7} {'Q':>7} {'SF1':>14} "
          f"{'bin7sym':>8} {'lifespan':>9} {'stillActive':>12}")
    for tau, n_ok, g, a, qv, rt, rt_std, b7s, lm, sa in summary:
        print(f"{tau:6d} {n_ok:3d} {g:7.4f} {a:7.4f} {qv:7.4f} {rt:6.4f}+/-{rt_std:.4f} "
              f"{b7s:8.4f} {lm:9.2f} {sa:12.3f}")
    print(f"\nFull per-seed log: {LOG_PATH}", flush=True)


if __name__ == "__main__":
    main()
