"""Seven-bin activity profile of the confirmed calibration candidates that form a valley (flat C1 excluded)."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

RUN = Path('results/calibration_20261027')
SOURCE = Path('results/empirical_source_audit')
REPORT = Path('docs/report/bayesian-calibration-2026-10-27')
details = json.loads((REPORT / 'candidate_details.json').read_text())
target = json.loads((RUN / 'targets.json').read_text())

emp = np.asarray(target['means_daily']); emp = emp / emp[3]
labels = pd.read_csv(SOURCE / 'libcon.csv').drop_duplicates('handle').set_index('handle')
raw = pd.read_parquet(SOURCE / 'counts.parquet')
raw = raw.loc[:, pd.to_datetime(raw.columns) < '2021-01-08'].mean(axis=1)
rng = np.random.default_rng(1729)
boot = np.column_stack([rng.choice(v, size=(5000, len(v)), replace=True).mean(axis=1) for v in
                        (raw.loc[labels.index[labels.ideological_lean_label.str.startswith(str(k))]].to_numpy() for k in range(1, 8))])
lo, hi = np.quantile(boot / boot[:, 3, None], [.025, .975], axis=0)

fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), layout='constrained')
for ax, kind, title in zip(axes, ['all', 'original'], ['Original + reshare activity', 'Original activity only (measurement sensitivity)']):
    ax.fill_between(range(7), lo, hi, color='grey', alpha=.15, label='Empirical account-bootstrap 95% interval')
    ax.plot(range(7), emp, 'k-o', lw=2, label='Empirical pre-event mean / middle')
    for c in details:
        if c['candidate'] == 'C1': continue  # flat profile: no valley
        rr = [json.loads((RUN / 'jobs' / (k + '.json')).read_text()) for k in c['summary']['job_keys']]
        rates = np.array([r[kind + '_rates'] for r in rr]); rates = rates / np.maximum(rates[:, 3, None], 1e-12)
        ax.errorbar(range(7), rates.mean(0), yerr=rates.std(0, ddof=1) / np.sqrt(len(rr)) * 1.96, fmt='o-', capsize=2, label=c['candidate'])
    ax.set_xticks(range(7), ['VL', 'L', 'SL', 'Middle', 'SC', 'C', 'VC']); ax.set_ylabel('Per-person rate / middle-bin rate')
    ax.set_title(title); ax.legend(fontsize=8); ax.grid(alpha=.2)
fig.savefig(REPORT / 'valley_profiles.png', dpi=180)
