#!/bin/sh
# E-034: build VeriPB 3 (official repo, main branch) with the user-local rustup toolchain (installed with
# --no-modify-path; cargo is called by full path).  Dependencies: crates.io, pinned by the repo's Cargo.lock (--locked).
set -eu
cd "$(dirname "$0")/../../.."
CARGO=$HOME/.cargo/bin/cargo
cd tools/veripb
git rev-parse HEAD
$CARGO build --release --locked -j 4
./target/release/veripb --version
