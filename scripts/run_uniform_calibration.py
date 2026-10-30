#!/usr/bin/env python3
"""Run the uniform study, then export its figures and held-out network nulls.

All stages are resumable; stage failures are recorded and exit nonzero. Invoke
with venv/bin/python. The main run's COMPLETE.json precedes this pipeline's
PIPELINE_COMPLETE.json, which also requires the analysis and null diagnostics.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers', type=int, default=24)
    args = parser.parse_args()
    run = ROOT/'results/calibration_uniform_20261028'
    report = ROOT/'docs/report/bayesian-calibration-uniform-2026-10-28'
    logs = ROOT/'logs/calibration_uniform_20261028'
    run.mkdir(parents=True, exist_ok=True);logs.mkdir(parents=True, exist_ok=True)
    report.mkdir(parents=True, exist_ok=True)
    (logs/'pipeline.pid').write_text(str(os.getpid())+'\n')
    stages = [
        ('full', ['bayesian_calibration.py', '--study', 'uniform-v3', '--phase', 'full',
                  '--output', str(run), '--workers', str(args.workers), '--pilot', '128', '--bo', '64']),
        ('analysis', ['analyze_bayesian_calibration.py', '--run', str(run), '--output', str(report), '--surrogate-audit']),
        ('network_null', ['calibration_network_null.py', '--run', str(run), '--output', str(report/'network_null.json')]),
    ]
    for name, command in stages:
        status = {'stage': name, 'state':'running', 'local_time':time.strftime('%Y-%m-%d %H:%M:%S')}
        (run/'pipeline_status.json').write_text(json.dumps(status, indent=2)+'\n')
        print(status, flush=True)
        with (logs/(name+'.out')).open('a') as stream:
            result = subprocess.run([sys.executable, '-u', str(ROOT/'scripts'/command[0]), *command[1:]],
                                    cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
        if result.returncode:
            status.update(state='failed', returncode=result.returncode)
            (run/'pipeline_status.json').write_text(json.dumps(status, indent=2)+'\n')
            raise SystemExit(result.returncode)
    status = {'stage':'all', 'state':'complete', 'local_time':time.strftime('%Y-%m-%d %H:%M:%S')}
    (run/'pipeline_status.json').write_text(json.dumps(status, indent=2)+'\n')
    (run/'PIPELINE_COMPLETE.json').write_text(json.dumps(status, indent=2)+'\n')
    print(status, flush=True)


if __name__ == '__main__':
    main()
