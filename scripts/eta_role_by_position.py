#!/usr/bin/env python3
"""Describe action shares by static follower-count tier in eta_noise_compare runs.

No new simulations. Roles are observed action proportions, not assigned labels.
"""
import csv
import hashlib
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/eta_noise_compare"
ACTS = ["post", "like", "reshare"]
COLS = ["nPost", "nLike", "nReshare"]
TIERS = ["0", "1-4", "5-19", "20-49", "50+"]


def tier(n):
    return "0" if n == 0 else "1-4" if n < 5 else "5-19" if n < 20 else "20-49" if n < 50 else "50+"


def read(p):
    with p.open() as f:
        return list(csv.DictReader(f))


def main():
    records, graph_hashes = [], {}
    for meta_file in sorted(OUT.glob("eta*.json")):
        meta = json.loads(meta_file.read_text())
        d = Path(meta["run_dir"])
        assert meta["tokens"]["rewire"] == "false"
        # Likes/reshares reorder followee queues even with rewire off. Compare edge
        # sets, not CSV row order, when checking that the graph itself is fixed.
        edges = sorted((int(r["follower"]), int(r["followee"]))
                       for r in read(d / "degrees/edges_final.csv"))
        digest = hashlib.sha256(json.dumps(edges).encode()).hexdigest()
        seed = meta["seed"]
        assert seed not in graph_hashes or graph_hashes[seed] == digest, "Graphs differ across eta"
        graph_hashes[seed] = digest
        snap = {int(r["agentId"]): r for r in read(d / "degrees/agent_snapshot_final.csv")}
        totals = {i: [0, 0, 0] for i in snap}
        halves = {i: [[0, 0, 0], [0, 0, 0]] for i in snap}
        for r in read(d / "metrics/agent_actions.csv"):
            step = int(r["step"])
            if step <= 15000:
                continue
            i = int(r["agentId"])
            for a, c in enumerate(COLS):
                n = int(r[c])
                totals[i][a] += n
                halves[i][int(step > 17500)][a] += n
        moments = {}
        for r in read(d / "metrics/eta_agents.csv"):
            if int(r["step"]) <= 15000:
                continue
            i = int(r["agentId"])
            v = moments.setdefault(i, {c: 0.0 for a in ACTS for c in ["nR_"+a, "sumR_"+a]})
            for c in v:
                v[c] += float(r[c])
        for label in TIERS:
            ids = [i for i in snap if tier(int(snap[i]["followerCount"])) == label and sum(totals[i])]
            if not ids:
                continue
            row = {"eta": meta["eta"], "seed": seed, "tier": label, "n_agents": len(ids)}
            row["mean_followers"] = statistics.mean(int(snap[i]["followerCount"]) for i in ids)
            ps = [[n / sum(totals[i]) for n in totals[i]] for i in ids]
            for a, action in enumerate(ACTS):
                row["share_"+action] = statistics.mean(p[a] for p in ps)
            agreements = []
            for i in ids:
                h = halves[i]
                if min(map(sum, h)) >= 30:
                    agreements.append(max(range(3), key=lambda a: h[0][a]) == max(range(3), key=lambda a: h[1][a]))
            row["dominant_half_agreement"] = statistics.mean(agreements) if agreements else float("nan")
            for a in ["post", "reshare"]:
                diffs = [moments[i]["sumR_"+a]/moments[i]["nR_"+a] - moments[i]["sumR_like"]/moments[i]["nR_like"]
                         for i in ids if min(moments[i]["nR_"+a], moments[i]["nR_like"]) >= 30]
                row["reward_gap_"+a+"_like"] = statistics.median(diffs) if diffs else float("nan")
                row["reward_gap_"+a+"_like_n_agents"] = len(diffs)
            records.append(row)
    assert len(graph_hashes) == 3 and len(records) == 45
    with (OUT / "position_roles.csv").open("w") as f:
        w = csv.DictWriter(f, fieldnames=list(records[0])); w.writeheader(); w.writerows(records)
    aggregate = []
    for eta in [0.1, 0.03, 0.01]:
        for label in TIERS:
            group = [r for r in records if r["eta"] == eta and r["tier"] == label]
            row = {"eta": eta, "tier": label, "n_seeds": len(group)}
            for k in records[0]:
                if k not in ("eta", "seed", "tier"):
                    row[k] = statistics.mean(r[k] for r in group)
                    row[k+"_seed_sd"] = statistics.stdev(r[k] for r in group)
            aggregate.append(row)
            print(eta, label, "n=", round(row["n_agents"], 1),
                  "post/like/reshare=", [round(row["share_"+a], 3) for a in ACTS],
                  "half agreement=", round(row["dominant_half_agreement"], 3))
    (OUT / "position_roles.json").write_text(json.dumps(aggregate, indent=2))
    (OUT / "position_graph_hashes.json").write_text(json.dumps(graph_hashes, indent=2))
    print("All three seeds have identical static graphs across eta.")


if __name__ == "__main__":
    main()
