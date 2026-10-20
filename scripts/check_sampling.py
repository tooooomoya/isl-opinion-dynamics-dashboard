#!/usr/bin/env python3
"""Does the rejection-sampled For You candidate set (cost ~ cap) reproduce the earlier scan-then-reservoir results, and how much faster is it?
Usage: nohup python3 scripts/check_sampling.py > logs/check_sampling.out 2>&1 &   (ids smp2_<net>_foryou; For You 100 %, standing config, 3 seeds)
Compare with std_<net>_foryou (same settings, scan-based sampling)."""
import os, sys
os.environ.setdefault("SEARCH_PAR", "6")
sys.path.insert(0, os.path.dirname(__file__))
import reward_search as rs
from standard_run import COMMON, FEEDS, NETS

if __name__ == "__main__":
    rs.compile_sources()
    jobs = []
    for net in ("hk", "random"):
        for seed in (0, 1, 2):
            t = dict(rs.BASE); t.update(COMMON); t.update(FEEDS["foryou"]); t.update(NETS[net])
            jobs.append({"id": f"smp2_{net}_foryou", "tokens": t, "seed": seed})
    rs.run_stage("check_sampling", jobs)
    print("SMP_DONE")
