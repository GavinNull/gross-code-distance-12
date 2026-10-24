"""Build the period-11 part of release/zenodo/ (version 2.0): circuit files (u11 and its two controls, c11, c12, c13,
the IBM depth-8 reference circuits of both codes), the extended code of u11, the complete weight-10 / weight-11
extended-logical lists of u11, and the witness descriptions.

Run from the repository root:
    PYTHONPATH=.:tests:release/zenodo/code uv run python scripts/zenodo/build_p11.py

Sources (internal; no path information is written into the package):
  u11                 search/experiments/e032/u11_spec.json
  u11 controls        search/experiments/e032/ctl_p10_spec.json (period 10), results/E-032-audit/segctl_spec.json
  c11, c12, c13       search/experiments/e030/c1{1,2,3}_spec.json
  IBM depth 8         e026/e030 common.spec("ibm") (built from baselines.schedule.ibm_depth8), compared with
                      search/experiments/e033/ibm_gross_spec.json and search/experiments/e030/ibm90_spec.json
  u11 lists           results/E-032-gross-short-period/w{10,11}_{X,Z}_all_A1A2A3B3B1B2.pkl (project DFS), cross-checked
                      set for set against the audit enumeration results/E-032-audit/lists_u11_spec_{Z,X}.pkl (memory basis)
Every circuit: package template == evaluator template (noiseless and SD6, R = 1..3, both bases, string equality).
"""
import json
import pickle
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, "tests")
sys.path.insert(0, "release/zenodo/code")

from evaluators.tasks import build_code, get_task                                        # noqa: E402
from evaluators.candidate import parse_schedule as ev_parse, build_circuits as ev_build   # noqa: E402
from evaluators.noise import add_noise                                                    # noqa: E402

from gross12 import schedule as PS, noise as PN                                           # noqa: E402
from p11 import common as P                                                               # noqa: E402

REL = Path("release/zenodo")
DATA = REL / "data"

codes = {"gross": P.load_code("gross"), "bb90": P.load_code("bb90")}
evcodes = {"gross": build_code(get_task("gross-dcirc"), None)[0], "bb90": build_code(get_task("bb90-dcirc"), None)[0]}
for f in codes:
    for a in ("HX", "HZ", "LX", "LZ"):
        assert (getattr(codes[f], a) == np.asarray(getattr(evcodes[f], a)) % 2).all(), (f, a)


def ibm_spec(family):
    if family == "gross":
        from search.experiments.e026 import common as c26
        s = c26.spec("ibm")
        ref = "search/experiments/e033/ibm_gross_spec.json"
    else:
        from search.experiments.e030 import common as c30
        s = c30.spec("ibm")
        ref = "search/experiments/e030/ibm90_spec.json"
    d = s.to_dict()
    assert ev_parse(json.load(open(ref))).canonical() == s.canonical(), "IBM spec file differs from the baseline"
    return d


SRC = {
    "u11": ("gross", "search/experiments/e032/u11_spec.json",
            "u11: gross code [[144,12,12]], single-ancilla, translation invariant, period 11 (Table I): X checks reset 0, "
            "order A2A1A3B3B2B1 at steps 1,2,3,4,5,9, measurement 10; Z checks reset 10, order B1B2B3A3A1A2 at steps "
            "0,4,5,6,7,8 of the next period, measurement 9 (wrapping). d_circ = 12 for every R, both bases (Theorem 1)"),
    "u11_control_p10": ("gross", "search/experiments/e032/ctl_p10_spec.json",
                        "control for u11: period 10, translation invariant, orders in the class of u11 (same extended "
                        "code); weight-11 extended logicals lift at R = 1, 2 (432 in the Z basis, 576 in the X basis), "
                        "so d_circ <= 11"),
    "u11_control_segmented": ("gross", "results/E-032-audit/segctl_spec.json",
                              "segmented control for u11: the u11 orders with an X block (reset 0, CNOTs 1..6, "
                              "measurement 7) and a Z block (reset 7, CNOTs 8..13, measurement 14), period 15; "
                              "non-interleaved, every weight-10 and weight-11 extended logical lifts at R = 1, 2"),
    "bb90_c11": ("bb90", "search/experiments/e030/c11_spec.json",
                 "c11: [[90,8,10]], single-ancilla, translation invariant, period 11 (Table I): X checks reset 0, order "
                 "B1B3B2A3A1A2 at steps 1,2,3,4,5,9, measurement 10; Z checks reset 10, order A2A1A3B2B3B1 at steps "
                 "0,4,5,6,7,8 of the next period, measurement 9 (wrapping). Extended code = that of c16. "
                 "d_circ = 10 for every R, both bases (Theorem 2)"),
    "bb90_c12": ("bb90", "search/experiments/e030/c12_spec.json",
                 "c12: [[90,8,10]], period 12, non-wrapping (every check: reset 0, measurement 11), translation "
                 "invariant, extended code = that of c16; d_circ = 10 for every R, both bases"),
    "bb90_c13": ("bb90", "search/experiments/e030/c13_spec.json",
                 "c13: [[90,8,10]], period 13 (c16 with its three CNOT-free steps removed: reset 0, measurement 12), "
                 "translation invariant, extended code = that of c16; d_circ = 10 for every R, both bases"),
    "ibm_gross_depth8": ("gross", None,
                         "reference: IBM's depth-8 syndrome circuit of the gross code (arXiv:2308.07915), expressed in "
                         "the single-ancilla template (period 8); used for the logical-error-rate comparisons"),
    "bb90_ibm_depth8": ("bb90", None,
                        "reference: IBM's depth-8 syndrome circuit of [[90,8,10]] (arXiv:2308.07915), expressed in the "
                        "single-ancilla template (period 8); used for the logical-error-rate comparisons"),
}
specs = {}
for name, (fam, path, desc) in SRC.items():
    d = ibm_spec(fam) if path is None else json.load(open(path))
    d = {"format": d["format"], "name": desc, "period": d["period"], "x_checks": d["x_checks"], "z_checks": d["z_checks"]}
    s_pkg = PS.parse_schedule(d)
    s_ev = ev_parse({k: v for k, v in d.items() if k != "name"})
    assert not PS.validate_schedule(s_pkg, codes[fam]), name
    for R in (1, 2, 3):
        cp = PS.build_circuits(s_pkg.canonical(), codes[fam], R)
        ce = ev_build(s_ev.canonical(), evcodes[fam], R)
        for b in "ZX":
            assert str(cp[b]) == str(ce[b]), (name, R, b)
            assert str(PN.add_sd6(cp[b])) == str(add_noise(ce[b], "sd6", 1e-3)), (name, R, b, "noise")
    json.dump(d, open(DATA / "circuits" / f"{name}.json", "w"), separators=(",", ":"))
    specs[name] = s_pkg
    print("circuit", name, "period", d["period"], "OK")
print("circuits OK (package template == evaluator template, noiseless and SD6, R = 1..3)")

# ---------------------------------------------------------------- u11 extended code + lists
code = codes["gross"]
u11 = specs["u11"]
G = P.order_group(u11, "gross")
assert len(G) == 72, len(G)
xo, zo = u11.orders()
for basis, kind in (("Z", "X"), ("X", "Z")):
    keys, sups, supkey = P.ext_columns(code, basis, u11)
    for ctl in ("u11_control_p10", "u11_control_segmented"):
        k2, _, _ = P.ext_columns(code, basis, specs[ctl])
        assert set(k2) == set(keys), (ctl, "different extended code")
    kidx = {k: j for j, k in enumerate(keys)}
    perms = []
    for a, b in G:
        pq = P.translation("gross", a, b)
        perms.append([kidx[supkey[tuple(sorted(pq[q] for q in s))]] for s in sups])
    classes = []
    seen = set()
    for j in range(len(keys)):
        if j in seen:
            continue
        o = sorted({p[j] for p in perms}); seen |= set(o); classes.append(o)
    orb_of = {j: o for o, cl in enumerate(classes) for j in cl}
    H, L = P.hl(code, basis)
    real = {k: [] for k in keys}
    for q in range(144):
        k = supkey.get((q,))
        if k is not None:
            real[k].append({"data_qubit": q})
    ords = xo if basis == "Z" else zo
    ctype = "X" if basis == "Z" else "Z"
    for i, o in enumerate(ords):
        for k in range(1, 6):
            s = tuple(sorted(o[k:]))
            if s in supkey:
                real[supkey[s]].append({"check": f"{ctype}{i}", "after_cnot": k, "residual": list(s)})
    cols = []
    for j, (k, s) in enumerate(zip(keys, sups)):
        v = np.zeros(144, np.uint8); v[list(s)] = 1
        h = np.flatnonzero((H @ v) % 2).tolist(); lv = np.flatnonzero((L @ v) % 2).tolist()
        cols.append({"index": j, "support": list(s), "kind": "data" if len(s) == 1 else "residual",
                     "H": h, "L": lv, "check_weight": len(h), "orbit": orb_of[j], "u11_realisations": real[k]})
    ext = {"description": f"Extended code of the {basis}-basis memory of the period-11 gross circuit u11 "
                          f"({'X' if basis == 'Z' else 'Z'} errors; H = H{basis}, L = L{basis} of "
                          f"data/code/gross_code.json; residuals from the {ctype}-check CNOT orders of u11, which lie in "
                          "the uniform class of A1A2A3B3B1B2 under reversal, s12 and s56). Column j: representative "
                          "support (data qubits), H = list of check rows with H s = 1, L = list of logical rows with "
                          "L s = 1, orbit under the 72 translations. The two control circuits have the same column set.",
           "basis": basis, "num_columns": len(cols), "num_checks": int(H.shape[0]), "num_logicals": int(L.shape[0]),
           "translation_group": [list(g) for g in G], "orbits": classes, "columns": cols}
    assert len(cols) == 360 and len(classes) == 5
    json.dump(ext, open(DATA / "extended_code" / f"u11_extended_code_{basis}_memory.json", "w"), separators=(",", ":"))
    assert P.ext_keys_from_file(code, "gross", basis) == keys
    Hm, Lm = P.key_matrices(keys, H.shape[0])
    au = pickle.load(open(f"results/E-032-audit/lists_u11_spec_{basis}.pkl", "rb"))
    assert set(au["cols"]) == set(keys), "audit column keys differ"
    au_map = [kidx[k] for k in au["cols"]]
    for w in (10, 11):
        d = pickle.load(open(f"results/E-032-gross-short-period/w{w}_{kind}_all_A1A2A3B3B1B2.pkl", "rb"))
        assert set(d["colset"]) == set(keys)
        lst = [tuple(sorted(kidx[k] for k in S)) for S in d["keys"]]
        assert lst == sorted(lst) and len(set(lst)) == len(lst)
        audit = {tuple(sorted(au_map[j] for j in S)) for S in au["sets"][w]}
        assert set(lst) == audit, (basis, w, len(lst), len(audit))
        assert len(lst) == {10: 144, 11: 7344}[w]
        entries, lorb = [], {}
        for S in lst:
            x = np.zeros(len(keys), np.uint8); x[list(S)] = 1
            assert len(set(S)) == w and not ((Hm @ x) % 2).any() and ((Lm @ x) % 2).any()
            rep = min(tuple(sorted(p[j] for j in S)) for p in perms)
            lorb.setdefault(rep, len(lorb))
            entries.append({"columns": list(S), "orbit": lorb[rep],
                            "logical_flipped": np.flatnonzero((Lm @ x) % 2).tolist()})
        assert all(len({tuple(sorted(p[j] for j in S)) for p in perms}) == 72 for S in lorb)
        print(basis, "columns", len(keys), "column orbits", len(classes), f"weight-{w}", len(entries),
              "orbits", len(lorb), "(all free)")
        json.dump({"description": f"All weight-{w} logicals of the extended code of the {basis}-basis memory of the "
                                  f"period-11 gross circuit u11 (d_ext = 10): each entry lists {w} distinct column "
                                  f"indices of data/extended_code/u11_extended_code_{basis}_memory.json whose H parts "
                                  "sum to zero and whose L parts do not; 'orbit' numbers the (free) orbits under the 72 "
                                  "translations; 'logical_flipped' = rows of L with odd sum. Entries are in lexicographic "
                                  "order; this is also the instance order of the lift certificates.",
                   "basis": basis, "weight": w, "count": len(entries), "num_orbits": len(lorb), "logicals": entries},
                  open(DATA / "logicals" / f"u11_weight{w}_logicals_{basis}_memory.json", "w"), separators=(",", ":"))
print("u11 extended codes and lists OK (project DFS lists == audit lists)")

# ---------------------------------------------------------------- witness descriptions
p = REL / "witnesses" / "upper_bound_weight12.json"
W12 = json.load(open(p))
W12["description"] = ("Weight-12 logical operators of the gross code used for the upper bound d_circ <= 12. For the "
                      "Z-basis memory an X-type logical (support on data qubits; commutes with HZ, anticommutes with "
                      "some rows of LZ), for the X-basis memory a Z-type logical. Applied as single-qubit flips right "
                      "after data initialisation; verified by code/inject_upper_bound.py for circuits A, B, C "
                      "(R = 1, 2, 3, 6, 10) and by code/p11/inject_upper_bound.py for u11 (R = 1, 2, 3, 6, 10, 31).")
json.dump(W12, open(p, "w"))
p = REL / "witnesses" / "bb90_upper_bound_weight10.json"
W10 = json.load(open(p))
W10["description"] = ("Weight-10 logical operators of [[90,8,10]] used for the upper bound d_circ <= 10. For the "
                      "Z-basis memory an X-type logical (support on data qubits; commutes with HZ, anticommutes with "
                      "some rows of LZ), for the X-basis memory a Z-type logical. Applied as single-qubit flips right "
                      "after data initialisation (one SD6 reset fault each); verified by code/bb90/inject_upper_bound.py "
                      "for c16 (R = 1, 2, 3, 6, 10, 13) and by code/p11/inject_upper_bound.py for c11, c12, c13 "
                      "(R = 1, 2, 5, 11, 25).")
json.dump(W10, open(p, "w"), indent=1)
print("witness descriptions updated")
