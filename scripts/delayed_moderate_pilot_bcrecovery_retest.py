"""
2026-08-04 -- Re-test the delayed-moderate-conduit hypothesis (moderate hub class silent vs always-
active) under bc_recovery=0.001 (bc_floor=0.2, bc_init=0.8, bc_dec=0.5 otherwise default) -- the most
promising single-lever point found in the bc_floor x bc_recovery screen
(docs/report/2026-08-02-delayed-moderate-conduit-pilot.md 2026-08-03 entry) for pulling
bc_extremity_corr toward this project's own -0.3 target without breaking the assort floor. Motivation:
the full 5-parameter OAT battery under the current DEFAULT bc settings found no extreme-camp effect
anywhere (docs/report same file) -- this checks whether a more WSSIT-consistent bc regime changes
that picture. Uses the batched-postCash-delivery fix and the corrected per-capita metric
(posts/post_result.csv direct counts) throughout.

n=15, fresh seed block (7700000-7700014, unused elsewhere), A_never/B_always, same class-selection
method (top-20 by t0 followerCount among |intrinsicOpinion|<0.2) as the rest of this pilot.

Usage: nohup python3 scripts/delayed_moderate_pilot_bcrecovery_retest.py > logs/delayed_moderate_pilot_bcrecovery_retest_stdout.log 2>&1 &
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
SEEDS = [7700000 + i for i in range(15)]
TOPK_MODERATE = 20
MODERATE_THRESHOLD = 0.2
SUBDIR = "2026-08-04_bcrecovery_conduit_retest"
CLASS_SELECT_SUBDIR = f"{SUBDIR}/_class_selection"
ARMS = ["A_never", "B_always"]

FIXED_TOKENS = [
    "network=hk", "hk_m=15", "hk_a=4", "hk_pt=0.05",
    "max_follow=43.8638", "follow_prob=0.01", "feed_capacity=15",
    "access_prob=0.1", "p_u=0.05",
    "bc_init=0.800000", "bc_dec=0.500000", "bc_floor=0.2", "bc_recovery=0.001", "bc_ceiling=1.0",
    "vocal_comfort_radius=0.1", "repost_prob=0.1", "relay_enabled=false",
    "out_of_bc_repost_prob=0.01", "rel_attrib=original",
    "stub_dist=uniform", "stub_min=0.82", "stub_max=0.82",
    "evict_beta=-1", "init_prune=trim",
    "initial_pp=0.25537", "max_pp=1.0", "min_pp=0.01", "pp_relax_eta=0.100000",
    "moderate_band=0.2",
    "extreme=none", "n_mod=0", "alpha=0",
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
        + FIXED_TOKENS + extra_tokens
    logfile = ROOT / "logs" / f"bcrecoverytest_seed{seed}_{subdir.split('/')[-1]}.log"
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


def camp_bin(x):
    shifted = x + 1.0
    return min(int(shifted / 0.4), 4)


def pop_counts(seed, arm):
    d = result_dir(seed, f"{SUBDIR}/{arm}")
    counts = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0}
    with open(d / "degrees" / "agent_snapshot_final.csv", newline="") as f:
        for r in csv.DictReader(f):
            counts[camp_bin(float(r["opinion"]))] += 1
    return counts


def orig_percapita(seed, arm, b, checkpoint=FULL_STEPS, window=WINDOW):
    d = result_dir(seed, f"{SUBDIR}/{arm}")
    with open(d / "posts" / "post_result.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    lo = checkpoint - window
    total = sum(int(r[f"bin_{b}"]) for r in rows if lo < int(r["step"]) <= checkpoint)
    pop = pop_counts(seed, arm)
    n = pop[b]
    return total / n / window if n > 0 else float("nan")


def main():
    print("=== Phase 1: class-selection dry runs ===", flush=True)
    run_wave([(s, 0, CLASS_SELECT_SUBDIR, []) for s in SEEDS], max_workers=len(SEEDS))

    class_ids = {}
    for s in SEEDS:
        class_ids[s] = derive_class_ids(s)
        print(f"  seed={s}: {len(class_ids[s])} class agents -> {class_ids[s]}", flush=True)

    print(f"\n=== Phase 2: A_never/B_always x {len(SEEDS)} seeds (steps={FULL_STEPS}), bc_recovery=0.001 ===", flush=True)
    jobs = []
    for s in SEEDS:
        idstr = ",".join(str(a) for a in class_ids[s])
        for arm in ARMS:
            tokens = [f"pin_moderate_ids={idstr}"]
            if arm == "A_never":
                tokens += [f"silent_until_ids={idstr}", f"activation_step={FULL_STEPS + 1}"]
            jobs.append((s, FULL_STEPS, f"{SUBDIR}/{arm}", tokens))
    run_wave(jobs, max_workers=20)

    print("\n=== CORRECTED original-post-only per-capita rate by bin, bc_recovery=0.001, n=15 ===")
    for b in range(5):
        a = np.array([orig_percapita(s, "A_never", b) for s in SEEDS])
        bb = np.array([orig_percapita(s, "B_always", b) for s in SEEDS])
        diff = bb - a
        t = diff.mean() / (diff.std(ddof=1) / np.sqrt(len(diff))) if diff.std(ddof=1) > 0 else float("nan")
        pct = 100 * diff.mean() / a.mean() if a.mean() else float("nan")
        label = {0: "extreme(-)", 1: "pre-extreme(-)", 2: "moderate", 3: "pre-extreme(+)", 4: "extreme(+)"}[b]
        print(f"  bin{b} {label:>14}: A={a.mean():.5f}  B={bb.mean():.5f}  diff={diff.mean():+.5f} ({pct:+.1f}%)  t={t:.2f}")

    print("\n=== also: opinionAssortativity / crossCuttingFraction (structural bridging) ===")
    def struct_metric(seed, arm, col, checkpoint=FULL_STEPS, window=WINDOW):
        d = result_dir(seed, f"{SUBDIR}/{arm}")
        with open(d / "metrics" / "results.csv", newline="") as f:
            rows = list(csv.DictReader(f))
        lo = checkpoint - window
        wrows = [r for r in rows if lo < int(r["step"]) <= checkpoint]
        return np.mean([float(r[col]) for r in wrows])
    for col in ["opinionAssortativity", "crossCuttingFraction"]:
        a = np.array([struct_metric(s, "A_never", col) for s in SEEDS])
        bb = np.array([struct_metric(s, "B_always", col) for s in SEEDS])
        diff = bb - a
        t = diff.mean() / (diff.std(ddof=1) / np.sqrt(len(diff))) if diff.std(ddof=1) > 0 else float("nan")
        print(f"  {col:>22}: A={a.mean():.4f}  B={bb.mean():.4f}  diff={diff.mean():+.4f}  t={t:.2f}")


if __name__ == "__main__":
    main()
