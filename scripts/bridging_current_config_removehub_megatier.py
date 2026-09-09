"""
2026-07-28 -- True node-removal counterfactual (see bridging_current_config_removehub.py for the
mechanism/rationale), mega tier, on the current-config point.

Differences from the mid-tier version:
  - TIER_BOUNDS = (500, N) (mega, followerCount>500) instead of mid (100,500].
  - N_SEEDS = 10, not 20 (user, 2026-07-28: "10 seeds are enough from now on" -- this project's
    calibration history has repeatedly found n=20 barely resolves anything on sf1_ratio anyway
    (SEM ~0.06-0.08), so the marginal resolving power lost going 20->10 is small relative to the
    compute saved; the compositional/behavioral metrics that DO resolve cleanly (postShare,
    crossRepostRate, disagreement) have much tighter SEMs and don't need n=20 either).
  - Writes into its own results/2026-07-28_removehub-mega-tier/ subfolder via the new
    `results_subdir` CLI token (ExperimentConfig.java, 2026-07-28) instead of a flat results/ --
    keeps the results/ top level from accumulating another ~100+ folders (per user's request to
    split experiments into separate, dashboard-switchable folders rather than one heavy directory).
  - result_dir() now globs results/**/run_<seed>_* (recursive) since the equilibria/control this
    script reuses now live in results/2026-07-27_current-config-equilibria/ and
    results/2026-07-27_bridging-mid-tier/ respectively, not flat results/.
  - Distinct log prefix `bridgecur_removehub_mega_seed` so the dashboard's run-set picker (which
    groups by logs/*.log filename prefix) shows this as its own switchable group.

Reuses the SAME equilibria and control runs as every other current-config experiment (equilibria
are tier-agnostic; control is an unmanipulated continuation, also tier-agnostic) -- only derives a
NEW mega-tier hub list from those equilibria and launches the new remove_hub arm.

Usage: python3 scripts/bridging_current_config_removehub_megatier.py
"""
import concurrent.futures
import csv
import subprocess
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
_JARS = list(ROOT.glob("lib/**/*.jar"))
LIBCP = ":".join(str(p) for p in _JARS) + (":" if _JARS else "") + str(ROOT / "bin")

N = 1000
EQUIL_STEPS = 20000
CONTINUE_STEPS = 20000
CHECKPOINTS = [10000, 20000]
N_SEEDS = 10
EQUIL_BASE_SEED = 3000000        # reuse first 10 of the existing 20 current-config equilibria
EXISTING_CONTROL_BASE = 3010000  # reuse first 10 of the existing mid-tier control runs (tier-agnostic)
REMOVE_HUB_BASE = 7010000        # new, verified unused
RESULTS_SUBDIR = "2026-07-28_removehub-mega-tier"
MODERATE_THRESHOLD = 0.2
TIER_BOUNDS = (500, N)  # mega / top tier

FIXED_TOKENS = [
    "network=hk", "hk_m=15", "hk_a=4", "hk_pt=0.05",
    "max_follow=43.8638", "follow_prob=0.01",
    "alpha=0.7", "hop=3", "feed_capacity=15", "vel_mode=windowed",
    "access_prob=0.1", "p_u=0.05",
    "bc_dec=0.500000", "bc_recovery=0.000100", "bc_floor=0.2", "bc_ceiling=1.0", "bc_init=0.800000",
    "init_dist=gaussian", "vocal_comfort_radius=0.1",
    "repost_prob=0.1", "relay_enabled=false", "out_of_bc_repost_prob=0.01", "rel_attrib=original",
    "stub_dist=uniform", "stub_min=0.82", "stub_max=0.82",
    "evict_beta=-1", "init_prune=trim",
    "initial_pp=0.25537", "max_pp=1.0", "min_pp=0.01", "pp_relax_eta=0.100000",
    "neutral_band=0.2",
]


def result_dir(seed):
    candidates = sorted(ROOT.glob(f"results/**/run_{seed}_*"), key=lambda p: p.stat().st_mtime)
    return candidates[-1] if candidates else None


def is_done(seed, steps):
    d = result_dir(seed)
    if d is None:
        return False
    rp = d / "metrics" / "results.csv"
    if not rp.exists():
        return False
    with open(rp, newline="") as f:
        rows = list(csv.DictReader(f))
    return bool(rows) and int(rows[-1]["step"]) >= steps


def equil_gexf_path(seed):
    d = result_dir(seed)
    return d / "GEXF" / "lambda_0.0" / f"step_{EQUIL_STEPS}.gexf"


def moderate_hub_ids(seed):
    d = result_dir(seed)
    lo, hi = TIER_BOUNDS
    hits = []
    with open(d / "degrees" / "agent_snapshot_final.csv", newline="") as f:
        for r in csv.DictReader(f):
            op, fo = float(r["opinion"]), int(r["followerCount"])
            if lo < fo <= hi and abs(op) < MODERATE_THRESHOLD:
                hits.append((int(r["agentId"]), op))
    return hits


def launch(seed, steps, extra_tokens):
    tokens = [f"seed={seed}", f"steps={steps}", "n=" + str(N), "force=true",
              f"results_subdir={RESULTS_SUBDIR}"] + FIXED_TOKENS + extra_tokens
    logfile = ROOT / "logs" / f"bridgecur_removehub_mega_seed{seed}.log"
    logfile.parent.mkdir(exist_ok=True)
    with open(logfile, "w") as lf:
        p = subprocess.Popen(["java", "-Xmx2g", "-cp", LIBCP, "dynamics.OpinionDynamics", *tokens],
                              stdout=lf, stderr=subprocess.STDOUT, cwd=ROOT)
    return p


def read_metrics_at(seed, checkpoint):
    d = result_dir(seed)
    with open(d / "metrics" / "results.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    window = [r for r in rows if int(r["step"]) <= checkpoint]
    at = next(r for r in reversed(window) if int(r["step"]) == checkpoint)
    q = None
    with open(d / "metrics" / "modularity.csv", newline="") as f:
        for row in csv.DictReader(f):
            if int(row["step"]) == checkpoint:
                q = float(row["Q_sign_repost"])
    opinion_var = float(at["opinionVar"])
    post_opinion_var = float(at["postOpinionVar"])
    sf1 = post_opinion_var / opinion_var if opinion_var > 0 else None
    out = dict(
        Q_sign_repost=q,
        opinionVar=opinion_var, postOpinionVar=post_opinion_var, sf1_ratio=sf1,
        crossCuttingFraction=float(at["crossCuttingFraction"]),
        interactionCrossCuttingFraction=float(at["interactionCrossCuttingFraction"]),
        bimodalityCoeff=float(at["bimodalityCoeff"]), opinionKurtosis=float(at["opinionKurtosis"]),
        disagreement=float(at["disagreement"]),
    )
    for c in ["blockCount", "unfollowCount", "evictionCount", "originalPostCount", "repostCount"]:
        out[c] = sum(float(r[c]) for r in window)
    for c in ["outGroupBlockPropensity", "outGroupSanctionRate", "crossRepostRate"]:
        out[c] = float(np.mean([float(r[c]) for r in window]))
    for b in range(5):
        out[f"postShare_{b}"] = float(np.mean([float(r[f"postShare_{b}"]) for r in window]))
    return out


def run_remove_hub_arm(equil_seeds, hub_lookup):
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=N_SEEDS) as ex:
        futs = {}
        for i, bseed in enumerate(equil_seeds):
            cont_seed = REMOVE_HUB_BASE + i
            if is_done(cont_seed, CONTINUE_STEPS):
                print(f"  [remove_hub] seed={cont_seed}: reusing existing", flush=True)
                results[bseed] = cont_seed
                continue
            ids = [a for a, _ in hub_lookup[bseed]]
            idstr = ",".join(str(a) for a in ids)
            read_path = equil_gexf_path(bseed)
            tokens = [f"remove_hub_ids={idstr}", "network=read", f"read_path={read_path}"]
            futs[ex.submit(lambda s=cont_seed, tk=tokens: launch(s, CONTINUE_STEPS, tk).wait())] = (bseed, cont_seed)
        for f in futs:
            bseed, cont_seed = futs[f]
            f.result()
            results[bseed] = cont_seed
    return results


def main():
    equil_seeds = [EQUIL_BASE_SEED + i for i in range(N_SEEDS)]
    print("Verifying current-config equilibria + existing mid-tier control runs are on disk (reused, tier-agnostic)...", flush=True)
    for i, s in enumerate(equil_seeds):
        assert is_done(s, EQUIL_STEPS), f"equilibrium seed {s} missing/incomplete"
        assert is_done(EXISTING_CONTROL_BASE + i, CONTINUE_STEPS), f"existing control seed {EXISTING_CONTROL_BASE+i} missing/incomplete"

    print("Deriving realized MEGA-tier neutral hub lists...", flush=True)
    hub_lookup = {s: moderate_hub_ids(s) for s in equil_seeds}
    for s in equil_seeds:
        print(f"  seed={s}: {len(hub_lookup[s])} moderate mega-tier hubs -> {[a for a,_ in hub_lookup[s]]}", flush=True)

    print("\n=== running arm: remove_hub (mega tier) ===", flush=True)
    remove_hub_seeds = run_remove_hub_arm(equil_seeds, hub_lookup)
    control_seeds = {bseed: EXISTING_CONTROL_BASE + i for i, bseed in enumerate(equil_seeds)}

    metric_names = ["Q_sign_repost", "opinionVar", "postOpinionVar", "sf1_ratio",
                     "crossCuttingFraction", "interactionCrossCuttingFraction",
                     "bimodalityCoeff", "opinionKurtosis", "disagreement",
                     "blockCount", "unfollowCount", "evictionCount", "originalPostCount", "repostCount",
                     "outGroupBlockPropensity", "outGroupSanctionRate", "crossRepostRate",
                     "postShare_0", "postShare_1", "postShare_2", "postShare_3", "postShare_4"]

    log_path = ROOT / "docs" / "report" / "bridging_current_config_removehub_megatier.csv"
    with open(log_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["arm", "base_seed", "checkpoint"] + metric_names)
        for arm, mapping in [("control", control_seeds), ("remove_hub", remove_hub_seeds)]:
            for bseed, cont_seed in mapping.items():
                for cp in CHECKPOINTS:
                    m = read_metrics_at(cont_seed, cp)
                    w.writerow([arm, bseed, cp] + [m[k] for k in metric_names])
    print(f"\nFull log: {log_path}")

    for cp in CHECKPOINTS:
        print(f"\n########## checkpoint = {cp} ##########")
        control_vals = {bseed: read_metrics_at(cseed, cp) for bseed, cseed in control_seeds.items()}
        remove_vals = {bseed: read_metrics_at(cseed, cp) for bseed, cseed in remove_hub_seeds.items()}
        print(f"\n=== [remove_hub] vs control @ step {cp} (n={N_SEEDS}) ===")
        for m in metric_names:
            paired = [(control_vals[s][m], remove_vals[s][m]) for s in equil_seeds
                      if control_vals[s][m] is not None and remove_vals[s][m] is not None]
            c = np.array([cv for cv, tv in paired]); t = np.array([tv for cv, tv in paired])
            diff = t - c
            tstat = diff.mean() / (diff.std(ddof=1) / np.sqrt(len(diff))) if len(diff) > 1 and diff.std(ddof=1) > 0 else float("nan")
            print(f"{m:>32}: control={c.mean():.4f}+/-{c.std():.4f}  remove_hub={t.mean():.4f}+/-{t.std():.4f}  "
                  f"diff={diff.mean():+.4f}+/-{diff.std():.4f}  t={tstat:.2f}")


if __name__ == "__main__":
    main()
