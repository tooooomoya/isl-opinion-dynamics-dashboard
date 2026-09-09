"""
Resume app_pol_baseline_bo_calibration.py after the background process was killed mid-round-2
(2026-07-21 -- harness session teardown, not a script bug; see docs/report entry). Rounds 0-1 (12
points, 60 seed-runs) are intact in app_pol_baseline_bo_evaluations.csv -- warm-start the skopt
Optimizer from those instead of discarding ~30 min of real compute, then continue for the
remaining rounds (appending to the same CSV, not overwriting).

Usage: python3 scripts/app_pol_baseline_bo_resume.py
"""
import csv
import time

from skopt import Optimizer

import app_pol_baseline_bo_calibration as base

REMAINING_ROUNDS = 6  # rounds 2..7 -> total 8 rounds matching the original design


def load_prior_points():
    points, losses = [], []
    with open(base.LOG_PATH, newline="") as f:
        for row in csv.DictReader(f):
            pt = [
                int(float(row["hop"])), float(row["bc_dec"]), float(row["bc_recovery"]),
                float(row["bc_init"]), float(row["comfort_pp"]),
            ]
            points.append(pt)
            losses.append(float(row["point_loss"]))
    return points, losses


def main():
    prior_points, prior_losses = load_prior_points()
    print(f"Warm-starting from {len(prior_points)} already-evaluated points "
          f"(best so far: loss={min(prior_losses):.3f})", flush=True)

    opt = Optimizer(base.SPACE, base_estimator="GP", acq_func="EI", random_state=41)
    opt.tell(prior_points, prior_losses)

    rows = list(zip(prior_losses, prior_points))
    next_round = 2  # rounds 0-1 already logged

    with open(base.LOG_PATH, "a", newline="") as f:
        writer = csv.writer(f)
        for rnd in range(next_round, next_round + REMAINING_ROUNDS):
            t0 = time.time()
            points = opt.ask(n_points=base.N_POINTS_PER_ROUND)
            point_seeds = [
                [base.BASE_SEED + (rnd * base.N_POINTS_PER_ROUND + i) * base.SEEDS_PER_POINT + j
                 for j in range(base.SEEDS_PER_POINT)]
                for i in range(len(points))
            ]
            print(f"[round {rnd}] evaluating {len(points)} points x {base.SEEDS_PER_POINT} seeds "
                  f"({len(points) * base.SEEDS_PER_POINT} concurrent JVMs, "
                  f"seeds {point_seeds[0][0]}-{point_seeds[-1][-1]})...", flush=True)

            point_results = base.evaluate_round(points, point_seeds)
            losses = [r[0] for r in point_results]
            opt.tell(points, losses)

            for i, (pt, seeds, (point_loss, agg)) in enumerate(zip(points, point_seeds, point_results)):
                writer.writerow([rnd, i, ";".join(map(str, seeds))] + list(pt) + [
                    point_loss, agg["gini_mean"], agg["gini_std"],
                    agg["assort_mean"], agg["assort_std"], agg["q_sign_repost_mean"], agg["q_sign_repost_std"],
                    agg["ratio_mean"], agg["ratio_std"],
                ])
                rows.append((point_loss, pt))
            f.flush()
            best = min(r[0] for r in rows)
            print(f"[round {rnd}] done in {time.time()-t0:.0f}s, best point_loss so far = {best:.3f}", flush=True)

    rows.sort(key=lambda r: r[0])
    print("\nTop 5 points by point_loss (across resumed + original rounds):")
    for loss, pt in rows[:5]:
        print(f"  loss={loss:.3f}  {dict(zip(base.DIM_NAMES, pt))}")
    print(f"\nFull log: {base.LOG_PATH}")

    best_loss, best_point = rows[0]
    base.run_confirmation(best_point)


if __name__ == "__main__":
    main()
