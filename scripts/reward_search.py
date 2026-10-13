#!/usr/bin/env python3
"""Staged, resumable sweep of the reward parameters (identity-fit weight, recognition weight, recognition shape).

Usage:  nohup python3 scripts/reward_search.py > logs/rsearch/driver.out 2>&1 &

Reward:  r = w_fit * I + w_rec * L,   L = m * (1 - exp(-likes / lam_r)) + (1 - m) * min(1, ln(1+likes)/ln(1+L_ref))
  * "stronger for fewer likes"   -> larger w_rec, larger m, smaller lam_r (the first likes are worth most)
  * "less reactive to similarity" -> smaller w_fit (identity fit varies little around its average, so scaling it down
                                     lowers its influence on which action pays; a constant offset would not matter)
Optimistic start: q_init = 10 * (w_fit + w_rec), the largest possible discounted return (gamma 0.9), so no action looks
worse than the truth merely because it was not tried early. One baseline per screen keeps the original q_init = 7.

What is scored (see docs/report/2026-10-13-reward-sweep.md):
  spread   = highest minus lowest mean immediate reward among actions, divided by the sd of a single reward
  captured = share of the achievable reward gain (best action per state vs a uniform choice) that agents actually take
  plus lock-in statistics, camp policy contrast and health checks. Rank: feasible, spread >= 0.3, then captured gain.

Stages: s1 grid (seed 0)  ->  s2 top-4 with seeds 1,2  ->  s3 top-2 with rewire on (seeds 0,1).
"""
import glob
import json
import math
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "results", "rsearch")
LOGD = os.path.join(ROOT, "logs", "rsearch")
SUMMARY = os.path.join(OUT, "summary.jsonl")
BIN = os.path.join(ROOT, "bin_rsearch")
PAR = int(os.environ.get("SEARCH_PAR", "16"))
HEAP = "2g"
TIMEOUT = 3600

BASE = {
    "steps": "20000", "log_repost_cascade": "false", "log_gexf": "false", "log_post_lifespan": "false",
    "q_tau": "0.1", "l_ref": "1000", "i_edge_lo": "0.63", "i_edge_hi": "0.71", "rewire": "false",
    "network": "hk", "dead_after": "200",
}
SCREENS = {
    "chrono": {"trend_share": "0", "foryou_share": "0"},
    "foryou": {"trend_share": "0", "foryou_share": "0.7", "foryou_hop": "1"},
}
ACTS = ["post", "like", "reshare"]
COLQ = {"post": "qPost", "like": "qLike", "reshare": "qReshare", "rewire": "qRewire"}
COLN = {"post": "nPost", "like": "nLike", "reshare": "nReshare", "rewire": "nRewire"}


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def libcp():
    return ":".join(sorted(glob.glob(os.path.join(ROOT, "lib", "**", "*.jar"), recursive=True)))


def compile_sources():
    if os.path.isdir(BIN):
        shutil.rmtree(BIN)
    os.makedirs(BIN)
    files = glob.glob(os.path.join(ROOT, "src", "**", "*.java"), recursive=True)
    cp = libcp()
    r = subprocess.run(["javac", "-d", BIN] + (["-cp", cp] if cp else []) + files, cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr)
        sys.exit("compile failed")
    log("compiled into " + BIN)


def load_summary():
    rows = {}
    if os.path.exists(SUMMARY):
        for line in open(SUMMARY):
            line = line.strip()
            if line:
                d = json.loads(line)
                rows[d["key"]] = d
    return rows


def append_summary(d):
    with open(SUMMARY, "a") as f:
        f.write(json.dumps(d, default=float) + "\n")


def summarize(run_dir, tokens, logfile):
    rewire_on = tokens.get("rewire", "false") == "true"
    acts = ACTS + (["rewire"] if rewire_on else [])
    res = pd.read_csv(os.path.join(run_dir, "metrics", "results.csv"))
    tail = res.iloc[-2000:]
    m = lambda c: float(tail[c].mean()) if c in tail else float("nan")
    out = {"fit": m("meanIdentityFit"), "rec": m("meanRecognition"), "gini": m("attnGini"), "feed": m("meanFeedSize"),
           "empty": m("emptyFeedShare"), "assort": m("opinionAssortativity"), "shares": {a: m("actionShare_" + a) for a in acts}}
    # immediate reward per (state, action), after the opening transient
    td = pd.read_csv(os.path.join(run_dir, "metrics", "td_log.csv"))
    td = td[(td.action.isin(acts)) & (td.step >= 5000)]
    def pool(g):
        n = g.n.sum()
        mu = (g.n * g.meanR).sum() / n
        var = (g.n * (g.varR + (g.meanR - mu) ** 2)).sum() / n
        return n, mu, var
    ra = {}
    for a in acts:
        g = td[td.action == a]
        if len(g):
            n, mu, var = pool(g)
            ra[a] = (n, mu, math.sqrt(var))
    means = [v[1] for v in ra.values()]
    out["rewardMean"] = {a: v[1] for a, v in ra.items()}
    out["rewSd"] = float(np.mean([v[2] for v in ra.values()]))
    out["rewRange"] = float(max(means) - min(means))
    out["spread"] = out["rewRange"] / out["rewSd"] if out["rewSd"] > 0 else 0.0
    # population reward table R[s][a]
    R = {}
    for (s, a), g in td.groupby(["state", "action"]):
        if g.n.sum() >= 30:
            R[(int(s), a)] = pool(g)[1]
    # Q table statistics and the reward-optimality of what agents actually did
    qt = pd.read_csv(os.path.join(run_dir, "degrees", "q_table_final.csv")).sort_values(["agentId", "state"])
    K = len(acts)
    n_ag = qt.agentId.nunique()
    Q = qt[[COLQ[a] for a in acts]].values.reshape(n_ag, 9, K)
    N = qt[[COLN[a] for a in acts]].values.reshape(n_ag, 9, K)
    srt = np.sort(Q, axis=2)
    lead = srt[:, :, -1] - srt[:, :, -2]
    fav = Q.argmax(2)
    visits = N.sum(2)
    ok = visits >= 20
    out["medLead"] = float(np.median(lead[ok])) if ok.any() else float("nan")
    out["favShare"] = float(np.take_along_axis(N, fav[:, :, None], 2)[ok].sum() / N[ok].sum()) if ok.any() else float("nan")
    qmean = float(np.mean(Q[ok])) if ok.any() else float("nan")
    out["relLead"] = out["medLead"] / qmean if qmean else float("nan")
    # captured gain: how much of the (best action per state vs uniform) reward gain agents realise
    num_taken = num_uniform = num_best = 0.0
    justified = total = 0
    for s in range(9):
        rs = {a: R[(s, a)] for a in acts if (s, a) in R}
        if len(rs) < 2:
            continue
        ns = np.array([N[:, s, i].sum() for i, a in enumerate(acts) if a in rs])
        vals = np.array([rs[a] for a in acts if a in rs])
        if ns.sum() == 0:
            continue
        w = ns.sum()
        num_taken += float((ns * vals).sum())
        num_uniform += float(w * vals.mean())
        num_best += float(w * vals.max())
        best_a = [a for a in acts if a in rs][int(vals.argmax())]
        bi = acts.index(best_a)
        sel = ok[:, s]
        justified += int((fav[sel, s] == bi).sum())
        total += int(sel.sum())
    out["captured"] = (num_taken - num_uniform) / (num_best - num_uniform) if num_best - num_uniform > 1e-9 else float("nan")
    out["justified"] = justified / total if total else float("nan")
    out["chance"] = 1.0 / K
    # convergence: relative change of the visit-weighted mean Q over the last 5000 steps
    sa = pd.read_csv(os.path.join(run_dir, "metrics", "state_action.csv"))
    def qbar(step):
        w = sa[(sa.step == step) & (sa.action.isin(acts))]
        g = w.groupby("state").agg(q=("meanQ", "mean"), v=("visits_in_state", "first"))
        return float(np.average(g.q, weights=g.v)) if g.v.sum() > 0 else float("nan")
    steps = sorted(sa.step.unique())
    last = steps[-1]
    prev = min(steps, key=lambda s: abs(s - (last - 5000)))
    out["qDrift"] = abs(qbar(last) - qbar(prev)) / abs(qbar(last))
    # camp contrast: post share of the lowest- vs highest-follower fifth
    snap = pd.read_csv(os.path.join(run_dir, "degrees", "agent_snapshot_final.csv")).sort_values("agentId").reset_index(drop=True)
    n = len(snap)
    order = np.lexsort((np.arange(n), snap.followerCount.values))
    camp = np.empty(n, int)
    for k in range(5):
        camp[order[k * n // 5:(k + 1) * n // 5]] = k
    aa = pd.read_csv(os.path.join(run_dir, "metrics", "agent_actions.csv"))
    aa = aa[aa.step > aa.step.max() - 5000]
    aa["camp"] = camp[aa.agentId.values]
    cs = aa.groupby("camp")[[COLN[a] for a in acts]].sum()
    cs = cs.div(cs.sum(1), axis=0)
    out["campPost"] = [float(cs.iloc[k]["nPost"]) for k in (0, 4)]
    out["campLike"] = [float(cs.iloc[k]["nLike"]) for k in (0, 4)]
    if rewire_on:
        out["rewireDone"] = float(res.rewire.sum())
    errs = None
    try:
        for line in open(logfile):
            if "sum of error reported" in line:
                errs = int(line.strip().split(":")[-1])
    except Exception:
        pass
    out["assertErrors"] = errs
    out["capacity"] = int(tokens.get("feed_capacity", 10))
    return out


def feasible(s):
    return bool(s.get("assertErrors") == 0 and s["feed"] >= 0.6 * s["capacity"] and s["empty"] <= 0.15
                and 0.05 <= s["rec"] <= 0.9 and s["gini"] <= 0.93)


def prune(run_dir):
    for sub in ["GEXF", "posts", "clusterings", "opinion", "figures"]:
        shutil.rmtree(os.path.join(run_dir, sub), ignore_errors=True)


def run_job(job):
    jid, tokens, seed = job["id"], job["tokens"], job["seed"]
    key = f"{jid}__s{seed}"
    os.makedirs(LOGD, exist_ok=True)
    logfile = os.path.join(LOGD, f"{jid}_seed{seed}.log")
    cmd = ["java", f"-Xmx{HEAP}", "-XX:+ExitOnOutOfMemoryError", "-cp", libcp() + ":" + BIN,
           "dynamics.OpinionDynamics", f"seed={seed}"] + [f"{k}={v}" for k, v in tokens.items()] + [f"results_subdir=rsearch/{jid}"]
    t0 = time.time()
    status, s = "ok", {}
    try:
        with open(logfile, "w") as lf:
            lf.write("CMD " + " ".join(cmd) + "\n")
            lf.flush()
            subprocess.run(cmd, cwd=ROOT, stdout=lf, stderr=subprocess.STDOUT, timeout=TIMEOUT, check=True)
        run_dir = glob.glob(os.path.join(OUT, jid, f"run_{seed}_*"))[0]
        s = summarize(run_dir, tokens, logfile)
        prune(run_dir)
    except Exception as e:
        status = f"failed: {type(e).__name__}: {e}"
    d = {"key": key, "id": jid, "seed": seed, "tokens": tokens, "status": status, "seconds": round(time.time() - t0), **s}
    if status == "ok":
        d["feasible"] = feasible(d)
    append_summary(d)
    log(f"done {key}: {status[:60]}" + (f" feasible={d['feasible']} spread={d['spread']:.2f} captured={d['captured']:.2f}" if status == "ok" else ""))
    return d


def run_stage(name, jobs):
    done = load_summary()
    todo = [j for j in jobs if f"{j['id']}__s{j['seed']}" not in done]
    log(f"stage {name}: {len(jobs)} jobs, {len(todo)} to run")
    with ThreadPoolExecutor(max_workers=PAR) as ex:
        list(ex.map(run_job, todo))
    done = load_summary()
    return [done[f"{j['id']}__s{j['seed']}"] for j in jobs if f"{j['id']}__s{j['seed']}" in done]


def merit(r):
    cap = r.get("captured")
    cap = -1.0 if cap is None or cap != cap else cap
    return (not r.get("feasible", False), r.get("spread", 0.0) < 0.3, -cap)


def rank(rows):
    return sorted([r for r in rows if r.get("status") == "ok"], key=merit)


def cfg_name(wf, wr, mix, lam):
    return f"wf{wf}_wr{wr}_m{mix}_l{lam}"


def stage1():
    jobs = []
    for scr, tk in SCREENS.items():
        for wf in ["1", "0.5", "0.25"]:
            for wr in ["1", "2"]:
                for mix in ["0.5", "1"]:
                    for lam in ["2", "0.5"]:
                        t = dict(BASE); t.update(tk)
                        t.update({"w_fit": wf, "w_rec": wr, "recog_mix": mix, "recog_lambda": lam,
                                  "q_init": str(int(round(10 * (float(wf) + float(wr)))))})
                        jobs.append({"id": f"r1_{scr}_{cfg_name(wf, wr, mix, lam)}", "tokens": t, "seed": 0})
        t = dict(BASE); t.update(tk); t.update({"q_init": "7"})
        jobs.append({"id": f"r1_{scr}_baseline_q7", "tokens": t, "seed": 0})
    return jobs


def stage2(top):
    return [{"id": r["id"], "tokens": r["tokens"], "seed": s} for r in top for s in (1, 2)]


def stage3(top):
    jobs = []
    for r in top:
        t = dict(r["tokens"]); t["rewire"] = "true"
        for s in (0, 1):
            jobs.append({"id": r["id"] + "__rewire", "tokens": t, "seed": s})
    return jobs


def write_ranking(path):
    rows = [r for r in load_summary().values() if r.get("status") == "ok"]
    cols = ["key", "feasible", "spread", "captured", "justified", "chance", "medLead", "relLead", "favShare", "qDrift", "fit", "rec",
            "gini", "feed", "campPost", "campLike", "rewRange", "rewSd", "assertErrors", "seconds"]
    df = pd.DataFrame([{c: r.get(c) for c in cols} for r in rows])
    if not df.empty:
        df = df.sort_values(["feasible", "captured"], ascending=[False, False])
    df.to_csv(path, index=False)


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(LOGD, exist_ok=True)
    if "--no-compile" not in sys.argv:
        compile_sources()
    r1 = run_stage("s1", stage1())
    top = []
    seen = set()
    for r in rank(r1):
        if r["id"] not in seen and "baseline" not in r["id"]:
            seen.add(r["id"]); top.append(r)
        if len(top) == 4:
            break
    log("stage-1 top: " + ", ".join(t["id"] for t in top))
    run_stage("s2", stage2(top))
    run_stage("s3", stage3(top[:2]))
    write_ranking(os.path.join(OUT, "ranking.csv"))
    log("ranking written; RSEARCH_DONE")


if __name__ == "__main__":
    main()
