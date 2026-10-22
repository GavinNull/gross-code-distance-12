"""Check the circuit tables of paper/draft.tex against the schedule specs.

- Table I (tab:circuit): period-11 gross circuit (search/experiments/e032/u11_spec.json) and
  period-11 [[90,8,10]] circuit (search/experiments/e030/c11_spec.json); one row per check type.
- Table tab:c16: period-16 [[90,8,10]] circuit (search/experiments/e028/c16_spec.json).
- Tables tab:circA, tab:circB, tab:circC: earlier gross circuits (per colour class, with the map
  from the Fig. 12 order).
For every row: reset step, CNOT order, CNOT steps and measurement step (where present) and the
map (where present) must equal what the spec gives. The script also asserts that the label
convention reproduces every check's support and that all checks of a row share one pattern.
Usage (repository root):  uv run python paper/scripts/check_tables.py   (exit 1 on mismatch)
"""
import json
import re
import sys

sys.path.insert(0, "paper/scripts")
from extract_class_orders import class_orders, transform_name  # noqa: E402

TEX = open("paper/draft.tex").read()
FIG12 = "results/E-021-gross-new-orders/fig12_spec.json"
CODES = {
    "gross": dict(L=12, M=6, A=[("A1", (3, 0)), ("A2", (0, 1)), ("A3", (0, 2))],
                  B=[("B1", (0, 3)), ("B2", (1, 0)), ("B3", (2, 0))]),
    "bb90": dict(L=15, M=3, A=[("A1", (9, 0)), ("A2", (0, 1)), ("A3", (0, 2))],
                 B=[("B1", (0, 0)), ("B2", (2, 0)), ("B3", (7, 0))]),
}


def type_patterns(spec_path, code):
    """Per check type: (order labels, CNOT steps in order from reset, reset, meas); asserts uniformity."""
    c = CODES[code]
    L, M = c["L"], c["M"]
    n = L * M

    def idx(a, b):
        return M * (a % L) + (b % M)

    def labels(i, t):
        x, y = divmod(i, M)
        first, second, sg = (c["A"], c["B"], 1) if t == "X" else (c["B"], c["A"], -1)
        o = {}
        for nm, (dx, dy) in first:
            o[idx(x + sg * dx, y + sg * dy)] = nm
        for nm, (dx, dy) in second:
            o[n + idx(x + sg * dx, y + sg * dy)] = nm
        return o

    d = json.load(open(spec_path))
    P = d["period"]
    out = {}
    for t, key in (("X", "x_checks"), ("Z", "z_checks")):
        pats = set()
        for i, ch in enumerate(d[key]):
            lab = labels(i, t)
            assert {q for q, _ in ch["cnots"]} == set(lab), (spec_path, t, i)
            seq = tuple((lab[q], tt) for q, tt in sorted(ch["cnots"], key=lambda e: (e[1] - ch["prep"]) % P))
            pats.add((seq, ch["prep"], ch["meas"]))
        assert len(pats) == 1, (spec_path, t, len(pats))
        out[t] = next(iter(pats))
    return out


def table_rows(label):
    i = TEX.index("\\label{%s}" % label)
    j = TEX.index("\\end{tabular}", i)
    return [r for r in TEX[i:j].split("\\\\") if "&" in r and re.search(r"\$[XZ](_\d)?\$", r)]


def clean(cell):
    return cell.replace("$", "").replace("_", "").replace(" ", "")


def check_type_table():
    bad = 0
    rows = table_rows("tab:circuit")
    assert len(rows) == 4, len(rows)
    specs = [("gross", "search/experiments/e032/u11_spec.json"), ("bb90", "search/experiments/e030/c11_spec.json")]
    for k, (code, spec) in enumerate(specs):
        pats = type_patterns(spec, code)
        for r in rows[2 * k:2 * k + 2]:
            cells = [c.strip() for c in r.split("&")]
            t = re.search(r"\$([XZ])\$", r).group(1)
            seq, prep, meas = pats[t]
            ok = (clean(cells[3]) == "".join(nm for nm, _ in seq)
                  and cells[4].replace(" ", "").split(",") == [str(tt) for _, tt in seq]
                  and cells[2] == str(prep) and cells[5] == str(meas))
            print(f"tab:circuit  {code:5s} {t}  {'OK' if ok else 'MISMATCH'}  order {''.join(nm for nm, _ in seq)}")
            bad += not ok
    pats = type_patterns("search/experiments/e028/c16_spec.json", "bb90")
    for r in table_rows("tab:c16"):
        cells = [c.strip() for c in r.split("&")]
        t = re.search(r"\$([XZ])\$", r).group(1)
        seq, prep, meas = pats[t]
        ok = (clean(cells[1]) == "".join(nm for nm, _ in seq)
              and cells[2].replace(" ", "").split(",") == [str(tt) for _, tt in seq]
              and (prep, meas) == (0, 15))
        print(f"tab:c16      bb90  {t}  {'OK' if ok else 'MISMATCH'}  order {''.join(nm for nm, _ in seq)}")
        bad += not ok
    return bad


def norm_map(cell):
    toks = re.findall(r"rev|s_\{12\}|s_\{56\}|id", cell)
    return "*".join(t.replace("_{", "").replace("}", "") for t in toks) or "id"


def check_class_tables():
    ref = class_orders(FIG12)[1]
    tables = {"tab:circA": "search/experiments/e024a/cs_P18_H24.json",
              "tab:circB": "search/experiments/e024b/p18w_spec.json",
              "tab:circC": "search/experiments/e021/cand_p21_spec.json"}
    bad = 0
    for lab, spec in tables.items():
        P, cls = class_orders(spec)
        rows = [r for r in table_rows(lab) if re.search(r"\$[XZ]_\d\$", r)]
        assert len(rows) == 6, (lab, len(rows))
        for r in rows:
            cells = [c.strip() for c in r.split("&")]
            m = re.search(r"([XZ])_(\d)", cells[0])
            key = (m.group(1), int(m.group(2)))
            seq, prep, meas = cls[key]
            g = transform_name([n for n, _ in ref[key][0]], [n for n, _ in seq])
            t_order = next(c for c in cells if "A_" in c).replace("$", "").replace("_", "")
            t_times = next(c for c in cells if re.fullmatch(r"[\d, ]+", c) and "," in c).replace(" ", "").split(",")
            ok = (t_order == "".join(n for n, _ in seq) and t_times == [str(t) for _, t in seq]
                  and norm_map(cells[-1]) == g)
            if len(cells) == 6:
                ok = ok and cells[1] == str(prep) and cells[4] == str(meas)
            print(f"{lab:12s} {key[0]}{key[1]} {'OK' if ok else 'MISMATCH'}  map {g}")
            bad += not ok
    return bad


if __name__ == "__main__":
    sys.exit(1 if (check_type_table() + check_class_tables()) else 0)
