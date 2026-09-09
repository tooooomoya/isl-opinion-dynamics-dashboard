"""
2026-08-25 -- two follow-up probes on the extreme camp's posting-rate/comfort-rate effect, motivated
by a Results-section discussion of CNA2026-5th.tex's outcome-heatmap (paired Cohen's d_z) figure:

(1) "extreme = |opinion|>=0.8" probe: does narrowing the extreme-camp definition from the paper's
    |opinion|>=0.6 (Agent.opinionClass bin0/bin4 boundary, which also drives feed/comfort dynamics)
    to |opinion|>=0.8 (motivated by a visual break around there in network-layout figures) make the
    control-vs-N_silent effect bigger in absolute terms? Uses the new Const.band08Of/cRateMean08_*/
    band08_* columns (analysis-only reclassification of the SAME simulated dynamics -- opinionClass
    and everything it drives is untouched, so this is not a re-run of the model with a different
    boundary, just a different way of counting the same runs' outputs).

(2) step-extension probe: does the effect keep growing past the paper's t=40,000 cutoff, consistent
    with the follow-network erosion mechanism (control-arm followeeCount still diverging from
    N_silent at t=40,000, docs/report/2026-08-25-third-channel-owncamp-decomposition.md) not having
    plateaued yet? Doubles steps to 80,000, same trailing window WIDTH (2000 steps) at the new tail.

Both restricted to the 4 low-VCR (vcr=0.10) cells across the paper's P_u grid -- the facilitating
regime where the extreme-camp effect is largest and most novel (per this session's discussion),
confirmed with the user before launching (2026-08-25 AskUserQuestion).

Fresh results_subdir (does not touch/require re-running the existing 94GB
results/2026-08-14_lmp_feedmech_structural_9b/ grid) -- new band08 columns don't exist in that data.

Usage: nohup python3 -u scripts/lmp_band08_probe.py > logs/lmp_band08_probe_stdout.log 2>&1 &
       (then disown)
"""
import concurrent.futures

from lmp_feedmech_stage1 import SEEDS, WINDOW, derive_groups, build_pin_token, launch, is_done

PU_LEVELS = (0.05, 0.08, 0.11, 0.15)
VCR = 0.10
STEP_CONFIGS = {"steps40k": 40000, "steps80k": 80000}
SUBDIR_ROOT = "2026-08-25_lmp_band08_probe"
ARMS = ("control", "N_silent")


def cell_name(pu, vcr):
    return f"pu{pu}_vcr{vcr}"


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
    print("=== Deriving hub-tier groups (reused shared HK class-selection) ===", flush=True)
    groups_by_seed = {s: derive_groups(s) for s in SEEDS}

    jobs = []
    for label, steps in STEP_CONFIGS.items():
        for pu in PU_LEVELS:
            for s in SEEDS:
                groups = groups_by_seed[s]
                pin_token = build_pin_token(groups)
                base = [pin_token, f"p_u={pu}", f"vocal_comfort_radius={VCR}"]
                c_sub = f"{SUBDIR_ROOT}/{label}/{cell_name(pu, VCR)}/control"
                jobs.append((s, steps, c_sub, base))
                m_ids = groups["M"][0]
                idstr = ",".join(str(a) for a in m_ids)
                msil_tokens = base + [f"silent_until_ids={idstr}", f"activation_step={steps + 1}"]
                m_sub = f"{SUBDIR_ROOT}/{label}/{cell_name(pu, VCR)}/N_silent"
                jobs.append((s, steps, m_sub, msil_tokens))

    print(f"\n=== Launching {len(jobs)} total runs "
          f"({len(PU_LEVELS)} pu x {len(STEP_CONFIGS)} step-configs x {len(ARMS)} arms x {len(SEEDS)} seeds) ===",
          flush=True)
    run_wave(jobs, max_workers=20)
    print("\n=== BAND08 PROBE RUNS COMPLETE ===", flush=True)


if __name__ == "__main__":
    main()
