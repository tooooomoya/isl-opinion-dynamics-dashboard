#!/usr/bin/env python3
"""Predict simple extreme activity contrasts, without changing live calibration."""
import os
for key in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:
    os.environ[key]='1'
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.ensemble import RandomForestRegressor
from sklearn.inspection import permutation_importance
from sklearn.model_selection import KFold
from bayesian_calibration import ROOT,NAMES,SPACE
from analyze_fit_mechanisms import load_jobs,complete_groups,bh

PARENT=ROOT/'results/calibration_multinetwork_20261028'
OUT=ROOT/'docs/report/extreme-activity-predictors-2026-10-29'


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    data=[];associations=[];importance=[];validation=[];seeddata=[]
    for network in ['hkshuf','random','dcsbm']:
        p=PARENT/network
        sobol={tuple(x) for x in json.loads((p/'pilot_design.json').read_text())[28:]}
        groups=[v for v in complete_groups(load_jobs(p)) if v[0]['phase']=='pilot' and tuple(v[0]['point']) in sobol]
        rows=[]
        for group in groups:
            contrasts=[]
            for j in group:
                # Same declared half-event stabilization as activity scoring.
                rates=np.asarray(j['original_rates'])+.5/np.asarray(j['populations'])/(j['steps']-j['window_start'])
                extreme=(rates[0]+rates[6])/2
                value=[np.log(extreme/rates[3]),np.log(extreme/rates[1:6].mean())]
                contrasts.append(value)
                seeddata.append({'network':network,'key':j['key'],'seed':j['seed'],
                                 'log_extreme_neutral':value[0],'log_extreme_inner':value[1]})
            rows.append({'network':network,**dict(zip(NAMES,group[0]['point'])),
                         **dict(zip(['log_extreme_neutral','log_extreme_inner'],np.mean(contrasts,axis=0)))})
        data.extend(rows)
        frame=pd.DataFrame(rows);x=frame[NAMES].to_numpy(float)
        for i,dim in enumerate(SPACE):
            if dim.prior=='log-uniform':x[:,i]=np.log(x[:,i])
        print(network,'settings',len(rows),flush=True)
        for outcome in ['log_extreme_neutral','log_extreme_inner']:
            y=frame[outcome].to_numpy();tests=[spearmanr(x[:,i],y) for i in range(len(NAMES))];q=bh([t.pvalue for t in tests])
            for i,name in enumerate(NAMES):associations.append({'network':network,'outcome':outcome,'parameter':name,
                'rho':tests[i].statistic,'p':tests[i].pvalue,'q_within_network_outcome':q[i]})
            predicted=np.empty(len(y));baseline=np.empty(len(y));permrows=[]
            for fold,(train,test) in enumerate(KFold(4,shuffle=True,random_state=1729).split(x)):
                model=RandomForestRegressor(n_estimators=150,min_samples_leaf=3,random_state=1729,n_jobs=1)
                model.fit(x[train],y[train]);predicted[test]=model.predict(x[test]);baseline[test]=y[train].mean()
                perm=permutation_importance(model,x[test],y[test],scoring='neg_mean_squared_error',n_repeats=5,random_state=1730+fold,n_jobs=1)
                permrows.extend(perm.importances.T)
            skill=1-np.mean((predicted-y)**2)/np.mean((baseline-y)**2)
            validation.append({'network':network,'outcome':outcome,'n_settings':len(y),'out_of_fold_skill_vs_constant':skill,
                               'rmse_log_ratio':np.sqrt(np.mean((predicted-y)**2))})
            a=np.asarray(permrows)
            for i,name in enumerate(NAMES):importance.append({'network':network,'outcome':outcome,'parameter':name,
                'heldout_mse_increase':a[:,i].mean(),'permutation_spread':a[:,i].std(ddof=1)})
            print(outcome,'predictive skill',round(skill,3),flush=True)
    pd.DataFrame(data).to_csv(OUT/'parameter_settings_and_contrasts.csv',index=False)
    pd.DataFrame(seeddata).to_csv(OUT/'seed_contrasts.csv',index=False)
    pd.DataFrame(associations).to_csv(OUT/'associations.csv',index=False)
    pd.DataFrame(importance).to_csv(OUT/'permutation_importance.csv',index=False)
    pd.DataFrame(validation).to_csv(OUT/'cross_validation.csv',index=False)
    frame=pd.DataFrame(data)
    fig,axes=plt.subplots(2,2,figsize=(11,8),layout='constrained')
    for ax,key,label in zip(axes.flat,['beta_h','rec_fraction','access_prob','fy_beta'],
                            ['Homophily beta_h','Identity-fit fraction of reward (1 − rec_fraction)','Access probability','For You sharpness fy_beta']):
        for network,color in zip(['hkshuf','random','dcsbm'],['#2b7398','#d48029','#718c41']):
            f=frame[frame.network==network];xx=1-f[key] if key=='rec_fraction' else f[key]
            ax.scatter(xx,np.exp(f.log_extreme_neutral),s=20,alpha=.5,color=color,label=network)
        ax.axhline(1,color='grey',ls='--',lw=.8);ax.set_yscale('log');ax.set_xlabel(label)
        if key=='access_prob':ax.set_xscale('log')
        ax.set_ylabel('Extreme / neutral original-post activity\n(geometric mean across five seeds)');ax.grid(alpha=.15)
    axes[0,0].legend(fontsize=8)
    fig.suptitle('Exploratory activity contrasts across initial Sobol settings — associations, not causal effects',fontsize=11)
    fig.savefig(OUT/'extreme_activity_predictors.png',dpi=180);plt.close(fig)
    lines=['# Predictors of simple extreme posting elevation','',
           'Read-only analysis; no live objective, simulation, or default was changed. Use completed valid five-seed initial Sobol settings only; exclude anchors and adaptive BO. '
           'Outcomes are mean per-seed log(original activity contrast): equal-side extreme per-person rate divided by neutral, or by the equal-bin mean of all five inner bins. '
           'All agents including zero posters contribute to bin rates. The existing half-event stabilization is retained. '
           'The second contrast checks that a result is not solely a low-neutral effect.','',
           'Marginal Spearman associations use BH correction over 25 inputs within each network/outcome. Forests use four-fold held-out prediction and permutation importance. '
           'Shared parameter points across network families are not independent replications. Predictive associations over the sampled box do not establish local causal effects.','',
           '| Network | Contrast | Settings | Predictive skill vs constant |','|---|---|---:|---:|']
    for row in validation:lines.append(f'| {row["network"]} | {row["outcome"]} | {row["n_settings"]} | {row["out_of_fold_skill_vs_constant"]:.3f} |')
    lines+=['','Consistent candidate directions: higher homophily, greater identity-fit weight relative to recognition, higher access probability, and lower For You sharpness. '
            'Access is tested at a fixed step horizon: it changes both decision opportunities and learning progress relative to post lifetime, so it is not evidence of a clock-independent equilibrium effect. '
            'Ratios above one do not ensure a full U shape at every inner bin, nor the empirical W-shaped target.','',
            '| Network | Contrast | Parameter | Spearman rho | Corrected q |','|---|---|---|---:|---:|']
    for row in associations:
        if row['parameter'] in ['beta_h','rec_fraction','access_prob','fy_beta']:
            lines.append(f'| {row["network"]} | {row["outcome"]} | {row["parameter"]} | {row["rho"]:.3f} | {row["q_within_network_outcome"]:.3f} |')
    (OUT/'report.md').write_text('\n'.join(lines)+'\n')
    print('Report ready:',OUT/'report.md',flush=True)


if __name__=='__main__':main()
