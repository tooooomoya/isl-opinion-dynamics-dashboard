#!/usr/bin/env python3
"""Isolated, resumable eta comparison for the existing k=20 stateless bandit.

No model equations change. A frozen source copy receives read-only diagnostics.
Run: python3 scripts/eta_noise_compare.py --parallel 9
Analysis only: python3 scripts/eta_noise_compare.py --analyze
Raw outputs and the complete source snapshot live in results/eta_noise_compare/.
"""
import argparse
import concurrent.futures
import csv
import hashlib
import json
import math
import statistics
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/eta_noise_compare"
LOG = ROOT / "logs/eta_noise_compare"
ACTS = ["post", "like", "reshare"]
ETAS = [0.1, 0.03, 0.01]
TOKENS = dict(steps="20000", log_repost_cascade="false", log_gexf="false",
              log_post_lifespan="false", q_tau="0.1", l_ref="1000",
              i_edge_lo="0.63", i_edge_hi="0.71", rewire="false", network="hk",
              dead_after="200", trend_share="0", foryou_share="1.0", foryou_hop="5",
              w_fit="20", w_rec="20", recog_mix="0.5", recog_lambda="2",
              q_init="40", learner="bandit", rho_l="0.3", rho_r="0.3", fy_beta="10")

DIAGNOSTICS = r'''package agent;
import java.nio.file.*;
import java.io.IOException;
import java.util.*;
/** Observations only: consumes no RNG and never changes agent state or Q. */
public final class EtaDiagnostics {
    private static final TreeMap<Integer, double[]> rows = new TreeMap<>();
    private static final HashMap<Integer, Integer> previousBest = new HashMap<>();
    // visits, switches, comparable, then 3x (nR,sumR,sumR2,sumQ,sumQ2),
    // followed by 3x (sumGap,sumGap2). Q/gap samples require all three actions offered.
    private static double[] row(int id) { return rows.computeIfAbsent(id, k -> new double[24]); }
    public static void reward(int id, int action, double r) {
        if (action >= 3) return;
        double[] d = row(id); int j = 3 + action * 5;
        d[j]++; d[j+1] += r; d[j+2] += r*r;
    }
    public static void choice(int id, double[] q, boolean[] ok) {
        if (!(ok[0] && ok[1] && ok[2])) return;
        double[] d = row(id); d[0]++;
        int best = 0;
        for (int a=1; a<3; a++) if(q[a]>q[best]) best=a;
        Integer old = previousBest.put(id, best);
        if (old != null) { d[2]++; if(old != best) d[1]++; }
        for(int a=0; a<3; a++) { int j=3+a*5; d[j+3]+=q[a]; d[j+4]+=q[a]*q[a]; }
        double[] gaps = {q[0]-q[1], q[2]-q[1], q[0]-q[2]};
        for(int a=0; a<3; a++) { d[18+2*a]+=gaps[a]; d[19+2*a]+=gaps[a]*gaps[a]; }
    }
    public static void flush(int step, Path dir) throws IOException {
        Path f=dir.resolve("eta_agents.csv"); StringBuilder b=new StringBuilder();
        if(!Files.exists(f)) b.append("step,agentId,nQ,switches,comparable,nR_post,sumR_post,sumR2_post,sumQ_post,sumQ2_post,nR_like,sumR_like,sumR2_like,sumQ_like,sumQ2_like,nR_reshare,sumR_reshare,sumR2_reshare,sumQ_reshare,sumQ2_reshare,sumGap_post_like,sumGap2_post_like,sumGap_reshare_like,sumGap2_reshare_like,sumGap_post_reshare,sumGap2_post_reshare\n");
        for(var e: rows.entrySet()) { b.append(step).append(',').append(e.getKey()); for(double v:e.getValue()) b.append(',').append(Double.toString(v)); b.append('\n'); }
        Files.writeString(f,b.toString(),StandardOpenOption.CREATE,StandardOpenOption.APPEND);
        rows.clear();
    }
}
'''


def log(s):
    print(time.strftime("%H:%M:%S"), s, flush=True)


def cp():
    return ":".join(str(p) for p in sorted((ROOT / "lib").rglob("*.jar")))


def freeze_compile():
    src = OUT / "source"
    if not (OUT / "manifest.json").exists():
        src.mkdir(parents=True, exist_ok=True)
        hashes = {}
        for f in sorted((ROOT / "src").rglob("*.java")):
            data = f.read_bytes()
            rel = f.relative_to(ROOT / "src")
            hashes[str(rel)] = hashlib.sha256(data).hexdigest()
            target = src / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        f = src / "agent/Agent.java"
        s = f.read_text()
        needle = "LearningLog.recordTd(lastState, lastAction, r, delta);"
        assert s.count(needle) == 1
        s = s.replace(needle, needle + "\n            EtaDiagnostics.reward(id, lastAction, r);")
        needle = "decisions[state][pick]++;"
        assert s.count(needle) == 1
        s = s.replace(needle, needle + "\n        EtaDiagnostics.choice(id, q[state], ok);")
        f.write_text(s)
        f = src / "dynamics/OpinionDynamics.java"
        s = f.read_text()
        needle = "writeAgentActions(step, dir);"
        assert s.count(needle) == 1
        f.write_text(s.replace(needle, needle + "\n            agent.EtaDiagnostics.flush(step, dir);"))
        (src / "agent/EtaDiagnostics.java").write_text(DIAGNOSTICS)
        manifest = {"source_sha256": hashes, "tokens": TOKENS, "etas": ETAS,
                    "seeds": [0, 1, 2], "tail_start_exclusive": 15000,
                    "instrumentation": "Read-only per-agent reward and pre-choice Q moments; no RNG calls."}
        (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2))
    bin_dir = OUT / "bin"
    bin_dir.mkdir(exist_ok=True)
    subprocess.run(["javac", "-cp", cp(), "-d", str(bin_dir)] +
                   [str(p) for p in sorted(src.rglob("*.java"))], check=True, cwd=ROOT)
    with (LOG / "model_tests.log").open("w") as f:
        subprocess.run(["java", "-cp", cp() + ":" + str(bin_dir), "test.ModelTests"],
                       check=True, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
    log("frozen source compiled; ModelTests passed")


def name(eta, seed):
    return f"eta{eta:g}_s{seed}"


def run(eta, seed):
    key = name(eta, seed)
    stamp = OUT / (key + ".json")
    if stamp.exists():
        return json.loads(stamp.read_text())
    partial = OUT / key
    if partial.exists():
        archive = OUT / "incomplete"
        archive.mkdir(exist_ok=True)
        partial.rename(archive / (key + "_" + str(time.time_ns())))
    logfile = LOG / (key + ".log")
    tokens = {**TOKENS, "q_eta": str(eta), "seed": str(seed),
              "results_subdir": "eta_noise_compare/" + key}
    cmd = ["java", "-Xmx2g", "-XX:+ExitOnOutOfMemoryError", "-Duser.language=en",
           "-Duser.country=US", "-cp", cp() + ":" + str(OUT / "bin"),
           "dynamics.OpinionDynamics"] + [f"{k}={v}" for k, v in tokens.items()]
    started = time.time()
    log("start " + key)
    with logfile.open("w") as f:
        f.write("CMD " + " ".join(cmd) + "\n")
        f.flush()
        subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT, check=True, timeout=7200)
    dirs = list((OUT / key).glob("run_*"))
    assert len(dirs) == 1, dirs
    assert "the sum of error reported : 0" in logfile.read_text()
    data = {"eta": eta, "seed": seed, "run_dir": str(dirs[0]), "tokens": tokens,
            "seconds": round(time.time() - started), "assert_errors": 0}
    stamp.write_text(json.dumps(data, indent=2))
    log("done " + key + f" ({data['seconds']}s)")
    return data


def read(path):
    with path.open() as f:
        return [{k: float(v) if k != "action" else v for k, v in r.items()} for r in csv.DictReader(f)]


def entropy(p):
    return -sum(x * math.log(x) for x in p if x > 0)


def mean(xs):
    return statistics.mean(xs) if xs else float("nan")


def median(xs):
    return statistics.median(xs) if xs else float("nan")


def analyze_run(meta):
    d = Path(meta["run_dir"])
    rows = [r for r in read(d / "metrics/eta_agents.csv") if r["step"] > 15000]
    by_agent = {}
    for r in rows:
        acc = by_agent.setdefault(int(r["agentId"]), {})
        for k, v in r.items():
            if k not in ("step", "agentId"):
                acc[k] = acc.get(k, 0) + v
    result = {"eta": meta["eta"], "seed": meta["seed"], "seconds": meta["seconds"]}
    for a in ACTS:
        n = sum(r["nR_" + a] for r in rows)
        sr = sum(r["sumR_" + a] for r in rows)
        sr2 = sum(r["sumR2_" + a] for r in rows)
        result["reward_" + a] = sr / n
        result["reward_sd_" + a] = math.sqrt(max(0, sr2 / n - (sr / n)**2))
        individual_sd, between_ss, within_ss = [], 0.0, 0.0
        q_sd = []
        for r in by_agent.values():
            na = r["nR_" + a]
            if na > 0:
                ma = r["sumR_" + a] / na
                va = max(0, r["sumR2_" + a] / na - ma*ma)
                within_ss += na * va
                between_ss += na * (ma - sr/n)**2
                if na >= 30:
                    individual_sd.append(math.sqrt(va))
            nq = r["nQ"]
            if nq >= 100:
                mq = r["sumQ_" + a] / nq
                q_sd.append(math.sqrt(max(0, r["sumQ2_" + a]/nq - mq*mq)))
        result["median_individual_reward_sd_" + a] = median(individual_sd)
        result["reward_variance_between_fraction_" + a] = between_ss / (between_ss + within_ss)
        result["median_individual_q_sd_" + a] = median(q_sd)
    result["mean_reward"] = (sum(r["sumR_" + a] for r in rows for a in ACTS)
                              / sum(r["nR_" + a] for r in rows for a in ACTS))
    gaps = ["post_like", "reshare_like", "post_reshare"]
    for gap in gaps:
        sd, mu = [], []
        for r in by_agent.values():
            n = r["nQ"]
            if n < 100:
                continue
            m = r["sumGap_" + gap] / n
            sd.append(math.sqrt(max(0, r["sumGap2_" + gap] / n - m*m)))
            mu.append(m)
        result["gap_sd_" + gap] = median(sd)
        result["gap_mean_" + gap] = median(mu)
    result["winner_switch_rate"] = sum(r["switches"] for r in rows) / sum(r["comparable"] for r in rows)
    # Within-agent reward differences: observational, not counterfactual treatment effects.
    for a in ["post", "reshare"]:
        diffs = []
        for r in by_agent.values():
            if min(r["nR_like"], r["nR_" + a]) >= 30:
                diffs.append(r["sumR_" + a] / r["nR_" + a] - r["sumR_like"] / r["nR_like"])
        result["within_agent_reward_gap_" + a + "_like"] = median(diffs)
        result["within_agent_reward_gap_" + a + "_like_n_agents"] = len(diffs)
    aa = [r for r in read(d / "metrics/agent_actions.csv") if r["step"] > 15000]
    totals, windows = {}, {}
    for r in aa:
        i, step = int(r["agentId"]), int(r["step"])
        ns = [r[k] for k in ["nPost", "nLike", "nReshare"]]
        accum = totals.setdefault(i, [0, 0, 0])
        for k in range(3):
            accum[k] += ns[k]
        windows.setdefault(i, {})[step] = [n / sum(ns) for n in ns]
    ps = [[n / sum(ns) for n in ns] for ns in totals.values()]
    pbar = [mean([p[k] for p in ps]) for k in range(3)]
    result["policy_jsd"] = entropy(pbar) - mean([entropy(p) for p in ps])
    result["median_agent_max_share"] = median([max(p) for p in ps])
    drift = []
    for ws in windows.values():
        steps = sorted(ws)
        drift.extend([sum(abs(ws[t][k] - ws[u][k]) for k in range(3)) / 2
                      for u, t in zip(steps, steps[1:])])
    result["median_policy_window_tv"] = median(drift)
    ns = [sum(v[k] for v in totals.values()) for k in range(3)]
    for k, a in enumerate(ACTS):
        result["share_" + a] = ns[k] / sum(ns)
    qt = [r for r in read(d / "degrees/q_table_final.csv") if r["state"] == 0]
    min_counts = [min(r[k] for k in ["nPost", "nLike", "nReshare"]) for r in qt]
    result["median_min_action_updates"] = median(min_counts)
    # Fraction for which initial Q's remaining EMA weight is > 5% for at least one arm.
    result["initialization_retained_fraction"] = mean([(1-meta["eta"])**n > 0.05 for n in min_counts])
    cg = [r for r in read(d / "metrics/choice_gap.csv") if r["step"] > 15000]
    bins = {}
    for r in cg:
        b = bins.setdefault(r["gap_lo"], [0, 0, 0])
        for k, c in enumerate(["offered", "chosen", "sumTheoryP"]):
            b[k] += r[c]
    result["choice_calibration_mae"] = (sum(abs(b[1]-b[2]) for b in bins.values())
                                        / sum(b[0] for b in bins.values()))
    metrics = [r for r in read(d / "metrics/results.csv") if r["step"] > 15000]
    for c in ["meanIdentityFit", "meanRecognition", "attnGini", "emptyFeedShare", "meanFeedSize"]:
        result[c] = mean([r[c] for r in metrics])
    return result


def analyze():
    rows = []
    for eta in ETAS:
        for seed in range(3):
            stamp = OUT / (name(eta, seed) + ".json")
            if stamp.exists():
                rows.append(analyze_run(json.loads(stamp.read_text())))
    if not rows:
        return
    with (OUT / "diagnostics.csv").open("w") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    aggregate = []
    for eta in ETAS:
        group = [r for r in rows if r["eta"] == eta]
        if not group:
            continue
        item = {"eta": eta, "n_seeds": len(group)}
        for key in rows[0]:
            if key not in ("eta", "seed"):
                item[key] = mean([r[key] for r in group])
                item[key + "_seed_sd"] = statistics.stdev([r[key] for r in group]) if len(group) > 1 else 0
        aggregate.append(item)
    (OUT / "aggregate.json").write_text(json.dumps(aggregate, indent=2))
    for g in aggregate:
        log(f"eta={g['eta']}: gapSD(post-like)={g['gap_sd_post_like']:.3f}, "
            f"switch={g['winner_switch_rate']:.3f}, likeShare={g['share_like']:.3f}, "
            f"policyJSD={g['policy_jsd']:.3f}, windowTV={g['median_policy_window_tv']:.3f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parallel", type=int, default=9)
    ap.add_argument("--analyze", action="store_true")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True); LOG.mkdir(parents=True, exist_ok=True)
    if not args.analyze:
        freeze_compile()
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.parallel) as ex:
            futures = [ex.submit(run, eta, seed) for eta in ETAS for seed in range(3)]
            for fut in concurrent.futures.as_completed(futures):
                fut.result()
    analyze()
    log("ETA_DONE")


if __name__ == "__main__":
    main()
