"""
OAT robustness/calibration sweep analysis (docs/report/2026-07-08-validation-gate-pilot.md,
"OAT robustness/calibration sweep" sections).

For each of the 19 cells (baseline + 18 one-at-a-time parameter changes, 3 seeds each), computes
the Step-2 gate metrics (reusing scripts/validation_gate_pilot_analysis.py's logic) and — for the
Tier-C `alpha` cells — fits a power law to the final in-degree distribution to check against the
Kwak et al. 2010 / sbm_gamma≈2.3 target.

Usage: python3 scripts/oat_sweep_analysis.py [results_dir]
"""
import sys
import re
from pathlib import Path

import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import validation_gate_pilot_analysis as vg

RESULTS_DIR = Path(sys.argv[1] if len(sys.argv) > 1 else "results")
SEEDS = [200, 201, 202]

# Mirrors run_oat_sweep.sh's CELLS array: (cell_name, folder_tag_substring_or_None_for_baseline)
CELLS = [
    ("baseline", None),
    ("repostprob-001", "_rp-0.010"),
    ("repostprob-010", "_rp-0.100"),
    ("bcinc-0001", "_bcinc-0.0010"),
    ("bcinc-0005", "_bcinc-0.0050"),
    ("stub-06", "_stub-uniform-0.60-0.60"),
    ("stub-095", "_stub-uniform-0.95-0.95"),
    ("sbmpout-0005", "_sbmpout-0.0050"),
    ("sbmpout-001", "_sbmpout-0.0100"),
    ("alpha-03", "_a-0.30_h-3"),
    ("alpha-06", "_a-0.60_h-3"),
    ("feedcap-5", "_fc-5"),
    ("feedcap-20", "_fc-20"),
    ("followprob-005", "_folp-0.050"),
    ("followprob-02", "_folp-0.200"),
    ("comfortpp-105", "_cpf-1.050"),
    ("comfortpp-12", "_cpf-1.200"),
    ("maxpp-03", "_mxpp-0.300"),
    ("maxpp-08", "_mxpp-0.800"),
]
ALL_TAGS = [t for _, t in CELLS if t is not None]


def find_run(seed: int, tag_substr):
    # Trailing "*" matters: Tier-D knobs (feed_capacity/follow_prob/comfort_pp/max_pp) are tagged
    # AFTER "_nohost" (appended at the very end of tag()), so an end-anchored pattern misses them.
    candidates = list(RESULTS_DIR.glob(f"run_{seed}_*n-300_st-15000_nohost*"))
    if tag_substr is None:
        # Baseline: must NOT contain any other cell's distinguishing substring.
        matches = [d for d in candidates if not any(t in d.name for t in ALL_TAGS)]
    else:
        matches = [d for d in candidates if tag_substr in d.name]
    if len(matches) != 1:
        return None
    return matches[0]


def fit_powerlaw_exponent(folder: Path, step: int = 15000):
    """Fit a power law to the final in-degree distribution (powerlaw package)."""
    fp = folder / "degrees" / f"degree_result_{step}.csv"
    if not fp.exists():
        return np.nan
    df = pd.read_csv(fp)
    deg = df["inDegree"].values
    deg = deg[deg > 0]
    if len(deg) < 20:
        return np.nan
    try:
        import powerlaw
        fit = powerlaw.Fit(deg, discrete=True, verbose=False)
        return fit.power_law.alpha
    except Exception as e:
        return np.nan


def main():
    rows = []
    for cell_name, tag in CELLS:
        for seed in SEEDS:
            folder = find_run(seed, tag)
            if folder is None:
                rows.append({"cell": cell_name, "seed": seed, "found": False})
                continue
            row = {"cell": cell_name, "seed": seed, "found": True, "folder": folder.name}
            row.update(vg.gate1_plateau(folder))
            row.update(vg.gate2_hub_scale(folder))
            row.update(vg.gate3_hub_bridging(folder))
            if cell_name.startswith("alpha"):
                row["degree_powerlaw_alpha"] = fit_powerlaw_exponent(folder)
            rows.append(row)

    df = pd.DataFrame(rows)
    out_csv = Path("docs/report/2026-07-09-oat-sweep-results.csv")
    df.to_csv(out_csv, index=False)
    print(f"Wrote {len(df)} rows to {out_csv}")

    missing = df[~df.get("found", pd.Series([True] * len(df)))]
    if len(missing):
        print("\n--- MISSING RUNS ---")
        print(missing[["cell", "seed"]].to_string(index=False))

    found = df[df["found"] == True].copy()
    metric_cols = [
        "opinionAssortativity_final", "crossCuttingFraction_final",
        "interactionCrossCuttingFraction_final", "signModularity_final",
        "hub_cross_camp_fraction", "n_hub_mediated_cascades",
    ]
    metric_cols = [c for c in metric_cols if c in found.columns]
    summary = found.groupby("cell")[metric_cols].mean(numeric_only=True)
    # order: baseline first, then in CELLS order
    order = [c for c, _ in CELLS if c in summary.index]
    summary = summary.reindex(order)
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 20)
    print("\n--- Per-cell mean (over available seeds) ---")
    print(summary.to_string())

    if "degree_powerlaw_alpha" in found.columns:
        pl = found[found["cell"].str.startswith("alpha")]
        if len(pl):
            print("\n--- Tier C: final degree power-law exponent vs sbm_gamma=2.3 / Kwak et al. gamma=2.276 target ---")
            print(pl.groupby("cell")["degree_powerlaw_alpha"].agg(["mean", "std", "count"]).to_string())

    if "moderate_followers_t0" in found.columns and "moderate_followers_final" in found.columns:
        found["moderate_growth"] = found["moderate_followers_final"] - found["moderate_followers_t0"]
        print("\n--- Moderate hub follower growth (final - t0), by cell ---")
        print(found.groupby("cell")["moderate_growth"].agg(["mean", "std", "count"]).reindex(order).to_string())


if __name__ == "__main__":
    main()
