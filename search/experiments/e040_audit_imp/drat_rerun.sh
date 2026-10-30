#!/bin/bash
# E-040 impossibility audit: re-solve a regenerated CNF with CaDiCaL 3.0.1 (DRAT proof) and check with drat-trim.
# usage: drat_rerun.sh a.cnf [b.cnf ...]   (proof deleted after check; result lines appended to results/E-040-audit-imp/drat.log)
for f in "$@"; do
  p="${f%.cnf}.drat"
  t0=$(date +%s)
  s=$(tools/cadical/build/cadical -q "$f" "$p" | grep '^s ')
  t1=$(date +%s)
  v=$(tools/drat-trim/drat-trim "$f" "$p" -t 100000 | tr '\r' '\n' | grep -E '^s ' | head -1)
  t2=$(date +%s)
  echo "$(shasum -a 256 "$f" | cut -c1-16) $f solve=[$s] $((t1-t0))s check=[$v] $((t2-t1))s" >> results/E-040-audit-imp/drat.log
  rm -f "$p"
done
