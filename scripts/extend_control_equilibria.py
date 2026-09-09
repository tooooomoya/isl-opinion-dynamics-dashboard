"""
2026-07-28 -- Extend the control-equilibria pool from 20 to 100 seeds (3000020-3000099), same
current-config point as the existing 2026-07-27_current-config-equilibria runs (network=hk,
steps=20000, no manipulation). Purpose: the moderate-reach-vs-SF1 dose-response correlation found
at n=20 (docs/report/2026-07-21-conduit-experiment-design.md, "cross-seed dose-response" section)
did not survive FDR correction across 64 exploratory cells, and the follower-stratum decomposition
(top>100 vs mid 50-100 vs small 10-50 vs peripheral<=10) was inconclusive at n=20 (partial
correlations noisy, CIs wide). n=100 gives |rho|>.197 at p<.05, enough to actually resolve both.

Usage: python3 scripts/extend_control_equilibria.py
"""
import concurrent.futures
import csv
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_JARS = list(ROOT.glob("lib/**/*.jar"))
LIBCP = ":".join(str(p) for p in _JARS) + (":" if _JARS else "") + str(ROOT / "bin")

N = 1000
STEPS = 20000
NEW_SEEDS = list(range(3000020, 3000100))  # 80 more, verified unused 2026-07-28
SUBDIR = "2026-07-27_current-config-equilibria"  # same subdir as the existing 20, one coherent pool
MAX_CONCURRENT = 24

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
    c = sorted(ROOT.glob(f"results/{SUBDIR}/run_{seed}_*"), key=lambda p: p.stat().st_mtime)
    return c[-1] if c else None


def is_done(seed):
    d = result_dir(seed)
    if d is None:
        return False
    rp = d / "metrics" / "results.csv"
    if not rp.exists():
        return False
    with open(rp, newline="") as f:
        rows = list(csv.DictReader(f))
    return bool(rows) and int(rows[-1]["step"]) >= STEPS


def launch(seed):
    tokens = [f"seed={seed}", f"steps={STEPS}", f"n={N}", "force=true",
              f"results_subdir={SUBDIR}"] + FIXED_TOKENS
    logfile = ROOT / "logs" / f"ctrlext_seed{seed}.log"
    logfile.parent.mkdir(exist_ok=True)
    with open(logfile, "w") as lf:
        p = subprocess.Popen(["java", "-Xmx2g", "-cp", LIBCP, "dynamics.OpinionDynamics", *tokens],
                              stdout=lf, stderr=subprocess.STDOUT, cwd=ROOT)
    return p


def main():
    todo = [s for s in NEW_SEEDS if not is_done(s)]
    print(f"{len(NEW_SEEDS) - len(todo)} already done, launching {len(todo)} new runs "
          f"(max {MAX_CONCURRENT} concurrent)", flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENT) as ex:
        futs = [ex.submit(lambda s=s: launch(s).wait()) for s in todo]
        for f in futs:
            f.result()
    print("done", flush=True)


if __name__ == "__main__":
    main()
