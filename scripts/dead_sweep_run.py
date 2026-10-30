#!/usr/bin/env python3
"""dead_after (L) sweep: standing config on hkshuf, Chrono / For You / Trend, L in {10,25,50,100,200,400}, 3 seeds, 20,000 steps.
Usage: nohup python3 scripts/dead_sweep_run.py > logs/dead_sweep.out 2>&1 & disown   (resumable; ids dsL_hkshuf_L<L>_<feed>)"""
import os, sys
os.environ.setdefault("SEARCH_PAR", "12")
sys.path.insert(0, os.path.dirname(__file__))
import reward_search as rs
from standard_run import COMMON, FEEDS, NETS

if __name__ == "__main__":
    rs.compile_sources()
    jobs = []
    for L in (10, 25, 50, 100, 200, 400):
        for name, f in FEEDS.items():
            for seed in range(3):
                t = dict(rs.BASE); t.update(COMMON); t.update(f); t.update(NETS["hkshuf"]); t["dead_after"] = str(L)
                jobs.append({"id": f"dsL_hkshuf_L{L}_{name}", "tokens": t, "seed": seed})
    rs.run_stage("dead_sweep", jobs)
    print("DEADSWEEP_DONE")
