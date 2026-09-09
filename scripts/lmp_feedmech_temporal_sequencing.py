"""
2026-08-07 (review follow-up) -- tests the user's proposed refinement of the two-level homophily-gate
hypothesis: "structural change (p_u-driven follow-graph reorganization) happens FIRST and reaches a
quasi-stable state, and only THEN does the perceptual/psychological layer (vcr-driven comfort
registration) become the operative factor." Nothing in this project's prior analysis actually tested
this -- Check 1/2 in lmp_feedmech_validate.py both only ever looked at the FINAL checkpoint (step
40000) or the trailing 2000-step window ending there, never a time series.

Uses ONLY already-completed data, no new simulation:
- Follow-graph GEXF snapshots exist every 5000 steps (GEXF/lambda_0.0/step_{step}.gexf) in
  results/2026-08-06_lmp_feedmech_stage1_gexf/ -- gives a connectivity-gap trajectory.
- results.csv has every step logged in results/2026-08-06_lmp_feedmech_stage1/ -- gives a
  posting-rate-gap and comfort-ratio-gap trajectory via the same trailing-window convention already
  established, just evaluated at each of the 9 checkpoints (0,5000,...,40000) instead of only 40000.

For each of the 8 (p_u, vcr) cells: prints connectivity-gap(checkpoint) and comfort-ratio-gap
(checkpoint) side by side, and reports the checkpoint at which each first reaches 80% of its OWN
final (step=40000) magnitude -- a simple, symmetric way to compare which layer "gets there first"
without assuming a particular functional form.

Usage: python3 scripts/lmp_feedmech_temporal_sequencing.py
"""
import numpy as np

from lmp_feedmech_stage1 import SEEDS, SUBDIR, cell_name, cell_name as _cn
from lmp_feedmech_stage1_gexf import cross_class_density, SUBDIR as GEXF_SUBDIR
from lmp_feedmech_validate import per_seed_ratio, cached_window_rows

PU_LEVELS = (0.05, 0.15)
VCR_LEVELS = (0.1, 0.15, 0.2, 0.3)
CHECKPOINTS = [5000, 10000, 15000, 20000, 25000, 30000, 35000, 40000]


def connectivity_gap_at(pu, vcr, checkpoint):
    ctrl_subdir = f"{GEXF_SUBDIR}/{cell_name(pu, vcr)}/control"
    msil_subdir = f"{GEXF_SUBDIR}/{cell_name(pu, vcr)}/N_silent"
    sides = []
    for ca, cb in ((0, 1), (4, 3)):
        c = np.array([cross_class_density(s, ctrl_subdir, ca, cb, checkpoint)[0] for s in SEEDS])
        m = np.array([cross_class_density(s, msil_subdir, ca, cb, checkpoint)[0] for s in SEEDS])
        sides.append(np.nanmean(m - c))
    return float(np.mean(sides))


def comfort_ratio_gap_at(pu, vcr, checkpoint):
    ctrl_subdir = f"{SUBDIR}/{cell_name(pu, vcr)}/control"
    msil_subdir = f"{SUBDIR}/{cell_name(pu, vcr)}/N_silent"
    diffs = []
    for reader_cls, author_cls in ((0, 1), (4, 3)):
        c = np.array([_ratio_at(s, ctrl_subdir, reader_cls, author_cls, checkpoint) for s in SEEDS])
        m = np.array([_ratio_at(s, msil_subdir, reader_cls, author_cls, checkpoint) for s in SEEDS])
        valid = ~(np.isnan(c) | np.isnan(m))
        if valid.sum() >= 2:
            diffs.append(np.mean(m[valid] - c[valid]))
    return float(np.mean(diffs)) if diffs else float("nan")


def _ratio_at(seed, subdir, reader_cls, author_cls, checkpoint):
    sel = cached_window_rows(seed, subdir, checkpoint=checkpoint)
    tot = sum(float(r[f"feedAuthorClass{author_cls}CountMean_{reader_cls}"]) for r in sel)
    com = sum(float(r[f"feedComfortClass{author_cls}CountMean_{reader_cls}"]) for r in sel)
    return com / tot if tot > 0 else float("nan")


def frac_of_final(series, checkpoints):
    """Returns the first checkpoint at which |value| >= 0.8 * |final value|, or None."""
    final = series[-1]
    if final == 0 or np.isnan(final):
        return None
    thresh = 0.8 * abs(final)
    for cp, v in zip(checkpoints, series):
        if not np.isnan(v) and abs(v) >= thresh and np.sign(v) == np.sign(final):
            return cp
    return None


def main():
    for pu in PU_LEVELS:
        for vcr in VCR_LEVELS:
            print(f"\n=== p_u={pu} vcr={vcr} ===", flush=True)
            conn = [connectivity_gap_at(pu, vcr, cp) for cp in CHECKPOINTS]
            comf = [comfort_ratio_gap_at(pu, vcr, cp) for cp in CHECKPOINTS]
            print("  step:      " + "  ".join(f"{cp:>7d}" for cp in CHECKPOINTS))
            print("  conn_gap:  " + "  ".join(f"{v:+.5f}" for v in conn))
            print("  comf_gap:  " + "  ".join(f"{v:+.5f}" for v in comf))
            t_conn = frac_of_final(conn, CHECKPOINTS)
            t_comf = frac_of_final(comf, CHECKPOINTS)
            print(f"  connectivity gap reaches 80% of final magnitude at step: {t_conn}")
            print(f"  comfort-ratio gap reaches 80% of final magnitude at step: {t_comf}")


if __name__ == "__main__":
    main()
