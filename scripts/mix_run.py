#!/usr/bin/env python3
"""Mixed feed: 50 % For You (hop 5) + 50 % Trend (hop 5), standing config, 10 seeds, 20,000 steps, on hkshuf and random (ER) starts.
Usage: nohup python3 scripts/mix_run.py > logs/mix.out 2>&1 & disown   (resumable; ids baseline_<net>_mix)"""
import os, sys
os.environ.setdefault("SEARCH_PAR", "12")
sys.path.insert(0, os.path.dirname(__file__))
import reward_search as rs
from standard_run import COMMON, NETS

MIX = {"foryou_share": "0.5", "foryou_hop": "5", "trend_share": "0.5", "trend_hop": "5"}
if __name__ == "__main__":
    rs.compile_sources()
    jobs = []
    for net in ("hkshuf", "random"):
        for seed in range(10):
            t = dict(rs.BASE); t.update(COMMON); t.update(MIX); t.update(NETS[net])
            jobs.append({"id": f"baseline_{net}_mix", "tokens": t, "seed": seed})
    rs.run_stage("mix", jobs)
    print("MIX_DONE")
