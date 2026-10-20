#!/bin/bash
# standing configuration on the random and SBM start networks with a regulated mean degree (HK already has exactly 15 per agent)
cd "$(dirname "$0")/.."
for net in random sbm; do python3 scripts/standard_run.py $net; done
echo STD2_DONE
