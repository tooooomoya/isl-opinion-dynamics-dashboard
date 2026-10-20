#!/usr/bin/env python3
"""Does crediting likes back to the action that made the post (credit=post) separate the actions' rewards?

Compares credit=stock (original: recognition stock in every visit's reward) with credit=post (likes a new post gets within
H steps are paid to the (state, action) that made it) on the For-You-100% screen, seeds 0-2.
Usage: nohup python3 scripts/credit_compare.py > logs/rsearch/credit_compare.out 2>&1 &
Reuses reward_search.py's run + summary code; rows land in results/rsearch/summary.jsonl (ids cr_*).
NOTE: in credit=post the logged reward sd (rewSd) covers only the immediate fit term, so 'spread' is overstated; read
'captured', 'justified', 'favShare' and the per-action rewardMean instead.
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
import reward_search as rs

ARMS = {"cr_stock": {"credit": "stock"},
        "cr_post50": {"credit": "post", "credit_horizon": "50"},
        "cr_post200": {"credit": "post", "credit_horizon": "200"}}

if __name__ == "__main__":
    rs.compile_sources()
    jobs = []
    for jid, extra in ARMS.items():
        for seed in (0, 1, 2):
            t = dict(rs.BASE); t.update(rs.SCREENS["foryou100"]); t.update(extra)
            t.update({"w_fit": "1", "w_rec": "1", "recog_mix": "0.5", "recog_lambda": "2", "q_init": "20"})
            jobs.append({"id": jid, "tokens": t, "seed": seed})
    rows = rs.run_stage("credit_compare", jobs)
    for r in rows:
        print(r["key"], r["status"][:40], {k: (round(r[k], 3) if isinstance(r.get(k), float) else r.get(k)) for k in
              ("captured", "justified", "favShare", "medLead", "rec", "fit", "feed")}, r.get("rewardMean"), r.get("shares"))
    print("CREDIT_DONE")
