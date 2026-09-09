"""
2026-08-03 -- Follow-up to bc_init_dec_objective_screen.py: that screen swept bc_init x bc_dec to
try to pull bc_extremity_corr and Q_sign_repost back toward this project's own calibration targets
(<=-0.3 and 0.48 respectively) by mimicking WSSIT-era's slower bc-narrowing -- but bc_dec turned out
to mean something structurally different from WSSIT-era's flat multiplicative decay (a per-step
gap-closing rate in a feedback loop, not a per-event decay constant), and slowing it made both
metrics WORSE (more negative correlation, lower Q), not better -- see that script's results in
docs/report/2026-08-02-delayed-moderate-conduit-pilot.md.

This screens two more direct levers instead: bc_floor (the hard minimum bc can reach -- raising it
directly caps how narrow tolerance can get for any agent regardless of dynamics, a mechanical ceiling
on |bc_extremity_corr| rather than an indirect dynamics change) and bc_recovery (the content-
independent mean-reversion rate pulling bc back toward bc_init every post -- currently tiny, 0.0001;
raising it lets bc genuinely "bounce back" after uncomfortable periods, closer to WSSIT-era's
apparent broad-tolerance persistence). out_of_bc_repost_prob was considered and dropped (user:
already known to be a low-probability event, not a promising lever here). bc_init/bc_dec held at
current defaults (0.8/0.5) throughout this screen.

No neutral-hub intervention (extreme=none n_neutral=0) -- general-model-calibration screen. n=5 per
grid point (screening pass; follow up with n=20 on any promising point).

Usage: nohup python3 scripts/bc_floor_recovery_objective_screen.py > logs/bc_floor_recovery_objective_screen_stdout.log 2>&1 &
       (then disown)
"""
import concurrent.futures
import csv
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
_JARS = list(ROOT.glob("lib/**/*.jar"))
LIBCP = ":".join(str(p) for p in _JARS) + (":" if _JARS else "") + str(ROOT / "bin")

N = 1000
STEPS = 40000
CHECKPOINT = 40000
N_SEEDS = 5
BASE_SEED = 4400100
SUBDIR = "2026-08-03_bc_floor_recovery_screen"

GINI_TARGET, Q_TARGET, RATIO_TARGET_RANGE, ASSORT_FLOOR, BC_CORR_TARGET = 0.8, 0.48, (1.19, 1.26), 0.6, -0.3

BC_FLOORS = [0.2, 0.35, 0.5]
BC_RECOVERIES = [0.0001, 0.001, 0.01]

BASE_TOKENS = [
    "network=hk", "hk_m=15", "hk_a=4", "hk_pt=0.05",
    "max_follow=43.8638", "follow_prob=0.01", "feed_capacity=15",
    "access_prob=0.1", "p_u=0.05",
    "bc_init=0.800000", "bc_dec=0.500000", "bc_ceiling=1.0",
    "vocal_comfort_radius=0.1", "repost_prob=0.1", "relay_enabled=false",
    "out_of_bc_repost_prob=0.01", "rel_attrib=original",
    "stub_dist=uniform", "stub_min=0.82", "stub_max=0.82",
    "evict_beta=-1", "init_prune=trim",
    "initial_pp=0.25537", "max_pp=1.0", "min_pp=0.01", "pp_relax_eta=0.100000",
    "neutral_band=0.2",
    "extreme=none", "n_neutral=0", "alpha=0",
]


def gini(x):
    x = np.sort(np.asarray(x, dtype=float))
    n = len(x)
    if n == 0 or x.sum() == 0:
        return float("nan")
    cum = np.cumsum(x)
    return (2 * np.sum((np.arange(1, n + 1)) * x) - (n + 1) * cum[-1]) / (n * cum[-1])


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


def launch(seed, subdir, bc_floor, bc_recovery):
    tokens = [f"seed={seed}", f"steps={STEPS}", f"n={N}", "force=true",
              "log_gexf=false", f"results_subdir={subdir}",
              f"bc_floor={bc_floor}", f"bc_recovery={bc_recovery}"] + BASE_TOKENS
    logfile = ROOT / "logs" / f"bcfloorrec_seed{seed}_{subdir.split('/')[-1]}.log"
    logfile.parent.mkdir(exist_ok=True)
    with open(logfile, "w") as lf:
        p = subprocess.Popen(["java", "-Xmx2g", "-cp", LIBCP, "dynamics.OpinionDynamics", *tokens],
                              stdout=lf, stderr=subprocess.STDOUT, cwd=ROOT)
    return p


def run_wave(jobs, max_workers=20):
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = []
        for seed, subdir, bc_floor, bc_recovery in jobs:
            if is_done(seed, subdir, STEPS):
                print(f"  seed={seed} subdir={subdir}: reusing existing", flush=True)
                continue
            futs.append(ex.submit(lambda s=seed, sd=subdir, bf=bc_floor, br=bc_recovery: launch(s, sd, bf, br).wait()))
        for f in futs:
            f.result()


def read_metrics(seed, subdir):
    d = result_dir(seed, subdir)
    if d is None:
        return None
    deg_path = d / "degrees" / f"degree_result_{STEPS}.csv"
    results_path = d / "metrics" / "results.csv"
    mod_path = d / "metrics" / "modularity.csv"
    if not (deg_path.exists() and results_path.exists() and mod_path.exists()):
        return None
    with open(deg_path, newline="") as f:
        indeg = [int(r["inDegree"]) for r in csv.DictReader(f)]
    g = gini(indeg)
    with open(results_path, newline="") as f:
        rows = {int(r["step"]): r for r in csv.DictReader(f)}
    row = rows.get(CHECKPOINT)
    if row is None:
        return None
    assort = float(row["opinionAssortativity"])
    opinion_var = float(row["opinionVar"])
    post_var = float(row["postOpinionVar"])
    ratio = post_var / opinion_var if opinion_var > 0 else None
    bc_corr = float(row["bcExtremityCorrelation"])
    q = None
    with open(mod_path, newline="") as f:
        for r in csv.DictReader(f):
            if int(r["step"]) == CHECKPOINT:
                q = float(r["Q_sign_repost"])
    if ratio is None:
        return None
    return dict(gini=g, assort=assort, q=q, ratio=ratio, bc_corr=bc_corr)


def main():
    print(f"=== Launching {len(BC_FLOORS)}x{len(BC_RECOVERIES)} grid, n={N_SEEDS} each ===", flush=True)
    jobs = []
    for bc_floor in BC_FLOORS:
        for bc_recovery in BC_RECOVERIES:
            name = f"bcfloor{bc_floor}_bcrec{bc_recovery}"
            for j in range(N_SEEDS):
                seed = BASE_SEED + j
                jobs.append((seed, f"{SUBDIR}/{name}", bc_floor, bc_recovery))
    run_wave(jobs, max_workers=20)

    print("\n=== Results: grid summary (n=5 each), checkpoint=40000 ===")
    print(f"{'bc_floor':>9} {'bc_rec':>9} {'gini':>8} {'assort':>8} {'Q_repost':>9} {'SF1':>8} {'bc_corr':>8}")
    for bc_floor in BC_FLOORS:
        for bc_recovery in BC_RECOVERIES:
            name = f"bcfloor{bc_floor}_bcrec{bc_recovery}"
            subdir = f"{SUBDIR}/{name}"
            metrics = [read_metrics(BASE_SEED + j, subdir) for j in range(N_SEEDS)]
            metrics = [m for m in metrics if m is not None]
            if not metrics:
                print(f"{bc_floor:>9} {bc_recovery:>9}  NO DATA")
                continue
            g = np.mean([m["gini"] for m in metrics])
            a = np.mean([m["assort"] for m in metrics])
            q = np.mean([m["q"] for m in metrics])
            r = np.mean([m["ratio"] for m in metrics])
            bcc = np.mean([m["bc_corr"] for m in metrics])
            print(f"{bc_floor:>9} {bc_recovery:>9} {g:8.4f} {a:8.4f} {q:9.4f} {r:8.4f} {bcc:8.4f}")

    print(f"\ntargets: gini={GINI_TARGET} assort>={ASSORT_FLOOR} Q_repost={Q_TARGET} "
          f"SF1 in {RATIO_TARGET_RANGE} bc_corr<={BC_CORR_TARGET}")


if __name__ == "__main__":
    main()
