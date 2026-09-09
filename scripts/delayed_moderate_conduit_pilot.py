"""
2026-08-02 -- Pilot: delayed-entry moderate-conduit experiment ("orthogonally-popular figure
starts speaking on a topic only once it's already contentious").

Context (docs/report/2026-07-31-wssit-era-vs-current-model-diff.md, "hub plateau" discussion):
the mega/middle-tier "moderate hub" pool used throughout the 2026-07-21+ removehub battery is
selected from the POST-EQUILIBRIUM network, so its follower base is already opinion-homophily-
shaped/camp-correlated by the time it's picked -- individual necessity there is near-zero
(0.07-0.64%, "founder-clique redundancy"). This experiment instead selects the moderate class from
the INITIAL (t=0, pre-opinion-sorting) network -- their t=0 audience isn't yet opinion-correlated,
approximating "popular for reasons orthogonal to this topic" (e.g. a celebrity unrelated to
politics) -- and controls WHEN that class starts participating on the topic, via new
ExperimentConfig fields `pinModerateIds`/`silentUntilIds`/`activationStep`
(src/experiment/ExperimentConfig.java, src/dynamics/OpinionDynamics.java, 2026-08-02).

Mechanism (user-specified 2026-08-02):
  - Class = top-K by t=0 followerCount among |intrinsicOpinion|<0.2 agents (rank-based, not an
    absolute followerCount cutoff, since t0 in-degree scale is generator/seed-dependent).
  - intrinsicOpinion/opinion reset to 0.0 at t=0 (pinModerateIds) -- a ONE-TIME reset, not a
    permanent freeze: stubbornness is deliberately left at its normal per-agent draw (user: this
    agent isn't stubbornly moderate, they simply weren't engaged with the topic yet, so their
    opinion should be free to drift once they do engage).
  - Channel silenced (NONE) until a class-wide activation step (silentUntilIds/activationStep) --
    fixed-step trigger (user decision), not an endogenous topic-heat threshold.
  - extreme=none (no artificially pinned +-1 background hubs -- user decision to rely on
    naturally-emergent extremity from the initial opinion distribution instead, consistent with
    research-direction.md's "knob, not assumption" principle).
  - alpha=0 (For-You feed off entirely -- isolates follow-graph-mediated dynamics only, matches
    the WSSIT-era regime and this project's own alpha0_conduit_replication.py precedent).

Four arms, same seed shared across all four (common-random-numbers pairing -- trajectories are
identical up to the first behavioral divergence):
  A_never:  class permanently silent (activation_step beyond FULL_STEPS) -- closest analogue to
            "exclude the redundant hub plateau entirely," the framing this whole investigation
            started from.
  B_always: class active from t=0 (no silence at all) -- the WSSIT-original-style baseline.
  C_10k:    class silent until step 10000, then activates.
  D_30k:    class silent until step 30000, then activates.

Known open risk (2026-08-02 discussion, NOT mitigated by this script -- user: "just check the log,
reconsider if it looks bad"): Agent.follow()'s capacity-based eviction can sever OTHER agents'
edges INTO a silenced class member purely by opinion-distance pressure as the network sorts, with
no post/content involved (unlike unfollow(), which requires reading an actual post). This means
"silence preserves the t0 cross-cutting follower base" is not guaranteed by construction. This
script logs class followerCount (inDegree) at every periodic checkpoint (already-existing
degree_result_<step>.csv snapshots, no new instrumentation needed) so this can be checked directly
before trusting any downstream metric difference between arms.

Usage: nohup python3 scripts/delayed_moderate_conduit_pilot.py > logs/delayed_moderate_pilot_stdout.log 2>&1 &
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
N_SEEDS = 5
TOPK_MODERATE = 20
MODERATE_THRESHOLD = 0.2
BASE_SEED = 7300000
SUBDIR = "2026-08-02_delayed-moderate-pilot"
CLASS_SELECT_SUBDIR = f"{SUBDIR}/_class_selection"

# activation_step=None means "no silent_until_ids at all" (active from t=0, arm B).
# FULL_STEPS+1 means "never fires within the run" (arm A).
ARMS = {
    "A_never": FULL_STEPS + 1,
    "B_always": None,
    "C_10k": 10000,
    "D_30k": 30000,
}

# Mirrors current ExperimentConfig field defaults explicitly (robustness against future default
# drift -- same convention as scripts/moderate_hub_4tier_removehub.py's FIXED_TOKENS), with
# extreme/alpha overridden per the design above.
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
    """jobs: list of (seed, steps, subdir, tokens)."""
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


def class_followercount_at(seed, arm, ids, step):
    d = result_dir(seed, f"{SUBDIR}/{arm}")
    fp = d / "degrees" / f"degree_result_{step}.csv"
    if not fp.exists():
        return None
    lookup = {}
    with open(fp, newline="") as f:
        for r in csv.DictReader(f):
            lookup[int(r["agentId"])] = int(r["inDegree"])
    vals = [lookup[i] for i in ids if i in lookup]
    return float(np.mean(vals)) if vals else None


def read_metrics_at(seed, arm, checkpoint):
    d = result_dir(seed, f"{SUBDIR}/{arm}")
    with open(d / "metrics" / "results.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    at = next(r for r in reversed(rows) if int(r["step"]) == checkpoint)
    q = None
    with open(d / "metrics" / "modularity.csv", newline="") as f:
        for row in csv.DictReader(f):
            if int(row["step"]) == checkpoint:
                q = float(row["Q_sign_repost"])
    opinion_var = float(at["opinionVar"])
    post_opinion_var = float(at["postOpinionVar"])
    sf1 = post_opinion_var / opinion_var if opinion_var > 0 else None
    return dict(
        sf1_ratio=sf1,
        opinionAssortativity=float(at["opinionAssortativity"]),
        crossCuttingFraction=float(at["crossCuttingFraction"]),
        bimodalityCoeff=float(at["bimodalityCoeff"]),
        Q_sign_repost=q,
        opinionKurtosis=float(at["opinionKurtosis"]),
        disagreement=float(at["disagreement"]),
    )


METRIC_NAMES = ["sf1_ratio", "opinionAssortativity", "crossCuttingFraction",
                "bimodalityCoeff", "Q_sign_repost", "opinionKurtosis", "disagreement"]

LOG_PATH = ROOT / "docs" / "report" / "delayed_moderate_conduit_pilot.csv"
FOLLOWER_LOG_PATH = ROOT / "docs" / "report" / "delayed_moderate_conduit_pilot_followercount.csv"


def main():
    seeds = [BASE_SEED + i for i in range(N_SEEDS)]

    print("=== Phase 1: class-selection dry runs (steps=0) ===", flush=True)
    run_wave([(s, 0, CLASS_SELECT_SUBDIR, []) for s in seeds], max_workers=N_SEEDS)

    class_ids = {}
    for s in seeds:
        class_ids[s] = derive_class_ids(s)
        print(f"  seed={s}: {len(class_ids[s])} class agents -> {class_ids[s]}", flush=True)

    print("\n=== Phase 2: 4 arms x 5 seeds (steps={}) ===".format(FULL_STEPS), flush=True)
    jobs = []
    for s in seeds:
        idstr = ",".join(str(a) for a in class_ids[s])
        for arm, activation_step in ARMS.items():
            tokens = [f"pin_moderate_ids={idstr}"]
            if activation_step is not None:
                tokens += [f"silent_until_ids={idstr}", f"activation_step={activation_step}"]
            jobs.append((s, FULL_STEPS, f"{SUBDIR}/{arm}", tokens))
    run_wave(jobs, max_workers=20)

    print("\n=== Reading metrics + writing logs ===", flush=True)
    with open(LOG_PATH, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["arm", "seed", "checkpoint", "n_class"] + METRIC_NAMES)
        for arm in ARMS:
            for s in seeds:
                for cp in CHECKPOINTS:
                    m = read_metrics_at(s, arm, cp)
                    w.writerow([arm, s, cp, len(class_ids[s])] + [m[k] for k in METRIC_NAMES])
    print(f"Full metrics log: {LOG_PATH}", flush=True)

    with open(FOLLOWER_LOG_PATH, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["arm", "seed", "checkpoint", "class_mean_followercount"])
        for arm in ARMS:
            for s in seeds:
                for cp in [0] + CHECKPOINTS:
                    step = cp if cp != 0 else 0
                    fc = class_followercount_at(s, arm, class_ids[s], step) if step > 0 else None
                    if step == 0:
                        # t0 snapshot for followerCount lives in agent_snapshot_t0.csv, not
                        # degree_result_0.csv naming -- read from there for the step=0 row.
                        d = result_dir(s, f"{SUBDIR}/{arm}")
                        lookup = {}
                        with open(d / "degrees" / "agent_snapshot_t0.csv", newline="") as sf:
                            for r in csv.DictReader(sf):
                                lookup[int(r["agentId"])] = int(r["followerCount"])
                        vals = [lookup[i] for i in class_ids[s] if i in lookup]
                        fc = float(np.mean(vals)) if vals else None
                    w.writerow([arm, s, step, fc])
    print(f"Follower-count diagnostic log: {FOLLOWER_LOG_PATH}", flush=True)

    print("\n=== Risk-1 diagnostic: class mean followerCount by arm/checkpoint (pooled over seeds) ===")
    for arm in ARMS:
        vals_by_cp = {}
        for cp in [0] + CHECKPOINTS:
            vals = []
            for s in seeds:
                d = result_dir(s, f"{SUBDIR}/{arm}")
                if cp == 0:
                    lookup = {}
                    with open(d / "degrees" / "agent_snapshot_t0.csv", newline="") as sf:
                        for r in csv.DictReader(sf):
                            lookup[int(r["agentId"])] = int(r["followerCount"])
                    v = [lookup[i] for i in class_ids[s] if i in lookup]
                else:
                    fp = d / "degrees" / f"degree_result_{cp}.csv"
                    lookup = {}
                    with open(fp, newline="") as sf:
                        for r in csv.DictReader(sf):
                            lookup[int(r["agentId"])] = int(r["inDegree"])
                    v = [lookup[i] for i in class_ids[s] if i in lookup]
                if v:
                    vals.append(float(np.mean(v)))
            if vals:
                vals_by_cp[cp] = np.mean(vals)
        print(f"  {arm:>10}: " + "  ".join(f"step{cp}={vals_by_cp.get(cp, float('nan')):.1f}" for cp in [0] + CHECKPOINTS))

    print("\n=== Metrics by arm, checkpoint (mean+/-std, n={}) ===".format(N_SEEDS))
    all_vals = {(arm, cp): {m: [] for m in METRIC_NAMES} for arm in ARMS for cp in CHECKPOINTS}
    for arm in ARMS:
        for cp in CHECKPOINTS:
            for s in seeds:
                m = read_metrics_at(s, arm, cp)
                for k in METRIC_NAMES:
                    if m[k] is not None:
                        all_vals[(arm, cp)][k].append(m[k])
    for cp in CHECKPOINTS:
        print(f"\n### checkpoint={cp} ###")
        for arm in ARMS:
            row = all_vals[(arm, cp)]
            summary = "  ".join(f"{k}={np.mean(row[k]):.4f}+/-{np.std(row[k]):.4f}" for k in METRIC_NAMES if row[k])
            print(f"  {arm:>10}: {summary}")

    print("\n=== Paired diffs vs B_always (same-seed, common random numbers) ===")
    for other in ["A_never", "C_10k", "D_30k"]:
        for cp in CHECKPOINTS:
            print(f"\n### {other} - B_always, checkpoint={cp} ###")
            for k in METRIC_NAMES:
                b = np.array(all_vals[("B_always", cp)][k])
                o = np.array(all_vals[(other, cp)][k])
                if len(b) != len(o) or len(b) < 2:
                    continue
                diff = o - b
                tstat = diff.mean() / (diff.std(ddof=1) / np.sqrt(len(diff))) if diff.std(ddof=1) > 0 else float("nan")
                print(f"  {k:>24}: diff={diff.mean():+.4f}+/-{diff.std():.4f}  t={tstat:.2f}")


if __name__ == "__main__":
    main()
