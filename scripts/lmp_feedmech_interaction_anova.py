"""
2026-08-06 (review follow-up) -- formal statistical test of the p_u x vcr INTERACTION claim
(docs/report/2026-08-02-delayed-moderate-conduit-pilot.md: "the p_u=0.15 row behaves qualitatively
differently from the other rows" -- so far only visually/qualitatively argued, never given a formal
interaction-term significance test, per the HANDOFF section's own known-weaknesses list).

Uses ONLY already-completed data (results/2026-08-06_lmp_feedmech_stage1/, still on disk, not yet
cleaned up) -- no new simulation runs. Available design: p_u in {0.05, 0.15} (2 levels) x vcr in
{0.1, 0.15, 0.2, 0.3} (4 levels), n=15 seeds (8900000-8900014), control + N_silent arms. This is a
subset of the original 4-level-p_u grid (whose raw per-seed data was already cleaned up per project
convention once its summary was written into the report) but still a genuine 2x4 balanced factorial,
sufficient to test exactly the flagship claim quoted above (does the vcr-shape of the N_silent-vs-
control effect differ between p_u=0.05 and p_u=0.15?).

Outcome variable: per-seed posting-rate contrast y = N_silent_rate - control_rate, using the
"trailing-window-mean-n" (NEW, time-matched) convention established in lmp_feedmech_stage1.py's
2026-08-06 denominator-fix entries as the fair per-capita comparison (not the OLD stale-snapshot-n,
not the fixed-control-n variant -- this uses each arm's own time-matched population, the most neutral
choice for a per-seed contrast feeding an ANOVA).

Two tests on the same data, since the earlier data (rare-event-dominated bc_inc metric, per this
project's own prior finding) motivates not trusting parametric normality assumptions alone:
1. Standard balanced 2-way ANOVA F-test on the interaction term (a=2, b=4, n=15 replicates/cell).
2. Label-permutation test (shuffle which of the 8 cell-labels each of the 120 y-values belongs to,
   recompute the interaction sum-of-squares each time) -- distribution-free cross-check of (1).

Usage: python3 scripts/lmp_feedmech_interaction_anova.py
"""
import numpy as np
from scipy import stats

from lmp_feedmech_stage1 import (
    SEEDS, SUBDIR, cell_name, extreme_post_total, pop_counts_nonhub_windowed, WINDOW,
)

PU_LEVELS = (0.05, 0.15)
VCR_LEVELS = (0.1, 0.15, 0.2, 0.3)


def per_seed_rate_contrast(pu, vcr):
    """Returns array y[seed] = N_silent_rate - control_rate (trailing-window-mean-n convention)."""
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
    """data: dict[(i,j)] -> array of n replicates, balanced (same n every cell).
    Returns (F, p, df_ab, df_err, SS_ab, SS_err)."""
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
            interaction_term = cell_mean[(i, j)] - row_mean[i] - col_mean[j] + grand
            ss_ab += n * interaction_term ** 2

    ss_err = sum(np.sum((v - cell_mean[k]) ** 2) for k, v in data.items())

    df_ab = (a - 1) * (b - 1)
    df_err = a * b * n - a * b

    ms_ab = ss_ab / df_ab
    ms_err = ss_err / df_err
    F = ms_ab / ms_err
    p = stats.f.sf(F, df_ab, df_err)
    return F, p, df_ab, df_err, ss_ab, ss_err


def permutation_test(data, n_perm=20000, seed=0):
    """Distribution-free cross-check: shuffle which (i,j) cell label each of the a*b*n values
    belongs to (breaking any real p_u/vcr structure), recompute SS_ab each time, and see how often
    the shuffled SS_ab meets or exceeds the observed one."""
    keys = list(data.keys())
    n = len(next(iter(data.values())))
    all_y = np.concatenate([data[k] for k in keys])
    a_levels = sorted({k[0] for k in keys})
    b_levels = sorted({k[1] for k in keys})
    a, b = len(a_levels), len(b_levels)

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
    count = 0
    for _ in range(n_perm):
        perm = rng.permutation(all_y)
        if ss_ab_from_flat(perm) >= observed:
            count += 1
    return observed, count / n_perm


def main():
    data = {}
    print("Loading per-seed rate contrasts (N_silent - control) for each of the 8 cells...", flush=True)
    for pu in PU_LEVELS:
        for vcr in VCR_LEVELS:
            y = per_seed_rate_contrast(pu, vcr)
            data[(pu, vcr)] = y
            print(f"  p_u={pu} vcr={vcr}: mean={y.mean():+.6f}  sd={y.std(ddof=1):.6f}  n={len(y)}", flush=True)

    print("\n=== Formal 2-way ANOVA: p_u x vcr interaction on the N_silent-control posting-rate contrast ===")
    F, p, df_ab, df_err, ss_ab, ss_err = two_way_anova_interaction(data)
    print(f"  F({df_ab},{df_err}) = {F:.3f}   p = {p:.5f}   SS_interaction={ss_ab:.3e}  SS_error={ss_err:.3e}")

    print("\n=== Permutation cross-check (distribution-free, 20000 shuffles) ===")
    observed, p_perm = permutation_test(data)
    print(f"  observed SS_interaction = {observed:.3e}   permutation p = {p_perm:.5f}")

    print("\n=== Cell means (for reference against the report's already-published d/t values) ===")
    for pu in PU_LEVELS:
        row = [f"{data[(pu, vcr)].mean():+.6f}" for vcr in VCR_LEVELS]
        print(f"  p_u={pu}: " + "  ".join(row))


if __name__ == "__main__":
    main()
