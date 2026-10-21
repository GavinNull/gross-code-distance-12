"""E-032: the fully translation-invariant ("uniform timing") family at period P: every X check uses the same label
order and CNOT times, every Z check the same (any of the 720 orders each), prep/meas inside the period with the
evaluator rule 0 < off(cnot) < off(meas) < P.  At P = 8 the 6 CNOTs of a check are at offsets 1..6 (forced), so a
circuit = (X order, Z order, Z start offset s in Z_8).  Legal: on every data qubit the 6 CNOT times are distinct mod P.
Deterministic: for every overlapping X/Z pair, floor((t_x - t_z)/P) is equal on the two shared qubits (E-024a
criterion, evaluator also checks via stim).  Prints counts and writes the list.

    PYTHONPATH=.:tests uv run python -m search.experiments.e032.uni8 --P 8
"""
from __future__ import annotations

import argparse
import itertools
import json

from search.experiments.e032 import common as C


def overlap_pairs():
    """(label in X check, label in Z check) pairs of shared qubits, as a set of 2-element tuples per overlap type."""
    T = C.table()
    out = set()
    for ia in range(C.N2):
        qa = {int(q): k for k, q in enumerate(T["X"][ia])}
        for ic in range(C.N2):
            qc = {int(q): k for k, q in enumerate(T["Z"][ic])}
            ov = sorted(set(qa) & set(qc))
            if ov:
                assert len(ov) == 2, len(ov)
                out.add(tuple(sorted((qa[q], qc[q]) for q in ov)))
    return sorted(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--P", type=int, default=8)
    a = ap.parse_args()
    P = a.P
    assert P == 8
    ov = overlap_pairs()
    perms = list(itertools.permutations(range(6)))
    out = []
    nleg = 0
    for ox in perms:
        tx = [0] * 6
        for k, lab in enumerate(ox):
            tx[lab] = 1 + k
        for oz in perms:
            tz0 = [0] * 6
            for k, lab in enumerate(oz):
                tz0[lab] = 1 + k
            for s in range(P):
                tz = [s + v for v in tz0]
                # L qubits: X labels A (0..2), Z labels B (3..5); R qubits: X labels B, Z labels A
                Lt = [tx[0], tx[1], tx[2], tz[3], tz[4], tz[5]]
                Rt = [tx[3], tx[4], tx[5], tz[0], tz[1], tz[2]]
                if len({v % P for v in Lt}) < 6 or len({v % P for v in Rt}) < 6:
                    continue
                nleg += 1
                ok = all(len({(tx[lx] - tz[lz]) // P for lx, lz in pr}) == 1 for pr in ov)
                if ok:
                    out.append((ox, oz, s))
    print(json.dumps({"P": P, "overlap_types": len(ov), "legal": nleg, "legal_det": len(out)}))
    (C.OUT / f"uni{P}.json").write_text(json.dumps(out))


if __name__ == "__main__":
    main()
