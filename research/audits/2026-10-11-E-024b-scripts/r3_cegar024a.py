"""Audit E-024b (r3): re-run E-024a's cegar.py unchanged except the output directory (UNSAT reproduction).
    PYTHONPATH=.:tests uv run python research/audits/2026-10-11-E-024b-scripts/r3_cegar024a.py --P 17 --tighten 0 ...
"""
from pathlib import Path
import search.experiments.e024a.cegar as CG
CG.OUT = Path("results/E-024b-audit/cegar024a"); CG.OUT.mkdir(parents=True, exist_ok=True)
CG.main()
