"""
2026-08-04 -- Robustness check for the N_silent finding in scripts/lmp_hubtier_pilot.py: with the
L/M/P hub tier's Moderate category silenced (vs control, everyone active), the ordinary (non-hub)
Extreme camp's per-capita original-post rate is LOWER (not higher, contra the user's original
"moderate silences pre-extreme, frees extreme" framing) while the ordinary Pre-extreme camp's rate
is HIGHER -- an unexplained sign-flip between adjacent opinion bins that does not fit a simple
distance-decay spillover story. User (2026-08-04): this alone -- "neutral hub's presence is linked
to extreme-camp activation" -- is interesting enough to be a candidate north-star pivot IF it's
robust; check robustness along two axes before treating it as a real finding:

  1. n increase / replication: add 15 fresh seeds (8800015-8800029) to the existing 15
     (8800000-8800014), for n=30 at the SAME bc_recovery=0.001 point already tested.
  2. bc-regime dependence: re-run all 30 seeds at bc_recovery=0.0001 (this project's own DEFAULT,
     not the exploratory 2026-08-03-screen point today's first pass used) -- checks whether the
     effect is specific to that not-yet-validated bc point or holds more generally.

Scoped to control/N_silent only (the two arms the effect concerns), not the full 6-arm battery, per
user's choice (2026-08-04) to check robustness cheaply before widening scope. Reuses already-
completed runs where possible: SEEDS_ORIG x bc=0.001 x {control,N_silent} already exist under
results/2026-08-04_lmp_hubtier_pilot/{arm}/ (no re-run); everything else is new.

Usage: nohup python3 scripts/lmp_hubtier_robustness.py > logs/lmp_hubtier_robustness_stdout.log 2>&1 &
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
N_HUB = 60

SEEDS_ORIG = [8800000 + i for i in range(15)]
SEEDS_NEW = [8800015 + i for i in range(15)]
ALL_SEEDS = SEEDS_ORIG + SEEDS_NEW

OLD_SUBDIR = "2026-08-04_lmp_hubtier_pilot"          # first-pass run, bc=0.001, SEEDS_ORIG only
OLD_CLASS_SELECT_SUBDIR = f"{OLD_SUBDIR}/_class_selection"
NEW_SUBDIR = "2026-08-04_lmp_hubtier_robustness"
NEW_CLASS_SELECT_SUBDIR = f"{NEW_SUBDIR}/_class_selection"

BC_POINTS = [0.001, 0.0001]
ARMS = ["control", "N_silent"]

GROUP_SIZES = [("E_minus", 10, -1.0), ("P_minus", 10, -0.4), ("M", 20, 0.0),
               ("P_plus", 10, 0.4), ("E_plus", 10, 1.0)]

BASE_TOKENS = [
    "network=hk", "hk_m=15", "hk_a=4", "hk_pt=0.05",
    "max_follow=43.8638", "follow_prob=0.01", "feed_capacity=15",
    "access_prob=0.1", "p_u=0.05",
    "bc_init=0.800000", "bc_dec=0.500000", "bc_floor=0.2", "bc_ceiling=1.0",
    "vocal_comfort_radius=0.1", "repost_prob=0.1", "relay_enabled=false",
    "out_of_bc_repost_prob=0.01", "rel_attrib=original",
    "stub_dist=uniform", "stub_min=0.82", "stub_max=0.82",
    "evict_beta=-1", "init_prune=trim",
    "initial_pp=0.25537", "max_pp=1.0", "min_pp=0.01", "pp_relax_eta=0.100000",
    "neutral_band=0.2",
    "extreme=none", "n_neutral=0", "alpha=0",
]
bin_label = {0: "extreme(-)", 1: "pre-extreme(-)", 2: "moderate", 3: "pre-extreme(+)", 4: "extreme(+)"}


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
    logfile = ROOT / "logs" / f"lmprobust_seed{seed}_{subdir.replace('/', '_')}.log"
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


def derive_groups(seed, class_select_subdir):
    d = result_dir(seed, class_select_subdir)
    ranked = []
    with open(d / "degrees" / "agent_snapshot_t0.csv", newline="") as f:
        for r in csv.DictReader(f):
            ranked.append((int(r["followerCount"]), int(r["agentId"])))
    ranked.sort(reverse=True)
    top_ids = [aid for _, aid in ranked[:N_HUB]]
    assert len(top_ids) == N_HUB, f"seed={seed}: only {len(top_ids)} agents available, need {N_HUB}"
    rng = random.Random(seed)
    rng.shuffle(top_ids)
    groups = {}
    i = 0
    for name, size, target in GROUP_SIZES:
        groups[name] = (top_ids[i:i + size], target)
        i += size
    return groups


def build_pin_token(groups):
    pairs = []
    for _, (ids, target) in groups.items():
        for aid in ids:
            pairs.append(f"{aid}:{target}")
    return "pin_opinion_ids=" + ",".join(pairs)


def run_subdir(seed, bc, arm):
    if bc == 0.001 and seed in SEEDS_ORIG:
        return f"{OLD_SUBDIR}/{arm}"
    return f"{NEW_SUBDIR}/bcrec{bc}/{arm}"


def class_select_subdir_for(seed):
    return OLD_CLASS_SELECT_SUBDIR if seed in SEEDS_ORIG else NEW_CLASS_SELECT_SUBDIR


def pop_counts_nonhub(seed, bc, arm):
    d = result_dir(seed, run_subdir(seed, bc, arm))
    counts = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0}
    with open(d / "degrees" / "agent_snapshot_final.csv", newline="") as f:
        for r in csv.DictReader(f):
            if r["isTarget"] == "0":
                counts[camp_bin(float(r["opinion"]))] += 1
    return counts


def nonhub_percapita(seed, bc, arm, b, checkpoint=FULL_STEPS, window=WINDOW):
    d = result_dir(seed, run_subdir(seed, bc, arm))
    with open(d / "posts" / "post_result.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    lo = checkpoint - window
    total = sum(int(r[f"bin_{b}"]) for r in rows if lo < int(r["step"]) <= checkpoint)
    n = pop_counts_nonhub(seed, bc, arm)[b]
    return total / n / window if n > 0 else float("nan")


def struct_metric_nonhub(seed, bc, arm, col, checkpoint=FULL_STEPS, window=WINDOW):
    d = result_dir(seed, run_subdir(seed, bc, arm))
    with open(d / "metrics" / "results.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    lo = checkpoint - window
    wrows = [r for r in rows if lo < int(r["step"]) <= checkpoint]
    return np.mean([float(r[col]) for r in wrows])


def report(seeds, bc, label):
    print(f"\n\n=== {label}: N_silent vs control, non-hub, n={len(seeds)}, bc_recovery={bc} ===")
    for b in range(5):
        c = np.array([nonhub_percapita(s, bc, "control", b) for s in seeds])
        m = np.array([nonhub_percapita(s, bc, "N_silent", b) for s in seeds])
        diff = m - c
        valid = ~np.isnan(diff)
        dv = diff[valid]
        t = dv.mean() / (dv.std(ddof=1) / np.sqrt(len(dv))) if dv.std(ddof=1) > 0 else float("nan")
        pct = 100 * dv.mean() / c[valid].mean() if c[valid].mean() else float("nan")
        print(f"  bin{b} {bin_label[b]:>14}: control={c[valid].mean():.5f}  N_silent={m[valid].mean():.5f}  "
              f"diff={dv.mean():+.5f} ({pct:+.1f}%)  t={t:.2f}  n={valid.sum()}")
    for col in ["opinionVar", "bimodalityCoeff", "opinionAssortativity", "crossCuttingFraction"]:
        c = np.array([struct_metric_nonhub(s, bc, "control", col) for s in seeds])
        m = np.array([struct_metric_nonhub(s, bc, "N_silent", col) for s in seeds])
        diff = m - c
        t = diff.mean() / (diff.std(ddof=1) / np.sqrt(len(diff))) if diff.std(ddof=1) > 0 else float("nan")
        print(f"  {col:>22}: control={c.mean():.4f}  N_silent={m.mean():.4f}  diff={diff.mean():+.4f}  t={t:.2f}")


def main():
    print("=== Phase 1: class-selection for the 15 new seeds (reusing existing for the original 15) ===", flush=True)
    run_wave([(s, 0, NEW_CLASS_SELECT_SUBDIR, []) for s in SEEDS_NEW], max_workers=len(SEEDS_NEW))

    groups_by_seed = {s: derive_groups(s, class_select_subdir_for(s)) for s in ALL_SEEDS}
    for s in SEEDS_NEW:
        sizes = {name: len(ids) for name, (ids, _) in groups_by_seed[s].items()}
        print(f"  seed={s}: {sizes}", flush=True)

    print("\n=== Phase 2: launching missing (seed, bc, arm) runs ===", flush=True)
    jobs = []
    for s in ALL_SEEDS:
        pin_token = build_pin_token(groups_by_seed[s])
        m_ids = groups_by_seed[s]["M"][0]
        for bc in BC_POINTS:
            for arm in ARMS:
                tokens = [pin_token, f"bc_recovery={bc}"]
                if arm == "N_silent":
                    idstr = ",".join(str(a) for a in m_ids)
                    tokens += [f"silent_until_ids={idstr}", f"activation_step={FULL_STEPS + 1}"]
                jobs.append((s, FULL_STEPS, run_subdir(s, bc, arm), tokens))
    run_wave(jobs, max_workers=20)

    report(SEEDS_ORIG, 0.001, "First-pass replication check (same seeds, same bc, sanity only)")
    report(ALL_SEEDS, 0.001, "AXIS 1: n=30 replication (bc_recovery=0.001, original + 15 new seeds)")
    report(ALL_SEEDS, 0.0001, "AXIS 2: bc-regime robustness (bc_recovery=0.0001, project default, n=30)")


if __name__ == "__main__":
    main()
