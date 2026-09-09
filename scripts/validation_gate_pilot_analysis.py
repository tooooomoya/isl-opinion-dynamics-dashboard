"""
Validation-gate pilot analysis (docs/report/2026-07-08-validation-gate-pilot.md).

Answers, per run, the Step-2 gate criteria under the 2026-07-08 Type-1/Type-2 redefinition:
  1. Do structural-separation metrics (opinionAssortativity / crossCuttingFraction /
     signModularity) plateau by t_max, or are they still trending?
  2. Do the pinned hubs retain mid-scale follower counts at t_max (not winner-take-all decay,
     not collapse)?
  3. Hub-attributable cross-camp bridging: among repost cascades where the neutral hub appears
     in the relay ancestry, what fraction reach an agent whose final-opinion camp is opposite the
     root (extreme-hub) source's camp? Compared across n_neutral in {0,1} and network type.

Usage: python3 scripts/validation_gate_pilot_analysis.py [results_dir] [steps] [min_seed] [max_seed]
(defaults: results_dir="results", steps=15000, seeds 100-102 — pass steps=30000 min_seed=100
max_seed=104 for the v2 re-run at n=500/steps=30000/5 seeds)
"""
import sys
import re
from pathlib import Path

import pandas as pd
import numpy as np

RESULTS_DIR = Path(sys.argv[1] if len(sys.argv) > 1 else "results")
PILOT_STEPS = int(sys.argv[2]) if len(sys.argv) > 2 else 15000
_min_seed = int(sys.argv[3]) if len(sys.argv) > 3 else 100
_max_seed = int(sys.argv[4]) if len(sys.argv) > 4 else 102
PILOT_SEEDS = set(range(_min_seed, _max_seed + 1))


def find_pilot_runs(results_dir: Path):
    runs = []
    for d in sorted(results_dir.iterdir()):
        if not d.is_dir() or not d.name.startswith("run_"):
            continue
        m = re.match(r"run_(\d+)_", d.name)
        if not m:
            continue
        seed = int(m.group(1))
        if seed not in PILOT_SEEDS:
            continue
        if f"_n-500_st-{PILOT_STEPS}" not in d.name:
            continue
        nw_m = re.search(r"_nw-(\w+)", d.name)
        nw = nw_m.group(1) if nw_m else "dcsbm"
        nmod_m = re.search(r"_nmod-(\d+)", d.name)
        nmod = int(nmod_m.group(1)) if nmod_m else None
        runs.append({"folder": d, "seed": seed, "network": nw, "n_neutral": nmod})
    return runs


def gate1_plateau(folder: Path):
    """Structural-separation trend at t_max: compare mean over the last 20% of steps vs the
    preceding 20% window. |slope-like delta| small relative to overall spread => plateaued."""
    fp = folder / "metrics" / "results.csv"
    if not fp.exists():
        return {}
    df = pd.read_csv(fp)
    out = {}
    for col in ["opinionAssortativity", "crossCuttingFraction", "interactionCrossCuttingFraction"]:
        if col not in df.columns or len(df) < 10:
            continue
        n = len(df)
        tail = df[col].iloc[int(n * 0.8):]
        mid = df[col].iloc[int(n * 0.6):int(n * 0.8)]
        if len(tail) == 0 or len(mid) == 0:
            continue
        out[f"{col}_final"] = tail.mean()
        out[f"{col}_delta_last2windows"] = tail.mean() - mid.mean()
    mod_fp = folder / "metrics" / "modularity.csv"
    if mod_fp.exists():
        mdf = pd.read_csv(mod_fp)
        if len(mdf) > 0:
            out["signModularity_final"] = mdf.iloc[-1, -1]
    return out


def gate2_hub_scale(folder: Path):
    """t0 vs final follower counts for the pinned hubs (run_config.csv lists hub ids/roles;
    agent_snapshot csvs give followerCount at t0 and final). Keyed by ROLE, not hub id, so the
    columns line up across seeds/networks (hub ids differ every run)."""
    cfg_fp = folder / "run_config.csv"
    if not cfg_fp.exists():
        return {}
    cfg = pd.read_csv(cfg_fp)
    t0_fp = folder / "degrees" / "agent_snapshot_t0.csv"
    final_fp = folder / "degrees" / "agent_snapshot_final.csv"
    if not t0_fp.exists() or not final_fp.exists():
        return {}
    t0 = pd.read_csv(t0_fp).set_index("agentId")
    final = pd.read_csv(final_fp).set_index("agentId")
    out = {}
    role_key = {"extreme+": "extreme_pos", "extreme-": "extreme_neg", "moderate": "moderate"}
    for _, row in cfg.iterrows():
        hid = int(row["hub_id"])
        role = role_key.get(row["role"], row["role"])
        if hid in t0.index and hid in final.index:
            out[f"{role}_followers_t0"] = int(t0.loc[hid, "followerCount"])
            out[f"{role}_followers_final"] = int(final.loc[hid, "followerCount"])
    return out


def gate3_hub_bridging(folder: Path):
    """Hub-mediated cross-camp reach: walk repost_cascades.csv ancestry to find cascades the
    neutral hub touches as relayer, rooted at an extreme hub; compare relayer's camp AT THE TIME
    OF THE RELAY EVENT (relayerOpinion column, logged 2026-07-09) to the root's camp. Falls back to
    the final-snapshot proxy (noisy — see docs/report/2026-07-08-validation-gate-pilot.md) only for
    older cascade CSVs that predate the relayerOpinion column."""
    cfg_fp = folder / "run_config.csv"
    casc_fp = folder / "posts" / "repost_cascades.csv"
    final_fp = folder / "degrees" / "agent_snapshot_final.csv"
    if not (cfg_fp.exists() and casc_fp.exists()):
        return {}
    cfg = pd.read_csv(cfg_fp)
    mod_rows = cfg[cfg["role"] == "moderate"]
    if len(mod_rows) == 0:
        return {"hub_bridging_note": "no neutral hub in this run (n_neutral=0)"}
    hub_id = int(mod_rows.iloc[0]["hub_id"])
    extreme_ids = set(cfg[cfg["role"].isin(["extreme+", "extreme-"])]["hub_id"].astype(int))

    casc = pd.read_csv(casc_fp)
    if len(casc) == 0:
        return {"hub_bridging_note": "no cascades logged"}
    using_event_time_opinion = "relayerOpinion" in casc.columns
    final = pd.read_csv(final_fp).set_index("agentId") if (not using_event_time_opinion and final_fp.exists()) else None

    # postId -> relayer, for ancestry walk
    relayer_of = dict(zip(casc["postId"], casc["relayer"]))
    parent_of = dict(zip(casc["postId"], casc["parentPostId"]))

    def hub_in_ancestry(post_id):
        seen = 0
        pid = post_id
        while pid in relayer_of and seen < 50:
            if relayer_of[pid] == hub_id:
                return True
            pid = parent_of.get(pid, -1)
            seen += 1
        return False

    # Only cascades rooted at an extreme hub (source-extremity-fixed treatment).
    casc = casc[casc["author"].isin(extreme_ids)] if "author" in casc.columns else casc
    if len(casc) == 0:
        return {"hub_bridging_note": "no extreme-rooted cascades"}

    casc = casc.copy()
    casc["hub_mediated"] = casc["postId"].apply(hub_in_ancestry)
    hub_casc = casc[casc["hub_mediated"]]
    if len(hub_casc) == 0:
        return {"n_hub_mediated_cascades": 0}

    def camp_from_final_snapshot(agent_id):
        if final is None or agent_id not in final.index:
            return np.nan
        op = final.loc[agent_id, "opinion"]
        return np.sign(op) if op != 0 else 0.0

    # `casc` is already filtered to rows whose `author` is an extreme hub. Under the default
    # rel_attrib=original, `author` is preserved unchanged through the whole relay chain (that IS
    # the "conduit immunity" mechanism — research-direction.md §2), so each row's own `author`
    # field already tells us the source camp directly; no separate rootPostId join is needed (and
    # an earlier version's join was wrong: rootPostId/parentPostId identify the ORIGINAL post,
    # which is never itself a row in this file — only relay events are logged rows — so joining
    # against `postId` could never match and silently produced all-NaN root_camp).
    author_camp = {a: np.sign(cfg[cfg["hub_id"] == a]["assigned_opinion"].iloc[0]) for a in extreme_ids}
    hub_casc = hub_casc.copy()
    hub_casc["root_camp"] = hub_casc["author"].map(author_camp)
    if using_event_time_opinion:
        # Camp AT THE MOMENT of the relay (logged directly, no run-duration-dependent drift).
        hub_casc["relayer_camp"] = np.sign(hub_casc["relayerOpinion"]).replace(0, np.nan)
    else:
        hub_casc["relayer_camp"] = hub_casc["relayer"].map(camp_from_final_snapshot)
    valid = hub_casc.dropna(subset=["root_camp", "relayer_camp"])
    valid = valid[valid["relayer_camp"] != 0]
    if len(valid) == 0:
        return {"n_hub_mediated_cascades": len(hub_casc), "hub_cross_camp_fraction": np.nan}
    cross = (valid["root_camp"] * valid["relayer_camp"] < 0).mean()
    return {
        "n_hub_mediated_cascades": len(hub_casc),
        "n_hub_mediated_valid_camp": len(valid),
        "hub_cross_camp_fraction": cross,
        "camp_source": "event_time" if using_event_time_opinion else "final_snapshot_proxy",
    }


def main():
    runs = find_pilot_runs(RESULTS_DIR)
    if not runs:
        print(f"No pilot runs found under {RESULTS_DIR} "
              f"(looking for seeds {PILOT_SEEDS}, tag containing _n-500_st-15000).")
        return
    rows = []
    for r in runs:
        row = {"network": r["network"], "n_neutral": r["n_neutral"], "seed": r["seed"], "folder": r["folder"].name}
        row.update(gate1_plateau(r["folder"]))
        row.update(gate2_hub_scale(r["folder"]))
        row.update(gate3_hub_bridging(r["folder"]))
        rows.append(row)
    df = pd.DataFrame(rows).sort_values(["network", "n_neutral", "seed"])
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 50)
    out_csv = (RESULTS_DIR.parent / "docs" / "report"
               / f"2026-07-08-validation-gate-pilot-results_st{PILOT_STEPS}.csv")
    df.to_csv(out_csv, index=False)
    print(f"Wrote {len(df)} rows to {out_csv}\n")
    print(df.to_string(index=False))

    print("\n--- Gate 3 summary: hub_cross_camp_fraction by network x n_neutral (mean over seeds) ---")
    if "hub_cross_camp_fraction" in df.columns:
        summary = df.groupby(["network", "n_neutral"])["hub_cross_camp_fraction"].agg(["mean", "count"])
        print(summary)


if __name__ == "__main__":
    main()
