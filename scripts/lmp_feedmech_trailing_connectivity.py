"""
2026-08-06 -- reconciles the tension between two findings:
  (1) PE<->E structural connectivity (cumulative, whole-run final snapshot) is HIGHER under N_silent
      (lmp_feedmech_stage1_gexf.py).
  (2) Population-only new-follow activity (trailing 2000-step window) is LOWER under N_silent, by a
      large margin, at every cell (lmp_feedmech_stage1.py's followCount).

These aren't necessarily contradictory (different time horizons: whole-run cumulative vs. last-2000-
step rate), but that's an assumption, not a shown fact. This script checks it directly: reads the SAME
already-existing GEXF data from lmp_feedmech_stage1_gexf.py's run (no new simulation runs -- GEXF
checkpoints are written every 5000 steps regardless, step_35000.gexf and step_40000.gexf both already
exist), and computes the NET CHANGE in PE<->E edge count over that trailing 5000-step window (closest
available window to the 2000-step follow-count window, given the fixed checkpoint cadence) --
control vs N_silent. If N_silent's trailing-window PE<->E edge growth is still higher than control's
despite lower OVERALL follow volume, the reconciliation holds (PE<->E is a disproportionate share of
N_silent's shrunken follow activity). If not, the two findings are in real tension, not just different
time windows, and the structural-homophily-gate story needs revisiting.

Usage: python3 scripts/lmp_feedmech_trailing_connectivity.py  (fast, all data already on disk)
"""
import numpy as np

from lmp_feedmech_stage1_gexf import CELLS, cross_class_density, SUBDIR
from lmp_feedmech_stage1 import cell_name

# NOT imported from lmp_feedmech_stage1.SEEDS -- that constant was extended to the full 15-seed
# block for Stage 2, but the GEXF batch (lmp_feedmech_stage1_gexf.py) only ever ran the original 5.
SEEDS = [8900000 + i for i in range(5)]
CHECKPOINTS = (35000, 40000)


def report_cell(pu, vcr):
    ctrl_subdir = f"{SUBDIR}/{cell_name(pu, vcr)}/control"
    msil_subdir = f"{SUBDIR}/{cell_name(pu, vcr)}/N_silent"

    print(f"\n--- p_u={pu} vcr={vcr} ---")
    for label, ca, cb in (("E- -> PE- (0->1)", 0, 1), ("E+ -> PE+ (4->3)", 4, 3)):
        ctrl_counts = {cp: np.array([cross_class_density(s, ctrl_subdir, ca, cb, checkpoint=cp)[3] for s in SEEDS]) for cp in CHECKPOINTS}
        msil_counts = {cp: np.array([cross_class_density(s, msil_subdir, ca, cb, checkpoint=cp)[3] for s in SEEDS]) for cp in CHECKPOINTS}
        ctrl_delta = ctrl_counts[40000] - ctrl_counts[35000]
        msil_delta = msil_counts[40000] - msil_counts[35000]
        print(f"    {label}:")
        print(f"      edge count @35000: control={ctrl_counts[35000].mean():.2f}  N_silent={msil_counts[35000].mean():.2f}")
        print(f"      edge count @40000: control={ctrl_counts[40000].mean():.2f}  N_silent={msil_counts[40000].mean():.2f}")
        print(f"      NET CHANGE (35000->40000, trailing 5000 steps): control={ctrl_delta.mean():+.2f}  N_silent={msil_delta.mean():+.2f}  diff={(msil_delta-ctrl_delta).mean():+.2f}")


def main():
    print("=== PE<->E edge-count NET CHANGE over the trailing 5000 steps (35000->40000), reusing")
    print("    already-existing GEXF checkpoints from lmp_feedmech_stage1_gexf.py's run -- no new")
    print("    simulation runs. Reconciles: is N_silent's trailing-window PE<->E growth still higher")
    print("    than control's, despite N_silent's much lower overall follow-count volume? ===")
    for pu, vcr in CELLS:
        report_cell(pu, vcr)


if __name__ == "__main__":
    main()
