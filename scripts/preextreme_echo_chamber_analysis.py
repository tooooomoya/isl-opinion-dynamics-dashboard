"""
2026-07-30 -- Post-hoc analysis (no new simulation runs) on already-completed Phase 1b output
(scripts/moderate_hub_4tier_removehub.py: control seeds 9200000-9, remove_hub small
9430000-9, remove_hub peripheral 9440000-9), testing the user's echo-chamber-deformation
hypothesis for why removing small/peripheral moderate hubs DECREASES pre-extreme per-capita
posting (docs/report/2026-07-21-conduit-experiment-design.md, Phase 1/1b entries).

Part A -- pre-extreme-filtered triad, both directions, control vs remove_hub(small/peripheral):
  IN  (pre-extreme as relayer/receiver): rows where `relayer` is final-classified pre-extreme
      (opinion bins 1,3). crossCutting = sign(conveyedOpinion) != sign(relayerOpinion) (same
      definition as the codebase's own Q_sign_repost/crossRepostRate -- Agent.java's own repost()
      comment). assortativity = corr(conveyedOpinion, relayerOpinion) across these rows.
  OUT (pre-extreme as original author/source): rows where `author` (root content producer,
      stable across the whole cascade since rel_attrib=original) is pre-extreme. Same
      crossCutting/assortativity definitions, now describing how OTHERS relay pre-extreme content.
  bimodality: bimodality coefficient of the pre-extreme population's OWN final opinion values
      (not edge-based) -- tests whether pre-extreme agents split into two separated poles.
  Window: steps (15000, 20000] of each continuation (a "current regime" snapshot, not lifetime-
  cumulative, since population classification is based on final opinion).

Part B -- diffusion strength + conduit-to-pre-extreme check, CONTROL arm only (characterizes the
agents that get removed in the treatment arms, before removal):
  For each control seed, derive the same moderate-small/moderate-peripheral agent id lists used by
  the 4-tier removal script (from the corresponding EQUILIBRIUM seed's final snapshot -- identical
  ids, since remove_hub continuations start from the same equilibrium). For relay events in a
  source window (10000, 19900] (leaves room to observe onward propagation within
  VELOCITY_WINDOW=100 without truncation at the log's end):
    reach_rate    = fraction of this group's relay events whose resulting post is itself reposted
                    at least once more (postId appears as some later row's parentPostId).
    preext_given_reach = of those that DID propagate onward, fraction whose next-hop relayer is
                    pre-extreme-classified.
  Compared against the population baseline (all relayers, not just the moderate small/peripheral
  group) to test whether these specific agents disproportionately channel content to pre-extremes.

Usage: python3 scripts/preextreme_echo_chamber_analysis.py
"""
import csv
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent

EQUIL_BASE_SEED = 9100000
CONTROL_BASE_SEED = 9200000
REMOVE_HUB_BASE = {"small": 9430000, "peripheral": 9440000}
N_SEEDS = 10
MODERATE_THRESHOLD = 0.2
TIERS = {"small": (3, 30), "peripheral": (0, 3)}
WINDOW_A = (15000, 20000)
WINDOW_B = (10000, 19900)


def result_dir(seed):
    cands = sorted(ROOT.glob(f"results/run_{seed}_*"))
    return cands[-1] if cands else None


def opinion_class(op):
    return min(int((op + 1.0) / 0.4), 4)


def load_final_state(seed):
    d = result_dir(seed)
    opinions, followers = {}, {}
    with open(d / "degrees" / "agent_snapshot_final.csv", newline="") as f:
        for r in csv.DictReader(f):
            aid = int(r["agentId"])
            opinions[aid] = float(r["opinion"])
            followers[aid] = int(r["followerCount"])
    return opinions, followers


def moderate_hub_ids_from_equil(equil_seed, tier):
    d = result_dir(equil_seed)
    lo, hi = TIERS[tier]
    hits = []
    with open(d / "degrees" / "agent_snapshot_final.csv", newline="") as f:
        for r in csv.DictReader(f):
            op, fo = float(r["opinion"]), int(r["followerCount"])
            if lo < fo <= hi and abs(op) < MODERATE_THRESHOLD:
                hits.append(int(r["agentId"]))
    return hits


def cross_and_assort(df):
    if len(df) < 10:
        return np.nan, np.nan, len(df)
    cross = float((np.sign(df["conveyedOpinion"]) * np.sign(df["relayerOpinion"]) < 0).mean())
    assort = float(df["conveyedOpinion"].corr(df["relayerOpinion"]))
    return cross, assort, len(df)


def bimodality_coeff(values):
    values = np.asarray(values, dtype=float)
    n = len(values)
    if n < 10:
        return np.nan
    m = values.mean()
    s = values.std(ddof=1)
    if s == 0:
        return np.nan
    skew = ((values - m) ** 3).mean() / s ** 3
    kurt = ((values - m) ** 4).mean() / s ** 4
    return (skew ** 2 + 1) / (kurt + 3 * (n - 1) ** 2 / ((n - 2) * (n - 3)))


def part_a():
    print("=== PART A: pre-extreme-filtered triad, control vs remove_hub(small/peripheral) ===\n")
    rows = []
    arms = [("control", CONTROL_BASE_SEED)] + [(f"remove_hub_{t}", b) for t, b in REMOVE_HUB_BASE.items()]
    for arm, base in arms:
        for i in range(N_SEEDS):
            seed = base + i
            opinions, _ = load_final_state(seed)
            classes = {a: opinion_class(op) for a, op in opinions.items()}
            pre_extreme_ids = {a for a, c in classes.items() if c in (1, 3)}
            d = result_dir(seed)
            df = pd.read_csv(d / "posts" / "repost_cascades.csv",
                              usecols=["step", "author", "relayer", "conveyedOpinion", "relayerOpinion"])
            dfw = df[(df["step"] > WINDOW_A[0]) & (df["step"] <= WINDOW_A[1])]
            in_df = dfw[dfw["relayer"].isin(pre_extreme_ids)]
            out_df = dfw[dfw["author"].isin(pre_extreme_ids)]
            cross_in, assort_in, n_in = cross_and_assort(in_df)
            cross_out, assort_out, n_out = cross_and_assort(out_df)
            bimodal = bimodality_coeff([opinions[a] for a in pre_extreme_ids])
            rows.append(dict(arm=arm, seed=seed, n_preextreme=len(pre_extreme_ids),
                              cross_in=cross_in, assort_in=assort_in, n_in=n_in,
                              cross_out=cross_out, assort_out=assort_out, n_out=n_out,
                              bimodal=bimodal))

    df_all = pd.DataFrame(rows)
    log_path = ROOT / "docs" / "report" / "preextreme_echo_chamber_analysis.csv"
    df_all.to_csv(log_path, index=False)
    print(f"Full per-seed log: {log_path}\n")

    metrics = ["cross_in", "assort_in", "cross_out", "assort_out", "bimodal"]
    for arm in ["remove_hub_small", "remove_hub_peripheral"]:
        print(f"\n--- {arm} vs control (n=10 paired by seed offset) ---")
        c = df_all[df_all.arm == "control"].reset_index(drop=True)
        t = df_all[df_all.arm == arm].reset_index(drop=True)
        for m in metrics:
            cv, tv = c[m].values, t[m].values
            mask = ~(np.isnan(cv) | np.isnan(tv))
            cv, tv = cv[mask], tv[mask]
            if len(cv) < 2:
                print(f"  {m:>10}: insufficient data")
                continue
            diff = tv - cv
            tstat = diff.mean() / (diff.std(ddof=1) / np.sqrt(len(diff))) if diff.std(ddof=1) > 0 else float("nan")
            print(f"  {m:>10}: control={cv.mean():.4f}+/-{cv.std():.4f}  {arm}={tv.mean():.4f}+/-{tv.std():.4f}  "
                  f"diff={diff.mean():+.4f}  t={tstat:.2f}  n={len(cv)}")


def part_b():
    print("\n\n=== PART B: diffusion reach + conduit-to-pre-extreme check (control arm only) ===\n")
    rows = []
    for i in range(N_SEEDS):
        equil_seed = EQUIL_BASE_SEED + i
        control_seed = CONTROL_BASE_SEED + i
        opinions, _ = load_final_state(control_seed)
        classes = {a: opinion_class(op) for a, op in opinions.items()}
        pre_extreme_ids = {a for a, c in classes.items() if c in (1, 3)}

        small_ids = set(moderate_hub_ids_from_equil(equil_seed, "small"))
        peripheral_ids = set(moderate_hub_ids_from_equil(equil_seed, "peripheral"))

        d = result_dir(control_seed)
        df = pd.read_csv(d / "posts" / "repost_cascades.csv",
                          usecols=["step", "postId", "parentPostId", "relayer"])
        children_parent_ids = set(df["parentPostId"].unique())

        # for each parentPostId, does at least one child relayer land in pre_extreme_ids?
        child_hits = df.groupby("parentPostId")["relayer"].apply(
            lambda s: any(r in pre_extreme_ids for r in s))

        src = df[(df["step"] > WINDOW_B[0]) & (df["step"] <= WINDOW_B[1])].copy()
        src["propagated"] = src["postId"].isin(children_parent_ids)
        src["preext_next"] = src["postId"].map(child_hits).fillna(False)

        def group_stats(mask):
            g = src[mask]
            n = len(g)
            if n == 0:
                return dict(n=0, reach_rate=np.nan, preext_given_reach=np.nan)
            reach_rate = g["propagated"].mean()
            reached = g[g["propagated"]]
            preext_given_reach = reached["preext_next"].mean() if len(reached) > 0 else np.nan
            return dict(n=n, reach_rate=float(reach_rate), preext_given_reach=float(preext_given_reach))

        overall = group_stats(pd.Series(True, index=src.index))
        small_stats = group_stats(src["relayer"].isin(small_ids))
        peripheral_stats = group_stats(src["relayer"].isin(peripheral_ids))

        rows.append(dict(seed=control_seed,
                          overall_n=overall["n"], overall_reach=overall["reach_rate"], overall_preext=overall["preext_given_reach"],
                          small_n=small_stats["n"], small_reach=small_stats["reach_rate"], small_preext=small_stats["preext_given_reach"],
                          peripheral_n=peripheral_stats["n"], peripheral_reach=peripheral_stats["reach_rate"], peripheral_preext=peripheral_stats["preext_given_reach"]))
        print(f"  seed={control_seed}: overall reach={overall['reach_rate']:.4f} (n={overall['n']}), "
              f"preext|reach={overall['preext_given_reach']:.4f} | "
              f"small reach={small_stats['reach_rate']:.4f} (n={small_stats['n']}), preext|reach={small_stats['preext_given_reach']:.4f} | "
              f"peripheral reach={peripheral_stats['reach_rate']:.4f} (n={peripheral_stats['n']}), preext|reach={peripheral_stats['preext_given_reach']:.4f}",
              flush=True)

    df_b = pd.DataFrame(rows)
    log_path = ROOT / "docs" / "report" / "preextreme_conduit_reach.csv"
    df_b.to_csv(log_path, index=False)
    print(f"\nFull per-seed log: {log_path}\n")

    print("--- Aggregate (mean +/- sd across 10 seeds) ---")
    for label, reach_col, preext_col in [("overall", "overall_reach", "overall_preext"),
                                          ("moderate-small", "small_reach", "small_preext"),
                                          ("moderate-peripheral", "peripheral_reach", "peripheral_preext")]:
        r = df_b[reach_col].dropna()
        p = df_b[preext_col].dropna()
        print(f"  {label:>20}: reach_rate={r.mean():.4f}+/-{r.std():.4f}  preext_given_reach={p.mean():.4f}+/-{p.std():.4f}")


if __name__ == "__main__":
    part_a()
    part_b()
