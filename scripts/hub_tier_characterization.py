"""
Hub-tier characterization (2026-07-21): descriptive, multi-seed run to establish a robust picture
of how many MODERATE hubs naturally occur at each in-degree tier -- not a causal treatment/control
experiment. Motivated by the deleted single-seed 920000 snapshot (docs/report/2026-07-18-joint-
stage-calibration.md's "Hub-swap causal experiment" section), whose specific agent IDs/values no
longer exist on disk (results/ was purged before the v7 calibration run) and which was only ever
one stochastic realization anyway -- not evidence of a typical/robust tier profile.

Runs N_SEEDS fresh (network=hk) simulations at the current calibrated defaults (2026-07-20 static-bc
adoption: bc_dec=1.0, bc_recovery=0.0, bc_init=0.56, comfort_pp=0.5, hop=1, max_pp=1.0, plus the v1
dims max_follow=57/follow_prob=0.009/alpha=0.76/feed_capacity=15/initial_pp=0.21/stub=0.69,
out_of_bc_repost_prob=0.0 unchanged), n=1000, steps=20000. Reads the per-agent
`degrees/agent_snapshot_final.csv` (agentId, opinion, followerCount, ...) that every run already
writes unconditionally (Writer.writeAgentSnapshot, OpinionDynamics.java:321) -- no log_gexf needed.

For each seed: rank agents by followerCount (in-degree) descending, assign to tiers by rank:
  top      = rank 1
  semi_top = ranks 2-5
  mid      = ranks 6-20
  low_mid  = ranks 21-50
"moderate" = |opinion| < MODERATE_THRESHOLD (0.2, matching the threshold used to select the 11
mid-tier swap candidates in the 2026-07-20 hub-swap series).

Outputs:
  docs/report/hub_tier_characterization_raw.csv   -- long format, one row per (seed, rank<=50)
  docs/report/hub_tier_characterization_summary.csv -- per-tier aggregate across seeds

Usage: python3 scripts/hub_tier_characterization.py
"""
import concurrent.futures
import csv
import subprocess
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
LIBCP = ":".join(str(p) for p in ROOT.glob("lib/*.jar")) + (":" if list(ROOT.glob("lib/*.jar")) else "") + str(ROOT / "bin")
N = 1000
STEPS = 20000
N_SEEDS = 20
BASE_SEED = 990000
MODERATE_THRESHOLD = 0.2
MAX_RANK = 50

TIERS = [
    ("top", 1, 1),
    ("semi_top", 2, 5),
    ("mid", 6, 20),
    ("low_mid", 21, 50),
]

FIXED = dict(max_follow=57, follow_prob=0.009, alpha=0.76, hop=1, bc_dec=1.0, bc_recovery=0.0,
             bc_init=0.56, stub=0.69, comfort_pp=0.5, feed_capacity=15, initial_pp=0.21,
             max_pp=1.0, out_of_bc_repost_prob=0.0)

RAW_LOG = ROOT / "docs" / "report" / "hub_tier_characterization_raw.csv"
SUMMARY_LOG = ROOT / "docs" / "report" / "hub_tier_characterization_summary.csv"


def launch(seed):
    tokens = [
        f"seed={seed}", "network=hk", f"n={N}", f"steps={STEPS}", "log_gexf=false",
        f"max_follow={FIXED['max_follow']}", f"follow_prob={FIXED['follow_prob']}",
        f"alpha={FIXED['alpha']}", f"hop={FIXED['hop']}",
        f"bc_dec={FIXED['bc_dec']:.6f}", f"bc_recovery={FIXED['bc_recovery']:.6f}",
        f"bc_init={FIXED['bc_init']:.6f}",
        "stub_dist=uniform", f"stub_min={FIXED['stub']}", f"stub_max={FIXED['stub']}",
        f"comfort_pp={FIXED['comfort_pp']:.6f}", f"feed_capacity={FIXED['feed_capacity']}",
        f"initial_pp={FIXED['initial_pp']}", f"max_pp={FIXED['max_pp']}",
        f"out_of_bc_repost_prob={FIXED['out_of_bc_repost_prob']}", "force=true",
    ]
    logfile = ROOT / "logs" / f"hubtier_seed{seed}.log"
    logfile.parent.mkdir(exist_ok=True)
    with open(logfile, "w") as lf:
        p = subprocess.Popen(
            ["java", "-Xmx2g", "-cp", LIBCP, "dynamics.OpinionDynamics", *tokens],
            stdout=lf, stderr=subprocess.STDOUT, cwd=ROOT,
        )
    return p


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
    rows.sort(key=lambda t: -t[2])  # descending by followerCount = in-degree
    return rows  # [(agentId, opinion, followerCount), ...] rank = index+1


def evaluate_seed(seed):
    p = launch(seed)
    p.wait()
    return seed, read_snapshot(seed)


def tier_of(rank):
    for name, lo, hi in TIERS:
        if lo <= rank <= hi:
            return name
    return None


def main():
    seeds = [BASE_SEED + j for j in range(N_SEEDS)]
    print(f"Launching {N_SEEDS} seeds ({seeds[0]}-{seeds[-1]}), n={N}, steps={STEPS}...", flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=N_SEEDS) as ex:
        results = list(ex.map(evaluate_seed, seeds))

    ok = [(s, rows) for s, rows in results if rows is not None]
    print(f"n={len(ok)}/{N_SEEDS} succeeded", flush=True)

    raw_rows = []
    for seed, rows in ok:
        for rank, (agent_id, opinion, followers) in enumerate(rows[:MAX_RANK], start=1):
            raw_rows.append([seed, rank, tier_of(rank), agent_id, opinion, followers,
                              int(abs(opinion) < MODERATE_THRESHOLD)])

    RAW_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(RAW_LOG, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["seed", "rank", "tier", "agentId", "opinion", "followerCount", "isModerate"])
        writer.writerows(raw_rows)
    print(f"Raw log: {RAW_LOG}")

    # Per-rank aggregate (mean/sd of opinion, followerCount, fraction-moderate across seeds)
    by_rank = {}
    for row in raw_rows:
        seed, rank, tier, agent_id, opinion, followers, is_mod = row
        by_rank.setdefault(rank, []).append((opinion, followers, is_mod))

    print("\n=== Per-rank profile (mean +/- sd across seeds) ===")
    print(f"{'rank':>4} {'tier':>9} {'mean_inDeg':>11} {'sd_inDeg':>9} {'mean_op':>8} {'sd_op':>7} {'frac_moderate':>13}")
    for rank in range(1, MAX_RANK + 1):
        vals = by_rank.get(rank, [])
        if not vals:
            continue
        ops = np.array([v[0] for v in vals])
        fols = np.array([v[1] for v in vals])
        mods = np.array([v[2] for v in vals])
        print(f"{rank:>4} {tier_of(rank):>9} {fols.mean():>11.1f} {fols.std():>9.1f} "
              f"{ops.mean():>8.3f} {ops.std():>7.3f} {mods.mean():>13.2f}")

    # Per-tier aggregate: count of neutral hubs within tier, per seed, then mean/sd across seeds
    summary_rows = []
    print("\n=== Per-tier neutral-hub count (per seed, then aggregated) ===")
    for name, lo, hi in TIERS:
        tier_size = hi - lo + 1
        counts = []
        for seed, rows in ok:
            in_tier = rows[lo - 1:hi] if len(rows) >= lo else []
            n_neutral = sum(1 for _, op, _ in in_tier if abs(op) < MODERATE_THRESHOLD)
            counts.append(n_neutral)
        counts = np.array(counts)
        print(f"{name:>9} (ranks {lo}-{hi}, size {tier_size}): moderate count = "
              f"{counts.mean():.2f} +/- {counts.std():.2f}  (out of {tier_size}), "
              f"per-seed: {counts.tolist()}")
        summary_rows.append([name, lo, hi, tier_size, counts.mean(), counts.std()] + counts.tolist())

    with open(SUMMARY_LOG, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["tier", "rank_lo", "rank_hi", "tier_size", "mean_moderate_count",
                          "sd_moderate_count"] + [f"seed_{s}" for s, _ in ok])
        writer.writerows(summary_rows)
    print(f"\nSummary log: {SUMMARY_LOG}")


if __name__ == "__main__":
    main()
