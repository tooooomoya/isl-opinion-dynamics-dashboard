#!/usr/bin/env python3
"""Re-run of the standing configuration after the reshare simplification (likes on a reshare go to the resharer only; each like on a copy
refreshes the original's life; reshare_alpha removed). Uniform start on hk/random/sbm/ws/hkshuf, Gaussian start on random/hkshuf,
Chrono / For You / Trend, 10 seeds each, one pool. Ids baseline_<net>_<feed> and gauss_<net>_<feed> as before (resumable).
Usage: nohup python3 scripts/rerun_no_alpha.py > logs/rerun_no_alpha.out 2>&1 & disown"""
import os, sys
os.environ.setdefault("SEARCH_PAR", "24")
sys.path.insert(0, os.path.dirname(__file__))
import reward_search as rs
from standard_run import COMMON, FEEDS, NETS
from init_gauss_run import GAUSS

if __name__ == "__main__":
    rs.compile_sources()
    jobs = []
    for prefix, nets, extra in [("baseline", ["hk", "random", "sbm", "ws", "hkshuf"], {}), ("gauss", ["random", "hkshuf"], GAUSS)]:
        for net in nets:
            for name, f in FEEDS.items():
                for seed in range(10):
                    t = dict(rs.BASE); t.update(COMMON); t.update(f); t.update(NETS[net]); t.update(extra)
                    jobs.append({"id": f"{prefix}_{net}_{name}", "tokens": t, "seed": seed})
    rs.run_stage("rerun_no_alpha", jobs)
    print("RERUN_DONE")
