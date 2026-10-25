"""E-037 audit: re-check E-037's weight-10 / weight-8 witnesses against my own DEMs, and replay the IBM-model ones as
deterministic Pauli injections in my own noiseless stim circuit (mydem gate list).

  uv run python search/experiments/e037_audit/witness_replay.py
"""
import json
from pathlib import Path

import numpy as np
import stim

import mydem

ROOT = Path(__file__).resolve().parents[3]
WIT = ROOT / "results" / "E-037-ibm-cert" / "witness" / "witness.jsonl"


def replay_ibm(name, typ, R, faults, drop=None):
    code = mydem.BB(name)
    cyc = code.cycle(with_round=True)
    inj = {}
    for k, (c, r, gate, qs) in enumerate(faults):
        if k == drop:
            continue
        inj.setdefault((c, r, tuple(gate)), []).append(tuple(qs))
    c = stim.Circuit()
    data = code.dl + code.dr
    c.append("R" if typ == "X" else "RX", data)
    c.append("R", code.zc); c.append("RX", code.xc)
    P = typ
    tg = stim.target_x if typ == "X" else stim.target_z

    def pauli(circ, qs):
        # deterministic fault as a probability-1 error channel (a plain Pauli gate would enter the reference sample)
        circ.append("CORRELATED_ERROR", [tg(q) for q in qs], 1.0)
    nm, rec, used = 0, {}, 0
    for cc in range(R + 2):
        for rr, g in cyc:
            k = g[0]
            key = (cc, rr, tuple(g))
            meas = ("MeasZ" if typ == "X" else "MeasX")
            if k == meas and key in inj:            # measurement faults go before
                for qs in inj[key]:
                    pauli(c, qs); used += 1
            if k == "CNOT":
                c.append("CX", [g[1], g[2]])
            elif k == "PrepX":
                c.append("RX", [g[1]])
            elif k == "PrepZ":
                c.append("R", [g[1]])
            elif k in ("MeasZ", "MeasX"):
                c.append("M" if k == "MeasZ" else "MX", [g[1]]); rec[(g[1], cc)] = nm; nm += 1
            if k != meas and key in inj:
                for qs in inj[key]:
                    pauli(c, qs); used += 1
    chk = code.zc if typ == "X" else code.xc
    c.append("M" if typ == "X" else "MX", data)
    drec = {q: nm + j for j, q in enumerate(data)}
    nm += len(data)
    for cc in range(R + 2):
        for i, q in enumerate(chk):
            t = [stim.target_rec(rec[(q, cc)] - nm)]
            if cc:
                t.append(stim.target_rec(rec[(q, cc - 1)] - nm))
            c.append("DETECTOR", t)
    Lop = code.lz if typ == "X" else code.lx
    for kk, row in enumerate(Lop):
        c.append("OBSERVABLE_INCLUDE", [stim.target_rec(drec[data[j]] - nm) for j in np.flatnonzero(row)], kk)
    det, obs = c.compile_detector_sampler().sample(1, separate_observables=True)
    # the reference sample of a noiseless circuit is all-zero for detectors; deterministic Paulis are frame flips
    return int(det[0].sum()), [int(i) for i in np.flatnonzero(obs[0])], used


def main():
    for ln in open(WIT):
        w = json.loads(ln)
        kind, name, typ, R = w["source"].split(":")
        R = int(R)
        # DEM-level check against my DEM: E-037 column ids index their cols.json; translate via detector sets
        theirs = json.loads(next((ROOT / "results" / "E-037-ibm-cert").glob(f"*/{w['source'].replace(':', '_')}_W*.cols.json")).read_text())
        mine = mydem.load(w["source"])
        idx = {tuple(d): j for j, d in enumerate(mine["D"])}
        cols = [idx[tuple(theirs["D"][j])] for j in w["columns"]]
        dd, oo = set(), set()
        for j in cols:
            dd ^= set(mine["D"][j]); oo ^= set(mine["L"][j])
        out = dict(source=w["source"], weight=len(set(cols)), dem_silent=not dd, dem_obs_flipped=sorted(oo))
        if kind == "ibm":
            nd, ob, used = replay_ibm(name, typ, R, w["faults"])
            nd1, _, _ = replay_ibm(name, typ, R, w["faults"], drop=0)
            out.update(stim_detectors_fired=nd, stim_obs_flipped=ob, injected=used, drop_one_fired=nd1)
        print(json.dumps(out), flush=True)


if __name__ == "__main__":
    main()
