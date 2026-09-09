"""Noise-vs-signal check (2026-07-22): is round10/pt3's SF1=0.702 (v2 evaluations, 5 seeds) a real
feature of that parameter point, or a noise draw on a metric already documented as needing ~85+
seeds to resolve reliably? Re-evaluates the exact same point with 20 fresh seeds (distinct from the
original 5) and reports the pooled 25-seed estimate. See
docs/report/2026-07-21-conduit-experiment-design.md for why this matters: it's the evidentiary
basis for whether SF1 stays in the v3 loss (kept, reduced weight) or should be dropped entirely.
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from app_pol_baseline_bo_v3_wasserstein import evaluate_seed, bin7_wasserstein  # noqa: E402

POINT = [15.631387721316617, 0.028134201829316415, 0.7873888120010701, 2,
         0.6249164762112291, 0.14352178982417452, 0.39363813751969157, 0.9,
         0.11670833313274241, 27, 0.3636216606042009]

ORIGINAL_SEEDS_RATIO = [0.7024095627773199] * 0  # placeholder, real 5-seed values not individually
# logged (only mean/std in the CSV) -- pool via mean/std reconstruction instead, see main()
ORIGINAL_MEAN, ORIGINAL_STD, ORIGINAL_N = 0.7024095627773199, 0.18297263634218738, 5

FRESH_SEEDS = list(range(1030000, 1030020))  # 20 fresh seeds, distinct from every prior run


def main():
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(FRESH_SEEDS)) as ex:
        results = list(ex.map(lambda s: evaluate_seed(POINT, s), FRESH_SEEDS))

    ok = [m for m in results if m is not None]
    print(f"n={len(ok)}/{len(FRESH_SEEDS)} fresh seeds succeeded")
    ratios = np.array([m[4] for m in ok])
    ginis = np.array([m[0] for m in ok])
    print(f"fresh 20-seed SF1 ratio: mean={ratios.mean():.4f} std={ratios.std():.4f} "
          f"min={ratios.min():.4f} max={ratios.max():.4f}")
    print(f"individual values: {sorted(ratios.round(4).tolist())}")
    print(f"fresh gini: mean={ginis.mean():.4f} std={ginis.std():.4f}")

    # pooled mean/var across original 5 + fresh N (via sum-of-squares reconstruction)
    orig_sum = ORIGINAL_MEAN * ORIGINAL_N
    orig_sumsq = (ORIGINAL_STD ** 2 + ORIGINAL_MEAN ** 2) * ORIGINAL_N
    fresh_sum = ratios.sum()
    fresh_sumsq = (ratios ** 2).sum()
    pooled_n = ORIGINAL_N + len(ratios)
    pooled_mean = (orig_sum + fresh_sum) / pooled_n
    pooled_var = (orig_sumsq + fresh_sumsq) / pooled_n - pooled_mean ** 2
    print(f"\npooled {pooled_n}-seed SF1 ratio: mean={pooled_mean:.4f} std={pooled_var**0.5:.4f}")
    print(f"original 5-seed estimate was: mean={ORIGINAL_MEAN:.4f} std={ORIGINAL_STD:.4f}")
    print(f"target range: [1.19, 1.26]")


if __name__ == "__main__":
    main()
