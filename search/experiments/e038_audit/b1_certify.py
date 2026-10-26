"""E-038 audit, claims 1-2: legality, correct stabiliser measurement, exact d_circ of the N8 / full-N7 specs with my
own circuit + my own exact search; positive controls (Kunlun circuit, E-036 bb18_p8_d3) must come out 3.
usage: uv run python -m search.experiments.e038_audit.b1_certify [--Rreset 3] [--Rnoreset 6]"""
import argparse
import json
import time

import numpy as np

from search.experiments.e038_audit import acore as C


def kunlun_spec():
    """Fig. S3 circuit (lead-checked edge by edge): X slots [-, A2, B2, B1, B3, A1, A3], Z [A1T, A3T, B1T, B2T, B3T,
    A2T, -] in CNOT layers 1..7; prep 0, meas 8.  Terms are identified by their monomial, recomputed here."""
    import numpy as np
    x = C._x
    y = C._y
    I = C._I
    A_terms = {"A1": x, "A2": I, "A3": (y @ y) % 2}
    B_terms = {"B1": y, "B2": I, "B3": (x @ x) % 2}
    SX = [None, "A2", "B2", "B1", "B3", "A1", "A3"]
    SZ = ["A1", "A3", "B1", "B2", "B3", "A2", None]
    d = {"format": "qec-schedule/v1", "period": 9, "x_checks": [], "z_checks": []}
    for kind, rows, slots in (("X", C.MEASURED["X"], SX), ("Z", C.MEASURED["Z"], SZ)):
        for r in rows:
            cn = []
            for s, term in enumerate(slots):
                if term is None:
                    continue
                M = A_terms.get(term, B_terms.get(term))
                isA = term[0] == "A"
                if kind == "X":
                    q = int(np.nonzero(M[r])[0][0]) + (0 if isA else 9)
                else:
                    q = int(np.nonzero(M.T[r])[0][0]) + (9 if isA else 0)
                cn.append([q, s + 1])
            d["x_checks" if kind == "X" else "z_checks"].append({"prep": 0, "meas": 8, "cnots": cn})
    return d


def syndrome_test(P, sch, meas):
    """noiseless; X (Z) error on data q right before round 1 of an R = 3 circuit must fire exactly the round-1
    detectors of the Z (X) checks whose support contains q (reset ancillas, all detectors) -> the circuit measures
    the intended stabilisers.  Also: noiseless circuit samples all-zero detectors (determinism)."""
    import stim
    bad = []
    for basis in ("Z", "X"):
        c0 = C.build(P, sch, basis, 3, p=0, meas=meas)
        det = c0.compile_detector_sampler(seed=1).sample(64)
        if det.any():
            bad.append(("nondeterministic", basis))
        for q in range(18):
            for pa in ("X", "Z"):
                c = C.build(P, sch, basis, 3, p=0, inject=(1, q, pa), meas=meas)
                det = c.compile_detector_sampler(seed=1).sample(1)[0]
                # detector numbering: per round, checks in order with type filter as in build
                ks = C.check_list(meas)
                names = []
                for j in range(3):
                    for k in ks:
                        if k[0] != basis and j == 0:
                            continue
                        names.append((k, j))
                names += [(k, "final") for k in ks if k[0] == basis]
                fired = {names[i] for i in np.nonzero(det)[0]}
                want_type = "Z" if pa == "X" else "X"
                want = {(k, 1) for k in ks if k[0] == want_type and q in C.supp(k)}
                if fired != want:
                    bad.append((basis, q, pa, sorted(map(str, fired)), sorted(map(str, want))))
    return bad


def certify(name, path_or_dict, meas, Rreset, Rnoreset, w4R=(1,)):
    P, sch = C.parse_spec(path_or_dict, meas)
    res = {"name": name, "P": P, "legal_problems": C.check_legal(P, sch), "parity_bad": C.parity_condition(sch),
           "couplers": len({(k, q) for k in sch for q in sch[k]["cx"]}),
           "cnot_layers": sorted({t for k in sch for t in sch[k]["cx"].values()})}
    res["syndrome_test_bad"] = syndrome_test(P, sch, meas)
    rows = []
    for reset, Rm in ((True, Rreset), (False, Rnoreset)):
        for R in range(1, Rm + 1):
            for b in ("Z", "X"):
                t0 = time.time()
                ms = C.mechs(C.build(P, sch, b, R, reset=reset, meas=meas))
                w = C.min_weight(ms, 4 if (R in w4R and reset) else 3)
                rows.append({"reset": reset, "R": R, "basis": b, "nmech": len(ms), "minw": w,
                             "sec": round(time.time() - t0, 1)})
                print(name, rows[-1], flush=True)
    res["rows"] = rows
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--Rreset", type=int, default=3)
    ap.add_argument("--Rnoreset", type=int, default=6)
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    jobs = [("kunlun", kunlun_spec(), C.MEASURED, 3, 3),
            ("bb18_p8_d3", "search/experiments/e036/bb18_p8_d3_spec.json", C.MEASURED, 3, 3),
            ("n8", "search/experiments/e038/bb18_n8_d4_spec.json", C.MEASURED, a.Rreset, a.Rnoreset),
            ("full_n7", "search/experiments/e038/full_n7_d4_spec.json", C.FULL, a.Rreset, a.Rnoreset)]
    out = open("results/E-038-audit/b1_certify.jsonl", "a")
    for nm, src, meas, rr, rn in jobs:
        if a.only and nm not in a.only.split(","):
            continue
        r = certify(nm, src, meas, rr, rn)
        out.write(json.dumps(r, default=str) + "\n")
        out.flush()
        print(json.dumps({k: v for k, v in r.items() if k != "rows"}, default=str), flush=True)
