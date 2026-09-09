"""Retro-check (2026-07-22): recompute point_loss for all 72 already-evaluated v2 points using
(a) Wasserstein-1 bin7 term instead of sum-of-squared-per-bin-z-scores, (b) SF1 ratio removed from
the loss (validation-only, per the circularity finding logged in
docs/report/2026-07-21-conduit-experiment-design.md). Uses the real per-seed post_bin7.csv files
still on disk from the v2 run -- no re-simulation. Sanity check before relaunching v3.
"""
import csv
from pathlib import Path

import numpy as np
from scipy.stats import wasserstein_distance

ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = ROOT / "docs" / "report" / "app_pol_baseline_v2_bo_evaluations.csv"

EMPIRICAL_POST_BIN_PROPORTIONS = np.array(
    [4328.725, 2682.863, 1503.682, 2135.798, 691.065, 1156.761, 3742.547]
)
EMPIRICAL_POST_BIN_PROPORTIONS /= EMPIRICAL_POST_BIN_PROPORTIONS.sum()
BIN_CENTERS = np.arange(7)  # equal-width bins, unit spacing is enough for a relative distance

GINI_TARGET, GINI_SCALE = 0.8, 0.05
Q_TARGET, Q_SCALE = 0.48, 0.05
ASSORT_FLOOR, ASSORT_SCALE = 0.6, 0.15
W1_SCALE = 0.3  # calibrated below from observed magnitudes

W_GINI, W_Q = 0.5, 0.7


def find_run_dir(seed):
    matches = sorted(ROOT.glob(f"results/run_{seed}_*"))
    return matches[-1] if matches else None


def wasserstein_for_seed(seed):
    d = find_run_dir(seed)
    if d is None:
        return None
    p = d / "metrics" / "post_bin7.csv"
    if not p.exists():
        return None
    with open(p, newline="") as f:
        counts = np.array([int(r["postCount"]) for r in csv.DictReader(f)], dtype=float)
    if counts.sum() <= 0:
        return None
    model_props = counts / counts.sum()
    return float(wasserstein_distance(BIN_CENTERS, BIN_CENTERS, u_weights=model_props, v_weights=EMPIRICAL_POST_BIN_PROPORTIONS))


def main():
    rows = list(csv.DictReader(open(LOG_PATH)))
    all_w1 = []
    results = []
    for row in rows:
        seeds = row["seeds"].split(";")
        w1s = [w for w in (wasserstein_for_seed(s) for s in seeds) if w is not None]
        if len(w1s) < 2:
            continue
        all_w1.extend(w1s)
        results.append((row, float(np.mean(w1s)), float(np.std(w1s))))

    print(f"Wasserstein-1 distance across {len(all_w1)} seed-level evaluations:")
    print(f"  mean={np.mean(all_w1):.4f} std={np.std(all_w1):.4f} min={np.min(all_w1):.4f} max={np.max(all_w1):.4f}")
    print(f"  (W1_SCALE={W1_SCALE} chosen so (mean/W1_SCALE)^2 lands near O(1-10), comparable to gini/Q terms)")
    print()

    def term(mean, std, target, scale):
        return ((mean - target) / scale) ** 2 + (std / scale) ** 2

    scored = []
    for row, w1_mean, w1_std in results:
        gini_t = term(float(row["gini_mean"]), float(row["gini_std"]), GINI_TARGET, GINI_SCALE)
        q_t = term(float(row["q_sign_repost_mean"]), float(row["q_sign_repost_std"]), Q_TARGET, Q_SCALE)
        a_mean = float(row["assort_mean"])
        assort_t = max(0.0, (ASSORT_FLOOR - a_mean) / ASSORT_SCALE) ** 2
        w1_t = (w1_mean / W1_SCALE) ** 2
        new_loss = W_GINI * gini_t + W_Q * q_t + assort_t + w1_t
        scored.append({
            "round": row["round"], "point_idx": row["point_idx"],
            "old_loss": float(row["point_loss"]), "new_loss": new_loss,
            "gini_t": gini_t, "q_t": q_t, "assort_t": assort_t, "w1_t": w1_t,
            "ratio_mean": float(row["ratio_mean"]),
            "old_bin7": float(row["bin7_loss_mean"]), "w1_mean": w1_mean,
        })

    scored.sort(key=lambda r: r["new_loss"])
    print("Top 5 points by NEW loss (Wasserstein bin7, SF1 removed, gini*0.5, Q*0.7):")
    for r in scored[:5]:
        print(f"  round={r['round']} pt={r['point_idx']}  new_loss={r['new_loss']:.3f}  "
              f"(gini_t={r['gini_t']:.2f} q_t={r['q_t']:.2f} assort_t={r['assort_t']:.2f} w1_t={r['w1_t']:.2f})  "
              f"old_loss={r['old_loss']:.3f}  ratio(SF1, monitor-only)={r['ratio_mean']:.3f}  "
              f"old_bin7={r['old_bin7']:.2f} w1={r['w1_mean']:.3f}")

    print()
    old_best = min(scored, key=lambda r: r["old_loss"])
    print(f"Old-loss winner (round={old_best['round']} pt={old_best['point_idx']}) under NEW loss: "
          f"new_loss={old_best['new_loss']:.3f} (rank "
          f"{sorted(scored, key=lambda r: r['new_loss']).index(old_best) + 1} of {len(scored)})")


if __name__ == "__main__":
    main()
