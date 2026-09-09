"""
2026-08-07 (review follow-up, refinement of lmp_feedmech_volume_sign_test.py) -- the first regression
(outcome ~ vol_diff + ratio_diff, R2=0.013) used raw volume and the RATIO as two separate additive
terms, which is not actually a fair test of "does comfortable volume delivered predict the outcome" --
that quantity is ratio*volume, and the model already computes it natively per step as
feedComfortClass{author}CountMean_{reader} (StepStats.feedClassComfortCountSum javadoc), so using it
directly (rather than reconstructing an approximation from two separate diff terms) is a strictly
better-specified test of the user's mechanism claim.

Tests: outcome (N_silent-control posting-rate diff) ~ comfort_gated_volume_diff (N_silent-control diff
of feedComfortClass3CountMean_4 / feedComfortClass1CountMean_0, i.e. same-side near-extreme content
that BOTH reached the feed AND fell inside the reader's vcr window) -- single predictor, per-seed,
n=120.

Usage: python3 scripts/lmp_feedmech_comfortvol_test.py
"""
import numpy as np

from lmp_feedmech_stage1 import SEEDS, SUBDIR, cell_name, trailing_window_means, extreme_post_total, \
    pop_counts_nonhub_windowed, WINDOW

PU_LEVELS = (0.05, 0.15)
VCR_LEVELS = (0.1, 0.15, 0.2, 0.3)

COLS = ["feedComfortClass1CountMean_0", "feedComfortClass3CountMean_4",
        "feedAuthorClass1CountMean_0", "feedAuthorClass3CountMean_4"]


def build_dataset():
    rows = []
    for pu in PU_LEVELS:
        for vcr in VCR_LEVELS:
            ctrl_subdir = f"{SUBDIR}/{cell_name(pu, vcr)}/control"
            msil_subdir = f"{SUBDIR}/{cell_name(pu, vcr)}/N_silent"
            for s in SEEDS:
                c = trailing_window_means(s, ctrl_subdir, COLS)
                m = trailing_window_means(s, msil_subdir, COLS)
                comfort_vol_diff = ((m["feedComfortClass1CountMean_0"] - c["feedComfortClass1CountMean_0"]) +
                                     (m["feedComfortClass3CountMean_4"] - c["feedComfortClass3CountMean_4"])) / 2.0
                raw_vol_diff = ((m["feedAuthorClass1CountMean_0"] - c["feedAuthorClass1CountMean_0"]) +
                                (m["feedAuthorClass3CountMean_4"] - c["feedAuthorClass3CountMean_4"])) / 2.0

                c_n = pop_counts_nonhub_windowed(s, ctrl_subdir)
                m_n = pop_counts_nonhub_windowed(s, msil_subdir)
                c_rate = extreme_post_total(s, ctrl_subdir) / (c_n[0] + c_n[4]) / WINDOW
                m_rate = extreme_post_total(s, msil_subdir) / (m_n[0] + m_n[4]) / WINDOW
                outcome = m_rate - c_rate

                rows.append(dict(pu=pu, vcr=vcr, seed=s, comfort_vol_diff=comfort_vol_diff,
                                  raw_vol_diff=raw_vol_diff, outcome=outcome))
    return rows


def ols(X, y):
    coefs, res, rank, sv = np.linalg.lstsq(X, y, rcond=None)
    yhat = X @ coefs
    ss_res = np.sum((y - yhat) ** 2)
    ss_tot = np.sum((y - y.mean()) ** 2)
    r2 = 1 - ss_res / ss_tot
    return coefs, r2, yhat


def main():
    print("Building per-seed dataset (120 obs)...", flush=True)
    rows = build_dataset()

    cv = np.array([r["comfort_vol_diff"] for r in rows])
    rv = np.array([r["raw_vol_diff"] for r in rows])
    out = np.array([r["outcome"] for r in rows])
    pu = np.array([r["pu"] for r in rows])
    vcr = np.array([r["vcr"] for r in rows])

    print("\n=== Cell means: comfort-gated near-extreme volume diff (N_silent-control) ===")
    for p in PU_LEVELS:
        line = [f"{cv[(pu == p) & (vcr == v)].mean():+.4f}" for v in VCR_LEVELS]
        print(f"  p_u={p}: " + "  ".join(line))

    print("\n=== Model: outcome ~ comfort_vol_diff (single predictor, per-seed n=120) ===")
    X = np.column_stack([np.ones_like(cv), cv])
    c, r2, _ = ols(X, out)
    print(f"  intercept={c[0]:+.5f}  slope={c[1]:+.6f}  R2={r2:.3f}")
    corr = np.corrcoef(cv, out)[0, 1]
    print(f"  Pearson r={corr:+.3f}")

    print("\n=== Does this reproduce the vcr zero-crossing SHIFT between p_u rows? ===")
    for p in PU_LEVELS:
        pred = [c[0] + c[1] * cv[(pu == p) & (vcr == v)].mean() for v in VCR_LEVELS]
        actual = [out[(pu == p) & (vcr == v)].mean() for v in VCR_LEVELS]
        print(f"  p_u={p}: predicted = " + "  ".join(f"{x:+.5f}" for x in pred))
        print(f"  p_u={p}: actual    = " + "  ".join(f"{x:+.5f}" for x in actual))


if __name__ == "__main__":
    main()
