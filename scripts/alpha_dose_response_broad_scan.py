"""
2026-09-11 -- First experiment in this repo's new line of work (recommendation-algorithm-in-feed
expansion, forked from Dev-ComplexNetworks2026 -- see docs/report/2026-09-09-repo-split-rec-feed-fork.md).

Broad, unopinionated first scan of alpha (feedAlgoShare, the fraction of each agent's feed filled
by the opinion-blind, repost-velocity-ranked "For You" recommender rather than the chronological
follower stream) against the model's standard polarization/structure outcome battery. Purpose is
NOT yet to test a specific bridging-vs-amplification mechanism (see design doc); it's to see which
direction(s) alpha moves the standard outcomes, to decide what to dig into next.

Design decisions and rationale: docs/report/2026-09-11-alpha-dose-response-broad-scan.md

Other params fixed at scripts/feed_redesign_v5_dose_response_n100.py's baseline (this repo's
inherited, previously-validated CNA2026 config) so alpha is the only manipulated variable.

Usage: nohup python3 scripts/alpha_dose_response_broad_scan.py > logs/alpha_dose_response_stdout.log 2>&1 &
       disown
"""
import concurrent.futures
import csv
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
_JARS = list(ROOT.glob("lib/**/*.jar"))
LIBCP = ":".join(str(p) for p in _JARS) + (":" if _JARS else "") + str(ROOT / "bin")

N = 1000
STEPS = 20000
CHECKPOINTS = [5000, 10000, 20000]
ALPHAS = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
N_SEEDS_PER_ALPHA = 20
BASE_SEED = 9100000  # fresh range, offset from all feed_redesign_*/stage_* seed ranges
MAX_WORKERS = 20     # 20 concurrent JVMs * 2g heap = 40g, safe under 120g system RAM

FIXED_TOKENS = [
    "network=hk", "hk_m=15", "hk_a=4", "hk_pt=0.05",
    "max_follow=43.8638", "follow_prob=0.01", "feed_capacity=15",
    "hop=4", "feed_decay_mode=exp", "feed_decay_lambda=0.10992130598108527",
    "feed_time_decay_tau=30",
    "access_prob=0.1", "p_u=0.05",
    "bc_dec=0.500000", "bc_recovery=0.000100", "bc_floor=0.2", "bc_ceiling=1.0", "bc_init=0.800000",
    "vocal_comfort_radius=0.1", "repost_prob=0.1", "relay_enabled=false",
    "out_of_bc_repost_prob=0.01", "rel_attrib=original",
    "stub_dist=uniform", "stub_min=0.82", "stub_max=0.82",
    "evict_beta=-1", "init_prune=trim",
    "initial_pp=0.25537", "max_pp=1.0", "min_pp=0.01", "pp_relax_eta=0.100000",
    "neutral_band=0.2",
]

OUTCOMES = [
    "opinionVar", "postOpinionVar", "bimodalityCoeff", "opinionAssortativity",
    "crossCuttingFraction", "interactionAssortativity", "interactionAssortativityW",
    "interactionCrossCuttingFraction", "interactionCrossCuttingFractionW",
    "postShare_0", "postShare_1", "postShare_2", "postShare_3", "postShare_4",
    "shannonIndex", "meanTolerance", "toleranceVar",
    "outGroupSanctionRate", "outGroupBlockPropensity",
]

LOG_PATH = ROOT / "docs" / "report" / "alpha_dose_response_broad_scan.csv"


def launch(alpha, seed):
    tokens = [f"seed={seed}", f"n={N}", f"steps={STEPS}", "log_gexf=false", "force=true",
              f"alpha={alpha:.4f}", *FIXED_TOKENS]
    logfile = ROOT / "logs" / f"alpha_scan_a{alpha:.2f}_seed{seed}.log"
    logfile.parent.mkdir(exist_ok=True)
    with open(logfile, "w") as lf:
        p = subprocess.Popen(
            ["java", "-Xmx2g", "-cp", LIBCP, "dynamics.OpinionDynamics", *tokens],
            stdout=lf, stderr=subprocess.STDOUT, cwd=ROOT,
        )
    return p


def read_outcomes(run_dir):
    with open(run_dir / "metrics" / "results.csv", newline="") as f:
        rows_by_step = {int(r["step"]): r for r in csv.DictReader(f)}
    q_by_step = {}
    mod_path = run_dir / "metrics" / "modularity.csv"
    if mod_path.exists():
        with open(mod_path, newline="") as f:
            for r in csv.DictReader(f):
                q_by_step[int(r["step"])] = float(r["Q_sign_repost"])
    out = {}
    for chk in CHECKPOINTS:
        r = rows_by_step.get(chk)
        if r is None:
            out[chk] = None
            continue
        row = {k: float(r[k]) for k in OUTCOMES if k in r}
        row["Q_sign_repost"] = q_by_step.get(chk)
        out[chk] = row
    return out


def evaluate(args):
    alpha, seed = args
    p = launch(alpha, seed)
    p.wait()
    candidates = sorted(ROOT.glob(f"results/run_{seed}_*"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        return None
    d = candidates[-1]
    try:
        out = read_outcomes(d)
    except (FileNotFoundError, KeyError) as e:
        print(f"alpha={alpha} seed={seed}: failed to read outcomes ({e})", flush=True)
        return None
    return dict(alpha=alpha, seed=seed, out=out)


def main():
    jobs = [(a, BASE_SEED + i * 1000 + s) for i, a in enumerate(ALPHAS) for s in range(N_SEEDS_PER_ALPHA)]
    print(f"Launching {len(jobs)} runs: {len(ALPHAS)} alpha points x {N_SEEDS_PER_ALPHA} seeds, "
          f"n={N}, steps={STEPS}, max_workers={MAX_WORKERS}", flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        results = list(ex.map(evaluate, jobs))
    ok = [r for r in results if r is not None]
    print(f"n={len(ok)}/{len(jobs)} runs succeeded", flush=True)

    all_outcome_keys = OUTCOMES + ["Q_sign_repost"]
    with open(LOG_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        header = ["alpha", "seed"]
        for chk in CHECKPOINTS:
            header += [f"{k}_{chk}" for k in all_outcome_keys]
        writer.writerow(header)
        for r in ok:
            row = [r["alpha"], r["seed"]]
            for chk in CHECKPOINTS:
                o = r["out"].get(chk) or {}
                row += [o.get(k) for k in all_outcome_keys]
            writer.writerow(row)
    print(f"Wrote {LOG_PATH}", flush=True)


if __name__ == "__main__":
    main()
