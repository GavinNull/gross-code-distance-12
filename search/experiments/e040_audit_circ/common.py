"""E-040 circuit audit (auditor, 2026-10-30): shared helpers.

Independent of search/experiments/e040 (never imported).  Reuses the audited theory-B auditor code
(search/theory/B_audit: Bulk timing model, bulk/finite column builders, CP-SAT lift, DEM-vs-model check) and the
E-032 auditor's mitmsearch.c (copied here), plus only the evaluator's public entry points.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
for p in (str(ROOT), str(ROOT / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

OUT = ROOT / "results" / "E-040-audit-circ"
OUT.mkdir(parents=True, exist_ok=True)

SPECS = {
    "g10": "search/experiments/e040/g10_d12_spec.json",
    "g8": "search/experiments/e040/g8_d11_spec.json",
    "u11": "search/experiments/e032/u11_spec.json",
    "ibm": "search/experiments/e033/ibm_gross_spec.json",
    "fig12": "results/E-021-gross-new-orders/fig12_spec.json",
}


def spec_path(name):
    return SPECS.get(name, name)


def load(name):
    return json.loads((ROOT / spec_path(name)).read_text())


def gross():
    from search.theory.B_audit.common import get_code
    return get_code("gross")


def jdump(rec, fname=None):
    s = json.dumps(rec)
    print(s, flush=True)
    if fname:
        with open(OUT / fname, "a") as f:
            f.write(s + "\n")
