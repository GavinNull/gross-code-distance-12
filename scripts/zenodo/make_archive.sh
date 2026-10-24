#!/bin/sh
# Finalise release/zenodo/ and pack release/zenodo.tar.gz (the archive itself is not committed).
#   sh scripts/zenodo/make_archive.sh
# 1. removes caches and run directories, 2. scans every text file (also inside .gz) for internal names / paths,
# 3. writes MANIFEST.sha256 (sha256 of every file), 4. packs the tarball with normalised owner and permissions.
set -eu
cd "$(dirname "$0")/../../release"
find zenodo -name __pycache__ -type d -prune -exec /bin/rm -r {} +
find zenodo -name .DS_Store -exec /bin/rm {} +
for d in zenodo/dext_run zenodo/full_run zenodo/proof_run_quick zenodo/dcirc_run zenodo/dcirc_run_quick zenodo/p11_direct_run \
         zenodo/p11_direct_run_quick zenodo/veripb_run zenodo/veripb_run_quick zenodo/ext_lift_run_quick zenodo/tools zenodo/.venv \
         zenodo/uv.lock; do [ -e "$d" ] && /bin/rm -r "$d"; done
PAT='E-0[0-9][0-9]|audit|results/|search/experiments|(^|[^a-z])research/|qec-ai|ephemeral|/Users/|/private/|/tmp/|experimenter|lead agent|claims_map|STATE\.md|decisions\.md|hypotheses\.md|evaluators?\b|2026-10-[0-9]|Desktop|\.claude|worktree|PI approved|rustup'
bad=0
for f in $(find zenodo -type f); do
  case "$f" in
    *.gz) gzip -dc "$f" | grep -q -i -E "$PAT" && { echo "LEAK? $f"; bad=1; } ;;
    *) grep -q -i -E "$PAT" "$f" && { echo "LEAK? $f"; grep -n -i -E "$PAT" "$f" | head -3; bad=1; } ;;
  esac
done
[ "$bad" -eq 0 ] || { echo "internal strings found; not packing"; exit 1; }
( cd zenodo && /bin/rm -f MANIFEST.sha256 && find . -type f ! -name MANIFEST.sha256 | LC_ALL=C sort | xargs shasum -a 256 > MANIFEST.sha256 )
/bin/rm -f zenodo.tar.gz
COPYFILE_DISABLE=1 tar --uid 0 --gid 0 --uname "" --gname "" -czf zenodo.tar.gz zenodo
ls -l zenodo.tar.gz
tar tzf zenodo.tar.gz | wc -l
