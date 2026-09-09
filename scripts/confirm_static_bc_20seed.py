"""
20-seed test (2026-07-20) of the STATIC-bc hypothesis: v9's adopted point uses bc_dec=0.999
(decline ~0.1%/hit) with bc_recovery=0.234 dominating so completely that bc effectively never
moves from bc_init in practice. User's observation: if that's true, the "dynamic" bc mechanism is
vestigial at this operating point and a literally-static bc should reproduce the same result.

bc_dec=1.0 EXACTLY makes this not an approximation: `bc *= 1.0` means decline never changes bc at
all, and since bc starts at bcInit (Agent constructor), the recovery term
`bcRecoveryRate*(bcInit-bc)` is then always multiplying zero too -- bc=bcInit for every agent,
permanently, regardless of bc_recovery's value. Set bc_recovery=0.0 for honesty (it has no effect
once decline is off). bc_init rounded 0.5586->0.56.

Point: hop=1, bc_dec=1.0, bc_recovery=0.0, bc_init=0.56, comfort_pp=0.5. Other dims fixed at
v1-calibrated values, same as v7/v9. Compare against v9's confirmed 20-seed result: Gini=0.872+/-
0.004, Q_sign_repost=0.454+/-0.049, assort=0.650+/-0.050, ratio=1.236+/-0.225.

Usage: python3 scripts/confirm_static_bc_20seed.py
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
BASE_SEED = 890000

POINT = dict(hop=1, bc_dec=1.0, bc_recovery=0.0, bc_init=0.56, comfort_pp=0.5)
FIXED = dict(max_follow=57, follow_prob=0.009, alpha=0.76, feed_capacity=15,
             initial_pp=0.21, stub=0.69, max_pp=1.0)

GINI_TARGET, Q_TARGET, RATIO_TARGET_RANGE, ASSORT_FLOOR = 0.8, 0.48, (1.19, 1.26), 0.6

LOG_PATH = ROOT / "docs" / "report" / "static_bc_20seed_confirm.csv"


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
    logfile = ROOT / "logs" / f"staticbc20_seed{seed}.log"
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
    print(f"Running {N_SEEDS} seeds on the static-bc point: {POINT}", flush=True)
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
