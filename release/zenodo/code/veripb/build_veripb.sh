#!/bin/sh
# Download (official repository, pinned commit) and build VeriPB 3 (3.0.2) into tools/veripb of the package root:
#   VeriPB  https://gitlab.com/MIAOresearch/software/VeriPB   main branch, commit f41ce91a6bba0223b925f8277d79a531a50d925c
# Needs git and a Rust toolchain (cargo); the crates.io dependencies are pinned by the repository's Cargo.lock
# (cargo build --locked).  Reference build: rustc 1.99.1, Cargo.lock sha256 9d41d186bd540c1a6c7c9f5b59cc4542cab2a3003a4ee74b8ffec638f149dfeb,
# binary sha256 fe7c89957d5a2abe15bbc00fa82617680029c1d0da5b0aefbc0c3811119d1be9 (macOS, arm64).
# Then:  export VERIPB=$PWD/tools/veripb/target/release/veripb
set -eu
cd "$(dirname "$0")/../.."
mkdir -p tools; cd tools
[ -d veripb ] || git clone -q https://gitlab.com/MIAOresearch/software/VeriPB.git veripb
git -C veripb checkout -q f41ce91a6bba0223b925f8277d79a531a50d925c
( cd veripb && cargo build --release --locked )
veripb/target/release/veripb --version
