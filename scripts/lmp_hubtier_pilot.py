"""
2026-08-04 -- L/M/P hub-tier pilot (docs/report/2026-08-02-delayed-moderate-conduit-pilot.md,
"New experimental design" entry under the 2026-08-04 section).

Motivation: the whole `extreme=none, moderate class only` pilot (bc OAT battery, bc_recovery OAT)
found no robust extreme-camp effect anywhere -- but `extreme=none` only means no ARTIFICIALLY PINNED
extreme hub, not no extreme hub at all. 13/15 seeds in the bc_recovery OAT's own class-selection
snapshot already had a natural extreme agent (|intrinsicOpinion|>=0.6) among the top-10-by-
followerCount by chance, sign unsystematic -- an uncontrolled confound. This design replaces that
with a hub tier deliberately spanning the full opinion spectrum, built and controlled per seed:

  - Select the top N_HUB=60 agents by t0 followerCount (unfiltered by opinion, unlike the old
    |intrinsicOpinion|<0.2 moderate-only selection).
  - Randomly split (seeded per run seed, so reproducible) into 5 categories of fixed size, and PIN
    each agent's intrinsicOpinion/opinion to that category's target value at t=0 (one-time reset,
    stubbornness left free -- same semantics as the pre-existing pinModerateIds, now generalized to
    an explicit per-agent target via the new pin_opinion_ids token/ExperimentConfig.pinOpinionIds):
      Extreme(-)      n=10   target=-1.0   (matches this project's own ExtremeMode.SYM convention)
      Pre-extreme(-)  n=10   target=-0.4   (midpoint of the bin1 camp-bin range [-0.6,-0.2))
      Moderate        n=20   target= 0.0   (matches the pre-existing pinModerateIds precedent)
      Pre-extreme(+)  n=10   target=+0.4
      Extreme(+)      n=10   target=+1.0
  - Group into 3 intervention categories: M=Moderate(20), E=Extreme both signs(20), P=Pre-extreme
    both signs(20) -- WSSIT's own L/M/R extended with a 4th (P) group WSSIT didn't test.
  - 6 arms (of the full 2^3=8 factorial; M-only-active and all-silent deliberately dropped for this
    first pass): control (all active), N-silent, E-silent, P-silent, E-only-active, P-only-active.
    Silencing reuses the pre-existing silentUntilIds/activationStep=steps+1 (never activates)
    mechanism, same convention as the earlier A_never arm.
  - bc regime: the exploratory bc_recovery=0.001 point from the 2026-08-03 screen (bc_floor=0.2,
    bc_init=0.8, bc_dec=0.5 otherwise default) -- user's choice (2026-08-04), over project defaults
    (bc_recovery=0.0001), to keep testing this design under the most WSSIT-consistent bc regime
    found so far, despite that point not yet showing a robust extreme-camp effect on its own
    (2026-08-04 bc_recovery OAT) -- this is a different question (confound control, not bc tuning).

n=15 fresh seed block (8800000-8800014, unused elsewhere), steps=40000, matching this pilot's
established convention throughout. Batched-postCash fix + corrected per-capita metric (posts/
post_result.csv direct counts) as used since 2026-08-02.

Usage: nohup python3 scripts/lmp_hubtier_pilot.py > logs/lmp_hubtier_pilot_stdout.log 2>&1 &
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
SEEDS = [8800000 + i for i in range(15)]
N_HUB = 60
SUBDIR = "2026-08-04_lmp_hubtier_pilot"
CLASS_SELECT_SUBDIR = f"{SUBDIR}/_class_selection"

GROUP_SIZES = [("E_minus", 10, -1.0), ("P_minus", 10, -0.4), ("M", 20, 0.0),
               ("P_plus", 10, 0.4), ("E_plus", 10, 1.0)]

ARMS = ["control", "N_silent", "E_silent", "P_silent", "E_only_active", "P_only_active"]

BASE_TOKENS = [
    "network=hk", "hk_m=15", "hk_a=4", "hk_pt=0.05",
    "max_follow=43.8638", "follow_prob=0.01", "feed_capacity=15",
    "access_prob=0.1", "p_u=0.05",
    "bc_init=0.800000", "bc_dec=0.500000", "bc_floor=0.2", "bc_recovery=0.001", "bc_ceiling=1.0",
    "vocal_comfort_radius=0.1", "repost_prob=0.1", "relay_enabled=false",
    "out_of_bc_repost_prob=0.01", "rel_attrib=original",
    "stub_dist=uniform", "stub_min=0.82", "stub_max=0.82",
    "evict_beta=-1", "init_prune=trim",
    "initial_pp=0.25537", "max_pp=1.0", "min_pp=0.01", "pp_relax_eta=0.100000",
    "neutral_band=0.2",
    "extreme=none", "n_neutral=0", "alpha=0",
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
        + BASE_TOKENS + extra_tokens
    logfile = ROOT / "logs" / f"lmphubtier_seed{seed}_{subdir.split('/')[-1]}.log"
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


def derive_groups(seed):
    """Top-N_HUB by t0 followerCount (unfiltered by opinion), randomly split into the 5 fixed-size
    target-opinion groups (seeded by this run's own seed, reproducible)."""
    d = result_dir(seed, CLASS_SELECT_SUBDIR)
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
    for name, (ids, target) in groups.items():
        for aid in ids:
            pairs.append(f"{aid}:{target}")
    return "pin_opinion_ids=" + ",".join(pairs)


def arm_silent_ids(groups, arm):
    m_ids = groups["M"][0]
    e_ids = groups["E_minus"][0] + groups["E_plus"][0]
    p_ids = groups["P_minus"][0] + groups["P_plus"][0]
    return {
        "control": [],
        "N_silent": m_ids,
        "E_silent": e_ids,
        "P_silent": p_ids,
        "E_only_active": m_ids + p_ids,
        "P_only_active": m_ids + e_ids,
    }[arm]


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


def struct_metric(seed, arm, col, checkpoint=FULL_STEPS, window=WINDOW):
    d = result_dir(seed, f"{SUBDIR}/{arm}")
    with open(d / "metrics" / "results.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    lo = checkpoint - window
    wrows = [r for r in rows if lo < int(r["step"]) <= checkpoint]
    return np.mean([float(r[col]) for r in wrows])


# ---- non-hub-only split (2026-08-04 follow-up: distinguish the pinned hub-tier agents' own
# posting/comfort behavior from the rest of their camp -- see docs/report/2026-08-02-delayed-
# moderate-conduit-pilot.md). Post-rate: posts/post_result.csv's bin_i counts ALREADY exclude every
# target/hub agent's own original posts by construction (OpinionDynamics.java's pre-existing
# `if (!agent.getTarget())` gate around writer.setPostBins() -- comment "C3"), so the numerator in
# orig_percapita() above is already hub-post-free; only the population DENOMINATOR needed
# correcting (pop_counts() above counts every agent regardless of isTarget). A genuine hub-only post
# rate is NOT obtainable from this file for the same reason (that gate means bin_i is identically 0
# for hub-authored posts, always) -- would need a dedicated per-agent post counter, not attempted
# here (Agent.numOfPosts, tried first, turned out to be a static feed-capacity field set once at
# construction, not a post counter -- reverted). Comfort rate: agent_snapshot_final.csv's
# avgComfortRate column (Agent.getAverageComfortRate(), a trailing-100-step average already
# maintained internally) is per-agent, so hub exclusion is a straightforward isTarget filter. ----


def load_snapshot(seed, arm, label):
    d = result_dir(seed, f"{SUBDIR}/{arm}")
    with open(d / "degrees" / f"agent_snapshot_{label}.csv", newline="") as f:
        return {int(r["agentId"]): r for r in csv.DictReader(f)}


def pop_counts_nonhub(seed, arm):
    counts = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0}
    for r in load_snapshot(seed, arm, "final").values():
        if r["isTarget"] == "0":
            counts[camp_bin(float(r["opinion"]))] += 1
    return counts


def nonhub_percapita(seed, arm, b, checkpoint=FULL_STEPS, window=WINDOW):
    d = result_dir(seed, f"{SUBDIR}/{arm}")
    with open(d / "posts" / "post_result.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    lo = checkpoint - window
    total = sum(int(r[f"bin_{b}"]) for r in rows if lo < int(r["step"]) <= checkpoint)
    n = pop_counts_nonhub(seed, arm)[b]
    return total / n / window if n > 0 else float("nan")


def comfort_by_hubstatus(seed, arm):
    """Per-bin, per-hub-status (isTarget) mean avgComfortRate at the final snapshot."""
    sums = {(b, st): 0.0 for b in range(5) for st in ("hub", "nonhub")}
    pop = {(b, st): 0 for b in range(5) for st in ("hub", "nonhub")}
    for r in load_snapshot(seed, arm, "final").values():
        b = camp_bin(float(r["opinion"]))
        st = "hub" if r["isTarget"] == "1" else "nonhub"
        sums[(b, st)] += float(r["avgComfortRate"])
        pop[(b, st)] += 1
    return {
        key: (sums[key] / pop[key] if pop[key] > 0 else float("nan"))
        for key in sums
    }


def main():
    print("=== Phase 1: class-selection dry runs (t0 followerCount ranking) ===", flush=True)
    run_wave([(s, 0, CLASS_SELECT_SUBDIR, []) for s in SEEDS], max_workers=len(SEEDS))

    print("\n=== Deriving hub-tier groups per seed ===", flush=True)
    groups_by_seed = {}
    for s in SEEDS:
        groups_by_seed[s] = derive_groups(s)
        sizes = {name: len(ids) for name, (ids, _) in groups_by_seed[s].items()}
        print(f"  seed={s}: {sizes}", flush=True)

    print(f"\n=== Phase 2: {len(ARMS)} arms x {len(SEEDS)} seeds (steps={FULL_STEPS}) ===", flush=True)
    jobs = []
    for s in SEEDS:
        groups = groups_by_seed[s]
        pin_token = build_pin_token(groups)
        for arm in ARMS:
            tokens = [pin_token]
            silent_ids = arm_silent_ids(groups, arm)
            if silent_ids:
                idstr = ",".join(str(a) for a in silent_ids)
                tokens += [f"silent_until_ids={idstr}", f"activation_step={FULL_STEPS + 1}"]
            jobs.append((s, FULL_STEPS, f"{SUBDIR}/{arm}", tokens))
    run_wave(jobs, max_workers=20)

    print("\n=== Per-capita original-post rate by bin, each arm vs control, n=15 ===")
    for arm in ARMS:
        if arm == "control":
            continue
        print(f"\n### {arm} vs control ###")
        for b in range(5):
            a = np.array([orig_percapita(s, "control", b) for s in SEEDS])
            bb = np.array([orig_percapita(s, arm, b) for s in SEEDS])
            diff = bb - a
            t = diff.mean() / (diff.std(ddof=1) / np.sqrt(len(diff))) if diff.std(ddof=1) > 0 else float("nan")
            pct = 100 * diff.mean() / a.mean() if a.mean() else float("nan")
            label = {0: "extreme(-)", 1: "pre-extreme(-)", 2: "moderate", 3: "pre-extreme(+)", 4: "extreme(+)"}[b]
            print(f"  bin{b} {label:>14}: control={a.mean():.5f}  {arm}={bb.mean():.5f}  "
                  f"diff={diff.mean():+.5f} ({pct:+.1f}%)  t={t:.2f}")
        for col in ["opinionAssortativity", "crossCuttingFraction"]:
            a = np.array([struct_metric(s, "control", col) for s in SEEDS])
            bb = np.array([struct_metric(s, arm, col) for s in SEEDS])
            diff = bb - a
            t = diff.mean() / (diff.std(ddof=1) / np.sqrt(len(diff))) if diff.std(ddof=1) > 0 else float("nan")
            print(f"  {col:>22}: control={a.mean():.4f}  {arm}={bb.mean():.4f}  diff={diff.mean():+.4f}  t={t:.2f}")

    # ---- non-hub-only split: does each arm's effect on a camp's posting rate/comfort rate survive
    # when the pinned hub-tier agents themselves are excluded from the population? post_result.csv's
    # numerator is already hub-post-free by construction (see comment above nonhub_percapita);
    # only the population denominator needed correcting. ----
    bin_label = {0: "extreme(-)", 1: "pre-extreme(-)", 2: "moderate", 3: "pre-extreme(+)", 4: "extreme(+)"}
    print(f"\n\n=== Non-hub-only per-capita ORIGINAL post rate, each arm vs control (n=15, "
          f"window={WINDOW}) ===")
    print("(numerator already hub-post-free by construction; denominator excludes the 60 pinned hub-tier agents)")
    for arm in ARMS:
        if arm == "control":
            continue
        print(f"\n### {arm} vs control (non-hub) ###")
        for b in range(5):
            c = np.array([nonhub_percapita(s, "control", b) for s in SEEDS])
            t_ = np.array([nonhub_percapita(s, arm, b) for s in SEEDS])
            diff = t_ - c
            valid = ~np.isnan(diff)
            if valid.sum() < 2:
                print(f"  bin{b} {bin_label[b]:>14}: insufficient non-hub population in this bin")
                continue
            dv = diff[valid]
            tstat = dv.mean() / (dv.std(ddof=1) / np.sqrt(len(dv))) if dv.std(ddof=1) > 0 else float("nan")
            pct = 100 * dv.mean() / c[valid].mean() if c[valid].mean() else float("nan")
            print(f"  bin{b} {bin_label[b]:>14}: control={c[valid].mean():.5f}  {arm}={t_[valid].mean():.5f}  "
                  f"diff={dv.mean():+.5f} ({pct:+.1f}%)  t={tstat:.2f}  n={valid.sum()}")

    print(f"\n\n=== Non-hub-only mean comfort rate (avgComfortRate, trailing-100-step), "
          f"each arm vs control (n=15) ===")
    comfort_by_seed_arm = {s: {arm: comfort_by_hubstatus(s, arm) for arm in ARMS} for s in SEEDS}
    for arm in ARMS:
        if arm == "control":
            continue
        print(f"\n### {arm} vs control (non-hub only) ###")
        for b in range(5):
            c = np.array([comfort_by_seed_arm[s]["control"][(b, "nonhub")] for s in SEEDS])
            t_ = np.array([comfort_by_seed_arm[s][arm][(b, "nonhub")] for s in SEEDS])
            diff = t_ - c
            valid = ~np.isnan(diff)
            if valid.sum() < 2:
                print(f"  bin{b} {bin_label[b]:>14}: insufficient non-hub population in this bin")
                continue
            dv = diff[valid]
            tstat = dv.mean() / (dv.std(ddof=1) / np.sqrt(len(dv))) if dv.std(ddof=1) > 0 else float("nan")
            print(f"  bin{b} {bin_label[b]:>14}: control={c[valid].mean():.4f}  {arm}={t_[valid].mean():.4f}  "
                  f"diff={dv.mean():+.4f}  t={tstat:.2f}  n={valid.sum()}")


if __name__ == "__main__":
    main()
