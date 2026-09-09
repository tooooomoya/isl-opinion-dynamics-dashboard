"""
2026-08-15 -- correction pass over lmp_feedmech_chamber_gate.py's Layer-2 (network-side) chamber
measures, which are contaminated by an artifact of the treatment itself.

THE ARTIFACT. Silencing the moderate hubs does not merely stop their content: because unfollow is
triggered only by an out-of-tolerance ENCOUNTER (Agent.java:619-643), a hub that posts nothing is
never encountered and therefore never purged. Extreme-camp readers consequently retain ~3.26 moderate
hubs under N_silent versus ~0.01-0.10 under control (lmp_feedmech_followee_composition.py). Those
retained ties are INERT -- verified here: moderate hubs' postProb is 0.966 under control but 0.010
under N_silent -- yet every unweighted network measure counts them at full strength. Both Layer-2
measures are affected, and, revealingly, in OPPOSITE directions:
  - src_overlap_third rises under N_silent (+0.45), because both camps retain the same inert hubs and
    thus appear to share an information environment they are not actually sharing.
  - louvain_comembership FALLS under N_silent (-0.11), because those same inert ties pull extreme
    agents into moderate-hub-centred communities and away from the near-extreme camp.
Two measures of "same chamber" moving in opposite directions under the same treatment is a symptom,
not a finding: both are reading tie topology that carries no information flow.

THE FIX. Weight every tie by the actual content-emitting activity of the author it points to, using
postProb as the activity measure (validated above: it separates active from silenced hubs by ~100x).
An inert tie then contributes ~nothing, and the measures describe the EFFECTIVE information
environment rather than the nominal graph. Reported alongside the unweighted originals so the size of
the artifact is visible rather than silently corrected away.

Also adds a purely structural control, `src_overlap_pop`: overlap restricted to NON-HUB authors
outside both camps. This removes the moderate hubs by construction rather than by weighting, as an
independent check that the weighted result is not an artifact of the weighting scheme itself.

Usage: nohup python3 -u scripts/lmp_feedmech_chamber_gate_wt.py > logs/chamber_gate_wt.log 2>&1 & disown
"""
import json
import xml.etree.ElementTree as ET

import networkx as nx
import numpy as np

from lmp_feedmech_stage1 import SEEDS, result_dir
from lmp_feedmech_structural_9b import SUBDIR, CELLS, cell_name, GEXF_NS
from lmp_feedmech_chamber_gate import gexf_path, CHECKPOINTS, ARMS

SIGN_PAIRS = ((0, 1), (4, 3))


def parse_full(path):
    root = ET.parse(path).getroot()
    graph = root.find(f"{GEXF_NS}graph")
    cls, tgt, pp = {}, {}, {}
    for node in graph.find(f"{GEXF_NS}nodes"):
        nid = node.get("id")
        c, t, p = None, False, 0.0
        av_parent = node.find(f"{GEXF_NS}attvalues")
        if av_parent is not None:
            for av in av_parent:
                k, v = av.get("for"), av.get("value")
                if k == "opinionclass":
                    c = int(v)
                elif k == "target":
                    t = (v == "true")
                elif k == "postprob":
                    p = float(v)
        cls[nid], tgt[nid], pp[nid] = c, t, p
    edges = [(e.get("source"), e.get("target")) for e in graph.find(f"{GEXF_NS}edges")]
    return cls, tgt, pp, edges


def cosine(a, b):
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    return float(a @ b / (na * nb)) if na > 0 and nb > 0 else float("nan")


def compute(path):
    cls, tgt, pp, edges = parse_full(path)
    pop = [n for n in cls if not tgt[n]]
    by_class = {c: [n for n in pop if cls[n] == c] for c in range(5)}
    e_all = set(by_class[0]) | set(by_class[4])
    ne_all = set(by_class[1]) | set(by_class[3])
    if not e_all or not ne_all:
        return None

    authors = sorted({t for _, t in edges})
    idx = {a: i for i, a in enumerate(authors)}
    vE = np.zeros(len(authors))
    vNE = np.zeros(len(authors))
    for s, t in edges:
        if s in e_all:
            vE[idx[t]] += 1
        elif s in ne_all:
            vNE[idx[t]] += 1

    third = np.array([(a not in e_all and a not in ne_all) for a in authors], dtype=float)
    act = np.array([pp.get(a, 0.0) for a in authors])          # activity weight
    pop_third = np.array([(a not in e_all and a not in ne_all and not tgt.get(a, False))
                          for a in authors], dtype=float)

    out = {
        "src_overlap_third": cosine(vE * third, vNE * third),
        "src_overlap_third_wt": cosine(vE * third * act, vNE * third * act),
        "src_overlap_pop": cosine(vE * pop_third, vNE * pop_third),
    }

    # Louvain on the activity-weighted graph: an edge's weight is how much content it actually carries
    Gw = nx.Graph()
    Gw.add_nodes_from(cls.keys())
    for s, t in edges:
        w = pp.get(t, 0.0)
        if w <= 0:
            continue
        if Gw.has_edge(s, t):
            Gw[s][t]["weight"] += w
        else:
            Gw.add_edge(s, t, weight=w)
    try:
        comms = nx.community.louvain_communities(Gw, weight="weight", seed=0)
        cm = {n: i for i, c in enumerate(comms) for n in c}
        co = tot = 0
        for e_cls, ne_cls in SIGN_PAIRS:
            for i in by_class[e_cls]:
                ci = cm.get(i)
                for j in by_class[ne_cls]:
                    tot += 1
                    if ci is not None and ci == cm.get(j):
                        co += 1
        out["louvain_comembership_wt"] = co / tot if tot else float("nan")
        out["louvain_Q_wt"] = float(nx.community.modularity(Gw, comms, weight="weight"))
    except Exception:
        out["louvain_comembership_wt"] = float("nan")
        out["louvain_Q_wt"] = float("nan")
    return out


KEYS = ("src_overlap_third", "src_overlap_third_wt", "src_overlap_pop",
        "louvain_comembership_wt", "louvain_Q_wt")

LABELS = {
    "src_overlap_third": "UNWEIGHTED shared third-party sources (contaminated -- shown for contrast)",
    "src_overlap_third_wt": "ACTIVITY-WEIGHTED shared third-party sources (inert ties ~ 0)",
    "src_overlap_pop": "shared NON-HUB third-party sources (hubs excluded structurally)",
    "louvain_comembership_wt": "Louvain co-membership on the activity-weighted graph",
    "louvain_Q_wt": "Louvain modularity Q on the activity-weighted graph",
}


def cached(seed, subdir):
    d = result_dir(seed, subdir)
    cp = d / "chamber_gate_wt.json"
    if cp.exists():
        return json.loads(cp.read_text())
    out = {}
    for step in CHECKPOINTS:
        p = gexf_path(seed, subdir, step)
        out[str(step)] = compute(p) if p is not None else None
    cp.write_text(json.dumps(out))
    return out


def main():
    data = {}
    for pu, vcr in CELLS:
        for arm in ARMS:
            subdir = f"{SUBDIR}/{cell_name(pu, vcr)}/{arm}"
            print(f"  {subdir} ...", flush=True)
            per_seed = [cached(s, subdir) for s in SEEDS]
            for step in CHECKPOINTS:
                vals = [ps[str(step)] for ps in per_seed if ps.get(str(step))]
                if vals:
                    data[(pu, vcr, arm, step)] = {
                        k: float(np.nanmean([v[k] for v in vals])) for k in KEYS
                    }

    print("\nSame-sign camp pairs (E-/NE-, E+/NE+), non-hub agents, mean over 15 seeds.\n")
    for key in KEYS:
        print("=" * 108)
        print(f"{key}  --  {LABELS[key]}")
        print("=" * 108)
        for vcr in (0.1, 0.15, 0.2):
            print(f"  vcr={vcr}")
            print(f"    {'step':>12s}" + "".join(f"{s:>12d}" for s in CHECKPOINTS))
            for pu in (0.05, 0.15):
                for arm in ARMS:
                    vals = [data.get((pu, vcr, arm, s), {}).get(key, np.nan) for s in CHECKPOINTS]
                    print(f"    p_u={pu} {arm:9s}" + "".join(f"{v:>12.4f}" for v in vals))
                diffs = [data.get((pu, vcr, 'N_silent', s), {}).get(key, np.nan) -
                         data.get((pu, vcr, 'control', s), {}).get(key, np.nan) for s in CHECKPOINTS]
                print(f"    p_u={pu} {'DIFF':9s}" + "".join(f"{v:>+12.4f}" for v in diffs))
            print()


if __name__ == "__main__":
    main()
