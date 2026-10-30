#!/usr/bin/env python3
"""Export calibration tables, figures, diagnostics and a self-contained results note.

Safe to run while the resumable driver is active. It reads completed job JSONs only.
"""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
import argparse
import json
from pathlib import Path
import warnings

import numpy as np
import pandas as pd
from scipy.stats import t
from sklearn.ensemble import RandomForestRegressor
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, Matern, WhiteKernel
from sklearn.inspection import permutation_importance
from sklearn.model_selection import KFold, cross_val_predict, train_test_split
from sklearn.metrics import mean_squared_error
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from bayesian_calibration import ROOT, SOURCE, NAMES, SPACE, tokens_from, choose_candidates, search_space
from calibration_metrics import gini


def read(path, default=None): return json.loads(path.read_text()) if path.exists() else default
def interval(x):
    x = np.asarray(x, dtype=float)
    mean = float(x.mean())
    return mean, float(t.ppf(.975, len(x)-1) * x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 1 else float('nan')


def flat_row(row, study='legacy'):
    out = {k: v for k, v in row.items() if not isinstance(v, (dict, list))}
    out.update(dict(zip(NAMES, row['point'])))
    out.update({k: v for k, v in tokens_from(row['point'], study).items() if k in ['foryou_share', 'trend_share', 'w_fit', 'w_rec']})
    for field in ['root', 'degree']:
        out.update({field+'_'+k:v for k,v in row.get(field,{}).items() if np.isscalar(v)})
    for kind in ['all','original']:
        for field in ['neutral_ratios', 'left_right_log_gap']:
            for i,value in enumerate(row.get(kind+'_'+field) or []):
                out[f'{kind}_{field}_{i}'] = value
    return out


def surrogate_audit(rows, output):
    good = [r for r in rows if r['failed'] == 0]
    if len(good) < 64: return
    x = np.asarray([r['point'] for r in good], float)
    for i, d in enumerate(SPACE):
        if d.prior == 'log-uniform': x[:, i] = np.log(x[:, i])
        lo,hi=(np.log(d.low),np.log(d.high)) if d.prior=='log-uniform' else (d.low,d.high)
        x[:, i] = (x[:, i] - lo) / (hi-lo)
    # Out-of-sample error relative to the available noisy point means.
    cv = KFold(4, shuffle=True, random_state=1729)
    result = {}
    importance = []
    for key in ['loss', 'all_activity_loss', 'network_loss']:
        y = np.asarray([r[key] for r in good],dtype=float)
        forest = RandomForestRegressor(n_estimators=100, min_samples_leaf=2, random_state=1729, n_jobs=1)
        pred = cross_val_predict(forest, x, y, cv=cv)
        result[key] = {'training_target':'raw score (same as the search)',
                       'forest_raw_rmse':float(mean_squared_error(y,pred)**.5), 'constant_raw_rmse':float(np.std(y)),
                       'forest_log1p_rmse': float(mean_squared_error(np.log1p(y),np.log1p(np.maximum(pred,0)))**.5),
                       'constant_log1p_rmse': float(np.std(np.log1p(y)))}
        train, test = train_test_split(np.arange(len(y)), test_size=.25, random_state=1729)
        forest.fit(x[train], y[train])
        imp = permutation_importance(forest, x[test], y[test], scoring='neg_mean_squared_error', n_repeats=15, random_state=1729)
        for name, mean, sd in zip(NAMES, imp.importances_mean, imp.importances_std):
            importance.append({'objective': key, 'parameter': name, 'heldout_mse_increase': mean, 'permutation_sd': sd})
        if key == 'loss':
            gp = GaussianProcessRegressor(kernel=ConstantKernel(1.) * Matern(length_scale=np.ones(x.shape[1]), nu=2.5)
                                          + WhiteKernel(.1), normalize_y=True, random_state=1729,
                                          n_restarts_optimizer=0)
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                gp_pred = cross_val_predict(gp, x, y, cv=cv)
            result[key]['gp_raw_rmse'] = float(mean_squared_error(y,gp_pred)**.5)
            result[key]['gp_log1p_rmse'] = float(mean_squared_error(np.log1p(y),np.log1p(np.maximum(gp_pred,0)))**.5)
    (output / 'surrogate_validation.json').write_text(json.dumps(result, indent=2) + '\n')
    pd.DataFrame(importance).to_csv(output / 'parameter_importance.csv', index=False)


def main():
    global NAMES, SPACE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, default=ROOT/'results/calibration_20261027')
    parser.add_argument('--output', type=Path, default=ROOT/'docs/report/bayesian-calibration-2026-10-27')
    parser.add_argument('--surrogate-audit', action='store_true')
    args = parser.parse_args(); args.output.mkdir(parents=True, exist_ok=True)
    target = read(args.run/'targets.json')
    uniform = target.get('study') == 'uniform-v3'
    manifest = read(args.run/'manifest.json', {})
    network = manifest.get('primary_network', 'hkshuf')
    study = manifest.get('study', target.get('study', 'legacy'))
    SPACE = search_space(study)
    NAMES = [d.name for d in SPACE]
    budget = read(args.run/'refinement_budget.json',{})
    design = read(args.run/'bo_async_design.json',[])
    prior = int(budget.get('pre_correction_proposals',0))
    if design:
        proposal_rows=[]
        for i,point in enumerate(design):
            proposal_rows.append({'proposal_index':i,'proposal_policy':'pre_correction_boundary_evaluation' if i<prior else 'corrected_forest_EI',
                                  **dict(zip(NAMES,point))})
        pd.DataFrame(proposal_rows).to_csv(args.output/'proposal_history.csv',index=False)
    jobs = [read(p) for p in (args.run/'jobs').glob('*.json')]
    attempts = [read(p) for p in (args.run/'attempts').glob('*.json')]
    ok = [j for j in jobs if j['status'] == 'ok']
    search = read(args.run/'search.json', read(args.run/'pilot.json', []))
    if not search:
        grouped = {}
        for job in ok:
            if job['phase'] == 'pilot': grouped.setdefault(tuple(job['point']), []).append(job)
        for point, rr in grouped.items():
            if len(rr) < 2: continue
            row = {'point': list(point), 'phase': 'pilot_partial', 'seed_count': len(rr), 'failed': 0,
                   'job_keys': [r['key'] for r in rr], 'loss': float(np.mean([r['loss'] for r in rr])),
                   'valid_fraction': float(np.mean([r['valid'] for r in rr]))}
            for key in ['all_activity_loss','original_activity_loss','network_loss']:
                row[key] = float(np.mean([r[key] for r in rr]))
            search.append(row)
    confirm = read(args.run/'confirm.json', [])
    validation = read(args.run/'validation.json', [])
    pd.DataFrame([flat_row(j, study) for j in jobs]).to_csv(args.output/'seed_summary.csv', index=False)
    for name, rows in [('search', search), ('confirm', confirm), ('validation', validation)]:
        if rows: pd.DataFrame([flat_row(r, study) for r in rows]).to_csv(args.output/(name+'.csv'), index=False)
    candidates = confirm or read(args.run/'finalists.json', [])
    if not candidates and search: candidates = choose_candidates(search,4)
    jobmap = {j['key']: j for j in ok}
    note = [f'# Current-model calibration results ({args.run.name})', '',
            f"Completed simulator jobs: {len(ok)}; currently failed evaluations: {len(jobs)-len(ok)}; preserved failed/retried attempts: {len(attempts)}. Full schedule complete: {(args.run/'COMPLETE.json').exists()}.", '',
            'Primary comparison: deduplicated pre-2021-01-08 seven-bin activity; model originals+reshares; root-attributed repost network, identical two-community detector on empirical/simulated graphs.', '',
            'Empirical collection filters are unavailable; an all-record count is provisionally matched to originals+reshares. This does not establish original-only empirical fit. No defaults have been adopted.', '']
    if manifest.get('fixed_parameters'):
        note += [f'Study: {study}; {len(NAMES)} explored parameters. Fixed inputs: '
                 + ', '.join(f'{k}={v:g}' for k,v in manifest['fixed_parameters'].items()) + '.', '']
    if uniform:
        note[4] = ('Primary comparison: iid uniform fixed opinions; three log activity ratios relative to neutral, '
                   'with equal weights for left/right per-person rates. Primary events: originals+reshares; '
                   'original-only is measurement sensitivity. Repost root Q uses the identical empirical/model detector.')
        note += ['The fitted target is symmetric_neutral_profiles.png. Seven-bin activity_profiles.png is an asymmetry diagnostic. '
                 'Ratios share a neutral denominator; standardized residuals are an engineering loss, not a likelihood. '
                 'Opinion values remain fixed (mu=0); activity and network patterns can emerge.', '']
    note += [f'Fitting and confirmation network: {network}. Network-transfer validation conditions are reported separately.', '']
    if prior:
        note += [f"Proposal audit: {prior} pre-correction lifetime-400 proposals are retained as valid physical evaluations, followed by a separate budget of {budget.get('new_corrected_proposal_budget',64)} proposals with corrected integer-log acquisition bounds. See proposal_history.csv; these policies must not be conflated in an optimizer benchmark.", '']
    if candidates:
        fig, axes = plt.subplots(1, 2, figsize=(12,4.5), layout='constrained')
        exp_rates = np.asarray(target['means_daily']); exp_rates /= exp_rates[3]
        labels = pd.read_csv(SOURCE/'libcon.csv').drop_duplicates('handle').set_index('handle')
        raw = pd.read_parquet(SOURCE/'counts.parquet')
        raw = raw.loc[:, pd.to_datetime(raw.columns) < '2021-01-08'].mean(axis=1)
        rng = np.random.default_rng(1729)
        bootstrap = []
        for k in range(1,8):
            values = raw.loc[labels.index[labels.ideological_lean_label.str.startswith(str(k))]].to_numpy()
            bootstrap.append(rng.choice(values,size=(5000,len(values)),replace=True).mean(axis=1))
        bootstrap = np.column_stack(bootstrap); bootstrap /= bootstrap[:,3,None]
        lo,hi=np.quantile(bootstrap,[.025,.975],axis=0)
        for ax in axes: ax.fill_between(range(7),lo,hi,color='grey',alpha=.15,label='Empirical account-bootstrap 95% interval')
        axes[0].plot(range(7), exp_rates, 'k-o', lw=2, label='Empirical pre-event mean / middle')
        axes[1].plot(range(7), exp_rates, 'k-o', lw=2, label='Empirical pre-event mean / middle')
        note += ['| Candidate | Seeds | Activity loss | Original-only loss | Root Q (95% CI for mean) | Degree Gini | Activity/window drift |',
                 '|---|---:|---:|---:|---:|---:|---:|']
        candidate_details = []
        activity_series=[('Empirical pre-event',raw.to_numpy()/raw.mean())]
        heterogeneity=[]
        for i, row in enumerate(sorted(candidates, key=lambda r:r['loss'])):
            rr = [jobmap[k] for k in row['job_keys'] if k in jobmap]
            if not rr: continue
            mean_q, ci = interval([r['root']['q'] for r in rr])
            label = f'C{i+1}'
            note.append(f"| {label} | {len(rr)} | {np.mean([r['all_activity_loss'] for r in rr]):.3f} | {np.mean([r['original_activity_loss'] for r in rr]):.3f} | {mean_q:.3f} ± {ci:.3f} | {np.mean([r['degree']['gini'] for r in rr]):.3f} | {np.mean([r['activity_window_drift'] or 0 for r in rr]):.3f} |")
            for ax, kind in zip(axes, ['all', 'original']):
                rates = np.array([r[kind+'_rates'] for r in rr]); rates = rates/np.maximum(rates[:,3,None],1e-12)
                ax.errorbar(range(7), rates.mean(axis=0), yerr=rates.std(axis=0,ddof=1)/np.sqrt(len(rr))*1.96 if len(rr)>1 else None,
                            fmt='o-', capsize=2, label=label)
            candidate_details.append({'candidate': label, 'point': dict(zip(NAMES,row['point'])),
                    'tokens': tokens_from(row['point'], study, network), 'summary':row,
                    'all_activity_rates_mean':np.mean([r['all_rates'] for r in rr],axis=0).tolist(),
                    'original_activity_rates_mean':np.mean([r['original_rates'] for r in rr],axis=0).tolist(),
                    'degree_mean': {k:float(np.mean([r['degree'][k] for r in rr])) for k in rr[0]['degree']}})
            heterogeneity.append((label,len(rr),np.mean([r['all_activity_cv'] for r in rr]),
                                  np.mean([r['all_activity_gini'] for r in rr]),np.mean([r['zero_activity_fraction'] for r in rr])))
            normalized=[]
            for r in rr:
                actions=pd.read_csv(Path(r['run_dir'])/'metrics/calibration_activity.csv')
                actions=actions[actions.start>=r['window_start']].groupby('agentId')[['nPost','nReshare']].sum().reindex(range(r['n']),fill_value=0)
                values=(actions.nPost+actions.nReshare).to_numpy(dtype=float)
                normalized.extend(values/max(values.mean(),1e-12))
            activity_series.append((label,np.asarray(normalized)))
        for ax, title in zip(axes,['Original + reshare activity','Original activity only (measurement sensitivity)']):
            ax.set_xticks(range(7),['VL','L','SL','Middle','SC','C','VC']);ax.set_ylabel('Per-person rate / middle-bin rate');ax.set_title(title);ax.legend(fontsize=8);ax.grid(alpha=.2)
        fig.savefig(args.output/'activity_profiles.png',dpi=180);plt.close(fig)
        if uniform:
            fig,axes=plt.subplots(1,2,figsize=(11,4.5),layout='constrained')
            t=target['symmetric_neutral']; lo,hi=np.asarray(t['ratio_bootstrap_95'])
            for ax,kind in zip(axes,['all','original']):
                ax.fill_between(range(4),lo,hi,color='grey',alpha=.15,label='Empirical account-bootstrap 95%')
                ax.plot(range(4),t['ratios'],'k-o',label='Equal-side empirical target')
                for i,row in enumerate(sorted(candidates,key=lambda r:r['loss'])):
                    rr=[jobmap[k] for k in row['job_keys'] if k in jobmap and jobmap[k].get(kind+'_neutral_ratios') is not None]
                    if not rr: continue
                    values=np.array([r[kind+'_neutral_ratios'] for r in rr])
                    cis=np.array([interval(values[:,j])[1] for j in range(4)]) if len(rr)>1 else None
                    ax.errorbar(range(4),values.mean(axis=0),yerr=cis,fmt='o-',capsize=2,label=f'C{i+1}')
                ax.set_xticks(range(4),t['bins']); ax.set_ylabel('Equal-side per-person activity / neutral')
                ax.set_title('Original + repost' if kind=='all' else 'Original-only sensitivity')
                ax.grid(alpha=.2);ax.legend(fontsize=7)
            fig.savefig(args.output/'symmetric_neutral_profiles.png',dpi=180);plt.close(fig)
        (args.output/'candidate_details.json').write_text(json.dumps(candidate_details,indent=2)+'\n')
        # Degree distributions belong to held-out validation, not the fitted loss.
        fig, ax=plt.subplots(figsize=(6,4.5),layout='constrained')
        for i,row in enumerate(sorted(candidates,key=lambda r:r['loss'])):
            degrees=[]
            for key in row['job_keys']:
                if key in jobmap:
                    s=pd.read_csv(Path(jobmap[key]['run_dir'])/'degrees/agent_snapshot_final.csv');degrees.extend(s.followerCount)
            if not degrees:continue
            values=np.sort(degrees);unique=np.unique(values);tail=np.array([(values>=k).mean() for k in unique])
            ax.plot(unique[unique>0],tail[unique>0],label=f'C{i+1}; P(k=0)={np.mean(np.array(degrees)==0):.2f}')
        ax.set_xscale('log');ax.set_yscale('log');ax.set_xlabel('Followers (in-degree)');ax.set_ylabel('P(K ≥ k), zero-degree agents retained');ax.legend(fontsize=8);ax.grid(alpha=.2)
        fig.savefig(args.output/'degree_ccdf.png',dpi=180);plt.close(fig)
        fig,ax=plt.subplots(figsize=(6,4.5),layout='constrained')
        for label,values in activity_series:
            values=np.sort(values);unique=np.unique(values);tail=(len(values)-np.searchsorted(values,unique,side='left'))/len(values)
            positive=unique>0
            ax.plot(unique[positive],tail[positive],label=label,lw=2 if label.startswith('Empirical') else 1)
        ax.set_xscale('log');ax.set_yscale('log');ax.set_xlabel('Individual posting activity / population mean')
        ax.set_ylabel('P(activity ≥ x), zero-activity agents retained');ax.grid(alpha=.2);ax.legend(fontsize=8)
        ax.set_title('Held-out activity heterogeneity',fontsize=11)
        fig.savefig(args.output/'activity_ccdf.png',dpi=180);plt.close(fig)
        note += ['',f"Held-out empirical pre-event activity: CV={raw.std(ddof=1)/raw.mean():.3f}, Gini={gini(raw):.3f} (762 unique people). Individual model activity is originals+reshares in the declared final window; windows/events differ, so this is a shape check, not another optimized target.", '',
                 '| Candidate | Seeds | Individual activity CV | Activity Gini | Zero-activity fraction |',
                 '|---|---:|---:|---:|---:|']
        for label,n,cv,gin,zero in heterogeneity:note.append(f'| {label} | {n} | {cv:.3f} | {gin:.3f} | {zero:.3f} |')
    if search:
        df=pd.DataFrame([flat_row(r, study) for r in search]);fig,ax=plt.subplots(figsize=(6,4.5),layout='constrained')
        sc=ax.scatter(df.all_activity_loss,df.network_loss,c=df.beta_h,cmap='viridis',s=25,alpha=.8)
        feasible=df[(df.failed==0)&(df.valid_fraction>=.5)].copy()
        values=feasible[['all_activity_loss','network_loss']].to_numpy()
        nondominated=np.array([not np.any(np.all(values<=v,axis=1)&np.any(values<v,axis=1)) for v in values])
        frontier=feasible.loc[nondominated].sort_values('all_activity_loss')
        frontier.to_csv(args.output/'provisional_pareto.csv',index=False)
        ax.plot(frontier.all_activity_loss,frontier.network_loss,'k--',lw=.8,label='Provisional nondominated points')
        ax.set_xlabel('Symmetric neutral-relative activity loss' if uniform else 'Folded activity loss');ax.set_ylabel('Repost network loss');ax.set_xscale('symlog',linthresh=.1);ax.set_yscale('symlog',linthresh=.1);fig.colorbar(sc,ax=ax,label='beta_h')
        seed_counts=[r['seed_count'] for r in search]
        seed_label=str(min(seed_counts)) if min(seed_counts)==max(seed_counts) else f'{min(seed_counts)}–{max(seed_counts)}'
        ax.set_title(f'Search estimates ({seed_label} seeds; not a confirmed frontier)',fontsize=10);ax.legend(fontsize=7)
        fig.savefig(args.output/'objective_tradeoff.png',dpi=180);plt.close(fig)
        note += ['',f"Search evaluated {len(search)} parameter points. Best mean search loss: {min(r['loss'] for r in search):.3f}. Search winner selection is noisy and is superseded by fresh-seed confirmation."]
    if args.surrogate_audit: surrogate_audit(search,args.output)
    for filename,title in [('credit_probe','Credit attribution at the standing mixed-feed baseline'),
                           ('profile_beta_probe','beta_h at the improving vocal-profile candidate')]:
        rows=read(args.run/(filename+'.json'),[])
        if not rows: continue
        pd.DataFrame([flat_row(r, study) for r in rows]).to_csv(args.output/(filename+'.csv'),index=False)
        fig,axes=plt.subplots(1,2,figsize=(10,4),layout='constrained')
        for phase in sorted({r['phase'] for r in rows}):
            rr=sorted([r for r in rows if r['phase']==phase],key=lambda r:r['point'][0])
            axes[0].plot([r['point'][0] for r in rr],[r['all_activity_loss'] for r in rr],'o-',label=phase.replace('credit_probe_',''))
            axes[1].plot([r['point'][0] for r in rr],[r['q'] for r in rr],'o-',label=phase.replace('credit_probe_',''))
        axes[0].set_ylabel('Seven-bin activity loss');axes[1].set_ylabel('Detected-community root Q')
        axes[1].axhline(target['repost']['q'],color='black',ls='--',label='Empirical Q')
        for ax in axes:ax.set_xlabel('beta_h');ax.grid(alpha=.2);ax.legend(fontsize=8)
        fig.suptitle(title+' (two fresh seeds per point)');fig.savefig(args.output/(filename+'.png'),dpi=180);plt.close(fig)
        note += ['',title+': see '+filename+'.csv and '+filename+'.png. These are local contrasts; the global search specification is unchanged.']
    note += ['', 'Source and measurement details: ../2026-10-27-calibration-run.md and ../2026-10-27-calibration-source-audit-and-search-design.md.',
             '', 'Generated plots: activity_profiles.png, degree_ccdf.png, objective_tradeoff.png. Per-seed and per-point CSVs preserve all available raw component scores.']
    (args.output/'results.md').write_text('\n'.join(note)+'\n')
    print('\n'.join(note[:8]))


if __name__=='__main__':main()
