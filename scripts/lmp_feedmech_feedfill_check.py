"""
2026-08-15 -- follow-up to lmp_feedmech_followee_composition.py.

That script found extreme-camp readers carry a mean out-degree of only ~2.85 (control) / ~6.5
(N_silent) against a max_follow capacity of 43.8638 -- capacity is nowhere near binding. Since the
feed is a uniform sample of the reader's postCash and postCash is filled ONLY by deliveries from
followees (alpha=0, chronological-only), a followee set that small raises the question this script
answers: is the feed actually FULL (15 slots, so new content displaces old) or STARVED (fewer than 15
items available, so content adds/subtracts without displacing anything)?

This matters because the project's existing mechanism story (docs/report 2026-08-06 entries, carried
into the comfort-volume regression) assumes displacement -- "when feed_capacity is fixed, more
near-extreme content filling freed-up slots can mechanically compete with (displace) own-camp
content." If feeds are starved, that premise is false and the M-hub effect is not a displacement
effect at all.

Reports, for extreme-camp (class 0/4) readers over the trailing 2000-step window:
  - feedChronoCountMean: actual delivered feed size (vs feed_capacity=15)
  - feedAuthorClass*CountMean / feedComfortClass*CountMean: composition and how much is within-vcr
  - avgComfortRate-adjacent quantities that drive targetPostProb

Usage: python3 scripts/lmp_feedmech_feedfill_check.py
"""
import numpy as np

from lmp_feedmech_stage1 import SEEDS, trailing_window_means
from lmp_feedmech_structural_9b import SUBDIR, CELLS, cell_name

ARMS = ("control", "N_silent")
VCRS = (0.1, 0.15, 0.2)

# reader classes 0 and 4 = the extreme camp (the paper's outcome population)
COLS = []
for r in (0, 4):
    COLS += [f"feedChronoCountMean_{r}", f"feedForYouCountMean_{r}",
             f"feedModCountMean_{r}", f"feedHubCountMean_{r}",
             f"feedRepostCountMean_{r}", f"feedOriginalCountMean_{r}"]
    COLS += [f"feedAuthorClass{a}CountMean_{r}" for a in range(5)]
    COLS += [f"feedComfortClass{a}CountMean_{r}" for a in range(5)]


def sym(rows, base):
    """Average the class-0-reader and class-4-reader versions of a column into one extreme-camp
    number (the two sides are mirror images; every other analysis in this project averages them)."""
    return (np.array([r[f"{base}_0"] for r in rows]) + np.array([r[f"{base}_4"] for r in rows])) / 2.0


def sym_author(rows, kind, near):
    """Same-sign camp-relative author tally: for class-0 readers the near-extreme side is class 1 and
    own camp is class 0; for class-4 readers they are 3 and 4 respectively."""
    if near == "own":
        a0, a4 = 0, 4
    elif near == "ne":
        a0, a4 = 1, 3
    elif near == "mid":
        a0 = a4 = 2
    return (np.array([r[f"feed{kind}Class{a0}CountMean_0"] for r in rows]) +
            np.array([r[f"feed{kind}Class{a4}CountMean_4"] for r in rows])) / 2.0


def main():
    print("Extreme-camp (class 0/4) readers, trailing 2000-step means. feed_capacity = 15.\n")

    data = {}
    for pu, vcr in CELLS:
        for arm in ARMS:
            subdir = f"{SUBDIR}/{cell_name(pu, vcr)}/{arm}"
            rows = [trailing_window_means(s, subdir, COLS) for s in SEEDS]
            data[(pu, vcr, arm)] = rows

    def show(label, fn):
        print(f"=== {label} ===")
        for pu in (0.05, 0.15):
            for arm in ARMS:
                vals = [fn(data[(pu, v, arm)]).mean() for v in VCRS]
                print(f"  p_u={pu} {arm:9s}" + "".join(f"{x:<14.4f}" for x in vals))
            diffs = [fn(data[(pu, v, 'N_silent')]).mean() - fn(data[(pu, v, 'control')]).mean()
                     for v in VCRS]
            print(f"  p_u={pu} {'DIFF':9s}" + "".join(f"{x:<+14.4f}" for x in diffs))
        print()

    print(f"{'':22s}" + "".join(f"vcr={v:<10}" for v in VCRS) + "\n")

    show("TOTAL FEED SIZE (chrono; capacity=15)", lambda rows: sym(rows, "feedChronoCountMean"))
    show("  of which: moderate-authored", lambda rows: sym(rows, "feedModCountMean"))
    show("  of which: hub-authored (any tier)", lambda rows: sym(rows, "feedHubCountMean"))
    show("  of which: reposts", lambda rows: sym(rows, "feedRepostCountMean"))
    show("  of which: originals", lambda rows: sym(rows, "feedOriginalCountMean"))

    show("author = OWN camp (class 0 for r0 / 4 for r4)",
         lambda rows: sym_author(rows, "Author", "own"))
    show("  within-vcr (comfortable) of those",
         lambda rows: sym_author(rows, "Comfort", "own"))
    show("author = NEAR-EXTREME same side (1 for r0 / 3 for r4)",
         lambda rows: sym_author(rows, "Author", "ne"))
    show("  within-vcr (comfortable) of those",
         lambda rows: sym_author(rows, "Comfort", "ne"))
    show("author = MIDDLE (class 2)",
         lambda rows: sym_author(rows, "Author", "mid"))
    show("  within-vcr (comfortable) of those",
         lambda rows: sym_author(rows, "Comfort", "mid"))

    # the ratio that actually drives targetPostProb
    def comfort_ratio(rows):
        tot = sum(sym(rows, f"feedAuthorClass{a}CountMean") for a in range(5))
        com = sum(sym(rows, f"feedComfortClass{a}CountMean") for a in range(5))
        return np.where(tot > 0, com / np.maximum(tot, 1e-12), np.nan)

    show("COMFORT RATIO = comfortable/total feed (drives targetPostProb)", comfort_ratio)


if __name__ == "__main__":
    main()
