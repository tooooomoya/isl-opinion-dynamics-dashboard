#!/usr/bin/env python3
"""Plot confirmed uniform-study fits and compare actual standing baseline tokens.

Reads completed seed results only. Writes figures, data, and parameter provenance;
does not change calibration measurements, selection, or running simulations.
"""
import ast
import json
import re
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT/'results/calibration_uniform_20261028'
OUT = ROOT/'docs/report/bayesian-calibration-uniform-2026-10-28'


def assignments(path, names):
    found = {}
    for node in ast.parse(path.read_text()).body:
        if isinstance(node, ast.Assign):
            for lhs in node.targets:
                if isinstance(lhs, ast.Name) and lhs.id in names:
                    found[lhs.id] = ast.literal_eval(node.value)
    return found


def scalar(value):
    if isinstance(value, str):
        if value.lower() in ['true', 'false']:
            return value.lower() == 'true'
        try:
            return float(value) if any(c in value.lower() for c in '.e') else int(value)
        except ValueError:
            pass
    return value


def baseline_tokens(keys):
    standard = assignments(ROOT/'scripts/standard_run.py', {'COMMON','FEEDS','NETS'})
    base = assignments(ROOT/'scripts/reward_search.py', {'BASE'})['BASE']
    explicit = {**base, **standard['COMMON'], **standard['FEEDS']['foryou'], **standard['NETS']['hkshuf']}
    java = (ROOT/'src/experiment/ExperimentConfig.java').read_text()
    defaults = {}
    for name, value in re.findall(r'public (?:double|int|boolean|String) (\w+) = ([^;]+);', java):
        try:
            defaults[name] = ast.literal_eval({'true':'True','false':'False'}.get(value, value))
        except (ValueError, SyntaxError):
            pass
    aliases = {}
    for names, field in re.findall(r'case ([^\n]+?) -> c\.(\w+) =', java):
        for name in re.findall(r'"(\w+)"', names):
            aliases[name] = field
    result = {}
    for key in keys:
        if key in explicit:
            result[key] = scalar(explicit[key])
        elif aliases.get(key) in defaults:
            result[key] = defaults[aliases[key]]
        else:
            raise ValueError(f'Cannot resolve standing baseline parameter {key}')
    return result


def summarize(rows):
    return {kind:np.array([j[kind+'_neutral_ratios'] for j in rows]) for kind in ['original','all']}


def draw(path, title, target, confirmed, search=None, signed=False):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), layout='constrained')
    ticks = ['VL','L','SL','Neutral','SC','C','VC'] if signed else ['Extreme','Partisan','Slightly partisan','Neutral']
    positions = range(len(ticks))
    if signed:
        target = np.asarray(target)[[0,1,2,3,2,1,0]]
    def values_for(rows, kind):
        if not signed:
            return summarize(rows)[kind]
        rates = np.asarray([j[kind+'_rates'] for j in rows])
        return rates/rates[:,3,None]
    for ax, kind in zip(axes, ['original','all']):
        ax.plot(positions, target, 'k--o', lw=2, label='Symmetric empirical target')
        values = values_for(confirmed, kind)
        lower, upper = np.quantile(values, [.1,.9], axis=0)
        ax.fill_between(positions, lower, upper, color='#d97732', alpha=.15,
                        label='10–90% range across confirmation seeds')
        ax.plot(positions, values.mean(axis=0), 'o-', color='#c35b1e', lw=2.4,
                label=f'Confirmation mean ({len(confirmed)} seeds; 40k steps)')
        if search is not None:
            values = values_for(search, kind)
            for value in values:
                ax.plot(positions, value, color='#2176ae', alpha=.25, lw=1)
            ax.plot(positions, values.mean(axis=0), 's-', color='#2176ae', lw=2,
                    label=f'Search mean ({len(search)} seeds; 20k steps)')
        ax.axhline(1, color='grey', lw=.7, alpha=.5)
        ax.set_xticks(positions, ticks, fontsize=9)
        ax.set_ylim(bottom=0)
        ax.set_ylabel('Per-person activity / neutral' + ('' if signed else ' (equal left/right weights)'))
        ax.set_title('Original posts only' if kind=='original' else 'Original posts + reposts (fitted event mapping)')
        ax.grid(alpha=.18);ax.legend(fontsize=7.5)
    fig.suptitle(title, fontsize=13)
    fig.savefig(path, dpi=200);plt.close(fig)


def fmt(value):
    return f'{value:.4g}' if isinstance(value, float) else str(value)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    target = json.loads((RUN/'targets.json').read_text())['symmetric_neutral']['ratios']
    jobs = {f.stem:json.loads(f.read_text()) for f in (RUN/'jobs').glob('*.json')}
    search = json.loads((RUN/'search.json').read_text())
    confirmations = json.loads((RUN/'confirm.json').read_text())
    eligible = lambda r:r['failed']==0 and r['valid_fraction']>=.5
    best = min(filter(eligible, confirmations), key=lambda r:r['all_activity_loss'])
    # Here the best confirmed activity fit is also the best combined fit; record both selection criteria.
    best_combined = min(filter(eligible, confirmations), key=lambda r:r['loss'])
    valley = min(filter(eligible, search), key=lambda r:r['all_activity_loss'])
    valley_confirm = next(r for r in confirmations if r['point']==valley['point'])
    rr = lambda r:[jobs[k] for k in r['job_keys'] if jobs[k]['status']=='ok']
    b, v, s = rr(best), rr(valley_confirm), rr(valley)
    assert best['point']==best_combined['point'], 'Split confirmed activity and combined winners in this report'
    draw(OUT/'best_confirmed_fit.png', 'Best confirmed activity fit — uniform, fixed opinions', target, b)
    draw(OUT/'best_search_valley_confirmation.png', 'Earlier best valley: search fit versus fresh-seed confirmation', target, v, s)
    draw(OUT/'best_confirmed_seven_bins.png', 'Best confirmed activity fit — seven-bin diagnostic', target, b, signed=True)
    draw(OUT/'best_valley_seven_bins.png', 'Earlier best valley: search fit versus fresh-seed confirmation', target, v, s, signed=True)
    ignored = {'seed','results_subdir','run_id','steps','metrics_every','metrics_heavy_every','calibration_log',
               'log_gexf','log_repost_cascade','log_post_lifespan'}
    keys = [k for k in b[0]['tokens'] if k not in ignored]
    baseline = baseline_tokens(keys)
    comparisons = []
    for key in keys:
        base, best_value, valley_value = baseline[key], b[0]['tokens'][key], v[0]['tokens'][key]
        comparisons.append({'parameter':key,'standing_hkshuf_foryou':base,
                            'best_confirmed':best_value,'previous_valley':valley_value,
                            'changed_best':base!=best_value,'changed_valley':base!=valley_value})
    pd.DataFrame(comparisons).to_csv(OUT/'best_fit_parameter_comparison.csv',index=False)
    details = {'selection':'Best confirmed primary activity loss, also best confirmed combined loss',
               'baseline_reference':'reward_search.BASE + standard_run.COMMON + FEEDS[foryou] + NETS[hkshuf] + Java defaults',
               'target':target, 'baseline_tokens':baseline,
               'best_confirmed':{'summary':best,'tokens':{k:b[0]['tokens'][k] for k in keys}},
               'previous_valley':{'search_summary':valley,'confirmation_summary':valley_confirm,
                                  'tokens':{k:v[0]['tokens'][k] for k in keys}},
               'baseline_feeds':'Standing script separately runs Chrono100 / ForYou100 / Trend100; fitted mixtures differ from all three.'}
    (OUT/'best_fit_conditions.json').write_text(json.dumps(details,indent=2)+'\n')
    data = []
    for label, rows in [('best_confirmed',b),('valley_search',s),('valley_confirmed',v)]:
        for j in rows:
            for kind, values in summarize([j]).items():
                data.append({'condition':label,'seed':j['seed'],'steps':j['steps'],'kind':kind,
                             'extreme':values[0,0],'partisan':values[0,1],'slight':values[0,2],'neutral':values[0,3],
                             'q':j['root']['q'],'activity_loss':j[kind+'_activity_loss']})
    pd.DataFrame(data).to_csv(OUT/'best_fit_profile_data.csv',index=False)
    lines = ['# Confirmed valley fit and standing-baseline comparison','',
             'The earlier two-seed valley did not retain its empirical fit at 40,000 steps with 20 fresh seeds. '
             'The best confirmed condition by both primary activity and combined loss has nearly flat original posting. '
             'Confirmation changes both horizon and seed sample, so the deterioration cannot be attributed to either alone.','',
             'Figures: best_confirmed_fit.png and best_search_valley_confirmation.png. Orange shading is the 10–90% '
             'range across confirmation seeds, not a confidence interval for the mean. All rates include zero posters.','',
             '| Condition | Seeds/steps | Original extreme / neutral | Original slight / neutral | Primary activity loss | Repost Q |',
             '|---|---:|---:|---:|---:|---:|']
    for label,rows,summary in [('Earlier valley (search)',s,valley),('Same valley (confirmation)',v,valley_confirm),('Best confirmed',b,best)]:
        a=summarize(rows)['original'].mean(axis=0)
        lines.append(f'| {label} | {len(rows)} / {rows[0]["steps"]} | {a[0]:.3f} | {a[2]:.3f} | {summary["all_activity_loss"]:.3f} | {summary["q"]:.3f} |')
    lines += ['', 'Empirical ratios: extreme=1.739, partisan=1.049, slight=0.702, neutral=1. '
              'Primary activity loss uses original+repost; original-only remains a measurement sensitivity because private collection filters are unknown.','',
              '## Parameter differences','',
              'Reference: the actual standing hkshuf / For You configuration in standard_run.py, including inherited reward_search.BASE and Java defaults. '
              'The standing study also runs pure Chrono and pure Trend feeds. No baseline simulation curve is invented here. '
              '`start_deg=0` means no explicit edge-count enforcement; hk_m=15 is its nominal HK growth degree.','',
              '| Parameter | Standing baseline | Best confirmed | Earlier valley |','|---|---:|---:|---:|']
    for row in comparisons:
        if row['changed_best'] or row['changed_valley']:
            lines.append(f'| {row["parameter"]} | {fmt(row["standing_hkshuf_foryou"])} | {fmt(row["best_confirmed"])} | {fmt(row["previous_valley"])} |')
    lines += ['', 'Both fitted conditions retain uniform opinions, mu=0, bandit learning, rewiring without the similarity gate, and stock recognition credit. '
              '`fit_baseline=empirical` means the simulated realized-population expectation; `analytic` is the uniform-distribution expectation. '
              'This is a reward-baseline difference, not empirical opinion initialization.','',
              'Logging differs too: baseline ordinary/heavy metrics every 1/25 steps; calibration 100/100 plus exact event logs. '
              'Confirmation uses 40,000 steps versus standing 20,000; both figures measure the final 10,000 steps. '
              'Parameter differences are associations from joint fitting, not estimates of individual causal effects.','',
              'User preference for future experiments: 10 confirmation seeds. This already-running study retains its original 20.']
    (OUT/'best_fit_comparison.md').write_text('\n'.join(lines)+'\n')
    print('\n'.join(lines[:13]))


if __name__ == '__main__':
    main()
