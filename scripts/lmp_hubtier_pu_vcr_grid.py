"""
2026-08-04 -- First p_u x vocal_comfort_radius JOINT grid, following up on the two independent 1-D
marginal sweeps (scripts/lmp_hubtier_pu_vcr_finegrain.py) that each showed a sign-reversing shape in
the "extreme camp" (non-hub bin0+bin4) per-capita post rate and its likely proximate mediator
(avgComfortRate). A 1-D slice at a time cannot distinguish a real 2-D phase boundary from two
independent, unrelated marginal effects -- this grid is the minimum step to start telling those
apart, per user's "let the thesis emerge from the data" approach (2026-08-04) rather than
pre-committing to a mechanism story.

Grid: p_u in {0.01, 0.03, 0.05, 0.15} x vcr in {0.1, 0.15, 0.2, 0.3} (4x4=16 cells). Deliberately
reuses points already run: baseline (p_u=0.05, vcr=0.1) plus the entire p_u marginal (vcr held at
0.1: p_u in {0.01,0.03,0.15}, from the OAT battery + finegrain sweep) and entire vcr marginal (p_u
held at 0.05: vcr in {0.15,0.2,0.3}, same sources) -- 7 of 16 cells already exist. Only the 9
off-diagonal (both non-baseline) cells are new:
  (0.01,0.15) (0.01,0.2) (0.01,0.3)
  (0.03,0.15) (0.03,0.2) (0.03,0.3)
  (0.15,0.15) (0.15,0.2) (0.15,0.3)

Same seed block (8900000-8900014) and hub-tier construction as both prior sweeps (reuses the OAT
battery's HK class-selection dry run). control/N_silent only, n=15, steps=40000. 9 new cells x 2
arms x 15 seeds = 270 new runs.

Usage: nohup python3 scripts/lmp_hubtier_pu_vcr_grid.py > logs/lmp_hubtier_pu_vcr_grid_stdout.log 2>&1 &
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
HK_CLASS_SELECT_SUBDIR = f"{OAT_SUBDIR}/_class_selection_hk"
SUBDIR = "2026-08-04_lmp_hubtier_pu_vcr_grid"
ARMS = ["control", "N_silent"]

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

PU_GRID = [0.01, 0.03, 0.05, 0.15]
VCR_GRID = [0.1, 0.15, 0.2, 0.3]

# maps a (pu, vcr) grid cell -> subdir of ALREADY-COMPLETED data if it exists, else None (new cell)
_EXISTING = {
    (0.05, 0.1): f"{OAT_SUBDIR}/baseline",
    (0.01, 0.1): f"{OAT_SUBDIR}/pu_001",
    (0.03, 0.1): f"{FG_SUBDIR}/pu_003",
    (0.15, 0.1): f"{OAT_SUBDIR}/pu_015",
    (0.05, 0.15): f"{FG_SUBDIR}/vcr_015",
    (0.05, 0.2): f"{OAT_SUBDIR}/vcr_02",
    (0.05, 0.3): f"{FG_SUBDIR}/vcr_03",
}


def cell_name(pu, vcr):
    return f"pu{pu}_vcr{vcr}"


def cell_subdir(pu, vcr):
    key = (pu, vcr)
    if key in _EXISTING:
        return _EXISTING[key]
    return f"{SUBDIR}/{cell_name(pu, vcr)}"


NEW_CELLS = [(pu, vcr) for pu in PU_GRID for vcr in VCR_GRID if (pu, vcr) not in _EXISTING]


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
    logfile = ROOT / "logs" / f"lmpgrid_seed{seed}_{subdir.replace('/', '_')}.log"
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


def pop_counts_nonhub(seed, subdir, arm):
    d = result_dir(seed, f"{subdir}/{arm}")
    counts = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0}
    with open(d / "degrees" / "agent_snapshot_final.csv", newline="") as f:
        for r in csv.DictReader(f):
            if r["isTarget"] == "0":
                counts[camp_bin(float(r["opinion"]))] += 1
    return counts


def combined_extreme_percapita(seed, subdir, arm, checkpoint=FULL_STEPS, window=WINDOW):
    d = result_dir(seed, f"{subdir}/{arm}")
    with open(d / "posts" / "post_result.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    lo = checkpoint - window
    total = sum(int(r["bin_0"]) + int(r["bin_4"]) for r in rows if lo < int(r["step"]) <= checkpoint)
    pop = pop_counts_nonhub(seed, subdir, arm)
    n = pop[0] + pop[4]
    return total / n / window if n > 0 else float("nan")


def comfort_extreme(subdir, arm):
    vals = []
    for s in SEEDS:
        d = result_dir(s, f"{subdir}/{arm}")
        if d is None:
            continue
        with open(d / "degrees" / "agent_snapshot_final.csv", newline="") as fh:
            agent_vals = [float(r["avgComfortRate"]) for r in csv.DictReader(fh)
                          if r["isTarget"] == "0" and camp_bin(float(r["opinion"])) in (0, 4)]
            vals.append(np.mean(agent_vals))
    return np.array(vals)


def report_cell(pu, vcr):
    subdir = cell_subdir(pu, vcr)
    c = np.array([combined_extreme_percapita(s, subdir, "control") for s in SEEDS])
    m = np.array([combined_extreme_percapita(s, subdir, "N_silent") for s in SEEDS])
    diff = m - c
    valid = ~np.isnan(diff)
    dv = diff[valid]
    sd = dv.std(ddof=1)
    t = dv.mean() / (sd / np.sqrt(len(dv))) if sd > 0 else float("nan")
    d = dv.mean() / sd if sd > 0 else float("nan")

    cc = comfort_extreme(subdir, "control")
    mm = comfort_extreme(subdir, "N_silent")
    cdiff = mm - cc
    csd = cdiff.std(ddof=1)
    ct = cdiff.mean() / (csd / np.sqrt(len(cdiff))) if csd > 0 else float("nan")
    cd = cdiff.mean() / csd if csd > 0 else float("nan")
    return dict(pu=pu, vcr=vcr, t=t, d=d, comfort_t=ct, comfort_d=cd)


def main():
    print("=== Deriving hub-tier groups (reused HK class-selection) ===", flush=True)
    groups_by_seed = {s: derive_groups(s) for s in SEEDS}

    print(f"\n=== Launching {len(NEW_CELLS)} new grid cells x {len(SEEDS)} seeds x 2 arms ===", flush=True)
    jobs = []
    for pu, vcr in NEW_CELLS:
        subdir = cell_subdir(pu, vcr)
        for s in SEEDS:
            groups = groups_by_seed[s]
            pin_token = build_pin_token(groups)
            m_ids = groups["M"][0]
            for arm in ARMS:
                tokens = [pin_token, f"p_u={pu}", f"vocal_comfort_radius={vcr}"]
                if arm == "N_silent":
                    idstr = ",".join(str(a) for a in m_ids)
                    tokens += [f"silent_until_ids={idstr}", f"activation_step={FULL_STEPS + 1}"]
                jobs.append((s, FULL_STEPS, f"{subdir}/{arm}", tokens))
    run_wave(jobs, max_workers=20)

    print("\n=== 4x4 grid: combined bin0+bin4 per-capita d (posting rate) ===")
    print(f"{'p_u \\\\ vcr':>10}" + "".join(f"{v:>10}" for v in VCR_GRID))
    for pu in PU_GRID:
        row = []
        for vcr in VCR_GRID:
            r = report_cell(pu, vcr)
            row.append(f"{r['d']:+.3f}")
        print(f"{pu:>10}" + "".join(f"{c:>10}" for c in row))

    print("\n=== 4x4 grid: combined bin0+bin4 avgComfortRate d ===")
    print(f"{'p_u \\\\ vcr':>10}" + "".join(f"{v:>10}" for v in VCR_GRID))
    for pu in PU_GRID:
        row = []
        for vcr in VCR_GRID:
            r = report_cell(pu, vcr)
            row.append(f"{r['comfort_d']:+.3f}")
        print(f"{pu:>10}" + "".join(f"{c:>10}" for c in row))

    print("\n=== Full detail per cell ===")
    for pu in PU_GRID:
        for vcr in VCR_GRID:
            r = report_cell(pu, vcr)
            print(f"  p_u={pu} vcr={vcr}: posting d={r['d']:+.3f} (t={r['t']:+.2f})  "
                  f"comfort d={r['comfort_d']:+.3f} (t={r['comfort_t']:+.2f})")


if __name__ == "__main__":
    main()
