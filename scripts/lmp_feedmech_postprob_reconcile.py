"""
2026-08-07 (review follow-up) -- reconciles the facilitator-cell (p_u=0.15, vcr=0.1) puzzle: a large
posting-RATE effect (established d=-1.049, control > N_silent, -7.8% relative) coexists with an
essentially-zero per-agent avgComfortRate distributional difference at the final snapshot (Mann-
Whitney p=0.880). avgComfortRate is only a proximate INPUT to postProb (via a relaxation/leaky-
integrator update, Agent.java: postProb += postProbRelaxRate*(targetPostProb-postProb)) -- postProb
itself is the actual quantity gating whether an agent attempts to post, and it LAGS comfortRate rather
than tracking it instantaneously. If comfortRate diverged between arms earlier in the run and later
re-converged, postProb (having partially "locked in" the earlier divergence) could still differ at the
final checkpoint even though comfortRate no longer does -- this would reconcile the puzzle rather than
indicate a measurement bug.

postProb is available as a GEXF node attribute (GraphVisualize.java) at every 5000-step checkpoint
(0,5000,...,40000) in results/2026-08-06_lmp_feedmech_stage1_gexf/ -- no new simulation needed. This
script tracks postProb's full trajectory (not just the final step) for non-hub bin0/4 agents, control
vs N_silent, in the facilitator cell, and cross-checks against opinionclass membership at each
checkpoint (to see whether population composition churn is a contributing factor).

Usage: python3 scripts/lmp_feedmech_postprob_reconcile.py
"""
import xml.etree.ElementTree as ET

import numpy as np
from scipy import stats

from lmp_feedmech_stage1 import SEEDS, cell_name
from lmp_feedmech_stage1_gexf import SUBDIR as GEXF_SUBDIR
from lmp_feedmech_stage1 import result_dir

GEXF_NS = "{http://gexf.net/1.3}"
CHECKPOINTS = [0, 5000, 10000, 15000, 20000, 25000, 30000, 35000, 40000]
PU, VCR = 0.15, 0.1


def parse_postprob_and_class(path):
    tree = ET.parse(path)
    root = tree.getroot()
    graph = root.find(f"{GEXF_NS}graph")
    postprob, opclass, tgt = {}, {}, {}
    for node in graph.find(f"{GEXF_NS}nodes"):
        nid = node.get("id")
        pp, cls, t = None, None, False
        attvalues = node.find(f"{GEXF_NS}attvalues")
        if attvalues is not None:
            for av in attvalues:
                f = av.get("for")
                if f == "postprob":
                    pp = float(av.get("value"))
                elif f == "opinionclass":
                    cls = int(av.get("value"))
                elif f == "target":
                    t = av.get("value") == "true"
        postprob[nid] = pp
        opclass[nid] = cls
        tgt[nid] = t
    return postprob, opclass, tgt


def gexf_path(seed, subdir, checkpoint):
    d = result_dir(seed, subdir)
    import glob
    cands = glob.glob(str(d / "GEXF" / "lambda_0.0" / f"step_{checkpoint}.gexf"))
    return cands[0] if cands else None


def bin04_postprob(seed, subdir, checkpoint):
    p = gexf_path(seed, subdir, checkpoint)
    if p is None:
        return np.array([]), 0
    postprob, opclass, tgt = parse_postprob_and_class(p)
    vals = [postprob[n] for n in postprob if opclass[n] in (0, 4) and not tgt[n]]
    n_total_bin04 = sum(1 for n in opclass if opclass[n] in (0, 4) and not tgt[n])
    return np.array(vals), n_total_bin04


def main():
    ctrl_subdir = f"{GEXF_SUBDIR}/{cell_name(PU, VCR)}/control"
    msil_subdir = f"{GEXF_SUBDIR}/{cell_name(PU, VCR)}/N_silent"

    print(f"=== p_u={PU} vcr={VCR} (facilitator cell) -- postProb trajectory, bin0/4 non-hub agents ===")
    print(f"{'step':>7}{'ctrl_mean_pp':>14}{'msil_mean_pp':>14}{'diff':>10}{'MW_p':>12}{'ctrl_n':>9}{'msil_n':>9}")
    for cp in CHECKPOINTS:
        c_all, m_all = [], []
        c_n_pop, m_n_pop = [], []
        for s in SEEDS:
            cv, cn = bin04_postprob(s, ctrl_subdir, cp)
            mv, mn = bin04_postprob(s, msil_subdir, cp)
            c_all.append(cv)
            m_all.append(mv)
            c_n_pop.append(cn)
            m_n_pop.append(mn)
        c_all = np.concatenate(c_all)
        m_all = np.concatenate(m_all)
        if len(c_all) > 1 and len(m_all) > 1:
            _, p = stats.mannwhitneyu(m_all, c_all, alternative="two-sided")
        else:
            p = float("nan")
        print(f"{cp:>7}{c_all.mean():>14.4f}{m_all.mean():>14.4f}{m_all.mean()-c_all.mean():>+10.4f}"
              f"{p:>12.2e}{np.mean(c_n_pop):>9.1f}{np.mean(m_n_pop):>9.1f}")


if __name__ == "__main__":
    main()
