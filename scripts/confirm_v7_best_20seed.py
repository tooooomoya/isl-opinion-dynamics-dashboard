"""
20-seed targeted confirm (2026-07-20) of v7's best point alone -- not a search, just resolving
whether its true SF1 ratio mean is closer to the search-round read (1.152+/-0.109, seeds
840145-840149) or the 5-seed confirm read (0.907+/-0.096, seeds 1740000-1740004). Gini/assort
replicated fine between those two batches; ratio didn't (a ~0.25 gap on stds of ~0.10). This is the
one open question left before deciding if v7's point is a credible foundation candidate.

Point: hop=1, bc_dec=0.5610532486900538, bc_recovery=0.10479013671137055,
bc_init=0.8383147043120511, comfort_pp=1.0177066037212583 (v7's best, docs/report/2026-07-18-
joint-stage-calibration.md). Other dims fixed at v1-calibrated values, same as v7.

Usage: python3 scripts/confirm_v7_best_20seed.py
"""
import concurrent.futures
import csv
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dashboard.analysis import fit_powerlaw

ROOT = Path(__file__).resolve().parent.parent
LIBCP = ":".join(str(p) for p in ROOT.glob("lib/*.jar")) + (":" if list(ROOT.glob("lib/*.jar")) else "") + str(ROOT / "bin")
N = 1000
STEPS = 20000
N_SEEDS = 20
BASE_SEED = 850000

POINT = dict(hop=1, bc_dec=0.5610532486900538, bc_recovery=0.10479013671137055,
             bc_init=0.8383147043120511, comfort_pp=1.0177066037212583)
FIXED = dict(max_follow=57, follow_prob=0.009, alpha=0.76, feed_capacity=15,
             initial_pp=0.21, stub=0.69, max_pp=1.0)

GINI_TARGET, Q_TARGET, RATIO_TARGET_RANGE, ASSORT_FLOOR = 0.8, 0.48, (1.19, 1.26), 0.6

LOG_PATH = ROOT / "docs" / "report" / "stage_joint_v7_best_20seed_confirm.csv"


def gini(x):
    x = np.sort(np.asarray(x, dtype=float))
    n = len(x)
    if n == 0 or x.sum() == 0:
        return float("nan")
    cum = np.cumsum(x)
    return (2 * np.sum((np.arange(1, n + 1)) * x) - (n + 1) * cum[-1]) / (n * cum[-1])


def launch(seed):
    tokens = [
        f"seed={seed}", "network=hk", f"n={N}", f"steps={STEPS}", "log_gexf=false",
        f"max_follow={FIXED['max_follow']}", f"follow_prob={FIXED['follow_prob']}",
        f"alpha={FIXED['alpha']}", f"hop={int(POINT['hop'])}",
        f"bc_dec={POINT['bc_dec']:.6f}", f"bc_recovery={POINT['bc_recovery']:.6f}",
        f"bc_init={POINT['bc_init']:.6f}",
        "stub_dist=uniform", f"stub_min={FIXED['stub']}", f"stub_max={FIXED['stub']}",
        f"comfort_pp={POINT['comfort_pp']:.6f}", f"feed_capacity={FIXED['feed_capacity']}",
        f"initial_pp={FIXED['initial_pp']}", f"max_pp={FIXED['max_pp']}",
        "out_of_bc_repost_prob=0.0", "force=true",
    ]
    logfile = ROOT / "logs" / f"v7best20_seed{seed}.log"
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
    gf = fit_powerlaw(indeg).get("alpha")
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
    return g, gf, assort, q, ratio


def evaluate_seed(seed):
    p = launch(seed)
    p.wait()
    return read_metrics(seed)


def main():
    seeds = [BASE_SEED + j for j in range(N_SEEDS)]
    print(f"Running {N_SEEDS} seeds on v7's best point: {POINT}", flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=N_SEEDS) as ex:
        results = list(ex.map(evaluate_seed, seeds))

    with open(LOG_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["seed", "gini", "gamma_fit", "assort", "q_sign_repost", "ratio"])
        for seed, m in zip(seeds, results):
            writer.writerow([seed] + (list(m) if m is not None else [None] * 5))

    ok = [m for m in results if m is not None]
    print(f"n={len(ok)}/{N_SEEDS} succeeded")
    if not ok:
        print("all runs failed")
        return
    ginis = np.array([m[0] for m in ok])
    gammas = np.array([m[1] for m in ok if m[1] is not None])
    assorts = np.array([m[2] for m in ok])
    qs = np.array([m[3] for m in ok if m[3] is not None])
    ratios = np.array([m[4] for m in ok if m[4] is not None])
    print(f"gini          = {ginis.mean():.4f} +/- {ginis.std():.4f}  (SEM {ginis.std()/np.sqrt(len(ginis)):.4f}, target {GINI_TARGET})")
    if len(gammas):
        print(f"gamma_fit (monitored) = {gammas.mean():.3f} +/- {gammas.std():.3f}")
    print(f"assort        = {assorts.mean():.4f} +/- {assorts.std():.4f}  (SEM {assorts.std()/np.sqrt(len(assorts)):.4f}, floor {ASSORT_FLOOR})")
    print(f"Q_sign_repost = {qs.mean():.4f} +/- {qs.std():.4f}  (SEM {qs.std()/np.sqrt(len(qs)):.4f}, target {Q_TARGET})")
    print(f"ratio         = {ratios.mean():.4f} +/- {ratios.std():.4f}  (SEM {ratios.std()/np.sqrt(len(ratios)):.4f}, target {RATIO_TARGET_RANGE})")
    print(f"ratio per-seed values: {sorted(np.round(ratios, 3).tolist())}")
    print(f"Full log: {LOG_PATH}", flush=True)


if __name__ == "__main__":
    main()
