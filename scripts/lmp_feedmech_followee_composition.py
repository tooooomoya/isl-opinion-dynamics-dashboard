"""
2026-08-15 -- diagnostic prompted by the 9c null result (docs/report/2026-08-07-cna2026-paper-writing-
handoff.md section 9c: structural regression R2=0.064-0.168, far weaker than the content-volume
regression's 0.560, and reproduces no crossing shift).

Motivation: alpha=0 in BASE_TOKENS -- feedAlgoShare=0 -- so the For-You/velocity channel is dead
(OpinionDynamics.java:295 sets velocityRanked=null; AdminOptim.java:396 gives algoSlots=0). The ONLY
delivery path is: author posts/reposts -> delivered to admin.getFollowers(author) -> reader's postCash
FIFO -> uniform sample of <=15 becomes the feed (AdminOptim.java:399-417). Under that mechanism the
global cross-camp edge DENSITY used in 9b (count/(|A|*|B|), symmetric-ish, activity-blind) is a poor
proxy for what actually reaches a reader, because feed share depends on the READER'S OWN followee
list weighted by each followee's posting activity, relative to their other followees -- not on a
population-level pair density.

This script measures the thing the mechanism actually reads: for each extreme-camp (class 0/4) non-hub
reader, the COMPOSITION of their followee set, split by followee class and by hub-vs-population, and
how it differs control vs N_silent across the p_u x vcr grid.

Specific hypothesis under test (formed from the code, to be confirmed/refuted here):
  Moderate-hub content (pinned opinion 0.0) is out-of-bc for an extreme reader (|0-(+-1)|=1.0, and bc
  is capped at bc_ceiling=1.0 with a strict < test), so under CONTROL every M-hub post an extreme
  agent sees is an out-of-tolerance encounter that fires unfollow+block at probability p_u
  (Agent.java:619-643). Under M_SILENT the M hubs emit nothing, so that trigger never fires and the
  extreme agents KEEP following them -- silent followees that occupy followee slots while delivering
  zero content. If the follow capacity (max_follow=43.8638) binds, those retained-but-silent ties
  crowd out live ones, which would be a structural difference the 9b density metric cannot see
  (it never looks at E->M_hub edges at all, only E->NE).

Usage: python3 scripts/lmp_feedmech_followee_composition.py
"""
import numpy as np

from lmp_feedmech_stage1 import SEEDS
from lmp_feedmech_structural_9b import (
    SUBDIR, CELLS, cell_name, parse_gexf, final_gexf_path,
)

ARMS = ("control", "N_silent")
EXTREME_CLASSES = (0, 4)


def followee_profile(seed, subdir):
    """For extreme-camp (class 0/4) NON-HUB readers, tally their out-edges (= who they follow),
    split by followee opinion class and hub status. Returns per-reader means."""
    cls, tgt, edges = parse_gexf(final_gexf_path(seed, subdir))

    readers = {n for n, c in cls.items() if c in EXTREME_CLASSES and not tgt[n]}
    if not readers:
        return None

    out_deg = {r: 0 for r in readers}
    # followee tallies, keyed by (class, is_hub)
    tally = {(c, h): {r: 0 for r in readers} for c in range(5) for h in (False, True)}

    for s, t in edges:
        if s in readers:
            out_deg[s] += 1
            key = (cls[t], tgt[t])
            if key in tally:
                tally[key][s] += 1

    prof = {"out_degree": float(np.mean(list(out_deg.values())))}
    for (c, h), d in tally.items():
        label = f"{'hub' if h else 'pop'}_class{c}"
        prof[label] = float(np.mean(list(d.values())))
    # aggregate rollups
    prof["hub_M"] = prof["hub_class2"]                       # moderate hubs (pinned 0.0 -> class 2)
    prof["hub_E"] = prof["hub_class0"] + prof["hub_class4"]  # extreme hubs (pinned +-1.0)
    prof["hub_NE"] = prof["hub_class1"] + prof["hub_class3"] # near-extreme hubs (pinned +-0.4)
    prof["hub_total"] = sum(prof[f"hub_class{c}"] for c in range(5))
    prof["pop_total"] = sum(prof[f"pop_class{c}"] for c in range(5))
    return prof


KEYS = ("out_degree", "hub_M", "hub_E", "hub_NE", "hub_total", "pop_total",
        "pop_class0", "pop_class1", "pop_class2", "pop_class3", "pop_class4")


def main():
    print("Extreme-camp (class 0/4, non-hub) readers: mean followee-set composition at step 40000.")
    print("'hub_M' = moderate hubs followed; 'pop_classN' = ordinary (non-hub) agents of class N followed.")
    print(f"max_follow capacity = 43.8638 (BASE_TOKENS) -- watch whether out_degree sits at it.\n")

    data = {}
    for pu, vcr in CELLS:
        for arm in ARMS:
            subdir = f"{SUBDIR}/{cell_name(pu, vcr)}/{arm}"
            profs = [followee_profile(s, subdir) for s in SEEDS]
            data[(pu, vcr, arm)] = {k: np.array([p[k] for p in profs]) for k in KEYS}

    for key in KEYS:
        print(f"=== {key} ===")
        print(f"{'':22s}" + "".join(f"vcr={v:<10}" for _, v in CELLS[:3]))
        for pu in (0.05, 0.15):
            for arm in ARMS:
                vals = [data[(pu, v, arm)][key].mean() for v in (0.1, 0.15, 0.2)]
                print(f"  p_u={pu} {arm:9s}" + "".join(f"{x:<14.3f}" for x in vals))
            diffs = [data[(pu, v, 'N_silent')][key].mean() - data[(pu, v, 'control')][key].mean()
                     for v in (0.1, 0.15, 0.2)]
            print(f"  p_u={pu} {'DIFF':9s}" + "".join(f"{x:<+14.3f}" for x in diffs))
        print()


if __name__ == "__main__":
    main()
