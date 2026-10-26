#!/bin/bash
# Gaussian-start experiment: random + HK-shuffled networks, plus the uniform-start HK-shuffled control (baseline_hkshuf_*); resumable
cd "$(dirname "$0")/.."
python3 scripts/init_gauss_run.py random
python3 scripts/init_gauss_run.py hkshuf
python3 scripts/standard_run.py hkshuf
echo GAUSS_ALL_DONE
