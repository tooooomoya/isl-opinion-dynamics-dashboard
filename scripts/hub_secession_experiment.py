"""
2026-07-26 -- Per-tier secession test, finally executing the design named (but never run) in
docs/report/2026-07-21-conduit-experiment-design.md's "Experiment redesign: secession test, not
addition test" section.

For each of the 20 already-equilibrated base networks (scripts/hub_tier_check_v15_synth.py, seeds
1726000-1726019, n=1000, steps=40000, current v15-frozen calibration point, init_dist=gaussian),
build a TREATMENT variant where every neutral hub (|opinion|<0.2) within the target TIER -- as
REALIZED in that seed's own network, not a hand-picked single agent -- has its opinion swapped to
extreme (sign preserved, magnitude 0.9). CONTROL is the unmodified network. Continue both
CONTINUE_STEPS further steps via network=read and compare structural/polarization outcomes,
treatment vs. control, paired by base seed.

Why deplete the WHOLE tier's moderate sub-population instead of one hand-picked hub (the 2026-07-18/
20 series' design): that 2026-07-21 postmortem found single-agent identity swaps can't isolate a
causal effect at all -- "neutral hub" is an emergent role with a huge reserve pool (hundreds of
other moderate agents), so swapping one occupant just gets the role refilled, not removed. Depleting
every moderate agent actually occupying a given reach tier, at once, is the "population-composition
manipulation" that document names as the legitimate, different experiment this substitution problem
leaves available.

Every dynamics-relevant parameter is pinned explicitly (same FIXED dict as
hub_tier_check_v15_synth.py) per this project's own pU-mislabeling lesson -- network=read does NOT
reconstruct simulation config from the source GEXF, only network structure + per-agent state.

Distinct seed ranges are required per (tier, arm): ExperimentConfig.tag() does not encode read_path
or which agents were swapped, so two runs with the same seed number and otherwise-identical config
collide on the same results/ folder name.

Usage: python3 scripts/hub_secession_experiment.py <tier>     # tier in {mega, mid, small}
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
CONTINUE_STEPS = 20000  # NOT accessProb-time-rescaled -- open caveat, see docstring precedent
BASE_SEEDS = list(range(1726000, 1726020))
MODERATE_THRESHOLD = 0.2
SWAP_MAGNITUDE = 0.9

TIER_BOUNDS = {"mega": (500, N), "mid": (100, 500), "small": (50, 100)}
# (control_seed_base, treatment_seed_base); continuation seed = base + (base_seed - 1726000)
TIER_SEED_OFFSETS = {
    "mid":   (2000000, 2010000),
    "mega":  (2020000, 2030000),
    "small": (2040000, 2050000),
}

GEXF_NS = "http://gexf.net/1.3"
SCRATCH = ROOT / "results" / "temp" / "secession"

# Verbatim from hub_tier_check_v15_synth.py's FIXED dict (2026-07-25 "Calibration closed for now"
# frozen ExperimentConfig snapshot) -- kept identical so the continuation is governed by the same
# dynamics as the base equilibrium run, only network=read/read_path/seed/steps differ.
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
    """(agentId, opinion) for agents with lo < followerCount <= hi and |opinion| < MODERATE_THRESHOLD,
    read from the already-validated Java-computed agent_snapshot_final.csv (not re-derived from GEXF
    edges) -- same source hub_tier_check_v15_synth.py used, so tier membership is guaranteed
    consistent with the confirmed tier characterization."""
    candidates = sorted(ROOT.glob(f"results/run_{seed}_*"), key=lambda p: p.stat().st_mtime)
    d = candidates[-1]
    snap_path = d / "degrees" / "agent_snapshot_final.csv"
    hits = []
    with open(snap_path, newline="") as f:
        for r in csv.DictReader(f):
            op, fo = float(r["opinion"]), int(r["followerCount"])
            if lo < fo <= hi and abs(op) < MODERATE_THRESHOLD:
                hits.append((int(r["agentId"]), op))
    return hits


def write_swapped_gexf(src_path, dst_path, swap_list):
    """swap_list: [(agentId, old_opinion), ...]. New opinion = +/-SWAP_MAGNITUDE, sign preserved
    (0.0 -> treated as non-negative, swaps to +SWAP_MAGNITUDE; ties at exactly 0 are vanishingly
    rare under a continuous gaussian init and don't need special handling).

    2026-07-26 fix: sets BOTH 'opinion' and 'intrinsicOpinion', not opinion alone. Agent.java:411's
    FJ update (`opinion = stubbornness*intrinsicOpinion + (1-stubbornness)*assimilated`) pulls
    opinion back toward intrinsicOpinion every step, weighted by stubbornness (0.82 here) -- leaving
    intrinsicOpinion at the old moderate value meant the swap mechanically decayed away (measured:
    93% of swapped agents had reverted to |opinion|<0.2 by step 20000 under the opinion-only version
    of this function). Same failure mode already diagnosed for the older InterventionSetup pathway,
    docs/report/2026-07-07-model-revision-requirements.md's R4 "Full hub pinning". stubbornness
    itself is deliberately left untouched (user decision, 2026-07-26) -- swapped agents keep their
    normal susceptibility to social influence going forward, rather than R4's stubbornness=1.0
    full pin; only the two opinion-valued attributes are overwritten."""
    ET.register_namespace("", GEXF_NS)
    tree = ET.parse(src_path)
    root = tree.getroot()
    attr_ids = {}
    for attrs in root.iter(f"{{{GEXF_NS}}}attributes"):
        for a in attrs.iter(f"{{{GEXF_NS}}}attribute"):
            if a.get("title") in ("opinion", "intrinsicOpinion"):
                attr_ids[a.get("title")] = a.get("id")
    missing_attrs = {"opinion", "intrinsicOpinion"} - set(attr_ids)
    if missing_attrs:
        raise RuntimeError(f"attribute definition(s) not found in {src_path}: {missing_attrs}")
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
        raise RuntimeError(f"agents not found (or missing one of the two attvalues) in {src_path}: {missing}")
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(dst_path, xml_declaration=True, encoding="UTF-8")


def launch(seed, read_path):
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
    logfile = ROOT / "logs" / f"secession_seed{seed}.log"
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
        last = list(csv.DictReader(f))[-1]
    q = None
    with open(mod_path, newline="") as f:
        for row in csv.DictReader(f):
            q = float(row["Q_sign_repost"])  # last row wins
    opinion_var = float(last["opinionVar"])
    post_opinion_var = float(last["postOpinionVar"])
    sf1 = post_opinion_var / opinion_var if opinion_var > 0 else None
    return dict(
        crossCuttingFraction=float(last["crossCuttingFraction"]),
        interactionCrossCuttingFraction=float(last["interactionCrossCuttingFraction"]),
        Q_sign_repost=q,
        opinionVar=opinion_var,
        sf1_ratio=sf1,
        bimodalityCoeff=float(last["bimodalityCoeff"]),
        opinionKurtosis=float(last["opinionKurtosis"]),
        disagreement=float(last["disagreement"]),
    )


def run_arm(condition, tier, base_seeds, swap_lookup, seed_base):
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
        futs = {}
        for i, bseed in enumerate(base_seeds):
            cont_seed = seed_base + i
            existing = read_metrics(cont_seed)
            if existing is not None:
                print(f"  [{condition}] seed={cont_seed} (base={bseed}): reusing existing result", flush=True)
                results[bseed] = existing
                continue
            if condition == "control":
                read_path = base_gexf_path(bseed)
            else:
                src = base_gexf_path(bseed)
                dst = SCRATCH / f"{tier}_treatment_from{bseed}.gexf"
                write_swapped_gexf(src, dst, swap_lookup[bseed])
                read_path = dst
            futs[ex.submit(lambda s=cont_seed, rp=read_path: (launch(s, rp).wait(), read_metrics(s))[1])] = (bseed, cont_seed)
        for fut in concurrent.futures.as_completed(futs):
            bseed, cont_seed = futs[fut]
            results[bseed] = fut.result()
    return results


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in TIER_BOUNDS:
        print(__doc__)
        sys.exit(1)
    tier = sys.argv[1]
    lo, hi = TIER_BOUNDS[tier]
    control_base, treatment_base = TIER_SEED_OFFSETS[tier]

    swap_lookup = {}
    for bseed in BASE_SEEDS:
        hits = moderate_hub_ids(bseed, lo, hi)
        swap_lookup[bseed] = hits
        print(f"seed={bseed}: {len(hits)} moderate {tier}-tier hubs to swap -> {[a for a, _ in hits]}", flush=True)

    print(f"\n[{tier}] launching CONTROL ({len(BASE_SEEDS)} seeds, base={control_base})...", flush=True)
    control_results = run_arm("control", tier, BASE_SEEDS, swap_lookup, control_base)
    print(f"[{tier}] launching TREATMENT ({len(BASE_SEEDS)} seeds, base={treatment_base})...", flush=True)
    treatment_results = run_arm("treatment", tier, BASE_SEEDS, swap_lookup, treatment_base)

    log_path = ROOT / "docs" / "report" / f"hub_secession_{tier}.csv"
    metric_names = ["crossCuttingFraction", "interactionCrossCuttingFraction", "Q_sign_repost",
                     "opinionVar", "sf1_ratio", "bimodalityCoeff", "opinionKurtosis", "disagreement"]
    with open(log_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["condition", "base_seed", "n_swapped"] + metric_names)
        for bseed in BASE_SEEDS:
            for cond, res in (("control", control_results), ("treatment", treatment_results)):
                r = res.get(bseed)
                row = [cond, bseed, len(swap_lookup[bseed])]
                row += [r[m] if r else None for m in metric_names] if r else [None] * len(metric_names)
                w.writerow(row)
    print(f"\nFull log: {log_path}")

    print(f"\n=== [{tier}] paired treatment vs. control (n={len(BASE_SEEDS)} base seeds) ===")
    for m in metric_names:
        c = np.array([control_results[s][m] for s in BASE_SEEDS if control_results.get(s) and control_results[s][m] is not None])
        t = np.array([treatment_results[s][m] for s in BASE_SEEDS if treatment_results.get(s) and treatment_results[s][m] is not None])
        paired = [(control_results[s][m], treatment_results[s][m]) for s in BASE_SEEDS
                  if control_results.get(s) and treatment_results.get(s)
                  and control_results[s][m] is not None and treatment_results[s][m] is not None]
        diff = np.array([tv - cv for cv, tv in paired])
        tstat = diff.mean() / (diff.std(ddof=1) / np.sqrt(len(diff))) if len(diff) > 1 and diff.std(ddof=1) > 0 else float("nan")
        print(f"{m:>32}: control={c.mean():.4f}+/-{c.std():.4f}  treatment={t.mean():.4f}+/-{t.std():.4f}  "
              f"paired_diff={diff.mean():+.4f}+/-{diff.std():.4f}  paired_t={tstat:.2f}  (n_pairs={len(diff)})")


if __name__ == "__main__":
    main()
