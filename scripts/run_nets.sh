#!/bin/bash
# standing config on a random and an SBM start network (sequential: one compile at a time; resumable)
cd "$(dirname "$0")/.."
python3 scripts/feed_compare.py on nogate random
python3 scripts/feed_compare.py on nogate sbm
echo NETS_DONE
