#!/usr/bin/env python3
"""Five-seed 100% For You/Chrono/Trend comparison with the frozen eta model.

python3 scripts/feed_role_compare.py --parallel 12
Completed runs are resumable. Existing For You eta=.03 seeds 0-2 are reused.
"""
import argparse
import concurrent.futures
import hashlib
import json
import shutil
import subprocess
import threading
import time
from pathlib import Path

import eta_noise_compare as base

ROOT = base.ROOT
OUT = ROOT / "results/feed_role_compare"
LOG = ROOT / "logs/feed_role_compare"
FEEDS = {
    "foryou": {"foryou_share": "1.0", "trend_share": "0"},
    "chrono": {"foryou_share": "0", "trend_share": "0"},
    "trend": {"foryou_share": "0", "trend_share": "1.0"},
}
COMMON = {**base.TOKENS, "q_eta": "0.03", "trend_hop": "5"}
LOCK = threading.Lock()


def log(message):
    line = time.strftime("%H:%M:%S") + " " + message
    with LOCK:
        print(line, flush=True)
        with (LOG / "progress.log").open("a") as f:
            f.write(line + "\n")


def prepare():
    OUT.mkdir(parents=True, exist_ok=True); LOG.mkdir(parents=True, exist_ok=True)
    if not (OUT / "manifest.json").exists():
        old = json.loads((base.OUT / "manifest.json").read_text())
        shutil.copytree(base.OUT / "source", OUT / "source")
        shutil.copytree(base.OUT / "bin", OUT / "bin")
        manifest = {"source_sha256_before_instrumentation": old["source_sha256"],
                    "common_tokens": COMMON, "feeds": FEEDS, "seeds": list(range(5)),
                    "reused": "For You eta=.03 seeds 0-2 from eta_noise_compare",
                    "instrumentation": old["instrumentation"],
                    "semantics": "Full feed-mode comparison; chrono uses direct-follow FIFO cache sampling, not timestamp sorting. Algorithmic modes use 5-hop candidates with distance decay."}
        manifest["class_sha256"] = {str(p.relative_to(OUT / "bin")): hashlib.sha256(p.read_bytes()).hexdigest()
                                    for p in (OUT / "bin").rglob("*.class")}
        (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2))
    for seed in range(3):
        path = OUT / f"foryou_s{seed}.json"
        if path.exists():
            continue
        old = json.loads((base.OUT / f"eta0.03_s{seed}.json").read_text())
        # trend_hop is inactive in these reused runs; all active settings match.
        for k, v in COMMON.items():
            if k != "trend_hop":
                assert old["tokens"].get(k) == v, (k, old["tokens"].get(k), v)
        old.update(feed="foryou", reused=True)
        path.write_text(json.dumps(old, indent=2))


def run(feed, seed):
    key = f"{feed}_s{seed}"
    stamp = OUT / (key + ".json")
    if stamp.exists():
        return json.loads(stamp.read_text())
    partial = OUT / key
    if partial.exists():
        archive = OUT / "incomplete"; archive.mkdir(exist_ok=True)
        partial.rename(archive / (key + "_" + str(time.time_ns())))
    tokens = {**COMMON, **FEEDS[feed], "seed": str(seed), "results_subdir": "feed_role_compare/" + key}
    cmd = ["java", "-Xmx2g", "-XX:+ExitOnOutOfMemoryError", "-Duser.language=en", "-Duser.country=US",
           "-cp", base.cp() + ":" + str(OUT / "bin"), "dynamics.OpinionDynamics"]
    cmd += [f"{k}={v}" for k, v in tokens.items()]
    started = time.time(); log("start " + key)
    logfile = LOG / (key + ".log")
    with logfile.open("w") as f:
        f.write("CMD " + " ".join(cmd) + "\n"); f.flush()
        subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT, check=True, timeout=7200)
    dirs = list((OUT / key).glob("run_*")); assert len(dirs) == 1
    assert "the sum of error reported : 0" in logfile.read_text()
    meta = {"eta": 0.03, "feed": feed, "seed": seed, "run_dir": str(dirs[0]), "tokens": tokens,
            "seconds": round(time.time()-started), "assert_errors": 0, "reused": False}
    stamp.write_text(json.dumps(meta, indent=2)); log(f"done {key} ({meta['seconds']}s)")
    return meta


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--parallel", type=int, default=12)
    ap.add_argument("--analyze", action="store_true"); args = ap.parse_args()
    if not args.analyze:
        prepare()
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.parallel) as pool:
            futures = [pool.submit(run, feed, seed) for feed in FEEDS for seed in range(5)]
            for future in concurrent.futures.as_completed(futures):
                future.result()
    import feed_role_analysis
    feed_role_analysis.main()
    log("FEED_ROLE_DONE")


if __name__ == "__main__":
    main()
