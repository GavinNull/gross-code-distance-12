#!/bin/zsh
# E-038 audit: drat-trim on E-038's existing V9 delta=1 and delta=8 proofs (CNF sha256 checked first).
cd "$(dirname $0)/../../.."
d=$1
out=results/E-038-audit/b9_redrat_V9_delta$d.txt
shasum -a 256 results/E-038-bb18-d4/cegar_bb18_V9_d4_delta$d.cnf results/E-038-bb18-d4/cegar_bb18_V9_d4_delta$d.drat > $out
tools/drat-trim/drat-trim results/E-038-bb18-d4/cegar_bb18_V9_d4_delta$d.cnf results/E-038-bb18-d4/cegar_bb18_V9_d4_delta$d.drat -t 40000 | tr '\r' '\n' | grep -E '^s ' >> $out
echo done >> $out
