"""
2026-08-07 (review follow-up) -- tests whether p_u ALONE (independent of M's silenced/active status)
structurally separates near-extreme (PE) from far-extreme (E) into heterophilic communities -- i.e.
does the ABSOLUTE E<->PE follow-graph connectivity density under CONTROL (M active, not just the
N_silent-minus-control GAP already checked) fall as p_u rises? If so, "p_u makes them heterophilic
regardless of vcr" would be a defensible reading. If control-arm density is roughly flat across p_u,
that reading is not supported -- p_u would only matter via how much it amplifies the M-silencing GAP,
not as a standalone separator of the two camps.

Also reports N_silent's absolute density for the same comparison (does p_u still fall even once M is
removed, i.e. is p_u's separating force independent of M's presence too?).

Uses only already-completed data (results/2026-08-06_lmp_feedmech_stage1_gexf/), no new simulation.

Usage: python3 scripts/lmp_feedmech_pu_absolute_connectivity.py
"""
import numpy as np

from lmp_feedmech_stage1 import SEEDS, cell_name
from lmp_feedmech_stage1_gexf import cross_class_density, SUBDIR as GEXF_SUBDIR

PU_LEVELS = (0.05, 0.15)
VCR_LEVELS = (0.1, 0.15, 0.2, 0.3)


def absolute_density(pu, vcr, arm, class_a, class_b):
    subdir = f"{GEXF_SUBDIR}/{cell_name(pu, vcr)}/{arm}"
    vals = np.array([cross_class_density(s, subdir, class_a, class_b, 40000)[0] for s in SEEDS])
    return np.nanmean(vals)


def main():
    for arm in ("control", "N_silent"):
        print(f"\n=== Arm: {arm} -- absolute E<->PE directed follow-density, by p_u and vcr ===")
        for side_name, ca, cb in (("E- -> PE-", 0, 1), ("E+ -> PE+", 4, 3)):
            print(f"  side={side_name}")
            for pu in PU_LEVELS:
                row = [absolute_density(pu, vcr, arm, ca, cb) for vcr in VCR_LEVELS]
                print(f"    p_u={pu}: " + "  ".join(f"{v:.6f}" for v in row) + f"   mean={np.mean(row):.6f}")

    print("\n=== Summary: does control-arm density fall as p_u rises (supports 'p_u alone separates')? ===")
    for side_name, ca, cb in (("E- -> PE-", 0, 1), ("E+ -> PE+", 4, 3)):
        d05 = np.mean([absolute_density(0.05, v, "control", ca, cb) for v in VCR_LEVELS])
        d15 = np.mean([absolute_density(0.15, v, "control", ca, cb) for v in VCR_LEVELS])
        print(f"  {side_name}: control density mean  p_u=0.05={d05:.6f}  p_u=0.15={d15:.6f}  ratio(0.15/0.05)={d15/d05:.3f}")


if __name__ == "__main__":
    main()
