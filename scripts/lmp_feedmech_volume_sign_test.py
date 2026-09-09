"""
2026-08-07 (review follow-up) -- tests the user's proposed "volume(p_u) x sign(vcr)" multiplicative
decomposition of the two-level homophily-gate mechanism: does
    posting_rate_diff (N_silent - control) ~ near_extreme_volume_diff * comfort_ratio_diff
actually hold at the per-seed level, and critically: does it reproduce the empirically-observed
SHIFT in the vcr zero-crossing point between p_u=0.05 (~0.14) and p_u=0.15 (~0.20) found in the prior
review turn? A pure "p_u scales volume only, vcr alone determines sign" reading predicts the SAME
zero-crossing vcr for both p_u rows (scaling by a positive constant doesn't move a zero-crossing) --
this is a sharp, falsifiable prediction of the user's stated decomposition, distinct from a model
where volume and a competing p_u-scaled displacement term both matter.

Uses only already-completed data (results/2026-08-06_lmp_feedmech_stage1/), per-seed (not cell-mean)
granularity for statistical power: n=15 seeds x 8 cells = 120 observations.

Usage: python3 scripts/lmp_feedmech_volume_sign_test.py
"""
import numpy as np

from lmp_feedmech_stage1 import SEEDS, SUBDIR, cell_name, trailing_window_means, extreme_post_total, \
    pop_counts_nonhub_windowed, WINDOW
from lmp_feedmech_validate import cached_window_rows

PU_LEVELS = (0.05, 0.15)
VCR_LEVELS = (0.1, 0.15, 0.2, 0.3)


def per_seed_ratio_val(seed, subdir, reader_cls, author_cls):
    sel = cached_window_rows(seed, subdir)
    tot = sum(float(r[f"feedAuthorClass{author_cls}CountMean_{reader_cls}"]) for r in sel)
    com = sum(float(r[f"feedComfortClass{author_cls}CountMean_{reader_cls}"]) for r in sel)
    return com / tot if tot > 0 else float("nan")


def build_dataset():
    rows = []
    for pu in PU_LEVELS:
        for vcr in VCR_LEVELS:
            ctrl_subdir = f"{SUBDIR}/{cell_name(pu, vcr)}/control"
            msil_subdir = f"{SUBDIR}/{cell_name(pu, vcr)}/N_silent"
            for s in SEEDS:
                # near-extreme volume reaching bins 0/4 (same-side pre-extreme -> extreme), averaged
                # over the two symmetric reader/author pairs (reader=0/author=1, reader=4/author=3)
                c0 = trailing_window_means(s, ctrl_subdir, ["feedAuthorClass1CountMean_0", "feedAuthorClass3CountMean_4"])
                m0 = trailing_window_means(s, msil_subdir, ["feedAuthorClass1CountMean_0", "feedAuthorClass3CountMean_4"])
                vol_diff = ((m0["feedAuthorClass1CountMean_0"] - c0["feedAuthorClass1CountMean_0"]) +
                            (m0["feedAuthorClass3CountMean_4"] - c0["feedAuthorClass3CountMean_4"])) / 2.0

                c_r0 = per_seed_ratio_val(s, ctrl_subdir, 0, 1)
                c_r4 = per_seed_ratio_val(s, ctrl_subdir, 4, 3)
                m_r0 = per_seed_ratio_val(s, msil_subdir, 0, 1)
                m_r4 = per_seed_ratio_val(s, msil_subdir, 4, 3)
                ratio_diff = np.nanmean([m_r0 - c_r0, m_r4 - c_r4])

                c_n = pop_counts_nonhub_windowed(s, ctrl_subdir)
                m_n = pop_counts_nonhub_windowed(s, msil_subdir)
                c_rate = extreme_post_total(s, ctrl_subdir) / (c_n[0] + c_n[4]) / WINDOW
                m_rate = extreme_post_total(s, msil_subdir) / (m_n[0] + m_n[4]) / WINDOW
                outcome = m_rate - c_rate

                rows.append(dict(pu=pu, vcr=vcr, seed=s, vol_diff=vol_diff, ratio_diff=ratio_diff, outcome=outcome))
    return rows


def ols(X, y):
    """X: (n,k) design matrix (include intercept column yourself), y: (n,). Returns coefs, r2."""
    coefs, res, rank, sv = np.linalg.lstsq(X, y, rcond=None)
    yhat = X @ coefs
    ss_res = np.sum((y - yhat) ** 2)
    ss_tot = np.sum((y - y.mean()) ** 2)
    r2 = 1 - ss_res / ss_tot
    return coefs, r2, yhat


def main():
    print("Building per-seed dataset (120 obs)...", flush=True)
    rows = build_dataset()

    vol = np.array([r["vol_diff"] for r in rows])
    rat = np.array([r["ratio_diff"] for r in rows])
    out = np.array([r["outcome"] for r in rows])
    pu = np.array([r["pu"] for r in rows])
    vcr = np.array([r["vcr"] for r in rows])

    print("\n=== Cell-mean check (sanity vs user-quoted volume numbers) ===")
    for p in PU_LEVELS:
        line = []
        for v in VCR_LEVELS:
            sel = (pu == p) & (vcr == v)
            line.append(f"{vol[sel].mean():+.3f}")
        print(f"  p_u={p}: " + "  ".join(line))

    print("\n=== Model 1: outcome ~ vol_diff + ratio_diff (additive, no interaction) ===")
    X1 = np.column_stack([np.ones_like(vol), vol, rat])
    c1, r2_1, _ = ols(X1, out)
    print(f"  intercept={c1[0]:+.5f}  b_vol={c1[1]:+.5f}  b_ratio={c1[2]:+.5f}  R2={r2_1:.3f}")

    print("\n=== Model 2: outcome ~ vol_diff * ratio_diff (WITH interaction -- the user's literal")
    print("  'volume x sign' claim implies the interaction term should dominate) ===")
    X2 = np.column_stack([np.ones_like(vol), vol, rat, vol * rat])
    c2, r2_2, _ = ols(X2, out)
    print(f"  intercept={c2[0]:+.5f}  b_vol={c2[1]:+.5f}  b_ratio={c2[2]:+.5f}  b_vol:ratio={c2[3]:+.5f}  R2={r2_2:.3f}")

    print("\n=== Does Model 1 (additive) reproduce the observed vcr zero-crossing SHIFT between p_u rows? ===")
    print("  (a pure 'p_u=scale-of-volume-only, vcr=sign-only' story predicts NO shift -- crossing")
    print("   point should be identical for both p_u rows under that story)")
    for p in PU_LEVELS:
        sel = pu == p
        # fit outcome ~ vcr within this p_u row using the additive model's actual vol/ratio values
        # (empirical, not assumed constant) to find where predicted outcome crosses zero
        vcr_grid = np.array(VCR_LEVELS)
        pred = []
        for v in vcr_grid:
            m = (pu == p) & (vcr == v)
            pred.append(c1[0] + c1[1] * vol[m].mean() + c1[2] * rat[m].mean())
        pred = np.array(pred)
        print(f"  p_u={p}: model-predicted outcome by vcr = " + "  ".join(f"{x:+.5f}" for x in pred))
        # empirical actual outcome for comparison
        actual = [out[(pu == p) & (vcr == v)].mean() for v in vcr_grid]
        print(f"  p_u={p}: ACTUAL outcome by vcr           = " + "  ".join(f"{x:+.5f}" for x in actual))


if __name__ == "__main__":
    main()
