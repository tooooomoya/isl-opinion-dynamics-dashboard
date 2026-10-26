#!/usr/bin/env python3
"""Start-network dial, REWIRE OFF (static follow graph): is the extremes' posting rise under For You caused by the heavy in-degree tail
(hub hypothesis) or by the network staying connected / hard to sort (findability hypothesis)?  Plan: docs/report/2026-10-26-network-dial.md
Usage: nohup python3 scripts/network_dial_run.py > logs/dial.out 2>&1 &   (resumable; ids dial_<net>_<feed>)
Standing config as standard_run.py except rewire=false. HK in-degree exponent gamma = 2 + A/m (m = 15); pt = triad-formation probability (clustering)."""
import os, sys
os.environ.setdefault("SEARCH_PAR", "12")
sys.path.insert(0, os.path.dirname(__file__))
import reward_search as rs
from standard_run import COMMON, FEEDS

NETS = {  # name -> network tokens (all: out-degree 15 fixed, ~15,000 directed edges, opinion-blind wiring)
    "hkA1": {"hk_a": "1"}, "hkA4": {"hk_a": "4"}, "hkA15": {"hk_a": "15"}, "hkA40": {"hk_a": "40"}, "hkA150": {"hk_a": "150"},   # tail dial, pt .05
    "hkpt0": {"hk_a": "4", "hk_pt": "0"}, "hkpt50": {"hk_a": "4", "hk_pt": "0.5"}, "hkpt95": {"hk_a": "4", "hk_pt": "0.95"},      # clustering dial, A 4
    "random": {"network": "random", "start_deg": "15"},                                                                       # no-hub reference
}
RUNS = [(n, f, False) for n in NETS for f in ("foryou", "chrono")] + [("hkA4", "foryou", True), ("random", "foryou", True)]  # + rewire-ON references

if __name__ == "__main__":
    rs.compile_sources()
    jobs = []
    for net, feed, on in RUNS:
        for seed in range(10):
            t = dict(rs.BASE); t.update(COMMON); t.update(FEEDS[feed]); t.update(NETS[net]); t["rewire"] = "true" if on else "false"
            jobs.append({"id": f"dial_{net}{'_on' if on else ''}_{feed}", "tokens": t, "seed": seed})
    rs.run_stage("dial", jobs)
    print("DIAL_DONE")
