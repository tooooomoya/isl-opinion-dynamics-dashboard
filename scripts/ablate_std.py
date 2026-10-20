#!/usr/bin/env python3
"""Which of the two 2026-10-16 changes (For You candidate cap 300, relative identity fit) changed the For You result on Holme-Kim?
Usage: nohup python3 scripts/ablate_std.py > logs/ablate_std.out 2>&1 &   (ids abl_<variant>; For You 100 %, 3 seeds)
variants: relnocap = relative fit, no cap; rawcap = raw fit, cap 300. Reference: std_hk_foryou (relative + cap) and fcng_foryou (raw, no cap, older code)."""
import os, sys
os.environ.setdefault("SEARCH_PAR", "6")
sys.path.insert(0, os.path.dirname(__file__))
import reward_search as rs
from standard_run import COMMON, FEEDS

if __name__ == "__main__":
    rs.compile_sources()
    jobs = []
    for var, upd in {"relnocap": {"foryou_cand_max": "0"}, "rawcap": {"fit_mode": "raw"}}.items():
        for seed in (0, 1, 2):
            t = dict(rs.BASE); t.update(COMMON); t.update(FEEDS["foryou"]); t.update(upd)
            if var == "rawcap": t.pop("fit_baseline", None)
            jobs.append({"id": f"abl_{var}", "tokens": t, "seed": seed})
    rs.run_stage("ablate_std", jobs)
    print("ABL_DONE")
