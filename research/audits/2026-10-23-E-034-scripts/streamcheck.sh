#!/bin/bash
# Auditor (E-034): generate a pbdfs proof and check it with VeriPB 3 as a stream, never stored.
# Independent of e034/certify3.py: plain shell pipe, pbdfs writes the proof on fd 3, `tee` splits the byte stream
# to shasum / wc and to VeriPB reading /dev/stdin.
#   streamcheck.sh PBDFS INST OPB OUTSTEM VERIPB [extra pbdfs args ...]
# Writes OUTSTEM.{search.log,veripb.log,sha,bytes,time.log} and appends one JSON line to OUTSTEM's dir/stream.jsonl.
# Verdict: OK only if VeriPB prints the exact line "s VERIFIED UNSATISFIABLE" AND pbdfs exits 0 with RESULT UNSAT.
set -u
PB=$1; INST=$2; OPB=$3; OUT=$4; VP=$5; shift 5
EXTRA="$*"
t0=$(date +%s)
set -o pipefail
"$PB" "$INST" -p /dev/fd/3 $EXTRA 3>&1 1>"$OUT.search.log" 2>&1 \
  | tee >(shasum -a 256 | cut -d' ' -f1 > "$OUT.sha") >(wc -c | tr -d ' ' > "$OUT.bytes") \
  | /usr/bin/time -l "$VP" --stats "$OPB" /dev/stdin > "$OUT.veripb.log" 2> "$OUT.time.log"
st=("${PIPESTATUS[@]}")
sleep 1
t1=$(date +%s)
res=$(grep '^RESULT' "$OUT.search.log" | tail -1)
ver=$(grep -cx 's VERIFIED UNSATISFIABLE' "$OUT.veripb.log")
rss=$(grep 'maximum resident set size' "$OUT.time.log" | awk '{print $1}')
ok=false
if [ "${st[0]}" = 0 ] && [ "$ver" -ge 1 ] && [[ "$res" == "RESULT UNSAT"* ]]; then ok=true; fi
uv run --project /Users/ephemeral/Desktop/qec-ai-search python - "$OUT" "$EXTRA" "${st[0]}" "${st[2]}" "$ver" "$rss" "$((t1-t0))" "$ok" "$res" "$OPB" "$VP" <<'EOF'
import json, sys, os, hashlib
out, extra, rs, rv, ver, rss, wall, ok, res, opb, vp = sys.argv[1:]
def sha(p):
    h = hashlib.sha256(); f = open(p, 'rb')
    for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()
tail = [l for l in open(out + '.veripb.log').read().splitlines() if l.strip()][-3:]
rec = dict(name=os.path.basename(out), extra=extra, search_rc=int(rs), veripb_rc=int(rv), verified_unsat_lines=int(ver),
           veripb_maxrss_GB=round(int(rss or 0) / 2**30, 2), wall_s=int(wall), ok=ok == 'true', result=res,
           proof_sha256=open(out + '.sha').read().strip(), proof_bytes=int(open(out + '.bytes').read().strip() or 0),
           opb_sha256=sha(opb), veripb_sha256=sha(vp)[:16], veripb_tail=tail)
print(json.dumps(rec))
open(os.path.join(os.path.dirname(out), 'stream.jsonl'), 'a').write(json.dumps(rec) + '\n')
EOF
