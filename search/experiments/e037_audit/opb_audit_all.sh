#!/bin/sh
# E-037 audit: opb_audit.py on every certified instance (88), sequential (one worker).
cd "$(dirname "$0")"
R=../../../results/E-037-ibm-cert
OUT=../../../results/E-037-audit/opb_audit.jsonl
for dir in cert sweep; do
  uv run python -c "
import json
for l in open('$R/$dir/runs.jsonl'):
    r=json.loads(l)
    if r.get('ok'): print(r['name'], r['source'], r['W'])
" | while read name src W; do
    uv run python opb_audit.py $R/$dir/$name.opb $src $W --runs $R/$dir/runs.jsonl >> $OUT 2>> $OUT.err || echo "{\"opb\": \"$name\", \"verdict\": \"FAIL\"}" >> $OUT
  done
done
