"""Build the revision-P part of release/zenodo/ (version 3.0): circuit files of Table I / II / S1 (g10, g8, g9, b9, b10;
u11, c11 and IBM's circuits are already in the package), extended codes and complete lists of the light extended
logicals of every attaining circuit, the instance order and the records of the g10 lift certificates (R* = 13).

    PYTHONPATH=.:tests:release/zenodo/code uv run python scripts/zenodo/build_v3.py
Sources (internal; no path information is written into the package):
  circuits  search/experiments/e040/g{10_d12,8_d11}_spec.json, search/experiments/e043/{g9_d11,b9_d9,b10_d9}_spec.json
  lists     g10, g8: results/E-040-audit-circ/list_{g10,g8}_{Z,X}_w*.pkl (audit enumeration, by memory basis), g10
            cross-checked set-equal with the lists of the certified run; g9, b9, b10, IBM: results/E-043-audit/list_*.pkl
            cross-checked set-equal with results/E-043-table where present
  g10 lift  results/E-042-g10-cert/lift/R13/results.jsonl (250 batches) + the instance order of that run
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

SRC = {
    "g10": ("gross", "search/experiments/e040/g10_d12_spec.json",
            "g10: gross code [[144,12,12]], single-ancilla, translation invariant, period 10 (Table II): X checks reset 9, "
            "order A1A2B1A3B2B3 at steps 0,1,2,3,4,7, measurement 8; Z checks reset 8, order B3B2A3B1A2A1 at steps "
            "9,2,3,4,5,6 (the first of the next period), measurement 7 (wrapping). d_circ = 12 for every R, both bases "
            "(Theorem 1)"),
    "g8": ("gross", "search/experiments/e040/g8_d11_spec.json",
           "g8: gross code, translation invariant, period 8 (Table S1): X checks reset 7, order A2A1B2B3B1A3 at steps "
           "0..5, measurement 6; Z checks reset 0, order A3B1B3B2A1A2 at steps 1..6, measurement 7. d_circ = 11 for "
           "every R, both bases"),
    "g9": ("gross", "search/experiments/e043/g9_d11_spec.json",
           "g9: gross code, translation invariant, period 9 (Table S1): X checks reset 8, order A1B1A2A3B2B3 at steps "
           "0,1,2,3,4,6, measurement 7; Z checks reset 7, order B3B2A3A2B1A1 at steps 8,1,2,3,4,5, measurement 6. "
           "d_circ = 11 for every R, both bases"),
    "bb90_b9": ("bb90", "search/experiments/e043/b9_d9_spec.json",
                "b9: [[90,8,10]], translation invariant, period 9 (Table S1): X checks reset 8, order A1A2B2B3A3B1 at "
                "steps 0,2,3,4,5,6, measurement 7; Z checks reset 0, order B1A3B2B3A2A1 at steps 1,2,3,4,5,7, "
                "measurement 8. d_circ = 9 for every R, both bases"),
    "bb90_b10": ("bb90", "search/experiments/e043/b10_d9_spec.json",
                 "b10: [[90,8,10]], translation invariant, period 10 (Table S1): X checks reset 9, order A1A2B2A3B3B1 "
                 "at steps 0,1,2,3,4,7, measurement 8; Z checks reset 8, order B1B3A3B2A1A2 at steps 9,2,3,4,5,6, "
                 "measurement 7. d_circ = 9 for every R, both bases"),
}
specs = {}
for name, (fam, path, desc) in SRC.items():
    d = json.load(open(path))
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
for name, fam in (("ibm_gross_depth8", "gross"), ("bb90_ibm_depth8", "bb90")):
    specs[name] = PS.parse_schedule(json.load(open(DATA / "circuits" / f"{name}.json")))
    for ref in (("search/experiments/e033/ibm_gross_spec.json",) if fam == "gross" else ("search/experiments/e030/ibm90_spec.json",)):
        assert ev_parse(json.load(open(ref))).canonical() == ev_parse(
            {k: v for k, v in json.load(open(DATA / "circuits" / f"{name}.json")).items() if k != "name"}).canonical()
print("circuits OK")


def ext_and_lists(tag, fam, spec, lists, dext, desc_circ, with_orbits):
    """write data/extended_code/{tag}_extended_code_{b}_memory.json and data/logicals/{tag}_weight{w}_..._memory.json;
    lists[basis][w] = list of column-key tuples.  Returns {basis: (keys, sorted lists)}."""
    code = codes[fam]
    l, m = (12, 6) if fam == "gross" else (15, 3)
    out = {}
    for basis in ("Z", "X"):
        keys, sups, supkey = P.ext_columns(code, basis, spec)
        kidx = {k: j for j, k in enumerate(keys)}
        G, perms, classes, orb_of = [], [], [], {}
        if with_orbits:
            G = P.order_group(spec, "gross" if fam == "gross" else "bb90")
            assert len(G) == l * m, len(G)
            for a, b in G:
                pq = P.translation("gross" if fam == "gross" else "bb90", a, b)
                perms.append([kidx[supkey[tuple(sorted(pq[q] for q in s))]] for s in sups])
            seen = set()
            for j in range(len(keys)):
                if j in seen:
                    continue
                o = sorted({p[j] for p in perms}); seen |= set(o); classes.append(o)
            orb_of = {j: o for o, cl in enumerate(classes) for j in cl}
        H, L = P.hl(code, basis)
        cols = []
        for j, s in enumerate(sups):
            v = np.zeros(code.n, np.uint8); v[list(s)] = 1
            h = np.flatnonzero((H @ v) % 2).tolist(); lv = np.flatnonzero((L @ v) % 2).tolist()
            c = {"index": j, "support": list(s), "kind": "data" if len(s) == 1 else "residual", "H": h, "L": lv,
                 "check_weight": len(h)}
            if with_orbits:
                c["orbit"] = orb_of[j]
            cols.append(c)
        ctype = "X" if basis == "Z" else "Z"
        ext = {"description": f"Extended code of the {basis}-basis memory of {desc_circ} ({ctype} errors... see "
                              f"README section 3): H = H{basis}, L = L{basis} of data/code/{fam}_code.json; residuals "
                              f"from the {ctype}-check CNOT orders of the circuit. Column j: representative support "
                              "(data qubits), H = check rows with H s = 1, L = logical rows with L s = 1"
                              + (", orbit under the translations." if with_orbits else "."),
               "basis": basis, "num_columns": len(cols), "num_checks": int(H.shape[0]), "num_logicals": int(L.shape[0]),
               "columns": cols}
        ext["description"] = ext["description"].replace(" errors... see README section 3)", " errors)")
        if with_orbits:
            ext["translation_group"] = [list(g) for g in G]
            ext["orbits"] = classes
        json.dump(ext, open(DATA / "extended_code" / f"{tag}_extended_code_{basis}_memory.json", "w"),
                  separators=(",", ":"))
        Hm, Lm = P.key_matrices(keys, H.shape[0])
        out[basis] = (keys, {})
        for w, kl in sorted(lists[basis].items()):
            lst = sorted(tuple(sorted(kidx[k] for k in S)) for S in kl)
            assert len(set(lst)) == len(lst)
            entries, lorb = [], {}
            for S in lst:
                x = np.zeros(len(keys), np.uint8); x[list(S)] = 1
                assert len(set(S)) == w and not ((Hm @ x) % 2).any() and ((Lm @ x) % 2).any()
                e = {"columns": list(S)}
                if with_orbits:
                    rep = min(tuple(sorted(p[j] for j in S)) for p in perms)
                    lorb.setdefault(rep, len(lorb))
                    e["orbit"] = lorb[rep]
                e["logical_flipped"] = np.flatnonzero((Lm @ x) % 2).tolist()
                entries.append(e)
            out[basis][1][w] = lst
            dd = {"description": f"All weight-{w} logicals of the extended code of the {basis}-basis memory of "
                                 f"{desc_circ} (d_ext = {dext[basis]}): each entry lists {w} distinct column indices of "
                                 f"data/extended_code/{tag}_extended_code_{basis}_memory.json whose H parts sum to zero "
                                 "and whose L parts do not; 'logical_flipped' = rows of L with odd sum. Entries are in "
                                 "lexicographic order.",
                  "basis": basis, "weight": w, "d_ext": dext[basis], "count": len(entries), "logicals": entries}
            if with_orbits:
                dd["num_orbits"] = len(lorb)
            json.dump(dd, open(DATA / "logicals" / f"{tag}_weight{w}_logicals_{basis}_memory.json", "w"),
                      separators=(",", ":"))
            print(tag, basis, "columns", len(keys), f"weight-{w}", len(entries), "orbits", len(lorb) if with_orbits else "-")
    return out


def pk(path):
    return [tuple(S) for S in pickle.load(open(path, "rb"))["keys"]]


A40 = Path("results/E-040-audit-circ")
A43 = Path("results/E-043-audit")
T43 = Path("results/E-043-table")
E40 = Path("results/E-040-min-period")

# ---- g10 (certified): audit lists, cross-checked with the lists of the certified run (E-040 enumeration, by kind)
L10 = {b: {w: pk(A40 / f"list_g10_{b}_w{w}.pkl") for w in (10, 11)} for b in "ZX"}
KIND = {"Z": "X", "X": "Z"}
for b in "ZX":
    run10 = pk(E40 / f"list_gross_{KIND[b]}_A1A2B1A3B2B3.pkl")
    run11 = pk(E40 / f"list11_gross_{KIND[b]}_A1A2B1A3B2B3.pkl")
    assert {frozenset(S) for S in run10} == {frozenset(S) for S in L10[b][10]}
    assert {frozenset(S) for S in run11} == {frozenset(S) for S in L10[b][11]}
    assert len(run10) == 3204 and len(run11) == 121104
g10 = ext_and_lists("g10", "gross", specs["g10"], L10, {"Z": 10, "X": 10},
                    "the period-10 gross circuit g10 (data/circuits/g10.json)", True)
# instance order of the certified lift run: weight-10 list then weight-11 list, each in the order of the run's lists
order = json.load(open(REL / "certificates/proofs/lift_instance_order.json"))
order["g10"] = {}
for b in "ZX":
    keys, lists = g10[b]
    kidx = {k: j for j, k in enumerate(keys)}
    order["g10"][b] = {}
    for w, f in ((10, f"list_gross_{KIND[b]}_A1A2B1A3B2B3.pkl"), (11, f"list11_gross_{KIND[b]}_A1A2B1A3B2B3.pkl")):
        pos = {S: i for i, S in enumerate(lists[w])}
        order["g10"][b][str(w)] = [pos[tuple(sorted(kidx[k] for k in S))] for S in pk(E40 / f)]
json.dump(order, open(REL / "certificates/proofs/lift_instance_order.json", "w"), separators=(",", ":"))
print("g10 instance order written")

# ---- the other circuits of Table I (not certified): lists of Theorem 4's target t
OTHER = {  # tag: (family, spec name, {basis: {w: file}}, dext, description)
    "g8": ("gross", "g8", {b: {w: A40 / f"list_g8_{b}_w{w}.pkl" for w in (9, 10)} for b in "ZX"}, {"Z": 9, "X": 9},
           "the period-8 gross circuit g8 (data/circuits/g8.json)"),
    "g9": ("gross", "g9", {b: {w: A43 / f"list_g9_{b}_w{w}.pkl" for w in (9, 10)} for b in "ZX"}, {"Z": 9, "X": 9},
           "the period-9 gross circuit g9 (data/circuits/g9.json)"),
    "bb90_b9": ("bb90", "bb90_b9", {b: {w: A43 / f"list_b9_{b}_w{w}.pkl" for w in (7, 8)} for b in "ZX"},
                {"Z": 7, "X": 7}, "the period-9 [[90,8,10]] circuit b9 (data/circuits/bb90_b9.json)"),
    "bb90_b10": ("bb90", "bb90_b10", {b: {w: A43 / f"list_b10_{b}_w{w}.pkl" for w in (7, 8)} for b in "ZX"},
                 {"Z": 7, "X": 7}, "the period-10 [[90,8,10]] circuit b10 (data/circuits/bb90_b10.json)"),
    "ibm_gross_depth8": ("gross", "ibm_gross_depth8", {"Z": {9: A43 / "list_ibmg_Z_w9.pkl"},
                                                       "X": {8: A43 / "list_ibmg_X_w8.pkl", 9: A43 / "list_ibmg_X_w9.pkl"}},
                         {"Z": 9, "X": 8}, "IBM's depth-8 gross circuit (data/circuits/ibm_gross_depth8.json)"),
    "bb90_ibm_depth8": ("bb90", "bb90_ibm_depth8", {"Z": {7: A43 / "list_ibm90_Z_w7.pkl"},
                                                     "X": {6: A43 / "list_ibm90_X_w6.pkl", 7: A43 / "list_ibm90_X_w7.pkl"}},
                        {"Z": 7, "X": 6}, "IBM's depth-8 [[90,8,10]] circuit (data/circuits/bb90_ibm_depth8.json)"),
}
CROSS = {"g9": "list_g9_d11_spec_{b}_w{w}.pkl", "ibm_gross_depth8": "list_ibm_gross_spec_{b}_w{w}.pkl",
         "bb90_ibm_depth8": "list_ibm90_spec_{b}_w{w}.pkl"}
for tag, (fam, sname, files, dext, desc) in OTHER.items():
    lists = {b: {w: pk(f) for w, f in files[b].items()} for b in "ZX"}
    if tag in CROSS:
        for b in "ZX":
            for w in lists[b]:
                g = T43 / CROSS[tag].format(b=b, w=w)
                assert {frozenset(S) for S in pk(g)} == {frozenset(S) for S in lists[b][w]}, (tag, b, w)
    ext_and_lists(tag, fam, specs[sname], lists, dext, desc, False)
print("lists OK")
