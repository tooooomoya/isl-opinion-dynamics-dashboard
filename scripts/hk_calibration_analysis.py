"""
Stage-1a HK generator calibration analysis (run_hk_calibration_sweep.sh).

Fits HolmeKimNetwork's (m, A, pt) against Kwak et al. 2010's Twitter follow-graph stylized
facts: degree-distribution power-law exponent gamma~2.276, and average local clustering
coefficient ~0.072 ("What is Twitter, a Social Network or a News Media?", WWW'10).

For each grid cell (3 seeds), reads degrees/degree_result_0.csv + clusterings/clustering_result_0.csv
from the t=0 pre-loop snapshot (pure generator output, no follow/unfollow dynamics), fits a power
law to the in-degree distribution (reusing dashboard.analysis.fit_powerlaw), and reports mean
clustering coefficient.

Usage: python3 scripts/hk_calibration_analysis.py [results_dir]
"""
import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dashboard.analysis import fit_powerlaw

RESULTS_DIR = Path(sys.argv[1] if len(sys.argv) > 1 else "results")
SEEDS = [0, 1, 2]
DEFAULT_M, DEFAULT_A, DEFAULT_PT = 3, 1, 0.3

CELLS = [
    ("m03a01", 3, 1),
    ("m05a01", 5, 1),
    ("m10a03", 10, 3),
    ("m15a04", 15, 4),
    ("m20a06", 20, 6),
    ("m25a07", 25, 7),
    ("m50a14", 50, 14),
]
PTS = [0.05, 0.1, 0.2, 0.3]

GAMMA_TARGET = 2.276     # Kwak et al. 2010
CLUSTERING_TARGET = 0.072  # Kwak et al. 2010


def tag_substr(m, a, pt):
    parts = []
    if m != DEFAULT_M:
        parts.append(f"_hkm-{m}")
    if a != DEFAULT_A:
        parts.append(f"_hka-{a}")
    if pt != DEFAULT_PT:
        parts.append(f"_hkpt-{pt:.2f}")
    return parts


def find_run(seed, m, a, pt):
    parts = tag_substr(m, a, pt)
    candidates = list(RESULTS_DIR.glob(f"run_{seed}_*_st-1"))
    for c in candidates:
        name = c.name
        if all(p in name for p in parts) and "_n-" not in name:
            # exclude accidental partial matches (e.g. hkm-10 matching hkm-100 if it existed)
            if all(re.search(re.escape(p) + r"(?:_|$)", name) for p in parts):
                return c
    return None


def read_degrees(d):
    path = d / "degrees" / "degree_result_0.csv"
    if not path.exists():
        return None
    with open(path, newline="") as f:
        return [int(row["inDegree"]) for row in csv.DictReader(f)]


def read_clustering(d):
    path = d / "clusterings" / "clustering_result_0.csv"
    if not path.exists():
        return None
    with open(path, newline="") as f:
        vals = [float(row["clusteringCoefficient"]) for row in csv.DictReader(f)]
    return sum(vals) / len(vals) if vals else None


def main():
    print(f"{'cell':<12}{'m':>4}{'A':>4}{'pt':>6}{'gamma_an':>10}"
          f"{'gamma_fit':>11}{'plausible':>11}{'clustering':>12}{'n_seeds':>9}")
    rows = []
    for name, m, a in CELLS:
        gamma_analytic = 2.0 + a / m
        for pt in PTS:
            fits, clusterings, n_ok = [], [], 0
            for seed in SEEDS:
                d = find_run(seed, m, a, pt)
                if d is None:
                    continue
                degs = read_degrees(d)
                clu = read_clustering(d)
                if degs is None or clu is None:
                    continue
                n_ok += 1
                clusterings.append(clu)
                fit = fit_powerlaw(degs)
                if "alpha" in fit:
                    fits.append(fit["alpha"])
            gamma_fit = sum(fits) / len(fits) if fits else None
            clu_mean = sum(clusterings) / len(clusterings) if clusterings else None
            plausible_frac = None
            rows.append((name, m, a, pt, gamma_analytic, gamma_fit, clu_mean, n_ok))
            print(f"{name:<12}{m:>4}{a:>4}{pt:>6.2f}{gamma_analytic:>10.3f}"
                  f"{'' if gamma_fit is None else f'{gamma_fit:>11.3f}'}"
                  f"{'':>11}"
                  f"{'' if clu_mean is None else f'{clu_mean:>12.4f}'}"
                  f"{n_ok:>9}")

    print(f"\nTargets: gamma (Kwak et al. 2010) = {GAMMA_TARGET}, "
          f"clustering (Kwak et al. 2010) = {CLUSTERING_TARGET}")

    scored = []
    for name, m, a, pt, ga, gf, clu, n_ok in rows:
        if clu is None or n_ok == 0:
            continue
        gamma_use = gf if gf is not None else ga
        loss = (gamma_use - GAMMA_TARGET) ** 2 + ((clu - CLUSTERING_TARGET) / 0.1) ** 2
        scored.append((loss, name, m, a, pt, ga, gf, clu))
    scored.sort()
    print("\nTop 5 by combined distance to (gamma, clustering) targets:")
    for loss, name, m, a, pt, ga, gf, clu in scored[:5]:
        print(f"  {name} pt={pt:.2f}  m={m} A={a}  gamma_analytic={ga:.3f} "
              f"gamma_fit={'n/a' if gf is None else f'{gf:.3f}'}  clustering={clu:.4f}  loss={loss:.4f}")


if __name__ == "__main__":
    main()
