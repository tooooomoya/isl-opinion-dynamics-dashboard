"""
2026-08-07 (review follow-up #2) -- extends lmp_feedmech_comfortvol_test.py (single predictor:
near-extreme comfort-gated volume diff, R2=0.259, but predicted the WRONG DIRECTION for the p_u-driven
vcr zero-crossing shift). Adds the competing/displaced term the report itself already named but never
formally regressed: OWN-CAMP comfort-gated volume (feedComfortClass0CountMean_0 /
feedComfortClass4CountMean_4 -- an extreme-camp reader's own class's content that also lands in their
feed and registers as comfortable, since same-class content is almost definitionally within vcr).
When feed_capacity is fixed, more near-extreme content filling freed-up slots can mechanically compete
with (displace) own-camp content reaching the same reader -- this was flagged in the 2026-08-06 report
entries ("net additional comfortable content (same-side pre-extreme + own-echo)") but never formally
tested against the outcome via regression, only eyeballed.

Tests, per-seed (n=120):
  Model A: outcome ~ near_extreme_comfort_vol_diff (baseline, already run, R2=0.259)
  Model B: outcome ~ near_extreme_comfort_vol_diff + own_camp_comfort_vol_diff (two predictors)
  Model C: outcome ~ total_comfort_vol_diff (their SUM as one term -- tests whether it's really just
           "total comfortable content, regardless of source" that matters)

For each: does it reproduce the empirically-observed vcr zero-crossing shift
(p_u=0.05 crosses ~0.14, p_u=0.15 crosses ~0.20 -- p_u=0.15 crosses LATER)?

Usage: python3 scripts/lmp_feedmech_comfortvol_test2.py
"""
import numpy as np

from lmp_feedmech_stage1 import SEEDS, SUBDIR, cell_name, trailing_window_means, extreme_post_total, \
    pop_counts_nonhub_windowed, WINDOW

PU_LEVELS = (0.05, 0.15)
VCR_LEVELS = (0.1, 0.15, 0.2, 0.3)

COLS = [
    "feedComfortClass1CountMean_0", "feedComfortClass3CountMean_4",   # near-extreme, comfort-gated
    "feedComfortClass0CountMean_0", "feedComfortClass4CountMean_4",   # own-camp, comfort-gated
    "feedModCountMean_0", "feedModCountMean_4",                        # moderate-authored (displaced)
]


def build_dataset():
    rows = []
    for pu in PU_LEVELS:
        for vcr in VCR_LEVELS:
            ctrl_subdir = f"{SUBDIR}/{cell_name(pu, vcr)}/control"
            msil_subdir = f"{SUBDIR}/{cell_name(pu, vcr)}/N_silent"
            for s in SEEDS:
                c = trailing_window_means(s, ctrl_subdir, COLS)
                m = trailing_window_means(s, msil_subdir, COLS)

                ne_diff = ((m["feedComfortClass1CountMean_0"] - c["feedComfortClass1CountMean_0"]) +
                           (m["feedComfortClass3CountMean_4"] - c["feedComfortClass3CountMean_4"])) / 2.0
                own_diff = ((m["feedComfortClass0CountMean_0"] - c["feedComfortClass0CountMean_0"]) +
                            (m["feedComfortClass4CountMean_4"] - c["feedComfortClass4CountMean_4"])) / 2.0
                mod_diff = ((m["feedModCountMean_0"] - c["feedModCountMean_0"]) +
                            (m["feedModCountMean_4"] - c["feedModCountMean_4"])) / 2.0

                c_n = pop_counts_nonhub_windowed(s, ctrl_subdir)
                m_n = pop_counts_nonhub_windowed(s, msil_subdir)
                c_rate = extreme_post_total(s, ctrl_subdir) / (c_n[0] + c_n[4]) / WINDOW
                m_rate = extreme_post_total(s, msil_subdir) / (m_n[0] + m_n[4]) / WINDOW
                outcome = m_rate - c_rate

                rows.append(dict(pu=pu, vcr=vcr, seed=s, ne_diff=ne_diff, own_diff=own_diff,
                                  mod_diff=mod_diff, outcome=outcome))
    return rows


def ols(X, y):
    coefs, res, rank, sv = np.linalg.lstsq(X, y, rcond=None)
    yhat = X @ coefs
    ss_res = np.sum((y - yhat) ** 2)
    ss_tot = np.sum((y - y.mean()) ** 2)
    r2 = 1 - ss_res / ss_tot
    return coefs, r2, yhat


def report_crossing(name, predict_fn, pu_arr, vcr_arr, out_arr):
    print(f"\n--- {name}: reproduces the vcr zero-crossing shift? ---")
    for p in PU_LEVELS:
        pred = [predict_fn(p, v) for v in VCR_LEVELS]
        actual = [out_arr[(pu_arr == p) & (vcr_arr == v)].mean() for v in VCR_LEVELS]
        print(f"  p_u={p}: predicted = " + "  ".join(f"{x:+.5f}" for x in pred))
        print(f"  p_u={p}: actual    = " + "  ".join(f"{x:+.5f}" for x in actual))


def main():
    print("Building per-seed dataset (120 obs)...", flush=True)
    rows = build_dataset()

    ne = np.array([r["ne_diff"] for r in rows])
    own = np.array([r["own_diff"] for r in rows])
    modd = np.array([r["mod_diff"] for r in rows])
    out = np.array([r["outcome"] for r in rows])
    pu = np.array([r["pu"] for r in rows])
    vcr = np.array([r["vcr"] for r in rows])

    print("\n=== Cell means: own-camp comfort-gated volume diff (N_silent-control) ===")
    for p in PU_LEVELS:
        line = [f"{own[(pu == p) & (vcr == v)].mean():+.4f}" for v in VCR_LEVELS]
        print(f"  p_u={p}: " + "  ".join(line))
    print("=== Cell means: moderate-authored volume diff (N_silent-control, should be ~ -control level) ===")
    for p in PU_LEVELS:
        line = [f"{modd[(pu == p) & (vcr == v)].mean():+.4f}" for v in VCR_LEVELS]
        print(f"  p_u={p}: " + "  ".join(line))

    print("\n=== Model A: outcome ~ ne_diff (baseline, already run) ===")
    XA = np.column_stack([np.ones_like(ne), ne])
    cA, r2A, _ = ols(XA, out)
    print(f"  intercept={cA[0]:+.5f}  b_ne={cA[1]:+.6f}  R2={r2A:.3f}")

    print("\n=== Model B: outcome ~ ne_diff + own_diff ===")
    XB = np.column_stack([np.ones_like(ne), ne, own])
    cB, r2B, _ = ols(XB, out)
    print(f"  intercept={cB[0]:+.5f}  b_ne={cB[1]:+.6f}  b_own={cB[2]:+.6f}  R2={r2B:.3f}")

    print("\n=== Model C: outcome ~ (ne_diff + own_diff) as ONE summed predictor ===")
    total = ne + own
    XC = np.column_stack([np.ones_like(total), total])
    cC, r2C, _ = ols(XC, out)
    print(f"  intercept={cC[0]:+.5f}  b_total={cC[1]:+.6f}  R2={r2C:.3f}")

    print("\n=== Model D: outcome ~ ne_diff + own_diff + mod_diff (add displaced-moderate term too) ===")
    XD = np.column_stack([np.ones_like(ne), ne, own, modd])
    cD, r2D, _ = ols(XD, out)
    print(f"  intercept={cD[0]:+.5f}  b_ne={cD[1]:+.6f}  b_own={cD[2]:+.6f}  b_mod={cD[3]:+.6f}  R2={r2D:.3f}")

    def predict_B(p, v):
        sel = (pu == p) & (vcr == v)
        return cB[0] + cB[1] * ne[sel].mean() + cB[2] * own[sel].mean()

    def predict_C(p, v):
        sel = (pu == p) & (vcr == v)
        return cC[0] + cC[1] * total[sel].mean()

    def predict_D(p, v):
        sel = (pu == p) & (vcr == v)
        return cD[0] + cD[1] * ne[sel].mean() + cD[2] * own[sel].mean() + cD[3] * modd[sel].mean()

    report_crossing("Model B (ne+own)", predict_B, pu, vcr, out)
    report_crossing("Model C (summed total comfortable volume)", predict_C, pu, vcr, out)
    report_crossing("Model D (ne+own+mod)", predict_D, pu, vcr, out)


if __name__ == "__main__":
    main()
