"""Positive control: rebuild the E-013 BB108 circuit with the generalised E-015 code, export DFS instances,
compare the column set with the auditor's instances (results/E-013-audit/inst_{Z,X}.txt).

    PYTHONPATH=. uv run python search/experiments/e015/validate108.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import OUT, check_orders, colour_symmetry, dump_instance, get_code, homs_to_Zp, proper  # noqa: E402

code = get_code("bb108")
hy = [h for h in homs_to_Zp(code, 2) if (h["u"], h["v"]) == (0, 1)][0]
col = hy["colour"]
blocks = {"X": {0: ((0, 1, 2), (2, 0, 1)), 1: ((2, 1, 0), (2, 0, 1))},
          "Z": {0: ((2, 1, 0), (0, 1, 2)), 1: ((0, 1, 2), (0, 1, 2))}}
expect = {"X": {0: [0, 1, 2, 5, 3, 4], 1: [2, 1, 0, 5, 3, 4]}, "Z": {0: [3, 4, 5, 2, 1, 0], 1: [3, 4, 5, 0, 1, 2]}}
from search.noninterleaved.colour_search import order_terms  # noqa: E402
sym = colour_symmetry(code, col)
print("homs to Z2:", [(h["u"], h["v"]) for h in homs_to_Zp(code, 2)], "sym size", len(sym))
for kind in "XZ":
    for c in (0, 1):
        assert list(order_terms(kind, *blocks[kind][c])) == expect[kind][c]
    assert proper(code, kind, col, blocks[kind])
    orders = check_orders(code, kind, col, blocks[kind])
    info = dump_instance(code, kind, orders, sym, OUT / f"inst_bb108_e013_{kind}.txt")
    print(kind, info)
    aud = Path(f"results/E-013-audit/inst_{kind}.txt")
    if aud.exists():
        A = aud.read_text().split("\n")
        r, n, no = map(int, A[0].split())
        sa = {(int(x.split()[0]), int(x.split()[1])) for x in A[1:1 + n]}
        B = (OUT / f"inst_bb108_e013_{kind}.txt").read_text().split("\n")
        sb = {(int(x.split()[0]) | (int(x.split()[1]) << 64), int(x.split()[2])) for x in B[1:1 + int(B[0].split()[1])]}
        print("  same column set as auditor instance:", sa == sb, len(sa), len(sb), "auditor orbits", no)
