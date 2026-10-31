"""E-043 audit (auditor, 2026-10-31): shared helpers.

Independent of search/experiments/e043 (never imported).  Reuses the audited theory-B auditor code
(search/theory/B_audit) and the E-032/E-040 auditors' mitmsearch.c (compiled into results/E-043-audit), plus only
the evaluator's public entry points (parse_schedule / validate_schedule / memory_circuit / unroll / add_noise /
check_l0).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
for p in (str(ROOT), str(ROOT / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

OUT = ROOT / "results" / "E-043-audit"
OUT.mkdir(parents=True, exist_ok=True)

# name -> (code, spec path, claimed target t, claimed d_circ)
CIRCS = {
    "ibm90": ("bb90", "search/experiments/e030/ibm90_spec.json", 8),
    "ibmg": ("gross", "search/experiments/e033/ibm_gross_spec.json", 10),
    "g9": ("gross", "search/experiments/e043/g9_d11_spec.json", 11),
    "b9": ("bb90", "search/experiments/e043/b9_d9_spec.json", 9),
    "b10": ("bb90", "search/experiments/e043/b10_d9_spec.json", 9),
    # controls already audited elsewhere
    "c11": ("bb90", "search/experiments/e030/c11_spec.json", 10),
    "g8": ("gross", "search/experiments/e040/g8_d11_spec.json", 11),
}


def info(name):
    return CIRCS[name]


def load(name):
    return json.loads((ROOT / CIRCS[name][1]).read_text())


def code_of(cname):
    from search.theory.B_audit.common import get_code
    return get_code(cname)


def jdump(rec, fname=None):
    s = json.dumps(rec, default=str)
    print(s, flush=True)
    if fname:
        with open(OUT / fname, "a") as f:
            f.write(s + "\n")
