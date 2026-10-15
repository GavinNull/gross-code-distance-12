"""A5: own lift (own encoder, own extended code, own complete lists from a4, per-S SAT instead of frontier DP).
For each R, basis:
  - DEM of the own circuit augmented with "image" observables (rows of H and of L on the final data readout); each
    augmented term = (detector mask, image key).
  - Table I: every image key is 0 or a column of the own extended code (assert); every column realised.
  - zero-image terms with detectors: classified (single ancilla readout flip pattern {(c,j),(c,j+1)}?).
  - count S in the weight-8 list that lift (one term per column, XOR of detectors = 0) [case w8];
    S in the weight-8 list + one zero-image term [case w8z]; S in the weight-9 list [case w9].
Usage: a5_lift.py SPEC BASIS R1 R2 ...  [--count] (default: stop at first hit per category)"""
import sys, json, time, pickle
sys.path.insert(0, "research/audits/2026-10-15-E-028-scripts")
import numpy as np, stim
from alib import *
from pysat.card import CardEnc, EncType
from pysat.solvers import Solver

HX, HZ, LX, LZ = code_with_logicals()

def augmented_terms(spec, basis, R):
    circ = memory_circuit(spec, basis, R)
    H, Lg = (HZ, LZ) if basis == "Z" else (HX, LX)
    nm = circ.num_measurements
    k0 = circ.num_observables
    aug = circ.copy()
    # data readout = last N measurements, data q at nm - N + q
    rows = list(H) + list(Lg)
    for r_i, row in enumerate(rows):
        aug.append("OBSERVABLE_INCLUDE", [stim.target_rec(int(q) - N) for q in np.nonzero(row)[0]], k0 + r_i)
    dem = aug.detector_error_model(decompose_errors=False, approximate_disjoint_errors=True)
    nH = H.shape[0]
    terms = []
    for inst in dem.flattened():
        if inst.type != "error":
            continue
        d = set(); o = set()
        for t in inst.targets_copy():
            if t.is_relative_detector_id(): d ^= {t.val}
            elif t.is_logical_observable_id(): o ^= {t.val}
        ob = frozenset(x for x in o if x < k0)
        hb = tuple(int(k0 + r in o) for r in range(nH))
        lb = tuple(int(k0 + nH + r in o) for r in range(Lg.shape[0]))
        # own observables == L part of image
        assert ob == frozenset(k for k in range(Lg.shape[0]) if lb[k])
        terms.append((frozenset(d), (hb, lb)))
    return terms, dem.num_detectors

def lifts(groups_list, nd, extra=None):
    """SAT: one term from each group (exactly one), optional group 'extra' (at most one), XOR of detectors = 0."""
    var = 0; cls = []; det_of = {}
    for gi, g in enumerate(groups_list + ([extra] if extra else [])):
        vs = []
        for d in g:
            var += 1; vs.append(var)
            for x in d: det_of.setdefault(x, []).append(var)
        if extra is not None and gi == len(groups_list):
            cls += CardEnc.atmost(vs, 1, top_id=10**7).clauses if len(vs) > 1 else []
        else:
            cls.append(vs)
            for i in range(len(vs)):
                for j in range(i + 1, len(vs)):
                    cls.append([-vs[i], -vs[j]])
    top = var
    for x, vs in det_of.items():
        cur = vs[0]
        for v in vs[1:]:
            top += 1; y = top
            cls += [[-cur, -v, -y], [cur, v, -y], [cur, -v, y], [-cur, v, y]]
            cur = y
        cls.append([-cur])
    # remap atmost aux ids (10**7+) to avoid clashes
    mp = {}
    def fix(l):
        a = abs(l)
        if a > 10**7:
            if a not in mp:
                nonlocal top
                top += 1; mp[a] = top
            return mp[a] if l > 0 else -mp[a]
        return l
    cls = [[fix(l) for l in c] for c in cls]
    with Solver(name="cd15", bootstrap_with=cls) as s:
        return s.solve()

if __name__ == "__main__":
    a = sys.argv[1:]
    count = "--count" in a
    a = [x for x in a if x != "--count"]
    spec_path, basis = a[0], a[1]
    spec = load_spec(spec_path)
    tag = spec_path.split("/")[-1][:3]
    kind = "X" if basis == "Z" else "Z"
    E = pickle.load(open(f"results/E-028-audit/ext_{tag}_{kind}.pkl", "rb"))
    keys = E["keys"]; kidx = {k: j for j, k in enumerate(keys)}
    for R in map(int, a[2:]):
        t0 = time.time()
        terms, nd = augmented_terms(spec, basis, R)
        groups = {j: set() for j in range(len(keys))}
        zeros = set(); nzero_nodet = 0
        for d, img in terms:
            if not any(img[0]) and not any(img[1]):
                if d: zeros.add(d)
                else: nzero_nodet += 1
                continue
            assert img in kidx, "Table I violated"
            groups[kidx[img]].add(d)
        assert all(groups.values()), "unrealised column"
        # classify zero-image terms
        def is_readout(d):
            if len(d) != 2: return False
            x, y = sorted(d)
            return y - x == N2
        zr = sum(1 for d in zeros if is_readout(d))
        out = {"spec": spec_path, "basis": basis, "R": R, "terms": len(terms), "cols": len(keys),
               "zero_terms_with_dets": len(zeros), "zero_readout_pattern": zr, "w8": 0, "w8z": 0, "w9": 0}
        G = {j: list(g) for j, g in groups.items()}
        for cat, lst in (("w8", E["s8"]), ("w8z", E["s8"]), ("w9", E["s9"])):
            for S in lst:
                gl = [G[j] for j in S]
                if cat == "w8z":
                    supp = set().union(*[set().union(*g) for g in gl])
                    ex = [z for z in zeros if z <= supp]
                    if not ex: continue
                    hit = lifts(gl, nd, ex)
                else:
                    hit = lifts(gl, nd)
                if hit:
                    out[cat] += 1
                    if not count: break
        out["sec"] = round(time.time() - t0, 1)
        print(json.dumps(out), flush=True)
        with open("results/E-028-audit/a5_lift.jsonl", "a") as f:
            f.write(json.dumps(out) + "\n")
