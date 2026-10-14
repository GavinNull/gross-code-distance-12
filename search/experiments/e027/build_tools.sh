#!/bin/sh
# Build the proof tools of the certificate experiment under tools/ (gitignored) and record their commit hashes.
#   sh search/experiments/e027/build_tools.sh
# Sources (official repositories, cloned beforehand or here):
#   https://github.com/arminbiere/cadical     -> tools/cadical/build/cadical
#   https://github.com/marijnheule/drat-trim  -> tools/drat-trim/drat-trim, tools/drat-trim/lrat-check
#   https://github.com/tanyongkiam/cake_lpr   -> tools/cake_lpr/cake_lpr  (pre-compiled CakeML assembly, ARMv8 build)
set -eu
cd "$(dirname "$0")/../../.."
mkdir -p tools; cd tools
for r in arminbiere/cadical marijnheule/drat-trim tanyongkiam/cake_lpr; do
  n=$(basename $r); [ -d "$n" ] || git -c http.version=HTTP/1.1 clone -q --depth 1 "https://github.com/$r.git"
done
( cd cadical && ./configure > /dev/null && make -j3 > /dev/null )
( cd drat-trim && cc -O2 -o drat-trim drat-trim.c && cc -O2 -o lrat-check lrat-check.c )
( cd cake_lpr && { [ "$(uname -m)" = arm64 ] && cc basis_ffi.c cake_lpr_arm8.S -o cake_lpr -std=c99 \
                   || cc -O2 basis_ffi.c cake_lpr.S -o cake_lpr -std=c99; } ) || echo "cake_lpr: build failed"
{ for n in cadical drat-trim cake_lpr; do
    echo "$n $(git -C $n rev-parse HEAD) $(git -C $n log -1 --format=%cI) $(git -C $n remote get-url origin)"
  done
  echo "cadical_version $(cadical/build/cadical --version)"
  echo "cc $(cc --version | head -1)"
  echo "uname $(uname -sm)"
} | tee VERSIONS.txt
