"""
2026-08-07 -- dose-response check on the M-tier-size hypothesis: does the mediator-regime effect size
scale with the Moderate hub tier's size? Two points already collected (both uniform population,
E-/P-/P+/E+ held at 10 each): M=20 (results/2026-08-07_lmp_feedmech_uniform_n30/) gave mediator mean
d=0.503; M=10 (results/2026-08-07_lmp_feedmech_uniform_hub_n30/) gave mediator mean d~0.15 (below the
0.3 regime-classification threshold). This run adds the M=15 midpoint (E-/P-/P+/E+ still 10 each,
N_HUB=10+10+15+10+10=55) to check whether the relationship is roughly monotonic/dose-response-like
across the three points, not just a two-point trend.

Reuses the existing uniform-init class-selection t0 snapshots (same follower-count ranking as the M=10
and M=20 runs -- ranking doesn't depend on hub allocation, only top-N and the split changes).

Usage: nohup python3 scripts/lmp_feedmech_uniform_hubM15_n30.py > logs/lmp_feedmech_uniform_hubM15_n30_stdout.log 2>&1 &
       (then disown)
"""
import csv
import random

from lmp_feedmech_stage1 import CELLS, cell_name, result_dir, launch, run_wave, build_pin_token, FULL_STEPS

SEEDS = [9990000 + i for i in range(30)]
CLASS_SELECT_SUBDIR = "2026-08-07_lmp_feedmech_uniform_n30/_class_selection_hk_uniform"
SUBDIR = "2026-08-07_lmp_feedmech_uniform_hubM15_n30"
UNIFORM_EXTRA = ["init_dist=uniform"]
ARMS = ("control", "N_silent")
N_TOP = 55


def derive_groups(seed):
    d = result_dir(seed, CLASS_SELECT_SUBDIR)
    ranked = []
    with open(d / "degrees" / "agent_snapshot_t0.csv", newline="") as f:
        for r in csv.DictReader(f):
            ranked.append((int(r["followerCount"]), int(r["agentId"])))
    ranked.sort(reverse=True)
    top_ids = [aid for _, aid in ranked[:N_TOP]]
    rng = random.Random(seed)
    rng.shuffle(top_ids)
    sizes = [("E_minus", 10, -1.0), ("P_minus", 10, -0.4), ("M", 15, 0.0),
             ("P_plus", 10, 0.4), ("E_plus", 10, 1.0)]
    groups = {}
    i = 0
    for name, size, target in sizes:
        groups[name] = (top_ids[i:i + size], target)
        i += size
    return groups


def main():
    print("=== Deriving hub-tier groups per seed (top-55, M=15, reusing existing t0 snapshots) ===",
          flush=True)
    groups_by_seed = {s: derive_groups(s) for s in SEEDS}

    print("\n=== Launching 8 cells x 2 arms x 30 seeds = 480 runs ===", flush=True)
    jobs = []
    for pu, vcr in CELLS:
        for s in SEEDS:
            groups = groups_by_seed[s]
            pin_token = build_pin_token(groups)
            m_ids = groups["M"][0]
            base = UNIFORM_EXTRA + [pin_token, f"p_u={pu}", f"vocal_comfort_radius={vcr}"]
            for arm in ARMS:
                tokens = list(base)
                if arm == "N_silent":
                    idstr = ",".join(str(a) for a in m_ids)
                    tokens += [f"silent_until_ids={idstr}", f"activation_step={FULL_STEPS + 1}"]
                jobs.append((s, FULL_STEPS, f"{SUBDIR}/{cell_name(pu, vcr)}/{arm}", tokens))
    run_wave(jobs, max_workers=20)
    print(f"\n=== Done. results/{SUBDIR}/ ready for analysis. ===", flush=True)


if __name__ == "__main__":
    main()
