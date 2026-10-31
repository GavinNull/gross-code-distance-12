"""E-043 step 3: Theorem-5 screening/certification of candidate signatures (rows of rescore_<code>_P<P>.json).

Per candidate: build the evaluator spec from its time vector (E-040 bulk.spec_of: prep just before the first CNOT,
measurement just after the last), then with the e043.cert tools (theory-B auditor code only):
  - evaluator validate_schedule, window conditions (Wb)(Wt) R = 1..3, zero-image hooks, strict translation invariance
  - d_ext and complete extended lists up to weight t - 1 for both bases (mitmsearch enum)
  - Theorem 5 at target t (requires t <= d_ext + 2): every weight-w list (w = d_ext .. t-1) with <= t-1-w flips must be
    bulk non-liftable (CP-SAT, orbit reps).  The first lifted set stops the candidate ('lifted').
A candidate that passes everything has d_circ >= t for every R and both bases (Theorem 5); the upper bound and the
direct DEM cross-check are separate steps.

  PYTHONPATH=.:tests uv run python -m search.experiments.e043.batch --code gross --P 9 --t 11 --dext 9 [--part 0/2]
"""
from __future__ import annotations

import argparse
import json
import pickle
import time
from contextlib import redirect_stdout
from io import StringIO

from search.experiments.e043 import cert
from search.experiments.e043.cert import OUT, build, jdump

SPECD = OUT / "specs"
SPECD.mkdir(exist_ok=True)


def dext_of(code, kind, order, table):
    from search.experiments.e040.codes import MOD
    from search.experiments.e040.lists import type_rep
    return table[(code, kind, MOD[code].name(type_rep(code, tuple(order))))]


def screen(code, spec, t):
    from search.theory.B_audit.common import Bulk
    from search.theory.B_audit.window_test import conds
    from search.theory.B_audit.lift import check_bulk_solution, solve_bulk
    from evaluators import candidate as cand
    sd = cert.load(spec)
    rec = {"spec": spec}
    codeobj = cert.code_of(code)
    rec["validate"] = [str(x) for x in (cand.validate_schedule(cand.parse_schedule(sd), codeobj) or [])]
    w = conds(codeobj, sd, Rmax=3)
    rec["window_ok"] = all(v["Wb"] and v["Wt"] and v["index_mismatches"] == 0 for v in w.values())
    for basis in ("Z", "X"):
        B, cols, zero, keys, colperm = build(code, spec, basis)
        rec[f"zero_{basis}"] = len(zero)
        buf = StringIO()
        with redirect_stdout(buf):
            cert.cmd_lists(code, spec, basis, t - 1)
        lr = json.loads(buf.getvalue().strip().splitlines()[-1])
        dext = lr["d_ext"]
        rec[f"dext_{basis}"] = dext
        rec[f"lists_{basis}"] = lr["by_weight"]
        if not isinstance(dext, int):
            continue          # no extended logical of weight <= t - 1: d_circ >= t by Lemma 1
        if t > dext + 2:
            rec["status"] = "theorem5_not_applicable"
            return rec
        kidx = {k: i for i, k in enumerate(keys)}
        for wgt in range(dext, t):
            pth = OUT / f"list_{cert.tag_of(spec)}_{basis}_w{wgt}.pkl"
            if not pth.exists():
                continue
            d = pickle.load(open(pth, "rb"))
            L = [tuple(sorted(kidx[k] for k in S)) for S in d["keys"]]
            seen = set()
            nrep = 0
            for i, S in enumerate(L):
                if S in seen:
                    continue
                nrep += 1
                for pm in colperm:
                    seen.add(tuple(sorted(pm[j] for j in S)))
                r = solve_bulk(d["keys"][i], cols, t - 1 - wgt)
                if r is not None:
                    sol, nfl = r
                    assert check_bulk_solution(sol, nfl, t - 1 - wgt)
                    rec["status"] = "lifted"
                    rec["lifted"] = {"basis": basis, "w": wgt, "flips": nfl, "index": i,
                                     "max_shift": max(abs(x) for _, x in sol)}
                    return rec
            rec[f"reps_{basis}_w{wgt}"] = nrep
    ok = rec["window_ok"] and rec["zero_Z"] == 0 and rec["zero_X"] == 0 and not rec["validate"]
    rec["status"] = "certified_ge_t" if ok else "premise_fail"
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", required=True)
    ap.add_argument("--P", type=int, required=True)
    ap.add_argument("--t", type=int, required=True)
    ap.add_argument("--dext", type=int, required=True, help="only candidates with d_ext >= this on both sides")
    ap.add_argument("--part", default="0/1")
    ap.add_argument("--rows", default="", help="explicit candidate file (list of rows) instead of rescore output")
    ap.add_argument("--stop_on_cert", type=int, default=0)
    a = ap.parse_args()
    from search.experiments.e040.bulk import spec_of
    table = {}
    for k in "XZ":
        for l in open(f"results/E-040-min-period/types_{a.code}_{k}.jsonl"):
            r = json.loads(l)
            table[(a.code, k, r["type"])] = r["dext"]
    rows = json.load(open(a.rows)) if a.rows else \
        json.load(open(OUT / f"rescore_{a.code}_P{a.P}.json"))["candidates"]
    sel = [(i, r) for i, r in enumerate(rows)
           if dext_of(a.code, "X", r["ox"], table) >= a.dext and dext_of(a.code, "Z", r["oz"], table) >= a.dext]
    pi, pn = map(int, a.part.split("/"))
    sel = sel[pi::pn]
    print(json.dumps({"selected": len(sel)}), flush=True)
    for i, r in sel:
        t0 = time.time()
        name = f"{a.code}_P{a.P}_c{i}"
        spec = f"results/E-043-table/specs/{name}.json"
        (cert.ROOT / spec).write_text(json.dumps(spec_of(a.code, r["tx"], r["tz"], a.P)))
        rec = {"code": a.code, "P": a.P, "t": a.t, "cand": i, "tx": r["tx"], "tz": r["tz"], "ox": r["ox"],
               "oz": r["oz"], "G": r["G"], "wX": r.get("wX"), "wZ": r.get("wZ")}
        rec.update(screen(a.code, spec, a.t))
        rec["sec"] = round(time.time() - t0, 1)
        jdump(rec, f"batch_{a.code}_P{a.P}_t{a.t}.jsonl")
        if a.stop_on_cert and rec["status"] == "certified_ge_t":
            break


if __name__ == "__main__":
    main()
