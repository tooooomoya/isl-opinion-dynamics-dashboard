"""
2026-07-26 -- Restart of the hub-swap experiment (docs/report/2026-07-21-conduit-experiment-design.md,
"Experiment redesign: secession test, not addition test"). First step: check where neutral hubs
actually sit in the in-degree distribution UNDER THE CURRENT (2026-07-25 v15-frozen) calibration
point, with a SYNTHETIC (gaussian, not init_dist=empirical) initial opinion distribution -- the
2026-07-21 hub_tier_characterization.py run used the 2026-07-20 static-bc point, since superseded
by the graded-bc redesign (v13) and the v14/v15 fixes; that tier picture is stale.

Per this project's own methodological lesson (docs/report/2026-07-21-conduit-experiment-design.md,
"ROOT CAUSE: v9-vs-v10 same point different result was an uncontrolled pU default"): pin EVERY
dynamics-relevant parameter explicitly in launch(), matching the exact "Calibration closed for now
(2026-07-25)" frozen ExperimentConfig defaults verbatim, rather than relying on compiled defaults
that could silently change on a future recompile.

n=1000, steps=40000 (current default -- the actual adopted run length, not the steps=20000 shortcut
used by many earlier calibration scripts), 20 seeds (user decision, 2026-07-26: "20 seeds is
enough" after the initial n=3 pass showed mega-tier composition was too seed-volatile to read).
log_gexf left at its default (true) since the next step (the actual swap) needs a GEXF snapshot to
swap from.

Resumable (per CLAUDE.md): re-runs only reuse existing results/run_<seed>_* folders and launch the
remainder, so extending N_SEEDS later doesn't re-simulate already-completed seeds.

Tiers (user decision, 2026-07-26, replacing the earlier mega/mid/tail-to-zero scheme): three closed
bands -- mega (>500 followers), mid (100-500], small (50-100]. Agents with <=50 followers are
excluded entirely (not a candidate pool for hub selection). A seed with zero agents in a tier (the
n=3 pass showed this happens for "mega") is EXCLUDED from that tier's frac_moderate/mean_opinion
aggregate rather than counted as a 0 (user decision, 2026-07-26: "if mega dont exist, just exclude
them from results") -- an empty tier is a missing observation, not evidence of zero moderation.

Usage: python3 scripts/hub_tier_check_v15_synth.py
"""
import concurrent.futures
import csv
import subprocess
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
_JARS = list(ROOT.glob("lib/**/*.jar"))  # matches run.sh's `find lib -name '*.jar'` (jars are nested, e.g. lib/gephi/*.jar)
LIBCP = ":".join(str(p) for p in _JARS) + (":" if _JARS else "") + str(ROOT / "bin")

N = 1000
STEPS = 40000
N_SEEDS = 20
BASE_SEED = 1726000  # fresh range, unused by any prior script (mnemonic: 07-26)
MODERATE_THRESHOLD = 0.2

# Verbatim from docs/report/2026-07-21-conduit-experiment-design.md's
# "Calibration closed for now (2026-07-25) -- frozen ExperimentConfig snapshot" entry.
FIXED = dict(
    network="hk", hk_m=15, hk_a=4, hk_pt=0.05,
    max_follow=43.8638, follow_prob=0.05955,
    alpha=0.63, hop=4, feed_capacity=31, vel_mode="windowed",
    access_prob=0.025,
    p_u=0.1,
    bc_dec=1.0, bc_recovery=0.0005, bc_floor=0.2, bc_ceiling=1.0, bc_init=1.0,
    init_dist="gaussian", init_op="noclip",
    vocal_comfort_radius=0.5,
    repost_prob=0.1, relay_enabled="false", out_of_bc_repost_prob=0.01, rel_attrib="original",
    stub_dist="uniform", stub_min=0.82, stub_max=0.82,
    evict_beta=-1, init_prune="trim",
    initial_pp=0.25537, max_pp=1.0, min_pp=0.01, pp_relax_eta=0.002215,
    neutral_band=0.2,
)

TIERS = [
    ("mega", 500, N),
    ("mid", 100, 500),
    ("small", 50, 100),
]

RAW_LOG = ROOT / "docs" / "report" / "hub_tier_v15_synth_raw.csv"
SUMMARY_LOG = ROOT / "docs" / "report" / "hub_tier_v15_synth_summary.csv"


def launch(seed):
    tokens = [
        f"seed={seed}", f"n={N}", f"steps={STEPS}", "force=true",
        f"network={FIXED['network']}", f"hk_m={FIXED['hk_m']}", f"hk_a={FIXED['hk_a']}",
        f"hk_pt={FIXED['hk_pt']}",
        f"max_follow={FIXED['max_follow']}", f"follow_prob={FIXED['follow_prob']}",
        f"alpha={FIXED['alpha']}", f"hop={FIXED['hop']}", f"feed_capacity={FIXED['feed_capacity']}",
        f"vel_mode={FIXED['vel_mode']}",
        f"access_prob={FIXED['access_prob']}",
        f"p_u={FIXED['p_u']}",
        f"bc_dec={FIXED['bc_dec']:.6f}", f"bc_recovery={FIXED['bc_recovery']:.6f}",
        f"bc_floor={FIXED['bc_floor']}", f"bc_ceiling={FIXED['bc_ceiling']}",
        f"bc_init={FIXED['bc_init']:.6f}",
        f"init_dist={FIXED['init_dist']}",
        f"vocal_comfort_radius={FIXED['vocal_comfort_radius']}",
        f"repost_prob={FIXED['repost_prob']}", f"relay_enabled={FIXED['relay_enabled']}",
        f"out_of_bc_repost_prob={FIXED['out_of_bc_repost_prob']}", f"rel_attrib={FIXED['rel_attrib']}",
        f"stub_dist={FIXED['stub_dist']}", f"stub_min={FIXED['stub_min']}", f"stub_max={FIXED['stub_max']}",
        f"evict_beta={FIXED['evict_beta']}", f"init_prune={FIXED['init_prune']}",
        f"initial_pp={FIXED['initial_pp']}", f"max_pp={FIXED['max_pp']}", f"min_pp={FIXED['min_pp']}",
        f"pp_relax_eta={FIXED['pp_relax_eta']:.6f}",
        f"neutral_band={FIXED['neutral_band']}",
    ]
    logfile = ROOT / "logs" / f"hubtier_v15_seed{seed}.log"
    logfile.parent.mkdir(exist_ok=True)
    with open(logfile, "w") as lf:
        p = subprocess.Popen(
            ["java", "-Xmx2g", "-cp", LIBCP, "dynamics.OpinionDynamics", *tokens],
            stdout=lf, stderr=subprocess.STDOUT, cwd=ROOT,
        )
    return p


def read_snapshot(seed):
    candidates = sorted(ROOT.glob(f"results/run_{seed}_*"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        return None, None
    d = candidates[-1]
    snap_path = d / "degrees" / "agent_snapshot_final.csv"
    if not snap_path.exists():
        return None, None
    rows = []
    with open(snap_path, newline="") as f:
        for r in csv.DictReader(f):
            rows.append((int(r["agentId"]), float(r["opinion"]), int(r["followerCount"])))
    rows.sort(key=lambda t: -t[2])
    return rows, d.name


def evaluate_seed(seed):
    rows, folder = read_snapshot(seed)
    if rows is not None:
        print(f"  seed={seed}: reusing existing {folder}", flush=True)
        return seed, rows, folder
    p = launch(seed)
    p.wait()
    rows, folder = read_snapshot(seed)
    return seed, rows, folder


def tier_of(followers):
    for name, lo, hi in TIERS:
        if lo < followers <= hi:
            return name
    return "excluded"  # <=50 followers: not a candidate pool for hub selection


def main():
    seeds = [BASE_SEED + j for j in range(N_SEEDS)]
    print(f"{N_SEEDS} seeds ({seeds[0]}-{seeds[-1]}), n={N}, steps={STEPS}, init_dist=gaussian, "
          f"v15-frozen params (fully pinned); reusing any already-completed seeds...", flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=N_SEEDS) as ex:
        results = list(ex.map(evaluate_seed, seeds))

    ok = [(s, rows, folder) for s, rows, folder in results if rows is not None]
    print(f"n={len(ok)}/{N_SEEDS} succeeded", flush=True)
    for seed, rows, folder in ok:
        print(f"  seed={seed} -> {folder}")

    raw_rows = []
    for seed, rows, folder in ok:
        for rank, (agent_id, opinion, followers) in enumerate(rows, start=1):
            raw_rows.append([seed, rank, tier_of(followers), agent_id, opinion, followers,
                              int(abs(opinion) < MODERATE_THRESHOLD)])

    RAW_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(RAW_LOG, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["seed", "rank", "tier", "agentId", "opinion", "followerCount", "isModerate"])
        w.writerows(raw_rows)
    print(f"\nRaw (all agents, all seeds): {RAW_LOG}")

    print("\n=== Per-tier summary (mean +/- sd across seeds; empty-tier seeds EXCLUDED, not zeroed) ===")
    summary_rows = []
    for name, lo, hi in TIERS:
        sizes = []          # tier_size across ALL seeds (0 is a real observation here)
        frac_mods, mean_ops, mean_fols = [], [], []  # only from seeds where this tier is non-empty
        for seed, rows, folder in ok:
            in_tier = [(a, op, fo) for a, op, fo in rows if lo < fo <= hi]
            sizes.append(len(in_tier))
            if in_tier:
                n_neutral = sum(1 for _, op, _ in in_tier if abs(op) < MODERATE_THRESHOLD)
                frac_mods.append(n_neutral / len(in_tier))
                mean_ops.append(np.mean([abs(op) for _, op, _ in in_tier]))
                mean_fols.append(np.mean([fo for _, _, fo in in_tier]))
        sizes_a = np.array(sizes)
        n_present = len(frac_mods)
        frac_mod_a = np.array(frac_mods)
        print(f"{name:>6}: tier_size={sizes_a.mean():.1f}+/-{sizes_a.std():.1f} (all {len(ok)} seeds)  "
              f"present_in={n_present}/{len(ok)} seeds  "
              f"frac_moderate={frac_mod_a.mean():.2f}+/-{frac_mod_a.std():.2f}  "
              f"mean|opinion|={np.mean(mean_ops) if mean_ops else float('nan'):.3f}  "
              f"mean_followers={np.mean(mean_fols) if mean_fols else float('nan'):.1f}")
        summary_rows.append([name, lo, hi, sizes_a.mean(), sizes_a.std(), n_present, len(ok),
                              frac_mod_a.mean() if n_present else None,
                              frac_mod_a.std() if n_present else None,
                              np.mean(mean_ops) if mean_ops else None,
                              np.mean(mean_fols) if mean_fols else None])

    with open(SUMMARY_LOG, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["tier", "lo_exclusive", "hi_inclusive", "mean_tier_size", "sd_tier_size",
                     "n_seeds_present", "n_seeds_total", "mean_frac_moderate", "sd_frac_moderate",
                     "mean_abs_opinion", "mean_followers"])
        w.writerows(summary_rows)
    print(f"\nSummary: {SUMMARY_LOG}")

    for name in ("mega", "mid", "small"):
        print(f"\n=== {name} tier, individual hubs (all seeds) ===")
        lo, hi = dict((t[0], (t[1], t[2])) for t in TIERS)[name]
        for seed, rows, folder in ok:
            hits = [(a, op, fo) for a, op, fo in rows if lo < fo <= hi]
            for a, op, fo in hits:
                mod_flag = "MODERATE" if abs(op) < MODERATE_THRESHOLD else ""
                print(f"  seed={seed} agent={a} followers={fo} opinion={op:+.3f} {mod_flag}")


if __name__ == "__main__":
    main()
