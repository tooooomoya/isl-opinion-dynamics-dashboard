"""
2026-08-02 -- Mechanism check for the "extreme per-capita posting rate rises ~17-25% when the
moderate class is continuously active (B_always vs A_never)" finding. User's three candidate
explanations, all tested directly against data already on disk (no new simulation):

  1. Mean bc (tolerance) among extreme-camp agents lower/higher in B vs A?
  2. In-camp circulation volume: does more extreme-authored content reach extreme agents overall
     when the moderate is active (via cascades data, split same-camp-direct vs moderate-relayed)?
  3. Denser/more-clustered follow-graph structure among extreme-camp agents in B vs A?

Grounding in the actual code (src/agent/Agent.java updateMyself()): postProb is driven SOLELY by
comfortPostRate = fraction of an agent's FEED within vocalComfortRadius (0.1) of their OWN opinion
-- NOT directly by how many times they get reposted. So the proximate mechanism, if any, must
show up as a rise in comfort rate (cRateMean_0/cRateMean_4, already logged in results.csv) for
extreme-camp agents specifically. Hypotheses 1-3 are then tested as candidate UPSTREAM causes of
that comfort-rate rise.

Usage: python3 scripts/delayed_moderate_pilot_extreme_mechanism.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SUBDIR = "2026-08-02_delayed-moderate-pilot"
SEEDS = [7300000 + i for i in range(5)]
ARMS = ["A_never", "B_always"]
TRAJ_STEPS = [0, 5000, 10000, 15000, 20000, 25000, 30000, 35000, 40000]
MODERATE_THRESHOLD = 0.2

CLASS_IDS = {
    7300000: [1, 15, 5, 2, 12, 22, 17, 35, 39, 30, 37, 44, 21, 26, 85, 29, 64, 157, 114, 83],
    7300001: [8, 14, 1, 7, 11, 15, 2, 31, 20, 46, 27, 37, 54, 34, 22, 50, 49, 44, 77, 45],
    7300002: [6, 41, 35, 21, 19, 25, 68, 67, 59, 48, 56, 169, 45, 137, 94, 80, 86, 104, 148, 123],
    7300003: [1, 4, 12, 15, 13, 19, 27, 50, 22, 29, 44, 21, 57, 73, 71, 114, 74, 30, 48, 112],
    7300004: [2, 0, 7, 1, 19, 23, 18, 34, 27, 42, 22, 41, 46, 47, 16, 51, 99, 32, 40, 135],
}


def result_dir(seed, arm):
    cands = sorted(ROOT.glob(f"results/{SUBDIR}/{arm}/run_{seed}_*"))
    return cands[-1] if cands else None


def camp5(op):
    shifted = op + 1.0
    return min(int(shifted / 0.4), 4)


def extreme_agent_ids(seed, arm):
    """agentIds classified extreme (bin0 or bin4) by FINAL opinion, per arm."""
    d = result_dir(seed, arm)
    df = pd.read_csv(d / "degrees" / "agent_snapshot_final.csv")
    df["bin"] = df["opinion"].apply(camp5)
    return set(df.loc[df["bin"].isin([0, 4]), "agentId"])


# ---------------------------------------------------------------------------
# 0. Direct proximate mechanism: per-bin comfort rate (already logged, drives postProb directly)
# ---------------------------------------------------------------------------
def comfort_rate_check():
    print("=" * 100)
    print("0. PROXIMATE MECHANISM: cRateMean (bin0+bin4, extreme), the DIRECT driver of postProb")
    print("=" * 100)
    header = "step".rjust(7) + "cRate_A".rjust(10) + "cRate_B".rjust(10) + "diff".rjust(10)
    print(header)
    for step in TRAJ_STEPS:
        vals = {}
        for arm in ARMS:
            v = []
            for s in SEEDS:
                d = result_dir(s, arm)
                df = pd.read_csv(d / "metrics" / "results.csv").set_index("step")
                row = df.loc[step]
                # population-weighted average of bin0 and bin4 (both extreme)
                v.append((row["cRateMean_0"] + row["cRateMean_4"]) / 2)
            vals[arm] = np.mean(v)
        print(f"{step:7d}{vals['A_never']:10.4f}{vals['B_always']:10.4f}{vals['B_always']-vals['A_never']:10.4f}")


# ---------------------------------------------------------------------------
# 1. Mean bc among extreme-camp agents
# ---------------------------------------------------------------------------
def bc_check():
    print("\n" + "=" * 100)
    print("1. Mean bc (tolerance) among extreme-camp agents (final-opinion classified), per arm")
    print("=" * 100)
    for arm in ARMS:
        vals = []
        for s in SEEDS:
            d = result_dir(s, arm)
            df = pd.read_csv(d / "degrees" / "agent_snapshot_final.csv")
            df["bin"] = df["opinion"].apply(camp5)
            ext = df[df["bin"].isin([0, 4])]
            vals.append(ext["bc"].mean())
        print(f"  {arm:>10}: mean bc = {np.mean(vals):.4f} +/- {np.std(vals):.4f}")


# ---------------------------------------------------------------------------
# 2. In-camp circulation volume via cascades: extreme-authored content reaching extreme agents,
#    split same-camp-direct vs via-moderate-class
# ---------------------------------------------------------------------------
def circulation_check():
    print("\n" + "=" * 100)
    print("2. Circulation volume: relay events where an EXTREME-authored post reaches an "
          "EXTREME-camp relayer (same-camp exposure), split by whether the relay was direct or "
          "via a moderate-class agent somewhere in the chain")
    print("=" * 100)
    for arm in ARMS:
        same_camp_direct = 0
        via_moderate = 0
        total_extreme_authored = 0
        for s in SEEDS:
            ids = set(CLASS_IDS[s])
            d = result_dir(s, arm)
            df = pd.read_csv(d / "posts" / "repost_cascades.csv")
            df["author_camp"] = df["conveyedOpinion"].apply(lambda o: 0 if abs(o) < MODERATE_THRESHOLD else (1 if o > 0 else -1))
            df["relayer_camp"] = df["relayerOpinion"].apply(lambda o: 0 if abs(o) < MODERATE_THRESHOLD else (1 if o > 0 else -1))
            extreme_authored = df[df["author_camp"] != 0]
            total_extreme_authored += len(extreme_authored)
            same_camp_hit = extreme_authored[extreme_authored["relayer_camp"] == extreme_authored["author_camp"]]
            # among same-camp exposure events, was the relayer directly reached, or is this event
            # itself the moderate-class relayer (counted separately)?
            same_camp_direct += int((same_camp_hit["relayer"].isin(ids) == False).sum())
            via_moderate += int(extreme_authored["relayer"].isin(ids).sum())
        print(f"\n  arm={arm}: total extreme-authored relay events (pooled) = {total_extreme_authored}")
        print(f"    same-camp direct relay events (non-class relayer, same camp as author): {same_camp_direct} "
              f"({100*same_camp_direct/total_extreme_authored:.2f}%)")
        print(f"    relayed BY the moderate class (any camp downstream): {via_moderate} "
              f"({100*via_moderate/total_extreme_authored:.2f}%)")


# ---------------------------------------------------------------------------
# 3. Clustering coefficient among extreme-camp agents (follow-graph, per-agent, already logged)
# ---------------------------------------------------------------------------
def clustering_check():
    print("\n" + "=" * 100)
    print("3. Mean follow-graph clustering coefficient among extreme-camp agents, over time")
    print("=" * 100)
    header = "step".rjust(7) + "clust_A".rjust(10) + "clust_B".rjust(10) + "diff".rjust(10)
    print(header)
    ext_ids = {arm: {s: extreme_agent_ids(s, arm) for s in SEEDS} for arm in ARMS}
    for step in TRAJ_STEPS:
        vals = {}
        for arm in ARMS:
            v = []
            for s in SEEDS:
                d = result_dir(s, arm)
                fp = d / "clusterings" / f"clustering_result_{step}.csv"
                if not fp.exists():
                    continue
                df = pd.read_csv(fp)
                sub = df[df["agentId"].isin(ext_ids[arm][s])]
                v.append(sub["clusteringCoefficient"].mean())
            vals[arm] = np.mean(v) if v else float("nan")
        print(f"{step:7d}{vals['A_never']:10.4f}{vals['B_always']:10.4f}{vals['B_always']-vals['A_never']:10.4f}")


if __name__ == "__main__":
    comfort_rate_check()
    bc_check()
    circulation_check()
    clustering_check()
