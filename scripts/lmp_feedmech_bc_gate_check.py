"""
2026-08-15 -- tests the mechanism hypothesis formed from lmp_feedmech_followee_composition.py and
lmp_feedmech_feedfill_check.py.

What those two established (see docs/report 2026-08-15 entry):
  1. Feeds are STARVED, not full: extreme-camp readers carry 2.0-3.0 feed items against
     feed_capacity=15. There is no slot competition, so the project's prior "displacement" premise
     (freed slots get refilled by competing content) is false.
  2. Moderate-authored content is a negligible share of an extreme reader's feed even under control
     (0.01-0.06 items of ~2.0-2.4). So the direct "M content dilutes the comfort ratio" story cannot
     account for the observed comfort-ratio gap (-0.05 at p_u=0.05, -0.13 at p_u=0.15).
  3. What actually moves is NEAR-EXTREME-authored content reaching extreme readers: control 0.06-0.23
     vs N_silent 0.21-0.62 items, and the gap is ~3x larger at p_u=0.15 than at p_u=0.05.
  4. Extreme readers follow ~3.26 moderate hubs under N_silent but ~0.01-0.10 under control -- i.e.
     under control they have purged the moderate hubs almost entirely.

Hypothesis this script tests -- the BOUNDED-CONFIDENCE GATE:
  Moderate-hub content (pinned 0.0) is out-of-bc for an extreme agent (|0-(+-1)| = 1.0, and bc is
  capped at bc_ceiling=1.0 with a strict < comparison), so under CONTROL every moderate-hub post an
  extreme agent sees is an out-of-tolerance encounter. Two consequences follow, both from Agent.java:
    (a) it fires unfollow+block at probability p_u (Agent.java:619-643), purging the M hub; and
    (b) it lowers that step's in-tolerance feed fraction, which drives bc DOWN (bc relaxes toward a
        target set by the in-tolerance fraction, and narrows faster than it widens).
  Because follow() only recruits from IN-bc feed content (Agent.java:547-596) while unfollow() blocks
  on OUT-of-bc content, bc's level decides whether near-extreme authors (|+-1.0 - +-0.4| = 0.6) are
  follow CANDIDATES or block TRIGGERS. So the prediction is:

      control  -> M content keeps bc NARROW (< ~0.6) -> NE authors are out-of-bc -> blocked, not
                  followed -> extreme readers stay insulated from NE content
      N_silent -> no M content -> bc stays WIDER (> ~0.6) -> NE authors are in-bc -> recruited as
                  followees -> NE content flows in

  i.e. the moderate hub's causal role is NOT to deliver moderate content into extreme feeds (it barely
  does), but to act as a TOLERANCE-NARROWING agent whose presence keeps the extreme camp's bc below
  the threshold at which near-extreme sources become followable.

Falsifiable predictions checked below:
  P1. mean bc among extreme-camp non-hub agents is HIGHER under N_silent than control.
  P2. the fraction of extreme agents with bc > 0.6 (the E-to-NE opinion gap) is higher under N_silent,
      and that fraction tracks the NE-content-in-feed gap across cells.
  P3. the control-vs-N_silent bc gap is larger at p_u=0.15 than p_u=0.05 (matching finding 3's ~3x).

Also reports the per-capita denominator (population size by class), since the paper's outcome is a
per-capita rate and a compositional shift would change it independently of any per-agent behavior.

Usage: python3 scripts/lmp_feedmech_bc_gate_check.py
"""
import csv

import numpy as np

from lmp_feedmech_stage1 import SEEDS, result_dir, pop_counts_nonhub_windowed
from lmp_feedmech_structural_9b import SUBDIR, CELLS, cell_name

ARMS = ("control", "N_silent")
VCRS = (0.1, 0.15, 0.2)
EXTREME_CLASSES = (0, 4)
NE_GAP = 0.6  # |extreme opinion (+-1.0) - near-extreme hub opinion (+-0.4)|


def opinion_class(op):
    return min(int((op + 1.0) / 0.4), 4)


def bc_profile(seed, subdir):
    """bc statistics over extreme-camp (class 0/4) NON-HUB agents at the final snapshot."""
    d = result_dir(seed, subdir)
    bcs, comfort = [], []
    with open(d / "degrees" / "agent_snapshot_final.csv", newline="") as f:
        for r in csv.DictReader(f):
            if r["isTarget"] != "0":
                continue
            if opinion_class(float(r["opinion"])) not in EXTREME_CLASSES:
                continue
            bcs.append(float(r["bc"]))
            comfort.append(float(r["avgComfortRate"]))
    if not bcs:
        return None
    bcs = np.array(bcs)
    return {
        "bc_mean": bcs.mean(),
        "bc_median": float(np.median(bcs)),
        "frac_bc_above_NE_gap": float((bcs > NE_GAP).mean()),
        "avg_comfort_rate": float(np.mean(comfort)),
        "n_extreme": len(bcs),
    }


KEYS = ("bc_mean", "bc_median", "frac_bc_above_NE_gap", "avg_comfort_rate", "n_extreme")


def main():
    print("Extreme-camp (class 0/4, non-hub) agents at step 40000.")
    print(f"'frac_bc_above_NE_gap' = share whose bc exceeds {NE_GAP}, the opinion distance from an")
    print("extreme agent to a near-extreme (+-0.4) source -- above it, NE authors are in-bc and thus")
    print("eligible as follow candidates; below it they are out-of-bc and trigger block instead.")
    print("bc_floor=0.2, bc_init=0.8, bc_ceiling=1.0.\n")

    data = {}
    for pu, vcr in CELLS:
        for arm in ARMS:
            subdir = f"{SUBDIR}/{cell_name(pu, vcr)}/{arm}"
            profs = [bc_profile(s, subdir) for s in SEEDS]
            data[(pu, vcr, arm)] = {k: np.array([p[k] for p in profs]) for k in KEYS}

    print(f"{'':22s}" + "".join(f"vcr={v:<10}" for v in VCRS) + "\n")
    for key in KEYS:
        print(f"=== {key} ===")
        for pu in (0.05, 0.15):
            for arm in ARMS:
                vals = [data[(pu, v, arm)][key].mean() for v in VCRS]
                print(f"  p_u={pu} {arm:9s}" + "".join(f"{x:<14.4f}" for x in vals))
            diffs = [data[(pu, v, 'N_silent')][key].mean() - data[(pu, v, 'control')][key].mean()
                     for v in VCRS]
            print(f"  p_u={pu} {'DIFF':9s}" + "".join(f"{x:<+14.4f}" for x in diffs))
        print()

    print("=== per-capita DENOMINATOR: live extreme-camp population (trailing-window mean) ===")
    print("(the paper's outcome is posts/population, so a compositional shift moves it by itself)")
    for pu in (0.05, 0.15):
        for arm in ARMS:
            vals = []
            for v in VCRS:
                subdir = f"{SUBDIR}/{cell_name(pu, v)}/{arm}"
                ns = [sum(pop_counts_nonhub_windowed(s, subdir)[c] for c in EXTREME_CLASSES)
                      for s in SEEDS]
                vals.append(np.mean(ns))
            print(f"  p_u={pu} {arm:9s}" + "".join(f"{x:<14.1f}" for x in vals))
        diffs = []
        for v in VCRS:
            c_sub = f"{SUBDIR}/{cell_name(pu, v)}/control"
            m_sub = f"{SUBDIR}/{cell_name(pu, v)}/N_silent"
            cn = np.mean([sum(pop_counts_nonhub_windowed(s, c_sub)[c] for c in EXTREME_CLASSES) for s in SEEDS])
            mn = np.mean([sum(pop_counts_nonhub_windowed(s, m_sub)[c] for c in EXTREME_CLASSES) for s in SEEDS])
            diffs.append(mn - cn)
        print(f"  p_u={pu} {'DIFF':9s}" + "".join(f"{x:<+14.1f}" for x in diffs))


if __name__ == "__main__":
    main()
