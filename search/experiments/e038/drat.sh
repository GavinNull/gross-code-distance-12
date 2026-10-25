#!/bin/sh
# E-038: CaDiCaL 3.0.1 (tools/cadical) proves UNSAT with an ASCII DRAT proof; drat-trim (tools/drat-trim) checks it.
# usage: search/experiments/e038/drat.sh results/E-038-bb18-d4/cegar_bb18_N7_d4.cnf
set -e
cnf="$1"
proof="${cnf%.cnf}.drat"
tools/cadical/build/cadical -q --binary=false "$cnf" "$proof" > "${cnf%.cnf}.cadical.out" || true
grep '^s ' "${cnf%.cnf}.cadical.out"
tools/drat-trim/drat-trim "$cnf" "$proof" -t 50000 > "${cnf%.cnf}.drattrim.out" || true
grep -E '^s |verified|VERIFIED' "${cnf%.cnf}.drattrim.out" | head -3
shasum -a 256 "$cnf" "$proof"
