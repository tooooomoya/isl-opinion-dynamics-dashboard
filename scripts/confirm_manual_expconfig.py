"""
Confirm run for the user's hand-picked ExperimentConfig defaults (2026-07-20), evaluated with the
same 5-seed harness and metrics as the v1-v4 joint BO scripts, for direct comparability.

Changes vs. the v1 joint-calibration defaults (see git diff src/experiment/ExperimentConfig.java):
  feedHopH        1    -> 2
  bcRecoveryRate  0.08 -> 0.001   (near-frozen recovery)
  bcDecRate       0.63 -> 0.98    (near-frozen decline: bc *= 0.98 per out-of-bc hit)
  bcInit          0.6  -> 1.0    (back to ceiling)
  maxPostProb     0.5  -> 1.0
  comfortPpFactor 2.07 -> 1.05
No CLI overrides passed -- runs whatever is compiled into bin/ right now.

Usage: python3 scripts/confirm_manual_expconfig.py
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
CONFIRM_SEEDS = 5
BASE_SEED = 810000

GINI_TARGET, Q_TARGET, RATIO_TARGET_RANGE = 0.8, 0.48, (1.19, 1.26)

LOG_PATH = ROOT / "docs" / "report" / "manual_expconfig_confirm.csv"


def gini(x):
    x = np.sort(np.asarray(x, dtype=float))
    n = len(x)
    if n == 0 or x.sum() == 0:
        return float("nan")
    cum = np.cumsum(x)
    return (2 * np.sum((np.arange(1, n + 1)) * x) - (n + 1) * cum[-1]) / (n * cum[-1])


def launch(seed):
    tokens = [f"seed={seed}", "network=hk", f"n={N}", f"steps={STEPS}", "log_gexf=false", "force=true"]
    logfile = ROOT / "logs" / f"manual_expconfig_seed{seed}.log"
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
    m = read_metrics(seed)
    if m is None:
        return None
    return m


def main():
    seeds = [BASE_SEED + j for j in range(CONFIRM_SEEDS)]
    print(f"Running {CONFIRM_SEEDS} seeds with current bin/ defaults: {seeds}", flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONFIRM_SEEDS) as ex:
        results = list(ex.map(evaluate_seed, seeds))

    with open(LOG_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["seed", "gini", "gamma_fit", "assort", "q_sign_repost", "ratio"])
        for seed, m in zip(seeds, results):
            if m is None:
                writer.writerow([seed, None, None, None, None, None])
            else:
                writer.writerow([seed] + list(m))

    ok = [m for m in results if m is not None]
    print(f"n={len(ok)}/{CONFIRM_SEEDS} succeeded")
    if not ok:
        print("all runs failed")
        return
    ginis = np.array([m[0] for m in ok])
    gammas = np.array([m[1] for m in ok if m[1] is not None])
    assorts = np.array([m[2] for m in ok])
    qs = np.array([m[3] for m in ok if m[3] is not None])
    ratios = np.array([m[4] for m in ok if m[4] is not None])
    print(f"gini          = {ginis.mean():.4f} +/- {ginis.std():.4f} (target {GINI_TARGET})")
    if len(gammas):
        print(f"gamma_fit (monitored) = {gammas.mean():.3f} +/- {gammas.std():.3f}")
    print(f"assort (monitored)     = {assorts.mean():.4f} +/- {assorts.std():.4f}")
    if len(qs):
        print(f"Q_sign_repost = {qs.mean():.4f} +/- {qs.std():.4f} (target {Q_TARGET})")
    if len(ratios):
        print(f"apparent-polarization ratio = {ratios.mean():.4f} +/- {ratios.std():.4f} "
              f"(target {RATIO_TARGET_RANGE})")
    print(f"Full log: {LOG_PATH}")


if __name__ == "__main__":
    main()
