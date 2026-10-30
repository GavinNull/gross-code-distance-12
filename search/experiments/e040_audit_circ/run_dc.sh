#!/bin/sh
# second exact bulk solver (theory B Bellman-Ford dc.py, not E-040 code) on orbit representatives
O=results/E-040-audit-circ
S=search/experiments/e040/g10_d12_spec.json
for b in Z X; do
  uv run python -m search.experiments.e040_audit_circ.reps g10 $b 10
  uv run python -m search.experiments.e040_audit_circ.reps g10 $b 11
  uv run python -m search.theory.B.dc --code gross --spec $S --basis $b --list $O/reps_g10_${b}_w10.pkl --flips 1
  uv run python -m search.theory.B.dc --code gross --spec $S --basis $b --list $O/reps_g10_${b}_w11.pkl
done
