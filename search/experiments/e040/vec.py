"""E-040: vectorised test of one bulk witness (bulk.Sector fault list) on many schedules at once.

Rows = schedules of one period P given by absolute times (tH: hook side, tR: reader side; arrays n x 6).  A hook
('h', c, S, j) is present iff S is a suffix of that row's hook order (every label of S later than every label not
in S); its detectors and those of data cuts ('d', q, b, r) are recomputed per row exactly as in bulk.Sector.dets;
the residual data error (hence the logical effect) does not depend on the row.  Row passes iff every hook is present
and every detector is flipped an even number of times.
"""
from __future__ import annotations

import numpy as np

OFF = 64


def codes_for(S, f, tH, tR, P):
    """list of int arrays (n,) of detector codes c + N2 * (round + OFF)."""
    N2 = S.N2
    out = []

    def data_time(q, t2):
        for c, b in S.readers[q]:
            r = np.floor_divide(t2 - 2 * tR[:, b], 2 * P) + 1
            out.append(c + N2 * (r + OFF))

    if f[0] == "d":
        _, q, b, r = f
        data_time(q, 2 * (tR[:, b] + r * P) + 1)
    elif f[0] == "h":
        _, c, Sx, j = f
        for m in Sx:
            data_time(int(S.TH[c][m]), 2 * (tH[:, m] + j * P) + 1)
    else:
        _, c, r = f
        out.append(np.full(len(tH), c + N2 * (r + OFF)))
        out.append(np.full(len(tH), c + N2 * (r + 1 + OFF)))
    return out


def test(S, faults, tH, tR, P):
    n = len(tH)
    ok = np.ones(n, bool)
    cols = []
    for f in faults:
        if f[0] == "h":
            Sx = sorted(f[2])
            Sc = [m for m in range(6) if m not in f[2]]
            ok &= tH[:, Sx].min(axis=1) > tH[:, Sc].max(axis=1)
        cols += codes_for(S, f, tH, tR, P)
    M = np.sort(np.stack(cols, axis=1), axis=1)
    if M.shape[1] % 2:
        return np.zeros(n, bool)
    ok &= (M[:, 0::2] == M[:, 1::2]).all(axis=1)
    return ok
