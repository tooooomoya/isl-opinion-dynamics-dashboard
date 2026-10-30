#!/usr/bin/env python3
"""Local beta_h contrast at a vocal-profile candidate; does not narrow the main search."""
import collections
import json
import time
import numpy as np
from bayesian_calibration import Runner, DEFAULT_OUT, write_json, log


def main():
    design=DEFAULT_OUT/'profile_beta_design.json'
    if design.exists():
        spec=json.loads(design.read_text())
    else:
        grouped=collections.defaultdict(list)
        for f in (DEFAULT_OUT/'jobs').glob('*.json'):
            j=json.loads(f.read_text())
            if j['phase']=='pilot' and j['status']=='ok':grouped[tuple(j['point'])].append(j)
        rows=min([v for v in grouped.values() if len(v)==2],key=lambda v:np.mean([j['all_activity_loss'] for j in v]))
        base=rows[0]['point']
        points=[]
        for beta in [1.5,2.,base[0],3.,4.,6.,9.]:
            p=list(base);p[0]=beta;points.append(p)
        spec={'reason':'vocal profile improves but repost Q undershoots; resolve beta interaction without narrowing global box',
              'base_job_keys':[j['key'] for j in rows],'points':points,'seeds':[277000,277001]}
        write_json(design,spec)
    # Avoid exceeding the declared four extra workers while the credit probe is active.
    while not (DEFAULT_OUT/'credit_probe.json').exists():time.sleep(10)
    runner=Runner(DEFAULT_OUT,4)
    rows=runner.batch(spec['points'],spec['seeds'],'profile_beta_probe')
    write_json(DEFAULT_OUT/'profile_beta_probe.json',rows)
    log('PROFILE BETA PROBE COMPLETE')


if __name__=='__main__':main()
