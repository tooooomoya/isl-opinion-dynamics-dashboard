"""
2026-08-15 -- decisive mechanism test, consolidating the 2026-08-15 diagnostic chain
(lmp_feedmech_followee_composition.py -> _feedfill_check.py -> _bc_gate_check.py).

TWO METHODOLOGICAL CORRECTIONS THIS SCRIPT MAKES (both matter for the numbers):

(1) COMFORT RATE MUST BE A MEAN OF PER-AGENT RATIOS, NOT A RATIO OF SUMS. An earlier pass in
    lmp_feedmech_feedfill_check.py aggregated comfort as (sum of comfortable feed items) / (sum of
    total feed items) across agents, which weights agents by their feed size and gave a uniformly
    NEGATIVE N_silent-minus-control gap (-0.05 to -0.14) at every cell. The quantity that actually
    drives behavior is per-agent: Agent.java:421 computes comfortPostRate = comfortPostNum/postNum
    for each agent, and Agent.java:445 feeds THAT into targetPostProb. Analysis.java:563-565
    aggregates it correctly as a mean over agents (cRateMean_i). The per-agent version reverses sign
    across the grid where the feed-size-weighted version does not -- this is the same ratio-of-means
    vs paired-difference hazard the handoff already flagged for 9b's p_u contrast.

(2) The "0.6 bounded-confidence gate" framing floated in _bc_gate_check.py's docstring is WRONG and is
    abandoned here. That script measured bc_mean = 0.27-0.35 among extreme-camp agents (bc_floor=0.2),
    with only 0.1%-5.6% of them above 0.6. Extreme-to-near-extreme opinion distance is NOT fixed at
    0.6: class 4 spans [0.6, 1.0] and class 3 spans [0.2, 0.6], so the actual distance between an
    extreme reader and a near-extreme author ranges from ~0 (both near the shared 0.6 boundary) to
    1.4. bc therefore acts as a graded window over that distance distribution, not a sharp gate at a
    single threshold.

THE MECHANISM UNDER TEST (restated correctly):
    Moderate-hub content (pinned 0.0) is out-of-bc for essentially every extreme-camp agent, so under
    CONTROL it (a) fires unfollow+block at rate p_u, purging the M hubs themselves, and (b) depresses
    the in-tolerance feed fraction that bc relaxes toward, holding bc NARROW. Since follow() recruits
    only from in-bc feed content, a narrower bc means fewer near-extreme authors ever qualify as
    follow candidates -- so the extreme camp accumulates fewer NE ties and stays insulated from NE
    content. Silencing the moderate hub removes that suppression: bc widens, NE ties accumulate, NE
    content flows into extreme feeds.
    The SIGN of the resulting posting-rate effect then depends on vcr, because the extra NE content
    enters the comfort ratio's DENOMINATOR always but its NUMERATOR only once vcr is wide enough to
    make that content "comfortable":
        low vcr  -> extra NE content is not comfortable -> comfort rate falls -> less posting
        high vcr -> extra NE content is comfortable     -> comfort rate rises -> more posting
    And p_u sets HOW MUCH extra NE content arrives (roughly 3x more at p_u=0.15 than 0.05), so a
    larger denominator penalty must be overcome at high p_u -- shifting the vcr crossing point RIGHT.
    That is a mechanism for the p_u x vcr crossing shift, which the comfort-VOLUME regression
    (lmp_feedmech_comfortvol_test2.py, R2=0.560) explicitly failed to reproduce.

PREDICTIONS TESTED HERE:
    P1. d_cRate (per-agent comfort rate, N_silent - control) reproduces the crossing shift: crosses
        zero at a LOWER vcr for p_u=0.05 than for p_u=0.15.
    P2. outcome ~ d_cRate has substantially higher R2 than the 9c structural regression (0.064-0.168)
        and than the comfort-volume regression (0.560).
    P3. d_cRate decomposes into a positive own-camp/comfortable-NE term and a negative
        NE-denominator-inflation term whose relative size is set by vcr.

Usage: python3 scripts/lmp_feedmech_mechanism_test.py
"""
import numpy as np

from lmp_feedmech_stage1 import (
    SEEDS, WINDOW, trailing_window_means, extreme_post_total, pop_counts_nonhub_windowed,
)
from lmp_feedmech_structural_9b import SUBDIR, CELLS, cell_name, per_seed_metrics

ARMS = ("control", "N_silent")
VCRS = (0.1, 0.15, 0.2)
PUS = (0.05, 0.15)

COLS = ["cRateMean_0", "cRateMean_4"]
for r in (0, 4):
    COLS += [f"feedAuthorClass{a}CountMean_{r}" for a in range(5)]
    COLS += [f"feedComfortClass{a}CountMean_{r}" for a in range(5)]


def sym_pair(row, kind, side):
    """Camp-relative, sign-symmetrized feed tally. For a class-0 reader the own camp is author class
    0 and the same-side near-extreme is class 1; mirrored to 4 and 3 for a class-4 reader."""
    a0, a4 = {"own": (0, 4), "ne": (1, 3), "mid": (2, 2)}[side]
    return (row[f"feed{kind}Class{a0}CountMean_0"] + row[f"feed{kind}Class{a4}CountMean_4"]) / 2.0


def build():
    rows = []
    for pu, vcr in CELLS:
        c_sub = f"{SUBDIR}/{cell_name(pu, vcr)}/control"
        m_sub = f"{SUBDIR}/{cell_name(pu, vcr)}/N_silent"
        for s in SEEDS:
            c = trailing_window_means(s, c_sub, COLS)
            m = trailing_window_means(s, m_sub, COLS)

            c_n = pop_counts_nonhub_windowed(s, c_sub)
            m_n = pop_counts_nonhub_windowed(s, m_sub)
            c_rate = extreme_post_total(s, c_sub) / (c_n[0] + c_n[4]) / WINDOW
            m_rate = extreme_post_total(s, m_sub) / (m_n[0] + m_n[4]) / WINDOW

            # per-agent comfort rate, extreme camp = mean of the two mirrored reader bins
            c_crate = (c["cRateMean_0"] + c["cRateMean_4"]) / 2.0
            m_crate = (m["cRateMean_0"] + m["cRateMean_4"]) / 2.0

            struct_c = per_seed_metrics(s, c_sub)
            struct_m = per_seed_metrics(s, m_sub)

            rows.append(dict(
                pu=pu, vcr=vcr, seed=s,
                outcome=m_rate - c_rate,
                d_crate=m_crate - c_crate,
                d_ne_total=sym_pair(m, "Author", "ne") - sym_pair(c, "Author", "ne"),
                d_ne_comfort=sym_pair(m, "Comfort", "ne") - sym_pair(c, "Comfort", "ne"),
                d_own_total=sym_pair(m, "Author", "own") - sym_pair(c, "Author", "own"),
                d_own_comfort=sym_pair(m, "Comfort", "own") - sym_pair(c, "Comfort", "own"),
                d_density=struct_m["density"] - struct_c["density"],
                d_bc_undir=struct_m["bc_undir"] - struct_c["bc_undir"],
            ))
    return rows


def ols(X, y):
    coefs, *_ = np.linalg.lstsq(X, y, rcond=None)
    yhat = X @ coefs
    ss_res = float(np.sum((y - yhat) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    return coefs, (1 - ss_res / ss_tot if ss_tot > 0 else float("nan"))


def zero_crossing(vcrs, vals):
    """Linear interpolation of where a per-vcr series crosses zero; None if it never changes sign."""
    for i in range(len(vals) - 1):
        a, b = vals[i], vals[i + 1]
        if a == 0:
            return vcrs[i]
        if a * b < 0:
            return vcrs[i] + (vcrs[i + 1] - vcrs[i]) * (-a) / (b - a)
    return None


def grid(rows, key):
    return {(p, v): np.mean([r[key] for r in rows if r["pu"] == p and r["vcr"] == v])
            for p in PUS for v in VCRS}


def main():
    print(f"Building per-seed dataset (n={len(CELLS) * len(SEEDS)})...", flush=True)
    rows = build()
    arr = {k: np.array([r[k] for r in rows]) for k in rows[0] if k != "seed"}
    pu, vcr, out = arr["pu"], arr["vcr"], arr["outcome"]

    print("\n" + "=" * 78)
    print("P1: does per-agent comfort rate reproduce the p_u-dependent vcr crossing shift?")
    print("=" * 78)
    g_out, g_cr = grid(rows, "outcome"), grid(rows, "d_crate")
    for label, g in (("outcome (posting-rate diff)", g_out), ("d_cRate (per-agent comfort)", g_cr)):
        print(f"\n  {label}:")
        for p in PUS:
            vals = [g[(p, v)] for v in VCRS]
            x = zero_crossing(VCRS, vals)
            xs = f"{x:.3f}" if x is not None else "no sign change"
            print(f"    p_u={p}: " + "  ".join(f"{y:+.5f}" for y in vals) + f"   -> crosses at vcr={xs}")

    print("\n  For reference, the comfort-VOLUME regression (comfortvol_test2.py) predicted a crossing")
    print("  near vcr=0.18 for BOTH p_u rows -- i.e. no shift at all -- which is why it was judged")
    print("  evidence against volume-mediation being the whole story (handoff section 9, item 3).")

    print("\n" + "=" * 78)
    print("P2: regression of outcome on the candidate mediators (per-seed, n=90)")
    print("=" * 78)
    ones = np.ones_like(out)
    models = [
        ("outcome ~ d_cRate", ["d_crate"]),
        ("outcome ~ d_ne_comfort", ["d_ne_comfort"]),
        ("outcome ~ d_ne_total", ["d_ne_total"]),
        ("outcome ~ d_ne_comfort + d_ne_total", ["d_ne_comfort", "d_ne_total"]),
        ("outcome ~ d_own_comfort + d_ne_comfort", ["d_own_comfort", "d_ne_comfort"]),
        ("outcome ~ d_density + d_bc_undir  [9c structural, for comparison]",
         ["d_density", "d_bc_undir"]),
        ("outcome ~ d_cRate + d_density + d_bc_undir", ["d_crate", "d_density", "d_bc_undir"]),
    ]
    for name, keys in models:
        X = np.column_stack([ones] + [arr[k] for k in keys])
        c, r2 = ols(X, out)
        terms = "  ".join(f"b_{k}={c[i + 1]:+.4f}" for i, k in enumerate(keys))
        print(f"  {name}")
        print(f"      intercept={c[0]:+.5f}  {terms}   R2={r2:.3f}")

    print("\n" + "=" * 78)
    print("P3: decomposition -- where does the comfort-rate change come from?")
    print("=" * 78)
    print("  Extra near-extreme content reaching extreme readers (N_silent - control), and how much")
    print("  of it registers as within-vcr 'comfortable'. The non-comfortable remainder inflates the")
    print("  comfort ratio's denominator only, which is the sign-flipping term.\n")
    g_net, g_nec = grid(rows, "d_ne_total"), grid(rows, "d_ne_comfort")
    g_owc = grid(rows, "d_own_comfort")
    print(f"  {'':12s}" + "".join(f"vcr={v:<12}" for v in VCRS))
    for p in PUS:
        print(f"  p_u={p}")
        print(f"    NE extra total    " + "".join(f"{g_net[(p, v)]:<+16.4f}" for v in VCRS))
        print(f"    NE extra comfort  " + "".join(f"{g_nec[(p, v)]:<+16.4f}" for v in VCRS))
        share = [g_nec[(p, v)] / g_net[(p, v)] if g_net[(p, v)] else float('nan') for v in VCRS]
        print(f"    -> comfortable %  " + "".join(f"{x:<16.1%}" for x in share))
        print(f"    own-camp comfort  " + "".join(f"{g_owc[(p, v)]:<+16.4f}" for v in VCRS))
    print("\n  Prediction: 'comfortable %' rises steeply with vcr, and at any given vcr the p_u=0.15")
    print("  row carries a LARGER absolute NE influx -- so its denominator penalty needs a wider vcr")
    print("  to be outweighed, pushing its crossing point to the right.")


if __name__ == "__main__":
    main()
