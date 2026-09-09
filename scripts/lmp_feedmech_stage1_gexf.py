"""
2026-08-06 -- PE<->E structural connectivity check (docs/report/2026-08-02-delayed-moderate-conduit-
pilot.md, "homophily/heterophily gate" discussion). Tests whether p_u acts as a STRUCTURAL homophily
gate between the pre-extreme (PE, bins 1/3) and far-extreme (E, bins 0/4) camps, complementing vcr's
already-confirmed PERCEPTUAL gate (feedComfortClass ratio, lmp_feedmech_stage1.py) -- i.e. does a
larger control-vs-N_silent gap in PE-E follow-graph connectivity show up at p_u=0.15 than p_u=0.05?

No new Java instrumentation needed: GraphVisualize.java already embeds opinionClass and target as GEXF
node attributes, so log_gexf=true is the only new token. Reuses lmp_feedmech_stage1.py's exact 8
cells/5 seeds/control+N_silent design (imported, not duplicated) but writes to its own results subdir
so Stage 1's already-analyzed v3 data isn't touched.

Usage: nohup python3 scripts/lmp_feedmech_stage1_gexf.py > logs/lmp_feedmech_stage1_gexf_stdout.log 2>&1 &
       (then disown)
"""
import concurrent.futures
import glob
import xml.etree.ElementTree as ET

import numpy as np

from lmp_feedmech_stage1 import (
    ROOT, LIBCP, BASE_TOKENS, SEEDS, CELLS, FULL_STEPS,
    cell_name, result_dir, is_done, launch, derive_groups, build_pin_token,
)

SUBDIR = "2026-08-06_lmp_feedmech_stage1_gexf"

GEXF_NS = "{http://gexf.net/1.3}"


def run_wave_gexf(jobs, max_workers=20):
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = []
        for seed, steps, subdir, tokens in jobs:
            if is_done(seed, subdir, steps):
                print(f"  seed={seed} subdir={subdir}: reusing existing", flush=True)
                continue
            futs.append(ex.submit(lambda s=seed, st=steps, sd=subdir, tk=tokens:
                                   launch(s, st, sd, tk, log_gexf=True).wait()))
        for f in futs:
            f.result()


def parse_gexf_classes_and_edges(path):
    """Returns (opinionclass_by_id: dict[str,int], is_target_by_id: dict[str,bool],
    edges: list[(source_id, target_id)]) for one GEXF snapshot."""
    tree = ET.parse(path)
    root = tree.getroot()
    graph = root.find(f"{GEXF_NS}graph")
    opinionclass, is_target = {}, {}
    for node in graph.find(f"{GEXF_NS}nodes"):
        nid = node.get("id")
        cls, tgt = None, False
        attvalues = node.find(f"{GEXF_NS}attvalues")
        if attvalues is not None:
            for av in attvalues:
                if av.get("for") == "opinionclass":
                    cls = int(av.get("value"))
                elif av.get("for") == "target":
                    tgt = av.get("value") == "true"
        opinionclass[nid] = cls
        is_target[nid] = tgt
    edges = [(e.get("source"), e.get("target")) for e in graph.find(f"{GEXF_NS}edges")]
    return opinionclass, is_target, edges


def final_gexf_path(seed, subdir, checkpoint=FULL_STEPS):
    d = result_dir(seed, subdir)
    cands = glob.glob(str(d / "GEXF" / "*" / f"step_{checkpoint}.gexf"))
    if not cands:
        raise FileNotFoundError(f"no step_{checkpoint}.gexf under {d}/GEXF")
    return cands[0]


def cross_class_density(seed, subdir, class_a, class_b, checkpoint=FULL_STEPS):
    """Directed density of edges FROM class_a members TO class_b members (source follows target),
    non-hub (target attr False) only. Returns (density, |A|, |B|, edge_count)."""
    path = final_gexf_path(seed, subdir, checkpoint)
    cls, tgt, edges = parse_gexf_classes_and_edges(path)
    A = {n for n, c in cls.items() if c == class_a and not tgt[n]}
    B = {n for n, c in cls.items() if c == class_b and not tgt[n]}
    if not A or not B:
        return float("nan"), len(A), len(B), 0
    count = sum(1 for s, t in edges if s in A and t in B)
    return count / (len(A) * len(B)), len(A), len(B), count


def report_cell(pu, vcr):
    ctrl_subdir = f"{SUBDIR}/{cell_name(pu, vcr)}/control"
    msil_subdir = f"{SUBDIR}/{cell_name(pu, vcr)}/N_silent"

    print(f"\n--- p_u={pu} vcr={vcr} ---")
    for label, ca, cb in (("E- -> PE- (0->1)", 0, 1), ("E+ -> PE+ (4->3)", 4, 3)):
        c_vals = [cross_class_density(s, ctrl_subdir, ca, cb)[0] for s in SEEDS]
        m_vals = [cross_class_density(s, msil_subdir, ca, cb)[0] for s in SEEDS]
        c = np.array(c_vals); m = np.array(m_vals)
        diff = m - c
        print(f"    {label}: control={c.mean():.5f}  N_silent={m.mean():.5f}  diff={diff.mean():+.5f}")


def main():
    print("=== Deriving hub-tier groups (reused shared HK class-selection) ===", flush=True)
    groups_by_seed = {s: derive_groups(s) for s in SEEDS}

    print(f"\n=== Launching control + N_silent (log_gexf=true) at {len(CELLS)} cells x {len(SEEDS)} seeds ===", flush=True)
    jobs = []
    for pu, vcr in CELLS:
        for s in SEEDS:
            groups = groups_by_seed[s]
            pin_token = build_pin_token(groups)
            base = [pin_token, f"p_u={pu}", f"vocal_comfort_radius={vcr}"]
            jobs.append((s, FULL_STEPS, f"{SUBDIR}/{cell_name(pu, vcr)}/control", base))
            m_ids = groups["M"][0]
            idstr = ",".join(str(a) for a in m_ids)
            msil_tokens = base + [f"silent_until_ids={idstr}", f"activation_step={FULL_STEPS + 1}"]
            jobs.append((s, FULL_STEPS, f"{SUBDIR}/{cell_name(pu, vcr)}/N_silent", msil_tokens))
    run_wave_gexf(jobs, max_workers=20)

    print("\n=== PE<->E directed follow-edge density (source follows target), control vs N_silent ===")
    print("Prediction under test: the control-vs-N_silent gap should be bigger at p_u=0.15 than p_u=0.05")
    print("if p_u acts as a structural homophily gate (docs/report 2026-08-06 discussion).")
    for pu, vcr in CELLS:
        report_cell(pu, vcr)


if __name__ == "__main__":
    main()
