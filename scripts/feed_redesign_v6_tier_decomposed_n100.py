"""
2026-07-29 -- v6: extends v5's n=100 control-seed dose-response check with follower-count TIER
decomposition. v5 only split by opinion class (moderate/extreme) crossed with a single "top" cutoff
(fc>100). This was a known open gap: docs/report/2026-07-21-conduit-experiment-design.md's original
2026-07-28 dose-response work flagged "the follower-stratum decomposition (top>100 vs mid 50-100 vs
small 10-50 vs peripheral<=10) was inconclusive at n=20 (partial correlations noisy, CIs wide)" --
under-powered, never resolved (n=100 was extended for exactly this, but that specific decomposition
was never actually re-run at n=100). User's question (2026-07-29): how do small hubs / peripheral
agents correlate with polarization metrics, not just top-tier hubs.

v5's underlying results/ were already cleaned up (disposable per project policy, conclusions
recorded) so this reruns 100 FRESH control seeds (new seed range) rather than depending on the old
one, same provisional feed-mechanism point (v4 winner: hop=4, feed_decay_mode=exp,
feed_decay_lambda~0.11, alpha=0.7, feed_time_decay_tau=30). n=1000, steps=20000, network=hk.

T0 predictors: v5's original 6 (reach_mod_all, mod_pop_share, reach_mod_top [fc>100], n_mod_top,
reach_ext_top [fc>100], n_ext_top) PLUS 16 new tier-decomposed ones -- for BOTH moderate
(|opinion|<0.2) and extreme (|opinion|>=0.6) classes, reach/n in each of 4 follower-count tiers:
top (>100), mid (50-100], small (10-50], peripheral (<=10) -- matching the tier boundaries named in
scripts/extend_control_equilibria.py's docstring. Plus reach_ext_all/ext_pop_share for symmetry with
the moderate "_all" predictors.

Outcomes/analysis unchanged from v5: SF1, crossCuttingFraction, opinionAssortativity, Q_sign_repost,
bimodalityCoeff, postShare_extreme, opinionVar, postOpinionVar, percapita_extreme,
percapita_preextreme, at checkpoints 5000/10000/20000, Spearman + BH-FDR across the full table, plus
the reach_mod_all/reach_ext_top independence and SF1 denominator-deflation confound checks.

Usage: nohup python3 scripts/feed_redesign_v6_tier_decomposed_n100.py > logs/feed_redesign_v6_tier_decomposed_stdout.log 2>&1 &
"""
import concurrent.futures
import csv
import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
_JARS = list(ROOT.glob("lib/**/*.jar"))
LIBCP = ":".join(str(p) for p in _JARS) + (":" if _JARS else "") + str(ROOT / "bin")

N = 1000
STEPS = 20000
CHECKPOINTS = [5000, 10000, 20000]
N_SEEDS = 100
BASE_SEED = 5500000  # fresh range, distinct from v5's 5400000-5400099
MODERATE_THRESHOLD = 0.2
EXTREME_THRESHOLD = 0.6
# Tier boundaries matching scripts/extend_control_equilibria.py's docstring convention.
# (lo, hi] except "top" (fc>100, hi=inf) and "peripheral" (lo=-1 so fc=0 agents are included).
TIERS = {
    "top": (100, float("inf")),
    "mid": (50, 100),
    "small": (10, 50),
    "peripheral": (-1, 10),
}

FIXED_TOKENS = [
    "network=hk", "hk_m=15", "hk_a=4", "hk_pt=0.05",
    "max_follow=43.8638", "follow_prob=0.01", "feed_capacity=15",
    "alpha=0.7", "hop=4", "feed_decay_mode=exp", "feed_decay_lambda=0.10992130598108527",
    "feed_time_decay_tau=30",
    "access_prob=0.1", "p_u=0.05",
    "bc_dec=0.500000", "bc_recovery=0.000100", "bc_floor=0.2", "bc_ceiling=1.0", "bc_init=0.800000",
    "vocal_comfort_radius=0.1", "repost_prob=0.1", "relay_enabled=false",
    "out_of_bc_repost_prob=0.01", "rel_attrib=original",
    "stub_dist=uniform", "stub_min=0.82", "stub_max=0.82",
    "evict_beta=-1", "init_prune=trim",
    "initial_pp=0.25537", "max_pp=1.0", "min_pp=0.01", "pp_relax_eta=0.100000",
    "neutral_band=0.2",
]

LOG_PATH = ROOT / "docs" / "report" / "feed_redesign_v6_tier_decomposed.csv"


def launch(seed):
    tokens = [f"seed={seed}", f"n={N}", f"steps={STEPS}", "log_gexf=false", "force=true", *FIXED_TOKENS]
    logfile = ROOT / "logs" / f"feed_redesign_v6_seed{seed}.log"
    logfile.parent.mkdir(exist_ok=True)
    with open(logfile, "w") as lf:
        p = subprocess.Popen(
            ["java", "-Xmx2g", "-cp", LIBCP, "dynamics.OpinionDynamics", *tokens],
            stdout=lf, stderr=subprocess.STDOUT, cwd=ROOT,
        )
    return p


def t0_class(opinion):
    shifted = opinion + 1.0
    return min(int(shifted / 0.4), 4)


def read_t0_predictors(run_dir):
    rows = []
    with open(run_dir / "degrees" / "agent_snapshot_t0.csv", newline="") as f:
        for r in csv.DictReader(f):
            rows.append((float(r["opinion"]), int(r["followerCount"])))
    total_followers = sum(fc for _, fc in rows) or 1
    n_agents = len(rows)
    pop_by_class = [0] * 5
    for op, fc in rows:
        pop_by_class[t0_class(op)] += 1
    mod = [(op, fc) for op, fc in rows if abs(op) < MODERATE_THRESHOLD]
    ext = [(op, fc) for op, fc in rows if abs(op) >= EXTREME_THRESHOLD]
    mod_top = [(op, fc) for op, fc in mod if fc > 100]
    ext_top = [(op, fc) for op, fc in ext if fc > 100]
    out = dict(
        reach_mod_all=sum(fc for _, fc in mod) / total_followers,
        mod_pop_share=len(mod) / n_agents,
        reach_mod_top=sum(fc for _, fc in mod_top) / total_followers,
        n_mod_top=len(mod_top),
        reach_ext_top=sum(fc for _, fc in ext_top) / total_followers,
        n_ext_top=len(ext_top),
        reach_ext_all=sum(fc for _, fc in ext) / total_followers,
        ext_pop_share=len(ext) / n_agents,
        pop_extreme_t0=pop_by_class[0] + pop_by_class[4],
        pop_preextreme_t0=pop_by_class[1] + pop_by_class[3],
    )
    # Tier-decomposed reach/count for both classes (2026-07-29, v6 -- answers "small hubs /
    # peripheral agents" question; "top" duplicates reach_mod_top/reach_ext_top above, kept for a
    # uniform naming scheme across all 4 tiers).
    for tier, (lo, hi) in TIERS.items():
        mod_t = [(op, fc) for op, fc in mod if lo < fc <= hi]
        ext_t = [(op, fc) for op, fc in ext if lo < fc <= hi]
        out[f"reach_mod_{tier}"] = sum(fc for _, fc in mod_t) / total_followers
        out[f"n_mod_{tier}"] = len(mod_t)
        out[f"reach_ext_{tier}"] = sum(fc for _, fc in ext_t) / total_followers
        out[f"n_ext_{tier}"] = len(ext_t)
    return out


def read_outcomes(run_dir):
    with open(run_dir / "metrics" / "results.csv", newline="") as f:
        rows_by_step = {int(r["step"]): r for r in csv.DictReader(f)}
    q_by_step = {}
    with open(run_dir / "metrics" / "modularity.csv", newline="") as f:
        for r in csv.DictReader(f):
            q_by_step[int(r["step"])] = float(r["Q_sign_repost"])
    out = {}
    for chk in CHECKPOINTS:
        r = rows_by_step.get(chk)
        if r is None:
            out[chk] = None
            continue
        opinion_var = float(r["opinionVar"])
        post_var = float(r["postOpinionVar"])
        total_posts = int(r["originalPostCount"]) + int(r["repostCount"])
        post_share_extreme = float(r["postShare_0"]) + float(r["postShare_4"])
        post_share_preextreme = float(r["postShare_1"]) + float(r["postShare_3"])
        out[chk] = dict(
            sf1=post_var / opinion_var if opinion_var > 0 else None,
            crossCuttingFraction=float(r["crossCuttingFraction"]),
            opinionAssortativity=float(r["opinionAssortativity"]),
            Q_sign_repost=q_by_step.get(chk),
            bimodalityCoeff=float(r["bimodalityCoeff"]),
            postShare_extreme=post_share_extreme,
            opinionVar=opinion_var,
            postOpinionVar=post_var,
            total_posts=total_posts,
            post_share_extreme_raw=post_share_extreme,
            post_share_preextreme_raw=post_share_preextreme,
        )
    return out


def evaluate_seed(seed):
    p = launch(seed)
    p.wait()
    candidates = sorted(ROOT.glob(f"results/run_{seed}_*"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        return None
    d = candidates[-1]
    try:
        pred = read_t0_predictors(d)
        out = read_outcomes(d)
    except (FileNotFoundError, KeyError):
        return None
    # per-capita rates by t0 class, per checkpoint
    for chk in CHECKPOINTS:
        o = out.get(chk)
        if o is None:
            continue
        o["percapita_extreme"] = (o["post_share_extreme_raw"] * o["total_posts"] / pred["pop_extreme_t0"]
                                   if pred["pop_extreme_t0"] > 0 else None)
        o["percapita_preextreme"] = (o["post_share_preextreme_raw"] * o["total_posts"] / pred["pop_preextreme_t0"]
                                      if pred["pop_preextreme_t0"] > 0 else None)
    return dict(seed=seed, pred=pred, out=out)


PREDICTORS = ["reach_mod_all", "mod_pop_share", "reach_ext_all", "ext_pop_share"]
for _tier in ["top", "mid", "small", "peripheral"]:
    PREDICTORS += [f"reach_mod_{_tier}", f"n_mod_{_tier}", f"reach_ext_{_tier}", f"n_ext_{_tier}"]
OUTCOMES = ["sf1", "crossCuttingFraction", "opinionAssortativity", "Q_sign_repost", "bimodalityCoeff",
            "postShare_extreme", "opinionVar", "postOpinionVar", "percapita_extreme", "percapita_preextreme"]


def bh_fdr(pvals):
    pvals = np.asarray(pvals)
    n = len(pvals)
    order = np.argsort(pvals)
    ranked = pvals[order]
    q = ranked * n / (np.arange(n) + 1)
    q = np.minimum.accumulate(q[::-1])[::-1]
    out = np.empty(n)
    out[order] = np.minimum(q, 1.0)
    return out


def main():
    seeds = list(range(BASE_SEED, BASE_SEED + N_SEEDS))
    print(f"Running {N_SEEDS} fresh control seeds {seeds[0]}-{seeds[-1]} at the provisional "
          f"feed-mechanism point...", flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as ex:
        results = list(ex.map(evaluate_seed, seeds))
    ok = [r for r in results if r is not None]
    print(f"n={len(ok)}/{N_SEEDS} runs succeeded", flush=True)

    with open(LOG_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        header = ["seed"] + PREDICTORS
        for chk in CHECKPOINTS:
            header += [f"{o}_{chk}" for o in OUTCOMES]
        writer.writerow(header)
        for r in ok:
            row = [r["seed"]] + [r["pred"][p] for p in PREDICTORS]
            for chk in CHECKPOINTS:
                o = r["out"].get(chk) or {}
                row += [o.get(k) for k in OUTCOMES]
            writer.writerow(row)

    # Correlation table
    cells = []  # (predictor, outcome, checkpoint, rho, p)
    for pred in PREDICTORS:
        x = np.array([r["pred"][pred] for r in ok], dtype=float)
        for chk in CHECKPOINTS:
            for out in OUTCOMES:
                y = np.array([(r["out"].get(chk) or {}).get(out) for r in ok], dtype=float)
                mask = ~np.isnan(x) & ~np.isnan(y)
                if mask.sum() < 10:
                    continue
                rho, p = spearmanr(x[mask], y[mask])
                cells.append((pred, out, chk, rho, p))

    pvals = [c[4] for c in cells]
    qvals = bh_fdr(pvals)
    print("\n=== Correlation table (Spearman rho, BH-FDR q across all cells) ===", flush=True)
    print(f"{'predictor':16s} {'outcome':22s} {'step':>6s} {'rho':>8s} {'p':>10s} {'q':>10s}")
    sig_cells = []
    for (pred, out, chk, rho, p), q in sorted(zip(cells, qvals), key=lambda z: z[0][4]):
        flag = " *FDR<0.10*" if q < 0.10 else ""
        print(f"{pred:16s} {out:22s} {chk:6d} {rho:8.3f} {p:10.4g} {q:10.4g}{flag}", flush=True)
        if q < 0.10:
            sig_cells.append((pred, out, chk, rho, p, q))

    print(f"\n=== {len(sig_cells)} cells survive BH-FDR<0.10 out of {len(cells)} tested ===")
    for pred, out, chk, rho, p, q in sig_cells:
        print(f"  {pred} -> {out} @ step{chk}: rho={rho:.3f}, p={p:.4g}, q={q:.4g}")

    # Confound checks
    reach_mod_all = np.array([r["pred"]["reach_mod_all"] for r in ok], dtype=float)
    reach_ext_top = np.array([r["pred"]["reach_ext_top"] for r in ok], dtype=float)
    rho_indep, p_indep = spearmanr(reach_mod_all, reach_ext_top)
    print(f"\n=== Confound check: reach_mod_all vs reach_ext_top independence ===")
    print(f"rho={rho_indep:.4f}, p={p_indep:.4g} (n=20 originally found -0.01 n.s.; n=100 found "
          f"-0.335 p=.0007 -- real coupling, do not assume independence)")

    for chk in CHECKPOINTS:
        ov = np.array([(r["out"].get(chk) or {}).get("opinionVar") for r in ok], dtype=float)
        pv = np.array([(r["out"].get(chk) or {}).get("postOpinionVar") for r in ok], dtype=float)
        mask = ~np.isnan(ov) & ~np.isnan(pv) & ~np.isnan(reach_mod_all)
        rho_ov, p_ov = spearmanr(reach_mod_all[mask], ov[mask])
        rho_pv, p_pv = spearmanr(reach_mod_all[mask], pv[mask])
        print(f"SF1 denominator-deflation check @ step{chk}: reach_mod_all->opinionVar rho={rho_ov:.3f} "
              f"(p={p_ov:.3g}), reach_mod_all->postOpinionVar rho={rho_pv:.3f} (p={p_pv:.3g})")

    print(f"\nFull per-seed log: {LOG_PATH}", flush=True)


if __name__ == "__main__":
    main()
