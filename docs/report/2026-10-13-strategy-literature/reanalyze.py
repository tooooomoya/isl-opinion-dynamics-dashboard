"""Read existing search outputs; no simulations or model changes.

Snapshot Qs average nine states. Their winners/ranges are diagnostics of that
average, NOT reconstructed policies. state_action.csv contains population Qs.
"""
import csv
import hashlib
import json
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
SOURCE = ROOT / "results/search/summary.jsonl"


def rows(path):
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def main():
    output = []
    inputs = {str(SOURCE.relative_to(ROOT)): hashlib.sha256(SOURCE.read_bytes()).hexdigest()}
    for line in SOURCE.read_text().splitlines():
        run = json.loads(line)
        if run.get("status") != "ok":
            continue
        candidates = list((ROOT / "results/search" / run["id"]).glob(f"run_{run['seed']}_*/metrics/state_action.csv"))
        if len(candidates) != 1:
            continue
        sa_path = candidates[0]
        snap_path = sa_path.parent.parent / "degrees/agent_snapshot_final.csv"
        sa = rows(sa_path)
        final_step = max(int(r["step"]) for r in sa)
        active = [r for r in sa if int(r["step"]) == final_step and r["action"] == "post"]
        visits = sum(int(r["visits_in_state"]) for r in active)
        high_fit = sum(int(r["visits_in_state"]) for r in active if int(r["fit_level"]) == 2)
        counts = [int(r["visits_in_state"]) for r in active]
        actions = ["Post", "Like", "Reshare"] + (["Rewire"] if run["tokens"].get("rewire") == "true" else [])
        snap = [r for r in rows(snap_path) if r["isTarget"] == "0"]
        winners = {a: 0 for a in actions}
        gaps = []
        for r in snap:
            q = [float(r["q" + a]) for a in actions]
            gaps.append(max(q) - min(q))
            # Ties split mass equally, avoiding an artificial preference for POST.
            best = [a for a, v in zip(actions, q) if v == max(q)]
            for a in best:
                winners[a] += 1 / len(best)
        tau = float(run["tokens"].get("q_tau", "0.1"))
        output.append({
            "key": run["key"], "id": run["id"], "seed": run["seed"],
            "population_q_gap": run["qGap"], "population_q_rel_gap": run["qRelGap"],
            "population_q_gap_over_tau_proxy": run["qGap"] / tau,
            "snapshot_state_averaged_agent_gap": mean(gaps),
            "snapshot_state_averaged_agent_gap_over_tau_proxy": mean(gaps) / tau,
            "high_fit_visit_share_final_window": high_fit / visits if visits else None,
            "most_visited_state_share_final_window": max(counts) / visits if visits else None,
            "visited_states_final_window": sum(c > 0 for c in counts),
            "snapshot_state_averaged_post_winner_share": winners["Post"] / len(snap),
            "snapshot_state_averaged_like_winner_share": winners["Like"] / len(snap),
            "snapshot_state_averaged_reshare_winner_share": winners["Reshare"] / len(snap),
            "q_table_available": (snap_path.parent / "q_table_final.csv").exists(),
        })
        for p in (sa_path, snap_path):
            inputs[str(p.relative_to(ROOT))] = hashlib.sha256(p.read_bytes()).hexdigest()
    with (OUT / "existing-run-diagnostics.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(output[0]))
        writer.writeheader()
        writer.writerows(output)
    sources = ["src/agent/Agent.java", "src/dynamics/OpinionDynamics.java", "scripts/attention_search.py"]
    for name in sources:
        inputs[name] = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
    (OUT / "input-hashes.json").write_text(json.dumps(inputs, indent=2) + "\n")
    for mode in ("chrono", "T1", "T4", "F1", "F2", "F4", "M"):
        group = [r for r in output if r["id"].startswith("s1_" + mode + "_")]
        print(mode, "runs=", len(group), json.dumps({
            name: round(mean(r[name] for r in group), 4)
            for name in ("population_q_gap_over_tau_proxy", "snapshot_state_averaged_agent_gap_over_tau_proxy", "high_fit_visit_share_final_window", "most_visited_state_share_final_window", "snapshot_state_averaged_post_winner_share", "snapshot_state_averaged_like_winner_share", "snapshot_state_averaged_reshare_winner_share")
        }))
    print("Analyzed", len(output), "runs; individual state Q tables available:", sum(r["q_table_available"] for r in output))


if __name__ == "__main__":
    main()
