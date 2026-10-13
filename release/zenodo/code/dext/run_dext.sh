#!/bin/sh
# Exhaustive searches of SM S4 on the extended code of Fig. 12 (= that of circuits A, B, C), both memory bases.
#   sh code/dext/run_dext.sh w10    d_ext >= 11: no extended logical of weight <= 10   (about 4 CPU hours)
#   sh code/dext/run_dext.sh w11    the complete list of weight-11 extended logicals  (about 1 CPU hour)
#   sh code/dext/run_dext.sh both
# Environment: P = number of parallel processes (default 4), OUT = work directory (default dext_run), PYTHON.
# Needs a C compiler (cc) supporting unsigned __int128 and __builtin_popcountll (gcc or clang).
set -eu
cd "$(dirname "$0")/../.."
WHAT=${1:-both}; P=${P:-4}; OUT=${OUT:-dext_run}; PYTHON=${PYTHON:-python}
mkdir -p "$OUT"
cc -O3 -o "$OUT/dfs_w10" code/dext/dfs_w10.c
cc -O3 -o "$OUT/enum_w11" code/dext/enum_w11.c
$PYTHON code/dext/make_instances.py "$OUT"
cd "$OUT"
if [ "$WHAT" = w10 ] || [ "$WHAT" = both ]; then
  # job line: basis case [split_mod split_idx]
  xargs -P "$P" -L 1 sh -c './dfs_w10 w10_$0.txt 10 $1 $2 $3 > w10_out_$0_$1_${3:-0}.txt' < w10_jobs.txt
fi
if [ "$WHAT" = w11 ] || [ "$WHAT" = both ]; then
  # job line: basis start_column split_mod split_idx exclusion_file
  xargs -P "$P" -L 1 sh -c 'EXCL=$4 ./enum_w11 w11_$0.txt 11 $1 $2 $3 > w11_out_$0_$1_$3.txt' < w11_jobs.txt
fi
cd - > /dev/null
$PYTHON code/dext/collect.py "$OUT" "$WHAT"
