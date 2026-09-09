"""
2026-08-04 -- Moderate-specificity check for the p_u x vcr interaction found in
scripts/lmp_hubtier_pu_vcr_grid.py (N_silent vs control, non-hub extreme-camp bin0+bin4). User
(2026-08-04, frank-critique request): before investing in a mechanistic explanation, is the p_u=0.15
row's "trough then sharp overshoot" interaction shape specific to silencing the MODERATE hub tier, or
would silencing ANY hub-tier category on this same outcome (the ordinary extreme camp's own
posting/comfort) show a similarly-shaped p_u-amplification pattern? If the latter, the finding isn't
about moderate's bridging role at all -- it would just be "low p_u = less noise = bigger effects for
any manipulation," a much less interesting and much less moderate-specific claim.

Placebo: P_silent (Pre-extreme hub tier silenced instead of Moderate) -- chosen over E_silent because
P_silent's effect size in the original 6-arm pilot was comparable in order of magnitude to N_silent's
(unlike E_silent, which dominated every arm and would trivially show large effects regardless of
p_u/vcr, making it an unfair/uninformative placebo).

8 diagnostic cells only (not the full 16), chosen to be maximally informative: the p_u=0.15 row (the
row with the qualitatively distinct "trough at low vcr -> largest-in-grid peak at vcr=0.3" shape) and
the p_u=0.05/baseline row (the row with the clean, ordinary-looking crossover), each across all 4 vcr
points. Reuses the ALREADY-COLLECTED control-arm data at those same 16 grid cells (no new control
runs needed) -- only P_silent needs running. Same seed block, hub-tier construction as the grid.

Usage: nohup python3 scripts/lmp_hubtier_specificity_check.py > logs/lmp_hubtier_specificity_check_stdout.log 2>&1 &
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
OAT_SUBDIR = "2026-08-04_lmp_hubtier_oat_battery"
FG_SUBDIR = "2026-08-04_lmp_hubtier_pu_vcr_finegrain"
GRID_SUBDIR = "2026-08-04_lmp_hubtier_pu_vcr_grid"
HK_CLASS_SELECT_SUBDIR = f"{OAT_SUBDIR}/_class_selection_hk"
SUBDIR = "2026-08-04_lmp_hubtier_specificity_check"

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

CELLS = [(pu, vcr) for pu in (0.05, 0.15) for vcr in (0.1, 0.15, 0.2, 0.3)]

# where the existing "control" arm data for each grid cell already lives
_CONTROL_SUBDIR = {
    (0.05, 0.1): f"{OAT_SUBDIR}/baseline",
    (0.05, 0.15): f"{FG_SUBDIR}/vcr_015",
    (0.05, 0.2): f"{OAT_SUBDIR}/vcr_02",
    (0.05, 0.3): f"{FG_SUBDIR}/vcr_03",
    (0.15, 0.1): f"{OAT_SUBDIR}/pu_015",
    (0.15, 0.15): f"{GRID_SUBDIR}/pu0.15_vcr0.15",
    (0.15, 0.2): f"{GRID_SUBDIR}/pu0.15_vcr0.2",
    (0.15, 0.3): f"{GRID_SUBDIR}/pu0.15_vcr0.3",
}


def cell_name(pu, vcr):
    return f"pu{pu}_vcr{vcr}"


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
    logfile = ROOT / "logs" / f"lmpspec_seed{seed}_{subdir.replace('/', '_')}.log"
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


def derive_groups(seed):
    d = result_dir(seed, HK_CLASS_SELECT_SUBDIR)
    ranked = []
    with open(d / "degrees" / "agent_snapshot_t0.csv", newline="") as f:
        for r in csv.DictReader(f):
            ranked.append((int(r["followerCount"]), int(r["agentId"])))
    ranked.sort(reverse=True)
    top_ids = [aid for _, aid in ranked[:60]]
    rng = random.Random(seed)
    rng.shuffle(top_ids)
    sizes = [("E_minus", 10, -1.0), ("P_minus", 10, -0.4), ("M", 20, 0.0),
             ("P_plus", 10, 0.4), ("E_plus", 10, 1.0)]
    groups = {}
    i = 0
    for name, size, target in sizes:
        groups[name] = (top_ids[i:i + size], target)
        i += size
    return groups


def build_pin_token(groups):
    pairs = []
    for _, (ids, target) in groups.items():
        for aid in ids:
            pairs.append(f"{aid}:{target}")
    return "pin_opinion_ids=" + ",".join(pairs)


def pop_counts_nonhub(seed, subdir):
    d = result_dir(seed, subdir)
    counts = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0}
    with open(d / "degrees" / "agent_snapshot_final.csv", newline="") as f:
        for r in csv.DictReader(f):
            if r["isTarget"] == "0":
                counts[camp_bin(float(r["opinion"]))] += 1
    return counts


def combined_extreme_percapita(seed, subdir, checkpoint=FULL_STEPS, window=WINDOW):
    d = result_dir(seed, subdir)
    with open(d / "posts" / "post_result.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    lo = checkpoint - window
    total = sum(int(r["bin_0"]) + int(r["bin_4"]) for r in rows if lo < int(r["step"]) <= checkpoint)
    pop = pop_counts_nonhub(seed, subdir)
    n = pop[0] + pop[4]
    return total / n / window if n > 0 else float("nan")


def comfort_extreme(subdir):
    vals = []
    for s in SEEDS:
        d = result_dir(s, subdir)
        if d is None:
            continue
        with open(d / "degrees" / "agent_snapshot_final.csv", newline="") as fh:
            agent_vals = [float(r["avgComfortRate"]) for r in csv.DictReader(fh)
                          if r["isTarget"] == "0" and camp_bin(float(r["opinion"])) in (0, 4)]
            vals.append(np.mean(agent_vals))
    return np.array(vals)


def report_cell(pu, vcr):
    control_subdir = _CONTROL_SUBDIR[(pu, vcr)] + "/control"
    psilent_subdir = f"{SUBDIR}/{cell_name(pu, vcr)}/P_silent"
    c = np.array([combined_extreme_percapita(s, control_subdir) for s in SEEDS])
    p = np.array([combined_extreme_percapita(s, psilent_subdir) for s in SEEDS])
    diff = p - c
    valid = ~np.isnan(diff)
    dv = diff[valid]
    sd = dv.std(ddof=1)
    t = dv.mean() / (sd / np.sqrt(len(dv))) if sd > 0 else float("nan")
    d = dv.mean() / sd if sd > 0 else float("nan")

    cc = comfort_extreme(control_subdir)
    pp = comfort_extreme(psilent_subdir)
    cdiff = pp - cc
    csd = cdiff.std(ddof=1)
    ct = cdiff.mean() / (csd / np.sqrt(len(cdiff))) if csd > 0 else float("nan")
    cd = cdiff.mean() / csd if csd > 0 else float("nan")
    return dict(pu=pu, vcr=vcr, t=t, d=d, comfort_t=ct, comfort_d=cd)


def main():
    print("=== Deriving hub-tier groups (reused HK class-selection) ===", flush=True)
    groups_by_seed = {s: derive_groups(s) for s in SEEDS}

    print(f"\n=== Launching P_silent at {len(CELLS)} cells x {len(SEEDS)} seeds ===", flush=True)
    jobs = []
    for pu, vcr in CELLS:
        for s in SEEDS:
            groups = groups_by_seed[s]
            pin_token = build_pin_token(groups)
            p_ids = groups["P_minus"][0] + groups["P_plus"][0]
            idstr = ",".join(str(a) for a in p_ids)
            tokens = [pin_token, f"p_u={pu}", f"vocal_comfort_radius={vcr}",
                      f"silent_until_ids={idstr}", f"activation_step={FULL_STEPS + 1}"]
            jobs.append((s, FULL_STEPS, f"{SUBDIR}/{cell_name(pu, vcr)}/P_silent", tokens))
    run_wave(jobs, max_workers=20)

    print("\n=== P_silent vs control (placebo): posting-rate d ===")
    print(f"{'p_u \\\\ vcr':>10}{'0.1':>10}{'0.15':>10}{'0.2':>10}{'0.3':>10}")
    for pu in (0.05, 0.15):
        row = [f"{report_cell(pu, vcr)['d']:+.3f}" for vcr in (0.1, 0.15, 0.2, 0.3)]
        print(f"{pu:>10}" + "".join(f"{c:>10}" for c in row))

    print("\n=== P_silent vs control (placebo): comfortRate d ===")
    print(f"{'p_u \\\\ vcr':>10}{'0.1':>10}{'0.15':>10}{'0.2':>10}{'0.3':>10}")
    for pu in (0.05, 0.15):
        row = [f"{report_cell(pu, vcr)['comfort_d']:+.3f}" for vcr in (0.1, 0.15, 0.2, 0.3)]
        print(f"{pu:>10}" + "".join(f"{c:>10}" for c in row))

    print("\n=== Full detail per cell ===")
    for pu, vcr in CELLS:
        r = report_cell(pu, vcr)
        print(f"  p_u={pu} vcr={vcr}: posting d={r['d']:+.3f} (t={r['t']:+.2f})  "
              f"comfort d={r['comfort_d']:+.3f} (t={r['comfort_t']:+.2f})")

    print("\n=== Recall N_silent (moderate) shape for comparison ===")
    print("N_silent posting d: pu=0.05: [-0.748, +0.114, +0.593, +0.544]  pu=0.15: [-1.101, -1.032, +0.199, +1.365]")
    print("N_silent comfort d: pu=0.05: [-0.495, +0.608, +0.882, +0.791]  pu=0.15: [-0.743, -0.517, +0.390, +1.778]")


if __name__ == "__main__":
    main()
