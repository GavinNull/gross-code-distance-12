"""E-045 Part B upper bound: an R = 1 undetectable logical of the IBM model (found by E-037's witness search on the
E-037 DEM), injected as deterministic Paulis into the NOISELESS stim version of the circuit (ibm_model gate list,
R noisy-slot cycles + T trailing cycles, stim's own frame simulation) at cycle s, for many R.  Pass: every detector 0
and the same observables flip as at R = 1, s = 0; controls: no injection silent; dropping any one fault fires a
detector.  experimenter.

    uv run python -m search.experiments.e045.persist_ibm
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import stim

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "search/experiments/e037"))
import ibm_model as im  # noqa: E402
import witness as w37  # noqa: E402

OUT = ROOT / "results" / "E-045-crocker" / "partB"


def stim_inject(code, typ, R, T, faults):
    """noiseless stim circuit of R + T cycles with faults (cycle, round, gate, qubits) injected (E-037 witness.py
    stim_inject with the number of trailing cycles as a parameter)"""
    want = {}
    for (cc, r, gt, qs) in faults:
        want.setdefault((cc, r, tuple(gt)), []).append(tuple(qs))
    cyc = im.cycle(code)
    c = stim.Circuit()
    data = code.Lq + code.Rq
    c.append("R" if typ == "X" else "RX", data)
    c.append("R", code.Zq)
    c.append("RX", code.Xq)
    tgt = (lambda q: stim.target_x(q)) if typ == "X" else (lambda q: stim.target_z(q))
    nm, rec = 0, {}
    for cc in range(R + T):
        for r, g in enumerate(cyc):
            for gt in g:
                k = gt[0]
                inj = want.get((cc, r, tuple(gt)), [])
                before, _ = im.faults_for(gt, typ)
                if before:
                    for qs in inj:
                        c.append("CORRELATED_ERROR", [tgt(q) for q in qs], 1.0)
                if k == "CNOT":
                    c.append("CX", [gt[1], gt[2]])
                elif k == "PrepX":
                    c.append("RX", [gt[1]])
                elif k == "PrepZ":
                    c.append("R", [gt[1]])
                elif k == "MeasZ":
                    c.append("M", [gt[1]]); rec[(gt[1], cc)] = nm; nm += 1
                elif k == "MeasX":
                    c.append("MX", [gt[1]]); rec[(gt[1], cc)] = nm; nm += 1
                if not before:
                    for qs in inj:
                        c.append("CORRELATED_ERROR", [tgt(q) for q in qs], 1.0)
    checks = code.Zq if typ == "X" else code.Xq
    c.append("M" if typ == "X" else "MX", data)
    drec = {q: nm + j for j, q in enumerate(data)}
    nm += len(data)
    for cc in range(R + T):
        for i, q in enumerate(checks):
            t = [stim.target_rec(rec[(q, cc)] - nm)]
            if cc:
                t.append(stim.target_rec(rec[(q, cc - 1)] - nm))
            c.append("DETECTOR", t, [i, cc])
    Lop = code.lz if typ == "X" else code.lx
    for kk, row in enumerate(Lop):
        c.append("OBSERVABLE_INCLUDE", [stim.target_rec(drec[data[j]] - nm) for j in np.nonzero(row)[0]], kk)
    return c


def run(c):
    det, obs = c.compile_detector_sampler().sample(2, separate_observables=True)
    assert (det == det[0]).all() and (obs == obs[0]).all()
    return int(det[0].sum()), np.nonzero(obs[0])[0].tolist()


def witness_faults(name, typ, W):
    src = f"ibm:{name}:{typ}:1"
    OUT.mkdir(parents=True, exist_ok=True)
    cols = w37.find(src, W, str(OUT))
    assert cols is not None
    code = im.Code(name)
    raw = im.build_dem(code, typ, 1, ibm_faithful=True, return_raw=True)
    m = im.merge(raw["det"], raw["logi"], raw["final"], raw["fdesc"], code, 1, typ)
    return cols, [raw["fdesc"][m["members"][j][0]] for j in cols]


def main():
    res = []
    for name, W in (("gross", 10), ("bb108", 8)):
        code = im.Code(name)
        for typ in ("X", "Z"):
            cols, faults = witness_faults(name, typ, W)
            assert all(f[0] == 0 for f in faults)
            base = run(stim_inject(code, typ, 1, 2, faults))
            rows = []
            for T in (2, 1, 0):
                for R in ((1, 2, 3, 5, 8, 12, 13, 20, 30) if T == 2 else (1, 2, 5, 13)):
                    for s in sorted({0, R - 1, R // 2}):
                        fs = [(s, f[1], f[2], f[3]) for f in faults]
                        nd, ob = run(stim_inject(code, typ, R, T, fs))
                        drop = (min(run(stim_inject(code, typ, R, T, fs[:i] + fs[i + 1:]))[0] for i in range(len(fs)))
                                if (T == 2 and R in (1, 30)) else None)
                        rows.append(dict(T=T, R=R, shift=s, detectors=nd, obs=ob, same_obs=ob == base[1],
                                         ok=(nd == 0 and ob == base[1]), min_drop_one=drop))
            empty = run(stim_inject(code, typ, 5, 2, []))
            rec = dict(code=name, typ=typ, basis="Z" if typ == "X" else "X", W=W, columns_R1=cols,
                       faults=[[f[0], f[1], list(f[2]), list(f[3])] for f in faults], base=base, control_empty=empty,
                       all_ok_T2=all(r["ok"] and (r["min_drop_one"] is None or r["min_drop_one"] > 0) for r in rows if r["T"] == 2),
                       fails_T1=[(r["R"], r["shift"]) for r in rows if r["T"] == 1 and not r["ok"]],
                       fails_T0=[(r["R"], r["shift"]) for r in rows if r["T"] == 0 and not r["ok"]], rows=rows)
            print(json.dumps({k: v for k, v in rec.items() if k not in ("rows", "faults")}), flush=True)
            res.append(rec)
    with open(OUT / "persist.jsonl", "w") as f:
        for r in res:
            f.write(json.dumps(r) + "\n")


if __name__ == "__main__":
    main()
