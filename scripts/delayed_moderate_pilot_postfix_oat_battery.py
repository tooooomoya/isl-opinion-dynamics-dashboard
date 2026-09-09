"""
2026-08-03 -- Full re-run of the delayed-moderate-conduit OAT battery (5 parameters: p_u,
vocal_comfort_radius, class top-K, class threshold, network topology) under the batched-postCash-
delivery fix (OpinionDynamics.java PendingDelivery) and using the CORRECTED per-capita metric
(posts/post_result.csv direct per-bin counts -- NOT postShare_b * (originalPostCount+repostCount),
which was found to be a bug: postShare_b's own population is ORIGINAL POSTS ONLY, see
Analysis.java:588). Motivation: under default parameters, the "moderate conduit raises extreme-camp
posting" effect was withdrawn (not distinguishable from noise, flips sign between seed blocks,
see docs/report/2026-08-02-delayed-moderate-conduit-pilot.md 2026-08-03 entries). This sweep checks
whether some other point in this 5-parameter space shows a more robust extreme-camp effect, now that
(a) the postCash order-dependent asymmetry is reduced and (b) the metric bug is fixed.

All 10 configs (1 baseline + 2 non-baseline levels each for p_u/vcr/topK/threshold + 1 for network)
share ONE class-selection dry-run batch for the HK topology (class membership depends only on t0
followerCount + intrinsicOpinion, unaffected by p_u/vcr/topK/threshold choices at the SAME topology)
plus one fresh dry-run batch for the dcsbm topology. n=15, fresh seed block (6600000-6600014, unused
elsewhere) so no pre-fix results can leak in.

Usage: nohup python3 scripts/delayed_moderate_pilot_postfix_oat_battery.py > logs/delayed_moderate_pilot_postfix_oat_battery_stdout.log 2>&1 &
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
SEEDS = [6600000 + i for i in range(15)]
SUBDIR = "2026-08-03_postfix-oat-battery"
HK_CLASS_SELECT_SUBDIR = f"{SUBDIR}/_class_selection_hk"
DCSBM_CLASS_SELECT_SUBDIR = f"{SUBDIR}/_class_selection_dcsbm"
ARMS = ["A_never", "B_always"]

BASE_TOKENS = [
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

# (config_name, override_tokens, top_k, threshold, needs_fresh_class_selection)
CONFIGS = [
    ("baseline", [], 20, 0.2, False),
    ("pu_001", ["p_u=0.01"], 20, 0.2, False),
    ("pu_015", ["p_u=0.15"], 20, 0.2, False),
    ("vcr_005", ["vocal_comfort_radius=0.05"], 20, 0.2, False),
    ("vcr_02", ["vocal_comfort_radius=0.2"], 20, 0.2, False),
    ("topk10", [], 10, 0.2, False),
    ("topk40", [], 40, 0.2, False),
    ("thresh01", [], 20, 0.1, False),
    ("thresh03", [], 20, 0.3, False),
    ("dcsbm", ["network=dcsbm", "sbm_k=4", "sbm_pin=0.08", "sbm_pout=0.002", "sbm_gamma=2.3", "sbm_deg=15"],
     20, 0.2, True),
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


def launch(seed, steps, subdir, override_tokens, extra_tokens, log_gexf=False):
    tokens = [f"seed={seed}", f"steps={steps}", f"n={N}", "force=true",
              f"log_gexf={str(log_gexf).lower()}", f"results_subdir={subdir}"] \
        + BASE_TOKENS + override_tokens + extra_tokens
    logfile = ROOT / "logs" / f"postfixoat_seed{seed}_{subdir.split('/')[-1]}.log"
    logfile.parent.mkdir(exist_ok=True)
    with open(logfile, "w") as lf:
        p = subprocess.Popen(["java", "-Xmx2g", "-cp", LIBCP, "dynamics.OpinionDynamics", *tokens],
                              stdout=lf, stderr=subprocess.STDOUT, cwd=ROOT)
    return p


def run_wave(jobs, max_workers=20):
    """jobs: list of (seed, steps, subdir, override_tokens, extra_tokens)."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = []
        for seed, steps, subdir, ov, tk in jobs:
            if is_done(seed, subdir, steps):
                print(f"  seed={seed} subdir={subdir}: reusing existing", flush=True)
                continue
            futs.append(ex.submit(lambda s=seed, st=steps, sd=subdir, o=ov, t=tk: launch(s, st, sd, o, t).wait()))
        for f in futs:
            f.result()


def derive_class_ids(seed, class_select_subdir, top_k, threshold):
    d = result_dir(seed, class_select_subdir)
    ranked = []
    with open(d / "degrees" / "agent_snapshot_t0.csv", newline="") as f:
        for r in csv.DictReader(f):
            if abs(float(r["intrinsicOpinion"])) < threshold:
                ranked.append((int(r["followerCount"]), int(r["agentId"])))
    ranked.sort(reverse=True)
    return [aid for _, aid in ranked[:top_k]]


def camp_bin(x):
    shifted = x + 1.0
    return min(int(shifted / 0.4), 4)


def pop_counts(seed, subdir, arm):
    d = result_dir(seed, f"{subdir}/{arm}")
    counts = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0}
    with open(d / "degrees" / "agent_snapshot_final.csv", newline="") as f:
        for r in csv.DictReader(f):
            counts[camp_bin(float(r["opinion"]))] += 1
    return counts


def orig_percapita(seed, subdir, arm, b, checkpoint=FULL_STEPS, window=WINDOW):
    d = result_dir(seed, f"{subdir}/{arm}")
    with open(d / "posts" / "post_result.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    lo = checkpoint - window
    total = sum(int(r[f"bin_{b}"]) for r in rows if lo < int(r["step"]) <= checkpoint)
    pop = pop_counts(seed, subdir, arm)
    n = pop[b]
    return total / n / window if n > 0 else float("nan")


def main():
    print("=== Class-selection dry runs: HK topology (covers baseline/pu/vcr/topk/threshold configs) ===", flush=True)
    run_wave([(s, 0, HK_CLASS_SELECT_SUBDIR, [], []) for s in SEEDS], max_workers=len(SEEDS))

    dcsbm_ov = next(ov for name, ov, _, _, fresh in CONFIGS if name == "dcsbm")
    print("\n=== Class-selection dry runs: DC-SBM topology ===", flush=True)
    run_wave([(s, 0, DCSBM_CLASS_SELECT_SUBDIR, dcsbm_ov, []) for s in SEEDS], max_workers=len(SEEDS))

    print("\n=== Phase 2: full battery, 10 configs x 15 seeds x 2 arms ===", flush=True)
    jobs = []
    for name, override, top_k, threshold, fresh in CONFIGS:
        class_select_subdir = DCSBM_CLASS_SELECT_SUBDIR if fresh else HK_CLASS_SELECT_SUBDIR
        for s in SEEDS:
            ids = derive_class_ids(s, class_select_subdir, top_k, threshold)
            idstr = ",".join(str(a) for a in ids)
            for arm in ARMS:
                tokens = [f"pin_moderate_ids={idstr}"]
                if arm == "A_never":
                    tokens += [f"silent_until_ids={idstr}", f"activation_step={FULL_STEPS + 1}"]
                jobs.append((s, FULL_STEPS, f"{SUBDIR}/{name}/{arm}", override, tokens))
    run_wave(jobs, max_workers=20)

    print("\n=== Results: corrected original-post-only per-capita rate, A_never vs B_always, n=15, per config ===")
    for name, override, top_k, threshold, fresh in CONFIGS:
        print(f"\n### config={name} (top_k={top_k}, threshold={threshold}, override={override}) ###")
        for b in range(5):
            a = np.array([orig_percapita(s, f"{SUBDIR}/{name}", "A_never", b) for s in SEEDS])
            bb = np.array([orig_percapita(s, f"{SUBDIR}/{name}", "B_always", b) for s in SEEDS])
            diff = bb - a
            t = diff.mean() / (diff.std(ddof=1) / np.sqrt(len(diff))) if diff.std(ddof=1) > 0 else float("nan")
            pct = 100 * diff.mean() / a.mean() if a.mean() else float("nan")
            label = {0: "extreme(-)", 1: "pre-extreme(-)", 2: "moderate", 3: "pre-extreme(+)", 4: "extreme(+)"}[b]
            print(f"  bin{b} {label:>14}: A={a.mean():.5f}  B={bb.mean():.5f}  diff={diff.mean():+.5f} ({pct:+.1f}%)  t={t:.2f}")


if __name__ == "__main__":
    main()
