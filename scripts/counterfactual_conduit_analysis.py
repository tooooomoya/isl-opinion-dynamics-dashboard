"""
2026-07-30 -- "Counterfactual Conduit" test (user's definition, 2026-07-30): for each cascade C
(grouped by rootPostId in repost_cascades.csv), I(C)=1 if it ever reaches the opposite camp from
the root's opinion sign (relay_enabled=false => conveyedOpinion is verbatim the root's opinion
throughout, so this is a plain sign check against relayerOpinion). I_{-R}(C) = same check after
pruning every node relayed by an agent in the target set R, AND everything downstream of it (a
node's children only exist because it created the post they relayed, so removing it removes its
whole subtree -- this is a structural/graph-necessity test on the ALREADY-OBSERVED cascade tree,
not a re-simulation). Delta(C) = I(C) - I_{-R}(C) in {0,1}: 1 iff R's participation was NECESSARY
for that specific cascade's cross-camp reach. Counterfactual Conduit = mean(Delta(C)).

Reported both unconditional (over ALL cascades, matching the user's literal formula) and
conditional (over only cascades that actually crossed camps, arguably more interpretable: "of
cascades that crossed camps, what fraction depended on R").

Entirely post-hoc on the CONTROL arm only (9200000-9) -- this test only makes sense against the
actually-observed, undamaged cascade history; remove_hub's own separate simulation runs are a
different (real re-simulation, different RNG) counterfactual, not what this test measures.

Also: a cheap supplementary check for the "peripheral agents activate broader local activity, and
removal deactivates it" alternative hypothesis (user, 2026-07-30, noted not yet tested) -- compares
mean per-step (originalPostCount+repostCount), i.e. total network activity, control vs remove_hub
(small/peripheral) over the same window, using results.csv columns already computed by every run
(no new heavy analysis needed).

Usage: python3 scripts/counterfactual_conduit_analysis.py
"""
import csv
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent

EQUIL_BASE_SEED = 9100000
CONTROL_BASE_SEED = 9200000
REMOVE_HUB_BASE = {"mega": 9410000, "middle": 9420000, "small": 9430000, "peripheral": 9440000}
N_SEEDS = 10
MODERATE_THRESHOLD = 0.2
TIERS = {"mega": (300, float("inf")), "middle": (30, 300), "small": (3, 30), "peripheral": (0, 3)}
CASCADE_WINDOW = (10000, 19000)
ACTIVITY_WINDOW = (15000, 20000)


def result_dir(seed):
    cands = sorted(ROOT.glob(f"results/run_{seed}_*"))
    return cands[-1] if cands else None


def moderate_hub_ids_from_equil(equil_seed, tier):
    d = result_dir(equil_seed)
    lo, hi = TIERS[tier]
    hits = set()
    with open(d / "degrees" / "agent_snapshot_final.csv", newline="") as f:
        for r in csv.DictReader(f):
            op, fo = float(r["opinion"]), int(r["followerCount"])
            if lo < fo <= hi and abs(op) < MODERATE_THRESHOLD:
                hits.add(int(r["agentId"]))
    return hits


def counterfactual_conduit(control_seed, R, window):
    d = result_dir(control_seed)
    df = pd.read_csv(d / "posts" / "repost_cascades.csv",
                      usecols=["step", "rootPostId", "parentPostId", "postId", "relayer",
                               "conveyedOpinion", "relayerOpinion"])
    depth1 = df[df["parentPostId"] == df["rootPostId"]]
    roots = set(depth1[(depth1["step"] > window[0]) & (depth1["step"] <= window[1])]["rootPostId"])
    sub = df[df["rootPostId"].isin(roots)]

    postid_arr = sub["postId"].to_numpy()
    parent_arr = sub["parentPostId"].to_numpy()
    relayer_arr = sub["relayer"].to_numpy()
    relayop_arr = sub["relayerOpinion"].to_numpy()
    root_arr = sub["rootPostId"].to_numpy()
    conv_arr = sub["conveyedOpinion"].to_numpy()

    relayer_of = dict(zip(postid_arr, relayer_arr))
    opinion_of = dict(zip(postid_arr, relayop_arr))
    children = {}
    for p, pid in zip(parent_arr, postid_arr):
        children.setdefault(p, []).append(pid)
    root_sign_of = dict(zip(root_arr, np.sign(conv_arr)))

    n_total = n_full = n_removed = 0
    for root in roots:
        rs = root_sign_of.get(root, 0)
        if rs == 0:
            continue
        n_total += 1
        stack = list(children.get(root, []))
        i_full = False
        while stack:
            pid = stack.pop()
            if np.sign(opinion_of[pid]) * rs < 0:
                i_full = True
            stack.extend(children.get(pid, []))
        if not i_full:
            continue
        n_full += 1
        stack = list(children.get(root, []))
        i_removed = False
        while stack:
            pid = stack.pop()
            if relayer_of[pid] in R:
                continue
            if np.sign(opinion_of[pid]) * rs < 0:
                i_removed = True
            stack.extend(children.get(pid, []))
        if i_removed:
            n_removed += 1

    return dict(n_total=n_total, n_crossed=n_full, n_still_crossed_after_removal=n_removed,
                cc_unconditional=(n_full - n_removed) / n_total if n_total else np.nan,
                cc_conditional=(n_full - n_removed) / n_full if n_full else np.nan)


def activity_check():
    print("\n=== Supplementary: broader activity check (control vs remove_hub) ===\n")
    print("Tests: does total network activity (originalPostCount+repostCount per step) drop broadly,")
    print("not just for pre-extreme, when small/peripheral moderates are removed?\n")
    for tier, base in REMOVE_HUB_BASE.items():
        control_vals, treat_vals = [], []
        for i in range(N_SEEDS):
            for seed, bucket in [(CONTROL_BASE_SEED + i, control_vals), (base + i, treat_vals)]:
                d = result_dir(seed)
                df = pd.read_csv(d / "metrics" / "results.csv", usecols=["step", "originalPostCount", "repostCount"])
                w = df[(df["step"] > ACTIVITY_WINDOW[0]) & (df["step"] <= ACTIVITY_WINDOW[1])]
                bucket.append((w["originalPostCount"] + w["repostCount"]).mean())
        c = np.array(control_vals); t = np.array(treat_vals)
        diff = t - c
        tstat = diff.mean() / (diff.std(ddof=1) / np.sqrt(len(diff))) if diff.std(ddof=1) > 0 else float("nan")
        print(f"  remove_hub_{tier}: control_mean_activity={c.mean():.2f}+/-{c.std():.2f}  "
              f"treated={t.mean():.2f}+/-{t.std():.2f}  diff={diff.mean():+.2f}+/-{diff.std():.2f}  "
              f"({100*diff.mean()/c.mean():+.1f}%)  t={tstat:.2f}  n={len(c)}")


def main():
    print("=== Counterfactual Conduit: is R's participation NECESSARY for cross-camp cascade reach? ===")
    print(f"Cascade window (depth-1 event step): {CASCADE_WINDOW}\n")

    rows = []
    for i in range(N_SEEDS):
        equil_seed = EQUIL_BASE_SEED + i
        control_seed = CONTROL_BASE_SEED + i
        line = f"  seed={control_seed}:"
        for tier in TIERS:
            R = moderate_hub_ids_from_equil(equil_seed, tier)
            res = counterfactual_conduit(control_seed, R, CASCADE_WINDOW)
            rows.append(dict(seed=control_seed, tier=tier, n_R=len(R), **res))
            line += f" {tier}(n_R={len(R)}) cc_uncond={res['cc_unconditional']:.4f} cc_cond={res['cc_conditional']:.4f} |"
        print(line, flush=True)

    df_all = pd.DataFrame(rows)
    log_path = ROOT / "docs" / "report" / "counterfactual_conduit.csv"
    df_all.to_csv(log_path, index=False)
    print(f"\nFull per-seed log: {log_path}\n")

    print("--- Aggregate (mean +/- sd across 10 seeds) ---")
    for tier in TIERS:
        g = df_all[df_all.tier == tier]
        print(f"  {tier:>10}: cc_unconditional={g.cc_unconditional.mean():.4f}+/-{g.cc_unconditional.std():.4f}  "
              f"cc_conditional={g.cc_conditional.mean():.4f}+/-{g.cc_conditional.std():.4f}  "
              f"(n_crossed avg={g.n_crossed.mean():.0f}/{g.n_total.mean():.0f} total cascades)")

    activity_check()


if __name__ == "__main__":
    main()
