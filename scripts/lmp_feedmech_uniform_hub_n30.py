"""
2026-08-07 -- second robustness layer on top of lmp_feedmech_uniform_n30.py: uniform opinion-init
PLUS uniform hub-tier allocation. The existing hub-tier design (10 E-/10 P-/20 M/10 P+/10 E+, N_HUB=60)
was explicitly "bell-shaped, more weight toward moderate" per the 2026-08-04 design decision -- the same
Gaussian-concentration assumption now being tested on the population side. This uses an EQUAL split
instead: 10 each across all five categories, N_HUB=50 (user's spec, 2026-08-07).

Reuses the existing uniform-init class-selection t0 snapshots
(results/2026-08-07_lmp_feedmech_uniform_n30/_class_selection_hk_uniform/, seeds 9990000-9990029) --
follower-count ranking depends only on network topology at t0, not on how hubs are later assigned, so
no new class-selection dry run is needed, just a different top-N/split applied to the same ranking.

Usage: nohup python3 scripts/lmp_feedmech_uniform_hub_n30.py > logs/lmp_feedmech_uniform_hub_n30_stdout.log 2>&1 &
       (then disown)
"""
import csv
import random

from lmp_feedmech_stage1 import CELLS, cell_name, result_dir, launch, run_wave, build_pin_token, FULL_STEPS

SEEDS = [9990000 + i for i in range(30)]
CLASS_SELECT_SUBDIR = "2026-08-07_lmp_feedmech_uniform_n30/_class_selection_hk_uniform"
SUBDIR = "2026-08-07_lmp_feedmech_uniform_hub_n30"
UNIFORM_EXTRA = ["init_dist=uniform"]
ARMS = ("control", "N_silent")
N_TOP = 50


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
    sizes = [("E_minus", 10, -1.0), ("P_minus", 10, -0.4), ("M", 10, 0.0),
             ("P_plus", 10, 0.4), ("E_plus", 10, 1.0)]
    groups = {}
    i = 0
    for name, size, target in sizes:
        groups[name] = (top_ids[i:i + size], target)
        i += size
    return groups


def main():
    print("=== Deriving hub-tier groups per seed (top-50, 10 each, reusing existing t0 snapshots) ===",
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
