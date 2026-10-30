#!/usr/bin/env python3
"""Read-only network, action-policy and exploratory parameter diagnostics."""
import os
for key in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:
    os.environ[key]='1'
import collections
import json
from pathlib import Path
import random

import igraph as ig
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.ensemble import RandomForestRegressor
from sklearn.inspection import permutation_importance
from sklearn.model_selection import KFold

from bayesian_calibration import ROOT,NAMES,SPACE
from calibration_metrics import network_metrics
from plot_uniform_best_fit import baseline_tokens

PARENT=ROOT/'results/calibration_multinetwork_20261028'
OUT=ROOT/'docs/report/fit-mechanisms-2026-10-29'
ACTIONS=['Post','Like','Repost','Rewire']
COLS=['nPost','nLike','nReshare','nRewire']
QCOLS=['qPost','qLike','qReshare','qRewire']
COLORS=['#d87820','#529d46','#8e64b7','#5b8dc0']


def write(name,value):
    (OUT/name).write_text(json.dumps(value,indent=2,default=lambda x:x.tolist() if isinstance(x,np.ndarray) else x.item())+'\n')


def load_jobs(directory):
    rows=[]
    for path in (directory/'jobs').glob('*.json'):
        try:rows.append(json.loads(path.read_text()))
        except FileNotFoundError:pass
    return rows


def complete_groups(jobs):
    groups=collections.defaultdict(list)
    for j in jobs:
        if j['phase']=='pilot' or j['phase'].startswith('bo_'):
            groups[tuple(j['point'])].append(j)
    return [sorted(v,key=lambda j:j['seed']) for v in groups.values()
            if len(v)==5 and all(j['status']=='ok' and j['valid'] for j in v)]


def network_snapshot(condition):
    # Prespecified representative: lowest seed, not the prettiest realization.
    job=condition[0];run=Path(job['run_dir']);snap=pd.read_csv(run/'degrees/agent_snapshot_final.csv').sort_values('agentId')
    n=len(snap);x=snap.intrinsicOpinion.to_numpy()
    initial=pd.read_csv(run/'degrees/edges_t0.csv').to_numpy(dtype=int)
    final=pd.read_csv(run/'degrees/edges_final.csv').to_numpy(dtype=int)
    end=job['steps'];window=[end-5000,end]
    root=pd.concat([pd.read_csv(run/f'metrics/calibration_root_{step}.csv') for step in window]).groupby(['source','actor'],as_index=False)['count'].sum()
    repost=root.to_numpy(dtype=int)
    assert len(final)==n*job['tokens']['start_deg']
    assert int(root['count'].sum())==job['action_counts']['nReshare']
    union=ig.Graph(n=n,edges=final.tolist()+repost[:,:2].tolist(),directed=False)
    union.es['weight']=[1.]*len(final)+np.log1p(repost[:,2]).tolist()
    union.simplify(combine_edges={'weight':'sum'})
    rng=np.random.default_rng(1729)
    ig.set_random_number_generator(random.Random(1729))
    layout=np.array(union.layout_fruchterman_reingold(weights='weight',niter=500,seed=rng.normal(size=(n,2)).tolist()).coords)
    initial_graph=ig.Graph(n=n,edges=initial.tolist(),directed=False)
    initial_graph.simplify()
    initial_layout=np.array(initial_graph.layout_fruchterman_reingold(niter=400,seed=rng.normal(size=(n,2)).tolist()).coords)
    fig,axes=plt.subplots(1,3,figsize=(17,6),layout='constrained')
    sizes=6+50*snap.followerCount.to_numpy()/max(1,snap.followerCount.max())
    specs=[('Initial follow network',initial,np.ones(len(initial))),('Final follow network',final,np.ones(len(final))),
           ('Root repost network: final 10k steps',repost[:,:2],repost[:,2])]
    metrics={}
    for ax,(title,edges,weights) in zip(axes,specs):
        coords=initial_layout if title=='Initial follow network' else layout
        width=.18 if title!='Root repost network: final 10k steps' else .12+.16*np.log1p(weights)
        ax.add_collection(LineCollection(coords[edges],colors='#475569',alpha=.035,linewidths=width,rasterized=True))
        points=ax.scatter(coords[:,0],coords[:,1],c=x,cmap='coolwarm',vmin=-1,vmax=1,s=sizes,edgecolors='none',zorder=2,rasterized=True)
        graph=ig.Graph(n=n,edges=edges.tolist(),directed=True);graph.es['weight']=weights.tolist()
        q_sign=graph.modularity((x>=0).astype(int).tolist(),weights='weight',directed=True)
        ax.set_title(f'{title}\n{len(edges):,} ties; opinion-sign Q={q_sign:.3f}',fontsize=11)
        ax.autoscale();ax.set_aspect('equal');ax.axis('off')
        graph.vs['opinion']=x.tolist();graph.vs['agentId']=list(range(n))
        graph.vs['layout_x']=coords[:,0].tolist();graph.vs['layout_y']=coords[:,1].tolist()
        filename=['initial_follow','final_follow','root_repost'][len(metrics)]
        graph.write_graphml(str(OUT/(filename+'.graphml')))
        metrics[filename]={'ties':len(edges),'weight_sum':int(sum(weights)),'q_sign':q_sign}
    fig.colorbar(points,ax=axes,shrink=.65,label='Fixed opinion: liberal (-1) to conservative (+1)')
    fig.suptitle(f'HK-shuffled condition — representative seed {job["seed"]}, n={n}',fontsize=14)
    fig.supxlabel('All ties shown; initial graph uses its own topology layout. Final follow/repost share a topology-derived layout; opinion is used only for color.\nNode size increases with final follower count. Follow: follower → followee; repost: root author → reposter. Arrowheads omitted.',fontsize=9)
    fig.savefig(OUT/'network_snapshots.png',dpi=200);plt.close(fig)
    write('network_snapshot_metrics.json',{'seed':job['seed'],'job_key':job['key'],'graphs':metrics,'detected_repost':job['root']})


def strategy_diagnostics(condition):
    rows=[];agents=[];binshares=[];timelines=[]
    for job in condition:
        run=Path(job['run_dir']);n=job['n'];end=job['steps']
        snap=pd.read_csv(run/'degrees/agent_snapshot_final.csv').sort_values('agentId')
        q=pd.read_csv(run/'degrees/q_table_final.csv').query('state==0').sort_values('agentId')
        assert job['tokens']['learner']=='bandit' and len(q)==n
        values=q[QCOLS].to_numpy();best=values.argmax(1);ties=(values==values.max(1,keepdims=True)).sum(1)>1
        best[ties]=4
        actions=pd.read_csv(run/'metrics/agent_actions.csv')
        tail=actions[actions.step>end-10000]
        def summed(a):return a.groupby('agentId')[COLS].sum().reindex(range(n),fill_value=0).to_numpy()
        counts=summed(tail);first=summed(tail[tail.step<=end-5000]);last=summed(tail[tail.step>end-5000])
        assert int(counts[:,0].sum())==job['action_counts']['nPost']
        assert int(counts[:,2].sum())==job['action_counts']['nReshare']
        valid=(first.sum(1)>0)&(last.sum(1)>0)
        total_variation=.5*np.abs(first/np.maximum(first.sum(1,keepdims=True),1)-last/np.maximum(last.sum(1,keepdims=True),1)).sum(1)
        preferred=np.bincount(best,minlength=5)/n
        actual=counts.sum(0)/counts.sum()
        row={'seed':job['seed'],'stable_dominant_action_fraction':float(np.mean(first[valid].argmax(1)==last[valid].argmax(1))),
             'median_window_total_variation':float(np.median(total_variation[valid])), 'tie_fraction':preferred[4]}
        for k,label in enumerate(ACTIONS):row['preferred_'+label.lower()]=preferred[k];row['actual_'+label.lower()]=actual[k]
        rows.append(row)
        x=snap.intrinsicOpinion.to_numpy();bins=np.minimum(((x+1)*3.5).astype(int),6)
        for b in range(7):
            c=counts[bins==b].sum(0);binshares.append({'seed':job['seed'],'bin':b,**dict(zip(ACTIONS,c/max(1,c.sum())))})
        timeline=actions.groupby('step')[COLS].sum();timeline=timeline.div(timeline.sum(axis=1),axis=0)
        timeline['seed']=job['seed'];timelines.append(timeline.reset_index())
        for i in range(n):
            agents.append({'seed':job['seed'],'agentId':i,'opinion':x[i],'preferred_action':(ACTIONS+['Tied'])[best[i]],
                           'dominant_last_10k':ACTIONS[counts[i].argmax()], 'window_total_variation':total_variation[i],
                           **dict(zip(QCOLS,values[i])),**{a+'_share':counts[i,k]/max(1,counts[i].sum()) for k,a in enumerate(ACTIONS)}})
    frame=pd.DataFrame(rows);frame.to_csv(OUT/'strategy_summary.csv',index=False)
    pd.DataFrame(agents).to_csv(OUT/'agent_strategies.csv',index=False)
    pd.DataFrame(binshares).to_csv(OUT/'strategy_by_opinion.csv',index=False)
    timeline=pd.concat(timelines);timeline.to_csv(OUT/'strategy_time_series.csv',index=False)
    fig,axes=plt.subplots(2,2,figsize=(12,9),layout='constrained')
    for ax,prefix,title in zip(axes[0],['preferred_','actual_'],['Final unconstrained argmax Q (bandit state 0)','Observed action share: final 10k steps']):
        vals=frame[[prefix+a.lower() for a in ACTIONS]].to_numpy()*100
        ax.bar(ACTIONS,vals.mean(0),yerr=vals.std(0,ddof=1),color=COLORS,capsize=3)
        for i,v in enumerate(vals.mean(0)):ax.text(i,v+1,f'{v:.2f}%',ha='center',fontsize=9)
        ax.set_ylim(0,110);ax.set_ylabel('% agents' if prefix=='preferred_' else '% decisions');ax.set_title(title,fontsize=11)
    b=pd.DataFrame(binshares).groupby('bin')[ACTIONS].mean();bottom=np.zeros(7)
    for action,color in zip(ACTIONS,COLORS):
        axes[1,0].bar(range(7),100*b[action],bottom=bottom,label=action,color=color);bottom+=100*b[action]
    axes[1,0].set_xticks(range(7),['VL','L','SL','Neutral','SC','C','VC']);axes[1,0].set_ylabel('% decisions');axes[1,0].set_title('Observed action mix by opinion (five-seed mean)')
    mean=timeline.groupby('step')[COLS].mean()
    for col,action,color in zip(COLS,ACTIONS,COLORS):axes[1,1].plot(mean.index,100*mean[col],label=action,color=color)
    axes[1,1].set_xlabel('Simulation step');axes[1,1].set_ylabel('% decisions');axes[1,1].set_title('Action mix through time');axes[1,1].legend(fontsize=8)
    fig.suptitle('Five-seed strategy diagnostics — ongoing exploration means no absorbing strategy',fontsize=13)
    fig.savefig(OUT/'strategy_ratios.png',dpi=190);plt.close(fig)
    return frame.mean(numeric_only=True).to_dict()


def bh(p):
    p=np.asarray(p);order=np.argsort(p);adjusted=p[order]*len(p)/np.arange(1,len(p)+1)
    result=np.empty(len(p));result[order]=np.minimum(1,np.minimum.accumulate(adjusted[::-1])[::-1]);return result


def importance_diagnostics(all_jobs):
    metrics=[];importances=[];associations=[];datasets=[]
    for network,jobs in all_jobs.items():
        design=json.loads((PARENT/network/'pilot_design.json').read_text());sobol={tuple(p) for p in design[28:]}
        groups=[v for v in complete_groups(jobs) if v[0]['phase']=='pilot' and tuple(v[0]['point']) in sobol]
        x=np.array([v[0]['point'] for v in groups],float)
        for i,dim in enumerate(SPACE):
            if dim.prior=='log-uniform':x[:,i]=np.log(x[:,i])
        dataset=[{'network':network,**dict(zip(NAMES,v[0]['point'])),
                  **{k:np.mean([j[k] for j in v]) for k in ['original_activity_loss','all_activity_loss','network_loss']}} for v in groups]
        datasets.extend(dataset)
        print('importance',network,'complete independent sampled settings',len(groups),flush=True)
        for outcome in ['original_activity_loss','all_activity_loss','network_loss']:
            raw=np.array([r[outcome] for r in dataset]);y=np.log1p(raw)
            cv=KFold(4,shuffle=True,random_state=1729);pred=np.empty(len(y));base=np.empty(len(y));fold_importance=[]
            for fold,(train,test) in enumerate(cv.split(x)):
                forest=RandomForestRegressor(n_estimators=120,min_samples_leaf=3,random_state=1729,n_jobs=1)
                forest.fit(x[train],y[train]);pred[test]=forest.predict(x[test]);base[test]=y[train].mean()
                perm=permutation_importance(forest,x[test],y[test],scoring='neg_mean_squared_error',n_repeats=5,random_state=1730+fold,n_jobs=1)
                fold_importance.extend(perm.importances.T)
            error=np.mean((pred-y)**2);baseline=np.mean((base-y)**2)
            skill=1-error/baseline
            metrics.append({'network':network,'outcome':outcome,'n_settings':len(y),'target':'log1p(mean five-seed component loss)',
                            'out_of_fold_rmse':np.sqrt(error),'constant_rmse':np.sqrt(baseline),'skill_vs_constant':skill})
            a=np.asarray(fold_importance)
            for i,name in enumerate(NAMES):importances.append({'network':network,'outcome':outcome,'parameter':name,
                    'heldout_mse_increase':a[:,i].mean(),'permutation_spread':a[:,i].std(ddof=1),'cv_skill':skill})
            tests=[spearmanr(x[:,i],raw) for i in range(len(NAMES))];q=bh([t.pvalue for t in tests])
            for i,name in enumerate(NAMES):associations.append({'network':network,'outcome':outcome,'parameter':name,
                'spearman_rho':tests[i].statistic,'p':tests[i].pvalue,'q_within_network_outcome':q[i]})
            print(network,outcome,'CV skill',round(skill,3),flush=True)
    pd.DataFrame(datasets).to_csv(OUT/'importance_input_settings.csv',index=False)
    pd.DataFrame(metrics).to_csv(OUT/'importance_cross_validation.csv',index=False)
    pd.DataFrame(importances).to_csv(OUT/'parameter_importance.csv',index=False)
    pd.DataFrame(associations).to_csv(OUT/'parameter_associations.csv',index=False)
    for outcome,filename,title in [
        ('original_activity_loss','parameter_importance.png','Exploratory original-post fit importance'),
        ('network_loss','network_parameter_importance.png','Which parameters predict repost-network fit?')]:
        fig,axes=plt.subplots(1,3,figsize=(15,5.8),layout='constrained')
        for ax,network in zip(axes,['hkshuf','random','dcsbm']):
            data=pd.DataFrame(importances);data=data[(data.network==network)&(data.outcome==outcome)].nlargest(8,'heldout_mse_increase').sort_values('heldout_mse_increase')
            ax.barh(data.parameter,data.heldout_mse_increase,xerr=data.permutation_spread,color='#547c9d',alpha=.8)
            ax.axvline(0,color='grey',lw=.8);ax.set_title(f'{network}; CV skill={data.cv_skill.iloc[0]:.2f}',fontsize=11)
            ax.set_xlabel('Held-out MSE increase after permutation\n(error bars: variation across folds/permutations)',fontsize=8)
        fig.suptitle(title+' — initial Sobol settings only; not causal effects',fontsize=12)
        fig.savefig(OUT/filename,dpi=180);plt.close(fig)
    return metrics,associations


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    all_jobs={n:load_jobs(PARENT/n) for n in ['hkshuf','random','dcsbm']}
    candidates=complete_groups(all_jobs['hkshuf'])
    condition=min(candidates,key=lambda v:np.mean([j['original_activity_loss'] for j in v]))
    write('selected_condition.json',{'selection':'Lowest mean original-only activity loss among complete valid five-seed HK-shuffled search groups',
          'keys':[j['key'] for j in condition],'representative_seed':condition[0]['seed'],'point':condition[0]['point'],
          'tokens':condition[0]['tokens'],'original_ratios_mean':np.mean([j['original_neutral_ratios'] for j in condition],axis=0),
          'primary_event_mapping':'original+repost; original-only selection here is an explicit diagnostic, not a changed calibration objective'})
    network_snapshot(condition);strategy=strategy_diagnostics(condition)
    print('Networks and strategy figures exported',flush=True)
    ignore={'seed','results_subdir','run_id','steps','metrics_every','metrics_heavy_every','calibration_log','log_gexf','log_repost_cascade','log_post_lifespan'}
    tokens={k:v for k,v in condition[0]['tokens'].items() if k not in ignore};baseline=baseline_tokens(tokens)
    comparison=[{'parameter':k,'standing_hkshuf_foryou':baseline[k],'selected':v,'changed':baseline[k]!=v} for k,v in tokens.items()]
    pd.DataFrame(comparison).to_csv(OUT/'parameter_settings.csv',index=False)
    metrics,associations=importance_diagnostics(all_jobs)
    lines=['# Network, strategies, and parameter diagnostics','',
           'Selected the strongest complete five-seed original-post profile in HK-shuffled. This is a partial fit: '
           'extreme/neutral≈1.66, slight/neutral≈1.04, so the empirical inner trough≈0.70 is absent. '
           'Selection is a diagnostic on original-only loss; the running calibration still fits original+repost. '
           'Representative graph seed is the lowest seed, chosen without inspecting graph appearance.','',
           '## Network snapshots','',
           'network_snapshots.png shows all 1,000 agents, all initial/final follow ties, and all root-attributed repost ties in the final 10k steps. '
           'The initial graph uses its own topology layout; the final follow and repost graphs share a final-topology layout. Opinion determines color only. GraphML files preserve directions and weights. '
           'Follow edges point follower→followee, repost edges root author→reposter. Arrowheads are omitted in the dense PNG.','',
           '## Strategy ratios','',
           'Use the actual bandit state 0 in q_table_final.csv. The summary Q columns in agent_snapshot_final.csv average states and include unvisited states, so they are not the correct basis for bandit preferences. '
           'Final greedy preferences are unconstrained argmax Q, not a proof of convergence or the actual stochastic policy. '
           'Actual action shares include epsilon exploration and availability restrictions; chosen like no-ops are included.','',
           '| Action | Agents with final greedy preference (%) | Observed decisions, final 10k (%) |','|---|---:|---:|']
    for action in ACTIONS:lines.append(f'| {action} | {100*strategy["preferred_"+action.lower()]:.2f} | {100*strategy["actual_"+action.lower()]:.2f} |')
    lines += ['',f'Dominant observed action is unchanged across the final two 5k windows for {100*strategy["stable_dominant_action_fraction"]:.1f}% of agents (five-seed mean); '
              f'median per-agent total-variation change in action mix is {strategy["median_window_total_variation"]:.4f}. '
              'This is a limited behavioral-stability diagnostic; it does not establish Q-value or network equilibrium. '
              f'With epsilon={condition[0]["tokens"]["q_eps"]:.4f}, uniform exploration over four available actions contributes epsilon/4≈{100*condition[0]["tokens"]["q_eps"]/4:.2f}% per action. '
              'Observed repost/rewire rates are close to that floor. The floor statement is conditional on all four actions being available.','',
              '## Parameter settings','', 'Reference is standard_run.py hkshuf / pure For You with inherited reward_search.BASE and Java defaults. '
              'The selected feed is mixed; the standing script also runs pure Chrono and pure Trend.','',
              '| Parameter | Standing baseline | Selected condition |','|---|---:|---:|']
    for row in comparison:
        if row['changed']:
            fmt=lambda value:f'{value:.4g}' if isinstance(value,float) else str(value)
            lines.append(f'| {row["parameter"]} | {fmt(row["standing_hkshuf_foryou"])} | {fmt(row["selected"])} |')
    lines += ['', '## Which parameters matter?','',
              'Exploratory analysis uses only complete valid five-seed initial Sobol settings, excluding the 28 manually chosen anchors and every adaptive BO proposal. '
              'Forests predict log1p(mean component loss), with four-fold out-of-fold validation and held-out permutation importance (five repeats per fold). '
              'This diagnostic response transformation does not change the running optimizer. Small positive predictive skill and unstable importance bars limit interpretation. '
              'Spearman associations have Benjamini–Hochberg correction across the 25 parameters within each network/outcome; cross-network analyses share parameter points and are not independent replications. '
              'No causal parameter effect is estimated, and broad-space importance need not identify the local change needed to create the missing trough.','',
              '| Network | Outcome | Settings | Out-of-fold predictive skill vs constant |','|---|---|---:|---:|']
    for row in metrics:lines.append(f'| {row["network"]} | {row["outcome"]} | {row["n_settings"]} | {row["skill_vs_constant"]:.3f} |')
    lines += ['', 'Original-post associations with corrected q<0.10 (larger loss means worse fit):','',
              '| Network | Parameter | Spearman rho | Corrected q |','|---|---|---:|---:|']
    for row in sorted(associations,key=lambda r:(r['network'],r['q_within_network_outcome'])):
        if row['outcome']=='original_activity_loss' and row['q_within_network_outcome']<.10:
            lines.append(f'| {row["network"]} | {row["parameter"]} | {row["spearman_rho"]:.3f} | {row["q_within_network_outcome"]:.3f} |')
    lines += ['', 'Network-loss prediction identifies beta_h as the dominant predictor in all three families, with much smaller secondary contributions from fy_beta. '
              'Original-post-loss prediction has little held-out skill, so its permutation ranking does not reliably identify the local change needed to create the missing trough. '
              'Repeated marginal associations with beta_h and q_tau are exploratory leads; they are not monotone prescriptions or causal effects. '
              'In the selected condition, the near-exploration-floor repost and rewire rates make epsilon, action costs and temperature useful priorities for controlled local mechanism tests, which have not been performed here.', '',
              'Each figure is based on completed outputs only. No simulator code, fitting objective, live job, or parameter default was changed.']
    (OUT/'report.md').write_text('\n'.join(lines)+'\n')
    write('strategy_means.json',strategy)
    print('Report ready:',OUT/'report.md',flush=True)


if __name__=='__main__':main()
