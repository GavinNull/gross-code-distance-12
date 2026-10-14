#!/bin/sh
# Download (official repositories, pinned commits) and build the proof tools into tools/ of the package root:
#   CaDiCaL 3.0.1   https://github.com/arminbiere/cadical     c60730422e758ef1cebe7aeddf2dda31c996bf04
#   drat-trim       https://github.com/marijnheule/drat-trim  2e3b2dc0ecf938addbd779d42877b6ed69d9a985
#   cake_lpr        https://github.com/tanyongkiam/cake_lpr   a36874a8b750b43fe4b385b8ddbf5b033e46a3fa  (optional;
#                   pre-compiled assembly of the CakeML-verified LRAT checker; x86-64 or ARMv8)
# Needs git, make and a C/C++ compiler.  Then:  export CADICAL=$PWD/tools/cadical/build/cadical \
#   DRAT_TRIM=$PWD/tools/drat-trim/drat-trim CAKE_LPR=$PWD/tools/cake_lpr/cake_lpr   (run_full.sh does this itself)
set -eu
cd "$(dirname "$0")/../.."
mkdir -p tools; cd tools
get() { [ -d "$2" ] || { git clone -q "https://github.com/$1.git" "$2"; }; git -C "$2" checkout -q "$3"; }
get arminbiere/cadical cadical c60730422e758ef1cebe7aeddf2dda31c996bf04
get marijnheule/drat-trim drat-trim 2e3b2dc0ecf938addbd779d42877b6ed69d9a985
( cd cadical && ./configure > /dev/null && make -j2 > /dev/null )
( cd drat-trim && cc -O2 -o drat-trim drat-trim.c )
if get tanyongkiam/cake_lpr cake_lpr a36874a8b750b43fe4b385b8ddbf5b033e46a3fa; then
  ( cd cake_lpr && case "$(uname -m)" in arm64|aarch64) cc basis_ffi.c cake_lpr_arm8.S -o cake_lpr -std=c99 ;;
                                           *) cc -O2 basis_ffi.c cake_lpr.S -o cake_lpr -std=c99 ;; esac ) \
    || echo "cake_lpr not built (optional)"
fi
cadical/build/cadical --version
