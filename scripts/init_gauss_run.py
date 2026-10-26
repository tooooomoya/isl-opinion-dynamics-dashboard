#!/usr/bin/env python3
"""Standing configuration with a Gaussian start distribution X ~ N(0, 0.5^2) (truncated to [-1, 1] by redraw) instead of U[-1, 1].
Chrono / For You (hop 5) / Trend 100 %, 10 seeds, 20,000 steps. Usage: nohup python3 scripts/init_gauss_run.py random|hkshuf > logs/gauss_<net>.out 2>&1 & disown
Ids gauss_<net>_<feed> (plot: scripts/plot_std.py OUT.png <net> gauss). The identity-fit baseline is the empirical one (mean similarity to the whole
population) because the analytic 1-(1+x^2)/4 holds only for uniform X; everything else is the standing config."""
import os, sys
os.environ.setdefault("SEARCH_PAR", "12")
sys.path.insert(0, os.path.dirname(__file__))
import reward_search as rs
from standard_run import COMMON, FEEDS, NETS

GAUSS = {"init_dist": "gaussian", "init_sd": "0.5", "fit_baseline": "empirical"}

if __name__ == "__main__":
    net = sys.argv[1]
    rs.compile_sources()
    jobs = []
    for name, f in FEEDS.items():
        for seed in range(10):
            t = dict(rs.BASE); t.update(COMMON); t.update(f); t.update(NETS[net]); t.update(GAUSS)
            jobs.append({"id": f"gauss_{net}_{name}", "tokens": t, "seed": seed})
    rs.run_stage(f"gauss_{net}", jobs)
    print("GAUSS_DONE")
