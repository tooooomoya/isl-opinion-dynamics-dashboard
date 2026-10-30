#!/usr/bin/env python3
"""Degree/strength-controlled repost diagnostics, outside the fitted objective.

Permute destinations of individual events: exact directed in/out event strengths
are preserved. Parallel ties and self loops are allowed in this configuration null.
"""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
import argparse
import collections
import json
from pathlib import Path
import zipfile
import numpy as np
import pandas as pd
from calibration_metrics import network_metrics, read_graph

ROOT=Path(__file__).resolve().parents[1]


def null_summary(edges,n,repeats=10):
    edges=np.asarray(edges,dtype=np.int64).reshape(-1,3)
    source=np.repeat(edges[:,0],edges[:,2]);dest=np.repeat(edges[:,1],edges[:,2])
    observed=network_metrics(edges,n)
    rng=np.random.default_rng(9871);values=[]
    for repeat in range(repeats):
        d=rng.permutation(dest)
        pairs,counts=np.unique(source*n+d,return_counts=True)
        randomized=np.column_stack([pairs//n,pairs%n,counts])
        # Preserve each node's in/out strength, including nodes absent from the giant component.
        assert np.array_equal(np.bincount(d,minlength=n),np.bincount(dest,minlength=n))
        values.append(network_metrics(randomized,n)['q'])
    mean=float(np.mean(values));sd=float(np.std(values,ddof=1))
    return {'observed':observed,'null_q':values,'null_mean':mean,'null_sd':sd,
            'excess_q':observed['q']-mean,'z_q':(observed['q']-mean)/sd if sd else None,
            'null_definition':'directed event-stub permutation; exact in/out strengths; loops/parallel events allowed'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',type=Path,default=ROOT/'results/calibration_20261027')
    p.add_argument('--output',type=Path,default=ROOT/'docs/report/bayesian-calibration-2026-10-27/network_null.json')
    p.add_argument('--empirical-only',action='store_true');p.add_argument('--repeats',type=int,default=10)
    args=p.parse_args();out={}
    with zipfile.ZipFile(ROOT/'results/empirical_source_audit/conover.zip') as z:
        n=len(z.read('retweet.nodes').decode().splitlines())
        counter=collections.Counter(tuple(map(int,row.split('\t')[:2])) for row in z.read('retweet.edgelist').decode().splitlines())
    out['empirical']=null_summary([(a,b,w) for (a,b),w in counter.items()],n,args.repeats)
    print('empirical',out['empirical'],flush=True)
    if not args.empirical_only and (args.run/'confirm.json').exists():
        candidates=json.loads((args.run/'confirm.json').read_text())
        for i,row in enumerate(sorted(candidates,key=lambda r:r['loss'])):
            results=[]
            available=[k for k in row['job_keys'] if json.loads((args.run/'jobs'/f'{k}.json').read_text())['status']=='ok']
            keys=sorted(available,key=lambda k:json.loads((args.run/'jobs'/f'{k}.json').read_text())['seed'])[:3]
            for key in keys:
                job=json.loads((args.run/'jobs'/f'{key}.json').read_text());run=Path(job['run_dir'])
                end=job['steps'];counter=collections.Counter()
                for step in [end-5000,end]:
                    for s,d,w in read_graph(run/f'metrics/calibration_root_{step}.csv'):counter[(int(s),int(d))]+=int(w)
                results.append(null_summary([(s,d,w) for (s,d),w in counter.items()],job['n'],args.repeats))
            out[f'C{i+1}']=results;print('candidate',i+1,'done',flush=True)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(out,indent=2)+'\n')


if __name__=='__main__':main()
