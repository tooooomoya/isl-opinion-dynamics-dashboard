"""
2026-08-07 -- robustness check: does the two-level homophily-gate mechanism (validated 2026-08-06,
re-audited 2026-08-07) survive under a UNIFORM initial-opinion distribution instead of the truncated
Gaussian used everywhere else in this pilot? Motivation (user, 2026-08-07): the Gaussian concentrates
mass near the center, producing uneven opinion-class population sizes (echo_chamber_by_class nodeCount
was 17+50+55+55+17 in an earlier smoke test) -- for a mechanism-focused CN2026 paper, a flatter
initial distribution may be a cleaner substrate and is worth checking doesn't change the qualitative
result. Requires `init_dist=uniform` (new: Agent.java, 2026-08-07, `intrinsicOpinion ~ U[-1,1]`,
compiled and smoke-tested -- t0 snapshot confirmed near-uniform, quartile counts [49,56,54,41] at n=200).

Same 8-cell design as lmp_feedmech_stage1.py (p_u in {0.05, 0.15} x vcr in {0.1, 0.15, 0.2, 0.3}),
control vs N_silent, but a FRESH n=30 seed block (9990000-9990029, not reused from the Gaussian runs --
n=30 directly, per user request, not the usual n=15-screen-then-extend pattern) and a fresh hub-tier
class-selection pass (the existing `_shared/class_selection_hk` snapshots were built under Gaussian
init and cannot be reused: opinion sampling consumes a variable number of RNG draws under Gaussian
(rejection sampling) vs exactly one under uniform, so the same seed number can yield a DIFFERENT
network/follower-count ranking between the two -- reusing the Gaussian ranking would silently pin the
"wrong" top-60 agents under uniform init for the same seed).

Usage: nohup python3 scripts/lmp_feedmech_uniform_n30.py > logs/lmp_feedmech_uniform_n30_stdout.log 2>&1 &
       (then disown)
"""
import csv
import random

from lmp_feedmech_stage1 import (
    CELLS, cell_name, result_dir, is_done, launch, run_wave, build_pin_token,
    FULL_STEPS,
)

# NOTE: launch() (imported above) already prepends lmp_feedmech_stage1.BASE_TOKENS internally --
# do NOT include BASE_TOKENS again here, only the tokens ADDITIONAL to that default set.
SEEDS = [9990000 + i for i in range(30)]
SUBDIR = "2026-08-07_lmp_feedmech_uniform_n30"
CLASS_SELECT_SUBDIR = f"{SUBDIR}/_class_selection_hk_uniform"
UNIFORM_EXTRA = ["init_dist=uniform"]
ARMS = ("control", "N_silent")


def derive_groups(seed):
    d = result_dir(seed, CLASS_SELECT_SUBDIR)
    ranked = []
    with open(d / "degrees" / "agent_snapshot_t0.csv", newline="") as f:
        for r in csv.DictReader(f):
            ranked.append((int(r["followerCount"]), int(r["agentId"])))
    ranked.sort(reverse=True)
    top_ids = [aid for _, aid in ranked[:60]]
    rng = random.Random(seed)
    rng.shuffle(top_ids)
    sizes = [("E_minus", 10, -1.0), ("P_minus", 10, -0.4), ("M", 20, 0.0),
             ("P_plus", 10, 0.4), ("E_plus", 10, 1.0)]
    groups = {}
    i = 0
    for name, size, target in sizes:
        groups[name] = (top_ids[i:i + size], target)
        i += size
    return groups


def main():
    print(f"=== Phase 1: class-selection dry runs (uniform init, n={len(SEEDS)}) ===", flush=True)
    run_wave([(s, 0, CLASS_SELECT_SUBDIR, UNIFORM_EXTRA) for s in SEEDS], max_workers=len(SEEDS))

    print("\n=== Deriving hub-tier groups per seed ===", flush=True)
    groups_by_seed = {s: derive_groups(s) for s in SEEDS}

    print("\n=== Phase 2: launching 8 cells x 2 arms x 30 seeds = 480 runs ===", flush=True)
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
    print("\n=== Done. Run scripts/lmp_feedmech_interaction_anova.py-style analysis against"
          f" results/{SUBDIR}/ next. ===", flush=True)


if __name__ == "__main__":
    main()
