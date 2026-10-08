"""Audit E-020 c2: re-run the experimenter's cegar.main unchanged, only redirecting output to results/E-020-audit.
    PYTHONPATH=.:tests uv run python research/audits/2026-10-09-E-020-scripts/c2_cegar_rerun.py --P 11 --sub "1,2;0,3" --tag sym_P11
"""
import sys
import search.experiments.e020.cegar as cg
cg.OUT = "results/E-020-audit"
sys.argv = ["cegar"] + sys.argv[1:]
cg.main()
