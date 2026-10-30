#!/usr/bin/env python3
"""Resumable calibration of the current attention-economy ABM. See the dated report.

Run with venv/bin/python. --phase full executes pilot, forest/EI optimization,
fresh-seed confirmations, feed/network checks and mechanism checks. New runs use
5 seeds in both search stages and 10 confirmation seeds, all at 40k steps;
historical output directories retain their saved seed/horizon design on resume.
--study uniform-raw-v4 --phase compact uses a separate raw-similarity study,
48 pilot + 16 BO settings, two finalists and a paired 40k horizon check.
No existing baseline output is overwritten or calibrated defaults adopted.
"""
import os
for name in ['OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS']:
    os.environ[name] = '1'
import argparse
import concurrent.futures
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time

import numpy as np
import pandas as pd
from scipy.stats import qmc
from skopt import Optimizer
from skopt.space import Integer, Real
from skopt.learning import RandomForestRegressor
from calibration_metrics import make_targets, summarize, add_uniform_target

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / 'results/calibration_20261027'
SOURCE = ROOT / 'results/empirical_source_audit'
REDUCED_STUDY = 'uniform-raw-reduced-v5'
UNIFORM_STUDIES = {'uniform-v3', 'uniform-raw-v4', REDUCED_STUDY}


class LogInteger(Integer):
    """Correct skopt 0.10.2's integer-log transformed bounds.

    Integer.transform() uses log coordinates with the identity transformer, but
    Integer.transformed_bounds returns physical bounds. Optimizer._tell clips
    proposed log coordinates to those physical bounds, forcing the upper endpoint
    after inverse_transform. Keep the declared discrete prior and fix only this
    coordinate-bound inconsistency; no simulator parameter or observation changes.
    """
    @property
    def transformed_bounds(self):
        if self.transform_ == 'normalize': return 0.,1.
        if self.prior == 'log-uniform': return np.log(self.low)/np.log(self.base),np.log(self.high)/np.log(self.base)
        return self.low,self.high


SPACE = [Real(0, 12, name='beta_h'), Real(.1, 2, name='like_max_dist'),
    Real(.01, .5, prior='log-uniform', name='q_eta'), Real(.02, 2, prior='log-uniform', name='q_tau'),
    Real(0, .3, name='q_eps'), Real(0, 20, name='q_init'), Real(.05, .95, name='rec_fraction'),
    Real(0, 2, name='cost_post'), Real(0, 2, name='cost_reshare'), Real(0, 4, name='cost_rewire'),
    Real(0, 1, name='recog_mix'), Real(.25, 10, prior='log-uniform', name='recog_lambda'),
    Real(10, 3000, prior='log-uniform', name='l_ref'), LogInteger(10, 400, prior='log-uniform', name='dead_after'),
    Real(.02, .3, prior='log-uniform', name='access_prob'), Integer(5, 40, name='feed_capacity'),
    Real(0, 40, name='fy_beta'), Integer(1, 10, name='foryou_hop'), Real(0, 2, name='foryou_hop_lambda'),
    Real(.01, .8, name='rho_l'), Real(.01, .8, name='rho_r'), Integer(1, 10, name='trend_hop'),
    Real(0, 1, name='feed_u'), Real(0, 1, name='feed_v'), Integer(5, 50, name='start_deg')]
NAMES = [d.name for d in SPACE]
BASE = dict(beta_h=3, like_max_dist=1, q_eta=.1, q_tau=.1, q_eps=.05, q_init=10, rec_fraction=.5,
            cost_post=.5, cost_reshare=.25, cost_rewire=1, recog_mix=.5, recog_lambda=2, l_ref=1000,
            dead_after=50, access_prob=.1, feed_capacity=10, fy_beta=10, foryou_hop=5, foryou_hop_lambda=.5,
            rho_l=.3, rho_r=.3, trend_hop=5, feed_u=1, feed_v=.5, start_deg=15)
FULL_SPACE = tuple(SPACE)
REDUCED_FIXED = dict(q_eta=.1, rho_l=.3, rho_r=.3, l_ref=1000,
                     recog_mix=.5, recog_lambda=2, foryou_hop=5, trend_hop=5,
                     foryou_hop_lambda=.5, feed_capacity=10, feed_u=4/9, feed_v=.5)


def search_space(study):
    return [d for d in FULL_SPACE if study != REDUCED_STUDY or d.name not in REDUCED_FIXED]


def configure_study(study):
    """Select optimizer coordinates; simulator tokens retain every fixed input."""
    global SPACE, NAMES
    SPACE = search_space(study)
    NAMES = [d.name for d in SPACE]


def log(message): print(time.strftime('%Y-%m-%d %H:%M:%S'), message, flush=True)
def write_json(path, obj):
    tmp = Path(str(path) + '.tmp')
    tmp.write_text(json.dumps(obj, indent=2, default=lambda x: x.item()) + '\n')
    tmp.replace(path)


def execution_design(output, requested=None):
    """Freeze seed budgets and horizons; preserve historical runs on resume."""
    output = Path(output)
    path = output/'execution_design.json'
    manifest = output/'manifest.json'
    if path.exists():
        design = json.loads(path.read_text())
    elif manifest.exists():
        old = json.loads(manifest.read_text())
        design = {'pilot_seed_count':2, 'bo_seed_count':3, 'confirm_seed_count':20,
                  'search_steps':old.get('search_steps',20000), 'confirm_steps':old.get('confirm_steps',40000)}
    else:
        design = {'pilot_seed_count':5, 'bo_seed_count':5, 'confirm_seed_count':10,
                  'search_steps':40000, 'confirm_steps':40000}
    for key,value in (requested or {}).items():
        if value is None:
            continue
        if key not in design or not isinstance(value,int) or value < 1:
            raise ValueError(f'Invalid execution setting {key}={value}')
        if (path.exists() or manifest.exists()) and design[key] != value:
            raise ValueError(f'Frozen execution design differs at {key}; use a new output directory')
        design[key] = value
    for key in ['search_steps','confirm_steps']:
        if design[key] < 10000 or design[key] % 5000:
            raise ValueError(f'{key} must be at least 10000 and a multiple of 5000')
    write_json(path,design)
    return design


def resource_retry_profile(result, log_text='', timeout=7200):
    """One engineering retry; model/invariant failures never become resource retries."""
    if result.get('status') != 'failed' or result.get('resource_retry'):
        return None
    if 'OutOfMemoryError' in log_text or 'OutOfMemoryError' in result.get('error',''):
        reason='heap_limit'
    elif 'TimeoutExpired' in result.get('error',''):
        reason='timeout'
    else:
        return None
    return {'resource_retry':True,'heap_gb':4,'timeout_seconds':max(timeout,10800),'reason':reason}


def tokens_from(x, study='legacy', network='hkshuf'):
    if network not in ['hkshuf','random','dcsbm']:
        raise ValueError(f'Unsupported fitting network {network}')
    dimensions = search_space(study)
    if len(x) != len(dimensions):
        raise ValueError(f'{study} requires {len(dimensions)} coordinates, received {len(x)}')
    p = dict(zip([d.name for d in dimensions], x))
    if study == REDUCED_STUDY:
        p.update(REDUCED_FIXED)
    types = {d.name:d for d in FULL_SPACE}
    q = {k: (int(v) if isinstance(types[k], Integer) else float(v)) for k,v in p.items()}
    rec = q.pop('rec_fraction'); u = q.pop('feed_u'); v = q.pop('feed_v')
    q.update(w_rec=10 * rec, w_fit=10 * (1 - rec), trend_share=math.sqrt(u) * (1 - v), foryou_share=math.sqrt(u) * v)
    q.update(network='hkshuf', hk_m=q['start_deg'], hk_a=4, hk_pt=.05, learner='bandit',
             rewire=True, rewire_gate=False, init_dist='empirical', fit_mode='relative', fit_baseline='empirical',
             like_gate='noop', notify_original=1, trend_count='both', trend_tie='random',
             foryou_cand_max=300, metrics_heavy_every=100, metrics_every=100, calibration_log=True,
             log_gexf=False, log_repost_cascade=False, log_post_lifespan=False, n=1000, mu=0)
    if study in UNIFORM_STUDIES:
        q['init_dist'] = 'uniform'
    if study in {'uniform-raw-v4', REDUCED_STUDY}:
        q['fit_mode'] = 'raw'
        q.pop('fit_baseline', None)  # no opinion-dependent subtraction
    q['network'] = network
    if network == 'random':
        q['random_p'] = q['start_deg'] / (q['n'] - 1)
    elif network == 'dcsbm':
        q.update(sbm_deg=q['start_deg'], sbm_k=4, sbm_pin=.08, sbm_pout=.002, sbm_gamma=2.3)
    return q


def initial_points(n):
    anchors = []
    for u, v in [(0., .5), (1., 1.), (1., 0.), (1., .5)]:
        for beta in [0., 1., 1.5, 2., 2.5, 3., 6.]:
            b = dict(BASE, feed_u=u, feed_v=v, beta_h=beta)
            anchors.append([b[k] for k in NAMES])
    # Inverse-CDF transform of a scrambled Sobol design, uniform in each declared prior.
    u = qmc.Sobol(len(SPACE), scramble=True, seed=20261027).random_base2(int(np.ceil(np.log2(max(n, 2)))))
    for row in u:
        point = []
        for dim, val in zip(SPACE, row):
            raw = np.exp(np.log(dim.low) + val * np.log(dim.high / dim.low)) if dim.prior == 'log-uniform' else dim.low + val * (dim.high - dim.low)
            point.append(int(np.clip(round(raw), dim.low, dim.high)) if isinstance(dim, Integer) else float(raw))
        anchors.append(point)
    return anchors[:n]


class Runner:
    def __init__(self, output, workers, timeout=7200, study='legacy', design=None, network='hkshuf'):
        self.out = Path(output).resolve(); self.out.mkdir(parents=True, exist_ok=True)
        self.study = study
        self.network = network
        self.workers = workers
        self.job_slots = threading.BoundedSemaphore(workers)
        self.launch_lock = threading.Lock()
        self.timeout = timeout
        for sub in ['runs', 'jobs', 'logs', 'attempts']: (self.out / sub).mkdir(exist_ok=True)
        manifest = self.out / 'manifest.json'
        if manifest.exists():
            saved_study = json.loads(manifest.read_text()).get('study', 'legacy')
            if saved_study != study:
                raise ValueError(f'Cannot mix study {study} with existing {saved_study} outputs')
            saved_network = json.loads(manifest.read_text()).get('primary_network', 'hkshuf')
            if saved_network != network:
                raise ValueError(f'Cannot mix fitting network {network} with existing {saved_network} outputs')
        self.design = execution_design(self.out, design)
        if not manifest.exists():
            shutil.copytree(ROOT / 'src', self.out / 'source')
            for name in ['bayesian_calibration.py', 'calibration_metrics.py']:
                shutil.copy(ROOT / 'scripts' / name, self.out / name)
            files = list((self.out / 'source').rglob('*.java'))
            self.bin = self.out / 'classes'; self.bin.mkdir(exist_ok=True)
            self.cp = os.pathsep.join(map(str, [self.bin, *ROOT.glob('lib/**/*.jar')]))
            subprocess.run(['javac', '-cp', self.cp, '-d', str(self.bin), *map(str, files)], check=True, cwd=ROOT)
            hashes = {str(p.relative_to(self.out)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
            write_json(manifest, {'created_local': time.strftime('%Y-%m-%d %H:%M:%S'), 'sources': hashes, 'study': study,
                'initial_opinions': 'iid uniform [-1,1]' if study in UNIFORM_STUDIES else 'empirical seven-bin composition',
                'activity_measure': 'three equal-side log rate ratios relative to neutral' if study in UNIFORM_STUDIES else 'population-pooled folded profile',
                'space': [{'name': d.name, 'low': d.low, 'high': d.high, 'prior': d.prior, 'integer': isinstance(d, Integer)} for d in SPACE],
                'fixed_parameters': REDUCED_FIXED if study == REDUCED_STUDY else {},
                'n': 1000, 'search_steps': self.design['search_steps'], 'confirm_steps': self.design['confirm_steps'],
                'execution_design':self.design, 'primary_network': network,
                'primary_events': 'original_plus_reshare', 'objectives': 'equal mean of standardized activity and Q squared residuals',
                'seed_policy': f"common search seeds; disjoint {self.design['confirm_seed_count']}-seed confirmations", 'workers': workers})
        self.bin = self.out / 'classes'
        self.cp = os.pathsep.join(map(str, [self.bin, *ROOT.glob('lib/**/*.jar')]))
        target_path = self.out / 'targets.json'
        self.target = json.loads(target_path.read_text()) if target_path.exists() else make_targets(SOURCE, target_path)
        if study in UNIFORM_STUDIES and self.target.get('study') != 'uniform-v3':
            if any((self.out / 'jobs').glob('*.json')):
                raise ValueError('Refusing to change targets after evaluations exist')
            self.target = add_uniform_target(SOURCE, self.target)
            write_json(target_path, self.target)
        if study in UNIFORM_STUDIES:
            metadata = json.loads(manifest.read_text())
            identity = {
                'measurement_sha256': hashlib.sha256((ROOT/'scripts/calibration_metrics.py').read_bytes()).hexdigest(),
                'target_sha256': hashlib.sha256(target_path.read_bytes()).hexdigest(),
                'base_tokens': tokens_from([BASE[k] for k in NAMES], study, network),
            }
            if 'measurement_identity' in metadata and metadata['measurement_identity'] != identity:
                raise ValueError('Frozen measurement/target/base specification changed; use a separate output directory')
            metadata['measurement_identity'] = identity
            metadata.setdefault('python_sources', {name:hashlib.sha256((ROOT/'scripts'/name).read_bytes()).hexdigest()
                                        for name in ['bayesian_calibration.py','calibration_metrics.py']})
            write_json(manifest, metadata)

    def active_pid(self, key):
        listing = subprocess.check_output(['ps', '-Ao', 'pid,command'], text=True)
        for line in listing.splitlines():
            if 'dynamics.OpinionDynamics' in line and ('run_id=' + key) in line:
                return int(line.strip().split(None, 1)[0])
        return None

    def active_simulators(self):
        prefix='results_subdir='+self.out.relative_to(ROOT/'results').as_posix()+'/runs/'
        result=[]
        for line in subprocess.check_output(['ps','-Ao','pid,command'],text=True).splitlines()[1:]:
            parts=line.strip().split(None,1)
            if len(parts)!=2:continue
            pid,command=parts
            if command.split()[0].endswith('/java') and 'dynamics.OpinionDynamics' in command and prefix in command:
                result.append(int(pid))
        return result

    def launch_simulator(self, cmd, stream, timeout, config_path):
        # Orphaned JVMs survive manager reload. Count those too before launching
        # retries; a semaphore alone only accounts for threads in this manager.
        with self.launch_lock:
            while len(self.active_simulators()) >= self.workers:
                time.sleep(2)
            config_path.touch()
            process=subprocess.Popen(cmd,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
        try:
            code=process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill();process.wait()
            raise
        if code:raise subprocess.CalledProcessError(code,cmd)

    def job(self, point, seed, phase, steps=20000, overrides=None):
        # Pilot/refinement pools may overlap; enforce the run-wide bound as well.
        with self.job_slots:
            result=self._job(point, seed, phase, steps, overrides)
            if result['status']=='failed' and not result.get('resource_retry'):
                logfile=self.out/'logs'/(result['key']+'.log')
                text=logfile.read_text() if logfile.exists() else ''
                if resource_retry_profile(result,text,self.timeout):
                    return self._job(point, seed, phase, steps, overrides)
            return result

    def _job(self, point, seed, phase, steps=20000, overrides=None):
        tokens = tokens_from(point, self.study, self.network); tokens.update(overrides or {}); tokens['steps'] = steps
        key = hashlib.sha256(json.dumps([tokens, seed], sort_keys=True).encode()).hexdigest()[:16]
        saved = self.out / 'jobs' / (key + '.json')
        resource_path=self.out/'runs'/key/'resources.json'
        resources=json.loads(resource_path.read_text()) if resource_path.exists() else {
            'resource_retry':False,'heap_gb':2,'timeout_seconds':self.timeout}
        if saved.exists():
            result = json.loads(saved.read_text())
            if result['status'] == 'ok': return result
            # Computational censoring is not evidence of poor scientific fit.
            old_log=self.out/'logs'/(key+'.log')
            resources=resource_retry_profile(result,old_log.read_text() if old_log.exists() else '',self.timeout)
            if resources is None:return result
            saved.rename(self.out / 'attempts' / (key + '_' + str(time.time_ns()) + '.json'))
            resource_path.parent.mkdir(parents=True,exist_ok=True)
            write_json(resource_path,resources)
            log(f"{phase}: resource retry {key}, {resources['reason']}, heap=4g, timeout={resources['timeout_seconds']}s")
        job_timeout=resources['timeout_seconds']
        run_subdir = self.out.relative_to(ROOT / 'results').as_posix() + '/runs/' + key
        tokens.update(seed=seed, results_subdir=run_subdir, run_id=key)
        folder = ROOT / 'results' / run_subdir / f'run_{seed}_id-{key}'
        config_path = self.out / 'runs' / key / 'config.json'
        config_path.parent.mkdir(parents=True, exist_ok=True)
        logfile = self.out / 'logs' / (key + '.log')
        start_wall = config_path.stat().st_mtime if config_path.exists() else time.time()
        inherited_pid = self.active_pid(key) if folder.exists() else None
        if inherited_pid:
            log(f'{phase}: adopting running JVM {inherited_pid} for {key}')
            while self.active_pid(key) is not None:
                if time.time() - start_wall > job_timeout:
                    os.kill(inherited_pid, 15)
                    result = {'key': key, 'seed': seed, 'phase': phase, 'point': point, 'tokens': tokens,
                        'run_dir': str(folder), 'status': 'failed', 'error': 'TimeoutExpired: inherited JVM exceeded extended timeout',
                        'loss': 1000, 'seconds': time.time() - start_wall, **resources}
                    write_json(saved, result)
                    return result
                time.sleep(5)
        complete = folder.exists() and logfile.exists() and 'the sum of error reported : 0' in logfile.read_text()
        if not complete:
            # Preserve interrupted output and old attempts; completed exact-hash output is adopted.
            if folder.exists(): folder.rename(folder.with_name(folder.name + '_interrupted_' + str(time.time_ns())))
            if logfile.exists(): shutil.copy(logfile, self.out / 'attempts' / (key + '_' + str(time.time_ns()) + '.log'))
            write_json(config_path, tokens)
            start_wall = time.time()
        cmd = ['java', f"-Xmx{resources['heap_gb']}g", '-XX:+UseSerialGC', '-XX:ActiveProcessorCount=1', '-XX:+ExitOnOutOfMemoryError',
               '-cp', self.cp, 'dynamics.OpinionDynamics', *[f'{k}={str(v).lower() if isinstance(v, bool) else v}' for k, v in tokens.items()]]
        result = {'key': key, 'seed': seed, 'phase': phase, 'point': point, 'tokens': tokens, 'run_dir': str(folder), **resources}
        try:
            if not complete:
                with logfile.open('w') as stream:
                    stream.write(' '.join(cmd) + '\n'); stream.flush()
                    self.launch_simulator(cmd,stream,job_timeout,config_path)
                    start_wall=config_path.stat().st_mtime
            stdout = logfile.read_text()
            if 'the sum of error reported : 0' not in stdout or 'AC Error:' in stdout:
                raise RuntimeError('Simulator invariant failure or incomplete run')
            result.update(summarize(folder, self.target, steps), status='ok')
        except Exception as e:
            result.update(status='failed', error=f'{type(e).__name__}: {e}', loss=1000)
        result['seconds'] = time.time() - start_wall
        result['timeout_seconds'] = job_timeout
        result['adopted_existing_output'] = bool(complete)
        write_json(saved, result)
        log(f"{phase} seed={seed} {key} {result['status']} {result['seconds']:.0f}s loss={result['loss']:.3f}")
        return result

    def batch(self, points, seeds, phase, steps=20000, overrides=None):
        work = [(i, p, s) for i, p in enumerate(points) for s in seeds]
        results = [[] for _ in points]
        log(f'{phase}: {len(points)} points x {len(seeds)} seeds, workers={self.workers}')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as pool:
            futures = {pool.submit(self.job, p, s, phase, steps, overrides): i for i, p, s in work}
            for future in concurrent.futures.as_completed(futures): results[futures[future]].append(future.result())
        return self.aggregate(points, results, phase)

    def initial_with_pending(self, points, seeds):
        """Begin refinement with at most four pending pilot points; retain the tail."""
        pool=concurrent.futures.ThreadPoolExecutor(max_workers=self.workers)
        steps=getattr(self,'design',{}).get('search_steps',20000)
        futures={pool.submit(self.job,p,s,'pilot',steps):i for i,p in enumerate(points) for s in seeds}
        by_point=[[f for f,i in futures.items() if i==j] for j in range(len(points))]
        minimum=max(1,len(points)-4)
        log(f'pilot: {len(points)} points x {len(seeds)} seeds; refinement may overlap up to four pending points')
        for future in concurrent.futures.as_completed(futures):
            future.result()  # propagate orchestration errors instead of silently losing a point
            ready=[i for i,ff in enumerate(by_point) if all(f.done() for f in ff)]
            if len(ready)>=minimum:break
        pool.shutdown(wait=False)
        ready_set=set(ready)
        rows=self.aggregate([points[i] for i in ready],[[f.result() for f in by_point[i]] for i in ready],'pilot')
        pending=[{'point':points[i],'futures':by_point[i]} for i in range(len(points)) if i not in ready_set]
        return rows,pending

    def collect_pending(self, pending, wait=False):
        rows=[];remaining=[]
        for item in pending:
            if wait or all(f.done() for f in item['futures']):
                rows.extend(self.aggregate([item['point']],[[f.result() for f in item['futures']]],'pilot'))
            else:remaining.append(item)
        return rows,remaining

    def experiments(self, specifications):
        """Independent validation conditions share one bounded worker pool."""
        results = [[[] for _ in spec['points']] for spec in specifications]
        work = [(i, j, point, seed, spec) for i, spec in enumerate(specifications)
                for j, point in enumerate(spec['points']) for seed in spec['seeds']]
        log(f'validation bundle: {len(work)} jobs, workers={self.workers}')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as pool:
            futures = {pool.submit(self.job, point, seed, spec['phase'], spec.get('steps',40000), spec.get('overrides')): (i,j)
                       for i,j,point,seed,spec in work}
            for future in concurrent.futures.as_completed(futures):
                i,j=futures[future];results[i][j].append(future.result())
        combined=[]
        for spec, rows in zip(specifications, results):
            combined.extend(self.aggregate(spec['points'],rows,spec['phase']))
        return combined

    @staticmethod
    def aggregate(points, results, phase):
        aggregated = []
        for point, rows in zip(points, results):
            ok = [r for r in rows if r['status'] == 'ok']
            row = {'point': point, 'phase': phase, 'seed_count': len(rows), 'failed': len(rows) - len(ok),
                   'job_keys': [r['key'] for r in rows], 'loss': float(np.mean([r['loss'] for r in rows]))}
            for k in ['all_activity_loss', 'original_activity_loss', 'network_loss', 'activity_window_drift', 'q_window_drift']:
                vals = [r[k] for r in ok if r.get(k) is not None]
                row[k] = float(np.mean(vals)) if vals else None
            row['q'] = float(np.mean([r['root']['q'] for r in ok])) if ok else None
            row['valid_fraction'] = sum(r['valid'] for r in ok) / len(rows)
            row['loss_seed_sd'] = float(np.std([r['loss'] for r in rows], ddof=1)) if len(rows) > 1 else None
            aggregated.append(row)
        return aggregated


def choose_candidates(rows, number=4):
    valid = [r for r in rows if r['failed'] == 0 and r['valid_fraction'] >= .5]
    chosen = []
    for key in ['loss', 'all_activity_loss', 'network_loss']:
        for row in sorted(valid, key=lambda r: r[key]):
            if row['point'] not in [r['point'] for r in chosen]: chosen.append(row); break
    # Avoid spending all confirmations on numerically indistinguishable nearby points.
    for row in sorted(valid, key=lambda r: r['loss']):
        if row['point'] not in [r['point'] for r in chosen]: chosen.append(row)
        if len(chosen) >= number: break
    return chosen[:number]


def refine_async(runner, pilot, pending, budget, optimizer=None):
    """Keep up to twelve points in flight; fit only genuine completed observations."""
    opt = optimizer or Optimizer(SPACE, base_estimator=RandomForestRegressor(n_estimators=100, min_samples_leaf=2,
                    n_jobs=1, random_state=1729), acq_func='EI', acq_optimizer='sampling',
                    n_initial_points=0, random_state=20261027, acq_optimizer_kwargs={'n_points': 6000})
    pilot=list(pilot)
    arrived,pending=runner.collect_pending(pending)
    pilot.extend(arrived)
    write_json(runner.out/'pilot.json',pilot)
    write_json(runner.out/'pilot_pending.json',[r['point'] for r in pending])
    observed=[r for r in pilot if r['failed']==0]
    opt.tell([r['point'] for r in observed], [r['loss'] for r in observed])
    path=runner.out/'bo_async_design.json'
    if path.exists():design=json.loads(path.read_text())
    else:
        design=[]
        for f in sorted(runner.out.glob('bo_design_*.json')):design.extend(json.loads(f.read_text()))
        write_json(path,design)
    if len(design)>budget:raise ValueError('Existing proposal history exceeds the requested budget')
    completed={};active={}
    design_settings=getattr(runner,'design',{})
    # Runner.job's shared semaphore already bounds overlapping pilot/BO pools.
    # A one-time reservation here would leave BO permanently throttled after
    # the pilot tail finishes, especially with five seeds and eight workers.
    workers=runner.workers
    pool=concurrent.futures.ThreadPoolExecutor(max_workers=workers)
    def submit(index,point):
        active[index]={'point':point,'futures':[pool.submit(runner.job,point,seed,f'bo_{index//8:02}',
                                                         design_settings.get('search_steps',20000))
                                               for seed in range(271000,271000+design_settings.get('bo_seed_count',3))]}
    for i,point in enumerate(design):submit(i,point)
    log(f'Asynchronous BO: budget={budget}, workers={workers}, max pending points=12')
    try:
        while active or len(design)<budget:
            changed=False
            arrived,pending=runner.collect_pending(pending)
            if arrived:
                pilot.extend(arrived);changed=True
                observed=[r for r in arrived if r['failed']==0]
                if observed:opt.tell([r['point'] for r in observed],[r['loss'] for r in observed])
                write_json(runner.out/'pilot.json',pilot)
                write_json(runner.out/'pilot_pending.json',[r['point'] for r in pending])
            done=[i for i,item in active.items() if all(f.done() for f in item['futures'])]
            for i in sorted(done):
                item=active.pop(i)
                row=runner.aggregate([item['point']],[[f.result() for f in item['futures']]],f'bo_{i//8:02}')[0]
                completed[i]=row;changed=True
                if row['failed']==0:opt.tell([row['point']],[row['loss']])
                write_json(runner.out/f'bo_point_{i:03}.json',row)
                log(f'BO point {i+1}/{budget}: loss={row["loss"]:.3f}; completed={len(completed)}')
            while len(active)<12 and len(design)<budget:
                # Constant-liar copies reserve unfinished points, never altering the real observations.
                work=opt.copy(random_state=20261027+len(design))
                reserved=[item['point'] for item in active.values()]+[item['point'] for item in pending]
                known=pilot+list(completed.values())
                best=min(r['loss'] for r in known if r['failed']==0)
                if reserved:work.tell(reserved,[best]*len(reserved))
                point=work.ask()
                if point in design:point=opt.space.rvs(n_samples=1,random_state=20271027+len(design))[0]
                index=len(design);design.append(point)
                write_json(path,design)
                with (runner.out/'bo_async_history.jsonl').open('a') as f:
                    f.write(json.dumps({'index':index,'initial_points_ready':len(pilot),'observed_bo_indices':sorted(completed),
                                        'pending_bo_indices':sorted(active)},default=lambda x:x.item())+'\n')
                submit(index,point)
            if changed:
                rows=pilot+[completed[i] for i in sorted(completed)]
                write_json(runner.out/'search.json',rows)
                for group in range(math.ceil(budget/8)):
                    indices=list(range(group*8,min((group+1)*8,budget)))
                    if all(i in completed for i in indices):
                        write_json(runner.out/f'bo_{group:02}.json',[completed[i] for i in indices])
            if active:
                futures=[f for item in active.values() for f in item['futures'] if not f.done()]
                if futures:concurrent.futures.wait(futures,timeout=30,return_when=concurrent.futures.FIRST_COMPLETED)
    finally:pool.shutdown(wait=True)
    arrived,pending=runner.collect_pending(pending,wait=True)
    pilot.extend(arrived)
    write_json(runner.out/'pilot.json',pilot)
    write_json(runner.out/'pilot_pending.json',[])
    return pilot+[completed[i] for i in sorted(completed)]


def full(runner, args):
    points = initial_points(args.pilot)
    write_json(runner.out / 'pilot_design.json', points)
    pilot,pending = runner.initial_with_pending(points, list(range(271000,271000+runner.design['pilot_seed_count'])))
    write_json(runner.out / 'pilot.json', pilot)
    write_json(runner.out / 'pilot_pending.json', [r['point'] for r in pending])
    all_rows=refine_async(runner,pilot,pending,args.bo)
    write_json(runner.out / 'search.json', all_rows)
    finalists = choose_candidates(all_rows, 4)
    write_json(runner.out / 'finalists.json', finalists)
    confirm = runner.batch([r['point'] for r in finalists], list(range(272000, 272000+runner.design['confirm_seed_count'])),
                           f"confirm{runner.design['confirm_steps']//1000}k", steps=runner.design['confirm_steps'])
    write_json(runner.out / 'confirm.json', confirm)
    best = [r for r in sorted(confirm, key=lambda r: r['loss']) if r['failed']==0 and r['valid_fraction']>=.5][:2]
    if not best: raise RuntimeError('No viable confirmed candidate; inspect completed results before validation')
    specifications = []
    for network in [n for n in ['random','hk','dcsbm','hkshuf'] if n != runner.network]:
        for b in best:
            t = tokens_from(b['point'],runner.study,runner.network); overrides = {'network': network}
            if network == 'dcsbm': overrides['sbm_deg'] = t['start_deg']
            if network == 'random': overrides['random_p'] = t['start_deg'] / (t['n'] - 1)
            specifications.append({'points':[b['point']], 'seeds':list(range(273000,273005)),
                                   'phase':'network_'+network,'overrides':overrides})
    for feed, overrides in [('chrono', {'foryou_share': 0., 'trend_share': 0.}),
                            ('foryou', {'foryou_share': 1., 'trend_share': 0.}),
                            ('trend', {'foryou_share': 0., 'trend_share': 1.})]:
        specifications.append({'points':[b['point'] for b in best], 'seeds':list(range(274000,274005)),
                               'phase':'feed_'+feed,'overrides':overrides})
    # Mechanism checks do not replace the calibrated standing specification.
    for label, overrides in [('gate_on', {'rewire_gate': True}), ('rewire_off', {'rewire': False}),
            ('learner_q', {'learner': 'q', 'q_gamma': .9}), ('notify_off', {'notify_original': 0}),
            ('fit_raw', {'fit_mode': 'raw'}), ('post_noise', {'post_noise': .2}),
            ('credit_post', {'credit': 'post', 'credit_horizon': 50})]:
        specifications.append({'points':[best[0]['point']], 'seeds':list(range(275000,275003)),
                               'phase':'mechanism_'+label,'overrides':overrides})
    if runner.study in UNIFORM_STUDIES:
        # Longer horizon checks whether the fitted shape is a transient. No empirical composition here.
        specifications.append({'points':[b['point'] for b in best], 'seeds':list(range(278000,278005)),
                               'phase':'horizon80k', 'steps':80000})
        specifications.append({'points':[best[0]['point']], 'seeds':list(range(278100,278105)),
                               'phase':'mechanism_beta_zero', 'overrides':{'beta_h':0.}})
    validation = runner.experiments(specifications)
    write_json(runner.out / 'validation.json', validation)
    write_json(runner.out / 'COMPLETE.json', {'finished_local': time.strftime('%Y-%m-%d %H:%M:%S'),
                'search_points': len(all_rows), 'confirmed_points': len(confirm), 'validation_settings': len(validation)})
    log('CALIBRATION COMPLETE')


def compact_points(number=48, study='uniform-raw-v4'):
    """Eight controlled anchors plus space-filling draws over all 25 priors."""
    anchors = initial_points(28)
    if study == REDUCED_STUDY:
        selected = []
        for beta, recognition in [(0,.5), (1,.5), (2,.5), (3,.5), (6,.5), (12,.5), (3,.2), (3,.8)]:
            point = dict(BASE, beta_h=beta, rec_fraction=recognition)
            selected.append([point[k] for k in NAMES])
    else:
        selected = [anchors[i] for i in [0, 5, 7, 12, 14, 19, 21, 26]]
    if number < len(selected):
        raise ValueError('Compact pilot needs at least eight settings')
    return selected + initial_points(28 + number - len(selected))[28:]


def compact(runner, args):
    """Bounded raw-fit search; defer blanket transfer/feed/mechanism matrices."""
    plan = {'study': runner.study, 'pilot': args.pilot, 'bo': args.bo,
            'finalists': 2, 'horizon_finalists': 1, 'horizon_seeds': 5,
            'horizon_steps': 40000, 'execution': runner.design,
            'search_parameters':NAMES, 'fixed_parameters':REDUCED_FIXED if runner.study == REDUCED_STUDY else {}}
    path = runner.out/'compact_design.json'
    if path.exists() and json.loads(path.read_text()) != plan:
        raise ValueError('Frozen compact design differs; use a new output directory')
    write_json(path, plan)
    points = compact_points(args.pilot, runner.study)
    write_json(runner.out/'pilot_design.json', points)
    pilot, pending = runner.initial_with_pending(points, list(range(271000, 271000+runner.design['pilot_seed_count'])))
    rows = refine_async(runner, pilot, pending, args.bo)
    write_json(runner.out/'search.json', rows)
    finalists = choose_candidates(rows, 2)
    if not finalists:
        raise RuntimeError('No viable search candidate; inspect results before proceeding')
    write_json(runner.out/'finalists.json', finalists)
    confirm = runner.batch([r['point'] for r in finalists],
                           list(range(272000, 272000+runner.design['confirm_seed_count'])),
                           'confirm20k', steps=runner.design['confirm_steps'])
    write_json(runner.out/'confirm.json', confirm)
    best = [r for r in sorted(confirm, key=lambda r:r['loss'])
            if r['failed']==0 and r['valid_fraction']>=.5]
    if not best:
        raise RuntimeError('No viable confirmed candidate; inspect results before proceeding')
    # Paired seeds distinguish horizon effects from a change in seed sample.
    validation = runner.experiments([{'points':[best[0]['point']],
        'seeds':list(range(272000, 272005)), 'phase':'horizon40k', 'steps':40000}])
    write_json(runner.out/'validation.json', validation)
    write_json(runner.out/'COMPLETE.json', {'finished_local':time.strftime('%Y-%m-%d %H:%M:%S'),
        'profile':'compact-raw', 'search_points':len(rows), 'confirmed_points':len(confirm),
        'validation_settings':len(validation), 'interpretation':'20k screening; inspect paired 40k horizon check before accepting fit'})


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--phase', choices=['smoke', 'full', 'compact'], default='full')
    p.add_argument('--output', type=Path, default=None)
    p.add_argument('--study', choices=['legacy', 'uniform-v3', 'uniform-raw-v4', REDUCED_STUDY], default='legacy')
    p.add_argument('--network', choices=['hkshuf','random','dcsbm'], default='hkshuf',
                   help='Network family used throughout fitting and confirmation')
    p.add_argument('--workers', type=int, default=16)
    p.add_argument('--pilot', type=int, default=None)
    p.add_argument('--bo', type=int, default=None, help='Defaults to the saved run budget, or 64 for a new run')
    p.add_argument('--timeout', type=int, default=7200)
    p.add_argument('--search-seeds', type=int, help='Seeds per pilot/BO setting; new runs default to 5')
    p.add_argument('--confirm-seeds', type=int, help='Fresh seeds per confirmation; new runs default to 10')
    p.add_argument('--search-steps', type=int, help='New runs default to 40000, matching confirmation')
    p.add_argument('--confirm-steps', type=int, help='New runs default to 40000')
    args = p.parse_args()
    configure_study(args.study)
    if args.pilot is None:
        args.pilot = 48 if args.phase == 'compact' else 128
    if args.phase == 'compact' and args.study not in {'uniform-raw-v4', REDUCED_STUDY}:
        p.error('Compact search requires a separate raw-fit study')
    if args.output is None and args.study == REDUCED_STUDY:
        args.output = ROOT / 'results/calibration_raw_reduced_20261029' / args.network
    if args.output is None and args.study == 'uniform-raw-v4':
        args.output = ROOT / 'results/calibration_raw_20261029' / args.network
    if args.output is None:
        args.output = ROOT / 'results/calibration_uniform_20261028' if args.study == 'uniform-v3' else DEFAULT_OUT
        if args.network != 'hkshuf': args.output = args.output.with_name(args.output.name+'_'+args.network)
    if args.bo is None:
        saved_budget=args.output.resolve()/'refinement_budget.json'
        args.bo=int(json.loads(saved_budget.read_text())['total_bo_points']) if saved_budget.exists() else (16 if args.phase == 'compact' else 64)
    if args.phase == 'compact':
        if args.search_steps is None: args.search_steps = 20000
        if args.confirm_steps is None: args.confirm_steps = 20000
        if args.search_steps != 20000 or args.confirm_steps != 20000:
            p.error('Compact profile fixes both search and confirmation at 20000 steps')
        if args.search_seeds not in (None, 5) or args.confirm_seeds not in (None, 10):
            p.error('Compact profile requires five search seeds and ten confirmation seeds')
    requested={'pilot_seed_count':args.search_seeds,'bo_seed_count':args.search_seeds,
               'confirm_seed_count':args.confirm_seeds,'search_steps':args.search_steps,'confirm_steps':args.confirm_steps}
    runner = Runner(args.output, args.workers, args.timeout, args.study, requested, args.network)
    if args.phase == 'smoke':
        rows = runner.batch([[BASE[k] for k in NAMES]], [270000, 270001], 'smoke', steps=1000)
        write_json(runner.out / 'smoke.json', rows)
    elif args.phase == 'compact': compact(runner, args)
    else: full(runner, args)


if __name__ == '__main__': main()
