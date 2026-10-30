#!/usr/bin/env python3
"""Standing configuration on one start network: Chrono / For You (hop 5) / Trend 100 %, 10 seeds, 20,000 steps.
Usage: nohup python3 scripts/standard_run.py hk|random|sbm|ws|hkshuf > logs/std_<net>.out 2>&1 &   (resumable; ids baseline_<net>_<feed>)
Standing config: dead_after L = 50 (since 2026-10-27; 200 before), bandit, rewire ON without the similarity gate, costs post .5 / reshare .25 / rewire 1.0, likes on a reshare go to the resharer only (the original's life is refreshed),
reshares join the original author's pool, rho_L = rho_R = .3, beta_F 10, w_fit = w_rec = 5, a like whose drawn post is farther than |dx| = 1.0 does nothing (gated like),
For You score = similarity x exp(-0.5 (hop-1)); candidate sample capped at 300 per feed and network-wide step metrics recomputed every 25 steps (both for speed).
Since 2026-10-29, identity reward is raw mean feed similarity, with the same zero baseline for every opinion. Historical baseline outputs use relative fit; use a new result namespace."""
import os, sys
os.environ.setdefault("SEARCH_PAR", "12")
sys.path.insert(0, os.path.dirname(__file__))
import reward_search as rs

COMMON = {"learner": "bandit", "q_init": "10", "rewire": "true", "rewire_gate": "false", "cost_post": "0.5", "cost_reshare": "0.25",
          "cost_rewire": "1.0", "notify_original": "1", "rho_l": "0.3", "rho_r": "0.3", "fy_beta": "10",
          "w_fit": "5", "w_rec": "5", "recog_mix": "0.5", "recog_lambda": "2", "like_max_dist": "1.0", "like_gate": "noop",
          "foryou_hop_lambda": "0.5", "foryou_cand_max": "300", "metrics_heavy_every": "25", "fit_mode": "raw",
          "trend_count": "both", "trend_tie": "random", "dead_after": "50"}   # Trend ranking fix (2026-10-26): likes count in the velocity, equal scores in random order; no effect on Chrono / For You
FEEDS = {"chrono": {"trend_share": "0", "foryou_share": "0"},
         "foryou": {"trend_share": "0", "foryou_share": "1.0", "foryou_hop": "5"},
         "trend": {"trend_share": "1.0", "trend_hop": "5", "foryou_share": "0"}}
NETS = {"hk": {}, "random": {"network": "random", "start_deg": "15"}, "sbm": {"network": "dcsbm", "sbm_deg": "15", "start_deg": "15"},
        "ws": {"network": "ws", "ws_out": "15", "ws_beta": "0.1", "start_deg": "15"},
        "hkshuf": {"network": "hkshuf", "hk_a": "4"}}   # HK degree sequence (m 15, A 4), wiring randomized: heavy tail without the age-ordered acyclic structure (docs/report/2026-10-26-network-dial.md)   # all four start with exactly 15,000 directed edges (mean degree 15)

if __name__ == "__main__":
    net = sys.argv[1]
    rs.compile_sources()
    jobs = []
    for name, f in FEEDS.items():
        for seed in range(10):
            t = dict(rs.BASE); t.update(COMMON); t.update(f); t.update(NETS[net])
            jobs.append({"id": f"baseline_raw_{net}_{name}", "tokens": t, "seed": seed})
    rs.run_stage(f"standard_raw_{net}", jobs)
    print("STD_DONE")
