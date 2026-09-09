#!/usr/bin/env bash
# Progress monitor for a batch started by scripts/run_batch.sh.
# Reads logs/*.log: a run is DONE when its log contains "Elapsed time",
# FAILED if it contains an Exception/Error, otherwise in-progress (latest "step = N" shown).
#
# Usage:
#   scripts/check_progress.sh            # one-shot summary
#   watch -n 10 scripts/check_progress.sh   # live refresh
set -euo pipefail
cd "$(dirname "$0")/.."

total=$(cat logs/batch_total.txt 2>/dev/null || echo "?")
exp=$(cat logs/batch_exp.txt 2>/dev/null || echo "?")

shopt -s nullglob
logs=(logs/*.log)
n=${#logs[@]}

done_n=0; fail_n=0; run_n=0
for f in "${logs[@]}"; do
  if grep -q "Elapsed time" "$f"; then
    done_n=$((done_n+1))
  elif grep -qiE "Exception|Error|TERMINATE" "$f"; then
    fail_n=$((fail_n+1))
  else
    run_n=$((run_n+1))
  fi
done

echo "Experiment $exp  |  total=$total  started=$n"
echo "  DONE=$done_n   running=$run_n   FAILED=$fail_n"

if [[ $fail_n -gt 0 ]]; then
  echo "--- failed runs ---"
  for f in "${logs[@]}"; do
    if ! grep -q "Elapsed time" "$f" && grep -qiE "Exception|Error|TERMINATE" "$f"; then
      echo "  $(basename "$f"): $(grep -iE "Exception|Error|TERMINATE" "$f" | head -1)"
    fi
  done
fi

echo "--- in-progress (latest step) ---"
shown=0
for f in $(ls -t "${logs[@]}" 2>/dev/null); do
  grep -q "Elapsed time" "$f" && continue
  grep -qiE "Exception|Error|TERMINATE" "$f" && continue
  step=$(grep -oE "step = [0-9]+" "$f" | tail -1)
  printf "  %-60s %s / %s\n" "$(basename "$f")" "${step:-step = 0}" "40000"
  shown=$((shown+1))
  [[ $shown -ge 10 ]] && break
done
[[ $shown -eq 0 ]] && echo "  (none)"
