#!/bin/sh
# usage: run_lift_g10.sh BASIS   (one serial worker)
b=$1
L="uv run python -m search.experiments.e040_audit_circ.lift_run"
C=results/E-040-audit-circ/segctl_g10.json
$L g10 $b 10 --flips 1
$L g10 $b 11
$L g10 $b 10 --flips 1 --spec $C
$L g10 $b 11 --spec $C
$L g10 $b 10 --flips 1 --all
$L g10 $b 11 --all
