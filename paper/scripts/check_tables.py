"""Check Table I (both codes), S1, S2 of paper/draft.tex against the schedule specs.

For every class row: CNOT order, CNOT steps (and, where present, reset/measurement
steps) and the map from the Fig. 12 order must equal the output of
extract_class_orders.py.  Usage (repository root):
    uv run python paper/scripts/check_tables.py
Exits non-zero on any mismatch.
"""
import re
import sys

sys.path.insert(0, "paper/scripts")
from extract_class_orders import class_orders, transform_name  # noqa: E402

FIG12 = "results/E-021-gross-new-orders/fig12_spec.json"
TABLES = {
    "tab:circuit": "search/experiments/e024a/cs_P18_H24.json",
    "tab:circB": "search/experiments/e024b/p18w_spec.json",
    "tab:circC": "search/experiments/e021/cand_p21_spec.json",
}


def norm_map(cell):
    toks = re.findall(r"rev|s_\{12\}|s_\{56\}|id", cell)
    return "*".join(t.replace("_{", "").replace("}", "") for t in toks) or "id"


def main():
    tex = open("paper/draft.tex").read()
    ref = class_orders(FIG12)[1]
    bad = 0
    for lab, spec in TABLES.items():
        P, cls = class_orders(spec)
        i = tex.index("\\label{%s}" % lab)
        j = tex.index("\\end{tabular}", i)
        rows = [r for r in tex[i:j].split("\\\\") if re.search(r"\$[XZ]_\d\$", r)]
        assert len(rows) == 6, (lab, len(rows))
        for r in rows:
            cells = [c.strip() for c in r.split("&")]
            m = re.search(r"([XZ])_(\d)", cells[0])
            key = (m.group(1), int(m.group(2)))
            seq, prep, meas = cls[key]
            order = "".join(n for n, _ in seq)
            times = [str(t) for _, t in seq]
            g = transform_name([n for n, _ in ref[key][0]], [n for n, _ in seq])
            t_order = next(c for c in cells if "A_" in c).replace("$", "").replace("_", "")
            t_times = next(c for c in cells if re.fullmatch(r"[\d, ]+", c) and "," in c).replace(" ", "").split(",")
            ok = t_order == order and t_times == times and norm_map(cells[-1]) == g
            if len(cells) == 6:  # reset / meas columns present
                ok = ok and cells[1] == str(prep) and cells[4] == str(meas)
            print(f"{lab:12s} {key[0]}{key[1]} {'OK' if ok else 'MISMATCH'}  order {order}  map {g}")
            bad += not ok
    sys.exit(1 if bad else 0)




def check_bb90():
    """[[90,8,10]] rows of Table I (one row per check type) against search/experiments/e028/c16_spec.json."""
    import json
    tex = open("paper/draft.tex").read()
    d = json.load(open("search/experiments/e028/c16_spec.json"))
    L, M = 15, 3
    A = [("A1", (9, 0)), ("A2", (0, 1)), ("A3", (0, 2))]
    B = [("B1", (0, 0)), ("B2", (2, 0)), ("B3", (7, 0))]

    def idx(a, b):
        return M * (a % L) + (b % M)

    def labels(i, t):
        x, y = divmod(i, M)
        o = {}
        first, second = (A, B) if t == "X" else (B, A)
        sgn = 1 if t == "X" else -1
        for n, (dx, dy) in first:
            o[idx(x + sgn * dx, y + sgn * dy)] = n
        for n, (dx, dy) in second:
            o[45 + idx(x + sgn * dx, y + sgn * dy)] = n
        return o

    i = tex.index("\\label{tab:circuit}")
    j = tex.index("\\end{tabular}", i)
    rows = {}
    for r in tex[i:j].split("\\\\"):
        m = re.search(r"\$([XZ])\$\s*&", r)
        if m:
            rows[m.group(1)] = [c.strip() for c in r[m.start():].split("&")]
    bad = 0
    for t, key in (("X", "x_checks"), ("Z", "z_checks")):
        pats = set()
        for k, c in enumerate(d[key]):
            lab = labels(k, t)
            assert {q for q, _ in c["cnots"]} == set(lab), (t, k)
            pats.add((tuple((lab[q], tt) for q, tt in sorted(c["cnots"], key=lambda e: e[1])), c["prep"], c["meas"]))
        assert len(pats) == 1, t
        seq, prep, meas = next(iter(pats))
        cells = rows[t]
        ok = (cells[2].replace("$", "").replace("_", "") == "".join(n for n, _ in seq)
              and cells[3].replace(" ", "").split(",") == [str(tt) for _, tt in seq]
              and cells[1] == str(prep) and cells[4] == str(meas) and d["period"] == 16)
        print(f"tab:circuit  {t}  ([[90]])  {'OK' if ok else 'MISMATCH'}  order {''.join(n for n, _ in seq)}")
        bad += not ok
    return bad


if __name__ == "__main__":
    bad90 = check_bb90()
    try:
        main()
    except SystemExit as e:
        sys.exit(1 if (e.code or bad90) else 0)
