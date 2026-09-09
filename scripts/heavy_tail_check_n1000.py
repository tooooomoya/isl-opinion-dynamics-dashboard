"""
Heavy-tail check at n=1000 (docs/report/2026-07-09-oat-sweep-findings.md follow-up).

Question: does the recommender (alpha) collapse the degree distribution's heavy tail (a real
Type-1/Type-2 validity concern, per research-direction.md's scale-free-dependency hypothesis) —
checked directly on the whole-network degree distribution, not via a single hub's follower count
(too noisy/narrow, per the 2026-07-09 correction). Uses two metrics that don't share the same
failure mode: a power-law MLE fit (alpha exponent, sensitive to fitting procedure/xmin) and the
Gini coefficient of the degree distribution (assumption-free concentration measure).

Usage: python3 scripts/heavy_tail_check_n1000.py
"""
import glob
from pathlib import Path

import pandas as pd
import numpy as np

RESULTS_DIR = Path("results")
CELLS = ["n1000-baseline", "n1000-alpha-03", "n1000-alpha-06"]
SEEDS = [300, 301, 302, 303, 304]


def gini(x):
    x = np.sort(np.asarray(x, dtype=float))
    n = len(x)
    if n == 0 or x.sum() == 0:
        return np.nan
    cum = np.cumsum(x)
    return (2 * np.sum((np.arange(1, n + 1)) * x) - (n + 1) * cum[-1]) / (n * cum[-1])


def find_folder(cellname, seed):
    tag_map = {
        "n1000-baseline": "",
        "n1000-alpha-03": "_a-0.30_h-3",
        "n1000-alpha-06": "_a-0.60_h-3",
    }
    tag = tag_map[cellname]
    # n=1000 is Const.NUM_OF_USER (the default), so tag() never appends "_n-1000".
    pattern = f"run_{seed}_*st-15000_nohost*"
    candidates = [Path(p) for p in glob.glob(str(RESULTS_DIR / pattern))]
    if tag == "":
        candidates = [c for c in candidates if "_a-0." not in c.name]
    else:
        candidates = [c for c in candidates if tag in c.name]
    if len(candidates) != 1:
        return None
    return candidates[0]


def fit_powerlaw(deg):
    deg = deg[deg > 0]
    if len(deg) < 20:
        return np.nan
    try:
        import powerlaw
        fit = powerlaw.Fit(deg, discrete=True, verbose=False)
        return fit.power_law.alpha
    except Exception:
        return np.nan


def main():
    rows = []
    for cell in CELLS:
        for seed in SEEDS:
            folder = find_folder(cell, seed)
            if folder is None:
                rows.append({"cell": cell, "seed": seed, "found": False})
                continue
            row = {"cell": cell, "seed": seed, "found": True}
            for label, step in [("t0", 0), ("final", 15000)]:
                fp = folder / "degrees" / f"degree_result_{step}.csv"
                if not fp.exists():
                    continue
                df = pd.read_csv(fp)
                deg = df["inDegree"].values
                row[f"powerlaw_alpha_{label}"] = fit_powerlaw(deg)
                row[f"gini_{label}"] = gini(deg)
                row[f"maxdeg_{label}"] = deg.max()
                row[f"meandeg_{label}"] = deg.mean()
                row[f"stddeg_{label}"] = deg.std()
            rows.append(row)

    df = pd.DataFrame(rows)
    out = Path("docs/report/2026-07-09-heavy-tail-n1000-results.csv")
    df.to_csv(out, index=False)
    print(f"Wrote {len(df)} rows to {out}")

    missing = df[df.get("found", pd.Series([True] * len(df))) == False]
    if len(missing):
        print("MISSING:", missing[["cell", "seed"]].to_string(index=False))

    found = df[df["found"] == True]
    cols = [c for c in found.columns if c not in ("cell", "seed", "found")]
    pd.set_option("display.width", 200)
    print("\n=== mean (5 seeds) ===")
    print(found.groupby("cell")[cols].mean(numeric_only=True).to_string())
    print("\n=== std (5 seeds) ===")
    print(found.groupby("cell")[cols].std(numeric_only=True).to_string())


if __name__ == "__main__":
    main()
