"""
SF1 batch-to-batch reproducibility check (2026-07-24): does a single n=20 confirmation batch's own
std/sqrt(20) actually predict how much SF1's mean moves between independent n=20 batches, or does
it understate real batch-to-batch variability?

Motivation: v10's top-K confirmation re-evaluated the literal same parameter point as v9's original
candidate 0 (identical 11-dim values, p_u=0.01) with a different set of 20 fresh seeds -- SF1 came
back 0.648+/-0.141 here vs. 1.032+/-0.157 in v9's confirmation of that same point. A ~2.4-SEM swing
between two "properly powered" n=20 reads of the same point, if real, means the n=20 standard this
project has been treating as sufficient (docs/report/2026-07-21-conduit-experiment-design.md) may
still be understating the true noise floor, not just n=3-5.

Design (user, 2026-07-24, "for n=20 is enough, [check] with n=10"): run N_BATCHES=10 independent
n=20 batches (200 total seed-evaluations) of the same fixed point, sequential batches at
BATCH_SEEDS=20 concurrent JVMs each. Compare:
  - the empirical std of the 10 batch-means (real batch-to-batch spread), vs.
  - the theoretical prediction pooled_std/sqrt(20) (what a single batch's own std implies the
    spread *should* be, if seeds were behaving as a simple iid sample).
If the empirical spread is much larger than the theoretical prediction, that's direct evidence
n=20's reported SEM is not trustworthy at face value -- not just noisy in the ordinary sense, but
systematically underestimating the true sampling variability (e.g. because outcomes are bimodal
across seeds, not unimodal-iid).

Target point: v9/v10's round_loss=2.500 point (max_follow=46.53, p_u=0.01 among others) -- the
exact point that produced the 1.032 vs 0.648 discrepancy.

Usage: nohup python3 scripts/app_pol_baseline_sf1_batch_noise_check.py > logs/sf1_batch_noise_check_stdout.log 2>&1 &
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
spec = importlib.util.spec_from_file_location("v10", ROOT / "scripts" / "app_pol_baseline_bo_v10_unfollow_prob.py")
v10 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v10)

# Target point (v9/v10's round_loss=2.500 candidate; DIM_NAMES order):
# max_follow, follow_prob, alpha, hop, bc_dec, bc_recovery, stub, pp_relax_eta,
# feed_capacity, initial_pp, vocal_comfort_radius, p_u
POINT = [46.53220591787546, 0.07432462914149714, 0.5237539418107421, 2,
         0.6284092583220391, 0.016045063704140546, 0.8733667887168182, 0.030993030452104258,
         34, 0.4750688367178578, 0.16162078175438113, 0.01]

BASE_SEED = 1900000  # fresh, distinct from every prior range this session
N_BATCHES = 10
BATCH_SEEDS = 20

LOG_PATH = ROOT / "docs" / "report" / "sf1_batch_noise_check.csv"


def main():
    print(f"Target point: {dict(zip(v10.DIM_NAMES, POINT))}", flush=True)
    print(f"Running {N_BATCHES} independent batches of {BATCH_SEEDS} seeds "
          f"({N_BATCHES * BATCH_SEEDS} total seed-evaluations)...\n", flush=True)

    batch_means, batch_stds, all_ratios = [], [], []
    with open(LOG_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["batch", "seeds", "n_ok", "sf1_mean", "sf1_std"])

        next_seed = BASE_SEED
        for b in range(N_BATCHES):
            seeds = list(range(next_seed, next_seed + BATCH_SEEDS))
            next_seed += BATCH_SEEDS
            t0 = time.time()
            with concurrent.futures.ThreadPoolExecutor(max_workers=BATCH_SEEDS) as ex:
                results = list(ex.map(lambda s: v10.evaluate_seed(POINT, s), seeds))
            ok = [r for r in results if r is not None]
            ratios = [r[4] for r in ok]  # index 4 = ratio (SF1), per v10.read_metrics's return tuple
            mean, std = float(np.mean(ratios)), float(np.std(ratios))
            batch_means.append(mean)
            batch_stds.append(std)
            all_ratios.extend(ratios)
            writer.writerow([b, f"{seeds[0]}-{seeds[-1]}", len(ok), mean, std])
            f.flush()
            print(f"batch {b}: n={len(ok)}/{BATCH_SEEDS} seeds {seeds[0]}-{seeds[-1]}, "
                  f"SF1={mean:.4f}+/-{std:.4f}, done in {time.time()-t0:.0f}s", flush=True)

    batch_means = np.array(batch_means)
    all_ratios = np.array(all_ratios)
    pooled_mean, pooled_std = float(np.mean(all_ratios)), float(np.std(all_ratios))
    theoretical_batch_sem = pooled_std / np.sqrt(BATCH_SEEDS)
    empirical_batch_sem = float(np.std(batch_means))

    print(f"\n=== Results ===", flush=True)
    print(f"Pooled (n={len(all_ratios)}): SF1 = {pooled_mean:.4f} +/- {pooled_std:.4f} (std)", flush=True)
    print(f"10 batch-means: {[f'{m:.4f}' for m in batch_means]}", flush=True)
    print(f"Empirical std of the 10 batch-means:        {empirical_batch_sem:.4f}", flush=True)
    print(f"Theoretical prediction (pooled_std/sqrt(20)): {theoretical_batch_sem:.4f}", flush=True)
    ratio = empirical_batch_sem / theoretical_batch_sem if theoretical_batch_sem > 0 else float("nan")
    print(f"Ratio (empirical / theoretical): {ratio:.2f}x", flush=True)
    if ratio > 1.5:
        print("=> Batch-to-batch spread is substantially larger than a single n=20 batch's own "
              "std/sqrt(20) predicts -- n=20's reported SEM is NOT a reliable error bar for this "
              "point; the discrepancy between v9's and v10's confirmations of the same point was "
              "real sampling behavior, not a fluke.", flush=True)
    else:
        print("=> Batch-to-batch spread roughly matches the theoretical prediction -- the v9/v10 "
              "discrepancy (1.032 vs 0.648) was within normal n=20 sampling variability, just an "
              "unlucky pair of draws.", flush=True)
    print(f"\nFull log: {LOG_PATH}", flush=True)


if __name__ == "__main__":
    main()
