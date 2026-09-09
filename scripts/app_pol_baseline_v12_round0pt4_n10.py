"""
n=10 confirmation of v12's round0/pt4 (2026-07-24): this point was never promoted to v12's top-5
round_loss ranking (point_loss=5.32, well above the top-5's 2.4-3.7), but at its original n=3 read
it looked attractive on SF1 (1.222+/-0.074, in target range [1.19,1.26], unusually tight for n=3)
and on gini (0.804, on target) -- while bc_corr (-0.151) and Q_sign_repost (0.399) were mediocre,
not standout. User asked to re-check at n=10 before reflecting these params into ExperimentConfig
for dashboard inspection (same pattern as round7/pt5 on 2026-07-23).

Point (v12 CSV round=0, point_idx=4, DIM_NAMES order):
max_follow, follow_prob, alpha, hop, bc_dec, bc_recovery, stub, pp_relax_eta, feed_capacity,
initial_pp, vocal_comfort_radius, p_u

Usage: nohup python3 scripts/app_pol_baseline_v12_round0pt4_n10.py \
    > logs/v12_round0pt4_n10_stdout.log 2>&1 &
"""
import concurrent.futures
import csv
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import importlib.util
spec = importlib.util.spec_from_file_location("v12", ROOT / "scripts" / "app_pol_baseline_bo_v12_bc_corr_target.py")
v12 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v12)

POINT = [39.192701156397064, 0.01, 0.65619761495988, 1,
         0.9513440184137525, 0.0015639963835120782, 0.7176936636745083, 0.006524415922499772,
         32, 0.22656227791719802, 0.15749381482180966, 0.048769755887932836]

BASE_SEED = 1300000  # fresh, distinct from every prior range this session
N_SEEDS = 10

LOG_PATH = ROOT / "docs" / "report" / "v12_round0pt4_n10.csv"


def main():
    print(f"Point (round0/pt4): {dict(zip(v12.DIM_NAMES, POINT))}", flush=True)
    seeds = list(range(BASE_SEED, BASE_SEED + N_SEEDS))
    print(f"Evaluating {N_SEEDS} seeds {seeds[0]}-{seeds[-1]}...", flush=True)

    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=N_SEEDS) as ex:
        results = list(ex.map(lambda s: v12.evaluate_seed(POINT, s), seeds))
    ok = [(s, r) for s, r in zip(seeds, results) if r is not None]
    print(f"done in {time.time()-t0:.0f}s, n={len(ok)}/{N_SEEDS} ok", flush=True)

    with open(LOG_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["seed", "gini", "assort", "q_sign_repost", "sf1_ratio", "bin7_w1", "bc_corr"])
        for s, r in ok:
            g, indeg, assort, q, ratio, b7w1, post_counts, pop_counts, bc_corr = r
            writer.writerow([s, g, assort, q, ratio, b7w1, bc_corr])

    def stat(idx):
        vals = [r[idx] for _, r in ok]
        return float(np.mean(vals)), float(np.std(vals))

    g_m, g_s = stat(0)
    a_m, a_s = stat(2)
    q_m, q_s = stat(3)
    r_m, r_s = stat(4)
    b_m, b_s = stat(5)
    c_m, c_s = stat(8)

    print(f"\n=== n={len(ok)} results ===", flush=True)
    print(f"gini           = {g_m:.4f} +/- {g_s:.4f} (target 0.8)", flush=True)
    print(f"assort         = {a_m:.4f} +/- {a_s:.4f} (floor 0.6)", flush=True)
    print(f"Q_sign_repost  = {q_m:.4f} +/- {q_s:.4f} (target 0.48)", flush=True)
    print(f"SF1 ratio      = {r_m:.4f} +/- {r_s:.4f} (target [1.19,1.26])", flush=True)
    print(f"bin7 W1        = {b_m:.4f} +/- {b_s:.4f} (0 = perfect)", flush=True)
    print(f"bc_corr        = {c_m:.4f} +/- {c_s:.4f} (target <= -0.3)", flush=True)
    print(f"\nFull log: {LOG_PATH}", flush=True)


if __name__ == "__main__":
    main()
