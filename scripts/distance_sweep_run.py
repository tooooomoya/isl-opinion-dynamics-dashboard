#!/usr/bin/env python3
"""Opinion-distance sweep: is the two-camp split under For You produced by the distance-dependent mechanisms?  Plan: docs/report/2026-10-27-distance-sweep.md
Usage: nohup python3 scripts/distance_sweep_run.py > logs/dsw.out 2>&1 & disown   (resumable; ids dsw_<net>_b<beta_h>_d<like_max_dist>_<feed>)
beta_h: weight exp(-beta_h |x_i - x_j|) when picking the post to react to and the rewire target (0 = distance ignored).
like_max_dist: a like on a post farther than this does nothing (>= 2 = no limit).  Everything else = standing config (standard_run.COMMON), rewire ON."""
import os, sys
os.environ.setdefault("SEARCH_PAR", "12")
sys.path.insert(0, os.path.dirname(__file__))
import reward_search as rs
from standard_run import COMMON, FEEDS, NETS

SEEDS = [0, 1, 2]
BETAS = [0, 1, 3, 6]
DISTS = [0.3, 1.0, 2.0]
CHRONO_CELLS = [(0, 2.0), (3, 1.0), (6, 0.3)]   # weakest / baseline / strongest distance influence
NET_LIST = ["random", "hkshuf"]

def build():
    jobs = []
    for net in NET_LIST:
        cells = [(b, d, "foryou") for b in BETAS for d in DISTS] + [(b, d, "chrono") for b, d in CHRONO_CELLS]
        for b, d, feed in cells:
            t = dict(rs.BASE); t.update(COMMON); t.update(FEEDS[feed]); t.update(NETS[net]); t.update({"beta_h": str(b), "like_max_dist": str(d)})
            for s in SEEDS:
                jobs.append({"id": f"dsw_{net}_b{b}_d{d}_{feed}", "tokens": t, "seed": s})
    jobs.sort(key=lambda j: j["id"].endswith("chrono"))
    return jobs

if __name__ == "__main__":
    rs.compile_sources()
    rs.run_stage("distance_sweep", build())
    print("DSW_DONE")
