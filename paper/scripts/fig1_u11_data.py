"""Data for Fig. 1 (u11): non-segmentability witness, one weight-10 extended logical lifting in the segmented control
and blocked in u11, and the proof-chain numbers for u11 (gross) and c11 ([[90,8,10]]).

  uv run python paper/scripts/fig1_u11_data.py          -> paper/figures/fig1_u11_data.json   (single process)

Everything circuit-level is recomputed here through the evaluator's PUBLIC entry points (build_code, parse_schedule,
validate_schedule, build_circuits, add_noise, unroll, check_l0) plus own code (extended code, lift, MUS, injection).
Read-only data: search/experiments/e032/u11_spec.json; results/E-032-audit/segctl_spec.json (compared with the
control built here); results/E-032-audit/lists_u11_spec_{Z,X}.pkl (auditor's complete weight-10/11 lists, keyed by
(H e, L e) with the evaluator's L; key set asserted equal to the extended code computed here).
Setting for (b): Z-basis memory (X errors, residuals of X checks), R = 1 and R = 2, SD6 noise at the evaluator's p.
"""
from __future__ import annotations

import collections
import json
import os
import pickle
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT)]
os.chdir(ROOT)

import numpy as np  # noqa: E402
import stim  # noqa: E402
from ortools.sat.python import cp_model  # noqa: E402

from evaluators.candidate import build_circuits, parse_schedule, unroll, validate_schedule  # noqa: E402
from evaluators.l0 import check_l0  # noqa: E402
from evaluators.noise import add_noise  # noqa: E402
from evaluators.tasks import build_code, get_task  # noqa: E402

U11 = "search/experiments/e032/u11_spec.json"
SEG_AUDIT = "results/E-032-audit/segctl_spec.json"
OUT = ROOT / "paper/figures/fig1_u11_data.json"
NOISE = {"DEPOLARIZE1", "DEPOLARIZE2", "X_ERROR", "Y_ERROR", "Z_ERROR", "PAULI_CHANNEL_1", "PAULI_CHANNEL_2"}
CODE, _ = build_code(get_task("gross-dcirc"), None)
HX, HZ, LX, LZ = [np.asarray(m, np.uint8) % 2 for m in (CODE.HX, CODE.HZ, CODE.LX, CODE.LZ)]
N, NC = 144, 72


def fail(msg):
    raise SystemExit(f"AUDIT MISMATCH: {msg}")


def lab_x(i):
    """term labels of X check i (A1=x^3, A2=y, A3=y^2 on L; B1=y^3, B2=x, B3=x^2 on R), conventions of the audit."""
    x, y = divmod(i, 6)
    A = [("A1", (3, 0)), ("A2", (0, 1)), ("A3", (0, 2))]
    B = [("B1", (0, 3)), ("B2", (1, 0)), ("B3", (2, 0))]
    out = {}
    for n, (dx, dy) in A:
        out[((x + dx) % 12) * 6 + (y + dy) % 6] = n
    for n, (dx, dy) in B:
        out[72 + ((x + dx) % 12) * 6 + (y + dy) % 6] = n
    return out


def lab_z(i):
    x, y = divmod(i, 6)
    A = [("A1", (3, 0)), ("A2", (0, 1)), ("A3", (0, 2))]
    B = [("B1", (0, 3)), ("B2", (1, 0)), ("B3", (2, 0))]
    out = {}
    for n, (dx, dy) in B:
        out[((x - dx) % 12) * 6 + (y - dy) % 6] = n
    for n, (dx, dy) in A:
        out[72 + ((x - dx) % 12) * 6 + (y - dy) % 6] = n
    return out


def order(c, P):
    return [a for _, a in sorted(((t - c["prep"]) % P, a) for a, t in c["cnots"])]


# ------------------------------------------------------------------ circuits
def build_segctl(u):
    """same per-check CNOT orders as u11; X block at steps 1..6 (prep 0, meas 7), Z block at 8..13 (prep 7, meas 14)."""
    P = u["period"]
    xs = [{"prep": 0, "meas": 7, "cnots": [[a, 1 + k] for k, a in enumerate(order(c, P))]} for c in u["x_checks"]]
    zs = [{"prep": 7, "meas": 14, "cnots": [[a, 8 + k] for k, a in enumerate(order(c, P))]} for c in u["z_checks"]]
    return {"format": "qec-schedule/v1", "period": 15, "x_checks": xs, "z_checks": zs}


def same_spec(a, b):
    nz = lambda d: (d["period"], [(c["prep"], c["meas"], sorted(map(tuple, c["cnots"]))) for c in d["x_checks"]],  # noqa
                    [(c["prep"], c["meas"], sorted(map(tuple, c["cnots"]))) for c in d["z_checks"]])
    return nz(a) == nz(b)


def legal_deterministic(d):
    spec = parse_schedule(d)
    probs = validate_schedule(spec, CODE)
    out = {"validate_problems": len(probs)}
    for R in (1, 3):
        for b, circ in build_circuits(spec.canonical(), CODE, R).items():
            rep = check_l0(circ, CODE, b)
            out[f"L0_R{R}_{b}"] = bool(getattr(rep, "passed", False))
            circ.detector_error_model()          # raises on non-deterministic detectors
            s = circ.compile_detector_sampler().sample(16, separate_observables=True)
            out[f"noiseless_zero_R{R}_{b}"] = bool(not s[0].any() and not s[1].any())
    return out


def ext_keys(d, basis):
    """own extended code: data columns + proper suffixes (cyclic order from prep) of the other-type checks."""
    H, L, hooks = (HZ, LZ, d["x_checks"]) if basis == "Z" else (HX, LX, d["z_checks"])
    P = d["period"]
    sups = [(j,) for j in range(N)] + [tuple(sorted(order(c, P)[k:])) for c in hooks for k in range(1, 6)]
    keys = {}
    for s in sups:
        v = np.zeros(N, np.uint8)
        v[list(s)] = 1
        hb, lb = (H @ v) % 2, (L @ v) % 2
        if hb.any() or lb.any():
            keys.setdefault(hb.tobytes() + lb.tobytes(), s)
    return keys


def build(d, R, basis):
    spec = parse_schedule(d).canonical()
    c = add_noise(build_circuits(spec, CODE, R)[basis], "sd6", 1e-3).flattened()
    H, L = (HZ, LZ) if basis == "Z" else (HX, LX)
    k0, nH = c.num_observables, H.shape[0]
    aug = c.copy()
    for r, row in enumerate(list(H) + list(L)):
        aug.append("OBSERVABLE_INCLUDE", [stim.target_rec(q - N) for q in np.nonzero(row)[0]], k0 + r)
    dem = aug.detector_error_model(decompose_errors=False, approximate_disjoint_errors=True)
    groups, zeros = {}, []
    for inst in dem.flattened():
        if inst.type != "error":
            continue
        dets, hb, lb, ob = set(), np.zeros(nH, np.uint8), np.zeros(L.shape[0], np.uint8), np.zeros(k0, np.uint8)
        for t in inst.targets_copy():
            if t.is_relative_detector_id():
                dets ^= {t.val}
            elif t.is_logical_observable_id():
                v = t.val
                if v < k0:
                    ob[v] ^= 1
                elif v < k0 + nH:
                    hb[v - k0] ^= 1
                else:
                    lb[v - k0 - nH] ^= 1
        if not (ob == lb).all():
            fail("circuit observable != image L part")
        key = hb.tobytes() + lb.tobytes()
        if hb.any() or lb.any():
            groups.setdefault(key, []).append((frozenset(dets), inst))
        elif dets:
            zeros.append((frozenset(dets), inst))
    return spec, c, aug, dem, groups, zeros


def solve(S, groups, zeros=None, active=None):
    """one term per column (and exactly one zero-image term if zeros is given); detector XOR = 0 on `active`."""
    M = cp_model.CpModel()
    lits, choice = {}, {}
    sets = [groups[k] for k in S] + ([zeros] if zeros is not None else [])
    for gi, g in enumerate(sets):
        vs = []
        for j, (dets, _) in enumerate(g):
            v = M.NewBoolVar("")
            vs.append(v)
            choice[(gi, j)] = v
            for x in dets:
                lits.setdefault(x, []).append(v)
        M.AddExactlyOne(vs)
    one = M.NewConstant(1)
    for x, ls in lits.items():
        if active is None or x in active:
            M.AddBoolXOr(ls + [one])
    s = cp_model.CpSolver()
    s.parameters.num_workers = 1
    s.parameters.random_seed = 7
    st = s.Solve(M)
    ok = st in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    pick = [sets[gi][j] for (gi, j), v in choice.items() if ok and s.Value(v)]
    return ok, pick, sorted(lits)


def mus(S, groups, zeros=None):
    ok, _, act = solve(S, groups, zeros)
    if ok:
        fail("expected no lift")
    i = 0
    while i < len(act):
        trial = act[:i] + act[i + 1:]
        if not solve(S, groups, zeros, set(trial))[0]:
            act = trial
        else:
            i += 1
    return act


def locate(aug, terms):
    sub = stim.DetectorErrorModel()
    for _, inst in terms:
        sub.append(inst)
    out = []
    for e in aug.explain_detector_error_model_errors(dem_filter=sub, reduce_to_one_representative_error=True):
        loc = e.circuit_error_locations[0]
        ps = [(p.gate_target.pauli_type, p.gate_target.value) for p in loc.flipped_pauli_product]
        if not ps:
            fail("bare measurement flip in witness (injection not implemented)")
        out.append(dict(tick=loc.tick_offset, op=loc.stack_frames[0].instruction_offset, paulis=ps,
                        gate=loc.instruction_targets.gate))
    return out


def inject(c, locs):
    by = collections.defaultdict(list)
    for L in locs:
        by[L["op"]].append(L)
    new = stim.Circuit()
    for i, op in enumerate(c):
        if op.name in NOISE:
            for L in by.get(i, []):
                for p, q in L["paulis"]:
                    new.append(f"{p}_ERROR", [q], 1.0)
            continue
        new.append(op)
    d, o = new.compile_detector_sampler().sample(1, separate_observables=True)
    return int(d.sum()), [int(x) for x in np.nonzero(o[0])[0]]


def gate_ticks(c):
    """(Z row, data q) -> ticks of CX(q -> Z anc); (X row, q) -> ticks of CX(X anc -> q); Z/X meas ticks per row."""
    tick, zr, xr, zm, xm = 0, collections.defaultdict(list), collections.defaultdict(list), \
        collections.defaultdict(list), collections.defaultdict(list)
    for op in c:
        if op.name == "TICK":
            tick += 1
            continue
        t = op.targets_copy()
        if op.name in ("CX", "CNOT"):
            for a, b in zip(t[::2], t[1::2]):
                a, b = a.value, b.value
                if b >= N + NC:
                    zr[(b - N - NC, a)].append(tick)
                elif N <= a < N + NC:
                    xr[(a - N, b)].append(tick)
        elif op.name in ("M", "MR"):
            for q in t:
                if q.value >= N + NC:
                    zm[q.value - N - NC].append(tick)
        elif op.name in ("MX", "MRX"):
            for q in t:
                if N <= q.value < N + NC:
                    xm[q.value - N].append(tick)
    return zr, xr, zm, xm


# ------------------------------------------------------------------ (a)
def panel_a(u):
    P = u["period"]
    spec = parse_schedule(u)
    if validate_schedule(spec, CODE):
        fail("u11 not legal")
    sig_x = {(c["prep"], c["meas"], tuple((lab_x(i)[a], t) for a, t in sorted(c["cnots"], key=lambda e: (e[1] - c["prep"]) % P)))
             for i, c in enumerate(u["x_checks"])}
    sig_z = {(c["prep"], c["meas"], tuple((lab_z(i)[a], t) for a, t in sorted(c["cnots"], key=lambda e: (e[1] - c["prep"]) % P)))
             for i, c in enumerate(u["z_checks"])}
    if len(sig_x) != 1 or len(sig_z) != 1:
        fail("u11 not translation invariant (one signature per type)")
    # cyclic sequence of each data qubit
    seqs = collections.Counter()
    per_q = {}
    for q in range(N):
        ev = sorted([(t, "X") for c in u["x_checks"] for a, t in c["cnots"] if a == q]
                    + [(t, "Z") for c in u["z_checks"] for a, t in c["cnots"] if a == q])
        per_q[q] = ev
        seqs[tuple((t, ty) for t, ty in ev)] += 1
    if len(seqs) != 2 or sorted(seqs.values()) != [72, 72]:
        fail(f"data-qubit sequences: {len(seqs)} kinds")
    for sq in seqs:
        s = [ty for _, ty in sq]
        sw = sum(s[i] != s[i - 1] for i in range(6))
        if sw != 2 or sorted(s) != ["X"] * 3 + ["Z"] * 3:
            fail("each data qubit: XXX then ZZZ cyclically (2 switches)")
    # own unroll (evaluator public `unroll`), R = 3; instance precedence edges on shared data qubits
    R = 3
    un = unroll(spec.canonical(), CODE, R)
    inst_of = {}
    xq0, zq0 = N, N + NC
    for t, lst in un.cnots.items():
        for a, b in lst:
            if a >= xq0 and a < zq0:          # X anc -> data
                inst_of.setdefault(("X", a - xq0), []).append((t, b))
            else:                               # data -> Z anc
                inst_of.setdefault(("Z", b - zq0), []).append((t, a))
    starts = {}
    for q, s in un.start.items():
        k = ("X", q - xq0) if q < zq0 else ("Z", q - zq0)
        starts[k] = s

    def instances(k):
        """round j -> (reset tick, [(tick, data)], meas tick)"""
        D = u["period"]
        cks = u["x_checks"] if k[0] == "X" else u["z_checks"]
        c = cks[k[1]]
        dm = (c["meas"] - c["prep"]) % D
        out = {}
        for j in range(R):
            s = starts[k] + D * j
            out[j] = (s, sorted((tt, a) for tt, a in inst_of[k] if s < tt < s + dm), s + dm)
        return out

    cyc = [("X", 9), ("Z", 17), ("X", 12), ("Z", 20), ("X", 22), ("Z", 24)]
    j = 1
    edges = []
    for u_, v_ in zip(cyc, cyc[1:] + cyc[:1]):
        iu, iv = instances(u_)[j], instances(v_)[j]
        shared = sorted({a for _, a in iu[1]} & {a for _, a in iv[1]})
        prec = [(a, tu, tv) for a in shared for tu, aa in iu[1] if aa == a for tv, bb in iv[1] if bb == a and tu < tv]
        if not prec:
            fail(f"cycle edge {u_}->{v_} (round {j}) has no precedence")
        edges.append(dict(u=list(u_), v=list(v_), qubit=prec[0][0], t_u=prec[0][1], t_v=prec[0][2]))
    inst = {f"{k[0]}{k[1]}": dict(reset=instances(k)[j][0], cnots=instances(k)[j][1], meas=instances(k)[j][2],
                                    next_reset=instances(k)[j][0] + P) for k in cyc}
    # straddle: some Z instance on the cycle has CNOTs both before and after a CNOT of the NEXT round's ... keep facts
    xs = next(iter(sig_x))
    zs = next(iter(sig_z))
    return dict(period=P, x_signature=dict(prep=xs[0], meas=xs[1], cnots=[list(e) for e in xs[2]]),
                z_signature=dict(prep=zs[0], meas=zs[1], cnots=[list(e) for e in zs[2]]),
                data_sequences=[[list(e) for e in sq] for sq in seqs], cycle=[f"{a}{b}" for a, b in cyc],
                cycle_round=j, edges=edges, instances=inst, R_unroll=R, sigma=un.sigma)


# ------------------------------------------------------------------ (b)
def panel_b(u, seg):
    basis = "Z"
    ku, ks = ext_keys(u, basis), ext_keys(seg, basis)
    if set(ku) != set(ks):
        fail("segmented control must have the same extended code")
    lp = pickle.load(open(ROOT / "results/E-032-audit/lists_u11_spec_Z.pkl", "rb"))
    if set(lp["cols"]) != set(ku) or len(lp["cols"]) != 360:
        fail("auditor list columns != own extended code (360)")
    L10 = [[lp["cols"][j] for j in S] for S in lp["sets"][10]]
    if len(L10) != 144 or len(lp["sets"][11]) != 7344:
        fail("lists 144 / 7344")
    res = {"n_w10": len(L10)}
    out_R = {}
    for R in (1, 2):
        _, cs, augs, dems, gs, zs = build(seg, R, basis)
        _, cu, augu, demu, gu, zu = build(u, R, basis)
        if set(gs) != set(ku) or set(gu) != set(ku):
            fail("Table I: realised images != extended columns")
        out_R[R] = (cs, augs, dems, gs, zs, cu, augu, demu, gu, zu)
    # choose the first weight-10 logical in the list that lifts in seg at R = 1 (all should)
    cs, augs, dems, gs, zs, cu, augu, demu, gu, zu = out_R[1]
    S = L10[0]
    ok, pick, _ = solve(S, gs)
    if not ok:
        fail("segmented control must lift the weight-10 logical")
    locs = locate(augs, pick)
    nd, fl = inject(cs, locs)
    if nd or not fl:
        fail(f"segctl injection: {nd} detectors, observables {fl}")
    if solve(S, gu)[0]:
        fail("u11 must not lift (audit: 0 for R = 1..31)")
    core = mus(S, gu)
    coords = demu.get_detector_coordinates()
    core_info = [dict(det=x, zcheck=int(coords[x][0]), round=int(coords[x][1])) for x in core]
    # columns of S: support and kind
    cols = []
    for key in S:
        sup = ku[key]
        cols.append(dict(support=list(sup), data=len(sup) == 1))
    # which DEM terms of each column touch the core detectors, in u11
    sig = []
    for key in S:
        sig.append(sorted(collections.Counter(tuple(int(x in dets) for x in core) for dets, _ in gu[key]).items()))
    zrU, xrU, zmU, xmU = gate_ticks(cu)
    zrS, xrS, zmS, xmS = gate_ticks(cs)
    core_checks = sorted({ci["zcheck"] for ci in core_info})
    allq = sorted({q for key in S for q in ku[key]})
    reads = {str(r): {str(q): dict(u11=zrU[(r, q)], seg=zrS[(r, q)]) for q in allq if HZ[r, q]} for r in core_checks}
    meas = {str(r): dict(u11=zmU[r], seg=zmS[r]) for r in core_checks}
    # residual columns: realisation in u11 (fault tick, X anc, deposit ticks)
    hooks = []
    for key in S:
        if len(ku[key]) > 1:
            for dets, inst in gu[key]:
                L = locate(augu, [(dets, inst)])[0]
                anc = [q - N for _, q in L["paulis"] if N <= q < N + NC]
                hooks.append(dict(support=list(ku[key]), fault_tick=L["tick"], paulis=L["paulis"],
                                  xcheck=anc, deposits={str(q): xrU[(anc[0], q)] for q in order(u["x_checks"][anc[0]], u["period"])}
                                  if anc else None, core_sig=[int(x in dets) for x in core]))
    # mechanism check for this logical: a single forced detector of one Z check that touches exactly one qubit q
    # of the logical; q lies in exactly two residual columns, deposited on opposite sides of that check's read
    ucore = core_info
    mech = None
    if len(ucore) == 1:
        r = ucore[0]["zcheck"]
        touched = [q for q in allq if HZ[r, q]]
        if len(touched) != 1:
            fail("forced check touches more than one qubit of the logical")
        q = touched[0]
        holders = [h for h in hooks if q in h["support"]]
        if len(holders) != 2 or any(len(gu[k]) != 1 for k in S if q in ku[k]):
            fail("qubit must lie in exactly two single-term residual columns")
        if any(q in ku[k] for k in S if len(ku[k]) == 1):
            fail("no data column on that qubit")
        rd = zrU[(r, q)][0]
        dep = sorted(h["deposits"][str(q)][0] for h in holders)
        if not (dep[0] < rd < dep[1]):
            fail("deposits must straddle the read in u11")
        segdep = sorted(xrS[(h["xcheck"][0], q)][0] for h in holders)
        rds = zrS[(r, q)][0]
        if not (segdep[1] < rds):
            fail("in the segmented control both deposits precede the read")
        segfault = {}
        for L in locs:
            for _, qq in L["paulis"]:
                if N <= qq < N + NC:
                    segfault[qq - N] = L["tick"]
        mech = dict(zcheck=r, qubit=q, xchecks=[h["xcheck"][0] for h in holders],
                    u11=dict(read=rd, meas=zmU[r][0], deposits={str(h["xcheck"][0]): h["deposits"][str(q)][0] for h in holders},
                             faults={str(h["xcheck"][0]): h["fault_tick"] for h in holders}),
                    seg=dict(read=rds, meas=zmS[r][0], deposits={str(h["xcheck"][0]): xrS[(h["xcheck"][0], q)][0] for h in holders},
                             faults={str(h["xcheck"][0]): segfault.get(h["xcheck"][0]) for h in holders}))
    res["mechanism"] = mech
    res.update(S_supports=[list(ku[k]) for k in S], columns=cols, seg_witness=locs, seg_injected_detectors=nd,
               seg_injected_observables=fl, u11_core=core_info, u11_core_sig=sig, reads=reads, meas=meas,
               u11_hook_terms=hooks)
    # all 144 at R = 1: lift in seg / none in u11; core sizes in u11
    sizes = collections.Counter()
    nseg = 0
    straddle = collections.Counter()
    for T in L10:
        nseg += solve(T, gs)[0]
        co = mus(T, gu)
        sizes[len(co)] += 1
        if len(co) != 1:
            continue
        r = int(coords[co[0]][0])
        tq = sorted({q for k in T for q in ku[k] if HZ[r, q]})
        ks = [k for k in T if any(HZ[r, q] for q in ku[k])]
        if any(len(ku[k]) == 1 or len(gu[k]) != 1 for k in ks):
            continue
        sides = []
        for k in ks:
            a = locate(augu, gu[k])[0]["paulis"][0][1] - N
            for q in ku[k]:
                if HZ[r, q]:
                    sides.append(xrU[(a, q)][0] > zrU[(r, q)][0])
        if len(sides) == 2 and sides[0] != sides[1]:
            straddle["same qubit" if len(tq) == 1 else "two qubits"] += 1
    res["u11_core1_straddle"] = dict(straddle)
    if nseg != 144:
        fail(f"segctl lifts all 144 weight-10 at R = 1 (audit), got {nseg}")
    res["seg_lifts_w10_R1"] = nseg
    res["u11_core_sizes_R1"] = dict(sorted(sizes.items()))
    # weight-10 + one zero-image term (readout flip), same logical
    zero_ok = [all(len(d) == 2 and abs(sorted(d)[1] - sorted(d)[0]) == NC for d, _ in z_) for z_ in (zs, zu)]
    okz, pickz, _ = solve(S, gs, zs)
    res["w10z"] = dict(seg_lifts=bool(okz), u11_lifts=bool(solve(S, gu, zu)[0]),
                       zero_terms_seg=len(zs), zero_terms_u11=len(zu), all_readout_flip_pattern=zero_ok)
    if okz:
        res["w10z"]["seg_readout_term"] = sorted(pickz[-1][0])
    if res["w10z"]["u11_lifts"]:
        fail("u11 w10z lift (audit: 0)")
    # R = 2 check of the same statements
    cs2, augs2, dems2, gs2, zs2, cu2, augu2, demu2, gu2, zu2 = out_R[2]
    res["R2"] = dict(seg_lifts=bool(solve(S, gs2)[0]), u11_lifts=bool(solve(S, gu2)[0]),
                     u11_core=[dict(det=x, zcheck=int(demu2.get_detector_coordinates()[x][0]),
                                    round=int(demu2.get_detector_coordinates()[x][1])) for x in mus(S, gu2)])
    if not res["R2"]["seg_lifts"] or res["R2"]["u11_lifts"]:
        fail("R = 2 outcome")
    return res


def main():
    u = json.loads((ROOT / U11).read_text())
    seg = build_segctl(u)
    seg_a = json.loads((ROOT / SEG_AUDIT).read_text())
    res = {"segctl_equals_audit": same_spec(seg, seg_a)}
    if not res["segctl_equals_audit"]:
        fail("segmented control built here differs from the auditor's segctl_spec.json")
    res["segctl_checks"] = legal_deterministic(seg)
    res["u11_checks"] = legal_deterministic(u)
    for k, v in list(res["segctl_checks"].items()) + list(res["u11_checks"].items()):
        if (k == "validate_problems" and v) or (k != "validate_problems" and not v):
            fail(f"legality/determinism {k} = {v}")
    res["a"] = panel_a(u)
    res["b"] = panel_b(u, seg)
    OUT.write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(res, indent=1, default=str)[:6000])


if __name__ == "__main__":
    main()
