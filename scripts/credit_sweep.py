#!/usr/bin/env python3
"""credit=post sweep: w_rec {1,2,4} x q_tau {0.1,0.05} x credit_horizon {50,200,500}, For You 100 %, seeds 0-2.
Usage: nohup python3 scripts/credit_sweep.py > logs/rsearch/credit_sweep.out 2>&1 &   (resumable; ends with CSWEEP_DONE)
Read captured / justified / favShare / medLead / rewardMean, not spread (see credit_compare.py)."""
import os, sys, itertools
sys.path.insert(0, os.path.dirname(__file__))
import reward_search as rs

if __name__ == "__main__":
    rs.compile_sources()
    jobs = []
    for wr, tau, H in itertools.product(["1", "2", "4"], ["0.1", "0.05"], ["50", "200", "500"]):
        for seed in (0, 1, 2):
            t = dict(rs.BASE); t.update(rs.SCREENS["foryou100"])
            t.update({"credit": "post", "credit_horizon": H, "q_tau": tau, "w_fit": "1", "w_rec": wr,
                      "recog_mix": "0.5", "recog_lambda": "2", "q_init": str(10 * (1 + int(wr)))})
            jobs.append({"id": f"cs_wr{wr}_t{tau}_H{H}", "tokens": t, "seed": seed})
    rs.run_stage("credit_sweep", jobs)
    print("CSWEEP_DONE")
