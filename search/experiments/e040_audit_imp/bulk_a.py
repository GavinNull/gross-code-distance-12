"""E-040 impossibility audit (independent code): exact bulk test of one fault pattern on many T(P) schedules.

Sector X (Z-basis memory, X errors): hook side = X checks (ancilla |+>, CNOT anc->data at tH[m] + jP), readers = Z
checks (CNOT data->anc at tR[b] + sP, measured once per instance s; detector D(c', s) = m(c', s) xor m(c', s-1)).
An X on data q at half-integer time tau flips every instance s of reader (c', b) with tR[b] + sP > tau, i.e. the
measurement record of c' changes from instance s0 = floor((tau - tR[b]) / P) + 1 on => exactly D(c', s0) fires.
Faults (bulk coordinates):
  ('d', q, b, r)  X on q at tau = tR[b] + rP + 1/2 (just after its read by reader label b, instance r)
  ('h', c, S, j)  X on ancilla of hook-side check c just before the CNOTs of S in instance j; requires S to be exactly
                  the set of labels strictly later than all others (a suffix of the order); puts X on TH[c][m] at
                  tau = tH[m] + jP + 1/2 for m in S (X on an X-measured ancilla is otherwise harmless)
  ('m', c, r)     flip of m(c, r): D(c, r), D(c, r+1)
Sector Z: the same with X <-> Z exchanged (Z-check hooks, X-check readers, X-basis memory).
A pattern applies iff all hooks exist and every detector fires an even number of times.  The residual data error
(XOR of data supports) does not depend on the times; it is checked separately (nontrivial logical)."""
import numpy as np

OFF = 32


def readers(C, sector):
    TR = C["T"]["Z" if sector == "X" else "X"]
    rd = [[] for _ in range(C["NQ"])]
    for c in range(C["N2"]):
        for b in range(6):
            rd[int(TR[c][b])].append((c, b))
    return rd


def residual(C, sector, faults):
    TH = C["T"]["X" if sector == "X" else "Z"]
    e = np.zeros(C["NQ"], np.uint8)
    for f in faults:
        if f[0] == "d":
            e[f[1]] ^= 1
        elif f[0] == "h":
            for m in f[2]:
                e[int(TH[f[1]][m])] ^= 1
    return e


def applies(C, sector, faults, tH, tR, P, rd=None):
    tH = np.asarray(tH, np.int64)
    tR = np.asarray(tR, np.int64)
    rd = rd or readers(C, sector)
    TH = C["T"]["X" if sector == "X" else "Z"]
    N2 = C["N2"]
    n = len(tH)
    ok = np.ones(n, bool)
    cols = []

    def hit(q, tau2):            # tau2 = 2 * tau (odd)
        for c2, b2 in rd[q]:
            s0 = np.floor_divide(tau2 - 2 * tR[:, b2], 2 * P) + 1
            cols.append(c2 + N2 * (s0 + OFF))

    for f in faults:
        if f[0] == "d":
            _, q, b, r = f
            hit(q, 2 * (tR[:, b] + r * P) + 1)
        elif f[0] == "h":
            _, c, S, j = f
            S = sorted(set(S))
            rest = [m for m in range(6) if m not in S]
            ok &= tH[:, S].min(1) > tH[:, rest].max(1)
            for m in S:
                hit(int(TH[c][m]), 2 * (tH[:, m] + j * P) + 1)
        elif f[0] == "m":
            _, c2, r = f
            cols.append(np.full(n, c2 + N2 * (r + OFF)))
            cols.append(np.full(n, c2 + N2 * (r + 1 + OFF)))
        else:
            raise ValueError(f)
    if len(cols) % 2:
        return np.zeros(n, bool)
    M = np.sort(np.stack(cols, 1), 1)
    return ok & (M[:, 0::2] == M[:, 1::2]).all(1)


def dets_one(C, sector, faults, tH, tR, P):
    """single schedule: set of fired detectors (c', s) (parity) of a fault list (hooks assumed present)."""
    rd = readers(C, sector)
    TH = C["T"]["X" if sector == "X" else "Z"]
    par = {}

    def flip(d):
        par[d] = par.get(d, 0) ^ 1

    def hit(q, tau2):
        for c2, b2 in rd[q]:
            flip((c2, (tau2 - 2 * tR[b2]) // (2 * P) + 1))

    for f in faults:
        if f[0] == "d":
            _, q, b, r = f
            hit(q, 2 * (tR[b] + r * P) + 1)
        elif f[0] == "h":
            _, c, S, j = f
            for m in S:
                hit(int(TH[c][m]), 2 * (tH[m] + j * P) + 1)
        else:
            flip((f[1], f[2]))
            flip((f[1], f[2] + 1))
    return {d for d, v in par.items() if v}
