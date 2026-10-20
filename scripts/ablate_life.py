#!/usr/bin/env python3
"""Why do reshared copies have a longer lifetime tail than original posts (random start network, Chrono / Trend)?
Ablation: standing config with notify_original = 0 (reshares of my posts no longer join the original author's pool). 2 seeds each.
Usage: nohup python3 scripts/ablate_life.py > logs/ablate_life.out 2>&1 &   (ids abl2_<feed>_nonotify; ends with ABL2_DONE)"""
import os, sys
os.environ.setdefault("SEARCH_PAR", "4")
sys.path.insert(0, os.path.dirname(__file__))
import reward_search as rs
from standard_run import COMMON, FEEDS, NETS

if __name__ == "__main__":
    rs.compile_sources()
    jobs = []
    for feed in ("chrono", "trend"):
        for seed in (0, 1):
            t = dict(rs.BASE); t.update(COMMON); t.update(FEEDS[feed]); t.update(NETS["random"]); t["notify_original"] = "0"
            jobs.append({"id": f"abl2_{feed}_nonotify", "tokens": t, "seed": seed})
    rs.run_stage("ablate_life", jobs)
    print("ABL2_DONE")
