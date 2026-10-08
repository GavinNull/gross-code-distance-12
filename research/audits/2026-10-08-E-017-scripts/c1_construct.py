"""C1: independent construction checks.
- mid-cycle code [[288,12,?]]: HX HZ^T = 0, k = 12
- contraction property of F_0, F_1 (which stabilizers become weight 1, on which qubit / basis)
- end-cycle codes: left-only support, generator weights, k
- noiseless determinism of detectors handled in c2.
Output: results/E-017-audit/c1_<hom>_<order>.json and end-cycle matrices (npz).
"""
import json
import sys

import numpy as np

from common import N, bb_checks, spec, propagate_pauli, rank, rref, nullspace

hom = sys.argv[1] if len(sys.argv) > 1 else "x"
order = sys.argv[2] if len(sys.argv) > 2 else "repo"
out = {}
HX, HZ = bb_checks()
assert not np.any((HX.astype(int) @ HZ.T.astype(int)) % 2)
rx, rz = rank(HX), rank(HZ)
out["mid"] = dict(n=2 * N, rankX=rx, rankZ=rz, k=2 * N - rx - rz)
gates, meas, a, b = spec(hom, order)
out["a_list"], out["b_list"] = a, b
ec = {}
for c in range(2):
    layers = gates[c]
    # every layer: each qubit at most once; count gates
    for layer in layers:
        qs = [q for g in layer for q in g]
        assert len(qs) == len(set(qs)), "qubit used twice in a layer"
        assert len(layer) == N
    mX, mZ = set(meas[c]["X"]), set(meas[c]["Z"])
    assert len(mX) == 72 and len(mZ) == 72 and not (mX & mZ) and all(q >= N for q in mX | mZ)
    contracted = {"X": [], "Z": []}
    expanded = {"X": [], "Z": []}
    for typ, H in (("X", HX), ("Z", HZ)):
        for s in range(N):
            v = H[s].astype(bool)
            if typ == "X":
                x, z = propagate_pauli(v, np.zeros(2 * N, bool), layers)
                sup = np.nonzero(x)[0]; other = np.nonzero(z)[0]
            else:
                x, z = propagate_pauli(np.zeros(2 * N, bool), v, layers)
                sup = np.nonzero(z)[0]; other = np.nonzero(x)[0]
            assert len(other) == 0  # CSS preserved by CNOT circuits
            if len(sup) == 1:
                q = int(sup[0])
                contracted[typ].append((s, q))
            else:
                expanded[typ].append((s, sup))
    # contracted X stabs must land on X-measured qubits, Z on Z-measured, bijectively
    cq = {t: sorted(q for _, q in contracted[t]) for t in "XZ"}
    ok = cq["X"] == sorted(mX) and cq["Z"] == sorted(mZ)
    # repo's contraction-round rule: X stab g: f(g)+f(a0); Z stab g: f(g)+f(b0)+1
    from common import HOMS, l as L_, m as M_
    f = HOMS[hom]
    rule_ok = all(((f((s // M_, s % M_)) + f(a[0])) % 2 == c) for s, _ in contracted["X"]) and \
        all(((f((s // M_, s % M_)) + f(b[0]) + 1) % 2 == c) for s, _ in contracted["Z"])
    # end-cycle code: expanding stabilisers after F_c; right support must be only on measured qubits of same basis
    rows = {"X": [], "Z": []}
    bad = 0
    for typ in "XZ":
        same = mX if typ == "X" else mZ
        for s, sup in expanded[typ]:
            right = [q for q in sup if q >= N]
            if not all(q in same for q in right):
                bad += 1
            v = np.zeros(N, np.uint8)
            v[[q for q in sup if q < N]] = 1
            rows[typ].append(v)
    HXe, HZe = np.array(rows["X"]), np.array(rows["Z"])
    assert not np.any((HXe.astype(int) @ HZe.T.astype(int)) % 2)
    k = N - rank(HXe) - rank(HZe)
    ec[c] = dict(n_contracted_X=len(contracted["X"]), n_contracted_Z=len(contracted["Z"]),
                 meas_match=ok, repo_round_rule=rule_ok, expanding_bad_right_support=bad,
                 rows_X=len(rows["X"]), rows_Z=len(rows["Z"]), rankX=rank(HXe), rankZ=rank(HZe), k=k,
                 wX=sorted(set(map(int, HXe.sum(1)))), wZ=sorted(set(map(int, HZe.sum(1)))),
                 left_degree_X=sorted(set(map(int, HXe.sum(0)))), left_degree_Z=sorted(set(map(int, HZe.sum(0)))))
    np.savez(f"/Users/ephemeral/Desktop/qec-ai-search/results/E-017-audit/endcycle_{hom}_{order}_c{c}.npz", HX=HXe, HZ=HZe)
out["endcycle"] = ec
# connectivity: distinct neighbours per qubit over both rounds
nb = [set() for _ in range(2 * N)]
for c in range(2):
    for layer in gates[c]:
        for (u, v) in layer:
            nb[u].add(v); nb[v].add(u)
out["connectivity"] = sorted(set(len(s) for s in nb))
print(json.dumps(out, indent=1, default=str))
json.dump(out, open(f"/Users/ephemeral/Desktop/qec-ai-search/results/E-017-audit/c1_{hom}_{order}.json", "w"), indent=1, default=str)
