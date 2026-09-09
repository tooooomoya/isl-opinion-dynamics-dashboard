"""
2026-07-26 -- Full redo of the bridging-role experiment series at accessProb=0.1 (reverted from the
un-validated 0.025 cut), steps=20000 (matching the calibration scripts' own SF1-validation
convention, v9-v15), with metrics read at BOTH checkpoint step=10000 and step=20000, not just a
single final-step snapshot.

Why: traced that the [1.19,1.26] SF1 target was only ever confirmed at accessProb=0.1/steps=20000.
accessProb was cut to 0.025 afterward (2026-07-25) to fix a DIFFERENT problem (bin7 non-stationarity
at steps=40000) and was never re-validated for SF1 -- and today's control arm's SF1 (0.868+/-0.276,
n=20, 95% CI entirely below 1.0) confirms this matters, not just a paperwork gap. User's fix
(2026-07-26): revert accessProb to the validated value, shorten the run to the validated step count,
and check the trajectory (10000 vs 20000) instead of trusting one un-validated far-future point.

Pipeline:
  1. Build (or reuse) 20 base equilibrium networks: n=1000, steps=20000, access_prob=0.1, all other
     dynamics params identical to the "Calibration closed for now" frozen defaults otherwise.
  2. Derive each seed's realized moderate mid-tier hub list (100 < followerCount <= 500,
     |opinion| < 0.2) from the equilibrium snapshot.
  3. Five arms, each 20 continuation seeds, steps=20000: control (unmodified), swap (opinion AND
     intrinsicOpinion -> +/-0.9), mute_access (accessProb=0 for target hubs), mute_repost
     (ChannelMode=POST_ONLY), algo_exclude (graph-level BFS exclusion from For-You reachability).
  4. Metrics extracted at BOTH checkpoint=10000 and checkpoint=20000 within each continuation
     (results.csv logs every step; modularity.csv logs every 5000, so both align).

Usage: python3 scripts/bridging_revalidated.py                 # build equilibria if missing, then all 5 arms
       python3 scripts/bridging_revalidated.py <arm>            # just one arm (control/swap/mute_access/mute_repost/algo_exclude)
"""
import concurrent.futures
import csv
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
_JARS = list(ROOT.glob("lib/**/*.jar"))
LIBCP = ":".join(str(p) for p in _JARS) + (":" if _JARS else "") + str(ROOT / "bin")

N = 1000
EQUIL_STEPS = 20000
CONTINUE_STEPS = 20000
CHECKPOINTS = [10000, 20000]
N_SEEDS = 20
EQUIL_BASE_SEED = 1800000
MODERATE_THRESHOLD = 0.2
SWAP_MAGNITUDE = 0.9
TIER_BOUNDS = (100, 500)  # mid tier

ARM_SEED_BASE = {
    "control": 1810000,
    "swap": 1820000,
    "mute_access": 1830000,
    "mute_repost": 1840000,
    "algo_exclude": 1850000,
}

GEXF_NS = "http://gexf.net/1.3"
SCRATCH = ROOT / "results" / "temp" / "bridging_revalidated"

FIXED = dict(
    network="hk", hk_m=15, hk_a=4, hk_pt=0.05,
    max_follow=43.8638, follow_prob=0.05955,
    alpha=0.63, hop=4, feed_capacity=31, vel_mode="windowed",
    access_prob=0.1,   # REVERTED from 0.025 (2026-07-26) -- see docstring
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


def common_tokens(extra):
    t = dict(FIXED)
    t.update(extra)
    return [
        f"n={N}", "force=true",
        f"network={t['network']}", f"hk_m={t['hk_m']}", f"hk_a={t['hk_a']}", f"hk_pt={t['hk_pt']}",
        f"max_follow={t['max_follow']}", f"follow_prob={t['follow_prob']}",
        f"alpha={t['alpha']}", f"hop={t['hop']}", f"feed_capacity={t['feed_capacity']}",
        f"vel_mode={t['vel_mode']}", f"access_prob={t['access_prob']}", f"p_u={t['p_u']}",
        f"bc_dec={t['bc_dec']:.6f}", f"bc_recovery={t['bc_recovery']:.6f}",
        f"bc_floor={t['bc_floor']}", f"bc_ceiling={t['bc_ceiling']}", f"bc_init={t['bc_init']:.6f}",
        f"init_dist={t['init_dist']}", f"vocal_comfort_radius={t['vocal_comfort_radius']}",
        f"repost_prob={t['repost_prob']}", f"relay_enabled={t['relay_enabled']}",
        f"out_of_bc_repost_prob={t['out_of_bc_repost_prob']}", f"rel_attrib={t['rel_attrib']}",
        f"stub_dist={t['stub_dist']}", f"stub_min={t['stub_min']}", f"stub_max={t['stub_max']}",
        f"evict_beta={t['evict_beta']}", f"init_prune={t['init_prune']}",
        f"initial_pp={t['initial_pp']}", f"max_pp={t['max_pp']}", f"min_pp={t['min_pp']}",
        f"pp_relax_eta={t['pp_relax_eta']:.6f}", f"neutral_band={t['neutral_band']}",
    ]


def result_dir(seed):
    candidates = sorted(ROOT.glob(f"results/run_{seed}_*"), key=lambda p: p.stat().st_mtime)
    return candidates[-1] if candidates else None


def launch(seed, steps, extra_tokens):
    tokens = [f"seed={seed}", f"steps={steps}"] + common_tokens({}) + extra_tokens
    logfile = ROOT / "logs" / f"bridgerev_seed{seed}.log"
    logfile.parent.mkdir(exist_ok=True)
    with open(logfile, "w") as lf:
        p = subprocess.Popen(["java", "-Xmx2g", "-cp", LIBCP, "dynamics.OpinionDynamics", *tokens],
                              stdout=lf, stderr=subprocess.STDOUT, cwd=ROOT)
    return p


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


def build_equilibria():
    seeds = [EQUIL_BASE_SEED + i for i in range(N_SEEDS)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=N_SEEDS) as ex:
        futs = []
        for s in seeds:
            if is_done(s, EQUIL_STEPS):
                print(f"  equil seed={s}: reusing existing", flush=True)
                continue
            futs.append(ex.submit(lambda s=s: launch(s, EQUIL_STEPS, []).wait()))
        for f in futs:
            f.result()
    return seeds


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


def write_swapped_gexf(src_path, dst_path, swap_list):
    ET.register_namespace("", GEXF_NS)
    tree = ET.parse(src_path)
    root = tree.getroot()
    attr_ids = {}
    for attrs in root.iter(f"{{{GEXF_NS}}}attributes"):
        for a in attrs.iter(f"{{{GEXF_NS}}}attribute"):
            if a.get("title") in ("opinion", "intrinsicOpinion"):
                attr_ids[a.get("title")] = a.get("id")
    targets = {str(aid): (SWAP_MAGNITUDE if op >= 0 else -SWAP_MAGNITUDE) for aid, op in swap_list}
    found = set()
    for node in root.iter(f"{{{GEXF_NS}}}node"):
        nid = node.get("id")
        if nid not in targets:
            continue
        hit = set()
        for av in node.iter(f"{{{GEXF_NS}}}attvalue"):
            if av.get("for") in (attr_ids["opinion"], attr_ids["intrinsicOpinion"]):
                av.set("value", str(targets[nid]))
                hit.add(av.get("for"))
        if hit == {attr_ids["opinion"], attr_ids["intrinsicOpinion"]}:
            found.add(nid)
    missing = set(targets) - found
    if missing:
        raise RuntimeError(f"agents not found/incomplete in {src_path}: {missing}")
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(dst_path, xml_declaration=True, encoding="UTF-8")


def extra_tokens_for(arm, base_seed, ids):
    if arm == "control":
        return [], equil_gexf_path(base_seed)
    if arm == "swap":
        dst = SCRATCH / f"swap_from{base_seed}.gexf"
        write_swapped_gexf(equil_gexf_path(base_seed), dst, ids)
        return [], dst
    if arm == "mute_access":
        idstr = ",".join(str(a) for a, _ in ids)
        return [f"mute_access_ids={idstr}"], equil_gexf_path(base_seed)
    if arm == "mute_repost":
        idstr = ",".join(str(a) for a, _ in ids)
        return [f"mute_repost_ids={idstr}"], equil_gexf_path(base_seed)
    if arm == "algo_exclude":
        idstr = ",".join(str(a) for a, _ in ids)
        return [f"algo_exclude_ids={idstr}"], equil_gexf_path(base_seed)
    raise ValueError(arm)


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


def run_arm(arm, equil_seeds, hub_lookup):
    seed_base = ARM_SEED_BASE[arm]
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=N_SEEDS) as ex:
        futs = {}
        for i, bseed in enumerate(equil_seeds):
            cont_seed = seed_base + i
            if is_done(cont_seed, CONTINUE_STEPS):
                print(f"  [{arm}] seed={cont_seed}: reusing existing", flush=True)
                results[bseed] = cont_seed
                continue
            extra, read_path = extra_tokens_for(arm, bseed, hub_lookup[bseed])
            tokens = extra + [f"network=read", f"read_path={read_path}"]
            futs[ex.submit(lambda s=cont_seed, tk=tokens: launch(s, CONTINUE_STEPS, tk).wait())] = (bseed, cont_seed)
        for f in futs:
            bseed, cont_seed = futs[f]
            f.result()
            results[bseed] = cont_seed
    return results


def main():
    arms = [sys.argv[1]] if len(sys.argv) > 1 else list(ARM_SEED_BASE.keys())
    for a in arms:
        if a not in ARM_SEED_BASE:
            print(__doc__); sys.exit(1)

    print("Building/reusing 20 base equilibrium networks (access_prob=0.1, steps=20000)...", flush=True)
    equil_seeds = build_equilibria()

    print("Deriving realized mid-tier neutral hub lists...", flush=True)
    hub_lookup = {s: moderate_hub_ids(s) for s in equil_seeds}
    for s in equil_seeds:
        print(f"  seed={s}: {len(hub_lookup[s])} moderate mid-tier hubs", flush=True)

    arm_cont_seeds = {}
    for arm in arms:
        print(f"\n=== running arm: {arm} ===", flush=True)
        arm_cont_seeds[arm] = run_arm(arm, equil_seeds, hub_lookup)

    if "control" not in arm_cont_seeds:
        arm_cont_seeds["control"] = run_arm("control", equil_seeds, hub_lookup)

    metric_names = ["Q_sign_repost", "opinionVar", "postOpinionVar", "sf1_ratio",
                     "crossCuttingFraction", "interactionCrossCuttingFraction",
                     "bimodalityCoeff", "opinionKurtosis", "disagreement",
                     "blockCount", "unfollowCount", "evictionCount", "originalPostCount", "repostCount",
                     "outGroupBlockPropensity", "outGroupSanctionRate", "crossRepostRate",
                     "postShare_0", "postShare_1", "postShare_2", "postShare_3", "postShare_4"]

    log_path = ROOT / "docs" / "report" / "bridging_revalidated.csv"
    with open(log_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["arm", "base_seed", "checkpoint"] + metric_names)
        for arm, mapping in arm_cont_seeds.items():
            for bseed, cont_seed in mapping.items():
                for cp in CHECKPOINTS:
                    m = read_metrics_at(cont_seed, cp)
                    w.writerow([arm, bseed, cp] + [m[k] for k in metric_names])
    print(f"\nFull log: {log_path}")

    for cp in CHECKPOINTS:
        print(f"\n########## checkpoint = {cp} ##########")
        control_map = arm_cont_seeds["control"]
        control_vals = {bseed: read_metrics_at(cseed, cp) for bseed, cseed in control_map.items()}
        for arm in arms:
            if arm == "control":
                continue
            print(f"\n=== [{arm}] vs control @ step {cp} (n={N_SEEDS}) ===")
            arm_map = arm_cont_seeds[arm]
            arm_vals = {bseed: read_metrics_at(cseed, cp) for bseed, cseed in arm_map.items()}
            for m in metric_names:
                paired = [(control_vals[s][m], arm_vals[s][m]) for s in equil_seeds
                          if control_vals[s][m] is not None and arm_vals[s][m] is not None]
                c = np.array([cv for cv, tv in paired]); t = np.array([tv for cv, tv in paired])
                diff = t - c
                tstat = diff.mean() / (diff.std(ddof=1) / np.sqrt(len(diff))) if len(diff) > 1 and diff.std(ddof=1) > 0 else float("nan")
                print(f"{m:>32}: control={c.mean():.4f}+/-{c.std():.4f}  {arm}={t.mean():.4f}+/-{t.std():.4f}  "
                      f"diff={diff.mean():+.4f}+/-{diff.std():.4f}  t={tstat:.2f}")


if __name__ == "__main__":
    main()
