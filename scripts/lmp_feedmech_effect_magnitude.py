"""
2026-08-07 (review follow-up) -- contextualizes the N_silent-control posting-rate DIFF values quoted
throughout this session (e.g. -0.014 to +0.048) against the actual BASELINE posting rate, so the
effect can be read as a percentage/relative change and in more intuitive units (posts per agent per
1000 steps), not just a raw per-step-probability difference that's hard to eyeball on its own.

"rate" here = extreme_post_total (bin0+bin4 ORIGINAL posts in the trailing 2000-step window) /
(windowed non-hub bin0+bin4 population) / WINDOW -- i.e. the per-agent-per-step probability that an
extreme-camp agent authors an original post, matching exactly what per_seed_rate_contrast /
report_cell() already compute, just also printing the absolute levels (not only the arm difference).

Usage: python3 scripts/lmp_feedmech_effect_magnitude.py
"""
import numpy as np

from lmp_feedmech_stage1 import SEEDS, SUBDIR, cell_name, extreme_post_total, pop_counts_nonhub_windowed, WINDOW

PU_LEVELS = (0.05, 0.15)
VCR_LEVELS = (0.1, 0.15, 0.2, 0.3)


def rates(pu, vcr):
    ctrl_subdir = f"{SUBDIR}/{cell_name(pu, vcr)}/control"
    msil_subdir = f"{SUBDIR}/{cell_name(pu, vcr)}/N_silent"
    ctrl_rates, msil_rates = [], []
    for s in SEEDS:
        c_n = pop_counts_nonhub_windowed(s, ctrl_subdir)
        m_n = pop_counts_nonhub_windowed(s, msil_subdir)
        c_rate = extreme_post_total(s, ctrl_subdir) / (c_n[0] + c_n[4]) / WINDOW
        m_rate = extreme_post_total(s, msil_subdir) / (m_n[0] + m_n[4]) / WINDOW
        ctrl_rates.append(c_rate)
        msil_rates.append(m_rate)
    return np.array(ctrl_rates), np.array(msil_rates)


def main():
    print(f"{'cell':<16}{'control_rate':>14}{'N_silent_rate':>14}{'diff':>10}{'%_of_control':>14}"
          f"{'posts/agent/1000steps(ctrl)':>30}{'posts/agent/1000steps(diff)':>30}")
    for pu in PU_LEVELS:
        for vcr in VCR_LEVELS:
            c, m = rates(pu, vcr)
            cr, mr = c.mean(), m.mean()
            diff = mr - cr
            pct = 100 * diff / cr
            print(f"p_u={pu} vcr={vcr:<6}{cr:>14.5f}{mr:>14.5f}{diff:>+10.5f}{pct:>+13.1f}%"
                  f"{cr*1000:>30.2f}{diff*1000:>+30.2f}")

    print("\nFor reference: access_prob=0.1 means each agent's turn (incl. the postProb roll) executes")
    print("~once every 10 steps on average, so 'rate' above is already an unconditional per-step")
    print("posting probability averaged over that access gating -- it is directly comparable across")
    print("cells/arms since access_prob is identical (0.1) everywhere in this design.")


if __name__ == "__main__":
    main()
