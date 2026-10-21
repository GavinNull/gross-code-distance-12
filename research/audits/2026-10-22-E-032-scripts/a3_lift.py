"""A3: own exact lift (own encoder + own image observables + own lists from a2 + per-S SAT).
For each R, basis:
  - DEM of the own circuit with "image" observables (rows of H and of L on the final data readout); each term =
    (detector mask, image key).  Circuit observables (evaluator L) must equal the image's L part.
  - Table I: every non-zero image key is a column of the own extended code; every column is realised.
  - telescoping: for every term and check c, XOR over rounds of detectors (c, j) = bit c of the image's H part.
  - zero-image terms: all of them, classified (readout-flip pattern {(c,j),(c,j+1)} or other).
  - count S in the weight-10 list that lift (one term per column, detector XOR = 0)          [w10]
          S in the weight-10 list + exactly one zero-image term                                [w10z]
          S in the weight-11 list                                                              [w11]
Usage: a3_lift.py SPEC BASIS LISTSPEC R1 R2 ...   (LISTSPEC: spec whose a2 lists to use, keys must match)"""
import sys, json, time, pickle, collections
sys.path.insert(0, "research/audits/2026-10-22-E-032-scripts")
import numpy as np, stim
from pysat.solvers import Solver
from alib32 import *
from extcode import ext_code

spec_path, basis, list_spec = sys.argv[1], sys.argv[2], sys.argv[3]
Rs = [int(x) for x in sys.argv[4:]]
spec = load_spec(spec_path)
from evaluators.tasks import build_code, get_task
ec, _ = build_code(get_task("gross-dcirc"), None)
EL = ((np.asarray(ec.LZ) if basis == "Z" else np.asarray(ec.LX)) % 2).astype(np.uint8)
E = ext_code(spec, basis, Lover=EL)
kidx = {k: j for j, k in enumerate(E["cols"])}
ltag = list_spec.split("/")[-1].split(".")[0] + "_" + basis
LP = pickle.load(open(f"results/E-032-audit/lists_{ltag}.pkl", "rb"))
assert set(LP["cols"]) == set(E["cols"]), "extended code differs from the list's"
lists = {w: [[kidx[LP["cols"][j]] for j in S] for S in LP["sets"][w]] for w in (10, 11)}
HX, HZ, _, _ = code()
H = HZ if basis == "Z" else HX
nH, k = H.shape[0], EL.shape[0]


def terms_for(R):
    circ = memory_circuit(spec, basis, R, image_obs=True, Lover=EL)
    t, nd, no = dem_terms(circ)
    assert no == 2 * k + nH
    out = []
    for d, o in t:
        ob = o & ((1 << k) - 1)
        hb = bytes(((o >> (k + r)) & 1) for r in range(nH))
        lb = bytes(((o >> (k + nH + r)) & 1) for r in range(k))
        assert ob == sum(lb[i] << i for i in range(k)), "circuit observable != image L part"
        out.append((d, hb + lb, hb))
    return out, nd


def lift_sat(groups, extra=None):
    """exactly one term from each group (lists of detector masks), and if extra is given exactly one from extra;
    XOR of chosen detector masks = 0."""
    gl = groups + ([extra] if extra is not None else [])
    var = 0; cls = []; det_of = collections.defaultdict(list)
    for g in gl:
        vs = []
        for d in g:
            var += 1; vs.append(var)
            x = d
            while x:
                b = x & -x; det_of[b.bit_length() - 1].append(var); x ^= b
        cls.append(vs)
        for i in range(len(vs)):
            for j in range(i + 1, len(vs)):
                cls.append([-vs[i], -vs[j]])
    top = var
    for _, vs in det_of.items():
        cur = vs[0]
        for v in vs[1:]:
            top += 1; y = top
            cls += [[-cur, -v, -y], [cur, v, -y], [-cur, v, y], [cur, -v, y]]   # y <-> cur xor v
            cur = y
        cls.append([-cur])
    with Solver(name="cd15", bootstrap_with=cls) as s:
        return s.solve()


tag = spec_path.split("/")[-1].split(".")[0]
for R in Rs:
    t0 = time.time()
    terms, nd = terms_for(R)
    zero_key = bytes(nH + k)
    groups = collections.defaultdict(list); zeros = []; nz_nodet = 0; tele_bad = 0
    for d, key, hb in terms:
        # telescoping: per check c, XOR_j det(c, j) == hb[c]   (detector index j*N2 + c, j = 0..R)
        for c in range(nH):
            par = 0
            for j in range(R + 1):
                par ^= (d >> (j * N2 + c)) & 1
            if par != hb[c]:
                tele_bad += 1
        if key == zero_key:
            if d:
                zeros.append(d)
            else:
                nz_nodet += 1
            continue
        assert key in kidx, "Table I violated: image is not an extended column"
        groups[kidx[key]].append(d)
    assert len(groups) == len(E["cols"]), "unrealised column"
    def readout(d):
        if bin(d).count("1") != 2:
            return False
        a = (d & -d).bit_length() - 1; b = d.bit_length() - 1
        return b - a == N2
    zr = sum(1 for d in zeros if readout(d))
    out = {"spec": spec_path, "basis": basis, "R": R, "terms": len(terms), "cols": len(E["cols"]),
           "telescoping_violations": tele_bad, "zero_image_terms_with_dets": len(zeros),
           "zero_image_readout_pattern": zr, "zero_image_without_dets": nz_nodet,
           "max_group": max(len(g) for g in groups.values()), "w10": 0, "w10z": 0, "w11": 0}
    for cat, lst in (("w10", lists[10]), ("w10z", lists[10]), ("w11", lists[11])):
        for S in lst:
            gl = [groups[j] for j in S]
            if cat == "w10z":
                supp = 0
                for g in gl:
                    for d in g:
                        supp |= d
                ex = [z for z in zeros if z & ~supp == 0]
                if not ex:
                    continue
                hit = lift_sat(gl, ex)
            else:
                hit = lift_sat(gl)
            out[cat] += bool(hit)
    out["sec"] = round(time.time() - t0, 1)
    print(json.dumps(out), flush=True)
    with open(f"results/E-032-audit/a3_lift_{tag}_{basis}.jsonl", "a") as f:
        f.write(json.dumps(out) + "\n")
