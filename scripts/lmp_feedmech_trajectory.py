"""
2026-08-15 -- trajectory analysis, prompted by a correct user critique of the 2026-08-15 mechanism
write-up (docs/report/2026-08-15-mechanism-re-derivation.md).

THE CRITIQUE: that write-up claimed moderate-hub content "holds bc narrow" in the control arm. But
the same write-up measured extreme-camp readers as following only 0.017-0.102 moderate hubs at step
40000 -- i.e. the moderate hubs are already purged. Once purged, moderate posts should barely reach
those readers at all, so a SUSTAINED bc-suppression story is not obviously available. The suppression
may instead be a TRANSIENT that acts early (while the moderate hubs are still followed) and then locks
in via slow-relaxing state, or it may be sustained through an indirect channel -- reposts. Because
rel_attrib=original keeps postUserId as the original creator, a followee who relays a moderate hub's
post delivers moderate-authored content to a reader who never followed (or has already blocked) that
hub. Which of these holds is not decidable from an end-of-run snapshot, which is all the prior
write-up used.

SECOND OPEN QUESTION (user-raised, and the more interesting one): why does a HIGHER unfollow
probability produce MORE near-extreme content flowing into extreme readers' feeds? Measured at
vcr=0.1, near-extreme-authored feed content is:
    control : p_u=0.05 -> 0.079,  p_u=0.15 -> 0.060   (higher p_u purges more; intuitive)
    N_silent: p_u=0.05 -> 0.213,  p_u=0.15 -> 0.494   (higher p_u admits 2.3x MORE; counterintuitive)
and bc is wider at higher p_u in BOTH arms (control 0.271->0.296, N_silent 0.285->0.333). The
candidate explanation is self-purification: p_u removes out-of-tolerance sources faster, which raises
the in-tolerance share of what remains, which relaxes bc UPWARD, which in turn lets more authors
qualify as follow candidates. That predicts a specific ORDERING IN TIME (purge first, bc rise second,
tie accumulation third) that only a trajectory can test.

WHAT THIS SCRIPT MEASURES, per 5000-step checkpoint (GEXF) and per binned step window (results.csv),
for both arms and both p_u, at vcr=0.1 (the cell where the counterintuitive p_u effect is largest):

  From GEXF checkpoints (0, 5000, ..., 40000):
    - E-camp readers' mean number of followed MODERATE HUBS  -> when does the purge happen?
    - E-camp readers' mean number of followed NEAR-EXTREME sources (hub + population)
    - E-camp readers' mean boundedConfidence  -> when does the arm gap in bc open?
    - E-camp readers' mean postProb
  From results.csv (binned means over 2000-step windows):
    - feedModCountMean (moderate-authored content reaching E readers) -> does it go to zero after the
      purge (transient story) or persist at a low nonzero level (repost-channel story)?
    - feedAuthorClass1/3 (near-extreme-authored content reaching E readers)
    - cRateMean (per-agent comfort rate)

Usage: python3 scripts/lmp_feedmech_trajectory.py
"""
import csv

import numpy as np
import pandas as pd

from lmp_feedmech_stage1 import result_dir
from lmp_feedmech_structural_9b import SUBDIR, cell_name, parse_gexf, GEXF_NS

import xml.etree.ElementTree as ET

SEEDS_TRAJ = [8900000 + i for i in range(8)]  # 8 seeds is enough to resolve trajectory shape
CHECKPOINTS = [0, 5000, 10000, 15000, 20000, 25000, 30000, 35000, 40000]
VCR = 0.1
PUS = (0.05, 0.15)
ARMS = ("control", "N_silent")
EXTREME_CLASSES = (0, 4)
NE_CLASSES = (1, 3)
MODERATE_CLASS = 2


def parse_gexf_full(path):
    """Like parse_gexf but also returns boundedConfidence and postProb per node."""
    root = ET.parse(path).getroot()
    graph = root.find(f"{GEXF_NS}graph")
    cls, tgt, bc, pp = {}, {}, {}, {}
    for node in graph.find(f"{GEXF_NS}nodes"):
        nid = node.get("id")
        attvalues = node.find(f"{GEXF_NS}attvalues")
        c, t, b, p = None, False, np.nan, np.nan
        if attvalues is not None:
            for av in attvalues:
                k, v = av.get("for"), av.get("value")
                if k == "opinionclass":
                    c = int(v)
                elif k == "target":
                    t = (v == "true")
                elif k == "boundedconfidence":
                    b = float(v)
                elif k == "postprob":
                    p = float(v)
        cls[nid], tgt[nid], bc[nid], pp[nid] = c, t, b, p
    edges = [(e.get("source"), e.get("target")) for e in graph.find(f"{GEXF_NS}edges")]
    return cls, tgt, bc, pp, edges


def gexf_at(seed, subdir, step):
    d = result_dir(seed, subdir)
    hits = list((d / "GEXF").glob(f"*/step_{step}.gexf"))
    return hits[0] if hits else None


def checkpoint_stats(seed, subdir, step):
    path = gexf_at(seed, subdir, step)
    if path is None:
        return None
    cls, tgt, bc, pp, edges = parse_gexf_full(path)
    readers = {n for n, c in cls.items() if c in EXTREME_CLASSES and not tgt[n]}
    if not readers:
        return None
    mod_hub = {r: 0 for r in readers}
    ne_any = {r: 0 for r in readers}
    for s, t in edges:
        if s in readers:
            if tgt[t] and cls[t] == MODERATE_CLASS:
                mod_hub[s] += 1
            if cls[t] in NE_CLASSES:
                ne_any[s] += 1
    return {
        "mod_hubs_followed": float(np.mean(list(mod_hub.values()))),
        "ne_followed": float(np.mean(list(ne_any.values()))),
        "bc": float(np.nanmean([bc[r] for r in readers])),
        "postProb": float(np.nanmean([pp[r] for r in readers])),
    }


FEED_COLS = ["step", "feedModCountMean_0", "feedModCountMean_4",
             "feedAuthorClass1CountMean_0", "feedAuthorClass3CountMean_4",
             "cRateMean_0", "cRateMean_4"]


def feed_trajectory(seed, subdir, bin_size=2000):
    d = result_dir(seed, subdir)
    df = pd.read_csv(d / "metrics" / "results.csv", usecols=FEED_COLS)
    df["mod"] = (df["feedModCountMean_0"] + df["feedModCountMean_4"]) / 2.0
    df["ne"] = (df["feedAuthorClass1CountMean_0"] + df["feedAuthorClass3CountMean_4"]) / 2.0
    df["crate"] = (df["cRateMean_0"] + df["cRateMean_4"]) / 2.0
    df["bin"] = (df["step"] // bin_size) * bin_size
    return df.groupby("bin")[["mod", "ne", "crate"]].mean()


def main():
    print(f"Trajectory at vcr={VCR}, extreme-camp (class 0/4) non-hub readers, "
          f"{len(SEEDS_TRAJ)} seeds.\n")

    # ---- GEXF checkpoint trajectories ----
    gx = {}
    for pu in PUS:
        for arm in ARMS:
            subdir = f"{SUBDIR}/{cell_name(pu, VCR)}/{arm}"
            for step in CHECKPOINTS:
                stats = [checkpoint_stats(s, subdir, step) for s in SEEDS_TRAJ]
                stats = [x for x in stats if x is not None]
                if stats:
                    gx[(pu, arm, step)] = {k: np.mean([x[k] for x in stats]) for k in stats[0]}

    for key, label in (("mod_hubs_followed", "MODERATE HUBS followed by E readers (of 20 available)"),
                       ("ne_followed", "NEAR-EXTREME sources followed by E readers"),
                       ("bc", "bounded confidence (mean over E readers)"),
                       ("postProb", "postProb (mean over E readers)")):
        print(f"=== {label} ===")
        print(f"  {'step':>8s}" + "".join(f"{s:>10d}" for s in CHECKPOINTS))
        for pu in PUS:
            for arm in ARMS:
                vals = [gx.get((pu, arm, s), {}).get(key, np.nan) for s in CHECKPOINTS]
                print(f"  p_u={pu} {arm:9s}" + "".join(f"{v:>10.3f}" for v in vals))
            diffs = [gx.get((pu, 'N_silent', s), {}).get(key, np.nan) -
                     gx.get((pu, 'control', s), {}).get(key, np.nan) for s in CHECKPOINTS]
            print(f"  p_u={pu} {'DIFF':9s}" + "".join(f"{v:>+10.3f}" for v in diffs))
        print()

    # ---- per-step feed trajectories ----
    print("=" * 100)
    print("Feed-content trajectories (2000-step bin means)")
    print("=" * 100)
    ft = {}
    for pu in PUS:
        for arm in ARMS:
            subdir = f"{SUBDIR}/{cell_name(pu, VCR)}/{arm}"
            frames = [feed_trajectory(s, subdir) for s in SEEDS_TRAJ]
            ft[(pu, arm)] = sum(frames) / len(frames)

    show_bins = [0, 2000, 4000, 6000, 10000, 14000, 20000, 28000, 34000, 38000]
    for col, label in (("mod", "MODERATE-authored content in E readers' feeds"),
                       ("ne", "NEAR-EXTREME-authored content in E readers' feeds"),
                       ("crate", "per-agent comfort rate (cRateMean)")):
        print(f"=== {label} ===")
        print(f"  {'bin':>8s}" + "".join(f"{b:>10d}" for b in show_bins))
        for pu in PUS:
            for arm in ARMS:
                s = ft[(pu, arm)][col]
                vals = [s.get(b, np.nan) for b in show_bins]
                print(f"  p_u={pu} {arm:9s}" + "".join(f"{v:>10.4f}" for v in vals))
            sc, sm = ft[(pu, 'control')][col], ft[(pu, 'N_silent')][col]
            diffs = [sm.get(b, np.nan) - sc.get(b, np.nan) for b in show_bins]
            print(f"  p_u={pu} {'DIFF':9s}" + "".join(f"{v:>+10.4f}" for v in diffs))
        print()


if __name__ == "__main__":
    main()
