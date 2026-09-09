"""
2026-08-02 -- Extend delayed_moderate_conduit_pilot.py's A_never/B_always arms from n=5 to n=15,
to firm up the "moderate class present continuously (B_always) raises extreme-camp per-capita
posting rate ~17-25% vs class permanently silent (A_never)" finding and its candidate mechanism
(comfort-rate rise, not bc change, not higher local clustering -- see docs/report write-up).
C_10k/D_30k are NOT re-run here -- this round is specifically about the presence/absence contrast,
which only needs A_never and B_always. Reuses the exact same FIXED_TOKENS, class-selection method
(top-20 by t0 followerCount among |intrinsicOpinion|<0.2), and results/log conventions as
scripts/delayed_moderate_conduit_pilot.py -- only the seed range (5 new seeds -> 10 additional
seeds, 7300005-7300014) and the arm set differ.

Usage: nohup python3 scripts/delayed_moderate_conduit_pilot_extend.py > logs/delayed_moderate_pilot_extend_stdout.log 2>&1 &
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
CHECKPOINTS = [5000, 15000, 25000, 35000, 40000]
NEW_SEEDS = [7300005 + i for i in range(10)]
ALL_SEEDS = [7300000 + i for i in range(15)]  # for downstream analysis convenience
TOPK_MODERATE = 20
MODERATE_THRESHOLD = 0.2
SUBDIR = "2026-08-02_delayed-moderate-pilot"
CLASS_SELECT_SUBDIR = f"{SUBDIR}/_class_selection"
ARMS = ["A_never", "B_always"]

FIXED_TOKENS = [
    "network=hk", "hk_m=15", "hk_a=4", "hk_pt=0.05",
    "max_follow=43.8638", "follow_prob=0.01", "feed_capacity=15",
    "access_prob=0.1", "p_u=0.05",
    "bc_dec=0.500000", "bc_recovery=0.000100", "bc_floor=0.2", "bc_ceiling=1.0", "bc_init=0.800000",
    "vocal_comfort_radius=0.1", "repost_prob=0.1", "relay_enabled=false",
    "out_of_bc_repost_prob=0.01", "rel_attrib=original",
    "stub_dist=uniform", "stub_min=0.82", "stub_max=0.82",
    "evict_beta=-1", "init_prune=trim",
    "initial_pp=0.25537", "max_pp=1.0", "min_pp=0.01", "pp_relax_eta=0.100000",
    "moderate_band=0.2",
    "extreme=none", "n_mod=0", "alpha=0",
]


def result_dir(seed, subdir):
    candidates = sorted(ROOT.glob(f"results/{subdir}/run_{seed}_*"), key=lambda p: p.stat().st_mtime)
    return candidates[-1] if candidates else None


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
        + FIXED_TOKENS + extra_tokens
    logfile = ROOT / "logs" / f"delaymod_seed{seed}_{subdir.split('/')[-1]}.log"
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


def derive_class_ids(seed):
    d = result_dir(seed, CLASS_SELECT_SUBDIR)
    ranked = []
    with open(d / "degrees" / "agent_snapshot_t0.csv", newline="") as f:
        for r in csv.DictReader(f):
            if abs(float(r["intrinsicOpinion"])) < MODERATE_THRESHOLD:
                ranked.append((int(r["followerCount"]), int(r["agentId"])))
    ranked.sort(reverse=True)
    return [aid for _, aid in ranked[:TOPK_MODERATE]]


def read_metrics_at(seed, arm, checkpoint):
    d = result_dir(seed, f"{SUBDIR}/{arm}")
    with open(d / "metrics" / "results.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    at = next(r for r in reversed(rows) if int(r["step"]) == checkpoint)
    opinion_var = float(at["opinionVar"])
    post_opinion_var = float(at["postOpinionVar"])
    sf1 = post_opinion_var / opinion_var if opinion_var > 0 else None
    return dict(
        sf1_ratio=sf1,
        opinionAssortativity=float(at["opinionAssortativity"]),
        crossCuttingFraction=float(at["crossCuttingFraction"]),
        cRate_extreme=(float(at["cRateMean_0"]) + float(at["cRateMean_4"])) / 2,
    )


def main():
    print("=== Phase 1: class-selection dry runs for new seeds (steps=0) ===", flush=True)
    run_wave([(s, 0, CLASS_SELECT_SUBDIR, []) for s in NEW_SEEDS], max_workers=len(NEW_SEEDS))

    class_ids = {}
    for s in NEW_SEEDS:
        class_ids[s] = derive_class_ids(s)
        print(f"  seed={s}: {len(class_ids[s])} class agents -> {class_ids[s]}", flush=True)

    print(f"\n=== Phase 2: A_never/B_always x {len(NEW_SEEDS)} new seeds (steps={FULL_STEPS}) ===", flush=True)
    jobs = []
    for s in NEW_SEEDS:
        idstr = ",".join(str(a) for a in class_ids[s])
        for arm in ARMS:
            tokens = [f"pin_moderate_ids={idstr}"]
            if arm == "A_never":
                tokens += [f"silent_until_ids={idstr}", f"activation_step={FULL_STEPS + 1}"]
            jobs.append((s, FULL_STEPS, f"{SUBDIR}/{arm}", tokens))
    run_wave(jobs, max_workers=20)

    print("\n=== Done. Verifying all 15 seeds now present for A_never/B_always ===", flush=True)
    for arm in ARMS:
        n_ok = sum(is_done(s, f"{SUBDIR}/{arm}", FULL_STEPS) for s in ALL_SEEDS)
        print(f"  {arm}: {n_ok}/{len(ALL_SEEDS)} seeds complete", flush=True)

    print("\n=== extreme cRateMean + opinionAssortativity + crossCuttingFraction, n=15, at final checkpoint ===")
    for arm in ARMS:
        vals = {k: [] for k in ["sf1_ratio", "opinionAssortativity", "crossCuttingFraction", "cRate_extreme"]}
        for s in ALL_SEEDS:
            m = read_metrics_at(s, arm, FULL_STEPS)
            for k in vals:
                vals[k].append(m[k])
        print(f"  {arm}: " + "  ".join(f"{k}={np.mean(v):.4f}+/-{np.std(v):.4f}" for k, v in vals.items()))


if __name__ == "__main__":
    main()
