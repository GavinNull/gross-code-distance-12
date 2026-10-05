"""Driver for dfs128 (complete search for a logical of weight <= W in the extended code, with orbit cases)."""
from __future__ import annotations

import re
import subprocess
import tempfile
import time
from pathlib import Path

from common import OUT, dump_instance

BIN = str(OUT / "dfs128")


def run_case(inst, W, case, split=None):
    cmd = [BIN, str(inst), str(W), str(case)] + ([str(split[0]), str(split[1])] if split else [])
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    m = re.search(r"nodes=(\d+) found=(\d+).*sec=([\d.]+)", out)
    found_lines = [l for l in out.splitlines() if l.startswith("FOUND")]
    return {"case": case, "nodes": int(m.group(1)), "found": int(m.group(2)), "sec": float(m.group(3)),
            "first": found_lines[:3]}


def decide(code, kind, orders, sym, W, stop_on_found=True, inst_path=None):
    """Is there a logical of weight <= W?  Runs all orbit cases (stops at the first case with a solution if
    stop_on_found).  Returns dict(found_any, cases=[...], info)."""
    tmp = None
    if inst_path is None:
        tmp = tempfile.NamedTemporaryFile(dir=OUT, suffix=".inst", delete=False)
        inst_path = Path(tmp.name)
        tmp.close()
    info = dump_instance(code, kind, orders, sym, inst_path)
    t0 = time.time()
    cases = []
    for c in range(info["orbits"]):
        r = run_case(inst_path, W, c)
        cases.append(r)
        if r["found"] and stop_on_found:
            break
    if tmp is not None:
        Path(inst_path).unlink()
    return {"W": W, "found_any": any(r["found"] for r in cases), "nodes": sum(r["nodes"] for r in cases),
            "sec": round(time.time() - t0, 2), "cases_run": len(cases), "info": info,
            "found_cases": [r for r in cases if r["found"]][:2]}
