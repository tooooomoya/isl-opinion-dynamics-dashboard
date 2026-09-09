"""
2026-08-14 -- handoff item 9c (docs/report/2026-08-07-cna2026-paper-writing-handoff.md, section 9c):
direct structural-mediation test, replacing/supplementing the comfort-volume regression
(lmp_feedmech_comfortvol_test2.py), which only tests whether FEED-CONTENT-VOLUME differences predict
the outcome -- silent on *why* that volume changes, and does not reproduce the p_u-driven crossing-
point shift (predicts ~vcr 0.18 for both p_u rows; actual crossing ~0.14 at p_u=0.05, ~0.20 at
p_u=0.15). This regresses the same per-seed outcome directly on the structural metrics computed in
lmp_feedmech_structural_9b.py (E<->NE follow-edge density, NE betweenness -- 3 variants), testing the
hypothesized p_u -> structure -> outcome chain in one step instead of the prior two-hop, partially-
indirect (p_u -> content volume -> outcome, structure's role only inferred by elimination) chain.

Design: both PREDICTOR and RESPONSE are N_silent-minus-control differences, paired per seed (same seed
reused across arms), across the full p_u x vcr grid (n=15 seeds x 2 p_u x 3 vcr = 90 observations) --
mirrors the paper's headline metric, which is itself defined as an N_silent-minus-control contrast.

Requires lmp_feedmech_structural_9b.py's simulation batch to have completed (reads the same GEXF
snapshots, no new runs).

Usage: python3 scripts/lmp_feedmech_structural_9c.py
"""
import numpy as np

from lmp_feedmech_stage1 import SEEDS, WINDOW, extreme_post_total, pop_counts_nonhub_windowed
from lmp_feedmech_structural_9b import SUBDIR, CELLS, cell_name, per_seed_metrics

STRUCT_METRICS = ("density", "bc_dir", "bc_undir", "bc_recip")


def build_dataset():
    rows = []
    for pu, vcr in CELLS:
        ctrl_subdir = f"{SUBDIR}/{cell_name(pu, vcr)}/control"
        msil_subdir = f"{SUBDIR}/{cell_name(pu, vcr)}/N_silent"
        for s in SEEDS:
            c_struct = per_seed_metrics(s, ctrl_subdir)
            m_struct = per_seed_metrics(s, msil_subdir)

            c_n = pop_counts_nonhub_windowed(s, ctrl_subdir)
            m_n = pop_counts_nonhub_windowed(s, msil_subdir)
            c_rate = extreme_post_total(s, ctrl_subdir) / (c_n[0] + c_n[4]) / WINDOW
            m_rate = extreme_post_total(s, msil_subdir) / (m_n[0] + m_n[4]) / WINDOW
            outcome = m_rate - c_rate

            row = dict(pu=pu, vcr=vcr, seed=s, outcome=outcome)
            for metric in STRUCT_METRICS:
                row[f"d_{metric}"] = m_struct[metric] - c_struct[metric]
            rows.append(row)
    return rows


def ols(X, y):
    coefs, res, rank, sv = np.linalg.lstsq(X, y, rcond=None)
    yhat = X @ coefs
    ss_res = np.sum((y - yhat) ** 2)
    ss_tot = np.sum((y - y.mean()) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    return coefs, r2, yhat


def report_crossing(name, predict_fn, pu_arr, vcr_arr, out_arr, vcr_levels):
    print(f"  reproduces the vcr zero-crossing shift?")
    for p in (0.05, 0.15):
        pred = [predict_fn(p, v, pu_arr, vcr_arr) for v in vcr_levels]
        actual = [out_arr[(pu_arr == p) & (vcr_arr == v)].mean() for v in vcr_levels]
        print(f"    p_u={p}: predicted = " + "  ".join(f"{x:+.5f}" for x in pred))
        print(f"    p_u={p}: actual    = " + "  ".join(f"{x:+.5f}" for x in actual))


def main():
    vcr_levels = sorted({v for _, v in CELLS})
    print(f"Building per-seed dataset (n={len(CELLS) * len(SEEDS)}, "
          f"grid=p_u{{0.05,0.15}} x vcr{vcr_levels})...", flush=True)
    rows = build_dataset()

    out = np.array([r["outcome"] for r in rows])
    pu = np.array([r["pu"] for r in rows])
    vcr = np.array([r["vcr"] for r in rows])
    d = {m: np.array([r[f"d_{m}"] for r in rows]) for m in STRUCT_METRICS}

    print("\n=== Cell means: outcome (N_silent - control extreme-camp posting rate) ===")
    for p in (0.05, 0.15):
        line = [f"{out[(pu == p) & (vcr == v)].mean():+.5f}" for v in vcr_levels]
        print(f"  p_u={p}: " + "  ".join(line))

    for metric in STRUCT_METRICS:
        print(f"\n=== Cell means: d_{metric} (N_silent - control) ===")
        for p in (0.05, 0.15):
            line = [f"{d[metric][(pu == p) & (vcr == v)].mean():+.6f}" for v in vcr_levels]
            print(f"  p_u={p}: " + "  ".join(line))

    print("\n=== Model: outcome ~ d_density (single predictor) ===")
    X = np.column_stack([np.ones_like(out), d["density"]])
    c, r2, _ = ols(X, out)
    print(f"  intercept={c[0]:+.6f}  b_density={c[1]:+.4f}  R2={r2:.3f}")

    for bc_metric in ("bc_dir", "bc_undir", "bc_recip"):
        print(f"\n=== Model: outcome ~ d_density + d_{bc_metric} ===")
        X = np.column_stack([np.ones_like(out), d["density"], d[bc_metric]])
        c, r2, _ = ols(X, out)
        print(f"  intercept={c[0]:+.6f}  b_density={c[1]:+.4f}  b_{bc_metric}={c[2]:+.4f}  R2={r2:.3f}")

        def predict(p, v, pu_arr, vcr_arr, c=c, bc_metric=bc_metric):
            sel = (pu_arr == p) & (vcr_arr == v)
            return c[0] + c[1] * d["density"][sel].mean() + c[2] * d[bc_metric][sel].mean()

        report_crossing(f"density+{bc_metric}", predict, pu, vcr, out, vcr_levels)

    print("\n=== Model: outcome ~ d_density + d_bc_dir + d_bc_undir + d_bc_recip (kitchen sink) ===")
    X = np.column_stack([np.ones_like(out), d["density"], d["bc_dir"], d["bc_undir"], d["bc_recip"]])
    c, r2, _ = ols(X, out)
    print(f"  intercept={c[0]:+.6f}  b_density={c[1]:+.4f}  b_bc_dir={c[2]:+.4f}  "
          f"b_bc_undir={c[3]:+.4f}  b_bc_recip={c[4]:+.4f}  R2={r2:.3f}")


if __name__ == "__main__":
    main()
