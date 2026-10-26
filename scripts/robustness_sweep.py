#!/usr/bin/env python3
"""Robustness check of the standing configuration (docs/report/2026-10-26-robustness-sweep-plan.md).
Stage 1: one-at-a-time (OAT) screen, Holme-Kim start, Chrono / For You / Trend (100 % each), seeds 0-2 (common random numbers across settings).
Usage: nohup python3 scripts/robustness_sweep.py [net] > logs/robustness_stage1.out 2>&1 & disown   (resumable via results/rsearch/summary.jsonl)
Run ids: rob_<param>_<level>_<net>_<feed>; the unchanged baseline is rob_base_<net>_<feed> (rerun under the same compiled code)."""
import os, sys
os.environ.setdefault("SEARCH_PAR", "12")
sys.path.insert(0, os.path.dirname(__file__))
import reward_search as rs
from standard_run import COMMON, FEEDS, NETS

SEEDS = [0, 1, 2]

def scale_costs(f):
    return {"cost_post": str(0.5 * f), "cost_reshare": str(0.25 * f), "cost_rewire": str(1.0 * f)}

# (param label, level label, token overrides); the baseline level of each parameter is omitted (it is rob_base)
SETTINGS = [
    ("qtau", "0.05", {"q_tau": "0.05"}), ("qtau", "0.3", {"q_tau": "0.3"}), ("qtau", "1.0", {"q_tau": "1.0"}),
    ("qeta", "0.03", {"q_eta": "0.03"}), ("qeta", "0.3", {"q_eta": "0.3"}),
    ("qeps", "0", {"q_eps": "0"}), ("qeps", "0.2", {"q_eps": "0.2"}),
    ("qinit", "0", {"q_init": "0"}), ("qinit", "5", {"q_init": "5"}), ("qinit", "20", {"q_init": "20"}),
    ("learner", "q", {"learner": "q", "q_gamma": "0.9"}),
    ("wratio", "2-8", {"w_fit": "2", "w_rec": "8"}), ("wratio", "8-2", {"w_fit": "8", "w_rec": "2"}),
    ("recog", "mix0-lam0.5", {"recog_mix": "0", "recog_lambda": "0.5"}), ("recog", "mix1-lam5", {"recog_mix": "1", "recog_lambda": "5"}),
    ("cost", "x0", scale_costs(0)), ("cost", "x0.5", scale_costs(0.5)), ("cost", "x2", scale_costs(2)),
    ("fitmode", "raw", {"fit_mode": "raw"}),
    ("cap", "5", {"feed_capacity": "5"}), ("cap", "20", {"feed_capacity": "20"}),
    ("access", "0.05", {"access_prob": "0.05"}), ("access", "0.2", {"access_prob": "0.2"}),
    ("fybeta", "3", {"fy_beta": "3"}), ("fybeta", "30", {"fy_beta": "30"}),
    ("hop", "2", {"foryou_hop": "2", "trend_hop": "2"}), ("hop", "10", {"foryou_hop": "10", "trend_hop": "10"}),
    ("hoplam", "0", {"foryou_hop_lambda": "0"}), ("hoplam", "1.5", {"foryou_hop_lambda": "1.5"}),
    ("candmax", "100", {"foryou_cand_max": "100"}), ("candmax", "0", {"foryou_cand_max": "0"}),
    ("rho", "0.1", {"rho_l": "0.1", "rho_r": "0.1"}), ("rho", "0.5", {"rho_l": "0.5", "rho_r": "0.5"}),
    ("dead", "50", {"dead_after": "50"}), ("dead", "100", {"dead_after": "100"}), ("dead", "400", {"dead_after": "400"}),
    ("likedist", "0.3", {"like_max_dist": "0.3"}), ("likedist", "0.6", {"like_max_dist": "0.6"}),
    ("notify", "0", {"notify_original": "0"}),
    ("rewire", "off", {"rewire": "false"}), ("rewire", "gated", {"rewire_gate": "true"}),
    ("postnoise", "0.1", {"post_noise": "0.1"}), ("postnoise", "0.3", {"post_noise": "0.3"}),
    ("startdeg", "8", {"hk_m": "8", "start_deg": "8"}), ("startdeg", "30", {"hk_m": "30", "start_deg": "30"}),
    ("hka", "15", {"hk_a": "15"}), ("hka", "60", {"hk_a": "60"}),
    ("n", "500", {"n": "500"}), ("n", "2000", {"n": "2000"}),
    ("steps", "10000", {"steps": "10000"}), ("steps", "40000", {"steps": "40000"}),
]

def build(net, seeds=SEEDS):
    jobs = []
    for param, level, ov in [("base", "0", {})] + SETTINGS:
        for feed, f in FEEDS.items():
            t = dict(rs.BASE); t.update(COMMON); t.update(f); t.update(NETS[net]); t.update(ov)
            if "foryou_hop" in ov and feed == "trend": pass          # trend_hop override already in ov; foryou_hop is ignored by Trend
            for s in seeds:
                jobs.append({"id": f"rob_{param}_{level}_{net}_{feed}", "tokens": t, "seed": s})
    # long jobs first so the pool does not end on a single Trend/n=2000 run
    jobs.sort(key=lambda j: -(("trend" in j["id"]) * 2 + ("foryou" in j["id"])) - ("_n_2000" in j["id"]) * 4 - ("_steps_40000" in j["id"]) * 4)
    return jobs

if __name__ == "__main__":
    net = sys.argv[1] if len(sys.argv) > 1 else "hk"
    rs.compile_sources()
    jobs = build(net)
    import shutil
    done = rs.load_summary()
    for jid in {j["id"] for j in jobs}:      # a failed earlier attempt would leave a second run_* dir that summarize() could pick up
        if any(f"{jid}__s{s}" not in done or done[f"{jid}__s{s}"]["status"] != "ok" for s in SEEDS):
            shutil.rmtree(os.path.join(rs.OUT, jid), ignore_errors=True)
    rs.run_stage(f"robustness_stage1_{net}", jobs)
    print("ROB_DONE")
