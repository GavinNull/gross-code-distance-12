"""E-030: E-028's weight-10 injection upper bound (e028/inject10.py logic, unchanged) writing into E-030's results dir.
    PYTHONPATH=.:tests uv run python -m search.experiments.e030.inject10_local SPEC.json"""
import runpy
import shutil
import sys
from pathlib import Path

runpy.run_module("search.experiments.e028.inject10", run_name="__main__")
src = Path("results/E-028-bb90-interleaved") / ("inject10_" + Path(sys.argv[1]).name)
shutil.move(str(src), str(Path("results/E-030-bb90-period-ler") / src.name))
