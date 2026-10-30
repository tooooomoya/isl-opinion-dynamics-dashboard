#!/usr/bin/env python3
"""Standing config with REWIRING OFF (rewire=false: the follow network stays at its start wiring), Chrono / For You (hop 5) / Trend 100 %, 10 seeds, 20,000 steps, on the
random (ER), dcsbm, ws and hkshuf start networks. Usage: nohup python3 scripts/norewire_run.py > logs/norewire.out 2>&1 & disown   (resumable; ids norewire_<net>_<feed>;
plot: python3 scripts/plot_std.py OUT.png <net> norewire)"""
import os, sys
os.environ.setdefault("SEARCH_PAR", "12")
sys.path.insert(0, os.path.dirname(__file__))
import reward_search as rs
from standard_run import COMMON, FEEDS, NETS

if __name__ == "__main__":
    rs.compile_sources()
    jobs = []
    for net in ("random", "sbm", "ws", "hkshuf"):
        for name, f in FEEDS.items():
            for seed in range(10):
                t = dict(rs.BASE); t.update(COMMON); t.update(f); t.update(NETS[net]); t["rewire"] = "false"
                jobs.append({"id": f"norewire_{net}_{name}", "tokens": t, "seed": seed})
    rs.run_stage("norewire", jobs)
    print("NOREWIRE_DONE")
