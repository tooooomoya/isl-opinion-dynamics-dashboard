"""
2026-08-07 (review follow-up) -- checks whether the N_silent-control effect on the extreme camp is a
uniform shift of the whole population's posting propensity, or concentrated in a subset of agents (a
"hyper-vocal minority" effect) -- the model is explicitly designed to target the latter (Agent.java's
comment on vocalComfortRadius cites Buntain & Snegovaya 2025's hyper-vocal-minority empirical target
as the reason vcr is a fixed radius rather than dynamic bc). If so, comparing only the CAMP-AVERAGE
posting rate (everything analyzed so far this session) could dilute/mask a within-camp compositional
effect that a distributional view would reveal.

No per-agent post-COUNT field currently exists in agent_snapshot (Agent.numOfPosts was found to be a
different, unrelated static value and reverted, per the 2026-08-04 "numOfPosts dead end" report entry)
-- so this uses avgComfortRate (per-agent, trailing-100-step average, in agent_snapshot_final.csv) as
the available proxy for posting propensity (it directly drives postProb via the model's comfort->
vocality mechanism, already established this session as a close-tracking leading indicator of posting
rate). Compares full per-agent distributions (not just means) for non-hub bin0+bin4 (extreme-camp)
agents, control vs N_silent, at a few representative cells:
  - the "facilitator" cell (p_u=0.15, vcr=0.1): strongest control>N_silent effect
  - the "mediator" cell (p_u=0.15, vcr=0.3): strongest N_silent>control effect (grid's largest)
  - the near-null cell (p_u=0.15, vcr=0.2) for contrast

Reports: mean, median, std, skewness, and the fraction of agents in the top quartile of comfortRate
(a crude "hyper-vocal" indicator) for each arm, plus a Kolmogorov-Smirnov test on whether the two
arms' distributions differ (not just their means).

Usage: python3 scripts/lmp_feedmech_distribution_check.py
"""
import csv

import numpy as np
from scipy import stats

from lmp_feedmech_stage1 import SEEDS, SUBDIR, cell_name, result_dir

CELLS = [(0.15, 0.1, "facilitator (largest control>N_silent)"),
         (0.15, 0.2, "near-null crossover point"),
         (0.15, 0.3, "mediator (largest N_silent>control)")]


def per_agent_comfort(seed, subdir):
    d = result_dir(seed, subdir)
    vals = []
    with open(d / "degrees" / "agent_snapshot_final.csv", newline="") as f:
        for r in csv.DictReader(f):
            if r["isTarget"] == "0":
                op = float(r["opinion"])
                shifted = op + 1.0
                cls = min(int(shifted / 0.4), 4)
                if cls in (0, 4):
                    vals.append(float(r["avgComfortRate"]))
    return np.array(vals)


def describe(name, x):
    top_q_thresh = 0.5  # comfortRate is already a [0,1] ratio, 0.5 is a natural "high" cutoff
    frac_high = np.mean(x > top_q_thresh)
    print(f"    {name:<12} n={len(x):<5} mean={x.mean():.4f}  median={np.median(x):.4f}  "
          f"std={x.std(ddof=1):.4f}  skew={stats.skew(x):+.3f}  frac(>{top_q_thresh})={frac_high:.3f}")


def main():
    for pu, vcr, label in CELLS:
        print(f"\n=== p_u={pu} vcr={vcr}  ({label}) ===")
        ctrl_subdir = f"{SUBDIR}/{cell_name(pu, vcr)}/control"
        msil_subdir = f"{SUBDIR}/{cell_name(pu, vcr)}/N_silent"

        ctrl_all = np.concatenate([per_agent_comfort(s, ctrl_subdir) for s in SEEDS])
        msil_all = np.concatenate([per_agent_comfort(s, msil_subdir) for s in SEEDS])

        describe("control", ctrl_all)
        describe("N_silent", msil_all)

        ks_stat, ks_p = stats.ks_2samp(ctrl_all, msil_all)
        print(f"    KS test (distribution shape differs, not just mean): D={ks_stat:.4f}  p={ks_p:.5f}")

        print("    Quantiles (0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99):")
        qs = [0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99]
        cq = np.quantile(ctrl_all, qs)
        mq = np.quantile(msil_all, qs)
        print("      control:  " + "  ".join(f"{v:.3f}" for v in cq))
        print("      N_silent: " + "  ".join(f"{v:.3f}" for v in mq))
        print("      diff:     " + "  ".join(f"{v:+.3f}" for v in (mq - cq)))


if __name__ == "__main__":
    main()
