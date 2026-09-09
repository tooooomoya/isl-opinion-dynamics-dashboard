"""
2026-07-31 -- Composition ratio of each moderate-hub tier's PARTICIPATION across EVERY cascade
(not restricted to cross-cutting ones, unlike the earlier composition-ratio check in
docs/report/2026-07-21-conduit-experiment-design.md). Answers: of all repost cascades in the
control arm, what fraction have at least one relayer belonging to each moderate tier
(mega/middle/small/peripheral), vs. cascades relayed entirely by non-moderate (extreme,
|opinion|>=0.2) agents?

Data: control arm, seeds 9200000-9200009 (alpha=0.7, current-config point, viaAlgo-instrumented
repost_cascades.csv). Tier definitions identical to scripts/moderate_hub_4tier_removehub.py
(mega>300, middle 30-300, small 3-30, peripheral 0-3 followers, |opinion|<0.2, classified from
agent_snapshot_final.csv -- static end-of-run classification, same convention used for hub
selection throughout this doc). Cascade population selected the same way as the necessity/
composition checks earlier in the doc: cascades whose depth==1 event step falls in (10000,19000],
then look at the FULL relayer set for that rootPostId across all depths/steps (no per-row step
restriction beyond that selection).

Categories are NOT mutually exclusive -- a cascade's relayer chain can touch multiple tiers.
"none" = relayed exclusively by non-moderate/extreme agents (no moderate-tier relayer at all).
"""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEEDS = [9200000 + i for i in range(10)]
MODERATE_THRESHOLD = 0.2
TIERS = {
    "mega": (300, float("inf")),
    "middle": (30, 300),
    "small": (3, 30),
    "peripheral": (0, 3),
}
WINDOW = (10000, 19000)


def result_dir(seed):
    cands = sorted(ROOT.glob(f"results/run_{seed}_*"), key=lambda p: p.stat().st_mtime)
    return cands[-1] if cands else None


def classify_agents(d):
    """agentId -> tier name or None (extreme / not moderate)."""
    cls = {}
    with open(d / "degrees" / "agent_snapshot_final.csv", newline="") as f:
        for r in csv.DictReader(f):
            aid = int(r["agentId"])
            op, fo = float(r["opinion"]), int(r["followerCount"])
            if abs(op) >= MODERATE_THRESHOLD:
                cls[aid] = None
                continue
            tier = None
            for name, (lo, hi) in TIERS.items():
                if lo < fo <= hi:
                    tier = name
                    break
            cls[aid] = tier
    return cls


def main():
    totals = {"n_cascades": 0}
    for t in TIERS:
        totals[t] = 0
    totals["none"] = 0
    per_seed_rows = []

    for seed in SEEDS:
        d = result_dir(seed)
        cls = classify_agents(d)

        depth1_step = {}   # rootPostId -> step of its depth==1 event
        relayers = {}       # rootPostId -> set(relayerId)
        with open(d / "posts" / "repost_cascades.csv", newline="") as f:
            for r in csv.DictReader(f):
                root = int(r["rootPostId"])
                depth = int(r["depth"])
                step = int(r["step"])
                relayer = int(r["relayer"])
                relayers.setdefault(root, set()).add(relayer)
                if depth == 1:
                    depth1_step[root] = step

        selected = [root for root, s in depth1_step.items() if WINDOW[0] < s <= WINDOW[1]]

        seed_counts = {t: 0 for t in TIERS}
        seed_none = 0
        for root in selected:
            tiers_present = {cls.get(rid) for rid in relayers[root]}
            tiers_present.discard(None)
            if not tiers_present:
                seed_none += 1
                totals["none"] += 1
            for t in tiers_present:
                seed_counts[t] += 1
                totals[t] += 1
        totals["n_cascades"] += len(selected)

        n = len(selected) if selected else 1
        row = {"seed": seed, "n_cascades": len(selected),
               **{t: seed_counts[t] / n for t in TIERS},
               "none": seed_none / n}
        per_seed_rows.append(row)
        print(f"seed={seed}: n_cascades={len(selected)}  "
              + "  ".join(f"{t}={seed_counts[t]/n:.4f}" for t in TIERS)
              + f"  none={seed_none/n:.4f}")

    n = totals["n_cascades"]
    print(f"\n=== pooled across {len(SEEDS)} seeds, n_cascades={n} ===")
    for t in TIERS:
        print(f"  {t:>10}: {totals[t]/n:.4f}  ({totals[t]}/{n})")
    print(f"  {'none':>10}: {totals['none']/n:.4f}  ({totals['none']}/{n})")

    import statistics
    print("\n=== mean +/- sd across seeds (unweighted) ===")
    for t in list(TIERS) + ["none"]:
        vals = [row[t] for row in per_seed_rows]
        print(f"  {t:>10}: {statistics.mean(vals):.4f} +/- {statistics.stdev(vals):.4f}")

    log_path = ROOT / "docs" / "report" / "cascade_moderate_tier_composition.csv"
    with open(log_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["seed", "n_cascades"] + list(TIERS) + ["none"])
        for row in per_seed_rows:
            w.writerow([row["seed"], row["n_cascades"]] + [row[t] for t in TIERS] + [row["none"]])
    print(f"\nFull log: {log_path}")


if __name__ == "__main__":
    main()
