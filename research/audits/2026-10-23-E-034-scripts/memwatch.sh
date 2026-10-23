#!/bin/bash
# Auditor: log RSS of every process whose command line contains PATTERN every 60 s; kill (by explicit PID) any of them
# whose RSS exceeds LIMIT_GB.  memwatch.sh PATTERN LIMIT_GB LOG ; stops when no such process is left for 10 min.
PAT=$1; LIM=$2; LOG=$3; idle=0
while true; do
  found=0
  while read -r pid rss cmd; do
    [ -z "$pid" ] && continue; found=1
    gb=$(echo "$rss" | awk '{printf "%.2f", $1/1048576}')
    echo "$(date +%H:%M:%S) pid=$pid rss_GB=$gb $cmd" >> "$LOG"
    if awk -v g="$gb" -v l="$LIM" 'BEGIN{exit !(g>l)}'; then echo "$(date +%H:%M:%S) KILL pid=$pid rss_GB=$gb" >> "$LOG"; kill "$pid"; fi
  done < <(ps -axo pid=,rss=,command= | grep -F -- "$PAT" | grep -v grep | grep -v memwatch | awk '{print $1, $2, $3}')
  if [ $found = 0 ]; then idle=$((idle+1)); else idle=0; fi
  [ $idle -ge 10 ] && break
  sleep 60
done
