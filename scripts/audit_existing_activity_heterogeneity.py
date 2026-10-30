#!/usr/bin/env python3
"""Read existing calibration logs for conditional activity inequality; no resimulation or rescoring."""
import os
for key in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:
    os.environ[key]='1'
import argparse
import collections
import concurrent.futures
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from calibration_metrics import gini

ROOT=Path(__file__).resolve().parents[1]
EXCLUDE={'seed','steps','results_subdir','run_id'}


def inspect(item):
    source,job=item
    path=Path(job['run_dir'])/'metrics/calibration_activity.csv'
    a=pd.read_csv(path,usecols=['start','step','agentId','intrinsicOpinion','nPost','nReshare'])
    if int(a.step.max()) != job['steps']:
        raise ValueError('Incomplete calibration window: '+str(path))
    a=a[a.start>=max(0,job['steps']-10000)]
    a=a.groupby('agentId').agg(intrinsicOpinion=('intrinsicOpinion','first'),nPost=('nPost','sum'),nReshare=('nReshare','sum'))
    n=job['n']
    if len(a)!=n or set(a.index)!=set(range(n)):
        raise ValueError('Missing agents, including zero posters: '+str(path))
    bins=np.minimum(((a.intrinsicOpinion.to_numpy()+1)*3.5).astype(int),6)
    pop=np.bincount(bins,minlength=7)
    if (pop==0).any():raise ValueError('Empty opinion bin: '+str(path))
    tokens={k:v for k,v in job['tokens'].items() if k not in EXCLUDE}
    condition=hashlib.sha256(json.dumps(tokens,sort_keys=True).encode()).hexdigest()[:16]
    row=dict(source=source,key=job['key'],phase=job['phase'],seed=job['seed'],steps=job['steps'],n=n,
             condition=condition,network=tokens['network'],fit_mode=tokens.get('fit_mode','raw'),
             init_dist=tokens.get('init_dist','uniform'),valid=job['valid'],loss=job['loss'],
             all_activity_loss=job['all_activity_loss'],original_activity_loss=job['original_activity_loss'],
             network_loss=job['network_loss'],q=job['root']['q'],total_originals=int(a.nPost.sum()),tokens=tokens)
    for name,amounts in [('original',a.nPost.to_numpy()),('all',(a.nPost+a.nReshare).to_numpy())]:
        values=[gini(amounts[bins==b]) for b in range(7)]
        row[name+'_within_gini']=float(np.mean(values))
        row[name+'_overall_gini']=gini(amounts)
        row[name+'_bin_ginis']=values
        row[name+'_zero_fraction']=float((amounts==0).mean())
    return row


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=ROOT/'docs/report/existing-heterogeneity-search-2026-10-30')
    p.add_argument('--workers',type=int,default=4)
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    roots=[ROOT/'results/calibration_raw_reduced_20261029', ROOT/'results/calibration_multinetwork_20261028',ROOT/'results/calibration_uniform_20261028']
    items=[];inventory=[]
    for parent in roots:
        paths=sorted(parent.glob('*/jobs/*.json')) if not (parent/'jobs').exists() else sorted((parent/'jobs').glob('*.json'))
        good=0;failed=0
        for path in paths:
            j=json.loads(path.read_text())
            if j.get('status')=='ok' and j['tokens'].get('init_dist')=='uniform':
                items.append((parent.name,j));good+=1
            else:failed+=1
        inventory.append(dict(source=parent.name,eligible_completed_jobs=good,excluded_failed_or_nonuniform=failed))
    print('Inventory:',inventory,flush=True)
    records=[];errors=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures={pool.submit(inspect,item):item for item in items}
        for future in concurrent.futures.as_completed(futures):
            try:records.append(future.result())
            except Exception as e:
                source,j=futures[future];errors.append(dict(source=source,key=j['key'],error=str(e)))
            if (len(records)+len(errors))%250==0:print('Inspected',len(records),'errors',len(errors),flush=True)
    records.sort(key=lambda r:(r['source'],r['network'],r['phase'],r['condition'],r['seed']))
    frame=pd.DataFrame([{k:(json.dumps(v) if isinstance(v,(list,dict)) else v) for k,v in r.items()} for r in records])
    frame.to_csv(args.output/'per_seed_heterogeneity.csv',index=False)
    source=ROOT/'results/empirical_source_audit'
    empirical=pd.read_parquet(source/'counts.parquet');labels=pd.read_csv(source/'libcon.csv').drop_duplicates('handle').set_index('handle')
    daily=empirical.loc[:,pd.to_datetime(empirical.columns)<'2021-01-08'].mean(axis=1)
    target=float(np.mean([gini(daily.loc[labels.index[labels.ideological_lean_label.str.startswith(str(b))]].to_numpy()) for b in range(1,8)]))
    grouped=collections.defaultdict(list)
    for r in records:
        stage='search' if r['phase']=='pilot' or r['phase'].startswith('bo_') else r['phase']
        grouped[(r['source'],r['network'],r['fit_mode'],r['steps'],stage,r['condition'])].append(r)
    conditions=[]
    for (source,network,mode,steps,stage,condition),rr in grouped.items():
        seeds=[r['seed'] for r in rr]
        if len(seeds)!=len(set(seeds)):raise ValueError('Duplicated seed in condition '+condition)
        row=dict(source=source,network=network,fit_mode=mode,steps=steps,stage=stage,condition=condition,
                 seeds=len(rr),valid_fraction=float(np.mean([r['valid'] for r in rr])),tokens=json.dumps(rr[0]['tokens'],sort_keys=True))
        for key in ['loss','all_activity_loss','original_activity_loss','network_loss','q','original_within_gini','all_within_gini','original_overall_gini','all_overall_gini','original_zero_fraction','all_zero_fraction']:
            row[key]=float(np.mean([r[key] for r in rr]))
            row[key+'_seed_sd']=float(np.std([r[key] for r in rr],ddof=1)) if len(rr)>1 else None
        row['all_gini_target_gap']=abs(row['all_within_gini']-target)
        conditions.append(row)
    c=pd.DataFrame(conditions).sort_values(['source','network','stage','loss'])
    c.to_csv(args.output/'condition_heterogeneity.csv',index=False)
    eligible=c[(c.seeds>=5)&(c.valid_fraction==1)]
    selections=[]
    for (source,network),group in eligible[eligible.stage=='search'].groupby(['source','network']):
        for criterion,column,ascending in [('best_existing_joint_fit','loss',True),('closest_conditional_gini','all_gini_target_gap',True)]:
            row=group.sort_values(column,ascending=ascending).iloc[0].to_dict();row['selection']=criterion;selections.append(row)
    pd.DataFrame(selections).to_csv(args.output/'selected_conditions.csv',index=False)
    raw=eligible[(eligible.fit_mode=='raw')&(eligible.stage=='search')]
    pareto=[]
    for network,group in raw.groupby('network'):
        values=group[['all_activity_loss','network_loss','all_gini_target_gap']].to_numpy()
        for i,(_,r) in enumerate(group.iterrows()):
            dominated=np.any(np.all(values<=values[i],axis=1)&np.any(values<values[i],axis=1))
            if not dominated:pareto.append(r.to_dict())
    pd.DataFrame(pareto).to_csv(args.output/'raw_search_pareto.csv',index=False)
    meta=dict(empirical_equal_bin_gini=target,inventory=inventory,inspected_jobs=len(records),errors=errors,
              eligible_conditions_at_least_five_valid_seeds=len(eligible),raw_search_conditions=len(raw),
              raw_search_within_gini_range=[float(raw.all_within_gini.min()),float(raw.all_within_gini.max())],
              raw_search_original_gini_range=[float(raw.original_within_gini.min()),float(raw.original_within_gini.max())],
              raw_search_conditions_within_gini_above_half=int((raw.all_within_gini>=.5).sum()),
              note='Read-only diagnostic; old objectives remain untouched. Raw and relative studies are separate. Calendar/model windows are not equated; no new scalar loss defined.')
    (args.output/'audit_summary.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(meta,indent=2),flush=True)
    print(pd.DataFrame(selections)[['source','network','selection','seeds','loss','all_within_gini','original_within_gini','q']].to_string(index=False),flush=True)
    if errors:raise SystemExit('Some source logs could not be inspected; see audit_summary.json')


if __name__=='__main__':main()
