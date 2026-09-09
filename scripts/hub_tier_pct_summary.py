"""
Post-processing (2026-07-21) of hub_tier_characterization.py's 20-seed run: re-derive tiers by
in-degree as a PERCENTAGE OF THE POPULATION (n=1000) rather than by rank position (per user
request), reusing the same completed sim runs -- no re-simulation needed, since
`degrees/agent_snapshot_final.csv` already contains all 1000 agents per seed, not just the
top-50-by-rank subset that hub_tier_characterization.py's own log truncated to.

Tiers (of n=1000):
  mega   : followerCount > 500   (>50% of the population follows this agent)
  mid    : 100 < followerCount <= 500   (>10%, <=50%)
  tail   : followerCount <= 100  (<=10%)
"moderate" = |opinion| < MODERATE_THRESHOLD (0.2, same threshold as before).

Usage: python3 scripts/hub_tier_pct_summary.py
"""
import csv
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
N = 1000
BASE_SEED = 990000
N_SEEDS = 20
MODERATE_THRESHOLD = 0.2

TIERS = [
    ("mega", 500, N),      # followerCount > 500
    ("mid", 100, 500),     # 100 < followerCount <= 500
    ("tail", -1, 100),     # followerCount <= 100
]

RAW_OUT = ROOT / "docs" / "report" / "hub_tier_pct_raw.csv"
SUMMARY_OUT = ROOT / "docs" / "report" / "hub_tier_pct_summary.csv"


def read_snapshot(seed):
    candidates = sorted(ROOT.glob(f"results/run_{seed}_*"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        return None
    d = candidates[-1]
    snap_path = d / "degrees" / "agent_snapshot_final.csv"
    if not snap_path.exists():
        return None
    rows = []
    with open(snap_path, newline="") as f:
        for r in csv.DictReader(f):
            rows.append((int(r["agentId"]), float(r["opinion"]), int(r["followerCount"])))
    return rows


def tier_of(followers):
    if followers > 500:
        return "mega"
    if followers > 100:
        return "mid"
    return "tail"


def main():
    seeds = [BASE_SEED + j for j in range(N_SEEDS)]
    all_rows = []
    per_seed = {}
    for seed in seeds:
        rows = read_snapshot(seed)
        if rows is None:
            print(f"seed {seed}: no snapshot found (run missing/incomplete)")
            continue
        per_seed[seed] = rows
        for agent_id, opinion, followers in rows:
            all_rows.append([seed, agent_id, opinion, followers, tier_of(followers),
                              int(abs(opinion) < MODERATE_THRESHOLD)])

    print(f"n={len(per_seed)}/{N_SEEDS} seeds found")
    if not per_seed:
        print("Nothing to summarize yet.")
        return

    RAW_OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(RAW_OUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["seed", "agentId", "opinion", "followerCount", "tier", "isModerate"])
        w.writerows(all_rows)
    print(f"Raw (all agents, all seeds): {RAW_OUT}")

    print("\n=== Per-tier summary (mean +/- sd across seeds) ===")
    summary_rows = []
    for name, lo, hi in TIERS:
        sizes, mods, mean_ops, mean_fols = [], [], [], []
        for seed, rows in per_seed.items():
            in_tier = [(a, op, fo) for a, op, fo in rows if lo < fo <= hi]
            sizes.append(len(in_tier))
            n_neutral = sum(1 for _, op, _ in in_tier if abs(op) < MODERATE_THRESHOLD)
            mods.append(n_neutral)
            if in_tier:
                mean_ops.append(np.mean([abs(op) for _, op, _ in in_tier]))
                mean_fols.append(np.mean([fo for _, _, fo in in_tier]))
        sizes = np.array(sizes); mods = np.array(mods)
        frac_mod = mods / np.maximum(sizes, 1)
        print(f"{name:>6} (followerCount {'>' + str(lo) if lo >= 0 else '<=' + str(hi)}"
              f"{', <=' + str(hi) if lo >= 0 else ''}): "
              f"tier_size={sizes.mean():.1f}+/-{sizes.std():.1f}  "
              f"n_moderate={mods.mean():.1f}+/-{mods.std():.1f}  "
              f"frac_moderate={frac_mod.mean():.2f}+/-{frac_mod.std():.2f}  "
              f"mean|opinion|={np.mean(mean_ops) if mean_ops else float('nan'):.3f}  "
              f"mean_followers={np.mean(mean_fols) if mean_fols else float('nan'):.1f}")
        summary_rows.append([name, lo, hi, sizes.mean(), sizes.std(), mods.mean(), mods.std(),
                              frac_mod.mean(), frac_mod.std(),
                              np.mean(mean_ops) if mean_ops else None,
                              np.mean(mean_fols) if mean_fols else None])

    with open(SUMMARY_OUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["tier", "lo_exclusive", "hi_inclusive", "mean_tier_size", "sd_tier_size",
                     "mean_n_moderate", "sd_n_moderate", "mean_frac_moderate", "sd_frac_moderate",
                     "mean_abs_opinion", "mean_followers"])
        w.writerows(summary_rows)
    print(f"\nSummary: {SUMMARY_OUT}")

    # Detail listing for mega + mid tiers (small enough to enumerate individually; tail isn't)
    for name in ("mega", "mid"):
        print(f"\n=== {name} tier, individual hubs (all seeds) ===")
        for seed, rows in per_seed.items():
            lo, hi = dict((t[0], (t[1], t[2])) for t in TIERS)[name]
            hits = sorted([(a, op, fo) for a, op, fo in rows if lo < fo <= hi], key=lambda t: -t[2])
            for a, op, fo in hits:
                mod_flag = "MODERATE" if abs(op) < MODERATE_THRESHOLD else ""
                print(f"  seed={seed} agent={a} followers={fo} opinion={op:+.3f} {mod_flag}")


if __name__ == "__main__":
    main()
