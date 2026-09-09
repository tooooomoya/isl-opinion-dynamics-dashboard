"""
2026-08-02 -- Follow-up deep dive on delayed_moderate_conduit_pilot.py's results: full opinion-
dynamics trajectory (not just the 5 checkpoints) and cascade-level mechanism analysis (what's
actually different about HOW cascades form/cross camps between arms, not just the summary
metrics). Read-only -- no new simulation, operates on results already on disk under
results/2026-08-02_delayed-moderate-pilot/.

Usage: python3 scripts/delayed_moderate_pilot_deepdive.py
"""
import csv
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SUBDIR = "2026-08-02_delayed-moderate-pilot"
SEEDS = [7300000 + i for i in range(5)]
ARMS = ["A_never", "B_always", "C_10k", "D_30k"]
MODERATE_THRESHOLD = 0.2
TRAJ_STEPS = list(range(0, 40001, 2000))

CLASS_IDS = {
    7300000: [1, 15, 5, 2, 12, 22, 17, 35, 39, 30, 37, 44, 21, 26, 85, 29, 64, 157, 114, 83],
    7300001: [8, 14, 1, 7, 11, 15, 2, 31, 20, 46, 27, 37, 54, 34, 22, 50, 49, 44, 77, 45],
    7300002: [6, 41, 35, 21, 19, 25, 68, 67, 59, 48, 56, 169, 45, 137, 94, 80, 86, 104, 148, 123],
    7300003: [1, 4, 12, 15, 13, 19, 27, 50, 22, 29, 44, 21, 57, 73, 71, 114, 74, 30, 48, 112],
    7300004: [2, 0, 7, 1, 19, 23, 18, 34, 27, 42, 22, 41, 46, 47, 16, 51, 99, 32, 40, 135],
}
ACTIVATION_STEP = {"A_never": None, "B_always": 0, "C_10k": 10000, "D_30k": 30000}


def result_dir(seed, arm):
    cands = sorted(ROOT.glob(f"results/{SUBDIR}/{arm}/run_{seed}_*"))
    return cands[-1] if cands else None


# ---------------------------------------------------------------------------
# Part 1: full opinion-dynamics trajectory (per-step results.csv, sampled every 2000 steps)
# ---------------------------------------------------------------------------
TRAJ_COLS = ["opinionVar", "postOpinionVar", "opinionAssortativity", "crossCuttingFraction",
             "bimodalityCoeff", "disagreement", "meanTolerance", "crossRepostRate",
             "outGroupBlockPropensity", "outGroupSanctionRate"]
WINDOW_COLS = ["blockCount", "unfollowCount", "evictionCount", "originalPostCount", "repostCount"]


def load_trajectory(seed, arm):
    d = result_dir(seed, arm)
    df = pd.read_csv(d / "metrics" / "results.csv")
    df = df.set_index("step")
    return df


def trajectory_summary():
    print("\n" + "=" * 100)
    print("PART 1: Opinion-dynamics trajectory (mean over 5 seeds, sampled every 2000 steps)")
    print("=" * 100)
    all_df = {arm: {s: load_trajectory(s, arm) for s in SEEDS} for arm in ARMS}

    for col in TRAJ_COLS:
        print(f"\n--- {col} ---")
        header = "step".rjust(7) + "".join(a.rjust(14) for a in ARMS)
        print(header)
        for step in TRAJ_STEPS:
            vals = []
            for arm in ARMS:
                v = np.mean([all_df[arm][s].loc[step, col] for s in SEEDS])
                vals.append(v)
            print(str(step).rjust(7) + "".join(f"{v:14.4f}" for v in vals))

    # windowed event RATES (per-step counts, summed over trailing 2000-step windows, /2000/N for
    # a per-agent-per-step rate) -- these are instantaneous flow rates, not levels, so they surface
    # exactly when block/unfollow/repost activity spikes (e.g. right at an arm's activation_step).
    print("\n--- windowed event rates (trailing 2000-step window, sum/2000, pooled over 5 seeds) ---")
    for col in WINDOW_COLS:
        print(f"\n{col} (per-step count, trailing-2000 mean):")
        header = "step".rjust(7) + "".join(a.rjust(14) for a in ARMS)
        print(header)
        for step in TRAJ_STEPS[1:]:
            lo = step - 2000
            vals = []
            for arm in ARMS:
                v = np.mean([all_df[arm][s].loc[lo + 1:step, col].mean() for s in SEEDS])
                vals.append(v)
            print(str(step).rjust(7) + "".join(f"{v:14.3f}" for v in vals))
    return all_df


# ---------------------------------------------------------------------------
# Part 2: cascade-level mechanism analysis (repost_cascades.csv)
# ---------------------------------------------------------------------------
def camp(op):
    if abs(op) < MODERATE_THRESHOLD:
        return 0  # moderate band, excluded from camp partition (project convention)
    return 1 if op > 0 else -1


def load_cascades(seed, arm):
    d = result_dir(seed, arm)
    df = pd.read_csv(d / "posts" / "repost_cascades.csv")
    return df


def cascade_analysis():
    print("\n" + "=" * 100)
    print("PART 2: Cascade-level mechanism analysis (pooled 5 seeds per arm)")
    print("=" * 100)

    for arm in ARMS:
        act = ACTIVATION_STEP[arm]
        n_cascades_total = 0
        n_events_total = 0
        n_crossing_events = 0
        n_class_relay_events = 0
        n_class_crossing_relay_events = 0
        n_extreme_authored_events = 0
        cascade_sizes = []
        class_root_cascades = set()
        all_root_cascades = set()
        crossing_root_cascades = set()
        class_crossing_root_cascades = set()

        for seed in SEEDS:
            ids = set(CLASS_IDS[seed])
            df = load_cascades(seed, arm)
            df["author_camp"] = df["conveyedOpinion"].apply(camp)
            df["relayer_camp"] = df["relayerOpinion"].apply(camp)
            crossing_mask = (df["author_camp"] != 0) & (df["relayer_camp"] != 0) & \
                             (df["author_camp"] != df["relayer_camp"])
            class_relay_mask = df["relayer"].isin(ids)
            # NOTE: strict extreme-vs-extreme crossing_mask is mechanically ALWAYS false when the
            # relayer is a class member (their relayerOpinion stays in the moderate band by
            # construction -> relayer_camp==0 -> excluded from the two-camp partition, same
            # convention as Analysis.java's crossCuttingFraction). "Does the class carry extreme
            # content across camps" needs a different operationalization: extreme_carry_mask =
            # relay events where the ROOT author is a genuine extreme (author_camp != 0) AND the
            # relayer is a class member -- this measures extreme-authored content flowing THROUGH
            # the class, regardless of the class's own (always-moderate) camp label.
            extreme_carry_mask = (df["author_camp"] != 0) & class_relay_mask

            n_events_total += len(df)
            n_crossing_events += int(crossing_mask.sum())
            n_class_relay_events += int(class_relay_mask.sum())
            n_class_crossing_relay_events += int(extreme_carry_mask.sum())
            n_extreme_authored_events += int((df["author_camp"] != 0).sum())

            sizes = df.groupby("rootPostId").size()
            cascade_sizes.extend(sizes.tolist())
            n_cascades_total += df["rootPostId"].nunique()

            root_ids = set(df["rootPostId"].unique())
            all_root_cascades |= {(seed, r) for r in root_ids}
            class_roots = set(df.loc[df["author"].isin(ids), "rootPostId"].unique())
            class_root_cascades |= {(seed, r) for r in class_roots}
            crossing_roots = set(df.loc[crossing_mask, "rootPostId"].unique())
            crossing_root_cascades |= {(seed, r) for r in crossing_roots}
            class_crossing_root_cascades |= {(seed, r) for r in (class_roots & crossing_roots)}

        print(f"\n### arm={arm} (activation_step={act}) ###")
        print(f"  total relay events (pooled 5 seeds): {n_events_total}")
        print(f"  total distinct cascades (rootPostId, pooled): {n_cascades_total}")
        print(f"  mean cascade size (relay events per cascade): {np.mean(cascade_sizes):.3f}  "
              f"median={np.median(cascade_sizes):.1f}  max={np.max(cascade_sizes)}")
        print(f"  crossing relay events / all relay events: {n_crossing_events}/{n_events_total} "
              f"= {100*n_crossing_events/n_events_total:.3f}%")
        print(f"  class-authored cascades / all cascades: {len(class_root_cascades)}/{len(all_root_cascades)} "
              f"= {100*len(class_root_cascades)/len(all_root_cascades):.3f}%")
        print(f"  crossing cascades / all cascades: {len(crossing_root_cascades)}/{len(all_root_cascades)} "
              f"= {100*len(crossing_root_cascades)/len(all_root_cascades):.3f}%")
        if crossing_root_cascades:
            print(f"  class-authored AMONG crossing cascades: {len(class_crossing_root_cascades)}/{len(crossing_root_cascades)} "
                  f"= {100*len(class_crossing_root_cascades)/len(crossing_root_cascades):.3f}%")
        print(f"  class relay events / all relay events: {n_class_relay_events}/{n_events_total} "
              f"= {100*n_class_relay_events/n_events_total:.3f}%")
        print(f"  class relay events carrying EXTREME-authored content / all class relay events: "
              f"{n_class_crossing_relay_events}/{n_class_relay_events} "
              f"= {100*n_class_crossing_relay_events/n_class_relay_events if n_class_relay_events else 0:.3f}%")
        print(f"  class's SHARE of all extreme-authored relay events (class vs everyone else "
              f"relaying extreme content): {n_class_crossing_relay_events}/{n_extreme_authored_events} "
              f"= {100*n_class_crossing_relay_events/n_extreme_authored_events if n_extreme_authored_events else 0:.3f}%")


# ---------------------------------------------------------------------------
# Part 3: cascade analysis split by pre/post activation window (C_10k, D_30k only)
# ---------------------------------------------------------------------------
def pre_post_activation_analysis():
    print("\n" + "=" * 100)
    print("PART 3: Crossing-cascade rate, PRE vs POST activation window (C_10k, D_30k)")
    print("=" * 100)
    for arm in ["C_10k", "D_30k"]:
        act = ACTIVATION_STEP[arm]
        pre_events = pre_crossing = 0
        post_events = post_crossing = 0
        pre_class_events = post_class_events = 0
        for seed in SEEDS:
            ids = set(CLASS_IDS[seed])
            df = load_cascades(seed, arm)
            df["author_camp"] = df["conveyedOpinion"].apply(camp)
            df["relayer_camp"] = df["relayerOpinion"].apply(camp)
            crossing_mask = (df["author_camp"] != 0) & (df["relayer_camp"] != 0) & \
                             (df["author_camp"] != df["relayer_camp"])
            class_mask = df["relayer"].isin(ids)
            pre = df["step"] < act
            post = ~pre
            pre_events += int(pre.sum()); pre_crossing += int((pre & crossing_mask).sum())
            post_events += int(post.sum()); post_crossing += int((post & crossing_mask).sum())
            pre_class_events += int((pre & class_mask).sum())
            post_class_events += int((post & class_mask).sum())
        print(f"\n### arm={arm} (activation_step={act}) ###")
        print(f"  PRE-activation:  {pre_crossing}/{pre_events} crossing = {100*pre_crossing/pre_events:.3f}%  "
              f"class relay events (should be ~0, silent): {pre_class_events}")
        print(f"  POST-activation: {post_crossing}/{post_events} crossing = {100*post_crossing/post_events:.3f}%  "
              f"class relay events: {post_class_events}  "
              f"(class share of post-activation relay events: {100*post_class_events/post_events:.3f}%)")


if __name__ == "__main__":
    trajectory_summary()
    cascade_analysis()
    pre_post_activation_analysis()
