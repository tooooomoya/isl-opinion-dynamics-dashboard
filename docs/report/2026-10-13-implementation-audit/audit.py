"""Reproduce implementation audit against an isolated copy of the current sources.

Run from anywhere: python3 <this file> [--output /path/to/new/audit-artifacts]
Outputs are written to a fresh temporary directory by default. Contract failures
are expected on the audited revision and cause exit 1. No simulations, sources or
logs in the repository are overwritten; no cleanup process-killing is invoked.
"""
from pathlib import Path
import argparse
import concurrent.futures
import csv
import hashlib
import json
import math
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time


ARMS = {
    "ws_chrono": ["network=ws", "trend_share=0", "rewire=false"],
    "dba_fy": ["network=dba", "trend_share=0", "foryou_share=0.7", "foryou_hop=2", "rewire=false"],
    "ws_trend": ["network=ws", "trend_share=0.7", "rewire=false"],
    "ws_mixed_rewire": ["network=ws", "trend_share=0.3", "foryou_share=0.4", "foryou_hop=2", "trend_hop=2", "rewire=true"],
}


def integration(root, output, cp):
    def run(item):
        arm, seed = item
        args = [f"seed={seed}", "n=64", "steps=1001", "assert_int=1", "log_gexf=false",
                f"results_subdir={arm}", *ARMS[arm]]
        log = output / f"integration-{arm}-{seed}.log"
        dirs = list((output / "results" / arm).glob(f"run_{seed}_*"))
        if not dirs:
            r = subprocess.run(["java", "-cp", cp, "dynamics.OpinionDynamics", *args],
                               cwd=output, capture_output=True, text=True, timeout=60)
            log.write_text(r.stdout + r.stderr)
            code = r.returncode
            dirs = list((output / "results" / arm).glob(f"run_{seed}_*"))
        else:
            code = 0  # Reanalyse already-generated audit-only output, never overwrite it.
        errors, checks = [], 0
        if code:
            errors.append(f"java_exit={code}")
        if not dirs or not (dirs[0] / "metrics/results.csv").exists():
            return {"arm": arm, "seed": seed, "checks": checks, "errors": errors + ["no_result"]}
        d = dirs[0]
        with (d / "metrics/results.csv").open() as h:
            rows = list(csv.DictReader(h))
        checks += 1
        if len(rows) != 1002 or rows[-1]["step"] != "1001":
            errors.append("row_count/end")
        for row in rows:
            checks += 5
            if None in row or any(v is None for v in row.values()):
                errors.append("CSV_schema")
                break
            if any(not math.isfinite(float(v)) for k, v in row.items() if k != "estError"):
                errors.append("nonfinite")
                break
            if int(row["createdPosts"]) != int(row["alivePosts"]) + int(row["diedPosts"]):
                errors.append("pool_conservation")
                break
            if int(row["visitCount"]) and abs(sum(float(row["actionShare_" + x]) for x in
                    ["post", "like", "reshare", "rewire"]) - 1) > .00021:
                errors.append("shares")
                break
            if row["opinionVar"] != rows[0]["opinionVar"]:
                errors.append("mu0_var_changed")
                break
        if "the sum of error reported : 0" not in log.read_text():
            errors.append("assertions_not_zero")
        for i in range(1, len(rows)):
            checks += 1
            if int(rows[i]["createdPosts"]) - int(rows[i-1]["createdPosts"]) != (
                    int(rows[i]["originalPostCount"]) + int(rows[i]["repostCount"])):
                errors.append("created_diff")
                break
        if "rewire=false" in ARMS[arm]:
            checks += 1
            if any(int(row["rewire"]) for row in rows):
                errors.append("static_rewire")
        cf = d / "posts/repost_cascades.csv"
        events = []
        if cf.exists():
            with cf.open() as h:
                events = list(csv.DictReader(h))
        checks += 2
        if len(events) != sum(int(row["repostCount"]) for row in rows):
            errors.append("cascade_event_count")
        pairs = [(e["relayer"], e["rootPostId"]) for e in events]
        if len(set(pairs)) != len(pairs):
            errors.append("duplicate_root_reshare")
        checks += 1
        with (d / "metrics/state_action.csv").open() as h:
            state_rows = list(csv.DictReader(h))
        if sum(int(x["count"]) for x in state_rows) != sum(int(row["visitCount"]) for row in rows):
            errors.append("diagnostic_final_window_missing")
        return {"arm": arm, "seed": seed, "checks": checks, "errors": errors,
                "last_step": rows[-1]["step"], "rows": len(rows), "cascades": len(events)}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        result = list(pool.map(run, [(a, s) for a in ARMS for s in range(3)]))
    (output / "integration.json").write_text(json.dumps(result, indent=2))
    return result


def python_contracts(root, output):
    sys.path.insert(0, str(root))
    from dashboard import core
    from dashboard import analysis
    result = []
    def check(name, ok, detail):
        result.append({"id": name, "pass": bool(ok), "detail": detail})
    run = (root / "run.sh").read_text()
    fn = run[run.index("run_one() {"):run.index("\nexport -f run_one")]
    logdir = output / "launcher-logs"
    logdir.mkdir(exist_ok=True)
    cmd = ("LIBCP=unused\nJAVA_HEAP=2g\nCONFIG_TOKENS=''\nRUN_NAME=''\nLOGDIR="
           + shlex.quote(str(logdir)) + "\njava() { return 42; }\n" + fn + "\nrun_one 0\n")
    r = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, cwd=output)
    text = (logdir / "run_0.log").read_text()
    check("LAUNCHER_JAVA_FAILURE_NONZERO", r.returncode != 0,
          f"java exits42; run_one exit={r.returncode}; END marker={'[END]' in text}")
    check("LAUNCHER_CLEANUP_OWN_PROCESSES", "pkill -f OpinionDynamics" not in run,
          "static check only; cleanup handler was never executed")
    logs = output / "status-logs"
    logs.mkdir(exist_ok=True)
    (logs / "run_0.log").write_text("[ABORT] result folder already exists\n[END]\n")
    (logs / "run_1.log").write_text("java.lang.OutOfMemoryError: Java heap space\n[END]\n")
    statuses = core.active_seeds(logs, prefix="run_")
    check("DASHBOARD_ABORT_FAILED", statuses.get(0) == "failed", f"ABORT classified {statuses.get(0)}")
    check("DASHBOARD_OOM_FAILED", statuses.get(1) == "failed", f"OOM classified {statuses.get(1)}")
    p = output / "sample-lifespans.csv"
    p.write_text("step,lifespan\n" + "\n".join(f"{i},{1000 if i == 1 else 1}" for i in range(10)) + "\n")
    tail = core.CsvTail(p, max_rows=4)
    tail.poll()
    vals = tail.column("lifespan")
    check("DASHBOARD_LIFESPAN_TOP_PRESERVED", max(vals) == 1000, f"true max1000; retained max={max(vals)}")
    check("DASHBOARD_EVENT_COUNT_EXACT", len(vals) == 10, f"true10 events; retained={len(vals)}")
    p = output / "chain.csv"
    p.write_text("step,rootPostId,parentPostId,postId\n" + "\n".join(f"{i},0,{i},{i+1}" for i in range(6)) + "\n")
    tail = core.CsvTail(p, max_rows=4)
    tail.poll()
    edges = [(int(a), int(b)) for a, b in zip(tail.column("parentPostId"), tail.column("postId"))]
    full = core._cascade_virality([(i, i+1) for i in range(6)], 0)
    sampled = core._cascade_virality(edges, 0)
    check("DASHBOARD_CASCADE_TOPOLOGY_PRESERVED", full == sampled, f"full={full}; decimated={sampled}")
    p = output / "partial.csv"
    p.write_text("step,value\n0,1\n1,")
    tail = core.CsvTail(p, max_rows=20)
    tail.poll()
    before = tail.column("value")
    with p.open("a") as h:
        h.write("2\n")
    tail.poll()
    check("CSV_TAIL_PARTIAL_LINE", before == [1.] and tail.column("value") == [1., 2.], "partial append read once")
    saved = core._RESULT_INDEX, core._RESULT_INDEX_AT
    x, y = output / "isolated/A/run_0_a", output / "isolated/B/run_0_b"
    x.mkdir(parents=True, exist_ok=True)
    y.mkdir(parents=True, exist_ok=True)
    core._RESULT_INDEX = {0: [x, y]}
    core._RESULT_INDEX_AT = time.monotonic()
    try:
        check("DASHBOARD_GROUP_ISOLATION", core.result_dir(0) is None and
              core.result_dir(0, "missing") is None and core.result_dir(0, "A/run") == x,
              "ambiguous/unmatched rejected; matching arm resolved")
    finally:
        core._RESULT_INDEX, core._RESULT_INDEX_AT = saved
    from types import SimpleNamespace
    graph = SimpleNamespace(nodes={"0": {"opinion": -.1}, "1": {"opinion": .1}})
    _, left, right = analysis._camps(graph)
    check("DASHBOARD_NEUTRAL_BAND_CONFIG", len(left) == 1 and len(right) == 1,
          f"neutral_band=0 should include +/- .1, dashboard fixed threshold={analysis.NEUTRAL_BAND_HALF_WIDTH}; camps={len(left)}/{len(right)} (CLI linkage absent)")
    (output / "python-contracts.json").write_text(json.dumps(result, indent=2))
    return result


def edge_integration(output, cp):
    cases = {
        "silent": ["n=24", "steps=1", "network=ws", "trend_share=0", "rewire=false", "access_prob=1", "silent_until_ids=0", "activation_step=20"],
        "pinned": ["n=24", "steps=2", "network=ws", "trend_share=0", "rewire=false", "access_prob=1", "extreme=SYM", "mu=0.1", "assert_int=1"],
        "small_ws": ["n=8", "steps=1", "network=ws", "assert_int=1"],
        "zero_lref": ["n=24", "steps=2", "l_ref=0", "access_prob=1", "assert_int=1"],
        "zero_window": ["n=24", "steps=2", "interaction_window=0"],
    }
    result = []
    for name, tokens in cases.items():
        r = subprocess.run(["java", "-cp", cp, "dynamics.OpinionDynamics", f"results_subdir=edge_{name}",
                            "log_gexf=false", *tokens], cwd=output, capture_output=True, text=True, timeout=30)
        (output / f"edge-{name}.log").write_text(r.stdout + r.stderr)
        row = {"case": name, "exit": r.returncode,
               "assert_lines": [x for x in r.stdout.splitlines() if "AC Error" in x or "sum of error" in x],
               "exception": [x for x in r.stderr.splitlines() if "Exception" in x]}
        dirs = list((output / "results" / ("edge_" + name)).glob("run_*"))
        if dirs and (dirs[0] / "metrics/results.csv").exists():
            with (dirs[0] / "metrics/results.csv").open() as h:
                rows = list(csv.DictReader(h))
            row["final_metrics"] = {k: rows[-1][k] for k in
                                    ["visitCount", "originalPostCount", "meanRecognition", "meanQ_post"]}
        if name == "pinned" and dirs:
            with (dirs[0] / "degrees/agent_snapshot_final.csv").open() as h:
                row["pinned_agents"] = [x for x in csv.DictReader(h) if x["isTarget"] == "1"]
        result.append(row)
    (output / "edge-integration.json").write_text(json.dumps(result, indent=2))
    return result


def network_smokes(output, cp):
    result = []
    for kind, seed in [(n, 0) for n in
            ["ws", "dba", "homophily", "random", "ba", "hk", "dms", "cnn", "lfr", "dcsbm"]] + [("cnn", 123)]:
        name = f"network_{kind}_{seed}"
        command = ["java", "-cp", cp, "dynamics.OpinionDynamics", f"seed={seed}", "n=64", "steps=5",
                   f"network={kind}", "log_gexf=false", "assert_int=1", f"results_subdir={name}"]
        try:
            r = subprocess.run(command, cwd=output, capture_output=True, text=True, timeout=5)
            (output / f"{name}.log").write_text(r.stdout + r.stderr)
            row = {"network": kind, "seed": seed, "exit": r.returncode, "timeout": False,
                   "assert_lines": [s for s in r.stdout.splitlines() if "AC Error" in s]}
        except subprocess.TimeoutExpired as ex:
            row = {"network": kind, "seed": seed, "exit": None, "timeout": True,
                   "stdout": (ex.stdout or b"").decode(errors="replace")}
        result.append(row)
    (output / "network-smokes.json").write_text(json.dumps(result, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    output = args.output.resolve() if args.output else Path(tempfile.mkdtemp(prefix="implementation-audit-"))
    if args.output:
        output.mkdir(exist_ok=False, parents=True)
    print(f"Audit artifacts: {output}", flush=True)
    shutil.copytree(root / "src", output / "src")
    cp = os.pathsep.join(str(p) for p in sorted(root.glob("lib/**/*.jar")))
    classes = output / "bin"
    sources = sorted((output / "src").rglob("*.java"))
    manifest = {"source_sha256": {str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
                "support_sha256": {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in [root / "run.sh", *sorted((root / "dashboard").glob("*.py"))]}}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2))
    subprocess.run(["javac", "-cp", cp, "-d", str(classes), *map(str, sources)], check=True)
    cp += os.pathsep + str(classes)
    base = subprocess.run(["java", "-cp", cp, "test.ModelTests"], capture_output=True, text=True)
    (output / "baseline-tests.txt").write_text(base.stdout + base.stderr)
    print(f"Baseline: exit={base.returncode}, passes={base.stdout.count('  PASS ')}", flush=True)
    subprocess.run(["javac", "-cp", cp, "-d", str(classes), str(Path(__file__).with_name("AuditContracts.java"))], check=True)
    contracts = subprocess.run(["java", "-cp", cp, "AuditContracts", str(output / "contracts")], capture_output=True, text=True)
    (output / "contracts.stdout.txt").write_text(contracts.stdout)
    (output / "contracts.stderr.txt").write_text(contracts.stderr)
    print(contracts.stdout, flush=True)
    integration_result = integration(root, output, cp)
    for row in integration_result:
        print(f"Integration {row['arm']} seed={row['seed']}: {row['errors']}", flush=True)
    edges = edge_integration(output, cp)
    for row in edges:
        print(f"Edge scenario {row['case']}: exit={row['exit']}, assertions={row['assert_lines']}", flush=True)
    py = python_contracts(root, output)
    for row in py:
        print(("PASS " if row["pass"] else "FAIL ") + row["id"] + " | " + row["detail"], flush=True)
    networks = network_smokes(output, cp)
    for row in networks:
        print(f"Network {row['network']} seed={row['seed']}: exit={row['exit']}, timeout={row['timeout']}", flush=True)
    if (base.returncode or contracts.returncode or any(r["errors"] for r in integration_result)
            or any(not r["pass"] for r in py) or any(r["timeout"] or r["exit"] for r in networks)):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
