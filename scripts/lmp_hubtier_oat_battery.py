"""
2026-08-04 -- 5-parameter OAT battery for the L/M/P hub-tier "moderate presence -> non-hub extreme
camp posts more" finding (docs/report/2026-08-02-delayed-moderate-conduit-pilot.md), modeled directly
on the project's own precedent battery (`delayed_moderate_pilot_postfix_oat_battery.py`, commit
e07e214) which swept p_u / vocal_comfort_radius / class-topK / class-threshold / network-topology for
the earlier single-moderate-class design. That precedent's "class top-K" and "class threshold" axes
(top-K by followerCount among |intrinsicOpinion|<threshold) don't translate directly to this design
(hub-tier selection here is top-N_HUB by followerCount, UNFILTERED by opinion) -- substituted with
two analogous "how is the hub tier built" sensitivity axes: N_HUB (hub-tier size) and the Extreme
category's pin magnitude (how extreme "extreme" is).

Baseline uses bc_recovery=0.0001 (this project's own DEFAULT, not the exploratory 2026-08-03-screen
point used in the first-pass/robustness runs) -- both bc points already passed the robustness check,
and the default is the more citable point for a paper claim. Scoped to control/N_silent only (the
arms the finding concerns), per this pilot's established narrowing choice.

10 configs (1 baseline + 2 levels each for p_u/vcr/N_HUB/pin-magnitude + 1 network-topology change):
  baseline   : (all defaults)
  pu_001     : p_u=0.01
  pu_015     : p_u=0.15
  vcr_005    : vocal_comfort_radius=0.05
  vcr_02     : vocal_comfort_radius=0.2
  nhub30     : N_HUB=30 (groups scaled 5/5/10/5/5, vs default 60 = 10/10/20/10/10)
  nhub90     : N_HUB=90 (groups scaled 15/15/30/15/15)
  pinext08   : Extreme category pinned to +-0.8 instead of +-1.0
  pinext06   : Extreme category pinned to +-0.6 (matches this project's own natural-extreme
               classification threshold, |intrinsicOpinion|>=0.6, used elsewhere in this pilot)
  dcsbm      : network=dcsbm instead of hk (needs its own fresh class-selection dry run)

n=15, fresh seed block (8900000-8900014, unused elsewhere). All non-dcsbm configs share one HK
class-selection dry-run batch (hub-tier membership depends only on t0 followerCount, unaffected by
p_u/vcr/bc_recovery choices at the SAME topology).

Usage: nohup python3 scripts/lmp_hubtier_oat_battery.py > logs/lmp_hubtier_oat_battery_stdout.log 2>&1 &
       (then disown)
"""
import concurrent.futures
import csv
import random
import subprocess
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
_JARS = list(ROOT.glob("lib/**/*.jar"))
LIBCP = ":".join(str(p) for p in _JARS) + (":" if _JARS else "") + str(ROOT / "bin")

N = 1000
FULL_STEPS = 40000
WINDOW = 2000
SEEDS = [8900000 + i for i in range(15)]
SUBDIR = "2026-08-04_lmp_hubtier_oat_battery"
HK_CLASS_SELECT_SUBDIR = f"{SUBDIR}/_class_selection_hk"
DCSBM_CLASS_SELECT_SUBDIR = f"{SUBDIR}/_class_selection_dcsbm"
ARMS = ["control", "N_silent"]
bin_label = {0: "extreme(-)", 1: "pre-extreme(-)", 2: "moderate", 3: "pre-extreme(+)", 4: "extreme(+)"}

BASE_TOKENS = [
    "network=hk", "hk_m=15", "hk_a=4", "hk_pt=0.05",
    "max_follow=43.8638", "follow_prob=0.01", "feed_capacity=15",
    "access_prob=0.1", "p_u=0.05",
    "bc_init=0.800000", "bc_dec=0.500000", "bc_floor=0.2", "bc_recovery=0.0001", "bc_ceiling=1.0",
    "vocal_comfort_radius=0.1", "repost_prob=0.1", "relay_enabled=false",
    "out_of_bc_repost_prob=0.01", "rel_attrib=original",
    "stub_dist=uniform", "stub_min=0.82", "stub_max=0.82",
    "evict_beta=-1", "init_prune=trim",
    "initial_pp=0.25537", "max_pp=1.0", "min_pp=0.01", "pp_relax_eta=0.100000",
    "neutral_band=0.2",
    "extreme=none", "n_neutral=0", "alpha=0",
]

DEFAULT_N_HUB = 60
DEFAULT_EXT_MAG = 1.0


def group_sizes(n_hub, ext_mag):
    unit = n_hub // 6
    assert unit * 6 == n_hub, f"N_HUB={n_hub} must be divisible by 6"
    return [("E_minus", unit, -ext_mag), ("P_minus", unit, -0.4), ("M", unit * 2, 0.0),
             ("P_plus", unit, 0.4), ("E_plus", unit, ext_mag)]


# (config_name, override_tokens, n_hub, ext_mag, network)
CONFIGS = [
    ("baseline", [], DEFAULT_N_HUB, DEFAULT_EXT_MAG, "hk"),
    ("pu_001", ["p_u=0.01"], DEFAULT_N_HUB, DEFAULT_EXT_MAG, "hk"),
    ("pu_015", ["p_u=0.15"], DEFAULT_N_HUB, DEFAULT_EXT_MAG, "hk"),
    ("vcr_005", ["vocal_comfort_radius=0.05"], DEFAULT_N_HUB, DEFAULT_EXT_MAG, "hk"),
    ("vcr_02", ["vocal_comfort_radius=0.2"], DEFAULT_N_HUB, DEFAULT_EXT_MAG, "hk"),
    ("nhub30", [], 30, DEFAULT_EXT_MAG, "hk"),
    ("nhub90", [], 90, DEFAULT_EXT_MAG, "hk"),
    ("pinext08", [], DEFAULT_N_HUB, 0.8, "hk"),
    ("pinext06", [], DEFAULT_N_HUB, 0.6, "hk"),
    ("dcsbm", ["network=dcsbm", "sbm_k=4", "sbm_pin=0.08", "sbm_pout=0.002", "sbm_gamma=2.3", "sbm_deg=15"],
     DEFAULT_N_HUB, DEFAULT_EXT_MAG, "dcsbm"),
]


def result_dir(seed, subdir):
    cands = sorted(ROOT.glob(f"results/{subdir}/run_{seed}_*"))
    return cands[-1] if cands else None


def is_done(seed, subdir, steps):
    d = result_dir(seed, subdir)
    if d is None:
        return False
    rp = d / "metrics" / "results.csv"
    if not rp.exists():
        return False
    with open(rp, newline="") as f:
        rows = list(csv.DictReader(f))
    return bool(rows) and int(rows[-1]["step"]) >= steps


def launch(seed, steps, subdir, extra_tokens, log_gexf=False):
    tokens = [f"seed={seed}", f"steps={steps}", f"n={N}", "force=true",
              f"log_gexf={str(log_gexf).lower()}", f"results_subdir={subdir}"] \
        + BASE_TOKENS + extra_tokens
    logfile = ROOT / "logs" / f"lmpoat_seed{seed}_{subdir.replace('/', '_')}.log"
    logfile.parent.mkdir(exist_ok=True)
    with open(logfile, "w") as lf:
        p = subprocess.Popen(["java", "-Xmx2g", "-cp", LIBCP, "dynamics.OpinionDynamics", *tokens],
                              stdout=lf, stderr=subprocess.STDOUT, cwd=ROOT)
    return p


def run_wave(jobs, max_workers=20):
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = []
        for seed, steps, subdir, tokens in jobs:
            if is_done(seed, subdir, steps):
                print(f"  seed={seed} subdir={subdir}: reusing existing", flush=True)
                continue
            futs.append(ex.submit(lambda s=seed, st=steps, sd=subdir, tk=tokens: launch(s, st, sd, tk).wait()))
        for f in futs:
            f.result()


def camp_bin(x):
    shifted = x + 1.0
    return min(int(shifted / 0.4), 4)


def derive_groups(seed, class_select_subdir, n_hub, ext_mag):
    d = result_dir(seed, class_select_subdir)
    ranked = []
    with open(d / "degrees" / "agent_snapshot_t0.csv", newline="") as f:
        for r in csv.DictReader(f):
            ranked.append((int(r["followerCount"]), int(r["agentId"])))
    ranked.sort(reverse=True)
    top_ids = [aid for _, aid in ranked[:n_hub]]
    assert len(top_ids) == n_hub, f"seed={seed}: only {len(top_ids)} agents available, need {n_hub}"
    rng = random.Random(seed)
    rng.shuffle(top_ids)
    groups = {}
    i = 0
    for name, size, target in group_sizes(n_hub, ext_mag):
        groups[name] = (top_ids[i:i + size], target)
        i += size
    return groups


def build_pin_token(groups):
    pairs = []
    for _, (ids, target) in groups.items():
        for aid in ids:
            pairs.append(f"{aid}:{target}")
    return "pin_opinion_ids=" + ",".join(pairs)


def pop_counts_nonhub(seed, subdir, arm):
    d = result_dir(seed, f"{subdir}/{arm}")
    counts = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0}
    with open(d / "degrees" / "agent_snapshot_final.csv", newline="") as f:
        for r in csv.DictReader(f):
            if r["isTarget"] == "0":
                counts[camp_bin(float(r["opinion"]))] += 1
    return counts


def nonhub_percapita(seed, subdir, arm, b, checkpoint=FULL_STEPS, window=WINDOW):
    d = result_dir(seed, f"{subdir}/{arm}")
    with open(d / "posts" / "post_result.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    lo = checkpoint - window
    total = sum(int(r[f"bin_{b}"]) for r in rows if lo < int(r["step"]) <= checkpoint)
    n = pop_counts_nonhub(seed, subdir, arm)[b]
    return total / n / window if n > 0 else float("nan")


def struct_metric(seed, subdir, arm, col, checkpoint=FULL_STEPS, window=WINDOW):
    d = result_dir(seed, f"{subdir}/{arm}")
    with open(d / "metrics" / "results.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    lo = checkpoint - window
    wrows = [r for r in rows if lo < int(r["step"]) <= checkpoint]
    return np.mean([float(r[col]) for r in wrows])


def main():
    print("=== Phase 1: class-selection dry runs (hk + dcsbm) ===", flush=True)
    run_wave([(s, 0, HK_CLASS_SELECT_SUBDIR, []) for s in SEEDS], max_workers=len(SEEDS))
    run_wave([(s, 0, DCSBM_CLASS_SELECT_SUBDIR, ["network=dcsbm", "sbm_k=4", "sbm_pin=0.08",
                                                   "sbm_pout=0.002", "sbm_gamma=2.3", "sbm_deg=15"])
              for s in SEEDS], max_workers=len(SEEDS))

    print("\n=== Deriving hub-tier groups per (config, seed) ===", flush=True)
    groups_by_config_seed = {}
    for name, _, n_hub, ext_mag, network in CONFIGS:
        cs_subdir = DCSBM_CLASS_SELECT_SUBDIR if network == "dcsbm" else HK_CLASS_SELECT_SUBDIR
        groups_by_config_seed[name] = {s: derive_groups(s, cs_subdir, n_hub, ext_mag) for s in SEEDS}

    print("\n=== Phase 2: launching all (config, seed, arm) runs ===", flush=True)
    jobs = []
    for name, override_tokens, n_hub, ext_mag, network in CONFIGS:
        for s in SEEDS:
            groups = groups_by_config_seed[name][s]
            pin_token = build_pin_token(groups)
            m_ids = groups["M"][0]
            for arm in ARMS:
                tokens = [pin_token] + override_tokens
                if arm == "N_silent":
                    idstr = ",".join(str(a) for a in m_ids)
                    tokens += [f"silent_until_ids={idstr}", f"activation_step={FULL_STEPS + 1}"]
                jobs.append((s, FULL_STEPS, f"{SUBDIR}/{name}/{arm}", tokens))
    run_wave(jobs, max_workers=20)

    print(f"\n=== N_silent vs control, non-hub, n={len(SEEDS)}, per config ===")
    for name, *_ in CONFIGS:
        subdir = f"{SUBDIR}/{name}"
        print(f"\n### {name} ###")
        for b in range(5):
            c = np.array([nonhub_percapita(s, subdir, "control", b) for s in SEEDS])
            m = np.array([nonhub_percapita(s, subdir, "N_silent", b) for s in SEEDS])
            diff = m - c
            valid = ~np.isnan(diff)
            if valid.sum() < 2:
                print(f"  bin{b} {bin_label[b]:>14}: insufficient non-hub population in this bin")
                continue
            dv = diff[valid]
            t = dv.mean() / (dv.std(ddof=1) / np.sqrt(len(dv))) if dv.std(ddof=1) > 0 else float("nan")
            pct = 100 * dv.mean() / c[valid].mean() if c[valid].mean() else float("nan")
            print(f"  bin{b} {bin_label[b]:>14}: control={c[valid].mean():.5f}  N_silent={m[valid].mean():.5f}  "
                  f"diff={dv.mean():+.5f} ({pct:+.1f}%)  t={t:.2f}  n={valid.sum()}")
        for col in ["opinionVar", "bimodalityCoeff", "opinionAssortativity", "crossCuttingFraction"]:
            c = np.array([struct_metric(s, subdir, "control", col) for s in SEEDS])
            m = np.array([struct_metric(s, subdir, "N_silent", col) for s in SEEDS])
            diff = m - c
            t = diff.mean() / (diff.std(ddof=1) / np.sqrt(len(diff))) if diff.std(ddof=1) > 0 else float("nan")
            print(f"  {col:>22}: control={c.mean():.4f}  N_silent={m.mean():.4f}  diff={diff.mean():+.4f}  t={t:.2f}")


if __name__ == "__main__":
    main()
