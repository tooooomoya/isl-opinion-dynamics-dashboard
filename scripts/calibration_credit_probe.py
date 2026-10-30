#!/usr/bin/env python3
"""Small declared mechanism probe alongside the unchanged primary calibration."""
from bayesian_calibration import Runner, DEFAULT_OUT, BASE, NAMES, write_json


def main():
    runner=Runner(DEFAULT_OUT,4)
    rows=[]
    for credit in ['stock','post']:
        points=[]
        for beta in [1.,2.,3.,6.]:
            p=dict(BASE,beta_h=beta)
            points.append([p[k] for k in NAMES])
        rows.extend(runner.batch(points,[276000,276001],'credit_probe_'+credit,
                                  overrides={'credit':credit,'credit_horizon':50}))
    write_json(DEFAULT_OUT/'credit_probe.json',rows)


if __name__=='__main__':main()
