"""
2026-07-29 -- v7: re-analysis of v6's already-completed runs (no new simulations), fixing the
per-capita post rate metric per user correction. The v5/v6 percapita_extreme/percapita_preextreme
used a single-step snapshot (postShare_i at the checkpoint step only) -- inspection of one seed
(5500004, reach_mod_top=0.2248, the highest in the sample) found postShare_1=postShare_3=0.0000
exactly at step 20000, i.e. literally zero of that one step's ~149 posts came from a currently
pre-extreme-classified agent, despite ~496 such agents existing. Not a bug (verified directly against
results.csv), but a real limitation: postShare_i is recomputed fresh from postCash every single step
(Analysis.java computePostShareArray), so with accessProb=0.1 gating ~90% of agents out of acting at
all per step plus posting being a further probabilistic gate, single-step class rates are noisy and
zero-inflated, especially late in a run.

User's fix (2026-07-29): use a TRAILING WINDOW of posts (1000 steps) ending at each checkpoint, not
the single checkpoint step, and define the rate as "average post count per agent per step" --
literally (class's total post count over the window) / (class's member count) / (window length in
steps). This is both less noisy (aggregates ~1000 per-step draws instead of reading one) and matches
the units the earlier established finding actually reported (a rate, not a share).

Implementation: results.csv logs every single step (verified: 20001 rows for a 20000-step run), so
for each checkpoint T in {5000, 10000, 20000}, sum (postShare_i(t) + postShare_j(t)) *
(originalPostCount(t) + repostCount(t)) over t in (T-1000, T] for the two 5-bin opinionClass indices
making up each behavioral class (pre-extreme = bins 1,3; extreme = bins 0,4), then divide by the t0
population count for that class (agent_snapshot_t0.csv, same denominator convention as v5/v6 --
population counts were checked roughly stable over the run for pre-extreme/moderate, less so for
strict extremes, which the writeup should flag) and by the window length (1000).

Re-reads v6's predictor/outcome CSV for everything else (predictors, other outcomes) and only
replaces percapita_extreme/percapita_preextreme with the windowed version, then re-runs the full
Spearman + BH-FDR analysis so the whole table is internally consistent again.

Usage: python3 scripts/feed_redesign_v7_windowed_percapita_reanalysis.py > logs/feed_redesign_v7_stdout.log 2>&1
"""
import csv
import sys
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.feed_redesign_v6_tier_decomposed_n100 import PREDICTORS, t0_class  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CHECKPOINTS = [5000, 10000, 20000]
WINDOW = 1000
V6_CSV = ROOT / "docs" / "report" / "feed_redesign_v6_tier_decomposed.csv"
LOG_PATH = ROOT / "docs" / "report" / "feed_redesign_v7_windowed_percapita.csv"

OTHER_OUTCOMES = ["sf1", "crossCuttingFraction", "opinionAssortativity", "Q_sign_repost",
                  "bimodalityCoeff", "postShare_extreme", "opinionVar", "postOpinionVar"]
OUTCOMES = OTHER_OUTCOMES + ["percapita_extreme_w", "percapita_preextreme_w"]


def find_run_dir(seed):
    candidates = sorted(ROOT.glob(f"results/run_{seed}_*"), key=lambda p: p.stat().st_mtime)
    return candidates[-1] if candidates else None


def t0_class_counts(run_dir):
    pop_by_class = [0] * 5
    with open(run_dir / "degrees" / "agent_snapshot_t0.csv", newline="") as f:
        for r in csv.DictReader(f):
            pop_by_class[t0_class(float(r["opinion"]))] += 1
    return pop_by_class[0] + pop_by_class[4], pop_by_class[1] + pop_by_class[3]  # extreme, preextreme


def windowed_percapita(run_dir, pop_extreme_t0, pop_preextreme_t0):
    """Returns {checkpoint: (percapita_extreme_w, percapita_preextreme_w)}."""
    with open(run_dir / "metrics" / "results.csv", newline="") as f:
        reader = csv.DictReader(f)
        rows = {}
        for r in reader:
            step = int(r["step"])
            if step == 0:
                continue
            total_posts = int(r["originalPostCount"]) + int(r["repostCount"])
            ext_posts = (float(r["postShare_0"]) + float(r["postShare_4"])) * total_posts
            preext_posts = (float(r["postShare_1"]) + float(r["postShare_3"])) * total_posts
            rows[step] = (ext_posts, preext_posts)

    out = {}
    for chk in CHECKPOINTS:
        lo = chk - WINDOW + 1
        ext_sum = sum(rows[s][0] for s in range(lo, chk + 1) if s in rows)
        preext_sum = sum(rows[s][1] for s in range(lo, chk + 1) if s in rows)
        n_steps = sum(1 for s in range(lo, chk + 1) if s in rows)
        rate_ext = ext_sum / pop_extreme_t0 / n_steps if pop_extreme_t0 > 0 and n_steps > 0 else None
        rate_preext = preext_sum / pop_preextreme_t0 / n_steps if pop_preextreme_t0 > 0 and n_steps > 0 else None
        out[chk] = (rate_ext, rate_preext)
    return out


def bh_fdr(pvals):
    pvals = np.asarray(pvals)
    n = len(pvals)
    order = np.argsort(pvals)
    ranked = pvals[order]
    q = ranked * n / (np.arange(n) + 1)
    q = np.minimum.accumulate(q[::-1])[::-1]
    out = np.empty(n)
    out[order] = np.minimum(q, 1.0)
    return out


def main():
    v6_rows = list(csv.DictReader(open(V6_CSV)))
    records = []
    missing = 0
    for row in v6_rows:
        seed = int(row["seed"])
        run_dir = find_run_dir(seed)
        if run_dir is None:
            missing += 1
            continue
        pop_ext, pop_preext = t0_class_counts(run_dir)
        wpc = windowed_percapita(run_dir, pop_ext, pop_preext)
        rec = {"seed": seed, "pred": {p: float(row[p]) for p in PREDICTORS}, "out": {}}
        for chk in CHECKPOINTS:
            d = {k: (float(row[f"{k}_{chk}"]) if row.get(f"{k}_{chk}") not in (None, "", "None") else None)
                 for k in OTHER_OUTCOMES}
            d["percapita_extreme_w"], d["percapita_preextreme_w"] = wpc[chk]
            rec["out"][chk] = d
        records.append(rec)
    print(f"Recomputed windowed per-capita for {len(records)}/{len(v6_rows)} seeds "
          f"({missing} missing results/ dirs)", flush=True)

    with open(LOG_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        header = ["seed"] + PREDICTORS
        for chk in CHECKPOINTS:
            header += [f"{o}_{chk}" for o in OUTCOMES]
        writer.writerow(header)
        for rec in records:
            row = [rec["seed"]] + [rec["pred"][p] for p in PREDICTORS]
            for chk in CHECKPOINTS:
                row += [rec["out"][chk].get(k) for k in OUTCOMES]
            writer.writerow(row)

    # sanity: distribution of the new metric vs the old zero-inflated one
    old_preext_20000 = np.array([float(r[f"percapita_preextreme_20000"]) for r in v6_rows
                                  if r.get("percapita_preextreme_20000") not in (None, "", "None")])
    new_preext_20000 = np.array([rec["out"][20000]["percapita_preextreme_w"] for rec in records
                                  if rec["out"][20000]["percapita_preextreme_w"] is not None])
    print(f"\nold (single-step) percapita_preextreme@20000: mean={old_preext_20000.mean():.4f}, "
          f"frac_exactly_zero={(old_preext_20000 == 0).mean():.3f}")
    print(f"new (windowed) percapita_preextreme_w@20000:  mean={new_preext_20000.mean():.4f}, "
          f"frac_exactly_zero={(new_preext_20000 == 0).mean():.3f}", flush=True)

    # Correlation table (predictors x new outcomes, same as v6 but percapita replaced)
    cells = []
    for pred in PREDICTORS:
        x = np.array([rec["pred"][pred] for rec in records], dtype=float)
        for chk in CHECKPOINTS:
            for out_name in OUTCOMES:
                y = np.array([rec["out"][chk].get(out_name) for rec in records], dtype=float)
                mask = ~np.isnan(x) & ~np.isnan(y)
                if mask.sum() < 10:
                    continue
                rho, p = spearmanr(x[mask], y[mask])
                cells.append((pred, out_name, chk, rho, p))

    pvals = [c[4] for c in cells]
    qvals = bh_fdr(pvals)
    print("\n=== Correlation table (windowed per-capita), Spearman rho, BH-FDR q ===", flush=True)
    sig_cells = []
    for (pred, out_name, chk, rho, p), q in sorted(zip(cells, qvals), key=lambda z: z[0][4]):
        if q < 0.10:
            sig_cells.append((pred, out_name, chk, rho, p, q))
    print(f"{len(sig_cells)} cells survive BH-FDR<0.10 out of {len(cells)} tested\n")
    for pred, out_name, chk, rho, p, q in sig_cells:
        print(f"  {pred} -> {out_name} @ step{chk}: rho={rho:.3f}, p={p:.4g}, q={q:.4g}")

    print(f"\nFull log: {LOG_PATH}", flush=True)


if __name__ == "__main__":
    main()
