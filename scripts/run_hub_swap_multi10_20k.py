"""
Multi-hub swap, 10 mid-tier moderate hubs simultaneously, 20000-step continuation, 30 seeds/arm
(2026-07-20). Follow-up to the 11-hub/15000-step run: nothing reached significance there (best was
SF1 ratio at t~-1.4, control 1.183 vs treatment 1.078), and two things changed at once (hub count,
window length) versus the earlier single-hub tests, confounding the read. Per user decision: don't
disentangle further, just scale up power on this same style of design -- drop to 10 hubs (dropped
agent 30, inDegree=51, the weakest candidate) "for simplicity", extend window 15000 -> 20000 steps,
and raise seeds 10 -> 30/arm (current SEM~0.05 on the SF1 ratio -> ~0.03 at n=30, enough to detect
the ~0.105 shift seen before at t~2.4 if it holds).

NEW control run needed (window length changed again) -- same starting snapshot
(results/run_920000_.../GEXF/lambda_0.0/step_20000.gexf), unmodified, continued to 20000 steps.

Usage: python3 scripts/run_hub_swap_multi10_20k.py
"""
import concurrent.futures
import csv
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
LIBCP = ":".join(str(p) for p in ROOT.glob("lib/**/*.jar")) + (":" if list(ROOT.glob("lib/**/*.jar")) else "") + str(ROOT / "bin")
N = 1000
CONTINUE_STEPS = 20000
N_SEEDS = 30
CONTROL_GEXF = "/tmp/hubswap/control.gexf"
TREATMENT_GEXF = "/tmp/hubswap/treatment_multi10.gexf"
CONTROL_BASE_SEED = 950000
TREATMENT_BASE_SEED = 951000
SWAPPED_IDS = [22, 16, 40, 37, 67, 43, 69, 46, 47, 98]

LOG_PATH = ROOT / "docs" / "report" / "hub_swap_multi10_20k.csv"
GEXF_NS = "http://gexf.net/1.3"


def launch(read_path, seed):
    tokens = [f"seed={seed}", "network=read", f"read_path={read_path}", f"n={N}",
              f"steps={CONTINUE_STEPS}", "log_gexf=false", "force=true"]
    logfile = ROOT / "logs" / f"hubswap_multi10_seed{seed}.log"
    logfile.parent.mkdir(exist_ok=True)
    with open(logfile, "w") as lf:
        p = subprocess.Popen(["java", "-Xmx2g", "-cp", LIBCP, "dynamics.OpinionDynamics", *tokens],
                              stdout=lf, stderr=subprocess.STDOUT, cwd=ROOT)
    return p


def read_metrics(seed):
    candidates = sorted(ROOT.glob(f"results/run_{seed}_*"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        return None
    d = candidates[-1]
    results_path = d / "metrics" / "results.csv"
    mod_path = d / "metrics" / "modularity.csv"
    if not (results_path.exists() and mod_path.exists()):
        return None
    with open(results_path, newline="") as f:
        last = list(csv.DictReader(f))[-1]
    ov = float(last["opinionVar"]); pv = float(last["postOpinionVar"])
    ratio = pv / ov if ov > 0 else None
    q = None
    with open(mod_path, newline="") as f:
        for row in csv.DictReader(f):
            if int(row["step"]) == CONTINUE_STEPS:
                q = float(row["Q_sign_repost"])
    return dict(
        ccf=float(last["crossCuttingFraction"]),
        iccf=float(last["interactionCrossCuttingFraction"]),
        q_sign_repost=q,
        disagreement=float(last["disagreement"]),
        opinionVar=ov,
        bimodalityCoeff=float(last["bimodalityCoeff"]),
        opinionKurtosis=float(last["opinionKurtosis"]),
        ratio=ratio,
    )


def run_condition(name, read_path, base_seed):
    seeds = [base_seed + j for j in range(N_SEEDS)]
    print(f"[{name}] launching {N_SEEDS} seeds ({seeds[0]}-{seeds[-1]}), steps={CONTINUE_STEPS}...", flush=True)
    procs = [launch(read_path, s) for s in seeds]
    for p in procs:
        p.wait()
    results = [read_metrics(s) for s in seeds]
    ok = [r for r in results if r is not None]
    print(f"[{name}] n={len(ok)}/{N_SEEDS} succeeded", flush=True)
    return seeds, results


def summarize(name, results):
    ok = [r for r in results if r is not None]
    print(f"\n=== {name} (n={len(ok)}) ===")
    for key in ["ccf", "iccf", "q_sign_repost", "disagreement", "opinionVar",
                "bimodalityCoeff", "opinionKurtosis", "ratio"]:
        vals = np.array([r[key] for r in ok if r[key] is not None])
        if len(vals):
            print(f"  {key:18s} = {vals.mean():.4f} +/- {vals.std():.4f}  (SEM {vals.std()/np.sqrt(len(vals)):.4f})")


def main():
    # Sequential, not concurrent: 30 seeds/arm x 2 arms = 60 JVMs at once would exceed both the
    # tested-safe ~30-concurrent range and available RAM (60x2GB=120GB > 112GB). Run one arm fully
    # (30 concurrent, within the validated range), then the other.
    c_seeds, c_results = run_condition("control", CONTROL_GEXF, CONTROL_BASE_SEED)
    t_seeds, t_results = run_condition("treatment (10 hubs -> extreme)", TREATMENT_GEXF, TREATMENT_BASE_SEED)

    with open(LOG_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        keys = ["ccf", "iccf", "q_sign_repost", "disagreement", "opinionVar",
                "bimodalityCoeff", "opinionKurtosis", "ratio"]
        writer.writerow(["condition", "seed"] + keys)
        for seed, r in zip(c_seeds, c_results):
            writer.writerow(["control", seed] + [r.get(k) if r else None for k in keys])
        for seed, r in zip(t_seeds, t_results):
            writer.writerow(["treatment", seed] + [r.get(k) if r else None for k in keys])

    summarize("CONTROL (10 hubs stay natural/moderate)", c_results)
    summarize("TREATMENT (10 hubs swapped to +/-0.9)", t_results)
    print(f"\nFull log: {LOG_PATH}")


if __name__ == "__main__":
    main()
