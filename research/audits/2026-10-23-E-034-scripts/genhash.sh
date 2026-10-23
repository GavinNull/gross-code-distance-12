#!/bin/bash
# Auditor (E-034): regenerate a pbdfs proof stream WITHOUT checking it, only to compare its sha256 / size / node count
# with the record of a checked run (the proof is never stored).   genhash.sh PBDFS INST OUTSTEM [pbdfs args ...]
set -u -o pipefail
PB=$1; INST=$2; OUT=$3; shift 3
t0=$(date +%s)
"$PB" "$INST" -p /dev/fd/3 "$@" 3>&1 1>"$OUT.search.log" 2>&1 | tee >(wc -c | tr -d ' ' > "$OUT.bytes") \
  | openssl dgst -sha256 | awk '{print $NF}' > "$OUT.sha"
st=("${PIPESTATUS[@]}"); sleep 2
echo "{\"name\": \"$(basename $OUT)\", \"args\": \"$*\", \"search_rc\": ${st[0]}, \"wall_s\": $(( $(date +%s) - t0 )), \"proof_sha256\": \"$(cat $OUT.sha)\", \"proof_bytes\": $(cat $OUT.bytes), \"result\": \"$(grep '^RESULT' $OUT.search.log | tail -1)\"}" | tee -a "$(dirname $OUT)/genhash.jsonl"
