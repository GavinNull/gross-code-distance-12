#!/bin/sh
# Stops (by PID) my own e024a CEGAR python processes whose single SAT call overran: elapsed > max_sec + 120 s.
# (The in-process watchdog cannot fire while pysat holds the GIL.)  Appends an UNKNOWN STATUS line to the run's log.
tosec() { echo "$1" | awk -F'[-:]' '{ if (NF==4) print $1*86400+$2*3600+$3*60+$4; else if (NF==3) print $1*3600+$2*60+$3; else print $1*60+$2 }'; }
while true; do
  ps -eo pid=,etime=,command= | grep "Python -m search.experiments.e024a.cegar" | grep -v grep | while read pid etm rest; do
    et=$(tosec "$etm")
    ms=$(echo "$rest" | sed -n 's/.*--max_sec \([0-9.]*\).*/\1/p' | cut -d. -f1)
    tag=$(echo "$rest" | sed -n 's/.*--tag \([^ ]*\).*/\1/p')
    P=$(echo "$rest" | sed -n 's/.*--P \([0-9]*\).*/\1/p')
    [ -z "$ms" ] && continue
    if [ "$et" -gt $((ms + 120)) ]; then
      kill "$pid"
      echo "STATUS P=$P |H|=? UNKNOWN it=? (stopped by reaper by PID: SAT call overran max_sec=$ms; elapsed ${et}s) ${et}s" >> results/E-024a-gross12-period/$tag.log
    fi
  done
  sleep 60
done
