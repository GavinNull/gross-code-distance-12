"""Period-11 circuits (Table I) and relatives: legality, determinism, frame, symmetry, non-segmentability, extended code.

For each circuit: (i) every check applies exactly six CNOTs to its row support at distinct steps inside its window and
no data qubit takes part in two CNOTs in one step; (ii) the noiseless memory circuits (R = 1, 2, 3, 6, both bases) have
deterministic detectors and observables and fire nothing; (iii) the shared timing: all X checks have one reset step,
one measurement step and one set of CNOT steps, likewise all Z checks (printed; for u11 and c11 compared with Table I);
(iv) the translations of the torus that map every check's CNOT order to the order of the image check (72 for the
gross code, 45 for [[90,8,10]] = translation invariant); (v) the extended-code column set (both bases) equals the
family's data file (u11_extended_code_* or bb90_extended_code_*), with 5 column orbits; (vi) segmentability: the
precedence graph on check instances (R = 3), with an edge u -> v whenever on a shared data qubit a CNOT of u precedes a
CNOT of v of the other type (same-type CNOTs on a data qubit commute), has strongly connected components containing
both types iff no reordering of commuting gates separates the X and Z CNOTs of a round; printed with a witness cycle
(for u11 the 6-cycle X9 -> Z17 -> X12 -> Z20 -> X22 -> Z24 -> X9 of SM S3 is checked edge by edge).

    python code/p11/check_circuits.py u11 u11_control_p10 u11_control_segmented c11 c12 c13
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common_cli import Verdict                                  # noqa: E402
from p11 import common as C                                     # noqa: E402
from gross12.schedule import build_circuits, unroll, validate_schedule  # noqa: E402

TABLE_I = {   # (reset, CNOT steps, measurement) per type, Table I of the paper
    "u11": {"X": (0, [1, 2, 3, 4, 5, 9], 10, "A2A1A3B3B2B1"), "Z": (10, [0, 4, 5, 6, 7, 8], 9, "B1B2B3A3A1A2")},
    "c11": {"X": (0, [1, 2, 3, 4, 5, 9], 10, "B1B3B2A3A1A2"), "Z": (10, [0, 4, 5, 6, 7, 8], 9, "A2A1A3B2B3B1")},
}
TERMS = {"gross": {"A": [(3, 0), (0, 1), (0, 2)], "B": [(0, 3), (1, 0), (2, 0)]},
         "bb90": {"A": [(9, 0), (0, 1), (0, 2)], "B": [(0, 0), (2, 0), (7, 0)]}}


def label_order(fam, typ, i, order):
    """term labels (A1..B3) of the CNOT order of check i of type typ."""
    f = C.FAMILY[fam]
    l, m = f["l"], f["m"]
    a0, b0 = divmod(i, m)
    lab = {}
    for blk, (P, sgn) in ((0, ("A" if typ == "X" else "B", 1)), (1, ("B" if typ == "X" else "A", 1))):
        for k, (p, q) in enumerate(TERMS[fam][P]):
            if typ == "X":
                a, b = (a0 + p) % l, (b0 + q) % m
            else:
                a, b = (a0 - p) % l, (b0 - q) % m
            lab[blk * l * m + a * m + b] = f"{P}{k + 1}"
    return "".join(lab[q] for q in order)


def tarjan(nodes, adj):
    index, low, onst, st, out, cnt = {}, {}, set(), [], [], [0]
    for root in nodes:
        if root in index:
            continue
        work = [(root, iter(adj.get(root, ())))]
        index[root] = low[root] = cnt[0]; cnt[0] += 1; st.append(root); onst.add(root)
        while work:
            v, it = work[-1]
            nxt = next(it, None)
            if nxt is not None:
                if nxt not in index:
                    index[nxt] = low[nxt] = cnt[0]; cnt[0] += 1; st.append(nxt); onst.add(nxt)
                    work.append((nxt, iter(adj.get(nxt, ()))))
                elif nxt in onst:
                    low[v] = min(low[v], index[nxt])
                continue
            work.pop()
            if work:
                low[work[-1][0]] = min(low[work[-1][0]], low[v])
            if low[v] == index[v]:
                comp = []
                while True:
                    w = st.pop(); onst.discard(w); comp.append(w)
                    if w == v:
                        break
                out.append(comp)
    return out


names = sys.argv[1:] or ["u11", "u11_control_p10", "u11_control_segmented", "c11", "c12", "c13"]
V = Verdict()
for name in names:
    fam = C.family_of(name)
    code = C.load_code(fam)
    spec = C.circuit(name)
    P = spec.period
    pr = validate_schedule(spec, code)
    V(not pr, f"[{name}] legality: period {P}, every check 6 CNOTs on its support inside its window at distinct steps, "
              f"no data-qubit conflict ({len(pr)} problems)")
    det = []
    for R in (1, 2, 3, 6):
        for b, c in build_circuits(spec.canonical(), code, R).items():
            c.detector_error_model()
            s = c.compile_detector_sampler(seed=1).sample(64, append_observables=True)
            det.append(not s.any())
    V(all(det), f"[{name}] determinism: R = 1, 2, 3, 6 both bases: detectors/observables deterministic, noiseless "
                f"circuit fires nothing ({sum(det)}/{len(det)})")
    xo, zo = spec.orders()
    timing = {}
    for ty, chk, ords in (("X", spec.x_checks, xo), ("Z", spec.z_checks, zo)):
        tset = {(c.prep, tuple(t for t, _ in sorted((t, q) for q, t in c.cnots)), c.meas) for c in chk}
        labs = {label_order(fam, ty, i, o) for i, o in enumerate(ords)}
        timing[ty] = (tset, labs)
    uniform = all(len(t) == 1 and len(lb) == 1 for t, lb in timing.values())
    desc = "; ".join(f"{ty}: reset {next(iter(t))[0]}, CNOT steps {sorted(next(iter(t))[1])}, measurement "
                     f"{next(iter(t))[2]}, order {next(iter(lb))}" for ty, (t, lb) in timing.items()) if uniform else ""
    ok = uniform
    if uniform and name in TABLE_I:
        for ty, (rs, steps, ms, lab) in TABLE_I[name].items():
            t, lb = timing[ty]
            r0, st0, m0 = next(iter(t))
            ok &= (r0, sorted(st0), m0, next(iter(lb))) == (rs, steps, ms, lab)
    V(ok, f"[{name}] shared timing: all checks of a type share reset, CNOT steps, measurement and order: {desc}"
          + (" (= Table I)" if name in TABLE_I else ""))
    U = unroll(spec.canonical(), code, 3)
    offs = sorted({U.start[q] % P for q in U.start})
    wraps = any((c.meas - c.prep) % P < max((t - c.prep) % P for _, t in c.cnots) or c.meas < c.prep
                for c in spec.x_checks + spec.z_checks)
    V(True, f"[{name}] frame: start offsets of the unrolled circuit modulo {P}: {offs}; "
            f"{'wrapping (some window passes the period boundary)' if wraps else 'non-wrapping'}")
    G = C.order_group(spec, fam)
    ng = C.FAMILY[fam]["n_group"]
    V(len(G) == ng, f"[{name}] symmetry: {len(G)}/{ng} translations map every check order to the order of the image "
                    f"check (translation invariant)")
    for basis in "ZX":
        keys = C.ext_keys_from_file(code, fam, basis)
        kc, sups, supkey = C.ext_columns(code, basis, spec)
        kidx = {k: j for j, k in enumerate(kc)}
        perms = []
        for a, b in G:
            pq = C.translation(fam, a, b)
            perms.append([kidx[supkey[tuple(sorted(pq[q] for q in s))]] for s in sups])
        seen, orbs = set(), []
        for j in range(len(kc)):
            if j not in seen:
                o = {p[j] for p in perms}; seen |= o; orbs.append(o)
        V(set(kc) == set(keys) and len(orbs) == 5 and all(len(o) == ng for o in orbs),
          f"[{name}] extended code, {basis}-basis memory: {len(kc)} merged columns, equal to the data file "
          f"{C.FAMILY[fam]['ext'].format(b=basis)}; {len(orbs)} column orbits of size {ng}")
    # segmentability (R = 3)
    R = 3
    ev = {}
    for t, lst in U.cnots.items():
        for x, y in lst:
            an, dq = (x, y) if x in U.start else (y, x)
            j = (t - U.start[an]) // P
            ev.setdefault(dq, []).append((t, an, j))
    xa = set(range(code.n, code.n + code.HX.shape[0]))
    typ = lambda an: "X" if an in xa else "Z"  # noqa: E731
    adj, nodes = {}, set()
    for dq, lst in ev.items():
        lst.sort()
        for i1 in range(len(lst)):
            for i2 in range(i1 + 1, len(lst)):
                (t1, u, ju), (t2, v, jv) = lst[i1], lst[i2]
                if typ(u) != typ(v):
                    adj.setdefault((u, ju), set()).add((v, jv)); nodes |= {(u, ju), (v, jv)}
    comps = tarjan(sorted(nodes), adj)
    mixed = [cpt for cpt in comps if len({typ(u) for u, _ in cpt}) > 1]
    nx_ = code.HX.shape[0]
    lab = lambda node: f"{typ(node[0])}{node[0] - code.n - (0 if typ(node[0]) == 'X' else nx_)}"  # noqa: E731
    msg = (f"{len(mixed)} strongly connected components containing both types (sizes "
           f"{sorted(len(c) for c in mixed)}) => not segmentable" if mixed else
           "no component contains both types (segmentable)")
    ok = True
    if name == "u11":
        cyc = ["X9", "Z17", "X12", "Z20", "X22", "Z24", "X9"]
        an = lambda s: code.n + int(s[1:]) + (0 if s[0] == "X" else nx_)  # noqa: E731
        ok = bool(mixed) and all(any((an(b), j) in adj.get((an(a), j), ()) for j in range(R))
                                 for a, b in zip(cyc, cyc[1:]))
        msg += "; the 6-cycle X9 -> Z17 -> X12 -> Z20 -> X22 -> Z24 -> X9 is present (edges within one round)"
    if name in ("u11", "c11", "u11_control_segmented"):
        ok &= bool(mixed) == (name != "u11_control_segmented")
    V(ok, f"[{name}] segmentability (R = {R}, {len(nodes)} instances): {msg}")
V.exit()
