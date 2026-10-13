"""Build release/zenodo/data/ (code matrices, circuit specifications, extended codes, the 4224-logical lists).

Run from the repository root:
    PYTHONPATH=.:tests:release/zenodo/code uv run python scripts/zenodo/build_data.py

Sources (internal; nothing of this path information is written into the package):
  code matrices        evaluator build_code("gross-dcirc")
  circuits             circuit A = search/experiments/e024a/cs_P18_H24.json, B = search/experiments/e024b/p18w_spec.json,
                       C = search/experiments/e021/cand_p21_spec.json, Fig. 12 = baselines.strikis.strikis_fig12,
                       retimings = results/E-020-gross-perchk-pipeline/p8_cand{0..3}.json
  4224 lists           audited rebuild (E-018 audit w11dfs outputs, rerun 2026-10-12 by reproduce_theorems.sh),
                       expanded by the 24-element group; cross-checked against the original audit outputs.
Every exported object is cross-checked against the internal implementation it came from.
"""
import glob
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, "tests")
sys.path.insert(0, "research/audits/2026-10-08-E-018-scripts")
sys.path.insert(0, "release/zenodo/code")

from evaluators.tasks import build_code, get_task                    # noqa: E402
from evaluators.candidate import parse_schedule as ev_parse, build_circuits as ev_build   # noqa: E402
from evaluators.noise import add_noise                                # noqa: E402

from gross12 import code as PC, schedule as PS, ext as PE, noise as PN   # noqa: E402

REL = Path("release/zenodo")
DATA = REL / "data"
evcode, _ = build_code(get_task("gross-dcirc"), None)

# ---------------------------------------------------------------- code matrices
rows = lambda M: [np.flatnonzero(r).tolist() for r in np.asarray(M) % 2]  # noqa: E731
code_json = {
    "description": "gross code [[144,12,12]] of arXiv:2308.07915: l=12, m=6, A = x^3+y+y^2, B = y^3+x+x^2, "
                   "HX = [A|B], HZ = [B^T|A^T]. Qubit/check index 6a+b for x^a y^b; left block = qubits 0..71, "
                   "right block = 72..143. Each matrix is given as a list of rows, each row as the sorted list of "
                   "the columns where it is 1. LX: 12 X-type logical operators, LZ: 12 Z-type logical operators "
                   "(the observables of the X- and Z-basis memories; all logical lists refer to these rows).",
    "n": 144, "k": 12, "d": 12, "l": 12, "m": 6,
    "A": ["x^3", "y", "y^2"], "B": ["y^3", "x", "x^2"],
    "term_labels": {"A1": "x^3", "A2": "y", "A3": "y^2", "B1": "y^3", "B2": "x", "B3": "x^2"},
    "HX": rows(evcode.HX), "HZ": rows(evcode.HZ), "LX": rows(evcode.LX), "LZ": rows(evcode.LZ),
}
(DATA / "code").mkdir(parents=True, exist_ok=True)
json.dump(code_json, open(DATA / "code" / "gross_code.json", "w"), indent=None, separators=(",", ":"))
code = PC.load_code()          # also asserts the polynomial definition, k = 12, commutation
for a in ("HX", "HZ", "LX", "LZ"):
    assert (getattr(code, a) == np.asarray(getattr(evcode, a)) % 2).all()
print("code matrices OK")

# ---------------------------------------------------------------- circuits
from schedule_helpers import from_baseline          # noqa: E402
from baselines.bb_code import gross_code            # noqa: E402
from baselines.strikis import strikis_fig12         # noqa: E402

fig12 = from_baseline(strikis_fig12(gross_code())[0]).to_dict()
assert json.load(open("results/E-021-gross-new-orders/fig12_spec.json"))["x_checks"] == fig12["x_checks"]
src = {
    "circuit_A": ("search/experiments/e024a/cs_P18_H24.json",
                  "Circuit A (Table I of the paper): period 18, pipelined, interleaved; d_circ = 12 (Theorem 1)"),
    "circuit_B": ("search/experiments/e024b/p18w_spec.json",
                  "Circuit B (Table S1): period 18, pipelined, interleaved; d_circ = 12"),
    "circuit_C": ("search/experiments/e021/cand_p21_spec.json",
                  "Circuit C (Table S2): period 21, common frame (reset 0, measurement 20), interleaved; d_circ = 12"),
}
(DATA / "circuits").mkdir(parents=True, exist_ok=True)
specs = {}
for name, (path, desc) in src.items():
    d = json.load(open(path))
    d = {"format": d["format"], "name": desc, "period": d["period"], "x_checks": d["x_checks"], "z_checks": d["z_checks"]}
    specs[name] = d
d = dict(fig12)
d["name"] = ("Fig. 12 of Strikis, Browne, Beverland (arXiv:2603.05481): period 8, pipelined, non-interleaved; "
             "d_circ = 11 (Corollary 1)")
specs["fig12"] = {k: d[k] for k in ("format", "name", "period", "x_checks", "z_checks")}
for k in range(4):
    d = json.load(open(f"results/E-020-gross-perchk-pipeline/p8_cand{k}.json"))
    specs[f"fig12_retiming_{k}"] = {"format": d["format"],
                                    "name": f"Period-8 retiming {k} of Fig. 12 (same CNOT orders, SM S9): one of the 4 "
                                            "conflict-free start assignments up to translation",
                                    "period": d["period"], "x_checks": d["x_checks"], "z_checks": d["z_checks"]}
for name, d in specs.items():
    s_pkg = PS.parse_schedule(d)
    s_ev = ev_parse({k: v for k, v in d.items() if k != "name"})
    assert not PS.validate_schedule(s_pkg, code), name
    for R in (1, 2, 3):
        cp = PS.build_circuits(s_pkg.canonical(), code, R)
        ce = ev_build(s_ev.canonical(), evcode, R)
        for b in "ZX":
            assert str(cp[b]) == str(ce[b]), (name, R, b)
            assert str(PN.add_sd6(cp[b])) == str(add_noise(ce[b], "sd6", 1e-3)), (name, R, b, "noise")
    json.dump(d, open(DATA / "circuits" / f"{name}.json", "w"), separators=(",", ":"))
# which retiming is Fig. 12 up to a global shift
f12c = PS.parse_schedule(specs["fig12"]).canonical().to_dict()
same = [k for k in range(4) if PS.parse_schedule(specs[f"fig12_retiming_{k}"]).canonical().to_dict() == f12c]
print("circuits OK (package template == evaluator template, noiseless and SD6, R = 1..3); retiming == Fig. 12:", same)

# ---------------------------------------------------------------- extended codes + 4224 lists
import a2_stage_a as A2            # noqa: E402  (E-018 audit)

f12 = PS.parse_schedule(specs["fig12"])
G = PE.order_group(f12)
assert len(G) == 24
DFS = sorted(glob.glob("results/reproduce_theorems_2026-10-12_gross12_p18/gross12_p18/e018/dfs_*.txt"))
DFS0 = sorted(glob.glob("results/E-018-audit/dfs_*.txt"))
assert len(DFS) == 240 and len(DFS0) == 240, (len(DFS), len(DFS0))
(DATA / "extended_code").mkdir(parents=True, exist_ok=True)
(DATA / "logicals").mkdir(parents=True, exist_ok=True)
xo, zo = f12.orders()
for basis, kind in (("Z", "X"), ("X", "Z")):
    keys, sups, supkey = PE.ext_columns(code, basis, f12)
    akeys, akidx, acolsup, asupkey = A2.build(kind)
    assert [hb.tobytes() + lb.tobytes() for hb, lb in akeys] == keys and acolsup == sups, "column order differs"
    for c, s in (("A", "circuit_A"), ("B", "circuit_B"), ("C", "circuit_C")):
        k2, _, _ = PE.ext_columns(code, basis, PS.parse_schedule(specs[s]))
        assert set(k2) == set(keys)
    perms = PE.column_perms(code, basis, f12, keys, sups, supkey, G)
    classes = PE.orbits(perms, len(keys))
    orb_of = {j: o for o, cl in enumerate(classes) for j in cl}
    H, L = PE.hl(code, basis)
    # realisations: every (data qubit) or (check, suffix) whose support has this column's key, in Fig. 12
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
                     "H": h, "L": lv, "check_weight": len(h), "orbit": orb_of[j], "fig12_realisations": real[k]})
    ext = {"description": f"Extended code of the {basis}-basis memory ({'X' if basis == 'Z' else 'Z'} errors; "
                          f"H = H{basis}, L = L{basis} of data/code/gross_code.json; residuals from the "
                          f"{ctype}-check CNOT orders of Fig. 12). Column j: representative support (data qubits), "
                          "H = list of check rows with H s = 1, L = list of logical rows with L s = 1. Circuits A, B, C "
                          "have the same set of columns.",
           "basis": basis, "num_columns": len(cols), "num_checks": int(H.shape[0]), "num_logicals": int(L.shape[0]),
           "translation_group": [list(g) for g in G], "orbits": classes, "columns": cols}
    json.dump(ext, open(DATA / "extended_code" / f"extended_code_{basis}_memory.json", "w"), separators=(",", ":"))
    assert PE.ext_keys_from_file(code, basis) == keys

    def expand(files):
        found, nodes, summ = set(), 0, 0
        for fn in files:
            if f"dfs_{kind}_" not in fn:
                continue
            for line in open(fn):
                if line.startswith("SUMMARY"):
                    nodes += int(line.split()[4]); summ += 1
                    continue
                S = tuple(map(int, line.split()))
                for p in perms:
                    found.add(tuple(sorted(p[j] for j in S)))
        return found, nodes, summ
    found, nodes, summ = expand(DFS)
    found0, nodes0, summ0 = expand(DFS0)
    assert found == found0 and nodes == nodes0 and summ == summ0 == 120, (len(found), len(found0))
    assert len(found) == 4224
    Hm = np.array([np.frombuffer(k[:72], np.uint8) for k in keys]).T
    Lm = np.array([np.frombuffer(k[72:], np.uint8) for k in keys]).T
    entries, lorb = [], {}
    for S in sorted(found):
        x = np.zeros(len(keys), np.uint8); x[list(S)] = 1
        assert len(set(S)) == 11 and not ((Hm @ x) % 2).any() and ((Lm @ x) % 2).any()
        rep = min(tuple(sorted(p[j] for j in S)) for p in perms)
        lorb.setdefault(rep, len(lorb))
        res = [j for j in S if len(sups[j]) > 1]
        entries.append({"columns": list(S), "orbit": lorb[rep],
                        "logical_flipped": np.flatnonzero((Lm @ x) % 2).tolist(),
                        "ten_data_plus_one_length2_residual": len(res) == 1 and len(sups[res[0]]) == 2})
    assert len(lorb) == 176
    n10 = sum(e["ten_data_plus_one_length2_residual"] for e in entries)
    print(basis, "columns", len(keys), "orbits", len(classes), "logicals", len(entries), "orbits", len(lorb),
          "10 data + r2:", n10, "dfs nodes", nodes)
    json.dump({"description": f"All weight-11 logicals of the extended code of the {basis}-basis memory (d_ext = 11): "
                              f"each entry lists 11 distinct column indices of "
                              f"data/extended_code/extended_code_{basis}_memory.json whose H parts sum to zero and "
                              "whose L parts do not; 'orbit' numbers the 176 orbits under the 24 translations; "
                              "'logical_flipped' = rows of L with odd sum.",
               "basis": basis, "count": len(entries), "num_orbits": len(lorb), "logicals": entries},
              open(DATA / "logicals" / f"weight11_logicals_{basis}_memory.json", "w"), separators=(",", ":"))
print("extended codes and lists OK")
