"""
Multi-seed confirmation of stage1c's best fully-interior candidate.

stage1c_bo_evaluations.csv's lowest-loss point (round 2, seed 80013: max_follow=100,
follow_prob=0.01, hop=5) sits on 3 of 4 search-box boundaries, so it isn't trustworthy as a
calibrated value (see docs/report/2026-07-17-stage1b-redo2-plan.md). This confirms instead the
best fully-interior point (round 4, seed 80023): max_follow=29.32, follow_prob=0.0145,
alpha=0.763, hop=4, loss=0.197 (single-seed). Same pattern as the Stage 1b redo's 5-seed
confirmation (docs/report/2026-07-15-calibration-decisions.md).

Usage: python3 scripts/stage1c_confirm_seed80023.py
"""
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
STEPS = 15000
GINI_TARGET, GINI_SCALE = 0.8, 0.05
GAMMA_TARGET, GAMMA_SCALE = 2.276, 0.3
ASSORT_FLOOR, ASSORT_SCALE = 0.6, 0.15

MAX_FOLLOW = 100.0
FOLLOW_PROB = 0.01
ALPHA = 0.8835537753483438
HOP = 5
SEEDS = [82000, 82001, 82002, 82003, 82004]

LOG_PATH = ROOT / "docs" / "report" / "stage1c_confirm_seed80013.csv"


def gini(x):
    x = np.sort(np.asarray(x, dtype=float))
    n = len(x)
    if n == 0 or x.sum() == 0:
        return float("nan")
    cum = np.cumsum(x)
    return (2 * np.sum((np.arange(1, n + 1)) * x) - (n + 1) * cum[-1]) / (n * cum[-1])


def compute_loss(g, gf, assort):
    gamma_term = ((gf - GAMMA_TARGET) / GAMMA_SCALE) ** 2 if gf is not None else 4.0
    assort_term = max(0.0, (ASSORT_FLOOR - assort) / ASSORT_SCALE) ** 2
    return ((g - GINI_TARGET) / GINI_SCALE) ** 2 + gamma_term + assort_term


def launch(seed):
    tokens = [
        f"seed={seed}", "network=hk", f"n={N}", f"steps={STEPS}", "log_gexf=false",
        f"max_follow={MAX_FOLLOW:.4f}", f"follow_prob={FOLLOW_PROB:.4f}",
        f"alpha={ALPHA:.4f}", f"hop={HOP}", "force=true",
    ]
    logfile = ROOT / "logs" / f"stage1c_confirm_boundary_seed{seed}.log"
    logfile.parent.mkdir(exist_ok=True)
    with open(logfile, "w") as lf:
        p = subprocess.Popen(
            ["java", "-Xmx2g", "-cp", LIBCP, "dynamics.OpinionDynamics", *tokens],
            stdout=lf, stderr=subprocess.STDOUT, cwd=ROOT,
        )
    return p


def evaluate(seed):
    p = launch(seed)
    p.wait()
    candidates = sorted(ROOT.glob(f"results/run_{seed}_*"), key=lambda x: x.stat().st_mtime)
    if not candidates:
        return None
    d = candidates[-1]
    deg_path = d / "degrees" / f"degree_result_{STEPS}.csv"
    if not deg_path.exists():
        return None
    with open(deg_path, newline="") as f:
        indeg = [int(r["inDegree"]) for r in csv.DictReader(f)]
    g = gini(indeg)
    gf = fit_powerlaw(indeg).get("alpha")
    with open(d / "metrics" / "results.csv", newline="") as f:
        last = list(csv.DictReader(f))[-1]
    assort = float(last["opinionAssortativity"])
    return compute_loss(g, gf, assort), g, gf, assort


def main():
    import concurrent.futures
    print(f"Confirming max_follow={MAX_FOLLOW:.2f}, follow_prob={FOLLOW_PROB:.4f}, "
          f"alpha={ALPHA:.3f}, hop={HOP} across {len(SEEDS)} seeds...", flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(SEEDS)) as ex:
        results = list(ex.map(evaluate, SEEDS))

    with open(LOG_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["seed", "loss", "gini", "gamma_fit", "opinion_assortativity"])
        for seed, r in zip(SEEDS, results):
            if r is None:
                writer.writerow([seed, "FAILED", "", "", ""])
                continue
            loss, g, gf, assort = r
            writer.writerow([seed, loss, g, gf, assort])

    ok = [r for r in results if r is not None]
    if ok:
        losses = np.array([r[0] for r in ok])
        ginis = np.array([r[1] for r in ok])
        gammas = np.array([r[2] for r in ok])
        assorts = np.array([r[3] for r in ok])
        print(f"\nn={len(ok)}/{len(SEEDS)} succeeded")
        print(f"loss   = {losses.mean():.3f} +/- {losses.std():.3f}")
        print(f"gini   = {ginis.mean():.4f} +/- {ginis.std():.4f} (target {GINI_TARGET})")
        print(f"gamma  = {gammas.mean():.3f} +/- {gammas.std():.3f} (target {GAMMA_TARGET})")
        print(f"assort = {assorts.mean():.4f} +/- {assorts.std():.4f} (floor {ASSORT_FLOOR})")
    print(f"\nFull log: {LOG_PATH}")


if __name__ == "__main__":
    main()
