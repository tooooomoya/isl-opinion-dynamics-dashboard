"""
2026-08-03 -- Light robustness check on the CLASS-SELECTION CRITERION itself (not the dynamics
parameters, which were already OAT-swept in delayed_moderate_pilot_robustness.py). The
"moderate class" targeted by the delayed-conduit-entry intervention is currently defined as: the
top TOPK_MODERATE=20 agents by t0 followerCount among agents with |intrinsicOpinion| < 0.2. Both
constants (20, 0.2) were picked without their own sensitivity check. This script re-derives the
class ID list from the SAME already-existing t0 network snapshots (class selection depends only on
t0 followerCount + intrinsicOpinion, both fixed before any per-step dynamics run -- so no fresh
class-selection dry run is needed, unlike the network=dcsbm arm in the dynamics-parameter sweep)
under 4 alternative (top_k, threshold) pairs, and re-runs the A_never/B_always contrast for each.

n=5, seeds 7300000-7300004 (same as the existing baseline/robustness batches, paired comparison).
Baseline (top_k=20, threshold=0.2) is NOT re-run -- reused from the main pilot subdir.

Usage: nohup python3 scripts/delayed_moderate_pilot_robustness_classdef.py > logs/delayed_moderate_pilot_robustness_classdef_stdout.log 2>&1 &
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
SUBDIR = "2026-08-02_delayed-moderate-pilot"
CLASS_SELECT_SUBDIR = f"{SUBDIR}/_class_selection"  # reused, already exists for these 5 seeds
ROBUST_SUBDIR = "2026-08-02_delayed-moderate-pilot/robustness/classdef"
ARMS = ["A_never", "B_always"]

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

# (config_name, top_k, threshold) -- baseline is top_k=20, threshold=0.2 (reused from main pilot)
CONFIGS = [
    ("topk10", 10, 0.2),
    ("topk40", 40, 0.2),
    ("thresh01", 20, 0.1),
    ("thresh03", 20, 0.3),
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


def launch(seed, steps, subdir, extra_tokens, log_gexf=False):
    tokens = [f"seed={seed}", f"steps={steps}", f"n={N}", "force=true",
              f"log_gexf={str(log_gexf).lower()}", f"results_subdir={subdir}"] \
        + BASE_TOKENS + extra_tokens
    logfile = ROOT / "logs" / f"delaymodclassdef_seed{seed}_{subdir.split('/')[-1]}.log"
    logfile.parent.mkdir(exist_ok=True)
    with open(logfile, "w") as lf:
        p = subprocess.Popen(["java", "-Xmx2g", "-cp", LIBCP, "dynamics.OpinionDynamics", *tokens],
                              stdout=lf, stderr=subprocess.STDOUT, cwd=ROOT)
    return p


def run_wave(jobs, max_workers=20):
    """jobs: list of (seed, steps, subdir, extra_tokens)."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = []
        for seed, steps, subdir, tk in jobs:
            if is_done(seed, subdir, steps):
                print(f"  seed={seed} subdir={subdir}: reusing existing", flush=True)
                continue
            futs.append(ex.submit(lambda s=seed, st=steps, sd=subdir, t=tk: launch(s, st, sd, t).wait()))
        for f in futs:
            f.result()


def derive_class_ids(seed, top_k, threshold):
    d = result_dir(seed, CLASS_SELECT_SUBDIR)
    ranked = []
    with open(d / "degrees" / "agent_snapshot_t0.csv", newline="") as f:
        for r in csv.DictReader(f):
            if abs(float(r["intrinsicOpinion"])) < threshold:
                ranked.append((int(r["followerCount"]), int(r["agentId"])))
    ranked.sort(reverse=True)
    return [aid for _, aid in ranked[:top_k]]


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
    with open(df_path, newline="") as f:
        for r in csv.DictReader(f):
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
    print("=== Deriving class IDs for each (top_k, threshold) config from existing t0 snapshots ===", flush=True)
    ids_by_config = {}
    for name, top_k, threshold in CONFIGS:
        ids_by_config[name] = {s: derive_class_ids(s, top_k, threshold) for s in SEEDS}
        for s in SEEDS:
            print(f"  {name} seed={s}: {len(ids_by_config[name][s])} agents -> {ids_by_config[name][s]}", flush=True)

    print("\n=== Launching A_never/B_always runs per config ===", flush=True)
    jobs = []
    for name, top_k, threshold in CONFIGS:
        for s in SEEDS:
            idstr = ",".join(str(a) for a in ids_by_config[name][s])
            for arm in ARMS:
                tokens = [f"pin_moderate_ids={idstr}"]
                if arm == "A_never":
                    tokens += [f"silent_until_ids={idstr}", f"activation_step={FULL_STEPS + 1}"]
                jobs.append((s, FULL_STEPS, f"{ROBUST_SUBDIR}/{name}/{arm}", tokens))
    run_wave(jobs, max_workers=20)

    print("\n=== Results: paired A_never vs B_always, n=5, final checkpoint, per config ===", flush=True)
    all_configs = [("baseline_topk20_thresh02", SUBDIR)] + [(name, f"{ROBUST_SUBDIR}/{name}") for name, _, _ in CONFIGS]
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
