"""
2026-07-28 -- Corrected causal-manipulation design: neutral-hub treatment applied at t=0 of a
FRESH network, observing the whole evolution trajectory, instead of on an already-equilibrated
network (which is what every bridging_current_config*.py script this week actually did).

User's correction: "the hypothesis that neutral hubs act as conduit and affect polarization is
about the term of 'evolution' of the NW not the equilibrium state ... treatment as swap or exclude
the neutral hubs from the initial state and see how dynamics evolve." Then: "the way of
manipulation is okay with what we've done ... just do it from the initial state. detect moderate
follower rankings in the initial state and split into top-tier and mid-tier (third tier may not be
explicit because the size is small at the initial state)."

Mechanism reused unchanged from bridging_current_config*.py: swap (opinion sign-flip via GEXF edit),
mute_access, mute_repost, algo_exclude, remove_hub (all via ExperimentConfig CLI id-set tokens).
What's different: the base network snapshot fed to `network=read` is each seed's own
GEXF/lambda_0.0/step_0.gexf (the true initial state, before any evolve() step) instead of
step_20000.gexf, and the run length is a full fresh 20000-step run (not a 20000-step continuation
on top of an already-run 20000).

Determinism check (2026-07-28, seed 3000000, steps=2000): `network=read` from a seed's own
step_0.gexf reproduces that seed's native `network=hk` run bit-for-bit in results.csv. Consequence:
the CONTROL arm does not need to be relaunched at all -- the already-completed
2026-07-27_current-config-equilibria runs (seeds 3000000-3000009, network=hk, steps=20000) already
*are* the correct "no manipulation, full evolution from t0" control for both tiers. Only the 5
manipulation arms are launched here.

Tier redefinition at t0 (see docs/report/2026-07-21-conduit-experiment-design.md, dated entry):
the *equilibrium* mega tier (followerCount>500) checked against a fresh HK network's own t0
followerCount distribution is completely EMPTY (max across 10 seeds was 423-483) -- follower counts
>500 are a product of ~20000 steps of follow/unfollow dynamics (rich-get-richer via the For-You
recommender), not something the raw HK generation itself produces. So at t0 there are only two
usable tiers, not three -- the user's suspicion that a third tier "may not be explicit" was right,
though the empty band turned out to be the top one, not the bottom one:
  - top-tier-initial:  followerCount(t0) > 100    (~7.4 neutral hubs/seed)
  - mid-tier-initial:  followerCount(t0) in (50,100]  (~7.0 neutral hubs/seed)

Usage: python3 scripts/initial_state_bridging.py <top|mid> [arm]
       arm in {swap, mute_access, mute_repost, algo_exclude, remove_hub}; omit for all 5.
"""
import concurrent.futures
import csv
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
_JARS = list(ROOT.glob("lib/**/*.jar"))
LIBCP = ":".join(str(p) for p in _JARS) + (":" if _JARS else "") + str(ROOT / "bin")

N = 1000
FULL_STEPS = 20000
CHECKPOINTS = list(range(0, FULL_STEPS + 1, 2000))
N_SEEDS = 10
SOURCE_BASE_SEED = 3000000  # existing 2026-07-27_current-config-equilibria runs (also = control)
SOURCE_SUBDIR = "2026-07-27_current-config-equilibria"
MODERATE_THRESHOLD = 0.2
SWAP_MAGNITUDE = 0.9

TIER_BOUNDS = {"top": (100, 10**9), "mid": (50, 100)}
# 9000000+/9100000+ verified unused against the full results/ seed inventory (2026-07-28).
ARM_SEED_BASE = {
    "top": {"swap": 9010000, "mute_access": 9020000, "mute_repost": 9030000,
            "algo_exclude": 9040000, "remove_hub": 9050000},
    "mid": {"swap": 9110000, "mute_access": 9120000, "mute_repost": 9130000,
            "algo_exclude": 9140000, "remove_hub": 9150000},
}
RESULTS_SUBDIR = {"top": "2026-07-28_initial-state-top-tier", "mid": "2026-07-28_initial-state-mid-tier"}

GEXF_NS = "http://gexf.net/1.3"
SCRATCH = ROOT / "results" / "temp" / "initial_state_bridging"

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


def source_dir(seed):
    return ROOT / "results" / SOURCE_SUBDIR / f"run_{seed}_ext-NONE_nmod-0_size-LARGEST_ch-BOTH_st-20000"


def t0_gexf_path(seed):
    return source_dir(seed) / "GEXF" / "lambda_0.0" / "step_0.gexf"


def moderate_hub_ids_t0(seed, tier):
    lo, hi = TIER_BOUNDS[tier]
    hits = []
    with open(source_dir(seed) / "degrees" / "agent_snapshot_t0.csv", newline="") as f:
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


def extra_tokens_for(arm, base_seed, ids, tier):
    if arm == "swap":
        dst = SCRATCH / f"swap_{tier}_from{base_seed}.gexf"
        write_swapped_gexf(t0_gexf_path(base_seed), dst, ids)
        return [], dst
    if arm in ("mute_access", "mute_repost", "algo_exclude", "remove_hub"):
        idstr = ",".join(str(a) for a, _ in ids)
        return [f"{arm}_ids={idstr}"], t0_gexf_path(base_seed)
    raise ValueError(arm)


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


def launch(seed, steps, extra_tokens, subdir):
    tokens = [f"seed={seed}", f"steps={steps}", f"n={N}", "force=true",
              f"results_subdir={subdir}"] + FIXED_TOKENS + extra_tokens
    logfile = ROOT / "logs" / f"initstate_seed{seed}.log"
    logfile.parent.mkdir(exist_ok=True)
    with open(logfile, "w") as lf:
        import subprocess
        p = subprocess.Popen(["java", "-Xmx2g", "-cp", LIBCP, "dynamics.OpinionDynamics", *tokens],
                              stdout=lf, stderr=subprocess.STDOUT, cwd=ROOT)
    return p


def run_arm(arm, tier, base_seeds, hub_lookup):
    seed_base = ARM_SEED_BASE[tier][arm]
    subdir = RESULTS_SUBDIR[tier]
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=N_SEEDS) as ex:
        futs = {}
        for i, bseed in enumerate(base_seeds):
            new_seed = seed_base + i
            if is_done(new_seed, FULL_STEPS):
                print(f"  [{tier}/{arm}] seed={new_seed}: reusing existing", flush=True)
                results[bseed] = new_seed
                continue
            extra, read_path = extra_tokens_for(arm, bseed, hub_lookup[bseed], tier)
            tokens = extra + ["network=read", f"read_path={read_path}"]
            futs[ex.submit(lambda s=new_seed, tk=tokens: launch(s, FULL_STEPS, tk, subdir).wait())] = (bseed, new_seed)
        for f in futs:
            bseed, new_seed = futs[f]
            f.result()
            results[bseed] = new_seed
    return results


def read_metrics_at(seed, checkpoint, is_source=False):
    d = source_dir(seed) if is_source else result_dir(seed)
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
    return dict(
        Q_sign_repost=q, opinionVar=opinion_var, postOpinionVar=post_opinion_var, sf1_ratio=sf1,
        crossCuttingFraction=float(at["crossCuttingFraction"]),
        interactionCrossCuttingFraction=float(at["interactionCrossCuttingFraction"]),
        bimodalityCoeff=float(at["bimodalityCoeff"]), opinionKurtosis=float(at["opinionKurtosis"]),
        disagreement=float(at["disagreement"]),
    )


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in TIER_BOUNDS:
        print(__doc__); sys.exit(1)
    tier = sys.argv[1]
    arms = [sys.argv[2]] if len(sys.argv) > 2 else list(ARM_SEED_BASE[tier].keys())

    base_seeds = [SOURCE_BASE_SEED + i for i in range(N_SEEDS)]
    print(f"Verifying source t0 snapshots on disk (seeds {base_seeds[0]}-{base_seeds[-1]})...", flush=True)
    for s in base_seeds:
        assert t0_gexf_path(s).exists(), f"missing step_0.gexf for seed {s}"
        assert is_done(s, FULL_STEPS), f"source control run incomplete for seed {s}"

    print(f"Deriving realized {tier}-tier neutral hub lists at t0...", flush=True)
    hub_lookup = {s: moderate_hub_ids_t0(s, tier) for s in base_seeds}
    for s in base_seeds:
        print(f"  seed={s}: {len(hub_lookup[s])} moderate {tier}-tier hubs -> {[a for a,_ in hub_lookup[s]]}", flush=True)

    arm_seeds = {}
    for arm in arms:
        print(f"\n=== running arm: {tier}/{arm} ===", flush=True)
        arm_seeds[arm] = run_arm(arm, tier, base_seeds, hub_lookup)

    metric_names = ["Q_sign_repost", "opinionVar", "postOpinionVar", "sf1_ratio",
                     "crossCuttingFraction", "interactionCrossCuttingFraction",
                     "bimodalityCoeff", "opinionKurtosis", "disagreement"]

    log_path = ROOT / "docs" / "report" / f"initial_state_bridging_{tier}tier.csv"
    with open(log_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["arm", "base_seed", "checkpoint"] + metric_names)
        for bseed in base_seeds:
            for cp in CHECKPOINTS:
                m = read_metrics_at(bseed, cp, is_source=True)
                w.writerow(["control", bseed, cp] + [m[k] for k in metric_names])
        for arm, mapping in arm_seeds.items():
            for bseed, new_seed in mapping.items():
                for cp in CHECKPOINTS:
                    m = read_metrics_at(new_seed, cp)
                    w.writerow([arm, bseed, cp] + [m[k] for k in metric_names])
    print(f"\nFull trajectory log: {log_path}")

    control_vals = {cp: {s: read_metrics_at(s, cp, is_source=True) for s in base_seeds} for cp in CHECKPOINTS}
    for arm in arms:
        arm_map = arm_seeds[arm]
        print(f"\n########## arm = {arm} (tier={tier}, n={N_SEEDS}) vs control, full trajectory ##########")
        for cp in CHECKPOINTS:
            arm_vals = {bseed: read_metrics_at(nseed, cp) for bseed, nseed in arm_map.items()}
            row = [f"step={cp:>6}"]
            for m in ["opinionVar", "postOpinionVar", "sf1_ratio", "Q_sign_repost", "crossCuttingFraction"]:
                paired = [(control_vals[cp][s][m], arm_vals[s][m]) for s in base_seeds
                          if control_vals[cp][s][m] is not None and arm_vals[s][m] is not None]
                c = np.array([cv for cv, tv in paired]); t = np.array([tv for cv, tv in paired])
                diff = t - c
                tstat = diff.mean() / (diff.std(ddof=1) / np.sqrt(len(diff))) if len(diff) > 1 and diff.std(ddof=1) > 0 else float("nan")
                row.append(f"{m}: c={c.mean():.4f} t={t.mean():.4f} diff={diff.mean():+.4f} t={tstat:+.2f}")
            print("  " + " | ".join(row))


if __name__ == "__main__":
    main()
