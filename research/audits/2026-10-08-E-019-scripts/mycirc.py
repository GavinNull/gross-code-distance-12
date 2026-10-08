"""E-019 audit: independent construction of Shaw-Terhal morphing circuits (arXiv:2407.16336v3).

Written from the paper text only (Table IV = Table II without a1=b1=1; Table VIII = round-2 CNOTs reversed;
Table IX = the explicit (a1,a2,a3)/(b1,b2,b3) orderings). Does NOT import search/experiments/e019 or the
E-017 audit scripts.

Group G = Z_l x Z_m written additively, monomial x^i y^j = (i, j). Paper convention: X-stabiliser
s(X,g) = X(Ag, Bg) (left support {a_i+g}, right {b_j+g}); Z-stabiliser s(Z,g) = Z(B^-1 g, A^-1 g).
K = ker f = {g: f(g)=0}; F1 uses g in K, h in K^c; F2 uses g in K^c, h in K.

Table IV (per g, h):
  r1: CX L(g)->R(-a1+b3+g) ; CX R(-a3+b1+h)->L(h)
  r2: CX L(g)->R(-a1+b2+g) ; CX R(-a2+b1+h)->L(h)
  r3: CX R(-a1+b1+g)->L(g) ; CX L(h)->R(-a1+b1+h)
  M : MX R(-a1+b1+g) ; MZ R(-a1+b1+h)
Table VIII:
  r1: as Table IV
  r2: CX R(-a1+b2+g)->L(g) ; CX L(h)->R(-a2+b1+h)
  r3: CX R(-a2+b2+h)->L(h) ; CX L(g)->R(-a2+b2+g)
  M : MX R(-a2+b2+h) ; MZ R(-a2+b2+g)
Cycle (paper main text): start in C~1; half-cycle = R_j, F_j^dagger, F_i, M_i, alternating i = 2, 1, 2, ...
"""
from __future__ import annotations
import numpy as np
import stim

HOM = {"x": lambda g: g[0] % 2, "y": lambda g: g[1] % 2, "xy": lambda g: (g[0] + g[1]) % 2}

# parent codes, 2407.16336 Table I (A, B in Table I's written order)
PARENT = {
    "bb72": (6, 6, [(3, 0), (0, 1), (0, 2)], [(0, 3), (1, 0), (2, 0)]),
    "bb108": (9, 6, [(3, 0), (0, 1), (0, 2)], [(0, 3), (1, 0), (2, 0)]),
    "bb144": (12, 6, [(3, 0), (0, 1), (0, 2)], [(0, 3), (1, 0), (2, 0)]),
    "bb288": (12, 12, [(3, 0), (0, 7), (0, 2)], [(0, 3), (1, 0), (2, 0)]),
}


class Morph:
    def __init__(self, l, m, a, b, hom, kind):
        """a, b: ordered triples (a1,a2,a3), (b1,b2,b3); kind 'IV' or 'VIII'."""
        self.l, self.m, self.a, self.b, self.hom, self.kind = l, m, list(a), list(b), hom, kind
        self.N = l * m
        f = HOM[hom]
        # criterion: f(a1) != f(a2) = f(a3), same for b
        fa = [f(x) for x in a]
        fb = [f(x) for x in b]
        assert fa[1] == fa[2] != fa[0] and fb[1] == fb[2] != fb[0], (a, b, hom)
        if hom in ("x", "xy"):
            assert l % 2 == 0
        if hom in ("y", "xy"):
            assert m % 2 == 0
        self.G = [(i, j) for i in range(l) for j in range(m)]

    def gi(self, g):
        return (g[0] % self.l) * self.m + (g[1] % self.m)

    def Lq(self, g):
        return self.gi(g)

    def Rq(self, g):
        return self.N + self.gi(g)

    @staticmethod
    def add(*gs):
        return (sum(g[0] for g in gs), sum(g[1] for g in gs))

    @staticmethod
    def neg(g):
        return (-g[0], -g[1])

    def F(self, i):
        """list of 3 layers (each list of (ctrl, tgt)) and measurement dict for contraction circuit F_i."""
        f = HOM[self.hom]
        a1, a2, a3 = self.a
        b1, b2, b3 = self.b
        ad, ng = self.add, self.neg
        layers = [[], [], []]
        meas = {"X": [], "Z": []}
        for g in self.G:
            is_g = (f(g) == 0) if i == 1 else (f(g) == 1)   # g-role (in K for F1) else h-role
            L = self.Lq(g)
            if self.kind == "IV":
                if is_g:
                    layers[0].append((L, self.Rq(ad(ng(a1), b3, g))))
                    layers[1].append((L, self.Rq(ad(ng(a1), b2, g))))
                    layers[2].append((self.Rq(ad(ng(a1), b1, g)), L))
                    meas["X"].append(self.Rq(ad(ng(a1), b1, g)))
                else:
                    h = g
                    layers[0].append((self.Rq(ad(ng(a3), b1, h)), L))
                    layers[1].append((self.Rq(ad(ng(a2), b1, h)), L))
                    layers[2].append((L, self.Rq(ad(ng(a1), b1, h))))
                    meas["Z"].append(self.Rq(ad(ng(a1), b1, h)))
            else:  # VIII
                if is_g:
                    layers[0].append((L, self.Rq(ad(ng(a1), b3, g))))
                    layers[1].append((self.Rq(ad(ng(a1), b2, g)), L))
                    layers[2].append((L, self.Rq(ad(ng(a2), b2, g))))
                    meas["Z"].append(self.Rq(ad(ng(a2), b2, g)))
                else:
                    h = g
                    layers[0].append((self.Rq(ad(ng(a3), b1, h)), L))
                    layers[1].append((L, self.Rq(ad(ng(a2), b1, h))))
                    layers[2].append((self.Rq(ad(ng(a2), b2, h)), L))
                    meas["X"].append(self.Rq(ad(ng(a2), b2, h)))
        for lay in layers:
            qs = [q for p in lay for q in p]
            assert len(qs) == len(set(qs)) == 2 * self.N, "layer not a perfect matching"
        assert len(set(meas["X"]) | set(meas["Z"])) == self.N and not (set(meas["X"]) & set(meas["Z"]))
        return layers, meas

    # ---------------- mid-cycle stabilisers as stim PauliStrings
    def mid_stabs(self):
        n2 = 2 * self.N
        X, Z = [], []
        for g in self.G:
            p = stim.PauliString(n2)
            for a in self.a:
                p[self.Lq(self.add(a, g))] = "X"
            for b in self.b:
                p[self.Rq(self.add(b, g))] = "X"
            X.append(p)
            q = stim.PauliString(n2)
            for b in self.b:
                q[self.Lq(self.add(self.neg(b), g))] = "Z"
            for a in self.a:
                q[self.Rq(self.add(self.neg(a), g))] = "Z"
            Z.append(q)
        return X, Z

    def layers_circuit(self, layers):
        c = stim.Circuit()
        for lay in layers:
            c.append("CX", [q for p in lay for q in p])
            c.append("TICK")
        return c

    def check_contraction(self):
        """derive (not assume): for F_i, each mid-cycle stabiliser either contracts to a single Pauli on a
        right qubit measured in the matching basis (contracting), or is mapped to an operator whose right
        support lies only on same-basis measured qubits (expanding). Returns end-cycle check matrices
        (left part of images of expanding stabilisers) for i = 1, 2."""
        X, Z = self.mid_stabs()
        out = {}
        for i in (1, 2):
            layers, meas = self.F(i)
            circ = self.layers_circuit(layers)
            mX, mZ = set(meas["X"]), set(meas["Z"])
            ncontr = {"X": 0, "Z": 0}
            Hend = {"X": [], "Z": []}
            contr_q = {"X": set(), "Z": set()}
            for typ, stabs in (("X", X), ("Z", Z)):
                mset = mX if typ == "X" else mZ
                for s in stabs:
                    t = s.after(circ)
                    sup = [q for q in range(2 * self.N) if t[q] != 0]
                    paulis = {"_XYZ"[t[q]] for q in sup}
                    assert paulis == {typ}, "basis mixing"
                    rs = [q for q in sup if q >= self.N]
                    ls = [q for q in sup if q < self.N]
                    if len(sup) == 1 and rs and rs[0] in mset:
                        ncontr[typ] += 1
                        contr_q[typ].add(rs[0])
                    else:
                        assert set(rs) <= mset, "expanding stabiliser has right support on other-basis measured qubit"
                        v = np.zeros(self.N, dtype=np.uint8)
                        v[ls] = 1
                        Hend[typ].append(v)
            assert ncontr["X"] == len(mX) == len(contr_q["X"]) and ncontr["Z"] == len(mZ) == len(contr_q["Z"]), ncontr
            out[i] = (np.array(Hend["X"]), np.array(Hend["Z"]))
        return out

    # ---------------- memory circuit
    def stab_images(self):
        """for i in (1,2): dict stab-id -> ('c', qubit) or ('e', left_support, right_support) under F_i.
        stab-id = (type, index g)."""
        X, Z = self.mid_stabs()
        out = {}
        for i in (1, 2):
            layers, meas = self.F(i)
            circ = self.layers_circuit(layers)
            d = {}
            for typ, stabs in (("X", X), ("Z", Z)):
                for gi, s in enumerate(stabs):
                    t = s.after(circ)
                    sup = [q for q in range(2 * self.N) if t[q] != 0]
                    rs = [q for q in sup if q >= self.N]
                    ls = [q for q in sup if q < self.N]
                    if len(sup) == 1 and rs:
                        d[(typ, gi)] = ("c", rs[0])
                    else:
                        d[(typ, gi)] = ("e", ls, rs)
            out[i] = d
        return out

    def memory(self, basis, T, *, full_detectors=True, nsamp=None, seed=1):
        """T half-cycles starting from C~1 (half-cycle t measures M_2 for odd t, M_1 for even t), final
        transversal readout of the left qubits in `basis` in the same layer as the last M.
        Detectors (explicit, from Pauli propagation): for a stabiliser s contracted at half-cycle t onto q:
        rec(q,t) xor rec(right support of its expanded image at t-1); same-basis always, other-basis for t>=2
        if full_detectors. Final: left readout on expanded image xor rec(right support, T).
        Observables: complement of the detector span inside the deterministic-parity space (noiseless sampling)."""
        N = self.N
        F = {1: self.F(1), 2: self.F(2)}
        img = self.stab_images()
        c = stim.Circuit()
        recidx = {}
        nrec = 0
        _, m1 = F[1]
        c.append("RX" if basis == "X" else "R", list(range(N)))
        c.append("RX", sorted(m1["X"]))
        c.append("R", sorted(m1["Z"]))
        c.append("TICK")
        for t in range(1, T + 1):
            i = 2 if t % 2 == 1 else 1
            j = 3 - i
            if t > 1:
                _, mj = F[j]
                c.append("RX", sorted(mj["X"]))
                c.append("R", sorted(mj["Z"]))
                c.append("TICK")
            for lay in reversed(F[j][0]):
                c.append("CX", [q for p in lay for q in p]); c.append("TICK")
            for lay in F[i][0]:
                c.append("CX", [q for p in lay for q in p]); c.append("TICK")
            mi = F[i][1]
            c.append("MX", sorted(mi["X"]))
            for q in sorted(mi["X"]):
                recidx[(t, q)] = nrec; nrec += 1
            c.append("M", sorted(mi["Z"]))
            for q in sorted(mi["Z"]):
                recidx[(t, q)] = nrec; nrec += 1
            if t < T:
                c.append("TICK")
        c.append("MX" if basis == "X" else "M", list(range(N)))
        for q in range(N):
            recidx[("fin", q)] = nrec; nrec += 1
        dets = []   # (list of record indices, coords)
        for t in range(1, T + 1):
            i = 2 if t % 2 == 1 else 1
            j = 3 - i
            for sid, v in img[i].items():
                if v[0] != "c":
                    continue
                typ = sid[0]
                if typ != basis and not (full_detectors and t >= 2):
                    continue
                rr = [recidx[(t, v[1])]]
                if t >= 2:
                    e = img[j][sid]
                    assert e[0] == "e"
                    rr += [recidx[(t - 1, q)] for q in e[2]]
                dets.append((rr, [v[1], t, 0 if typ == "Z" else 1]))
        ilast = 2 if T % 2 == 1 else 1
        for sid, v in img[ilast].items():
            if v[0] == "e" and sid[0] == basis:
                rr = [recidx[("fin", q)] for q in v[1]] + [recidx[(T, q)] for q in v[2]]
                dets.append((rr, [-1, T + 1, 2]))
        # deterministic parity spaces by noiseless sampling (relative to reference sample).
        # D_all: untwirled. D_det: with the k logical ops of C~1 conjugate to the observables applied with
        # prob 1/2 each right after the initial reset (logical twirl) -> observables become random.
        bmask = np.zeros(nrec, dtype=bool)
        for (t, q), k in recidx.items():
            if t == "fin":
                bmask[k] = True
        # record basis: MX for X-measured right qubits, final in `basis`
        rb = {}
        for t in range(1, T + 1):
            i = 2 if t % 2 == 1 else 1
            for q in F[i][1]["X"]:
                rb[recidx[(t, q)]] = "X"
            for q in F[i][1]["Z"]:
                rb[recidx[(t, q)]] = "Z"
        for q in range(N):
            rb[recidx[("fin", q)]] = basis
        cols = np.array([k for k in range(nrec) if full_detectors or rb[k] == basis])
        HX1, HZ1 = self.check_contraction()[1]
        flipper = logicals(HX1, HZ1) if basis == "Z" else logicals(HZ1, HX1)   # X-logicals flip Z obs
        ctw = stim.Circuit()
        first = True
        for inst in c:
            ctw.append(inst)
            if first and inst.name == "TICK":
                first = False
                for v in flipper:
                    ctw.append("E", [stim.target_x(int(q)) if basis == "Z" else stim.target_z(int(q))
                                     for q in np.nonzero(v)[0]], 0.5)
        ns = nsamp or (len(cols) + 400)
        ref = c.reference_sample().astype(np.uint8)
        S = (c.compile_sampler(seed=seed).sample(ns).astype(np.uint8) ^ ref[None, :])[:, cols]
        Stw = (ctw.compile_sampler(seed=seed + 1).sample(ns).astype(np.uint8) ^ ref[None, :])[:, cols]
        Dall = gf2_null(S)
        Ddet = gf2_null(Stw)
        def lift(V):
            out = np.zeros((len(V), nrec), dtype=np.uint8)
            out[:, cols] = V
            return out
        Dall, Ddet = lift(Dall), lift(Ddet)
        Dm = np.zeros((len(dets), nrec), dtype=np.uint8)
        for k, (rr, _) in enumerate(dets):
            for x in rr:
                Dm[k, x] ^= 1
        Sfull = c.compile_sampler(seed=seed + 2).sample(ns).astype(np.uint8) ^ ref[None, :]
        Stwf = ctw.compile_sampler(seed=seed + 3).sample(ns).astype(np.uint8) ^ ref[None, :]
        assert not (Dm @ Stwf.T % 2).any(), "explicit detector not deterministic under logical twirl"
        rD = gf2_rank(Dm)
        extra = []
        cur = Dm.copy(); rk = rD
        for v in Ddet:
            t2 = np.vstack([cur, v])
            if gf2_rank(t2) > rk:
                extra.append(v); cur = t2; rk += 1
        obs = []
        for v in Dall:
            t2 = np.vstack([cur, v])
            if gf2_rank(t2) > rk:
                obs.append(v); cur = t2; rk += 1
        assert len(obs) == len(flipper), (len(obs), len(flipper))
        self.det_info = dict(n_det_explicit=len(dets), rank_explicit=int(rD), n_extra_det=len(extra),
                             dim_det=int(Ddet.shape[0]), dim_all=int(Dall.shape[0]), n_obs=len(obs))
        def tg(x):
            return stim.target_rec(x - nrec)
        for rr, co in dets:
            c.append("DETECTOR", [tg(x) for x in rr], co)
        for v in extra:
            c.append("DETECTOR", [tg(x) for x in np.nonzero(v)[0]], [-2, 0, 3])
        for o, v in enumerate(obs):
            c.append("OBSERVABLE_INCLUDE", [tg(x) for x in np.nonzero(v)[0]], o)
        self.recidx = recidx
        return c


# ---------------- GF(2) helpers (own)
def gf2_rank(M):
    M = np.array(M, dtype=np.uint8) % 2
    r = 0
    rows, cols = M.shape
    for c in range(cols):
        p = np.nonzero(M[r:, c])[0]
        if len(p) == 0:
            continue
        p = p[0] + r
        M[[r, p]] = M[[p, r]]
        nz = np.nonzero(M[:, c])[0]
        nz = nz[nz != r]
        M[nz] ^= M[r]
        r += 1
        if r == rows:
            break
    return r


def gf2_null(M):
    M = np.array(M, dtype=np.uint8) % 2
    rows, cols = M.shape
    piv = []
    r = 0
    for c in range(cols):
        if r == rows:
            break
        p = np.nonzero(M[r:, c])[0]
        if len(p) == 0:
            continue
        p = p[0] + r
        M[[r, p]] = M[[p, r]]
        nz = np.nonzero(M[:, c])[0]
        nz = nz[nz != r]
        M[nz] ^= M[r]
        piv.append(c)
        r += 1
    free = [c for c in range(cols) if c not in set(piv)]
    out = np.zeros((len(free), cols), dtype=np.uint8)
    for k, fc in enumerate(free):
        out[k, fc] = 1
        for ri, pc in enumerate(piv):
            if M[ri, fc]:
                out[k, pc] = 1
    return out


def logicals(Hs, Ho):
    """same-type logicals: ker(Ho) modulo rowspace(Hs)."""
    K = gf2_null(Ho)
    cur = np.array(Hs, dtype=np.uint8)
    rk = gf2_rank(cur)
    out = []
    for v in K:
        t = np.vstack([cur, v])
        if gf2_rank(t) > rk:
            out.append(v)
            cur = t
            rk += 1
    return np.array(out, dtype=np.uint8)


def table_IX_orderings():
    """explicit orderings from 2407.16336 Table IX (Table VIII schedules) as ((a1,a2,a3),(b1,b2,b3))."""
    x = lambda k: (k, 0)
    y = lambda k: (0, k)
    return {
        ("bb72", "x"): [((x(3), y(1), y(2)), (x(1), x(2), y(3))), ((x(3), y(2), y(1)), (x(1), y(3), x(2)))],
        ("bb72", "y"): [((y(1), y(2), x(3)), (y(3), x(1), x(2))), ((y(1), x(3), y(2)), (y(3), x(2), x(1)))],
        ("bb72", "xy"): [((y(2), y(1), x(3)), (x(2), x(1), y(3))), ((y(2), x(3), y(1)), (x(2), y(3), x(1)))],
        ("bb144", "x"): [((x(3), y(2), y(1)), (x(1), y(3), x(2))), ((x(3), y(1), y(2)), (x(1), x(2), y(3)))],
        ("bb144", "y"): [((y(1), y(2), x(3)), (y(3), x(1), x(2))), ((y(1), x(3), y(2)), (y(3), x(2), x(1)))],
    }


def natural_order(code, hom):
    """a1 = the f-odd-one-out; (a2, a3) in Table I's written order of the remaining two terms (same for b)."""
    l, m, A, B = PARENT[code]
    f = HOM[hom]
    out = []
    for P in (A, B):
        v = [f(e) for e in P]
        odd = [k for k in range(3) if v.count(v[k]) == 1][0]
        rest = [P[k] for k in range(3) if k != odd]
        out.append((P[odd], rest[0], rest[1]))
    return out
