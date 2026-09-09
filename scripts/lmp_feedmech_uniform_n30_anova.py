"""
2026-08-07 -- same formal p_u x vcr interaction test as lmp_feedmech_interaction_anova.py
(2-way ANOVA + label-permutation cross-check on the per-seed N_silent-control posting-rate contrast),
run against the uniform-opinion-init, n=30 robustness batch
(results/2026-08-07_lmp_feedmech_uniform_n30/) instead of the original Gaussian-init, n=15 data.
Reference (Gaussian, n=15, from lmp_feedmech_interaction_anova.py): F(3,112)=4.70, p=0.0039 (parametric);
permutation p=0.032.

Usage: python3 scripts/lmp_feedmech_uniform_n30_anova.py
"""
import numpy as np
from scipy import stats

from lmp_feedmech_stage1 import CELLS, cell_name, extreme_post_total, pop_counts_nonhub_windowed, WINDOW

SEEDS = [9990000 + i for i in range(30)]
SUBDIR = "2026-08-07_lmp_feedmech_uniform_n30"
PU_LEVELS = (0.05, 0.15)
VCR_LEVELS = (0.1, 0.15, 0.2, 0.3)


def per_seed_rate_contrast(pu, vcr):
    ctrl_subdir = f"{SUBDIR}/{cell_name(pu, vcr)}/control"
    msil_subdir = f"{SUBDIR}/{cell_name(pu, vcr)}/N_silent"
    ys = []
    for s in SEEDS:
        c_n = pop_counts_nonhub_windowed(s, ctrl_subdir)
        m_n = pop_counts_nonhub_windowed(s, msil_subdir)
        c_n_tot = c_n[0] + c_n[4]
        m_n_tot = m_n[0] + m_n[4]
        c_posts = extreme_post_total(s, ctrl_subdir)
        m_posts = extreme_post_total(s, msil_subdir)
        c_rate = c_posts / c_n_tot / WINDOW
        m_rate = m_posts / m_n_tot / WINDOW
        ys.append(m_rate - c_rate)
    return np.array(ys)


def two_way_anova_interaction(data):
    a_levels = sorted({k[0] for k in data})
    b_levels = sorted({k[1] for k in data})
    a, b = len(a_levels), len(b_levels)
    n = len(next(iter(data.values())))
    assert all(len(v) == n for v in data.values()), "unbalanced design"

    all_y = np.concatenate(list(data.values()))
    grand = all_y.mean()
    cell_mean = {k: v.mean() for k, v in data.items()}
    row_mean = {i: np.mean([cell_mean[(i, j)] for j in b_levels]) for i in a_levels}
    col_mean = {j: np.mean([cell_mean[(i, j)] for i in a_levels]) for j in b_levels}

    ss_ab = 0.0
    for i in a_levels:
        for j in b_levels:
            t = cell_mean[(i, j)] - row_mean[i] - col_mean[j] + grand
            ss_ab += n * t ** 2
    ss_err = sum(np.sum((v - cell_mean[k]) ** 2) for k, v in data.items())

    df_ab = (a - 1) * (b - 1)
    df_err = a * b * n - a * b
    ms_ab = ss_ab / df_ab
    ms_err = ss_err / df_err
    F = ms_ab / ms_err
    p = stats.f.sf(F, df_ab, df_err)
    return F, p, df_ab, df_err, ss_ab, ss_err


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
        ss = 0.0
        for i in a_levels:
            for j in b_levels:
                t = cell_mean[(i, j)] - row_mean[i] - col_mean[j] + grand
                ss += n * t ** 2
        return ss

    observed = ss_ab_from_flat(np.concatenate([data[k] for k in keys]))
    rng = np.random.default_rng(seed)
    count = sum(1 for _ in range(n_perm) if ss_ab_from_flat(rng.permutation(all_y)) >= observed)
    return observed, count / n_perm


def main():
    data = {}
    print("Loading per-seed rate contrasts (uniform init, n=30)...", flush=True)
    for pu in PU_LEVELS:
        for vcr in VCR_LEVELS:
            y = per_seed_rate_contrast(pu, vcr)
            data[(pu, vcr)] = y
            print(f"  p_u={pu} vcr={vcr}: mean={y.mean():+.6f}  sd={y.std(ddof=1):.6f}  n={len(y)}", flush=True)

    print("\n=== Formal 2-way ANOVA: p_u x vcr interaction (uniform init, n=30) ===")
    F, p, df_ab, df_err, ss_ab, ss_err = two_way_anova_interaction(data)
    print(f"  F({df_ab},{df_err}) = {F:.3f}   p = {p:.5f}")

    print("\n=== Permutation cross-check (20000 shuffles) ===")
    observed, p_perm = permutation_test(data)
    print(f"  permutation p = {p_perm:.5f}")

    print("\n=== Cell means (compare against Gaussian n=15 baseline) ===")
    for pu in PU_LEVELS:
        row = [f"{data[(pu, vcr)].mean():+.6f}" for vcr in VCR_LEVELS]
        print(f"  p_u={pu}: " + "  ".join(row))


if __name__ == "__main__":
    main()
