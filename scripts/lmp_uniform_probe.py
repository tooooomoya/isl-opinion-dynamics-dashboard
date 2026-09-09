"""
2026-08-25 -- light robustness check: does a uniform initial-opinion distribution (instead of the
paper's truncated-Gaussian) change the extreme camp's posting-rate/comfort-rate/raw-count effect,
now that today's session established those are the smallest-magnitude effects in the current
CNA2026-5th 4x4 grid? A prior robustness sweep (2026-08-07, docs/report/2026-08-02-delayed-moderate-
conduit-pilot.md) already tested uniform-population under the OLD 8-cell/M=20-hub grid and found the
facilitator effect's Cohen's d essentially unchanged (0.972 Gaussian -> 0.997 uniform) but only
measured standardized effect size, never raw post counts, and not on the current grid/hub design.

Per user instruction: match BOTH the population shape (init_dist=uniform, intrinsicOpinion~U[-1,1],
already implemented in Agent.java) AND the hub-tier allocation to uniform -- the current default hub
split is M-heavy (E-/P-/M/P+/E+ = 10/10/20/10/10, N_HUB=60); this script uses the equal split
(10/10/10/10/10, N_HUB=50, M=10) that 2026-08-07's Batch 2 used, instead of reusing derive_groups()'s
M=20 split.

Scope (confirmed with user, light/exploratory): the same 4 low-VCR cells (P_u in
{0.05,0.08,0.11,0.15}, VCR=0.10) used in today's band08 probe, 40,000 steps, 5 seeds
(8900000-8900004) instead of the paper's 15 -- 40 runs total.

Reuses the same shared HK_CLASS_SELECT_SUBDIR follower-ranking snapshot as every other script in
this project (network topology is generated independently of opinion distribution/hub allocation,
so no fresh topology run is needed -- see lmp_feedmech_stage1.derive_groups and the 2026-08-02
report's note that this ranking doesn't need re-deriving for hub-size variants).

Usage: nohup python3 -u scripts/lmp_uniform_probe.py > logs/lmp_uniform_probe_stdout.log 2>&1 &
       (then disown)
"""
import concurrent.futures
import csv
import random

from lmp_feedmech_stage1 import (
    HK_CLASS_SELECT_SUBDIR, result_dir, build_pin_token, launch, is_done,
)

SEEDS = [8900000 + i for i in range(5)]
PU_LEVELS = (0.05, 0.08, 0.11, 0.15)
VCR = 0.10
STEPS = 40000
SUBDIR = "2026-08-25_lmp_uniform_probe"
ARMS = ("control", "N_silent")


def cell_name(pu, vcr):
    return f"pu{pu}_vcr{vcr}"


def derive_groups_uniform_hub(seed):
    """Same top-N-by-followerCount selection as derive_groups(), but N_HUB=50 with an equal
    10/10/10/10/10 split (2026-08-07 Batch 2's 'uniform hub split') instead of the default
    10/10/20/10/10 (M-heavy, N_HUB=60)."""
    d = result_dir(seed, HK_CLASS_SELECT_SUBDIR)
    ranked = []
    with open(d / "degrees" / "agent_snapshot_t0.csv", newline="") as f:
        for r in csv.DictReader(f):
            ranked.append((int(r["followerCount"]), int(r["agentId"])))
    ranked.sort(reverse=True)
    top_ids = [aid for _, aid in ranked[:50]]
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


def run_wave(jobs, max_workers=20):
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = []
        for seed, steps, subdir, tokens in jobs:
            if is_done(seed, subdir, steps):
                print(f"  seed={seed} subdir={subdir}: reusing existing", flush=True)
                continue
            futs.append(ex.submit(lambda s=seed, st=steps, sd=subdir, tk=tokens: launch(s, st, sd, tk).wait()))
        print(f"  {len(futs)} runs launching (rest already done)...", flush=True)
        for f in futs:
            f.result()


def main():
    print("=== Deriving UNIFORM hub-tier groups (10/10/10/10/10, N_HUB=50) ===", flush=True)
    groups_by_seed = {s: derive_groups_uniform_hub(s) for s in SEEDS}

    jobs = []
    for pu in PU_LEVELS:
        for s in SEEDS:
            groups = groups_by_seed[s]
            pin_token = build_pin_token(groups)
            base = [pin_token, f"p_u={pu}", f"vocal_comfort_radius={VCR}", "init_dist=uniform"]
            c_sub = f"{SUBDIR}/{cell_name(pu, VCR)}/control"
            jobs.append((s, STEPS, c_sub, base))
            m_ids = groups["M"][0]
            idstr = ",".join(str(a) for a in m_ids)
            msil_tokens = base + [f"silent_until_ids={idstr}", f"activation_step={STEPS + 1}"]
            m_sub = f"{SUBDIR}/{cell_name(pu, VCR)}/N_silent"
            jobs.append((s, STEPS, m_sub, msil_tokens))

    print(f"\n=== Launching {len(jobs)} total runs "
          f"({len(PU_LEVELS)} pu x {len(ARMS)} arms x {len(SEEDS)} seeds) ===", flush=True)
    run_wave(jobs, max_workers=20)
    print("\n=== UNIFORM PROBE RUNS COMPLETE ===", flush=True)


if __name__ == "__main__":
    main()
