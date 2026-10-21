"""Run the VeriPB 2 checker (official repo, branch version2, commit b0d55dc, built in tools/veripb2 without pip).
The only change w.r.t. `veripb` installed by pip: package metadata is absent, so importlib.metadata.version('veripb')
is answered here (it is used only to print the banner).  Checker code is untouched.
    uv run python search/experiments/e031/veripb_run.py INSTANCE.opb PROOF.pbp [veripb options]
"""
import importlib.metadata as md
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools", "veripb2"))
_orig = md.version
md.version = lambda name: "2-b0d55dc(version2 branch)" if name == "veripb" else _orig(name)
import veripb  # noqa: E402
from veripb.utils import run_cmd_main  # noqa: E402

if __name__ == "__main__":
    sys.exit(run_cmd_main())
