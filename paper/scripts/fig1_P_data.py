"""Data for Fig. 1 of revision P (paper/figures/fig1_P_data.json).

(a) delta matrices delta(A_i, B_j) of IBM's depth-8 gross circuit, the period-10 circuit g10 and the period-11 circuit
    u11 (from paper/figures/circuits_P.json, written by circuits_P.py from the specs).
(b) The two-hook negative cycle on the first weight-10 extended logical of u11 (Z-basis memory), computed with the
    audited bulk model of search/theory/B_audit (research/audits/2026-10-29-theoryB.md, section 4: list 0 has the
    certificate X45 (suffix length 4) / X59 (suffix length 2), holonomy 2; all 144 logicals have holonomy 2).
    For every column of the logical we record its realisations; for the two hooks we record the reader indices at
    the two private readers and the term pair (A_i, B_j) of each edge.

Required inputs (paths relative to the repository root):
  from the data package (results/ is not in git):
    results/E-032-gross-short-period/w10_X_all_A1A2A3B3B1B2.pkl
        the 144 weight-10 X-type extended logicals of u11 (pickle with key "keys"); panel (b) uses list item 0
        and asserts the 144 x holonomy-2 histogram.
  from the repository:
    search/experiments/e032/u11_spec.json      schedule spec of u11
    paper/figures/circuits_P.json             delta matrices for panel (a); regenerate it with
                                               paper/scripts/circuits_P.py, which in turn needs the data-package
                                               directories results/E-040-audit-circ and results/E-043-audit
    search/theory/B_audit/                     audited bulk (staircase) model
Output: paper/figures/fig1_P_data.json (read by paper/scripts/fig1_P.py).

Usage (repository root):  PYTHONPATH=.:tests uv run python paper/scripts/fig1_P_data.py
"""
from __future__ import annotations

import json
import pickle
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "paper" / "scripts"))
from check_tables import CODES  # noqa: E402
from fig_common import check  # noqa: E402

SPEC = "search/experiments/e032/u11_spec.json"
LIST = "results/E-032-gross-short-period/w10_X_all_A1A2A3B3B1B2.pkl"


def term_pair(c, z):
    """(i, j) such that z = c + A_i + B_j (gross labelling of check_tables.CODES)."""
    g = CODES["gross"]
    L, M = g["L"], g["M"]
    ca, cb = divmod(c, M)
    za, zb = divmod(z, M)
    hits = [(i, j) for i, (_, (ax, ay)) in enumerate(g["A"]) for j, (_, (bx, by)) in enumerate(g["B"])
            if ((ca + ax + bx - za) % L, (cb + ay + by - zb) % M) == (0, 0)]
    assert len(hits) == 1, (c, z, hits)
    return hits[0]


def main():
    from search.theory.B_audit.common import Bulk, get_code, load_spec_dict
    from search.theory.B_audit.lift import bulk_columns

    circ = {r["name"]: r for r in json.loads((ROOT / "paper/figures/circuits_P.json").read_text())}
    B = Bulk(load_spec_dict(SPEC), get_code("gross"), "Z")
    cols, zero = bulk_columns(B)
    check(not zero, "u11 has zero-image hooks")
    keys = pickle.load(open(ROOT / LIST, "rb"))["keys"]
    check(len(keys) == 144, f"u11 weight-10 list has {len(keys)} entries, audit says 144")

    def certificate(S):
        touch = defaultdict(set)
        for ci, k in enumerate(S):
            for _, _, items in cols[k]:
                for z, _ in items:
                    touch[z].add(ci)
        rigid = [ci for ci, k in enumerate(S) if len(cols[k]) == 1 and cols[k][0][0] == "h"]
        best = (0, None)
        for a in range(len(rigid)):
            for b in range(a + 1, len(rigid)):
                f, g = rigid[a], rigid[b]
                itf, itg = defaultdict(list), defaultdict(list)
                for z, v in cols[S[f]][0][2]:
                    itf[z].append(v)
                for z, v in cols[S[g]][0][2]:
                    itg[z].append(v)
                priv = [z for z in touch if touch[z] == {f, g} and len(itf[z]) == 1 and len(itg[z]) == 1]
                if len(priv) >= 2:
                    d = {z: itf[z][0] - itg[z][0] for z in priv}
                    h = max(d.values()) - min(d.values())
                    if h > best[0]:
                        zmax = max(d, key=d.get)
                        zmin = min(d, key=d.get)
                        best = (h, (f, g, zmin, zmax, itf, itg))
        return best

    hist = Counter(certificate(S)[0] for S in keys)
    check(hist == Counter({2: 144}), f"two-hook holonomy histogram {dict(hist)}, audit says 144 x 2")

    S = keys[0]
    h, (f, g, z1, z2, itf, itg) = certificate(S)
    (cf, kf), (cg, kg) = cols[S[f]][0][1], cols[S[g]][0][1]
    columns = []
    for k in S:
        real = cols[k]
        hooks = [r[1] for r in real if r[0] == "h"]
        data = sorted({r[1] for r in real if r[0] == "d"})
        columns.append({"data_qubits": data, "hooks": [[c, 7 - kk] for c, kk in hooks]})  # [check, suffix length]
    hooks_only = [c for c in columns if not c["data_qubits"]]
    edges = []
    for (c, idx) in ((cf, itf), (cg, itg)):
        for z in (z1, z2):
            i, j = term_pair(c, z)
            edges.append({"x": c, "z": z, "index": idx[z][0], "term_pair": [f"A{i + 1}", f"B{j + 1}"]})
    ex = {"hook_f": [cf, 7 - kf], "hook_g": [cg, 7 - kg], "readers": [z1, z2], "holonomy": h, "edges": edges,
          "columns": columns, "n_rigid_hook_columns": len(hooks_only)}
    check({cf, cg} == {45, 59} and {z1, z2} == {58, 60} and h == 2, f"example differs from the audit: {ex}")
    # consistency with delta: the reader index of a single-qubit hit equals delta(term pair) of u11
    du11 = circ["u11"]["delta"]
    for e in edges:
        i, j = int(e["term_pair"][0][1]) - 1, int(e["term_pair"][1][1]) - 1
        check(e["index"] == du11[i][j], f"edge {e} vs delta {du11[i][j]}")
    out = {"delta": {n: circ[n]["delta"] for n in ("ibmg", "g10", "u11")},
           "dcirc": {n: circ[n]["dcirc"] for n in ("ibmg", "g10", "u11")},
           "period": {n: circ[n]["period"] for n in ("ibmg", "g10", "u11")},
           "two_hook_histogram_u11_Z_w10": dict(hist), "example_u11_Z_list0": ex}
    p = ROOT / "paper/figures/fig1_P_data.json"
    p.write_text(json.dumps(out, indent=1))
    print(json.dumps(ex, indent=1))
    print("wrote", p)


if __name__ == "__main__":
    main()
