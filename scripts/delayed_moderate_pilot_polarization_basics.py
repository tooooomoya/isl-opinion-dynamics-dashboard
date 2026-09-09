"""
2026-08-02 -- Follow-up: the basic question underneath the timing/erosion deep-dive -- does the
moderate class's mere PRESENCE (active vs never) change polarization at all, and specifically how
does extreme/pre-extreme agents' posting behavior change? Main contrast: A_never (moderate class
permanently silent, closest to "moderate absent") vs B_always (active from t=0, closest to
"moderate present"). C_10k/D_30k included for reference. Read-only, operates on
results/2026-08-02_delayed-moderate-pilot/ already on disk.

Usage: python3 scripts/delayed_moderate_pilot_polarization_basics.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SUBDIR = "2026-08-02_delayed-moderate-pilot"
SEEDS = [7300000 + i for i in range(5)]
ARMS = ["A_never", "B_always", "C_10k", "D_30k"]
TRAJ_STEPS = list(range(0, 40001, 2000))
WINDOW = 2000


def result_dir(seed, arm):
    cands = sorted(ROOT.glob(f"results/{SUBDIR}/{arm}/run_{seed}_*"))
    return cands[-1] if cands else None


def load_results(seed, arm):
    d = result_dir(seed, arm)
    return pd.read_csv(d / "metrics" / "results.csv").set_index("step")


def population_counts(seed, arm):
    """5-bin population classification from this arm's OWN final opinion (same convention as
    scripts/moderate_hub_4tier_removehub.py's population_counts -- bin width 0.4 over [-1,1],
    bins 0/4 = extreme, bins 1/3 = pre-extreme, bin 2 = center/moderate)."""
    d = result_dir(seed, arm)
    counts = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0}
    df = pd.read_csv(d / "degrees" / "agent_snapshot_final.csv")
    shifted = df["opinion"] + 1.0
    cls = (shifted / 0.4).astype(int).clip(upper=4)
    for c in cls:
        counts[c] += 1
    return counts


def main():
    print("=" * 100)
    print("Population composition (final opinion, 5-bin classification, mean over 5 seeds)")
    print("=" * 100)
    pop = {arm: {s: population_counts(s, arm) for s in SEEDS} for arm in ARMS}
    for arm in ARMS:
        means = {b: np.mean([pop[arm][s][b] for s in SEEDS]) for b in range(5)}
        print(f"  {arm:>10}: bin0(extreme-)={means[0]:.1f}  bin1(pre-ext-)={means[1]:.1f}  "
              f"bin2(center)={means[2]:.1f}  bin3(pre-ext+)={means[3]:.1f}  bin4(extreme+)={means[4]:.1f}")

    all_df = {arm: {s: load_results(s, arm) for s in SEEDS} for arm in ARMS}

    print("\n" + "=" * 100)
    print("crossCuttingFraction & opinionAssortativity: moderate ACTIVE (B) vs NEVER (A)")
    print("=" * 100)
    header = "step".rjust(7) + "  ccf_A".rjust(10) + "  ccf_B".rjust(10) + "  ccf_B/A".rjust(10) \
        + "  assort_A".rjust(11) + "  assort_B".rjust(11)
    print(header)
    for step in TRAJ_STEPS:
        ccf_a = np.mean([all_df["A_never"][s].loc[step, "crossCuttingFraction"] for s in SEEDS])
        ccf_b = np.mean([all_df["B_always"][s].loc[step, "crossCuttingFraction"] for s in SEEDS])
        as_a = np.mean([all_df["A_never"][s].loc[step, "opinionAssortativity"] for s in SEEDS])
        as_b = np.mean([all_df["B_always"][s].loc[step, "opinionAssortativity"] for s in SEEDS])
        ratio = ccf_b / ccf_a if ccf_a > 0 else float("nan")
        print(f"{step:7d}{ccf_a:10.4f}{ccf_b:10.4f}{ratio:10.3f}{as_a:11.4f}{as_b:11.4f}")

    print("\n" + "=" * 100)
    print("Per-capita post rate (originalPost+repost, trailing-2000-step window / population), "
          "by class: extreme (bin0+4) vs pre-extreme (bin1+3) vs center (bin2)")
    print("=" * 100)
    for arm in ARMS:
        print(f"\n### arm={arm} ###")
        header = "step".rjust(7) + "extreme".rjust(10) + "pre_ext".rjust(10) + "center".rjust(10)
        print(header)
        for step in TRAJ_STEPS[1:]:
            lo = step - WINDOW
            ext_rate = []
            pre_rate = []
            ctr_rate = []
            for s in SEEDS:
                df = all_df[arm][s]
                w = df.loc[lo + 1:step]
                total = w["originalPostCount"] + w["repostCount"]
                ext_posts = ((w["postShare_0"] + w["postShare_4"]) * total).sum()
                pre_posts = ((w["postShare_1"] + w["postShare_3"]) * total).sum()
                ctr_posts = (w["postShare_2"] * total).sum()
                p = pop[arm][s]
                ext_pop = p[0] + p[4]
                pre_pop = p[1] + p[3]
                ctr_pop = p[2]
                if ext_pop > 0: ext_rate.append(ext_posts / ext_pop / WINDOW)
                if pre_pop > 0: pre_rate.append(pre_posts / pre_pop / WINDOW)
                if ctr_pop > 0: ctr_rate.append(ctr_posts / ctr_pop / WINDOW)
            print(f"{step:7d}{np.mean(ext_rate):10.4f}{np.mean(pre_rate):10.4f}{np.mean(ctr_rate):10.4f}")

    print("\n" + "=" * 100)
    print("Per-capita post rate: A_never vs B_always side by side, with diff")
    print("=" * 100)
    for cls_name, share_cols in [("extreme (bin0+4)", ("postShare_0", "postShare_4")),
                                   ("pre-extreme (bin1+3)", ("postShare_1", "postShare_3"))]:
        print(f"\n--- {cls_name} ---")
        header = "step".rjust(7) + "rate_A".rjust(10) + "rate_B".rjust(10) + "diff(B-A)".rjust(12) + "diff%".rjust(10)
        print(header)
        for step in TRAJ_STEPS[1:]:
            lo = step - WINDOW
            rates = {}
            for arm in ["A_never", "B_always"]:
                vals = []
                for s in SEEDS:
                    df = all_df[arm][s]
                    w = df.loc[lo + 1:step]
                    total = w["originalPostCount"] + w["repostCount"]
                    posts = ((w[share_cols[0]] + w[share_cols[1]]) * total).sum()
                    p = pop[arm][s]
                    bins = [int(c.split("_")[1]) for c in share_cols]
                    n_pop = sum(p[b] for b in bins)
                    if n_pop > 0:
                        vals.append(posts / n_pop / WINDOW)
                rates[arm] = np.mean(vals)
            diff = rates["B_always"] - rates["A_never"]
            pct = 100 * diff / rates["A_never"] if rates["A_never"] else float("nan")
            print(f"{step:7d}{rates['A_never']:10.4f}{rates['B_always']:10.4f}{diff:12.4f}{pct:9.1f}%")


if __name__ == "__main__":
    main()
