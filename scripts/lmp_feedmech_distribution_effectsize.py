"""
2026-08-07 (review follow-up) -- adds formal effect sizes to lmp_feedmech_distribution_check.py's
distributional comparison. Cohen's d is reported for reference but flagged as questionable given the
extreme bimodality (spikes at 0 and 1) already found -- a rank-based, distribution-free effect size
(Mann-Whitney U -> rank-biserial correlation, equivalent to 2*CLES-1 where CLES = P(N_silent draw >
control draw)) is more appropriate and is the primary number reported.

Usage: python3 scripts/lmp_feedmech_distribution_effectsize.py
"""
import numpy as np
from scipy import stats

from lmp_feedmech_distribution_check import CELLS, per_agent_comfort
from lmp_feedmech_stage1 import SEEDS, SUBDIR, cell_name


def main():
    for pu, vcr, label in CELLS:
        print(f"\n=== p_u={pu} vcr={vcr}  ({label}) ===")
        ctrl_subdir = f"{SUBDIR}/{cell_name(pu, vcr)}/control"
        msil_subdir = f"{SUBDIR}/{cell_name(pu, vcr)}/N_silent"
        c = np.concatenate([per_agent_comfort(s, ctrl_subdir) for s in SEEDS])
        m = np.concatenate([per_agent_comfort(s, msil_subdir) for s in SEEDS])

        pooled_sd = np.sqrt(((len(c) - 1) * c.var(ddof=1) + (len(m) - 1) * m.var(ddof=1)) / (len(c) + len(m) - 2))
        cohens_d = (m.mean() - c.mean()) / pooled_sd

        u, p = stats.mannwhitneyu(m, c, alternative="two-sided")
        cles = u / (len(m) * len(c))          # P(random N_silent draw > random control draw)
        rank_biserial = 2 * cles - 1           # -1..+1, 0 = no effect

        frac_c = np.mean(c > 0.5)
        frac_m = np.mean(m > 0.5)
        # effect size for the binary ">0.5" comparison: odds-ratio-adjacent, use simple risk difference + Cohen's h
        h = 2 * np.arcsin(np.sqrt(frac_m)) - 2 * np.arcsin(np.sqrt(frac_c))

        print(f"    Cohen's d (mean-based, CAUTION: distribution is bimodal, not normal): {cohens_d:+.3f}")
        print(f"    Mann-Whitney U p={p:.2e}   CLES (P(N_silent>control))={cles:.3f}   rank-biserial r={rank_biserial:+.3f}")
        print(f"    frac(comfortRate>0.5): control={frac_c:.3f}  N_silent={frac_m:.3f}  diff={frac_m-frac_c:+.3f}"
              f"   Cohen's h={h:+.3f}")
        print("    Quantile-level shift (the actual location of the effect):")
        for q in (0.25, 0.5, 0.75):
            cq, mq = np.quantile(c, q), np.quantile(m, q)
            print(f"      Q{int(q*100)}: control={cq:.3f}  N_silent={mq:.3f}  diff={mq-cq:+.3f}")


if __name__ == "__main__":
    main()
