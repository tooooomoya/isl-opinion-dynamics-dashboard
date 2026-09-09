"""
v9 top-K re-selection (2026-07-23): fixes a selection-pipeline gap found after v9's first topk
stage completed, without re-running the expensive 96-point BO search.

Bug: `compute_round_loss`'s bc_extremity_corr term is a one-sided ceiling penalty --
`max(0, (bc_corr - CEILING)/SCALE)^2` -- zero once bc_corr clears the -0.1 ceiling, with NO further
credit for going more negative. round4/pt5 (SF1=1.187 at n=5, bc_corr=-0.472 at n=5 -- the best
combined SF1+bc_corr point seen across the whole run) scored round_loss=3.79, worse than all 5
points that made the original top-5 (whose round_losses were 2.500-2.909), because its gini/bin7
terms were mediocre and its exceptional bc_corr bought zero extra credit past the ceiling. It never
reached the n=20 confirmation stage. The original top-5's winner (candidate 4, selected by
SF1-closeness) had bc_corr=-0.029+/-0.070 at n=20 -- fails the ceiling with real margin, not just
bad luck -- so the round-loss ranking that fed the selection stage was itself the problem, not the
final SF1-closest pick.

Fix here: re-score all 96 already-evaluated v9 points (docs/report/app_pol_baseline_v9_bo_evaluations.csv)
with bc_corr_credit = (bc_corr_mean - CEILING)/SCALE (linear, unbounded, no max(0,...) clamp) in
place of the squared one-sided term -- same scale/normalization, but now more-negative bc_corr keeps
earning credit instead of saturating at the ceiling. gini/Q/assort/bin7 terms unchanged. Re-rank,
take the new top-5, and run the same properly-powered n=20 SF1-selection stage v9 already used
(reusing launch/evaluate_seed/aggregate from the v9 module) -- no new simulation of the 96 round
points needed, only 5*20=100 fresh seed-evaluations for the confirmation itself.

Usage: nohup python3 scripts/app_pol_baseline_v9_reselect_topk.py > logs/app_pol_baseline_v9_reselect_stdout.log 2>&1 &
"""
import csv
import importlib.util
import sys
import time
import concurrent.futures
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

spec = importlib.util.spec_from_file_location("v9", ROOT / "scripts" / "app_pol_baseline_bo_v9_graded_postprob.py")
v9 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v9)

RESELECT_SEED_OFFSET = 700000  # distinct from v9's own topk offset (500000) -- avoids seed collision
TOP_K = 5
SELECT_SEEDS = v9.SELECT_SEEDS  # 20

SELECT_LOG_PATH = ROOT / "docs" / "report" / "app_pol_baseline_v9_reselect_topk.csv"


def rescored_loss(row):
    """Same as v9.compute_round_loss but with an unbounded linear bc_corr credit instead of the
    one-sided squared ceiling penalty -- see module docstring."""
    gini_t = v9.term(float(row["gini_mean"]), float(row["gini_std"]), v9.GINI_TARGET, v9.GINI_SCALE)
    q_t = v9.term(float(row["q_sign_repost_mean"]), float(row["q_sign_repost_std"]), v9.Q_TARGET, v9.Q_SCALE)
    a_mean = float(row["assort_mean"])
    assort_t = max(0.0, (v9.ASSORT_FLOOR - a_mean) / v9.ASSORT_SCALE) ** 2
    bin7_t = v9.term(float(row["bin7_w1_mean"]), float(row["bin7_w1_std"]), 0.0, v9.BIN7_W1_SCALE)
    bc_corr_mean = float(row["bc_extremity_corr_mean"])
    bc_corr_credit = (bc_corr_mean - v9.BC_EXTREMITY_CORR_CEILING) / v9.BC_EXTREMITY_CORR_SCALE
    return v9.W_GINI * gini_t + v9.W_Q * q_t + assort_t + v9.W_BIN7 * bin7_t + bc_corr_credit


def main():
    with open(v9.LOG_PATH, newline="") as f:
        rows = list(csv.DictReader(f))
    print(f"Loaded {len(rows)} already-evaluated v9 points from {v9.LOG_PATH}", flush=True)

    scored = []
    for r in rows:
        pt = [float(r[name]) if name not in ("hop", "feed_capacity") else int(float(r[name]))
              for name in v9.DIM_NAMES]
        scored.append((rescored_loss(r), r["round"], r["point_idx"], pt,
                        float(r["ratio_mean"]), float(r["bc_extremity_corr_mean"])))
    scored.sort(key=lambda x: x[0])

    print("\nNew top-10 by re-scored selection loss (unbounded bc_corr credit):", flush=True)
    for s, rnd, pidx, pt, sf1, bc in scored[:10]:
        print(f"  round={rnd} pt={pidx} score={s:.3f}  SF1(n~3-5)={sf1:.4f}  bc_corr(n~3-5)={bc:.4f}", flush=True)

    old_top5_keys = set()
    old_rows_sorted = sorted(rows, key=lambda r: float(r["point_loss"]))[:TOP_K]
    for r in old_rows_sorted:
        old_top5_keys.add((r["round"], r["point_idx"]))

    picked = scored[:TOP_K]
    new_top5_keys = {(rnd, pidx) for _, rnd, pidx, _, _, _ in picked}
    print(f"\nOverlap with original top-5: {len(old_top5_keys & new_top5_keys)}/5 candidates unchanged", flush=True)
    print(f"Original top-5 (round,pt): {sorted(old_top5_keys)}", flush=True)
    print(f"New top-5 (round,pt):      {sorted(new_top5_keys)}", flush=True)

    # Bonus 6th candidate: best raw SF1 (n~3-5) among points that ALREADY clear the bc_corr
    # ceiling -- catches the direct "is there an in-target point with genuine bc asymmetry"
    # question that the structural rescoring above doesn't target (it optimizes gini/Q/assort/
    # bin7 + bc_corr credit, not SF1 proximity, by design -- SF1 stays out of any n<20 ranking to
    # avoid the winner's-curse pattern seen repeatedly this project). Added only if not already
    # in the rescored top-5.
    ceiling_clearers = [x for x in scored if x[5] <= v9.BC_EXTREMITY_CORR_CEILING]
    ceiling_clearers.sort(key=lambda x: abs(x[4] - v9.RATIO_TARGET))
    bonus = None
    for s, rnd, pidx, pt, sf1, bc in ceiling_clearers:
        if (rnd, pidx) not in new_top5_keys:
            bonus = (s, rnd, pidx, pt, sf1, bc)
            break
    if bonus:
        print(f"\nBonus 6th candidate (best raw SF1 among bc_corr-ceiling-clearers, not already "
              f"in top-5): round={bonus[1]} pt={bonus[2]} SF1={bonus[4]:.4f} bc_corr={bonus[5]:.4f}", flush=True)
        picked = picked + [bonus]

    candidates = [(s, pt) for s, rnd, pidx, pt, sf1, bc in picked]

    print(f"\n=== Re-evaluating new top-{TOP_K} with {SELECT_SEEDS} seeds each "
          f"(out_of_bc_repost_prob={v9.OOB_TREATMENT}) ===", flush=True)

    with open(SELECT_LOG_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["candidate_rank", "selection_score"] + v9.DIM_NAMES +
                         ["n_ok", "gini_mean", "gini_std", "assort_mean", "assort_std",
                          "q_sign_repost_mean", "q_sign_repost_std", "ratio_mean", "ratio_std",
                          "bin7_w1_mean", "bin7_w1_std", "bc_extremity_corr_mean", "bc_extremity_corr_std"])

        results = []
        for k, (score, pt) in enumerate(candidates):
            seeds = [v9.BASE_SEED + RESELECT_SEED_OFFSET + k * SELECT_SEEDS + j for j in range(SELECT_SEEDS)]
            print(f"  candidate {k} (selection_score={score:.3f}): evaluating {SELECT_SEEDS} seeds "
                  f"{seeds[0]}-{seeds[-1]}...", flush=True)
            t0 = time.time()
            with concurrent.futures.ThreadPoolExecutor(max_workers=SELECT_SEEDS) as ex:
                metrics = list(ex.map(lambda s: v9.evaluate_seed(pt, s), seeds))
            ok = [m for m in metrics if m is not None]
            agg = v9.aggregate(ok)
            writer.writerow([k, score] + list(pt) + [
                len(ok), agg["gini_mean"], agg["gini_std"], agg["assort_mean"], agg["assort_std"],
                agg["q_sign_repost_mean"], agg["q_sign_repost_std"], agg["ratio_mean"], agg["ratio_std"],
                agg["bin7_w1_mean"], agg["bin7_w1_std"],
                agg["bc_extremity_corr_mean"], agg["bc_extremity_corr_std"],
            ])
            f.flush()
            sf1_gap = abs(agg["ratio_mean"] - v9.RATIO_TARGET) if agg["ratio_mean"] is not None else float("inf")
            in_range = agg["ratio_mean"] is not None and 1.19 <= agg["ratio_mean"] <= 1.26
            clears_bc = agg["bc_extremity_corr_mean"] is not None and agg["bc_extremity_corr_mean"] <= v9.BC_EXTREMITY_CORR_CEILING
            print(f"  candidate {k} done in {time.time()-t0:.0f}s: n={len(ok)}/{SELECT_SEEDS}, "
                  f"SF1={agg['ratio_mean']:.4f}+/-{agg['ratio_std']:.4f} (in_range={in_range}), "
                  f"bc_corr={agg['bc_extremity_corr_mean']:.4f}+/-{agg['bc_extremity_corr_std']:.4f} "
                  f"(clears_ceiling={clears_bc}), gap-to-target={sf1_gap:.4f}", flush=True)
            results.append((score, pt, agg, ok, sf1_gap, in_range, clears_bc))

    print("\n=== All 5 re-selected candidates, both-criteria check ===", flush=True)
    both = [r for r in results if r[5] and r[6]]
    for score, pt, agg, ok, gap, in_range, clears_bc in sorted(results, key=lambda r: r[4]):
        flag = "*** BOTH SF1-in-range AND bc_corr-clears-ceiling ***" if (in_range and clears_bc) else ""
        print(f"  score={score:.3f} SF1={agg['ratio_mean']:.4f}+/-{agg['ratio_std']:.4f} "
              f"bc_corr={agg['bc_extremity_corr_mean']:.4f}+/-{agg['bc_extremity_corr_std']:.4f} "
              f"gini={agg['gini_mean']:.4f} Q={agg['q_sign_repost_mean']:.4f} "
              f"assort={agg['assort_mean']:.4f} bin7={agg['bin7_w1_mean']:.4f} {flag}", flush=True)

    if both:
        winner = min(both, key=lambda r: r[4])
        print(f"\n=== WINNER (both criteria met, closest SF1 among them) ===", flush=True)
        print(f"params: {dict(zip(v9.DIM_NAMES, winner[1]))}", flush=True)
    else:
        print("\nNo candidate met both criteria simultaneously even after re-selection.", flush=True)

    print(f"\nFull log: {SELECT_LOG_PATH}", flush=True)


if __name__ == "__main__":
    main()
