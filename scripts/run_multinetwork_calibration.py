#!/usr/bin/env python3
"""Independent uniform-opinion calibration on HK-shuffled, random and DC-SBM.

Shares a fixed total worker budget across families. Each family performs its own
pilot, RF/EI search, confirmation, transfer checks, report export and network nulls.
Existing single-network study outputs are preserved and are not training data.
--compact-raw uses raw identity fit and omits the blanket validation matrix.
"""
import argparse
import concurrent.futures
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def write(path, value):
    temporary = path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,indent=2)+'\n')
    temporary.replace(path)


def stamp():
    return time.strftime('%Y-%m-%d %H:%M:%S')


def run_family(network, workers, args):
    run=args.output/network
    report=args.report/network
    logs=args.logs/network
    logs.mkdir(parents=True,exist_ok=True)
    report.mkdir(parents=True,exist_ok=True)
    run.mkdir(parents=True,exist_ok=True)
    status_path=args.output/f'status_{network}.json'
    study = 'uniform-raw-reduced-v5' if args.reduced_raw else ('uniform-raw-v4' if args.compact_raw else 'uniform-v3')
    steps = '20000' if args.compact_raw else '40000'
    commands=[
        ('full',['bayesian_calibration.py','--study',study,'--phase','compact' if args.compact_raw else 'full','--network',network,
                 '--output',str(run),'--workers',str(workers),'--pilot',str(args.pilot),'--bo',str(args.bo),
                 '--search-seeds','5','--confirm-seeds','10','--search-steps',steps,'--confirm-steps',steps]),
        ('analysis',['analyze_bayesian_calibration.py','--run',str(run),'--output',str(report),'--surrogate-audit']),
        ('network_null',['calibration_network_null.py','--run',str(run),'--output',str(report/'network_null.json')]),
    ]
    for stage, command in commands:
        status={'network':network,'stage':stage,'state':'running','workers':workers,'local_time':stamp()}
        print(status,flush=True)
        with (logs/(stage+'.out')).open('a') as stream:
            process=subprocess.Popen([sys.executable,'-u',str(ROOT/'scripts'/command[0]),*command[1:]],
                                     cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
            status['pid']=process.pid;write(status_path,status)
            code=process.wait()
        if code:
            status.update(state='failed',returncode=code,local_time=stamp())
            write(status_path,status)
            return status
    status={'network':network,'stage':'all','state':'complete','local_time':stamp()}
    write(status_path,status);write(run/'PIPELINE_COMPLETE.json',status)
    print(status,flush=True)
    return status


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=None)
    parser.add_argument('--report',type=Path,default=None)
    parser.add_argument('--logs',type=Path,default=None)
    parser.add_argument('--workers',type=int,default=None,help='Total across all network families')
    parser.add_argument('--pilot',type=int,default=None)
    parser.add_argument('--bo',type=int,default=None)
    parser.add_argument('--compact-raw', action='store_true', help='Separate raw-fit study: 48 pilot + 16 BO; 20k search and confirmation; paired 40k horizon check')
    parser.add_argument('--reduced-raw', action='store_true', help='13-parameter raw-fit compact search; 12 fixed inputs, balanced feed mixture')
    args=parser.parse_args()
    if args.reduced_raw: args.compact_raw = True
    suffix = 'raw_reduced_20261029' if args.reduced_raw else ('raw_20261029' if args.compact_raw else 'multinetwork_20261028')
    if args.output is None: args.output = ROOT/'results'/('calibration_'+suffix)
    if args.logs is None: args.logs = ROOT/'logs'/('calibration_'+suffix)
    if args.report is None: args.report = ROOT/'docs/report'/('bayesian-calibration-'+suffix.replace('_','-')) if args.compact_raw else ROOT/'docs/report/bayesian-calibration-multinetwork-2026-10-28'
    if args.workers is None: args.workers = 12 if args.compact_raw else 24
    if args.pilot is None: args.pilot = 48 if args.compact_raw else 128
    if args.bo is None: args.bo = 16 if args.compact_raw else 64
    for field in ['output','report','logs']:
        setattr(args,field,getattr(args,field).resolve())
        getattr(args,field).mkdir(parents=True,exist_ok=True)
    lock=(args.output/'pipeline.lock').open('a')
    try:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit('This multi-network pipeline is already running')
    networks=['hkshuf','random','dcsbm']
    if args.workers<len(networks):
        raise SystemExit('Need at least one worker for each network family')
    allocation={network:args.workers//3+(i<args.workers%3) for i,network in enumerate(networks)}
    design={'networks':networks,'worker_allocation':allocation,'pilot_settings_per_network':args.pilot,
            'bo_settings_per_network':args.bo,'search_seeds_per_setting':5,'confirmation_seeds':10,
            'search_steps':40000,'confirmation_steps':40000,'initial_opinions':'iid uniform [-1,1]',
            'parameter_policy':'independent 25-dimensional searches; shared initial design and search seed numbers',
            'max_main_simulations_per_network':(args.pilot+args.bo)*5+40+96}
    if args.compact_raw:
        design.update(study='uniform-raw-v4', identity_reward='raw mean similarity',
                      search_steps=20000, confirmation_steps=20000, finalists_per_network=2,
                      horizon_steps=40000, horizon_seeds=5, horizon_finalists_per_network=1,
                      max_main_simulations_per_network=(args.pilot+args.bo)*5+20+5,
                      parameter_policy='independent 25-dimensional screening; 8 anchors + space-filling pilot; no old observations; no blanket validation matrix')
    if args.reduced_raw:
        from bayesian_calibration import REDUCED_STUDY, REDUCED_FIXED, search_space
        design.update(study=REDUCED_STUDY,
                      search_parameters=[d.name for d in search_space(REDUCED_STUDY)],
                      fixed_parameters=REDUCED_FIXED,
                      parameter_policy='independent 13-dimensional screening; 8 homophily/reward anchors + 40 Sobol settings; fixed equal Chrono/For You/Trend; no old observations')
    design_path=args.output/'study_design.json'
    if design_path.exists() and json.loads(design_path.read_text())!=design:
        raise SystemExit('Frozen multi-network design differs; use a new output directory')
    write(design_path,design)
    provenance=args.output/'workflow_sources'
    if not provenance.exists():
        provenance.mkdir()
        names=['run_multinetwork_calibration.py','bayesian_calibration.py','calibration_metrics.py',
               'analyze_bayesian_calibration.py','calibration_network_null.py']
        for name in names:shutil.copy(ROOT/'scripts'/name,provenance/name)
        write(args.output/'workflow_manifest.json',{'created_local':stamp(),
              'sources':{name:hashlib.sha256((provenance/name).read_bytes()).hexdigest() for name in names}})
    (args.logs/'pipeline.pid').write_text(str(os.getpid())+'\n')
    write(args.output/'pipeline_status.json',{'state':'running','started_local':stamp(),'pid':os.getpid()})
    results=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures={pool.submit(run_family,n,allocation[n],args):n for n in networks}
        for future in concurrent.futures.as_completed(futures):
            network=futures[future]
            try:result=future.result()
            except Exception as error:
                result={'network':network,'state':'failed','error':f'{type(error).__name__}: {error}'}
                write(args.output/f'status_{network}.json',result)
            results.append(result)
    state='complete' if all(r['state']=='complete' for r in results) else 'failed'
    status={'state':state,'finished_local':stamp(),'families':results}
    write(args.output/'pipeline_status.json',status)
    if state=='complete':write(args.output/'PIPELINE_COMPLETE.json',status)
    print(status,flush=True)
    raise SystemExit(0 if state=='complete' else 1)


if __name__=='__main__':main()
