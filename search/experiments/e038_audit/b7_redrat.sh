#!/bin/zsh
# E-038 audit: re-run CaDiCaL 3.0.1 + drat-trim on E-038's own certificates (N7 cubes [1,506] and [505,7] from
# final_N7.cnf; existing V8 delta=1 proof), proofs written to the scratch dir given as $1 and deleted afterwards.
cd "$(dirname $0)/../../.."
S=$1
out=results/E-038-audit/b7_redrat.txt
shasum -a 256 results/E-038-bb18-d4/final_N7.cnf >> $out
for cube in "1 506" "505 7" "507 514"; do
  set -- ${=cube}
  hdr=$(head -1 results/E-038-bb18-d4/final_N7.cnf); nv=$(echo $hdr | awk '{print $3}'); nc=$(echo $hdr | awk '{print $4}')
  { echo "p cnf $nv $((nc+2))"; tail -n +2 results/E-038-bb18-d4/final_N7.cnf; echo "$1 0"; echo "$2 0"; } > $S/cube.cnf
  echo "cube $1 $2" >> $out
  tools/cadical/build/cadical -q $S/cube.cnf $S/cube.drat | grep '^s ' >> $out
  tools/drat-trim/drat-trim $S/cube.cnf $S/cube.drat -t 40000 | tr '\r' '\n' | grep -E '^s ' >> $out
  shasum -a 256 $S/cube.drat >> $out
  rm -f $S/cube.drat
done
echo "V8 delta1 existing proof" >> $out
tools/drat-trim/drat-trim results/E-038-bb18-d4/cegar_bb18_V8_d4_delta1.cnf results/E-038-bb18-d4/cegar_bb18_V8_d4_delta1.drat -t 40000 | tr '\r' '\n' | grep -E '^s ' >> $out
rm -f $S/cube.cnf
echo done >> $out
