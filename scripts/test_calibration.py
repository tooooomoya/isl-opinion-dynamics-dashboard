"""Measurement tests; run with venv/bin/python -m unittest discover -s scripts -p test_calibration.py."""
import unittest
import tempfile
import json
from pathlib import Path
import numpy as np
from bayesian_calibration import ROOT, SPACE, NAMES, BASE, Runner, LogInteger, initial_points, tokens_from, refine_async, execution_design, resource_retry_profile
from calibration_metrics import network_metrics, profile, equal_side_ratios, neutral_activity_loss


class CalibrationTests(unittest.TestCase):
    def test_reduced_coordinates_preserve_fixed_inputs_and_report_tokens(self):
        import bayesian_calibration as bc
        from analyze_bayesian_calibration import flat_row
        names=[d.name for d in bc.search_space(bc.REDUCED_STUDY)]
        self.assertEqual(len(names),13)
        self.assertEqual(len(bc.REDUCED_FIXED),12)
        point=[BASE[k] for k in names]
        for network in ['hkshuf','random','dcsbm']:
            tokens=tokens_from(point,bc.REDUCED_STUDY,network)
            self.assertEqual(tokens['fit_mode'],'raw')
            self.assertEqual(tokens['init_dist'],'uniform')
            self.assertAlmostEqual(tokens['trend_share'],1/3)
            self.assertAlmostEqual(tokens['foryou_share'],1/3)
            for key,value in bc.REDUCED_FIXED.items():
                if key not in ['feed_u','feed_v']: self.assertEqual(tokens[key],value)
        with self.assertRaisesRegex(ValueError,'requires 13 coordinates'):
            tokens_from([BASE[k] for k in NAMES],bc.REDUCED_STUDY)
        try:
            bc.configure_study(bc.REDUCED_STUDY)
            points=bc.compact_points(48,bc.REDUCED_STUDY)
            self.assertEqual(len(points),48)
            self.assertTrue(all(len(p)==13 for p in points))
            self.assertEqual(len({tuple(p) for p in points}),48)
            for p in points:
                self.assertTrue(all(d.low<=v<=d.high for d,v in zip(bc.SPACE,p)))
            self.assertEqual({p[bc.NAMES.index('beta_h')] for p in points[:8]}, {0,1,2,3,6,12})
            from unittest.mock import patch
            with patch('analyze_bayesian_calibration.NAMES', names):
                row=flat_row({'point':point},bc.REDUCED_STUDY)
            self.assertEqual(row['start_deg'],15)
            self.assertAlmostEqual(row['foryou_share'],1/3)
            from skopt import Optimizer
            from skopt.learning import RandomForestRegressor
            optimizer=Optimizer(bc.SPACE, base_estimator=RandomForestRegressor(n_estimators=10, random_state=1),
                                n_initial_points=0, acq_optimizer='sampling', random_state=1,
                                acq_optimizer_kwargs={'n_points':100})
            optimizer.tell(points[:12], list(range(12)))
            proposal=optimizer.ask()
            self.assertEqual(len(proposal),13)
            self.assertEqual(tokens_from(proposal,bc.REDUCED_STUDY)['q_eta'],.1)
        finally:
            bc.configure_study('legacy')

    def test_compact_workflow_uses_fresh_confirmation_and_paired_horizon_seeds(self):
        from types import SimpleNamespace
        from unittest.mock import Mock, patch
        from bayesian_calibration import compact
        points = [[BASE[k] for k in NAMES], [BASE[k]+(.01 if k=='beta_h' else 0) for k in NAMES]]
        rows = [dict(point=p, failed=0, valid_fraction=1., loss=i+1.,
                     all_activity_loss=i+1., network_loss=i+1.) for i,p in enumerate(points)]
        with tempfile.TemporaryDirectory() as tmp:
            runner=Mock(out=Path(tmp), study='uniform-raw-v4', design={
                'pilot_seed_count':5, 'bo_seed_count':5, 'confirm_seed_count':10,
                'search_steps':20000, 'confirm_steps':20000})
            runner.initial_with_pending.return_value=([],[])
            runner.batch.return_value=rows
            runner.experiments.return_value=[]
            with patch('bayesian_calibration.refine_async',return_value=rows):
                compact(runner, SimpleNamespace(pilot=48, bo=16))
            search_seeds=runner.initial_with_pending.call_args.args[1]
            confirmation_seeds=runner.batch.call_args.args[1]
            self.assertEqual(len(search_seeds),5)
            self.assertEqual(len(confirmation_seeds),10)
            self.assertFalse(set(search_seeds)&set(confirmation_seeds))
            self.assertEqual(runner.batch.call_args.kwargs['steps'],20000)
            horizon=runner.experiments.call_args.args[0][0]
            self.assertEqual(horizon['seeds'],confirmation_seeds[:5])
            self.assertEqual(horizon['steps'],40000)
            self.assertEqual(len(horizon['points']),1)

    def test_raw_study_is_separate_and_historical_tokens_unchanged(self):
        from bayesian_calibration import compact_points
        point = [BASE[k] for k in NAMES]
        for network in ['hkshuf', 'random', 'dcsbm']:
            raw = tokens_from(point, 'uniform-raw-v4', network)
            self.assertEqual(raw['fit_mode'], 'raw')
            self.assertEqual(raw['init_dist'], 'uniform')
            self.assertNotIn('fit_baseline', raw)
            old = tokens_from(point, 'uniform-v3', network)
            self.assertEqual(old['fit_mode'], 'relative')
            self.assertEqual(old['fit_baseline'], 'empirical')
        self.assertEqual(len(compact_points()), 48)
        self.assertEqual(len({tuple(p) for p in compact_points()}), 48)
        # The reduced pilot must still explore each dimension beyond its anchor value.
        self.assertTrue(all(len(set(p[i] for p in compact_points()[8:])) > 1 for i in range(len(NAMES))))
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'manifest.json').write_text(json.dumps({'study':'uniform-v3'}))
            with self.assertRaisesRegex(ValueError, 'Cannot mix study'):
                Runner(Path(tmp), 1, study='uniform-raw-v4')

    def test_launch_waits_for_inherited_simulator_capacity(self):
        import threading
        from unittest.mock import Mock,patch
        runner=Runner.__new__(Runner);runner.workers=2;runner.launch_lock=threading.Lock()
        runner.active_simulators=Mock(side_effect=[[1,2],[1]])
        process=Mock();process.wait.return_value=0
        with tempfile.TemporaryDirectory() as tmp,patch('bayesian_calibration.subprocess.Popen',return_value=process) as launch,patch('bayesian_calibration.time.sleep') as sleep:
            runner.launch_simulator(['java','example'],None,100,Path(tmp)/'config.json')
            self.assertEqual(runner.active_simulators.call_count,2)
            sleep.assert_called_once_with(2)
            launch.assert_called_once()
            process.wait.assert_called_once_with(timeout=100)

    def test_resource_failure_classification_and_retry_bound(self):
        failure={'status':'failed','error':'TimeoutExpired'}
        self.assertEqual(resource_retry_profile(failure)['timeout_seconds'],10800)
        self.assertEqual(resource_retry_profile(failure,'OutOfMemoryError')['reason'],'heap_limit')
        self.assertIsNone(resource_retry_profile({**failure,'resource_retry':True}))
        self.assertIsNone(resource_retry_profile({'status':'failed','error':'RuntimeError: invariant failure'}))

    def test_heap_retry_preserves_tokens_and_archives_first_attempt(self):
        import subprocess
        import threading
        from unittest.mock import patch
        with tempfile.TemporaryDirectory(dir=ROOT/'results',prefix='test_resource_retry_') as tmp:
            runner=Runner.__new__(Runner)
            runner.out=Path(tmp);runner.study='uniform-v3';runner.network='hkshuf'
            runner.timeout=7200;runner.cp='unused';runner.target={}
            runner.job_slots=threading.BoundedSemaphore(1)
            runner.active_pid=lambda key:None
            for name in ['jobs','logs','runs','attempts']:(runner.out/name).mkdir()
            calls=[]
            def simulate(cmd,stream,timeout,config_path):
                calls.append((cmd,timeout))
                if len(calls)==1:
                    stream.write('Terminating due to java.lang.OutOfMemoryError: Java heap space\n')
                    raise subprocess.CalledProcessError(3,cmd)
                stream.write('the sum of error reported : 0\n')
                return subprocess.CompletedProcess(cmd,0)
            with patch.object(runner,'launch_simulator',side_effect=simulate,create=True),patch('bayesian_calibration.summarize',return_value={'loss':1.}):
                result=runner.job([BASE[k] for k in NAMES],1,'test')
                self.assertEqual(runner.job([BASE[k] for k in NAMES],1,'test')['status'],'ok')
            self.assertEqual(len(calls),2)
            self.assertEqual(calls[0][0][1],'-Xmx2g');self.assertEqual(calls[1][0][1],'-Xmx4g')
            self.assertEqual(calls[0][0][2:],calls[1][0][2:])
            self.assertEqual([c[1] for c in calls],[7200,10800])
            self.assertTrue(result['resource_retry']);self.assertEqual(result['status'],'ok')
            self.assertEqual(len(list((runner.out/'attempts').glob('*.json'))),1)
            self.assertTrue((runner.out/'runs'/result['key']/'resources.json').exists())

    def test_overlapping_pools_respect_run_wide_worker_limit(self):
        import concurrent.futures
        import threading
        import time
        runner=Runner.__new__(Runner)
        runner.job_slots=threading.BoundedSemaphore(2)
        lock=threading.Lock();active=0;peak=0
        def work(*args):
            nonlocal active,peak
            with lock:active+=1;peak=max(peak,active)
            time.sleep(.01)
            with lock:active-=1
            return {'status':'ok'}
        runner._job=work
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            self.assertEqual(list(pool.map(lambda seed:runner.job([],seed,'overlap'),range(12))),[{'status':'ok'}]*12)
        self.assertEqual(peak,2)

    def test_network_specific_density_and_resume_identity(self):
        point=[BASE[k] for k in NAMES]
        for degree in [5,15,50]:
            point[NAMES.index('start_deg')]=degree
            for network in ['hkshuf','random','dcsbm']:
                t=tokens_from(point,'uniform-v3',network)
                self.assertEqual(t['network'],network)
                self.assertEqual(t['start_deg'],degree)
                if network=='random':self.assertAlmostEqual(t['random_p']*999,degree)
                if network=='dcsbm':self.assertEqual(t['sbm_deg'],degree)
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'manifest.json').write_text(json.dumps({'study':'uniform-v3','primary_network':'hkshuf'}))
            with self.assertRaisesRegex(ValueError,'Cannot mix fitting network'):
                Runner(Path(tmp),1,study='uniform-v3',network='random')

    def test_seed_design_defaults_and_historical_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)
            d=execution_design(output)
            self.assertEqual((d['pilot_seed_count'],d['bo_seed_count'],d['confirm_seed_count']),(5,5,10))
            self.assertEqual(d['search_steps'],d['confirm_steps'])
            with self.assertRaisesRegex(ValueError,'Frozen execution design'):
                execution_design(output,{'pilot_seed_count':2})
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)
            (output/'manifest.json').write_text(json.dumps({'search_steps':20000,'confirm_steps':40000}))
            d=execution_design(output)
            self.assertEqual((d['pilot_seed_count'],d['bo_seed_count'],d['confirm_seed_count']),(2,3,20))
            self.assertEqual(d['search_steps'],20000)

    def test_uniform_activity_target_uses_equal_sides_and_neutral(self):
        rates=np.array([8.,6.,2.,4.,6.,2.,4.])
        expected=np.array([1.5,1.,1.,1.])
        np.testing.assert_allclose(equal_side_ratios(rates),expected)
        np.testing.assert_allclose(equal_side_ratios(rates*100),expected)
        np.testing.assert_allclose(equal_side_ratios(rates[::-1]),expected)
        # Unequal populations cannot change the score at the same per-person rates.
        target={'symmetric_neutral':{'log_ratios':np.log(expected[:3]),'log_ratio_sd_floored':[.15]*3}}
        for pop in [np.ones(7)*100,np.array([160,130,85,207,46,71,63])]:
            counts=rates*pop*10-.5  # account for declared half-event stabilization
            loss,ratios=neutral_activity_loss(counts,pop,10,target)
            self.assertAlmostEqual(loss,0.)
            np.testing.assert_allclose(ratios,expected)
        self.assertEqual(tokens_from([BASE[k] for k in NAMES],'uniform-v3')['init_dist'],'uniform')
        self.assertEqual(tokens_from([BASE[k] for k in NAMES])['init_dist'],'empirical')

    def test_run_cannot_resume_under_a_different_study(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'manifest.json').write_text(json.dumps({'study':'legacy'}))
            with self.assertRaisesRegex(ValueError,'Cannot mix study'):
                Runner(Path(tmp),1,study='uniform-v3')

    def test_log_integer_acquisition_coordinates_do_not_clip_to_upper_endpoint(self):
        from skopt import Optimizer
        from skopt.learning import RandomForestRegressor
        dim=LogInteger(10,400,prior='log-uniform')
        np.testing.assert_allclose(dim.transformed_bounds,dim.transform([10,400]))
        for value in [10,25,100,399,400]:
            clipped=np.clip(dim.transform([value]),*dim.transformed_bounds)
            self.assertEqual(dim.inverse_transform(clipped),[value])
        optimizer=Optimizer([dim],base_estimator=RandomForestRegressor(n_estimators=20,min_samples_leaf=1,random_state=1),
                            n_initial_points=0,acq_func='EI',acq_optimizer='sampling',random_state=1,
                            acq_optimizer_kwargs={'n_points':500})
        x=[[v] for v in [10,15,20,30,50,80,120,180,250,320,400]]
        optimizer.tell(x,[(np.log(p[0])-np.log(30))**2 for p in x])
        self.assertLess(optimizer.ask()[0],100)

    def test_feed_simplex_and_parameter_roundtrip(self):
        from skopt.space import Integer
        for dim in SPACE:
            midpoint=np.sqrt(dim.low*dim.high) if dim.prior=='log-uniform' else (dim.low+dim.high)/2
            if isinstance(dim,Integer):midpoint=round(midpoint)
            values=[dim.low,midpoint,dim.high]
            clipped=np.clip(dim.transform(values),*dim.transformed_bounds)
            np.testing.assert_allclose(dim.inverse_transform(clipped),values,atol=1e-10)
        points = initial_points(128)
        self.assertEqual(len(points), 128)
        for point in points:
            self.assertEqual(len(point), 25)
            for value, dim in zip(point, SPACE): self.assertTrue(dim.low <= value <= dim.high)
            tokens = tokens_from(point)
            self.assertLessEqual(tokens['foryou_share'] + tokens['trend_share'], 1.00000001)
            self.assertAlmostEqual(tokens['w_fit'] + tokens['w_rec'], 10.)
            self.assertEqual(tokens['hk_m'], tokens['start_deg'])
        self.assertEqual({p[0] for p in points[:28]}, {0, 1, 1.5, 2, 2.5, 3, 6})

    def test_relative_activity_invariant_to_clock_units(self):
        x = np.array([8, 5, 2, 4, 1, 2, 7.])
        np.testing.assert_allclose(profile(x), profile(100 * x), atol=1e-12)
        self.assertGreater(np.linalg.norm(profile(x) - profile(np.ones(7))), .5)

    def test_detected_partition_does_not_assume_ideology_sign(self):
        # Two dense connected blocks; ideology signs alternate within each block.
        edges = [(i, j, 20) for base in [0, 5] for i in range(base, base + 5)
                 for j in range(base, base + 5) if i != j] + [(4, 5, 1), (5, 4, 1)]
        m = network_metrics(edges, 10, np.tile([-1., 1.], 5))
        self.assertGreater(m['q'], .45)
        self.assertLess(m['q_sign'], .1)
        self.assertTrue(m['two_communities'])
        self.assertLess(m['cross'], .01)

    def test_isolates_retained_in_component_denominator(self):
        edges = [(i, j, 1) for i in range(5) for j in range(5) if i != j]
        self.assertEqual(network_metrics(edges, 10)['component_fraction'], .5)

    def test_parallel_validation_keeps_conditions_and_seed_groups(self):
        runner=Runner.__new__(Runner);runner.workers=3
        def fake_job(point,seed,phase,steps=40000,overrides=None):
            value=point[0]+seed+(overrides or {}).get('offset',0)
            return {'key':f'{phase}_{point[0]}_{seed}','status':'ok','loss':value,'valid':True,
                    'root':{'q':.45},'all_activity_loss':value,'original_activity_loss':value,
                    'network_loss':0.,'activity_window_drift':0.,'q_window_drift':0.}
        runner.job=fake_job
        rows=runner.experiments([
            {'phase':'first','points':[[1],[2]],'seeds':[10,11]},
            {'phase':'second','points':[[3]],'seeds':[20,21],'overrides':{'offset':100}}])
        self.assertEqual([r['phase'] for r in rows],['first','first','second'])
        self.assertEqual([r['loss'] for r in rows],[11.5,12.5,123.5])
        self.assertTrue(all(r['seed_count']==2 and r['failed']==0 for r in rows))
        initial,pending=runner.initial_with_pending([[1],[2],[3]],[10,11])
        tail,pending=runner.collect_pending(pending,wait=True)
        self.assertEqual(sorted(r['point'][0] for r in initial+tail),[1,2,3])
        self.assertEqual(pending,[])

    def test_async_budget_and_constant_liars_are_not_real_observations(self):
        class OptimizerStub:
            def __init__(self,counter=None):self.counter=counter if counter is not None else [0];self.tells=[]
            def tell(self,x,y):self.tells.append((x,y))
            def copy(self,random_state=None):return OptimizerStub(self.counter)
            def ask(self):self.counter[0]+=1;return [100+self.counter[0]]
        runner=Runner.__new__(Runner);runner.workers=2
        def job(point,seed,phase,steps=20000):
            return {'seed':seed,'key':f'{phase}_{point[0]}_{seed}','status':'ok','loss':float(point[0]),'valid':True,
                    'root':{'q':.45},'all_activity_loss':1.,'original_activity_loss':1.,'network_loss':0.,
                    'activity_window_drift':0.,'q_window_drift':0.}
        runner.job=job
        initial=runner.aggregate([[1]],[[job([1],10,'pilot'),job([1],11,'pilot')]],'pilot')
        optimizer=OptimizerStub()
        with tempfile.TemporaryDirectory() as tmp:
            runner.out=Path(tmp)
            from concurrent.futures import Future
            ready=[]
            for seed in [10,11]:
                f=Future();f.set_result(job([2],seed,'pilot'));ready.append(f)
            rows=refine_async(runner,initial,[{'point':[2],'futures':ready}],14,optimizer)
            self.assertEqual(len(rows),16)
            self.assertEqual(len(optimizer.tells),15)  # initial observations + fourteen true point means
            self.assertEqual(len(optimizer.tells[0][0]),2)  # already-finished pilot futures are collected before scheduling
            self.assertTrue(all(r['seed_count']==3 for r in rows[2:]))
            self.assertEqual(len(json.loads((runner.out/'bo_async_design.json').read_text())),14)
            history=[json.loads(s) for s in (runner.out/'bo_async_history.jsonl').read_text().splitlines()]
            self.assertTrue(all(len(h['pending_bo_indices'])<12 for h in history))
        # New-study configuration actually submits five simulations per BO setting.
        with tempfile.TemporaryDirectory() as tmp:
            runner.out=Path(tmp)
            runner.design={'pilot_seed_count':5,'bo_seed_count':5,'search_steps':40000}
            calls=[]
            from unittest.mock import patch
            import concurrent.futures
            import threading
            pending_lock=threading.Lock()
            pending_future=concurrent.futures.Future()
            original_pool=concurrent.futures.ThreadPoolExecutor
            capacities=[]
            def record_pool(*args,**kwargs):
                capacities.append(kwargs['max_workers'])
                return original_pool(*args,**kwargs)
            def configured_job(point,seed,phase,steps):
                calls.append((seed,steps))
                with pending_lock:
                    if not pending_future.done():pending_future.set_result(job([2],10,'pilot'))
                return job(point,seed,phase,steps)
            runner.job=configured_job
            with patch('bayesian_calibration.concurrent.futures.ThreadPoolExecutor',side_effect=record_pool):
                rows=refine_async(runner,initial,[{'point':[2],'futures':[pending_future]}],1,OptimizerStub())
            self.assertEqual(capacities,[runner.workers])
            self.assertEqual(rows[-1]['seed_count'],5)
            self.assertEqual(sorted(calls),[(s,40000) for s in range(271000,271005)])


if __name__ == '__main__': unittest.main()
