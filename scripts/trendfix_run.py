#!/usr/bin/env python3
"""Trend feed with the corrected ranking: likes count like reshares (trend_count=both) and equal scores are ordered at random (trend_tie=random).
Standing config otherwise; Trend 100 % (hop 5), 10 seeds, 20,000 steps. Ids trendfix_<net>_trend (the old ones, baseline_<net>_trend, are kept for comparison).
Usage: nohup python3 scripts/trendfix_run.py hk|random|sbm|ws|hkshuf [gauss] > logs/trendfix_<net>.out 2>&1 & disown   (resumable)"""
import os, sys
os.environ.setdefault("SEARCH_PAR", "12")
sys.path.insert(0, os.path.dirname(__file__))
import reward_search as rs
from standard_run import COMMON, FEEDS, NETS
from init_gauss_run import GAUSS

FIX = {"trend_count": "both", "trend_tie": "random"}

if __name__ == "__main__":
    net = sys.argv[1]; gauss = len(sys.argv) > 2 and sys.argv[2] == "gauss"
    rs.compile_sources()
    jobs = []
    for seed in range(10):
        t = dict(rs.BASE); t.update(COMMON); t.update(FEEDS["trend"]); t.update(NETS[net]); t.update(FIX)
        if gauss: t.update(GAUSS)
        jobs.append({"id": f"trendfix{'_gauss' if gauss else ''}_{net}_trend", "tokens": t, "seed": seed})
    rs.run_stage(f"trendfix_{net}", jobs)
    print("TRENDFIX_DONE")
