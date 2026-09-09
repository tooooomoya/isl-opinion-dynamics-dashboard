"""
2026-08-02 -- Light one-at-a-time (OAT) robustness check for the "moderate class continuously
active (B_always) raises extreme-camp per-capita posting rate and cross-cutting exposure vs class
permanently silent (A_never)" finding (see docs/report write-up of
delayed_moderate_conduit_pilot.py). Tests whether this is specific to the single v15-calibration
HK point, or holds across a light perturbation of the two parameters most directly implicated in
the established mechanism (p_u = the paper's own phase knob; vocal_comfort_radius = the exact
threshold gating the postProb-driving comfort-rate channel), plus one different network-generator
family (DC-SBM) at matched t0 mean degree (HK's own t0 mean in-degree measured at exactly 15.0
across all 5 baseline seeds -- sbm_deg set to 15, not its default 50, so the comparison is about
topology SHAPE, not shape+density).

n=5, seeds 7300000-7300004 (same seeds as the existing baseline, for paired comparison). The
p_u/vocal_comfort_radius arms REUSE the existing HK class-ID lists (network generation and initial
opinion assignment happen before any per-step dynamics, so t0 topology + class selection is
identical regardless of p_u/vcr) -- only the network=dcsbm arm needs a fresh class-selection dry
run. Baseline points (p_u=0.05, vcr=0.1, network=hk) are NOT re-run -- reused from the existing
n=15 pilot (first 5 seeds).

Usage: nohup python3 scripts/delayed_moderate_pilot_robustness.py > logs/delayed_moderate_pilot_robustness_stdout.log 2>&1 &
       (then disown)
"""
import concurrent.futures
import csv
import subprocess
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
_JARS = list(ROOT.glob("lib/**/*.jar"))
LIBCP = ":".join(str(p) for p in _JARS) + (":" if _JARS else "") + str(ROOT / "bin")

N = 1000
FULL_STEPS = 40000
SEEDS = [7300000 + i for i in range(5)]
TOPK_MODERATE = 20
MODERATE_THRESHOLD = 0.2
SUBDIR = "2026-08-02_delayed-moderate-pilot"
ROBUST_SUBDIR = f"{SUBDIR}/robustness"
ARMS = ["A_never", "B_always"]

CLASS_IDS_HK = {
    7300000: [1, 15, 5, 2, 12, 22, 17, 35, 39, 30, 37, 44, 21, 26, 85, 29, 64, 157, 114, 83],
    7300001: [8, 14, 1, 7, 11, 15, 2, 31, 20, 46, 27, 37, 54, 34, 22, 50, 49, 44, 77, 45],
    7300002: [6, 41, 35, 21, 19, 25, 68, 67, 59, 48, 56, 169, 45, 137, 94, 80, 86, 104, 148, 123],
    7300003: [1, 4, 12, 15, 13, 19, 27, 50, 22, 29, 44, 21, 57, 73, 71, 114, 74, 30, 48, 112],
    7300004: [2, 0, 7, 1, 19, 23, 18, 34, 27, 42, 22, 41, 46, 47, 16, 51, 99, 32, 40, 135],
}

BASE_TOKENS = [
    "network=hk", "hk_m=15", "hk_a=4", "hk_pt=0.05",
    "max_follow=43.8638", "follow_prob=0.01", "feed_capacity=15",
    "access_prob=0.1", "p_u=0.05",
    "bc_dec=0.500000", "bc_recovery=0.000100", "bc_floor=0.2", "bc_ceiling=1.0", "bc_init=0.800000",
    "vocal_comfort_radius=0.1", "repost_prob=0.1", "relay_enabled=false",
    "out_of_bc_repost_prob=0.01", "rel_attrib=original",
    "stub_dist=uniform", "stub_min=0.82", "stub_max=0.82",
    "evict_beta=-1", "init_prune=trim",
    "initial_pp=0.25537", "max_pp=1.0", "min_pp=0.01", "pp_relax_eta=0.100000",
    "moderate_band=0.2",
    "extreme=none", "n_mod=0", "alpha=0",
]

# Each entry: (config_name, override_tokens, needs_fresh_class_selection)
CONFIGS = [
    ("pu_001", ["p_u=0.01"], False),
    ("pu_015", ["p_u=0.15"], False),
    ("vcr_005", ["vocal_comfort_radius=0.05"], False),
    ("vcr_02", ["vocal_comfort_radius=0.2"], False),
    ("dcsbm", ["network=dcsbm", "sbm_k=4", "sbm_pin=0.08", "sbm_pout=0.002", "sbm_gamma=2.3", "sbm_deg=15"], True),
]


def result_dir(seed, subdir):
    candidates = sorted(ROOT.glob(f"results/{subdir}/run_{seed}_*"), key=lambda p: p.stat().st_mtime)
    return candidates[-1] if candidates else None


def is_done(seed, subdir, steps):
    d = result_dir(seed, subdir)
    if d is None:
        return False
    rp = d / "metrics" / "results.csv"
    if not rp.exists():
        return False
    with open(rp, newline="") as f:
        rows = list(csv.DictReader(f))
    return bool(rows) and int(rows[-1]["step"]) >= steps


def launch(seed, steps, subdir, override_tokens, extra_tokens, log_gexf=False):
    tokens = [f"seed={seed}", f"steps={steps}", f"n={N}", "force=true",
              f"log_gexf={str(log_gexf).lower()}", f"results_subdir={subdir}"] \
        + BASE_TOKENS + override_tokens + extra_tokens
    logfile = ROOT / "logs" / f"delaymodrob_seed{seed}_{subdir.split('/')[-1]}.log"
    logfile.parent.mkdir(exist_ok=True)
    with open(logfile, "w") as lf:
        p = subprocess.Popen(["java", "-Xmx2g", "-cp", LIBCP, "dynamics.OpinionDynamics", *tokens],
                              stdout=lf, stderr=subprocess.STDOUT, cwd=ROOT)
    return p


def run_wave(jobs, max_workers=20):
    """jobs: list of (seed, steps, subdir, override_tokens, extra_tokens)."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = []
        for seed, steps, subdir, ov, tk in jobs:
            if is_done(seed, subdir, steps):
                print(f"  seed={seed} subdir={subdir}: reusing existing", flush=True)
                continue
            futs.append(ex.submit(lambda s=seed, st=steps, sd=subdir, o=ov, t=tk: launch(s, st, sd, o, t).wait()))
        for f in futs:
            f.result()


def derive_class_ids(seed, subdir):
    d = result_dir(seed, subdir)
    ranked = []
    with open(d / "degrees" / "agent_snapshot_t0.csv", newline="") as f:
        for r in csv.DictReader(f):
            if abs(float(r["intrinsicOpinion"])) < MODERATE_THRESHOLD:
                ranked.append((int(r["followerCount"]), int(r["agentId"])))
    ranked.sort(reverse=True)
    return [aid for _, aid in ranked[:TOPK_MODERATE]]


def read_metrics_at(seed, subdir, checkpoint):
    d = result_dir(seed, subdir)
    with open(d / "metrics" / "results.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    at = next(r for r in reversed(rows) if int(r["step"]) == checkpoint)
    opinion_var = float(at["opinionVar"])
    post_opinion_var = float(at["postOpinionVar"])
    sf1 = post_opinion_var / opinion_var if opinion_var > 0 else None
    return dict(sf1_ratio=sf1, opinionAssortativity=float(at["opinionAssortativity"]),
                crossCuttingFraction=float(at["crossCuttingFraction"]))


def population_counts(seed, subdir):
    d = result_dir(seed, subdir)
    df_path = d / "degrees" / "agent_snapshot_final.csv"
    counts = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0}
    import csv as _csv
    with open(df_path, newline="") as f:
        for r in _csv.DictReader(f):
            shifted = float(r["opinion"]) + 1.0
            cls = min(int(shifted / 0.4), 4)
            counts[cls] += 1
    return counts


def extreme_percapita_rate(seed, subdir, checkpoint, window=2000):
    d = result_dir(seed, subdir)
    with open(d / "metrics" / "results.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    lo = checkpoint - window
    wrows = [r for r in rows if lo < int(r["step"]) <= checkpoint]
    total_posts = 0.0
    for r in wrows:
        total = float(r["originalPostCount"]) + float(r["repostCount"])
        total_posts += (float(r["postShare_0"]) + float(r["postShare_4"])) * total
    pop = population_counts(seed, subdir)
    ext_pop = pop[0] + pop[4]
    return total_posts / ext_pop / window if ext_pop > 0 else float("nan")


def main():
    print("=== Class selection for dcsbm (fresh dry run needed) ===", flush=True)
    dcsbm_ov = next(ov for name, ov, fresh in CONFIGS if name == "dcsbm")
    run_wave([(s, 0, f"{ROBUST_SUBDIR}/dcsbm/_class_selection", dcsbm_ov, []) for s in SEEDS],
             max_workers=len(SEEDS))
    dcsbm_class_ids = {s: derive_class_ids(s, f"{ROBUST_SUBDIR}/dcsbm/_class_selection") for s in SEEDS}
    for s in SEEDS:
        print(f"  seed={s}: dcsbm class -> {dcsbm_class_ids[s]}", flush=True)

    print("\n=== Phase 2: robustness runs ===", flush=True)
    jobs = []
    for name, override, fresh in CONFIGS:
        ids_by_seed = dcsbm_class_ids if fresh else CLASS_IDS_HK
        for s in SEEDS:
            idstr = ",".join(str(a) for a in ids_by_seed[s])
            for arm in ARMS:
                tokens = [f"pin_moderate_ids={idstr}"]
                if arm == "A_never":
                    tokens += [f"silent_until_ids={idstr}", f"activation_step={FULL_STEPS + 1}"]
                jobs.append((s, FULL_STEPS, f"{ROBUST_SUBDIR}/{name}/{arm}", override, tokens))
    run_wave(jobs, max_workers=20)

    print("\n=== Results: paired A_never vs B_always, n=5, final checkpoint, per config ===", flush=True)
    # baseline (p_u=0.05, vcr=0.1, network=hk) reused from the main pilot subdir, not ROBUST_SUBDIR
    all_configs = [("baseline_hk_pu05_vcr01", SUBDIR)] + [(name, f"{ROBUST_SUBDIR}/{name}") for name, _, _ in CONFIGS]
    for name, base_subdir in all_configs:
        print(f"\n### config={name} ###")
        A = [read_metrics_at(s, f"{base_subdir}/A_never", FULL_STEPS) for s in SEEDS]
        B = [read_metrics_at(s, f"{base_subdir}/B_always", FULL_STEPS) for s in SEEDS]
        ea = [extreme_percapita_rate(s, f"{base_subdir}/A_never", FULL_STEPS) for s in SEEDS]
        eb = [extreme_percapita_rate(s, f"{base_subdir}/B_always", FULL_STEPS) for s in SEEDS]
        for k in ["opinionAssortativity", "crossCuttingFraction"]:
            a = np.array([x[k] for x in A]); b = np.array([x[k] for x in B])
            diff = b - a
            t = diff.mean()/(diff.std(ddof=1)/np.sqrt(len(diff))) if diff.std(ddof=1) > 0 else float("nan")
            print(f"  {k:>22}: A={a.mean():.4f}+/-{a.std():.4f}  B={b.mean():.4f}+/-{b.std():.4f}  diff={diff.mean():+.4f}  t={t:.2f}")
        ea, eb = np.array(ea), np.array(eb)
        diff = eb - ea
        t = diff.mean()/(diff.std(ddof=1)/np.sqrt(len(diff))) if diff.std(ddof=1) > 0 else float("nan")
        pct = 100*diff.mean()/ea.mean() if ea.mean() else float("nan")
        print(f"  {'extreme_percapita_rate':>22}: A={ea.mean():.4f}+/-{ea.std():.4f}  B={eb.mean():.4f}+/-{eb.std():.4f}  diff={diff.mean():+.4f} ({pct:+.1f}%)  t={t:.2f}")


if __name__ == "__main__":
    main()
