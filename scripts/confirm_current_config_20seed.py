"""
20-seed confirm (2026-07-27) of the current ExperimentConfig.java defaults (HEAD, "new calibration
plan" commit) -- follow-up to the 5-seed self-run check documented in
docs/report/2026-07-21-conduit-experiment-design.md ("Self-run 5-seed check at the 'new calibration
plan' config"). That check found SF1's mean landing inside [1.19,1.26] at n=5, but n=5 is exactly the
sample size this project has repeatedly found noise-dominated for SF1 (past finding: "SF1 needs ~85+
seeds to resolve"). This run quadruples the seed count to shrink the SEM and give SF1 real resolving
power.

No CLI parameter overrides -- runs whatever is compiled into bin/ right now (current
ExperimentConfig.java defaults), same as the user's own manual 5-seed run. Metrics read at BOTH
checkpoint=20000 and checkpoint=40000 (results.csv/modularity.csv log every step, so both are
available from one run), matching the historical validated-checkpoint convention (accessProb=0.1 was
only ever confirmed at steps=20000) while also reporting the longer horizon the current default run
length (40000) actually reaches.

Usage: python3 scripts/confirm_current_config_20seed.py
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
STEPS = 40000
CHECKPOINTS = [20000, 40000]
N_SEEDS = 20
BASE_SEED = 1900000

GINI_TARGET, Q_TARGET, RATIO_TARGET_RANGE, ASSORT_FLOOR = 0.8, 0.48, (1.19, 1.26), 0.6

LOG_PATH = ROOT / "docs" / "report" / "current_config_20seed_confirm.csv"


def gini(x):
    x = np.sort(np.asarray(x, dtype=float))
    n = len(x)
    if n == 0 or x.sum() == 0:
        return float("nan")
    cum = np.cumsum(x)
    return (2 * np.sum((np.arange(1, n + 1)) * x) - (n + 1) * cum[-1]) / (n * cum[-1])


def launch(seed):
    tokens = [f"seed={seed}", "network=hk", f"n={N}", f"steps={STEPS}", "log_gexf=false", "force=true"]
    logfile = ROOT / "logs" / f"confirm_current20_seed{seed}.log"
    logfile.parent.mkdir(exist_ok=True)
    with open(logfile, "w") as lf:
        p = subprocess.Popen(
            ["java", "-Xmx2g", "-cp", LIBCP, "dynamics.OpinionDynamics", *tokens],
            stdout=lf, stderr=subprocess.STDOUT, cwd=ROOT,
        )
    return p


def read_metrics_at(seed, checkpoint):
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
        rows = {int(r["step"]): r for r in csv.DictReader(f)}
    row = rows.get(checkpoint)
    if row is None:
        return None
    assort = float(row["opinionAssortativity"])
    opinion_var = float(row["opinionVar"])
    post_var = float(row["postOpinionVar"])
    ratio = post_var / opinion_var if opinion_var > 0 else None
    q = None
    with open(mod_path, newline="") as f:
        for r in csv.DictReader(f):
            if int(r["step"]) == checkpoint:
                q = float(r["Q_sign_repost"])
    if ratio is None:
        return None
    return g, gf, assort, q, ratio


def evaluate_seed(seed):
    p = launch(seed)
    p.wait()
    return {chk: read_metrics_at(seed, chk) for chk in CHECKPOINTS}


def summarize(label, ms):
    ok = [m for m in ms if m is not None]
    print(f"\n--- {label} (n={len(ok)}/{len(ms)}) ---", flush=True)
    if not ok:
        print("all runs failed at this checkpoint")
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
    print(f"ratio (SF1)   = {ratios.mean():.4f} +/- {ratios.std():.4f}  (SEM {ratios.std()/np.sqrt(len(ratios)):.4f}, target {RATIO_TARGET_RANGE})")
    print(f"ratio per-seed values: {sorted(np.round(ratios, 3).tolist())}")


def main():
    seeds = [BASE_SEED + j for j in range(N_SEEDS)]
    print(f"Running {N_SEEDS} seeds with current bin/ defaults (no CLI overrides): {seeds}", flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=N_SEEDS) as ex:
        results = list(ex.map(evaluate_seed, seeds))

    with open(LOG_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["seed", "checkpoint", "gini", "gamma_fit", "assort", "q_sign_repost", "ratio"])
        for seed, per_chk in zip(seeds, results):
            for chk in CHECKPOINTS:
                m = per_chk.get(chk)
                writer.writerow([seed, chk] + (list(m) if m is not None else [None] * 5))

    for chk in CHECKPOINTS:
        summarize(f"checkpoint={chk}", [per_chk.get(chk) for per_chk in results])

    print(f"\nFull log: {LOG_PATH}", flush=True)


if __name__ == "__main__":
    main()
