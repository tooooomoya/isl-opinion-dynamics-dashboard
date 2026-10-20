#!/bin/bash
# runs the noisy-post feed comparison at sd 0.5 then 0.7 (sequential: one compile at a time; each stage is resumable)
cd "$(dirname "$0")/.."
for sd in 0.5 0.7; do python3 scripts/feed_compare.py on $sd; done
echo NOISE_LEVELS_DONE
