"""
OAT scan (2026-07-21): how fast do the calibrated structural facts (Gini, Q_sign_repost, assort)
and apparent-polarization ratio (SF1) degrade as out_of_bc_repost_prob rises from 0 toward
repost_prob (0.1), at the current v7/Path-1 default point (hop=1, bc_dec=0.561, bc_recovery=0.105,
bc_init=0.838, comfort_pp=1.018 -- all left at ExperimentConfig defaults, not overridden here)?

Purpose: pick a non-arbitrary out_of_bc_repost_prob treatment dose for the upcoming
"secede moderate hubs from an app-pol-producing condition" experiment
(docs/report/2026-07-21-conduit-experiment-design.md) -- highest value that doesn't wreck the
already-calibrated structural facts, rather than an arbitrary guess or (rejected) equal-to-
repost_prob coupling.

Cheap first pass: 3 seeds per point, no full recalibration. Not a BO search -- just a direct
one-at-a-time sweep over out_of_bc_repost_prob with everything else held at the v7 defaults.

Usage: python3 scripts/oob_repost_prob_scan.py
"""
import concurrent.futures
import csv
import subprocess
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
LIBCP = ":".join(str(p) for p in ROOT.glob("lib/*.jar")) + (":" if list(ROOT.glob("lib/*.jar")) else "") + str(ROOT / "bin")
N = 1000
STEPS = 20000
OOB_VALUES = [0.0, 0.01, 0.02, 0.05, 0.1]
SEEDS_PER_POINT = 3
BASE_SEED = 970000

GINI_TARGET = 0.8
Q_TARGET = 0.48
ASSORT_FLOOR = 0.6
RATIO_TARGET_LOW, RATIO_TARGET_HIGH = 1.19, 1.26

LOG_PATH = ROOT / "docs" / "report" / "oob_repost_prob_scan_raw.csv"
SUMMARY_PATH = ROOT / "docs" / "report" / "oob_repost_prob_scan_summary.csv"


def gini(x):
    x = np.sort(np.asarray(x, dtype=float))
    n = len(x)
    if n == 0 or x.sum() == 0:
        return float("nan")
    cum = np.cumsum(x)
    return (2 * np.sum((np.arange(1, n + 1)) * x) - (n + 1) * cum[-1]) / (n * cum[-1])


def launch(oob, seed):
    tokens = [
        f"seed={seed}", "network=hk", f"n={N}", f"steps={STEPS}", "log_gexf=false",
        f"out_of_bc_repost_prob={oob:.4f}", "force=true",
    ]
    logfile = ROOT / "logs" / f"oob_scan_oob{oob:.4f}_seed{seed}.log"
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
    if q is None or ratio is None:
        return None
    return g, assort, q, ratio


def evaluate_seed(oob, seed):
    p = launch(oob, seed)
    p.wait()
    return read_metrics(seed)


def main():
    jobs = [(oob, BASE_SEED + i * 100 + j) for i, oob in enumerate(OOB_VALUES) for j in range(SEEDS_PER_POINT)]
    print(f"Launching {len(jobs)} runs (n={N}, steps={STEPS}) across {len(OOB_VALUES)} "
          f"out_of_bc_repost_prob values x {SEEDS_PER_POINT} seeds...", flush=True)
    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(jobs)) as ex:
        results = list(ex.map(lambda j: evaluate_seed(*j), jobs))
    print(f"All runs finished in {time.time() - t0:.0f}s", flush=True)

    with open(LOG_PATH, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["out_of_bc_repost_prob", "seed", "gini", "assort", "q_sign_repost", "ratio"])
        for (oob, seed), m in zip(jobs, results):
            row = list(m) if m is not None else [None] * 4
            w.writerow([oob, seed] + row)

    print(f"\n{'oob_prob':>10} {'gini':>16} {'Q_sign_repost':>18} {'assort':>16} {'ratio(SF1)':>16}")
    summary_rows = []
    for oob in OOB_VALUES:
        pts = [m for (o, s), m in zip(jobs, results) if o == oob and m is not None]
        n_ok = len(pts)
        if n_ok == 0:
            print(f"{oob:>10.4f} {'FAILED':>16}")
            continue
        g_mean, g_std = np.mean([p[0] for p in pts]), np.std([p[0] for p in pts])
        a_mean, a_std = np.mean([p[1] for p in pts]), np.std([p[1] for p in pts])
        q_mean, q_std = np.mean([p[2] for p in pts]), np.std([p[2] for p in pts])
        r_mean, r_std = np.mean([p[3] for p in pts]), np.std([p[3] for p in pts])
        print(f"{oob:>10.4f} {g_mean:>7.4f}+/-{g_std:<6.4f} {q_mean:>9.4f}+/-{q_std:<6.4f} "
              f"{a_mean:>7.4f}+/-{a_std:<6.4f} {r_mean:>7.4f}+/-{r_std:<6.4f}  (n={n_ok}/{SEEDS_PER_POINT})")
        summary_rows.append([oob, n_ok, g_mean, g_std, q_mean, q_std, a_mean, a_std, r_mean, r_std])
    print(f"\nTargets: gini~{GINI_TARGET}, Q_sign_repost~{Q_TARGET}, assort>={ASSORT_FLOOR}, "
          f"ratio(SF1) in [{RATIO_TARGET_LOW},{RATIO_TARGET_HIGH}]")

    with open(SUMMARY_PATH, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["out_of_bc_repost_prob", "n_ok", "gini_mean", "gini_std", "q_sign_repost_mean",
                    "q_sign_repost_std", "assort_mean", "assort_std", "ratio_mean", "ratio_std"])
        w.writerows(summary_rows)
    print(f"\nRaw: {LOG_PATH}\nSummary: {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
