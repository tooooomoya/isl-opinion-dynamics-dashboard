"""
Hub-swap experiment, mid-tier extension (2026-07-20). Follow-up to run_hub_swap_experiment.py:
that test used agent 3, the rank-1 hub with 725/1000 followers (72.5% of the entire population) --
essentially a mega-hub, not a "mid-scale" conduit, which is what the user's actual hypothesis is
about (moderate hubs of MODEST reach delivering cross-cutting posts via repost/algorithmic
surfacing, not overwhelming direct reach). Found 3 moderate candidates with inDegree in [80,220]
from the same equilibrium snapshot (seed 920000): agent 22 (153 followers, opinion=-0.014),
agent 16 (125 followers, opinion=-0.188), agent 40 (94 followers, opinion=-0.0002).

Reuses the EXISTING 10 control runs (seeds 930000-930009, results/run_93000*) as the shared
baseline -- they already contain agents 22/16/40's natural, unmodified state, so no new control
simulation is needed. Only runs 3 new treatment arms (10 seeds each, one per candidate hub swapped
to opinion=-0.9, same base snapshot as before with ONLY that one hub's opinion changed).

Usage: python3 scripts/run_hub_swap_midtier.py
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

HUBS = {
    "agent22": {"id": 22, "gexf": "/tmp/hubswap/treatment_a22.gexf", "base_seed": 932000},
    "agent16": {"id": 16, "gexf": "/tmp/hubswap/treatment_a16.gexf", "base_seed": 933000},
    "agent40": {"id": 40, "gexf": "/tmp/hubswap/treatment_a40.gexf", "base_seed": 934000},
}
CONTROL_SEEDS = list(range(930000, 930010))  # existing runs, reused as-is

LOG_PATH = ROOT / "docs" / "report" / "hub_swap_midtier.csv"
GEXF_NS = "http://gexf.net/1.3"


def launch(name, read_path, seed):
    tokens = [f"seed={seed}", "network=read", f"read_path={read_path}", f"n={N}",
              f"steps={CONTINUE_STEPS}", "log_gexf=true", "force=true"]
    logfile = ROOT / "logs" / f"hubswap_{name}_seed{seed}.log"
    logfile.parent.mkdir(exist_ok=True)
    with open(logfile, "w") as lf:
        p = subprocess.Popen(["java", "-Xmx2g", "-cp", LIBCP, "dynamics.OpinionDynamics", *tokens],
                              stdout=lf, stderr=subprocess.STDOUT, cwd=ROOT)
    return p


def hub_cross_fraction(gexf_path, hub_id):
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
    followers = [e.get("source") for e in root.iter(f"{{{GEXF_NS}}}edge") if e.get("target") == str(hub_id)]
    if not followers:
        return None, 0
    cross = sum(1 for f in followers if opinion.get(f) is not None and opinion[f] * hub_op < 0)
    return cross / len(followers), len(followers)


def read_metrics(seed, hub_id, step=CONTINUE_STEPS):
    candidates = sorted(ROOT.glob(f"results/run_{seed}_*"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        return None
    d = candidates[-1]
    results_path = d / "metrics" / "results.csv"
    mod_path = d / "metrics" / "modularity.csv"
    gexf_path = d / "GEXF" / "lambda_0.0" / f"step_{step}.gexf"
    if not (results_path.exists() and mod_path.exists() and gexf_path.exists()):
        return None
    with open(results_path, newline="") as f:
        last = list(csv.DictReader(f))[-1]
    ccf = float(last["crossCuttingFraction"])
    iccf = float(last["interactionCrossCuttingFraction"])
    q = None
    with open(mod_path, newline="") as f:
        for row in csv.DictReader(f):
            if int(row["step"]) == step:
                q = float(row["Q_sign_repost"])
    hub_cross, n_followers = hub_cross_fraction(gexf_path, hub_id)
    return ccf, iccf, q, hub_cross, n_followers


def summarize(name, results):
    ok = [r for r in results if r is not None]
    if not ok:
        print(f"{name}: n=0 (all failed)")
        return
    ccf = np.array([r[0] for r in ok]); iccf = np.array([r[1] for r in ok])
    q = np.array([r[2] for r in ok if r[2] is not None])
    hub_cross = np.array([r[3] for r in ok if r[3] is not None])
    n_foll = np.array([r[4] for r in ok])
    print(f"  n={len(ok)}  ccf={ccf.mean():.4f}+/-{ccf.std():.4f}  iccf={iccf.mean():.4f}+/-{iccf.std():.4f}  "
          f"q={q.mean():.4f}+/-{q.std():.4f}  hub_cross={hub_cross.mean():.4f}+/-{hub_cross.std():.4f}  "
          f"n_followers={n_foll.mean():.1f}")


def main():
    rows = []
    print("=== Baseline (existing control runs, seeds 930000-930009), per candidate hub ===")
    for name, info in HUBS.items():
        results = [read_metrics(s, info["id"], step=CONTINUE_STEPS) for s in CONTROL_SEEDS]
        print(f"[{name} baseline, hub={info['id']}]")
        summarize(name, results)
        for s, r in zip(CONTROL_SEEDS, results):
            rows.append([name, "control", s] + (list(r) if r else [None] * 5))

    print("\n=== Treatment (hub swapped to -0.9), running now ===")
    for name, info in HUBS.items():
        seeds = [info["base_seed"] + j for j in range(N_SEEDS)]
        print(f"[{name}] launching {N_SEEDS} seeds ({seeds[0]}-{seeds[-1]})...", flush=True)
        procs = [launch(name, info["gexf"], s) for s in seeds]
        for p in procs:
            p.wait()
        results = [read_metrics(s, info["id"], step=CONTINUE_STEPS) for s in seeds]
        print(f"[{name} treatment, hub={info['id']}]")
        summarize(name, results)
        for s, r in zip(seeds, results):
            rows.append([name, "treatment", s] + (list(r) if r else [None] * 5))

    with open(LOG_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["hub_name", "condition", "seed", "crossCuttingFraction",
                          "interactionCrossCuttingFraction", "Q_sign_repost",
                          "hub_follower_cross_fraction", "hub_n_followers"])
        writer.writerows(rows)
    print(f"\nFull log: {LOG_PATH}")


if __name__ == "__main__":
    main()
