#!/usr/bin/env python3
"""Cross-tabulate existing eta runs by followers and X; no new simulations.

Primary |X| cutoffs are 1/3 and 2/3; repeat at 1/4 and 3/4.
Each agent receives equal weight within a cell, then seeds receive equal weight.
"""
import csv
import hashlib
import json
import math
import statistics
from pathlib import Path

from eta_role_by_position import ACTS, COLS, OUT, read, tier


def xbin(x, lo, hi, signed=False):
    if abs(x) < lo:
        return "central"
    label = "middle" if abs(x) < hi else "edge"
    return ("left_" if x < 0 else "right_") + label if signed else label


def summarize(ids, people):
    result = {"n_agents": len(ids)}
    for action in ACTS:
        result["share_"+action] = statistics.mean(people[i]["share_"+action] for i in ids)
    result["mean_abs_x"] = statistics.mean(abs(people[i]["x"]) for i in ids)
    result["mean_followers"] = statistics.mean(people[i]["followers"] for i in ids)
    result["mean_reward"] = statistics.mean(people[i]["mean_reward"] for i in ids)
    pairs = [people[i]["half_agreement"] for i in ids if people[i]["half_agreement"] is not None]
    result["half_agreement"] = statistics.mean(pairs) if pairs else None
    for action in ["post", "reshare"]:
        vals = [people[i]["gap_"+action+"_like"] for i in ids if people[i]["gap_"+action+"_like"] is not None]
        result["gap_"+action+"_like"] = statistics.median(vals) if vals else None
        result["gap_"+action+"_like_n_agents"] = len(vals)
    return result


def dump_csv(path, rows):
    with path.open("w") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)


def main():
    cells, individuals, graph_hashes, covariates = [], [], {}, {}
    for meta_path in sorted(OUT.glob("eta*.json")):
        meta = json.loads(meta_path.read_text())
        d = Path(meta["run_dir"])
        assert meta["tokens"]["rewire"] == "false"
        edges = sorted((int(r["follower"]), int(r["followee"])) for r in read(d / "degrees/edges_final.csv"))
        digest = hashlib.sha256(json.dumps(edges).encode()).hexdigest()
        seed, eta = meta["seed"], meta["eta"]
        assert graph_hashes.setdefault(seed, digest) == digest
        snap = {int(r["agentId"]): r for r in read(d / "degrees/agent_snapshot_final.csv")}
        assert all(r["opinion"] == r["intrinsicOpinion"] for r in snap.values()), "X drift requires a different stratification"
        cov = [(i, float(r["intrinsicOpinion"]), int(r["followerCount"])) for i, r in sorted(snap.items())]
        assert covariates.setdefault(seed, cov) == cov, "Agent X or degree differs across eta"
        totals = {i: [0, 0, 0] for i in snap}
        halves = {i: [[0, 0, 0], [0, 0, 0]] for i in snap}
        for r in read(d / "metrics/agent_actions.csv"):
            step = int(r["step"])
            if step <= 15000:
                continue
            i = int(r["agentId"])
            for a, c in enumerate(COLS):
                n = int(r[c]); totals[i][a] += n
                halves[i][int(step > 17500)][a] += n
        moments = {}
        for r in read(d / "metrics/eta_agents.csv"):
            if int(r["step"]) <= 15000:
                continue
            i = int(r["agentId"])
            v = moments.setdefault(i, {c: 0.0 for a in ACTS for c in ["nR_"+a, "sumR_"+a]})
            for c in v:
                v[c] += float(r[c])
        people = {}
        for i, r in snap.items():
            n = sum(totals[i])
            assert n > 0
            m = moments[i]
            person = {"eta": eta, "seed": seed, "agent_id": i,
                      "x": float(r["intrinsicOpinion"]), "followers": int(r["followerCount"]),
                      "tier": tier(int(r["followerCount"])), "n_visits": n}
            for a, action in enumerate(ACTS):
                person["share_"+action] = totals[i][a]/n
            h = halves[i]
            person["half_agreement"] = (int(max(range(3), key=lambda a: h[0][a]) == max(range(3), key=lambda a: h[1][a]))
                                        if min(map(sum, h)) >= 30 else None)
            person["mean_reward"] = sum(m["sumR_"+a] for a in ACTS)/sum(m["nR_"+a] for a in ACTS)
            for a in ["post", "reshare"]:
                person["gap_"+a+"_like"] = (m["sumR_"+a]/m["nR_"+a] - m["sumR_like"]/m["nR_like"]
                                            if min(m["nR_"+a], m["nR_like"]) >= 30 else None)
            people[i] = person
            individuals.append(person)
        for lo, hi, spec in [(1/3, 2/3, "thirds"), (0.25, 0.75, "quarters")]:
            for signed in [False, True]:
                groups = {}
                for i, p in people.items():
                    label = xbin(p["x"], lo, hi, signed)
                    for degree in [p["tier"], "ALL"]:
                        groups.setdefault((degree, label), []).append(i)
                for (degree, label), ids in groups.items():
                    cells.append({"eta": eta, "seed": seed, "cutoffs": spec, "signed": signed,
                                  "tier": degree, "x_group": label, **summarize(ids, people)})
    assert len(individuals) == 9000 and len(graph_hashes) == 3
    dump_csv(OUT / "position_x_individuals.csv", individuals)
    dump_csv(OUT / "position_x_cells.csv", cells)
    contrasts = []
    for eta in [0.1, 0.03, 0.01]:
        for seed in [0, 1, 2]:
            for degree in ["0", "1-4", "5-19", "20-49", "50+", "ALL"]:
                g = {r["x_group"]: r for r in cells if r["eta"] == eta and r["seed"] == seed
                     and r["cutoffs"] == "thirds" and not r["signed"] and r["tier"] == degree}
                row = {"eta": eta, "seed": seed, "tier": degree}
                for action in ACTS:
                    row[action+"_edge_minus_central"] = g["edge"]["share_"+action] - g["central"]["share_"+action]
                    row[action+"_middle_minus_central"] = g["middle"]["share_"+action] - g["central"]["share_"+action]
                contrasts.append(row)
    dump_csv(OUT / "position_x_contrasts.csv", contrasts)
    # Reconstruct the prior degree-only result from the X cells as an aggregation check.
    for previous in read(OUT / "position_roles.csv"):
        group = [r for r in cells if r["eta"] == float(previous["eta"]) and r["seed"] == int(previous["seed"])
                 and r["cutoffs"] == "thirds" and not r["signed"] and r["tier"] == previous["tier"]]
        n = sum(r["n_agents"] for r in group)
        assert n == int(previous["n_agents"])
        for action in ACTS:
            reconstructed = sum(r["n_agents"]*r["share_"+action] for r in group)/n
            assert abs(reconstructed-float(previous["share_"+action])) < 1e-12
    grouped = {}
    for r in cells:
        key = tuple(r[k] for k in ["eta", "cutoffs", "signed", "tier", "x_group"])
        grouped.setdefault(key, []).append(r)
    aggregate = []
    for key, rows in grouped.items():
        item = dict(zip(["eta", "cutoffs", "signed", "tier", "x_group"], key))
        item["n_seeds"] = len(rows)
        item["min_cell_n"] = min(r["n_agents"] for r in rows)
        for c in rows[0]:
            if c in ["eta", "seed", "cutoffs", "signed", "tier", "x_group"]:
                continue
            vals = [r[c] for r in rows if r[c] is not None and math.isfinite(r[c])]
            item[c] = statistics.mean(vals) if vals else None
            item[c+"_seed_sd"] = statistics.stdev(vals) if len(vals) > 1 else None
            item[c+"_valid_seeds"] = len(vals)
        aggregate.append(item)
    (OUT / "position_x_aggregate.json").write_text(json.dumps(aggregate, indent=2, allow_nan=False))
    for r in sorted(aggregate, key=lambda r: (r["tier"], r["x_group"])):
        if r["eta"] == 0.03 and r["cutoffs"] == "thirds" and not r["signed"]:
            print(r["tier"], r["x_group"], "minN", r["min_cell_n"],
                  "post/like/reshare", [round(r["share_"+a], 3) for a in ACTS],
                  "gapRS-like", round(r["gap_reshare_like"], 3) if r["gap_reshare_like"] is not None else None)
    print("Validated: 9000 agent-run records; same fixed X and edge sets across eta for each seed.")


if __name__ == "__main__":
    main()
