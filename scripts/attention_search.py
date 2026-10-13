#!/usr/bin/env python3
"""Staged, resumable parameter search for the attention-economy model.

Usage:  nohup python3 scripts/attention_search.py > logs/search/driver.out 2>&1 &

What "good" means is defined in docs/report/2026-10-13-parameter-search.md (rubric). In short, a setting
is *feasible* if the system is healthy (feeds are not starved, recognition is neither absent nor
saturated, attention is not totally concentrated, no assertion errors), and among feasible settings we
rank by how differentiated the learned action values are (relative Q gap, visit-weighted).

Stages (each skips jobs already present in results/search/summary.jsonl, so a restart resumes):
  s1  screen x start network x post life         (single seed)
  s2  one-factor-at-a-time variations around the top-3 stage-1 settings (learning + For You parameters)
  s3  the overall top-4 with 2 more seeds; the top-2 also with rewire on (gated), seed 0 and 1

Heavy output dirs (GEXF, posts, clusterings, ...) are deleted after each run is summarised; metrics/ and
degrees/ are kept.
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
OUT = os.path.join(ROOT, "results", "search")
LOGD = os.path.join(ROOT, "logs", "search")
SUMMARY = os.path.join(OUT, "summary.jsonl")
BIN = os.path.join(ROOT, "bin_search")
PAR = int(os.environ.get("SEARCH_PAR", "16"))
HEAP = "2g"
TIMEOUT = 2700  # seconds per run

BASE = {
    "steps": "20000", "log_repost_cascade": "false", "log_gexf": "false", "log_post_lifespan": "false",
    "q_tau": "0.1", "q_init": "7", "l_ref": "1000",
    "i_edge_lo": "0.63", "i_edge_hi": "0.71", "rewire": "false",
}

SCREENS = {  # name -> tokens (Trend / For You shares and reach)
    "chrono": {"trend_share": "0", "foryou_share": "0"},
    "T1":     {"trend_share": "0.7", "trend_hop": "1"},
    "T4":     {"trend_share": "0.7", "trend_hop": "4"},
    "F1":     {"trend_share": "0", "foryou_share": "0.7", "foryou_hop": "1"},
    "F2":     {"trend_share": "0", "foryou_share": "0.7", "foryou_hop": "2"},
    "F4":     {"trend_share": "0", "foryou_share": "0.7", "foryou_hop": "4"},
    "M":      {"trend_share": "0.35", "trend_hop": "4", "foryou_share": "0.35", "foryou_hop": "2"},
}


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def libcp():
    jars = sorted(glob.glob(os.path.join(ROOT, "lib", "**", "*.jar"), recursive=True))
    return ":".join(jars)


def compile_sources():
    if os.path.isdir(BIN):
        shutil.rmtree(BIN)
    os.makedirs(BIN)
    files = [f for f in glob.glob(os.path.join(ROOT, "src", "**", "*.java"), recursive=True)]
    cp = libcp()
    cmd = ["javac", "-d", BIN] + (["-cp", cp] if cp else []) + files
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr)
        sys.exit("compile failed")
    log("compiled into " + BIN)


def load_summary():
    rows = {}
    if os.path.exists(SUMMARY):
        with open(SUMMARY) as f:
            for line in f:
                line = line.strip()
                if line:
                    d = json.loads(line)
                    rows[d["key"]] = d
    return rows


def append_summary(d):
    with open(SUMMARY, "a") as f:
        f.write(json.dumps(d, default=float) + "\n")


def entropy_skew(shares):
    s = np.array([x for x in shares if x > 0], dtype=float)
    k = len(shares)
    if k < 2 or s.sum() <= 0:
        return 0.0
    s = s / s.sum()
    h = -(s * np.log(s)).sum()
    return float(1.0 - h / math.log(k))


def summarize(run_dir, cfg, logfile):
    res = pd.read_csv(os.path.join(run_dir, "metrics", "results.csv"))
    tail = res.iloc[-2000:]
    def m(col):
        return float(tail[col].mean()) if col in tail else float("nan")
    rewire_on = cfg.get("rewire", "false") == "true"
    acts = ["post", "like", "reshare"] + (["rewire"] if rewire_on else [])
    shares = [m("actionShare_" + a) for a in acts]
    out = {
        "identityFit": m("meanIdentityFit"), "recognition": m("meanRecognition"),
        "attnGini": m("attnGini"), "attnTop1pct": m("attnTop1pctShare"),
        "alivePosts": m("alivePosts"), "assortativity": m("opinionAssortativity"),
        "estError": m("estError"), "meanFeedSize": m("meanFeedSize"), "emptyFeedShare": m("emptyFeedShare"),
        "shares": dict(zip(acts, shares)), "policySkew": entropy_skew(shares),
    }
    # visit-weighted Q structure from the per-window state/action log
    sa = pd.read_csv(os.path.join(run_dir, "metrics", "state_action.csv"))
    def q_stats(step):
        w = sa[(sa.step == step) & (sa.action.isin(acts))]
        gaps, vals, wts = [], [], []
        for _, g in w.groupby("state"):
            v = g.visits_in_state.iloc[0]
            if v <= 0:
                continue
            gaps.append(g.meanQ.max() - g.meanQ.min()); vals.append(g.meanQ.mean()); wts.append(v)
        if not wts:
            return float("nan"), float("nan")
        wts = np.array(wts, float)
        return float(np.average(gaps, weights=wts)), float(np.average(vals, weights=wts))
    steps = sorted(sa.step.unique())
    last = steps[-1]
    prev = min(steps, key=lambda s: abs(s - (last - 5000)))
    gap, qv = q_stats(last)
    _, qv_prev = q_stats(prev)
    out["qGap"] = gap
    out["qMean"] = qv
    out["qRelGap"] = gap / abs(qv) if qv and qv == qv else float("nan")
    out["qDrift"] = abs(qv - qv_prev) / abs(qv) if qv and qv == qv and qv_prev == qv_prev else float("nan")
    # per-agent spread of action values (means over the 9 states, so diluted by unvisited states)
    snap = pd.read_csv(os.path.join(run_dir, "degrees", "agent_snapshot_final.csv"))
    qcols = ["qPost", "qLike", "qReshare"] + (["qRewire"] if rewire_on else [])
    out["agentQGap"] = float((snap[qcols].max(axis=1) - snap[qcols].min(axis=1)).mean())
    out["zeroFollowerShare"] = float((snap.followerCount == 0).mean())
    out["capacity"] = int(cfg.get("feed_capacity", 10))
    errs = None
    try:
        with open(logfile) as f:
            for line in f:
                if "sum of error reported" in line:
                    errs = int(line.strip().split(":")[-1])
    except Exception:
        pass
    out["assertErrors"] = errs
    return out


def feasible(s):
    cap = s["capacity"]
    return bool(
        s.get("assertErrors") == 0
        and s["meanFeedSize"] >= 0.6 * cap
        and s["emptyFeedShare"] <= 0.15
        and 0.05 <= s["recognition"] <= 0.8
        and s["attnGini"] <= 0.9
        and s["alivePosts"] > 0
    )


def prune(run_dir):
    for sub in ["GEXF", "posts", "clusterings", "opinion", "figures"]:
        shutil.rmtree(os.path.join(run_dir, sub), ignore_errors=True)


def run_job(job):
    jid, tokens, seed = job["id"], job["tokens"], job["seed"]
    key = f"{jid}__s{seed}"
    os.makedirs(LOGD, exist_ok=True)
    logfile = os.path.join(LOGD, f"{jid}_seed{seed}.log")
    cmd = ["java", f"-Xmx{HEAP}", "-XX:+ExitOnOutOfMemoryError", "-cp", libcp() + ":" + BIN,
           "dynamics.OpinionDynamics", f"seed={seed}"] + [f"{k}={v}" for k, v in tokens.items()] \
          + [f"results_subdir=search/{jid}"]
    t0 = time.time()
    status = "ok"
    try:
        with open(logfile, "w") as lf:
            lf.write("CMD " + " ".join(cmd) + "\n")
            lf.flush()
            subprocess.run(cmd, cwd=ROOT, stdout=lf, stderr=subprocess.STDOUT, timeout=TIMEOUT, check=True)
        run_dir = glob.glob(os.path.join(OUT, jid, f"run_{seed}_*"))[0]
        s = summarize(run_dir, tokens, logfile)
        prune(run_dir)
    except Exception as e:  # keep going; record the failure
        status = f"failed: {type(e).__name__}"
        s = {}
    d = {"key": key, "id": jid, "seed": seed, "tokens": tokens, "status": status,
         "seconds": round(time.time() - t0), **s}
    if status == "ok":
        d["feasible"] = feasible(d)
    append_summary(d)
    log(f"done {key}: {status}" + (f" feasible={d['feasible']} relGap={d['qRelGap']:.4f}" if status == 'ok' else ""))
    return d


def run_stage(name, jobs):
    done = load_summary()
    todo = [j for j in jobs if f"{j['id']}__s{j['seed']}" not in done]
    log(f"stage {name}: {len(jobs)} jobs, {len(todo)} to run")
    with ThreadPoolExecutor(max_workers=PAR) as ex:
        list(ex.map(run_job, todo))
    done = load_summary()
    return [done[f"{j['id']}__s{j['seed']}"] for j in jobs if f"{j['id']}__s{j['seed']}" in done]


def rank(rows):
    ok = [r for r in rows if r.get("status") == "ok"]
    return sorted(ok, key=lambda r: (not r.get("feasible", False), -(r.get("qRelGap") or 0.0)))


def stage1():
    jobs = []
    for net in ["ws", "dba"]:
        for scr, tk in SCREENS.items():
            for L in [50, 100, 200]:
                t = dict(BASE); t.update(tk); t["network"] = net; t["dead_after"] = str(L)
                jobs.append({"id": f"s1_{scr}_{net}_L{L}", "tokens": t, "seed": 0})
    return jobs


OFAT = [
    ("tau0.03", {"q_tau": "0.03"}), ("tau0.3", {"q_tau": "0.3"}),
    ("gam0", {"q_gamma": "0"}), ("gam0.5", {"q_gamma": "0.5"}),
    ("qinit0", {"q_init": "0"}),
    ("eps0.02", {"q_eps": "0.02"}), ("eps0.1", {"q_eps": "0.1"}),
    ("eta0.03", {"q_eta": "0.03"}), ("eta0.3", {"q_eta": "0.3"}),
    ("cap5", {"feed_capacity": "5"}), ("cap15", {"feed_capacity": "15"}),
    ("acc0.05", {"access_prob": "0.05"}), ("acc0.2", {"access_prob": "0.2"}),
    ("bh1", {"beta_h": "1"}), ("bh8", {"beta_h": "8"}),
]
OFAT_FY = [
    ("fyb1", {"fy_beta": "1"}), ("fyb8", {"fy_beta": "8"}),
    ("rhoLow", {"rho_l": "0.02", "rho_r": "0.05"}), ("rhoHigh", {"rho_l": "0.2", "rho_r": "0.4"}),
]


def stage2(top):
    jobs = []
    for r in top:
        base_tokens = r["tokens"]
        variants = list(OFAT) + (OFAT_FY if float(base_tokens.get("foryou_share", "0")) > 0 else [])
        for vname, tk in variants:
            t = dict(base_tokens); t.update(tk)
            jobs.append({"id": f"s2_{r['id'][3:]}__{vname}", "tokens": t, "seed": 0})
    return jobs


def stage3(top, top_rewire):
    jobs = []
    for r in top:
        for seed in [1, 2]:
            jobs.append({"id": r["id"], "tokens": r["tokens"], "seed": seed})
    for r in top_rewire:
        for seed in [0, 1]:
            t = dict(r["tokens"]); t["rewire"] = "true"
            jobs.append({"id": r["id"] + "__rewire", "tokens": t, "seed": seed})
    return jobs


def write_ranking(rows, path):
    ok = [r for r in rows if r.get("status") == "ok"]
    cols = ["key", "feasible", "qRelGap", "qGap", "qDrift", "agentQGap", "policySkew", "meanFeedSize",
            "emptyFeedShare", "recognition", "attnGini", "identityFit", "assortativity", "alivePosts",
            "estError", "zeroFollowerShare", "assertErrors", "seconds"]
    df = pd.DataFrame([{c: r.get(c) for c in cols} for r in ok])
    if not df.empty:
        df = df.sort_values(["feasible", "qRelGap"], ascending=[False, False])
    df.to_csv(path, index=False)
    return df


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(LOGD, exist_ok=True)
    if "--no-compile" not in sys.argv:
        compile_sources()
    r1 = run_stage("s1", stage1())
    top1 = rank(r1)[:3]
    log("stage-1 top: " + ", ".join(t["id"] for t in top1))
    r2 = run_stage("s2", stage2(top1))
    allrows = [r for r in load_summary().values() if r["id"].startswith(("s1_", "s2_"))]
    best = rank(allrows)
    # distinct settings only (one row per id), top 4; the top 2 of them also with rewire on
    top = best[:4]
    log("overall top: " + ", ".join(t["id"] for t in top))
    run_stage("s3", stage3(top, top[:2]))
    final = list(load_summary().values())
    df = write_ranking(final, os.path.join(OUT, "ranking.csv"))
    log("ranking written: " + os.path.join(OUT, "ranking.csv"))
    log("SEARCH_DONE")


if __name__ == "__main__":
    main()
