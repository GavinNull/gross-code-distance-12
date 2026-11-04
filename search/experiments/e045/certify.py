"""E-045: E-037's certify.py driver (unchanged, imported) with the instance builder replaced by e045/tess_inst.py, so
that SOURCE may be tess:gross:BASIS.  Same arguments and the same acceptance rule (VeriPB 3 prints
"s VERIFIED UNSATISFIABLE" and the search ends "RESULT UNSAT").  experimenter.

    uv run python search/experiments/e045/certify.py tess:gross:Z 9 --out results/E-045-crocker/cert
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "search/experiments/e037"))
import certify as c37  # noqa: E402


def run_build(args, log):
    p = subprocess.run([sys.executable, str(HERE / "tess_inst.py")] + args, capture_output=True, text=True)
    log.write(p.stdout + p.stderr)
    if p.returncode:
        raise SystemExit("build failed:\n" + p.stdout + p.stderr)


c37.run_build = run_build

if __name__ == "__main__":
    c37.main()
