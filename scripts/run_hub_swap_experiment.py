"""
Moderate-vs-extreme hub swap experiment (2026-07-20). Control/treatment pair: identical network
topology and identical starting state for all 999 non-hub agents (both read from the same
equilibrium GEXF snapshot, results/run_920000_.../GEXF/lambda_0.0/step_20000.gexf under the newly
adopted static-bc defaults), differing ONLY in agent 3's opinion (control: 0.1225, its natural
value -- rank-1 hub by in-degree, 725/1000 followers; treatment: 0.9, swapped extreme, same sign).

Continues both for CONTINUE_STEPS more steps via network=read, N_SEEDS times each, and compares:
  - Global crossCuttingFraction / interactionCrossCuttingFraction / Q_sign_repost (already logged)
  - Hub-specific: among agent 3's followers, what fraction are opposite-sign to agent 3 (from the
    continuation's own final GEXF snapshot -- the one thing not already in results.csv)

Usage: python3 scripts/run_hub_swap_experiment.py
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
CONTINUE_STEPS = 5000
N_SEEDS = 10
BASE_SEED = 930000
HUB_ID = 3

CONTROL_GEXF = "/tmp/hubswap/control.gexf"
TREATMENT_GEXF = "/tmp/hubswap/treatment.gexf"

LOG_PATH = ROOT / "docs" / "report" / "hub_swap_experiment.csv"
GEXF_NS = "http://gexf.net/1.3"


def launch(condition, read_path, seed):
    tokens = [
        f"seed={seed}", "network=read", f"read_path={read_path}", f"n={N}",
        f"steps={CONTINUE_STEPS}", "log_gexf=true", "force=true",
    ]
    logfile = ROOT / "logs" / f"hubswap_{condition}_seed{seed}.log"
    logfile.parent.mkdir(exist_ok=True)
    with open(logfile, "w") as lf:
        p = subprocess.Popen(
            ["java", "-Xmx2g", "-cp", LIBCP, "dynamics.OpinionDynamics", *tokens],
            stdout=lf, stderr=subprocess.STDOUT, cwd=ROOT,
        )
    return p


def hub_cross_fraction(gexf_path, hub_id):
    """Among hub_id's followers (edges hub_id->follower or follower->hub_id, whichever direction
    the follow graph uses for 'follows'), fraction whose opinion sign differs from hub_id's."""
    tree = ET.parse(gexf_path)
    root = tree.getroot()
    attr_id = None
    for attrs in root.iter(f"{{{GEXF_NS}}}attributes"):
        for a in attrs.iter(f"{{{GEXF_NS}}}attribute"):
            if a.get("title") == "opinion":
                attr_id = a.get("id")
    opinion = {}
    for node in root.iter(f"{{{GEXF_NS}}}node"):
        nid = node.get("id")
        for av in node.iter(f"{{{GEXF_NS}}}attvalue"):
            if av.get("for") == attr_id:
                opinion[nid] = float(av.get("value"))
    hub_op = opinion.get(str(hub_id))
    if hub_op is None:
        return None, 0
    followers = []
    for edge in root.iter(f"{{{GEXF_NS}}}edge"):
        s, t = edge.get("source"), edge.get("target")
        if t == str(hub_id):  # s follows hub_id (edge = follower -> followee)
            followers.append(s)
    if not followers:
        return None, 0
    cross = sum(1 for f in followers if opinion.get(f) is not None and opinion[f] * hub_op < 0)
    return cross / len(followers), len(followers)


def read_metrics(seed):
    candidates = sorted(ROOT.glob(f"results/run_{seed}_*"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        return None
    d = candidates[-1]
    results_path = d / "metrics" / "results.csv"
    mod_path = d / "metrics" / "modularity.csv"
    gexf_path = d / "GEXF" / "lambda_0.0" / f"step_{CONTINUE_STEPS}.gexf"
    if not (results_path.exists() and mod_path.exists() and gexf_path.exists()):
        return None
    with open(results_path, newline="") as f:
        last = list(csv.DictReader(f))[-1]
    ccf = float(last["crossCuttingFraction"])
    iccf = float(last["interactionCrossCuttingFraction"])
    q = None
    with open(mod_path, newline="") as f:
        for row in csv.DictReader(f):
            if int(row["step"]) == CONTINUE_STEPS:
                q = float(row["Q_sign_repost"])
    hub_cross, n_followers = hub_cross_fraction(gexf_path, HUB_ID)
    return ccf, iccf, q, hub_cross, n_followers


def run_condition(condition, read_path):
    seeds = [BASE_SEED + (0 if condition == "control" else 1000) + j for j in range(N_SEEDS)]
    print(f"[{condition}] launching {N_SEEDS} seeds ({seeds[0]}-{seeds[-1]})...", flush=True)
    procs = [launch(condition, read_path, s) for s in seeds]
    for p in procs:
        p.wait()
    results = [read_metrics(s) for s in seeds]
    ok = [r for r in results if r is not None]
    print(f"[{condition}] n={len(ok)}/{N_SEEDS} succeeded", flush=True)
    return seeds, results


def summarize(name, results):
    ok = [r for r in results if r is not None]
    ccf = np.array([r[0] for r in ok])
    iccf = np.array([r[1] for r in ok])
    q = np.array([r[2] for r in ok if r[2] is not None])
    hub_cross = np.array([r[3] for r in ok if r[3] is not None])
    n_foll = np.array([r[4] for r in ok])
    print(f"\n=== {name} (n={len(ok)}) ===")
    print(f"crossCuttingFraction            = {ccf.mean():.4f} +/- {ccf.std():.4f}")
    print(f"interactionCrossCuttingFraction  = {iccf.mean():.4f} +/- {iccf.std():.4f}")
    if len(q):
        print(f"Q_sign_repost                    = {q.mean():.4f} +/- {q.std():.4f}")
    if len(hub_cross):
        print(f"hub (#{HUB_ID}) follower cross-fraction = {hub_cross.mean():.4f} +/- {hub_cross.std():.4f}  (mean n_followers={n_foll.mean():.0f})")
    return ccf, iccf, q, hub_cross


def main():
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        fut_control = ex.submit(run_condition, "control", CONTROL_GEXF)
        fut_treatment = ex.submit(run_condition, "treatment", TREATMENT_GEXF)
        control_seeds, control_results = fut_control.result()
        treatment_seeds, treatment_results = fut_treatment.result()

    with open(LOG_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["condition", "seed", "crossCuttingFraction", "interactionCrossCuttingFraction",
                          "Q_sign_repost", "hub_follower_cross_fraction", "hub_n_followers"])
        for seed, r in zip(control_seeds, control_results):
            writer.writerow(["control", seed] + (list(r) if r else [None] * 5))
        for seed, r in zip(treatment_seeds, treatment_results):
            writer.writerow(["treatment", seed] + (list(r) if r else [None] * 5))

    summarize("CONTROL (hub stays moderate, opinion=0.1225)", control_results)
    summarize("TREATMENT (hub swapped to extreme, opinion=0.9)", treatment_results)
    print(f"\nFull log: {LOG_PATH}")


if __name__ == "__main__":
    main()
