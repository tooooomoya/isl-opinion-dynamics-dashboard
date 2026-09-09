"""
2026-08-07 -- same formal p_u x vcr interaction test, run against the uniform-population +
uniform-hub-allocation (10 each, top-50) batch: results/2026-08-07_lmp_feedmech_uniform_hub_n30/.
Also reports Cohen's d per cell and facilitator/mediator regime averages for direct comparison against
the Gaussian (n=15) and uniform-population-only (n=30) numbers already reported this session.

Usage: python3 scripts/lmp_feedmech_uniform_hub_n30_anova.py
"""
import numpy as np
from scipy import stats

from lmp_feedmech_stage1 import CELLS, cell_name, extreme_post_total, pop_counts_nonhub_windowed, WINDOW

SEEDS = [9990000 + i for i in range(30)]
SUBDIR = "2026-08-07_lmp_feedmech_uniform_hubM15_n30"
PU_LEVELS = (0.05, 0.15)
VCR_LEVELS = (0.1, 0.15, 0.2, 0.3)


def per_seed_rate_contrast(pu, vcr):
    ctrl_subdir = f"{SUBDIR}/{cell_name(pu, vcr)}/control"
    msil_subdir = f"{SUBDIR}/{cell_name(pu, vcr)}/N_silent"
    ys = []
    for s in SEEDS:
        c_n = pop_counts_nonhub_windowed(s, ctrl_subdir)
        m_n = pop_counts_nonhub_windowed(s, msil_subdir)
        c_rate = extreme_post_total(s, ctrl_subdir) / (c_n[0] + c_n[4]) / WINDOW
        m_rate = extreme_post_total(s, msil_subdir) / (m_n[0] + m_n[4]) / WINDOW
        ys.append(m_rate - c_rate)
    return np.array(ys)


def two_way_anova_interaction(data):
    a_levels = sorted({k[0] for k in data})
    b_levels = sorted({k[1] for k in data})
    a, b = len(a_levels), len(b_levels)
    n = len(next(iter(data.values())))
    all_y = np.concatenate(list(data.values()))
    grand = all_y.mean()
    cell_mean = {k: v.mean() for k, v in data.items()}
    row_mean = {i: np.mean([cell_mean[(i, j)] for j in b_levels]) for i in a_levels}
    col_mean = {j: np.mean([cell_mean[(i, j)] for i in a_levels]) for j in b_levels}
    ss_ab = sum(n * (cell_mean[(i, j)] - row_mean[i] - col_mean[j] + grand) ** 2
                for i in a_levels for j in b_levels)
    ss_err = sum(np.sum((v - cell_mean[k]) ** 2) for k, v in data.items())
    df_ab = (a - 1) * (b - 1)
    df_err = a * b * n - a * b
    F = (ss_ab / df_ab) / (ss_err / df_err)
    p = stats.f.sf(F, df_ab, df_err)
    return F, p, df_ab, df_err


def permutation_test(data, n_perm=20000, seed=0):
    keys = list(data.keys())
    n = len(next(iter(data.values())))
    all_y = np.concatenate([data[k] for k in keys])
    a_levels = sorted({k[0] for k in keys})
    b_levels = sorted({k[1] for k in keys})

    def ss_ab_from_flat(flat):
        d = {k: flat[idx * n:(idx + 1) * n] for idx, k in enumerate(keys)}
        grand = flat.mean()
        cell_mean = {k: v.mean() for k, v in d.items()}
        row_mean = {i: np.mean([cell_mean[(i, j)] for j in b_levels]) for i in a_levels}
        col_mean = {j: np.mean([cell_mean[(i, j)] for i in a_levels]) for j in b_levels}
        return sum(n * (cell_mean[(i, j)] - row_mean[i] - col_mean[j] + grand) ** 2
                   for i in a_levels for j in b_levels)

    observed = ss_ab_from_flat(all_y)
    rng = np.random.default_rng(seed)
    count = sum(1 for _ in range(n_perm) if ss_ab_from_flat(rng.permutation(all_y)) >= observed)
    return count / n_perm


def main():
    data = {}
    print("Loading per-seed rate contrasts (uniform pop, M=15, n=30)...", flush=True)
    for pu in PU_LEVELS:
        for vcr in VCR_LEVELS:
            y = per_seed_rate_contrast(pu, vcr)
            data[(pu, vcr)] = y
            d = y.mean() / y.std(ddof=1)
            print(f"  p_u={pu} vcr={vcr}: mean={y.mean():+.6f}  sd={y.std(ddof=1):.6f}  d={d:+.3f}", flush=True)

    F, p, df_ab, df_err = two_way_anova_interaction(data)
    print(f"\n=== ANOVA: F({df_ab},{df_err})={F:.3f}  p={p:.5f} ===")
    p_perm = permutation_test(data)
    print(f"=== Permutation p={p_perm:.5f} ===")

    print("\n=== Facilitator/mediator regime averages (Cohen's d) ===")
    facil, med = [], []
    for pu in PU_LEVELS:
        for vcr in VCR_LEVELS:
            y = data[(pu, vcr)]
            d = y.mean() / y.std(ddof=1)
            if d < -0.3:
                facil.append(d)
            elif d > 0.3:
                med.append(d)
    if facil:
        print(f"  facilitator cells (d<-0.3): {['%.3f' % x for x in facil]}  mean|d|={np.mean(np.abs(facil)):.3f}")
    else:
        print("  facilitator: none")
    if med:
        print(f"  mediator cells (d>0.3):     {['%.3f' % x for x in med]}  mean d={np.mean(med):.3f}")
    else:
        print("  mediator: none")


if __name__ == "__main__":
    main()
