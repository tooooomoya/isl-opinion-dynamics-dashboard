#!/bin/bash
# the standing configuration on the three start networks, one after the other (one compile at a time; resumable)
cd "$(dirname "$0")/.."
for net in hk random sbm; do python3 scripts/standard_run.py $net; done
echo STD_ALL_DONE
