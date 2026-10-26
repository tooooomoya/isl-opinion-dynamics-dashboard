#!/usr/bin/env python3
"""Feed-algorithm comparison with rewire ON and production cost ON (fixed from now on).
Usage: nohup python3 scripts/feed_compare.py [on|off [post_noise|nogate [random|sbm]]] > logs/feed_compare.out 2>&1 &   (rewire on by default; "off" = static network, ids fcoff_*; ends with FC_DONE)
Feeds: chrono 100 % (baseline) / For You 100 % (hop 5) / Trend 100 % (hop 5); 3 seeds each; 20,000 steps.
Common: bandit learner, Holme-Kim start network, rewire on, cost_post 0.5 / cost_reshare 0.25 / cost_rewire 1.0 (rewire dearest), notify_original 1 (reshares of my own posts join my candidate pool, exempt from the hop filter), rho_L=rho_R=0.3, beta_F 10,
w_fit = w_rec = 5, q_init 10, like only within |dx| <= 0.3, L = 200, tau 0.1. Outputs results/rsearch/fc_<feed>/ + summary.jsonl."""
import os, sys
os.environ.setdefault("SEARCH_PAR", "9")
sys.path.insert(0, os.path.dirname(__file__))
import reward_search as rs

COMMON = {"learner": "bandit", "q_init": "10", "rewire": "true", "cost_post": "0.5", "cost_reshare": "0.25", "cost_rewire": "1.0", "notify_original": "1",
          "rho_l": "0.3", "rho_r": "0.3", "fy_beta": "10", "w_fit": "5", "w_rec": "5", "recog_mix": "0.5", "recog_lambda": "2",
          "like_max_dist": "0.3"}
FEEDS = {"chrono": {"trend_share": "0", "foryou_share": "0"},
         "foryou": {"trend_share": "0", "foryou_share": "1.0", "foryou_hop": "5"},
         "trend": {"trend_share": "1.0", "trend_hop": "5", "foryou_share": "0"}}

if __name__ == "__main__":
    REW = sys.argv[1] if len(sys.argv) > 1 else "on"
    NOGATE = len(sys.argv) > 2 and sys.argv[2] == "nogate"   # rewire without the closer-than-oldest-followee check, ids fcng_*
    NOISE = sys.argv[2] if len(sys.argv) > 2 and not NOGATE else None   # e.g. 0.3: noisy posts (post_noise) + rewire judged by posts, ids fcn<sd>_*
    PFX = ("fc" if REW == "on" else "fcoff") if NOISE is None else f"fcn{NOISE}"
    NET = sys.argv[3] if len(sys.argv) > 3 else None   # start network other than Holme-Kim: random (p .015) or sbm (DC-SBM, mean degree 15)
    if NOGATE: PFX = "fcng" if NET is None else f"fcng_{NET}"
    rs.compile_sources()
    jobs = []
    for name, f in FEEDS.items():
        for seed in (0, 1, 2):
            t = dict(rs.BASE); t.update(COMMON); t.update(f); t["rewire"] = "true" if REW == "on" else "false"
            if NOISE is not None: t["post_noise"] = NOISE
            if NOGATE: t["rewire_gate"] = "false"
            if NET == "random": t["network"] = "random"
            if NET == "sbm": t.update({"network": "dcsbm", "sbm_deg": "15"})
            jobs.append({"id": f"{PFX}_{name}", "tokens": t, "seed": seed})
    rs.run_stage("feed_compare", jobs)
    print("FC_DONE")
