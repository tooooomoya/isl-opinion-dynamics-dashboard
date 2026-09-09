#!/usr/bin/env bash
# Batch runner for the moderate-influencer / repost-hub experiments.
#
# Usage:
#   scripts/run_batch.sh A 4            # Exp A (channel isolation), 4 parallel jobs
#   scripts/run_batch.sh B 6            # Exp B (number x size), 6 parallel jobs
#   SEEDS_N=9 scripts/run_batch.sh A 4  # use seeds 0..9 instead of 0..29
#   SKIP_COMPILE=1 scripts/run_batch.sh A 4
#
# Logs: logs/<config>.log (one per run; check with scripts/check_progress.sh).
set -euo pipefail
cd "$(dirname "$0")/.."

EXP="${1:-A}"
JOBS="${2:-4}"
SEEDS=$(seq 0 "${SEEDS_N:-29}")

BUILD=/tmp/pvm_build
LIBS="lib/ApacheCommonsMath/commons-math3-3.6.1.jar:lib/gephi/gephi-toolkit-0.10.0-all.jar:lib/gurobi/gurobi.jar"
CP_RUN="$BUILD:$LIBS"
export CP_RUN

mkdir -p "$BUILD" logs

if [[ "${SKIP_COMPILE:-0}" != "1" ]]; then
  echo "[run_batch] compiling..."
  find src -name '*.java' > /tmp/pvm_srcs.txt
  javac -d "$BUILD" -cp "src:$LIBS" @/tmp/pvm_srcs.txt
fi

# Build the job list (one config line per run).
JOBFILE=$(mktemp)
case "$EXP" in
  A)  # channel isolation: fixed small moderate set, vary channel x extreme background
    for ext in none sym asym; do
      for ch in both post_only repost_only none; do
        for s in $SEEDS; do
          echo "seed=$s extreme=$ext n_neutral=1 size=largest channel=$ch"
        done
      done
    done > "$JOBFILE" ;;
  B)  # number x size: vary n_neutral x size x extreme background, channel fixed
    for ext in none sym asym; do
      for nm in 1 2 3 5; do
        for sz in largest smallest; do
          for s in $SEEDS; do
            echo "seed=$s extreme=$ext n_neutral=$nm size=$sz channel=both"
          done
        done
      done
    done > "$JOBFILE" ;;
  *) echo "Unknown experiment '$EXP' (use A or B)"; exit 1 ;;
esac

TOTAL=$(wc -l < "$JOBFILE" | tr -d ' ')
echo "$TOTAL" > logs/batch_total.txt
echo "$EXP" > logs/batch_exp.txt
echo "[run_batch] Experiment $EXP: $TOTAL runs, $JOBS parallel. Started $(date '+%F %T')."

# Run. Each line of JOBFILE is the full arg string for one run.
xargs -P "$JOBS" -I {} bash -c '
  args="{}"
  tag=$(echo "$args" | sed "s/[ =]/_/g")
  java -cp "$CP_RUN" dynamics.OpinionDynamics $args > "logs/${tag}.log" 2>&1
' < "$JOBFILE"

rm -f "$JOBFILE"
echo "[run_batch] All $TOTAL runs finished $(date '+%F %T')."
