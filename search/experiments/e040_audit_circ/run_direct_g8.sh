#!/bin/sh
D="uv run python -m search.experiments.e040_audit_circ.direct"
$D g8 X 1 11
$D g8 X 1 10
$D g8 Z 2 10
$D g8 X 2 10
$D g8 Z 3 10
$D g8 X 3 10
