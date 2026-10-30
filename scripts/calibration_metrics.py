"""Observation model shared by empirical targets and the current ABM calibration."""
import collections
import json
import random
import threading
import zipfile
from pathlib import Path

import igraph as ig
import numpy as np
import pandas as pd

GRAPH_LOCK = threading.Lock()  # igraph has a process-global RNG


def gini(values):
    x = np.sort(np.asarray(values, dtype=float))
    return float(2 * np.dot(np.arange(1, len(x) + 1), x) / (len(x) * x.sum()) - (len(x) + 1) / len(x)) if x.sum() else 0.


def profile(rates):
    x = np.asarray(rates, dtype=float)
    if np.any(x <= 0):
        raise ValueError("Each empirical ideology bin must have a positive mean rate")
    x = np.log(x)
    return x - x.mean()


FOLD = [(0, 6), (1, 5), (2, 4), (3,)]  # the model is left/right symmetric: mirror bins are pooled


def equal_side_ratios(rates):
    """Equal weight per side, then divide by neutral; supports bootstrap matrices."""
    rates = np.asarray(rates, dtype=float)
    folded = np.stack([rates[..., list(g)].mean(axis=-1) for g in FOLD], axis=-1)
    if np.any(folded[..., 3] <= 0):
        raise ValueError('Neutral activity must be positive')
    return folded / folded[..., 3, None]


def add_uniform_target(source, target):
    """Prospective uniform-v3 target; never pool people across unequal sides."""
    source = Path(source)
    counts = pd.read_parquet(source / 'counts.parquet')
    labels = pd.read_csv(source / 'libcon.csv').drop_duplicates('handle').set_index('handle')
    daily = counts.loc[:, pd.to_datetime(counts.columns) < '2021-01-08'].mean(axis=1)
    groups = [daily.loc[labels.index[labels.ideological_lean_label.str.startswith(str(k))]].to_numpy() for k in range(1, 8)]
    rng = np.random.default_rng(1729)
    boot = np.column_stack([rng.choice(g, size=(5000, len(g)), replace=True).mean(axis=1) for g in groups])
    logboot = np.log(equal_side_ratios(boot)[..., :3])
    ratios = equal_side_ratios(target['means_daily'])
    target['study'] = 'uniform-v3'
    target['symmetric_neutral'] = {
        'bins': ['extreme', 'partisan', 'slight', 'neutral'],
        'ratios': ratios.tolist(), 'log_ratios': np.log(ratios[:3]).tolist(),
        'log_ratio_sd_floored': np.maximum(logboot.std(axis=0, ddof=1), .15).tolist(),
        'bootstrap_log_ratio_covariance': np.cov(logboot, rowvar=False).tolist(),
        'ratio_bootstrap_95': np.quantile(equal_side_ratios(boot), [.025, .975], axis=0).tolist(),
        'note': 'Equal-side mean of per-person rates / neutral; three nontrivial log ratios. '
                'Shared neutral denominator induces covariance. Engineering loss, not a likelihood.',
    }
    return target


def neutral_activity_loss(counts, populations, window, target):
    rates = (np.asarray(counts, dtype=float) + .5) / np.asarray(populations) / window
    ratio = equal_side_ratios(rates)
    t = target['symmetric_neutral']
    residual = (np.log(ratio[:3]) - np.asarray(t['log_ratios'])) / np.asarray(t['log_ratio_sd_floored'])
    return float(np.mean(residual ** 2)), ratio.tolist()


def fold_profile(means_or_counts, pop=None, window=None, smooth=0.):
    """Pool mirror ideology bins; returns centered-log profile over the 4 folded bins (extreme, moderate, slight, middle).

    With pop/window given, input is event counts per bin (smoothed by `smooth` events per folded bin); else mean rates.
    """
    x = np.asarray(means_or_counts, dtype=float)
    if pop is None:
        raise ValueError("pass counts with pop and window")
    pop = np.asarray(pop, dtype=float)
    rates = np.array([(x[list(g)].sum() + smooth) / pop[list(g)].sum() / window for g in FOLD])
    return profile(rates)


def folded_activity_loss(counts, pop, window, target):
    residual = (fold_profile(counts, pop, window, .5) - np.asarray(target['fold']['profile'])) / np.asarray(target['fold']['profile_bootstrap_sd_floored'])
    return float(np.mean(residual ** 2))


def add_fold_target(source, target):
    """Symmetrized activity target: handles of mirror bins k and 8-k pooled (person level), same bootstrap recipe."""
    source = Path(source)
    counts = pd.read_parquet(source / 'counts.parquet')
    labels = pd.read_csv(source / 'libcon.csv').drop_duplicates('handle').set_index('handle')
    daily = counts.loc[:, pd.to_datetime(counts.columns) < '2021-01-08'].mean(axis=1)
    by_bin = [daily.loc[labels.index[labels.ideological_lean_label.str.startswith(str(k))]].to_numpy() for k in range(1, 8)]
    groups = [np.concatenate([by_bin[i] for i in g]) for g in FOLD]
    rng = np.random.default_rng(1729)
    means = np.array([g.mean() for g in groups])
    logboot = np.log(np.column_stack([rng.choice(g, size=(5000, len(g)), replace=True).mean(axis=1) for g in groups]))
    sd = np.maximum((logboot - logboot.mean(axis=1, keepdims=True)).std(axis=0, ddof=1), .15)
    target['fold'] = {'bins': ['extreme(1+7)', 'moderate(2+6)', 'slight(3+5)', 'middle(4)'], 'means_daily': means.tolist(),
                      'profile': profile(means).tolist(), 'profile_bootstrap_sd_floored': sd.tolist(),
                      'populations': [len(g) for g in groups],
                      'note': 'v2 loss 2026-10-27: left/right asymmetry of the empirical profile is not modelled, so mirror bins are pooled'}
    return target


def network_metrics(edges, n, opinions=None):
    """Two-community detection: leading eigenvector + seeded two-label propagation.

    Identical pipeline on released data and simulated root-attributed event counts.
    Partition found on the undirected weighted projection; Q measured directed.
    Retain the best Q partition among spectral and six propagation runs. LPA may
    collapse to one label, which is never treated as a successful two-camp fit.
    """
    if len(edges) == 0:
        return {"q": 0., "cross": 0., "edges": 0, "events": 0, "component_fraction": 0., "two_communities": False}
    with GRAPH_LOCK:
        ig.set_random_number_generator(random.Random(1729))
        a = np.asarray(edges, dtype=np.int64)
        graph = ig.Graph(n=n, edges=a[:, :2].tolist(), directed=True)
        graph.es['weight'] = a[:, 2].tolist()
        graph.vs['original_id'] = list(range(n))
        graph = graph.components(mode='weak').giant()
        projected = graph.as_undirected(mode='collapse', combine_edges={'weight': 'sum'})
        spectral = projected.community_leading_eigenvector(clusters=2, weights='weight').membership
        partitions = [spectral]
        for k in range(6):
            ig.set_random_number_generator(random.Random(1729 + k))
            partitions.append(projected.community_label_propagation(weights='weight', initial=spectral).membership)
        candidates = [(graph.modularity(p, weights='weight', directed=True), p) for p in partitions if len(set(p)) == 2]
        q, part = max(candidates, key=lambda x: x[0]) if candidates else (0., spectral)
        weights = np.asarray(graph.es['weight'], dtype=float)
        ee = np.asarray(graph.get_edgelist(), dtype=int)
        labels = np.asarray(part)
        cross = float(np.dot(weights, labels[ee[:, 0]] != labels[ee[:, 1]]) / weights.sum())
        out = {"q": float(q), "cross": cross, "edges": graph.ecount(), "events": int(weights.sum()),
               "component_fraction": graph.vcount() / n, "two_communities": len(set(part)) == 2}
        if opinions is not None:
            x = np.asarray(opinions)[graph.vs['original_id']]
            out['q_sign'] = float(graph.modularity((x >= 0).astype(int).tolist(), weights='weight', directed=True))
            # Best correspondence after swapping the names of the two structural communities.
            accuracy = np.mean(labels == (x >= 0))
            out['sign_agreement'] = float(max(accuracy, 1 - accuracy))
        return out


def make_targets(source, output):
    source, output = Path(source), Path(output)
    counts = pd.read_parquet(source / 'counts.parquet')
    labels = pd.read_csv(source / 'libcon.csv').drop_duplicates('handle').set_index('handle')
    dates = pd.to_datetime(counts.columns)
    daily = counts.loc[:, dates < '2021-01-08'].mean(axis=1)
    groups = [daily.loc[labels.index[labels.ideological_lean_label.str.startswith(str(k))]].to_numpy() for k in range(1, 8)]
    rng = np.random.default_rng(1729)
    means = np.array([g.mean() for g in groups])
    boot = np.column_stack([rng.choice(g, size=(5000, len(g)), replace=True).mean(axis=1) for g in groups])
    logboot = np.log(boot)
    clr = logboot - logboot.mean(axis=1, keepdims=True)
    # Stabilized scale: sparse finite panels must not create arbitrarily large weights.
    sd = np.maximum(clr.std(axis=0, ddof=1), .15)
    with zipfile.ZipFile(source / 'conover.zip') as z:
        n = len(z.read('retweet.nodes').decode().splitlines())
        events = collections.Counter(tuple(map(int, row.split('\t')[:2])) for row in z.read('retweet.edgelist').decode().splitlines())
    graph = network_metrics([(a, b, w) for (a, b), w in events.items()], n)
    target = {"window": "2020-01-01 through 2021-01-07", "event_definition": "supplied tweet records; original/retweet collection filters unavailable",
        "primary_model_events": "original_plus_reshare", "means_daily": means.tolist(), "profile": profile(means).tolist(),
        "profile_bootstrap_sd_floored": sd.tolist(), "activity_scale_floor": .15,
        "bin_populations": [len(g) for g in groups], "repost": graph,
        "q_scale": .05, "q_scale_note": "declared calibration tolerance, not an estimated empirical standard error"}
    add_fold_target(source, target)
    output.write_text(json.dumps(target, indent=2) + '\n')
    return target


def read_graph(path):
    x = pd.read_csv(path)
    return x[['source', 'actor', 'count']].to_numpy(dtype=np.int64)


def summarize(run, target, steps):
    run = Path(run)
    actions = pd.read_csv(run / 'metrics/calibration_activity.csv')
    assert actions.step.max() == steps
    snap = pd.read_csv(run / 'degrees/agent_snapshot_final.csv').sort_values('agentId')
    n = len(snap)
    x = snap.intrinsicOpinion.to_numpy()
    bins = np.minimum(((x + 1) * 3.5).astype(int), 6)
    pop = np.bincount(bins, minlength=7)
    if np.any(pop == 0):
        raise ValueError("Empty ideology bin")
    start = max(0, steps - 10000)
    a = actions[actions.start >= start].groupby('agentId')[['nPost', 'nReshare', 'nVisits']].sum().reindex(range(n), fill_value=0)
    out = {'steps': steps, 'window_start': start, 'populations': pop.tolist(), 'n': n}
    for name, amounts in [('original', a.nPost.to_numpy()), ('all', (a.nPost + a.nReshare).to_numpy())]:
        rates = np.bincount(bins, weights=amounts, minlength=7) / pop / (steps - start)
        # Half-event smoothing matters only for a practically silent bin; retain raw rates too.
        smooth = (np.bincount(bins, weights=amounts, minlength=7) + .5) / pop / (steps - start)
        residual = (profile(smooth) - target['profile']) / target['profile_bootstrap_sd_floored']
        out[name + '_rates'] = rates.tolist()
        out[name + '_activity_loss_v1_asym'] = float(np.mean(residual ** 2))
        out[name + '_activity_loss'] = folded_activity_loss(np.bincount(bins, weights=amounts, minlength=7), pop, steps - start, target)
        if target.get('study') == 'uniform-v3':
            out[name + '_activity_loss'], out[name + '_neutral_ratios_smoothed'] = neutral_activity_loss(
                np.bincount(bins, weights=amounts, minlength=7), pop, steps - start, target)
            out[name + '_neutral_ratios'] = equal_side_ratios(rates).tolist() if rates[3] > 0 else None
            out[name + '_left_right_log_gap'] = np.log(smooth[:3] / smooth[6:3:-1]).tolist()
        out[name + '_activity_gini'] = gini(amounts)
        out[name + '_activity_cv'] = float(amounts.std(ddof=1) / amounts.mean()) if amounts.mean() else 0.
        out[name + '_edge_center_ratio'] = float((rates[0] + rates[6]) / (2 * rates[3])) if rates[3] else None
    out['action_counts'] = {k: int(a[k].sum()) for k in a}
    out['zero_activity_fraction'] = float(((a.nPost + a.nReshare) == 0).mean())
    for kind in ['root', 'immediate']:
        ee = np.concatenate([read_graph(run / f'metrics/calibration_{kind}_{t}.csv') for t in sorted(actions.step.unique()) if t > start])
        counter = collections.Counter()
        for s, d, w in ee: counter[(int(s), int(d))] += int(w)
        out[kind] = network_metrics([(s, d, w) for (s, d), w in counter.items()], n, x)
    # Independent consecutive 5000-step activity and root-Q diagnostics.
    windows = []
    for t in [steps - 5000, steps]:
        aa = actions[actions.step == t].sort_values('agentId')
        if len(aa) != n: continue
        rr = np.bincount(bins, weights=(aa.nPost + aa.nReshare).to_numpy(), minlength=7) / pop
        windows.append({'end': int(t), 'profile': profile(rr + 1e-9).tolist(),
                        'q': network_metrics(read_graph(run / f'metrics/calibration_root_{t}.csv'), n)['q']})
    out['consecutive_windows'] = windows
    out['activity_window_drift'] = float(np.sqrt(np.mean((np.array(windows[0]['profile']) - windows[1]['profile']) ** 2))) if len(windows) == 2 else None
    out['q_window_drift'] = abs(windows[0]['q'] - windows[1]['q']) if len(windows) == 2 else None
    degree = snap.followerCount.to_numpy()
    out['degree'] = {'gini': gini(degree), 'zero_fraction': float((degree == 0).mean()),
                     'top1pct_share': float(np.sort(degree)[-max(1, n // 100):].sum() / degree.sum()),
                     'max': int(degree.max()), 'mean': float(degree.mean())}
    out['network_loss'] = float(((out['root']['q'] - target['repost']['q']) / target['q_scale']) ** 2)
    # Degenerate or nearly empty interactions cannot count as a realistic structural match.
    out['valid'] = bool(out['root']['two_communities'] and out['root']['component_fraction'] >= .5
                        and out['root']['events'] >= n and a.nPost.sum() >= n)
    out['loss'] = .5 * (out['all_activity_loss'] + out['network_loss']) + (0 if out['valid'] else 50)
    out['loss_version'] = 3 if target.get('study') == 'uniform-v3' else 2
    return out


def rescore_v1_to_v2(result, target):
    """Recompute the folded (v2) activity loss of a saved v1 job result from its stored per-bin rates."""
    if result.get('status') != 'ok' or result.get('loss_version') == 2:
        return result
    win = result['steps'] - result['window_start']
    for name in ['original', 'all']:
        counts = np.asarray(result[name + '_rates']) * np.asarray(result['populations']) * win
        result[name + '_activity_loss_v1_asym'] = result[name + '_activity_loss']
        result[name + '_activity_loss'] = folded_activity_loss(counts, result['populations'], win, target)
    result['loss_v1_asym'] = result['loss']
    result['loss'] = .5 * (result['all_activity_loss'] + result['network_loss']) + (0 if result['valid'] else 50)
    result['loss_version'] = 2
    return result
