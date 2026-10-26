#!/usr/bin/env python3
"""Degree-matched control for the start-network dial: HK degree sequence, wiring randomized (network=hkshuf). Plan/results: docs/report/2026-10-26-network-dial.md
Usage: nohup python3 scripts/dial_shuf_run.py > logs/dial_shuf.out 2>&1 &   (resumable; ids dial_hkshufA<A>[_on]_<feed>)"""
import os, sys
os.environ.setdefault("SEARCH_PAR", "12")
sys.path.insert(0, os.path.dirname(__file__))
import reward_search as rs
from standard_run import COMMON, FEEDS
RUNS = [(a, f, on) for a in (1, 4, 150) for f, on in (("foryou", False), ("chrono", False), ("foryou", True))]
if __name__ == "__main__":
    rs.compile_sources()
    jobs = []
    for a, feed, on in RUNS:
        for seed in range(10):
            t = dict(rs.BASE); t.update(COMMON); t.update(FEEDS[feed]); t.update({"network": "hkshuf", "hk_a": str(a)}); t["rewire"] = "true" if on else "false"
            jobs.append({"id": f"dial_hkshufA{a}{'_on' if on else ''}_{feed}", "tokens": t, "seed": seed})
    rs.run_stage("dial_shuf", jobs)
    print("DIAL_DONE")
