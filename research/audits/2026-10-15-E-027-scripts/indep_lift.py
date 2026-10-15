"""Auditor's independent lift encoder for E-027 (no code from code/proofs/ or gross12/ext.py is used).

Only the *noiseless* template circuit (gross12.schedule.build_circuits) and the data files (code matrices, extended
code columns, 4224 logicals) are taken from the package.  Everything else is re-implemented here:
  * SD6 fault enumeration directly from the noiseless layers (CX -> 15 two-qubit Paulis after; R/RX -> X/Z after;
    M/MX -> X/Z before; DEPOLARIZE1 X/Y/Z on every circuit qubit idle in the layer), every Pauli component kept
    separately (no merging);
  * own Pauli-frame propagation (bool arrays, one column per fault) -> measurement flips -> detectors, the
    circuit's own 12 observables, and the image (H e, L e) of the final-readout flip pattern e;
  * own CNF: per group (column of the logical) one variable per distinct detector pattern of faults with exactly that
    image, exactly-one via at-least-one + *binary* at-most-one, XOR = 0 on *every* detector of the circuit via 3-literal
    Tseitin chains, and an explicit "some circuit observable flips" condition (12 XOR chains + one OR clause) that
    uses the circuit's OBSERVABLE_INCLUDEs, not the L part of the image.

    python indep_lift.py CIRCUIT BASIS R I [I ...] [--enum N] [--theirs]
"""
import hashlib
import json
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
PKG = ROOT / "release" / "zenodo"
sys.path.insert(0, str(PKG / "code"))
from common_cli import circuit, load_code          # noqa: E402  (template + code matrices only)
from gross12.schedule import build_circuits         # noqa: E402

CADICAL = str(ROOT / "tools/cadical/build/cadical")
PAULI2 = [(a, b) for a in "IXYZ" for b in "IXYZ" if (a, b) != ("I", "I")]


def xz(p):
    return {"I": (0, 0), "X": (1, 0), "Y": (1, 1), "Z": (0, 1)}[p]


def faults_and_effects(circ, R, basis):
    code = load_code()
    spec = circuit(circ)
    c = build_circuits(spec.canonical(), code, R)[basis].flattened()
    # layers
    layers = [[]]
    for inst in c:
        if inst.name == "TICK":
            layers.append([])
        else:
            layers[-1].append(inst)
    allq = set()
    for inst in c:
        if inst.name in ("CX", "R", "RX", "M", "MX"):
            allq.update(t.value for t in inst.targets_copy())
        elif inst.name not in ("TICK", "DETECTOR", "OBSERVABLE_INCLUDE", "QUBIT_COORDS", "SHIFT_COORDS"):
            raise ValueError(inst.name)
    Q = max(allq) + 1
    # enumerate faults as (layer index, op index, phase, [(q, px, pz)])
    faults = []
    for li, layer in enumerate(layers):
        touched = set()
        for oi, inst in enumerate(layer):
            n = inst.name
            if n in ("DETECTOR", "OBSERVABLE_INCLUDE", "QUBIT_COORDS", "SHIFT_COORDS"):
                continue
            qs = [t.value for t in inst.targets_copy()]
            touched.update(qs)
            if n == "CX":
                for a, b in zip(qs[::2], qs[1::2]):
                    for pa, pb in PAULI2:
                        faults.append((li, oi, "after", [(a,) + xz(pa), (b,) + xz(pb)]))
            elif n in ("R", "RX"):
                for q in qs:
                    faults.append((li, oi, "after", [(q, 1, 0) if n == "R" else (q, 0, 1)]))
            elif n in ("M", "MX"):
                for q in qs:
                    faults.append((li, oi, "before", [(q, 1, 0) if n == "M" else (q, 0, 1)]))
        for q in sorted(allq - touched):
            for p in "XYZ":
                faults.append((li, len(layer), "after", [(q,) + xz(p)]))
    F = len(faults)
    inj = defaultdict(list)
    for f, (li, oi, ph, paulis) in enumerate(faults):
        inj[(li, oi, ph)].append((f, paulis))
    X = np.zeros((Q, F), bool)
    Z = np.zeros((Q, F), bool)

    def inject(key):
        for f, paulis in inj.get(key, ()):
            for q, px, pz in paulis:
                X[q, f] ^= bool(px)
                Z[q, f] ^= bool(pz)

    meas = []
    dets, obs = [], defaultdict(list)
    for li, layer in enumerate(layers):
        for oi, inst in enumerate(layer):
            n = inst.name
            if n == "DETECTOR":
                dets.append([len(meas) + t.value for t in inst.targets_copy()])
                continue
            if n == "OBSERVABLE_INCLUDE":
                k = int(inst.gate_args_copy()[0])
                obs[k] += [len(meas) + t.value for t in inst.targets_copy()]
                continue
            if n in ("QUBIT_COORDS", "SHIFT_COORDS"):
                continue
            qs = [t.value for t in inst.targets_copy()]
            inject((li, oi, "before"))
            if n == "CX":
                for a, b in zip(qs[::2], qs[1::2]):
                    X[b] ^= X[a]
                    Z[a] ^= Z[b]
            elif n in ("R", "RX"):
                for q in qs:
                    X[q] = False
                    Z[q] = False
            elif n == "M":
                for q in qs:
                    meas.append((q, X[q].copy()))
                    Z[q] = False
            elif n == "MX":
                for q in qs:
                    meas.append((q, Z[q].copy()))
                    X[q] = False
            inject((li, oi, "after"))
        inject((li, len(layer), "after"))
    M = np.array([m for _, m in meas])                        # (n_meas, F)
    D = np.zeros((len(dets), F), bool)
    for i, recs in enumerate(dets):
        for r in recs:
            D[i] ^= M[r]
    O = np.zeros((len(obs), F), bool)
    for k in sorted(obs):
        for r in obs[k]:
            O[k] ^= M[r]
    nq = code.n
    final = [q for q, _ in meas[-nq:]]
    assert final == list(range(nq)), "final readout is not data 0..n-1 in order"
    E = M[-nq:].astype(np.int64)                              # final data flips (n, F)
    H, L = (code.HZ, code.LZ) if basis == "Z" else (code.HX, code.LX)
    Hi = (H.astype(np.int64) @ E) % 2
    Li = (L.astype(np.int64) @ E) % 2
    return dict(code=code, F=F, D=D, O=O, Hi=Hi.astype(bool), Li=Li.astype(bool), ndet=len(dets), faults=faults)


def ext_columns(basis, code):
    d = json.load(open(PKG / "data/extended_code" / f"extended_code_{basis}_memory.json"))
    H, L = (code.HZ, code.LZ) if basis == "Z" else (code.HX, code.LX)
    cols = []
    for c in d["columns"]:
        h = np.zeros(H.shape[0], bool); h[c["H"]] = True
        l = np.zeros(L.shape[0], bool); l[c["L"]] = True
        # recompute from the support (independent of the file's H/L lists)
        v = np.zeros(code.n, np.int64); v[c["support"]] = 1
        assert ((H @ v) % 2 == h).all() and ((L @ v) % 2 == l).all()
        cols.append(h.tobytes() + l.tobytes())
    return cols


def my_groups(eff, basis):
    code = eff["code"]
    cols = ext_columns(basis, code)
    colset = set(cols)
    D, O, Hi, Li = eff["D"], eff["O"], eff["Hi"], eff["Li"]
    groups = defaultdict(dict)       # key -> {det pattern (frozenset): obs tuple}
    stats = dict(faults=eff["F"], zero_image=0, zero_image_with_obs=0, image_not_column=0, obs_ne_L=0,
                 inconsistent_obs=0, nonzero_image_no_dets=0)
    for f in range(eff["F"]):
        h, l = Hi[:, f], Li[:, f]
        o = O[:, f]
        if not (o == l).all():
            stats["obs_ne_L"] += 1
        if not h.any() and not l.any():
            stats["zero_image"] += 1
            if o.any():
                stats["zero_image_with_obs"] += 1
            continue
        key = h.tobytes() + l.tobytes()
        if key not in colset:
            stats["image_not_column"] += 1
            continue
        dp = frozenset(np.flatnonzero(D[:, f]).tolist())
        if not dp:
            stats["nonzero_image_no_dets"] += 1
        ot = tuple(np.flatnonzero(o).tolist())
        if dp in groups[key] and groups[key][dp] != ot:
            stats["inconsistent_obs"] += 1
        groups[key].setdefault(dp, ot)
    stats["columns_with_faults"] = sum(1 for k in cols if groups.get(k))
    stats["patterns"] = sum(len(v) for v in groups.values())
    return cols, groups, stats


class CNF:
    def __init__(self):
        self.n = 0
        self.cl = []

    def v(self):
        self.n += 1
        return self.n

    def xor_eq(self, lits, rhs):
        """XOR(lits) = rhs (rhs a literal or a bool) via y_k = y_{k-1} xor x_k (3-literal Tseitin)."""
        if not lits:
            if rhs is True:
                self.cl.append([])
            elif rhs is not False:
                self.cl.append([-rhs])
            return
        acc = lits[0]
        for x in lits[1:]:
            y = self.v()
            # y <-> acc xor x
            self.cl += [[-y, acc, x], [-y, -acc, -x], [y, -acc, x], [y, acc, -x]]
            acc = y
        if rhs is True:
            self.cl.append([acc])
        elif rhs is False:
            self.cl.append([-acc])
        else:
            self.cl += [[-acc, rhs], [acc, -rhs]]

    def exactly_one_binary(self, xs):
        self.cl.append(list(xs))
        k = max(1, (len(xs) - 1).bit_length())
        bits = [self.v() for _ in range(k)]
        for i, x in enumerate(xs):
            for j, b in enumerate(bits):
                self.cl.append([-x, b if (i >> j) & 1 else -b])

    def dimacs(self):
        return f"p cnf {self.n} {len(self.cl)}\n" + "".join(" ".join(map(str, c)) + " 0\n" for c in self.cl)


def my_instance(S_keys, groups, ndet, nobs, block=()):
    cnf = CNF()
    var = []                       # per group: list of (var, det pattern, obs)
    det_lits = defaultdict(list)
    obs_lits = defaultdict(list)
    for key in S_keys:
        pats = sorted(groups.get(key, {}).items(), key=lambda kv: sorted(kv[0]))
        vs = []
        for dp, ot in pats:
            x = cnf.v()
            vs.append((x, dp, ot))
            for d in dp:
                det_lits[d].append(x)
            for o in ot:
                obs_lits[o].append(x)
        if not vs:
            cnf.cl.append([])       # no fault with this image: instance trivially unsatisfiable
        else:
            cnf.exactly_one_binary([x for x, _, _ in vs])
        var.append(vs)
    for d in range(ndet):           # every detector, touched or not
        cnf.xor_eq(det_lits.get(d, []), False)
    ovars = []
    for o in range(nobs):
        t = cnf.v()
        cnf.xor_eq(obs_lits.get(o, []), t)
        ovars.append(t)
    cnf.cl.append(ovars)            # some circuit observable flips
    for sol in block:               # blocking clauses for enumeration (solution = tuple of det patterns per group)
        cl = []
        for vs, dp in zip(var, sol):
            cl += [-x for x, p, _ in vs if p == dp]
        cnf.cl.append(cl)
    return cnf, var


def solve(text):
    p = subprocess.run([CADICAL, "-q"], input=text.encode(), capture_output=True)
    model = set()
    if p.returncode == 10:
        model = {int(t) for l in p.stdout.decode().splitlines() if l.startswith("v") for t in l.split()[1:] if int(t) > 0}
    return {10: "SAT", 20: "UNSAT"}.get(p.returncode, f"err{p.returncode}"), model


def decode(var, model):
    sol = []
    for vs in var:
        ch = [dp for x, dp, _ in vs if x in model]
        assert len(ch) == 1
        sol.append(ch[0])
    return tuple(sol)


def check_lift(sol, S_keys, groups):
    acc = set()
    o = set()
    for dp, key in zip(sol, S_keys):
        assert dp in groups[key]
        acc ^= set(dp)
        o ^= set(groups[key][dp])
    return not acc and bool(o)


def enumerate_mine(S_keys, groups, ndet, nobs, cap):
    sols = []
    while len(sols) < cap:
        cnf, var = my_instance(S_keys, groups, ndet, nobs, sols)
        ans, model = solve(cnf.dimacs())
        if ans != "SAT":
            return sols, ans
        sols.append(decode(var, model))
    return sols, "CAP"


if __name__ == "__main__":
    a = sys.argv[1:]
    circ, basis, R = a[0], a[1], int(a[2])
    enum = int(a[a.index("--enum") + 1]) if "--enum" in a else 0
    rest = a[3:a.index("--enum")] if "--enum" in a else a[3:]
    idx = [int(x) for x in rest]
    eff = faults_and_effects(circ, R, basis)
    cols, groups, st = my_groups(eff, basis)
    lists = json.load(open(PKG / "data/logicals" / f"weight11_logicals_{basis}_memory.json"))["logicals"]
    out = {"circuit": circ, "basis": basis, "R": R, "dem_stats": st, "detectors": eff["ndet"], "instances": {}}
    for i in idx:
        S = [cols[j] for j in lists[i]["columns"]]
        cnf, var = my_instance(S, groups, eff["ndet"], eff["O"].shape[0])
        ans, model = solve(cnf.dimacs())
        rec = {"answer": ans, "vars": cnf.n, "clauses": len(cnf.cl)}
        if ans == "SAT":
            sol = decode(var, model)
            rec["lift_valid"] = check_lift(sol, S, groups)
        if enum:
            sols, how = enumerate_mine(S, groups, eff["ndet"], eff["O"].shape[0], enum)
            rec["enumerated"] = len(sols)
            rec["enum_end"] = how
            rec["sols_sha"] = hashlib.sha256(json.dumps(sorted([[sorted(dp) for dp in s] for s in sols])).encode()).hexdigest()
        out["instances"][i] = rec
    print(json.dumps(out))
