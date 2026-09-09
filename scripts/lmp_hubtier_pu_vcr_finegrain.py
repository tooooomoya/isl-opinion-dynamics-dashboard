"""
2026-08-04 -- Finer-grained p_u / vocal_comfort_radius sweep, following up on the 10-config OAT
battery (scripts/lmp_hubtier_oat_battery.py) whose combined-bin0+bin4 ("extreme camp") effect size
showed a seemingly-monotonic trend across p_u (d=+0.881 at p_u=0.01 [REVERSED] -> d=-0.748 at
p_u=0.05 [baseline] -> d=-1.101 at p_u=0.15) but a NON-monotonic, harder-to-read shape across
vocal_comfort_radius (d=+0.163 [~null] at vcr=0.05 -> d=-0.748 at vcr=0.1 [baseline] -> d=+0.593
[REVERSED] at vcr=0.2). User (2026-08-04): worth mapping both shapes more finely -- p_u's apparent
monotonicity may be mechanistically informative (this project's own research-direction.md already
frames P_u as the Type-1/Type-2 phase-diagram axis); vcr's shape needs more points before it means
anything.

New points (existing baseline/pu_001/pu_015/vcr_005/vcr_02 from the OAT battery are reused, not
re-run):
  p_u:  0.02, 0.03 (bracket the 0.01->0.05 sign-flip region), 0.10 (between 0.05 and 0.15), 0.25
        (beyond 0.15, check whether the baseline-direction trend continues or saturates/reverses)
  vcr:  0.075 (between 0.05 and 0.1), 0.15 (between 0.1 and 0.2), 0.3 (beyond 0.2)

Same seed block (8900000-8900014), same hub-tier construction (N_HUB=60, Extreme pin=+-1.0) and
class-selection dry run (reused from the OAT battery's HK_CLASS_SELECT_SUBDIR) as the original
battery, for direct comparability. control/N_silent only, n=15, steps=40000.

Usage: nohup python3 scripts/lmp_hubtier_pu_vcr_finegrain.py > logs/lmp_hubtier_pu_vcr_finegrain_stdout.log 2>&1 &
       (then disown)
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
FULL_STEPS = 40000
WINDOW = 2000
SEEDS = [8900000 + i for i in range(15)]
OAT_SUBDIR = "2026-08-04_lmp_hubtier_oat_battery"  # for reusing HK class-selection + existing configs
HK_CLASS_SELECT_SUBDIR = f"{OAT_SUBDIR}/_class_selection_hk"
SUBDIR = "2026-08-04_lmp_hubtier_pu_vcr_finegrain"
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

# (config_name, override_tokens)
NEW_CONFIGS = [
    ("pu_002", ["p_u=0.02"]),
    ("pu_003", ["p_u=0.03"]),
    ("pu_010", ["p_u=0.10"]),
    ("pu_025", ["p_u=0.25"]),
    ("vcr_0075", ["vocal_comfort_radius=0.075"]),
    ("vcr_015", ["vocal_comfort_radius=0.15"]),
    ("vcr_03", ["vocal_comfort_radius=0.3"]),
]

# existing OAT-battery configs reused for the combined report (name, subdir, param, value)
EXISTING = [
    ("pu_001", f"{OAT_SUBDIR}/pu_001", "p_u", 0.01),
    ("baseline", f"{OAT_SUBDIR}/baseline", "p_u", 0.05),
    ("pu_015", f"{OAT_SUBDIR}/pu_015", "p_u", 0.15),
    ("vcr_005", f"{OAT_SUBDIR}/vcr_005", "vcr", 0.05),
    ("baseline", f"{OAT_SUBDIR}/baseline", "vcr", 0.1),
    ("vcr_02", f"{OAT_SUBDIR}/vcr_02", "vcr", 0.2),
]
NEW_PARAM = {
    "pu_002": ("p_u", 0.02), "pu_003": ("p_u", 0.03), "pu_010": ("p_u", 0.10), "pu_025": ("p_u", 0.25),
    "vcr_0075": ("vcr", 0.075), "vcr_015": ("vcr", 0.15), "vcr_03": ("vcr", 0.3),
}


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
    logfile = ROOT / "logs" / f"lmpfg_seed{seed}_{subdir.replace('/', '_')}.log"
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
    import random
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


def report_point(label, subdir):
    c = np.array([combined_extreme_percapita(s, subdir, "control") for s in SEEDS])
    m = np.array([combined_extreme_percapita(s, subdir, "N_silent") for s in SEEDS])
    diff = m - c
    valid = ~np.isnan(diff)
    dv = diff[valid]
    sd = dv.std(ddof=1)
    t = dv.mean() / (sd / np.sqrt(len(dv))) if sd > 0 else float("nan")
    d = dv.mean() / sd if sd > 0 else float("nan")
    return dict(label=label, control=c[valid].mean(), m_silent=m[valid].mean(), diff=dv.mean(), t=t, d=d)


def main():
    print("=== Deriving hub-tier groups (reused HK class-selection) ===", flush=True)
    groups_by_seed = {s: derive_groups(s) for s in SEEDS}

    print(f"\n=== Launching {len(NEW_CONFIGS)} new configs x {len(SEEDS)} seeds x 2 arms ===", flush=True)
    jobs = []
    for name, override_tokens in NEW_CONFIGS:
        for s in SEEDS:
            groups = groups_by_seed[s]
            pin_token = build_pin_token(groups)
            m_ids = groups["M"][0]
            for arm in ARMS:
                tokens = [pin_token] + override_tokens
                if arm == "N_silent":
                    idstr = ",".join(str(a) for a in m_ids)
                    tokens += [f"silent_until_ids={idstr}", f"activation_step={FULL_STEPS + 1}"]
                jobs.append((s, FULL_STEPS, f"{SUBDIR}/{name}/{arm}", tokens))
    run_wave(jobs, max_workers=20)

    print("\n=== p_u sweep (combined bin0+bin4, N_silent vs control) ===")
    pu_points = [("pu_001 (0.01)", f"{OAT_SUBDIR}/pu_001"), ("pu_002 (0.02)", f"{SUBDIR}/pu_002"),
                 ("pu_003 (0.03)", f"{SUBDIR}/pu_003"), ("baseline (0.05)", f"{OAT_SUBDIR}/baseline"),
                 ("pu_010 (0.10)", f"{SUBDIR}/pu_010"), ("pu_015 (0.15)", f"{OAT_SUBDIR}/pu_015"),
                 ("pu_025 (0.25)", f"{SUBDIR}/pu_025")]
    for label, subdir in pu_points:
        r = report_point(label, subdir)
        print(f"  {r['label']:>16}: control={r['control']:.5f}  N_silent={r['m_silent']:.5f}  "
              f"diff={r['diff']:+.5f}  t={r['t']:+.2f}  d={r['d']:+.3f}")

    print("\n=== vocal_comfort_radius sweep (combined bin0+bin4, N_silent vs control) ===")
    vcr_points = [("vcr_005 (0.05)", f"{OAT_SUBDIR}/vcr_005"), ("vcr_0075 (0.075)", f"{SUBDIR}/vcr_0075"),
                  ("baseline (0.1)", f"{OAT_SUBDIR}/baseline"), ("vcr_015 (0.15)", f"{SUBDIR}/vcr_015"),
                  ("vcr_02 (0.2)", f"{OAT_SUBDIR}/vcr_02"), ("vcr_03 (0.3)", f"{SUBDIR}/vcr_03")]
    for label, subdir in vcr_points:
        r = report_point(label, subdir)
        print(f"  {r['label']:>16}: control={r['control']:.5f}  N_silent={r['m_silent']:.5f}  "
              f"diff={r['diff']:+.5f}  t={r['t']:+.2f}  d={r['d']:+.3f}")


if __name__ == "__main__":
    main()
