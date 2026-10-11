"""Audit E-024b (r1): re-run the experimenter's gsat.py unchanged except the output directory.
    PYTHONPATH=.:tests uv run python research/audits/2026-10-11-E-024b-scripts/r1_gsat.py --col 3,1,1 --x ... --z ... --P 17 ...
"""
import sys
from pathlib import Path
import search.experiments.e024b.gsat as G
G.OUT = Path("results/E-024b-audit/gsat"); G.OUT.mkdir(parents=True, exist_ok=True)
G.main()
