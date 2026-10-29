"""Item 1: compare the step-pairing model with the evaluator's SD6 DEM, signature set by signature set.

The model is built from the *noiseless stim circuit itself* (parsed layer by layer), not from unroll() or the spec:
for each ancilla we read its instances (prep, CX list with times, measurement) off the circuit.
  Z basis: writers = MX ancillas (CX anc->data), readers = M ancillas (CX data->anc), errors of X type.
  X basis: writers = M ancillas (CX data->anc: Z on target spreads to control), readers = MX ancillas.
Single faults of the model: data error at every half-integer time 0.5 .. last+0.5; writer ancilla error after its
(k-1)-th CNOT of each instance (k = 1..6, k=1 = right after reset); reader measurement flip.
Finite index of a deposit at time u on q for reader b = #{instances of b whose CX on q is earlier than u}; item flips
detector (row(b), index).  Observable = L image of the residual data error.

  uv run python -m search.theory.B_audit.dem_check gross search/experiments/e032/u11_spec.json 2
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict

import numpy as np
import stim

from search.theory.B_audit.common import get_code, load_spec_dict


def parse(circ: stim.Circuit, n: int):
    """returns layers count, per-ancilla instance list [(prep_t, [(t, data)], meas_t)], meas gate type per ancilla."""
    t = 0
    inst = defaultdict(list)    # anc -> list of dicts
    kind = {}
    for op in circ.flattened():
        name = op.name
        if name == "TICK":
            t += 1
            continue
        qs = [x.value for x in op.targets_copy() if x.is_qubit_target]
        if name in ("R", "RX"):
            for q in qs:
                if q >= n:
                    inst[q].append({"prep": t, "cx": [], "meas": None})
        elif name == "CX":
            for a, b in zip(qs[::2], qs[1::2]):
                if a >= n and b < n:
                    inst[a][-1]["cx"].append((t, b)); kind.setdefault(a, "W_ctrl")
                elif b >= n and a < n:
                    inst[b][-1]["cx"].append((t, a)); kind.setdefault(b, "W_tgt")
                else:
                    raise AssertionError("unexpected CX")
        elif name in ("M", "MX"):
            for q in qs:
                if q >= n:
                    inst[q][-1]["meas"] = t
                    kind[q] = (kind[q], name)
        elif name in ("DETECTOR", "OBSERVABLE_INCLUDE"):
            pass
        else:
            raise AssertionError(name)
    return t, inst, kind


def model(code, circ, basis):
    n = code.n
    mx = code.HX.shape[0]
    nlay, inst, kind = parse(circ, n)
    last = nlay - 1          # last ancilla layer index; final data readout is after it
    # Z basis: readers are M-measured (Z) ancillas; X basis: MX ancillas
    rgate = "M" if basis == "Z" else "MX"
    readers = {a for a, k in kind.items() if k[1] == rgate}
    writers = set(kind) - readers
    row = {a: (a - n) if a < n + mx else (a - n - mx) for a in kind}
    L = (np.asarray(code.LZ if basis == "Z" else code.LX) % 2).astype(np.uint8)
    reads = defaultdict(list)   # q -> [(row, sorted read times)]
    for b in readers:
        per_q = defaultdict(list)
        for I in inst[b]:
            for tt, q in I["cx"]:
                per_q[q].append(tt)
        for q, ts in per_q.items():
            reads[q].append((row[b], sorted(ts)))
    R = len(next(iter(inst.values())))

    def items(q, u):
        return [(r, sum(1 for x in ts if x < u)) for r, ts in reads[q]]

    def obs(qs):
        v = np.zeros(n, np.uint8)
        for q in qs:
            v[q] ^= 1
        return frozenset(np.flatnonzero(L.astype(np.int64) @ v % 2).tolist())

    def red(its):
        s = set()
        for it in its:
            s ^= {it}
        return frozenset(s)
    out = set()
    for q in range(n):
        for u2 in range(1, 2 * (last + 1) + 1, 2):
            out.add((red(items(q, u2 / 2)), obs([q])))
    for a in writers:
        for I in inst[a]:
            cx = sorted(I["cx"])
            assert len(cx) == 6 and I["prep"] < cx[0][0] and cx[-1][0] < I["meas"]
            for k in range(1, 7):
                suf = cx[k - 1:]
                its = []
                for tt, q in suf:
                    its += items(q, tt)
                out.add((red(its), obs([q for _, q in suf])))
    for b in readers:
        for t in range(R):
            out.add((frozenset({(row[b], t), (row[b], t + 1)}), frozenset()))
    out.discard((frozenset(), frozenset()))
    return out, R


def dem(circ):
    from evaluators.noise import add_noise
    noisy = add_noise(circ, "sd6", 1e-3)
    coords = noisy.get_detector_coordinates()
    d = noisy.detector_error_model(approximate_disjoint_errors=True, flatten_loops=True)
    out = set()
    for e in d.flattened():
        if e.type != "error":
            continue
        ds, os_ = set(), set()
        for t in e.targets_copy():
            if t.is_relative_detector_id():
                c = coords[t.val]
                ds ^= {(int(c[0]), int(c[1]))}
            elif t.is_logical_observable_id():
                os_ ^= {t.val}
        if ds or os_:
            out.add((frozenset(ds), frozenset(os_)))
    return out


def main():
    codename, specpath = sys.argv[1], sys.argv[2]
    Rs = [int(x) for x in sys.argv[3].split(",")]
    from evaluators import candidate as cand
    code = get_code(codename)
    spec = cand.parse_schedule(load_spec_dict(specpath))
    assert not cand.validate_schedule(spec, code)
    for R in Rs:
        res = {"code": codename, "spec": specpath, "R": R}
        for basis in ("Z", "X"):
            circ = cand.memory_circuit(spec, code, basis, R)
            M, Rr = model(code, circ, basis)
            assert Rr == R
            D = dem(circ)
            res[basis] = {"model": len(M), "dem": len(D), "equal": M == D, "model_only": len(M - D),
                          "dem_only": len(D - M)}
            if M != D:
                res[basis]["ex_dem_only"] = [sorted(map(list, x[0])) for x in list(D - M)[:3]]
                res[basis]["ex_model_only"] = [sorted(map(list, x[0])) for x in list(M - D)[:3]]
        print(json.dumps(res), flush=True)


if __name__ == "__main__":
    main()
