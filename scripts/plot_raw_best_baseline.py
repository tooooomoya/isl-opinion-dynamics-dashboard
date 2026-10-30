#!/usr/bin/env python3
"""Reproduce baseline-style figures and selection histories for raw-fit winners."""
import os
for key in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:
    os.environ[key]='1'
import argparse
import json
from pathlib import Path
import subprocess
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
ACTIONS=['Post','Like','Repost','Rewire']
COUNTS=['nPost','nLike','nReshare','nRewire']
QCOLS=['qPost','qLike','qReshare','qRewire']
COLORS=['#2878b5','#e69f00','#17866b','#b279a2']
NETWORKS=[('hkshuf','HK-shuffled'),('random','Random (ER)'),('dcsbm','DC-SBM')]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,default=ROOT/'results/calibration_raw_reduced_20261029')
    parser.add_argument('--output',type=Path,default=ROOT/'docs/report/raw-best-snapshots-2026-10-30')
    parser.add_argument('--skip-baseline',action='store_true')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    columns=[];timelines=[];group_timelines=[];summaries=[];provenance={}
    for network,label in NETWORKS:
        directory=args.run/network
        validation=json.loads((directory/'validation.json').read_text())
        selected=next(row for row in validation if row['phase']=='horizon40k')
        jobs=sorted([json.loads((directory/'jobs'/f'{key}.json').read_text()) for key in selected['job_keys']],key=lambda j:j['seed'])
        assert len(jobs)==5 and all(j['status']=='ok' and j['steps']==40000 and j['tokens']['fit_mode']=='raw' for j in jobs)
        assert all(j['point']==jobs[0]['point'] for j in jobs)
        tokens=jobs[0]['tokens']
        columns.append(dict(label=label,dead_after=tokens['dead_after'],fit_mode='raw',representative_seed=jobs[0]['seed'],runs=[j['run_dir'] for j in jobs]))
        provenance[network]=dict(job_keys=[j['key'] for j in jobs],seeds=[j['seed'] for j in jobs],tokens=tokens,
                                 representative_key=jobs[0]['key'],representative_seed=jobs[0]['seed'],steps=40000,
                                 baseline_window_steps=5000,repost_definition='immediate author/resharer pairs from reactions_conv.csv, final 5000 steps; distinct from root-attributed calibration graph')
        for job in jobs:
            run=Path(job['run_dir']);actions=pd.read_csv(run/'metrics/agent_actions.csv')
            snap=pd.read_csv(run/'degrees/agent_snapshot_final.csv').sort_values('agentId')
            n=len(snap);assert n==job['n']
            q=pd.read_csv(run/'degrees/q_table_final.csv').query('state==0').sort_values('agentId')
            assert job['tokens']['learner']=='bandit' and len(q)==n
            counts=actions.groupby('step')[COUNTS+['nLikeGated']].sum()
            fractions=counts[COUNTS].div(counts[COUNTS].sum(axis=1),axis=0)
            for col in COUNTS:counts[col+'_share']=fractions[col]
            counts['network']=network;counts['seed']=job['seed'];timelines.append(counts.reset_index())
            x=snap.set_index('agentId').intrinsicOpinion
            joined=actions.join(x,on='agentId')
            masks=[('Neutral',joined.intrinsicOpinion.abs()<1/3),
                   ('Moderate',(joined.intrinsicOpinion.abs()>=1/3)&(joined.intrinsicOpinion.abs()<2/3)),
                   ('Extreme',joined.intrinsicOpinion.abs()>=2/3)]
            for group,mask in masks:
                c=joined[mask].groupby('step')[COUNTS].sum()
                c=c.div(c.sum(axis=1),axis=0);c['group']=group;c['network']=network;c['seed']=job['seed'];group_timelines.append(c.reset_index())
            tail=actions[actions.step>35000][COUNTS].sum().to_numpy()
            check=actions[actions.step>30000][COUNTS].sum()
            assert int(check['nPost'])==job['action_counts']['nPost']
            assert int(check['nReshare'])==job['action_counts']['nReshare']
            qv=q[QCOLS].to_numpy();best=qv.argmax(axis=1)
            ties=(qv==qv.max(axis=1,keepdims=True)).sum(axis=1)>1
            record=dict(network=network,seed=job['seed'],tie_fraction=float(ties.mean()),q=job['root']['q'])
            for i,action in enumerate(ACTIONS):
                record['greedy_'+action]=float(((best==i)&~ties).mean())
                record['observed_'+action]=float(tail[i]/tail.sum())
            summaries.append(record)
    (args.output/'baseline_columns.json').write_text(json.dumps(columns,indent=2)+'\n')
    (args.output/'selected_runs.json').write_text(json.dumps(provenance,indent=2)+'\n')
    timeline=pd.concat(timelines,ignore_index=True);groups=pd.concat(group_timelines,ignore_index=True);summary=pd.DataFrame(summaries)
    timeline.to_csv(args.output/'strategy_history.csv',index=False)
    groups.to_csv(args.output/'strategy_history_by_opinion.csv',index=False)
    summary.to_csv(args.output/'strategy_final_summary.csv',index=False)
    fig,axes=plt.subplots(3,3,figsize=(16,12),layout='constrained')
    for col,(network,label) in enumerate(NETWORKS):
        t=timeline[timeline.network==network]
        ax=axes[0,col]
        for count,action,color in zip(COUNTS,ACTIONS,COLORS):
            s=t.groupby('step')[count+'_share'].agg(['mean','std'])*100
            ax.plot(s.index,s['mean'],label=action,color=color,lw=1.7)
            ax.fill_between(s.index,(s['mean']-s['std']).clip(lower=0),(s['mean']+s['std']).clip(upper=100),color=color,alpha=.12)
        ax.set_title(label+'\nA  Observed action-selection history');ax.set_ylim(0,100);ax.set_ylabel('% decisions');ax.legend(fontsize=8,ncol=2)
        ax=axes[1,col]
        for group,color in [('Neutral','#777777'),('Moderate','#dfa34a'),('Extreme','#b33d4b')]:
            s=groups[(groups.network==network)&(groups.group==group)].groupby('step')[['nPost','nReshare']].mean()*100
            ax.plot(s.index,s.nPost,color=color,lw=1.6,label=group+' / Post')
            ax.plot(s.index,s.nReshare,color=color,lw=1.6,ls='--',label=group+' / Repost')
        ax.set_title('B  Posting and reposting by opinion');ax.set_ylabel('% decisions within opinion group');ax.set_ylim(bottom=0)
        ax.legend(fontsize=7,ncol=2)
        ax=axes[2,col];rows=summary[summary.network==network];loc=np.arange(4)
        for offset,prefix,label_,hatch in [(-.2,'greedy_','Final greedy Q preference',None),(.2,'observed_','Observed choices: final 5k','//')]:
            values=rows[[prefix+a for a in ACTIONS]].to_numpy()*100
            ax.bar(loc+offset,values.mean(axis=0),width=.38,yerr=values.std(axis=0,ddof=1),capsize=3,color=COLORS,alpha=1 if prefix=='greedy_' else .55,hatch=hatch,label=label_)
        ax.set_xticks(loc,ACTIONS);ax.set_ylim(0,105);ax.set_ylabel('% agents (greedy) / % decisions (observed)');ax.set_title('C  Final preference versus actual choices');ax.legend(fontsize=7)
        for row in [0,1]:axes[row,col].set_xlabel('Simulation step (500-step intervals)');axes[row,col].grid(alpha=.15)
    fig.suptitle('Best joint-fit raw-similarity condition — strategy selection through time\nFive 40,000-step runs per network; mean across seeds; A shading / C error bars = ±1 seed SD',fontsize=14)
    fig.supxlabel('Post / Repost are action choices. Like includes gated no-ops. Final greedy preference uses bandit state 0, without availability constraints; ties are separate.\nNeutral: |x|<1/3; Moderate: 1/3≤|x|<2/3; Extreme: |x|≥2/3. Continuing exploration means stable shares do not prove an absorbing strategy.',fontsize=9)
    fig.savefig(args.output/'baseline_raw_best_strategy_history.png',dpi=180);plt.close(fig)
    means=summary.groupby('network').mean(numeric_only=True)
    (args.output/'strategy_means.json').write_text(means.to_json(orient='index',indent=2)+'\n')
    if not args.skip_baseline:
        env=os.environ.copy();env.update(PLOT_COLS=str((args.output/'baseline_columns.json').resolve()),
            PLOT_TITLE='Best joint-fit raw-similarity condition | columns = initial network families | 5 seeds, 40,000 steps | feed = Chrono / For You / Trend, one-third each',
            PLOT_EXPORT_PREFIX=str((args.output/'baseline_raw_best').resolve()))
        subprocess.run([sys.executable,str(ROOT/'scripts/plot_std.py'),str((args.output/'baseline_raw_best_fit.png').resolve()),'hkshuf','raw_best'],cwd=ROOT,env=env,check=True)
    print(means[[c for c in means if c.startswith('observed_') or c.startswith('greedy_')]].round(4).to_string())
    print('Output:',args.output)


if __name__=='__main__':main()
