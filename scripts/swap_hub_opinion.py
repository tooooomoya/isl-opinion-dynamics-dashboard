"""
Moderate-vs-extreme hub swap (2026-07-20): the decisive causal test named in research-direction.md's
own DAG ("degree-matched rewiring without a moderate conduit -- is it the bridge, or just the
exposure?") -- here done even more surgically: SAME hub, SAME network, only its opinion changes.

Takes a control-run GEXF snapshot (network + all agents' state at equilibrium) and writes a copy
with exactly one node's opinion attribute overwritten. Everything else (edges, all other 999
agents' opinion/bc/postProb/accessProb) is byte-identical. Feed the two files to `network=read` as
the starting point for two continuation runs -- topology and every other agent's state are
provably identical at t=0; the ONLY difference is the target hub's opinion.

Usage: python3 scripts/swap_hub_opinion.py <src.gexf> <dst.gexf> <agent_id> <new_opinion>
"""
import sys

GEXF_NS = "http://gexf.net/1.3"


def swap_opinion(src_path, dst_path, agent_id, new_opinion):
    import xml.etree.ElementTree as ET
    ET.register_namespace("", GEXF_NS)
    ns = {"g": GEXF_NS}
    tree = ET.parse(src_path)
    root = tree.getroot()

    attr_id = None
    for attrs in root.iter(f"{{{GEXF_NS}}}attributes"):
        for a in attrs.iter(f"{{{GEXF_NS}}}attribute"):
            if a.get("title") == "opinion":
                attr_id = a.get("id")
    if attr_id is None:
        raise RuntimeError("no 'opinion' attribute definition found in GEXF")

    found = False
    for node in root.iter(f"{{{GEXF_NS}}}node"):
        if node.get("id") != str(agent_id):
            continue
        for av in node.iter(f"{{{GEXF_NS}}}attvalue"):
            if av.get("for") == attr_id:
                old = av.get("value")
                av.set("value", str(new_opinion))
                print(f"agent {agent_id}: opinion {old} -> {new_opinion}")
                found = True
    if not found:
        raise RuntimeError(f"agent {agent_id} or its opinion attvalue not found in {src_path}")

    tree.write(dst_path, xml_declaration=True, encoding="UTF-8")
    print(f"wrote {dst_path}")


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print(__doc__)
        sys.exit(1)
    swap_opinion(sys.argv[1], sys.argv[2], int(sys.argv[3]), float(sys.argv[4]))
