"""
2026-07-26 -- Bridging-role isolation, three cleaner alternatives to the opinion-swap secession
test (`hub_secession_experiment.py`). User's critique of the swap design: it bundles "remove the
bridge" with "inject a new extremist" into one manipulation, confounding the two. These three
treatments isolate different slices of "moderate mid-tier hub" without ever touching opinion:

  - mute_access: accessProb=0 for the target hubs -- full deactivation (no posting, reposting,
    following, unfollowing, or opinion update). The broadest "what if this hub simply weren't
    participating" counterfactual.
  - mute_repost: ChannelMode=POST_ONLY for the target hubs -- they keep posting their own
    (moderate) content and stay normally followable, but stop relaying/reposting anything. Isolates
    the specific bridging mechanism (relaying cross-camp content), since the hub's own voice and
    position in the follow graph are otherwise unchanged.
  - algo_exclude: the target hubs are excluded from the For-You velocity-ranked candidate pool
    only (AdminOptim.AdminFeedback) -- their organic/chrono reach (readers who directly follow
    them) is untouched. Not literal node removal (user: "if it's not pure counterfactual, implement
    ignorance just inside the recommendation algo") -- isolates whether ALGORITHMIC amplification
    of the hub specifically (vs. organic follow-based reach) is doing any bridging work.

All three are implemented as new ExperimentConfig CLI tokens (mute_access_ids/mute_repost_ids/
algo_exclude_ids, comma-separated agent IDs -- see ExperimentConfig.java, OpinionDynamics.java,
AdminOptim.java, 2026-07-26), applied directly to the UNMODIFIED base equilibrium GEXF via
network=read -- no GEXF editing needed for any of these (unlike the opinion swap), which also
sidesteps that whole class of bug (forgetting to edit a second attribute). CONTROL is identical to
hub_secession_experiment.py's control (same unmodified network, same continuation dynamics) and is
reused directly from disk (seeds 2000000-2000019) rather than re-simulated.

Usage: python3 scripts/hub_bridging_experiment.py <tier> <treatment>
       treatment in {mute_access, mute_repost, algo_exclude}
"""
import concurrent.futures
import csv
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
_JARS = list(ROOT.glob("lib/**/*.jar"))
LIBCP = ":".join(str(p) for p in _JARS) + (":" if _JARS else "") + str(ROOT / "bin")

N = 1000
CONTINUE_STEPS = 20000
BASE_SEEDS = list(range(1726000, 1726020))
MODERATE_THRESHOLD = 0.2

TIER_BOUNDS = {"mega": (500, N), "mid": (100, 500), "small": (50, 100)}
CONTROL_BASE = 2000000  # reused from hub_secession_experiment.py's mid-tier control, unaffected
TREATMENT_BASES = {
    "mute_access": 2100000,
    "mute_repost": 2110000,
    "algo_exclude": 2120000,
}
CLI_TOKEN = {
    "mute_access": "mute_access_ids",
    "mute_repost": "mute_repost_ids",
    "algo_exclude": "algo_exclude_ids",
}

# Verbatim from hub_secession_experiment.py's FIXED dict.
FIXED = dict(
    network="read", hk_m=15, hk_a=4, hk_pt=0.05,
    max_follow=43.8638, follow_prob=0.05955,
    alpha=0.63, hop=4, feed_capacity=31, vel_mode="windowed",
    access_prob=0.025,
    p_u=0.1,
    bc_dec=1.0, bc_recovery=0.0005, bc_floor=0.2, bc_ceiling=1.0, bc_init=1.0,
    init_dist="gaussian",
    vocal_comfort_radius=0.5,
    repost_prob=0.1, relay_enabled="false", out_of_bc_repost_prob=0.01, rel_attrib="original",
    stub_dist="uniform", stub_min=0.82, stub_max=0.82,
    evict_beta=-1, init_prune="trim",
    initial_pp=0.25537, max_pp=1.0, min_pp=0.01, pp_relax_eta=0.002215,
    neutral_band=0.2,
)


def base_gexf_path(seed):
    candidates = sorted(ROOT.glob(f"results/run_{seed}_*"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        return None
    d = candidates[-1]
    p = d / "GEXF" / "lambda_0.0" / "step_40000.gexf"
    return p if p.exists() else None


def moderate_hub_ids(seed, lo, hi):
    candidates = sorted(ROOT.glob(f"results/run_{seed}_*"), key=lambda p: p.stat().st_mtime)
    d = candidates[-1]
    snap_path = d / "degrees" / "agent_snapshot_final.csv"
    hits = []
    with open(snap_path, newline="") as f:
        for r in csv.DictReader(f):
            op, fo = float(r["opinion"]), int(r["followerCount"])
            if lo < fo <= hi and abs(op) < MODERATE_THRESHOLD:
                hits.append(int(r["agentId"]))
    return hits


def launch(seed, read_path, extra_token=None):
    tokens = [
        f"seed={seed}", f"read_path={read_path}", f"n={N}", f"steps={CONTINUE_STEPS}", "force=true",
        f"network={FIXED['network']}", f"hk_m={FIXED['hk_m']}", f"hk_a={FIXED['hk_a']}",
        f"hk_pt={FIXED['hk_pt']}",
        f"max_follow={FIXED['max_follow']}", f"follow_prob={FIXED['follow_prob']}",
        f"alpha={FIXED['alpha']}", f"hop={FIXED['hop']}", f"feed_capacity={FIXED['feed_capacity']}",
        f"vel_mode={FIXED['vel_mode']}",
        f"access_prob={FIXED['access_prob']}",
        f"p_u={FIXED['p_u']}",
        f"bc_dec={FIXED['bc_dec']:.6f}", f"bc_recovery={FIXED['bc_recovery']:.6f}",
        f"bc_floor={FIXED['bc_floor']}", f"bc_ceiling={FIXED['bc_ceiling']}",
        f"bc_init={FIXED['bc_init']:.6f}",
        f"init_dist={FIXED['init_dist']}",
        f"vocal_comfort_radius={FIXED['vocal_comfort_radius']}",
        f"repost_prob={FIXED['repost_prob']}", f"relay_enabled={FIXED['relay_enabled']}",
        f"out_of_bc_repost_prob={FIXED['out_of_bc_repost_prob']}", f"rel_attrib={FIXED['rel_attrib']}",
        f"stub_dist={FIXED['stub_dist']}", f"stub_min={FIXED['stub_min']}", f"stub_max={FIXED['stub_max']}",
        f"evict_beta={FIXED['evict_beta']}", f"init_prune={FIXED['init_prune']}",
        f"initial_pp={FIXED['initial_pp']}", f"max_pp={FIXED['max_pp']}", f"min_pp={FIXED['min_pp']}",
        f"pp_relax_eta={FIXED['pp_relax_eta']:.6f}",
        f"neutral_band={FIXED['neutral_band']}",
    ]
    if extra_token:
        tokens.append(extra_token)
    logfile = ROOT / "logs" / f"bridging_seed{seed}.log"
    logfile.parent.mkdir(exist_ok=True)
    with open(logfile, "w") as lf:
        p = subprocess.Popen(
            ["java", "-Xmx2g", "-cp", LIBCP, "dynamics.OpinionDynamics", *tokens],
            stdout=lf, stderr=subprocess.STDOUT, cwd=ROOT,
        )
    return p


def read_metrics(seed):
    candidates = sorted(ROOT.glob(f"results/run_{seed}_*"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        return None
    d = candidates[-1]
    results_path = d / "metrics" / "results.csv"
    mod_path = d / "metrics" / "modularity.csv"
    if not (results_path.exists() and mod_path.exists()):
        return None
    with open(results_path, newline="") as f:
        rows = list(csv.DictReader(f))
    last = rows[-1]
    q = None
    with open(mod_path, newline="") as f:
        for row in csv.DictReader(f):
            q = float(row["Q_sign_repost"])
    opinion_var = float(last["opinionVar"])
    post_opinion_var = float(last["postOpinionVar"])
    sf1 = post_opinion_var / opinion_var if opinion_var > 0 else None
    sum_cols = ["blockCount", "unfollowCount", "evictionCount", "originalPostCount", "repostCount"]
    rate_cols = ["outGroupBlockPropensity", "outGroupSanctionRate", "crossRepostRate"]
    out = dict(
        crossCuttingFraction=float(last["crossCuttingFraction"]),
        interactionCrossCuttingFraction=float(last["interactionCrossCuttingFraction"]),
        Q_sign_repost=q,
        opinionVar=opinion_var,
        postOpinionVar=post_opinion_var,
        sf1_ratio=sf1,
        bimodalityCoeff=float(last["bimodalityCoeff"]),
        opinionKurtosis=float(last["opinionKurtosis"]),
        disagreement=float(last["disagreement"]),
    )
    for c in sum_cols:
        out[c] = sum(float(r[c]) for r in rows)
    for c in rate_cols:
        out[c] = float(np.mean([float(r[c]) for r in rows]))
    for b in range(5):
        out[f"postShare_{b}"] = float(np.mean([float(r[f"postShare_{b}"]) for r in rows]))
    return out


def run_control():
    results = {}
    for i in range(len(BASE_SEEDS)):
        cont_seed = CONTROL_BASE + i
        m = read_metrics(cont_seed)
        if m is None:
            raise RuntimeError(f"control seed {cont_seed} missing on disk -- expected reuse from hub_secession_experiment.py's mid-tier run")
        results[BASE_SEEDS[i]] = m
    return results


def run_treatment(treatment, tier, seed_base):
    lo, hi = TIER_BOUNDS[tier]
    token_name = CLI_TOKEN[treatment]
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
        futs = {}
        for i, bseed in enumerate(BASE_SEEDS):
            cont_seed = seed_base + i
            existing = read_metrics(cont_seed)
            if existing is not None:
                print(f"  [{treatment}] seed={cont_seed} (base={bseed}): reusing existing result", flush=True)
                results[bseed] = existing
                continue
            ids = moderate_hub_ids(bseed, lo, hi)
            extra = f"{token_name}={','.join(str(a) for a in ids)}"
            read_path = base_gexf_path(bseed)
            futs[ex.submit(lambda s=cont_seed, rp=read_path, e=extra: (launch(s, rp, e).wait(), read_metrics(s))[1])] = bseed
        for fut in concurrent.futures.as_completed(futs):
            bseed = futs[fut]
            results[bseed] = fut.result()
    return results


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in TIER_BOUNDS or sys.argv[2] not in TREATMENT_BASES:
        print(__doc__)
        sys.exit(1)
    tier, treatment = sys.argv[1], sys.argv[2]

    print(f"[{treatment}/{tier}] loading control (reused from disk, seeds {CONTROL_BASE}-{CONTROL_BASE+19})...", flush=True)
    control_results = run_control()
    print(f"[{treatment}/{tier}] launching treatment (base={TREATMENT_BASES[treatment]})...", flush=True)
    treatment_results = run_treatment(treatment, tier, TREATMENT_BASES[treatment])

    metric_names = list(next(iter(control_results.values())).keys())
    log_path = ROOT / "docs" / "report" / f"hub_bridging_{treatment}_{tier}.csv"
    with open(log_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["condition", "base_seed"] + metric_names)
        for bseed in BASE_SEEDS:
            for cond, res in (("control", control_results), (treatment, treatment_results)):
                r = res.get(bseed)
                w.writerow([cond, bseed] + ([r[m] for m in metric_names] if r else [None] * len(metric_names)))
    print(f"\nFull log: {log_path}")

    print(f"\n=== [{treatment}/{tier}] paired vs. control (n={len(BASE_SEEDS)} base seeds) ===")
    for m in metric_names:
        paired = [(control_results[s][m], treatment_results[s][m]) for s in BASE_SEEDS
                  if control_results.get(s) and treatment_results.get(s)
                  and control_results[s][m] is not None and treatment_results[s][m] is not None]
        c = np.array([cv for cv, tv in paired])
        t = np.array([tv for cv, tv in paired])
        diff = t - c
        tstat = diff.mean() / (diff.std(ddof=1) / np.sqrt(len(diff))) if len(diff) > 1 and diff.std(ddof=1) > 0 else float("nan")
        print(f"{m:>32}: control={c.mean():.4f}+/-{c.std():.4f}  {treatment}={t.mean():.4f}+/-{t.std():.4f}  "
              f"diff={diff.mean():+.4f}+/-{diff.std():.4f}  t={tstat:.2f}  (n={len(diff)})")


if __name__ == "__main__":
    main()
