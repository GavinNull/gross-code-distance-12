#!/bin/sh
# usage: run_queue.sh QUEUEFILE  (one run_mincc.py argument line per job, sequential = one worker)
cd "$(dirname "$0")"
while read -r line; do
  [ -z "$line" ] && continue
  uv run python run_mincc.py $line >> ../../../results/E-037-audit/queue.log 2>&1
done < "$1"
