#!/bin/sh
# E-031: VeriPB (official repository, PI-approved download) under tools/ (gitignored); commits appended to tools/VERSIONS.txt.
#   sh search/experiments/e031/build_tools.sh
# VeriPB 3 (branch main) is written in Rust and needs a Rust toolchain plus ~190 crates from crates.io; neither is
# installed here and neither was approved for download, so the checker used is VeriPB 2 (official branch `version2`,
# Python + C++), whose C++ core is compiled directly with clang against GMP/zlib (Homebrew, already present) and the
# header-only pybind11 already on disk.  The Python part runs unmodified (search/experiments/e031/veripb_run.py only
# supplies the missing package-metadata version string for the banner).
# The proof generator search/experiments/e031/pbdfs.c is our own (untrusted; every claim rests on the VeriPB check).
set -eu
cd "$(dirname "$0")/../../.."
mkdir -p tools; cd tools
[ -d veripb ] || git -c http.version=HTTP/1.1 clone -q --depth 1 https://gitlab.com/MIAOresearch/software/VeriPB.git veripb
V2=b0d55dc87b5aaf55b14747be564a8e9060c081f3
if [ ! -d veripb2 ]; then
  git -C veripb fetch -q --depth 1 origin version2
  git -C veripb worktree add -q ../veripb2 "$V2"
fi
PYINC=$(cd .. && uv run python -c "import sysconfig; print(sysconfig.get_paths()['include'])")
SUF=$(cd .. && uv run python -c "import sysconfig; print(sysconfig.get_config_var('EXT_SUFFIX'))")
PB=${PYBIND11_INCLUDE:-$HOME/.claude-science/conda/pkgs/pybind11-3.0.1-pyh7a1b43c_0/site-packages/pybind11/include}
( cd veripb2 && clang++ -std=c++17 -DPY_BINDINGS -O3 -DNDEBUG -shared -fPIC -undefined dynamic_lookup \
    -I"$PYINC" -I"$PB" -I/opt/homebrew/include -L/opt/homebrew/lib \
    veripb/optimized/pybindings.cpp veripb/optimized/constraints.cpp veripb/optimized/parsing.cpp veripb/optimized/gzstream.cpp \
    -lgmp -lgmpxx -lz -o "veripb/optimized/pybindings$SUF" 2>/dev/null )
{ echo "veripb-main $(git -C veripb rev-parse HEAD) $(git -C veripb log -1 --format=%cI) $(git -C veripb remote get-url origin) (cloned 2026-10-21, not built: needs Rust)"
  echo "veripb-version2 $(git -C veripb2 rev-parse HEAD) $(git -C veripb2 log -1 --format=%cI) branch version2 (E-031 checker; C++ core built with $(clang++ --version | head -1); gmp $(ls /opt/homebrew/Cellar/gmp 2>/dev/null | head -1); pybind11 3.0.1 headers)"
} >> VERSIONS.txt
tail -2 VERSIONS.txt
